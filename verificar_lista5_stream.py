#!/usr/bin/env python3
"""Testa todos os canais do lista5.m3u, resolve playlists HLS encadeados,
valida bytes reais de midia e remove da lista os que nao funcionam."""

import os
import re
import shutil
import sys
import threading
from urllib.parse import urljoin, urlsplit

import requests
from concurrent.futures import ThreadPoolExecutor

M3U_FILE = 'lista5.m3u'
BACKUP_FILE = 'lista5.m3u.bak.pre_teste_stream'
TIMEOUT = 15
MAX_WORKERS = 8
MAX_DEPTH = 6
READ_LIMIT = 200000
COLLAPSE = True

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36')

_local = threading.local()


def session():
    s = getattr(_local, 's', None)
    if s is None:
        s = requests.Session()
        s.headers.update({
            'User-Agent': UA,
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
        })
        _local.s = s
    return s


def get(url, referer=None):
    hdr = {'Referer': referer} if referer else {}
    r = session().get(url, timeout=TIMEOUT, stream=True, headers=hdr)
    try:
        body = r.raw.read(READ_LIMIT, decode_content=True)
    finally:
        r.close()
    return r.status_code, body


def is_playlist(body):
    head = body.lstrip()[:64]
    return head.startswith(b'#EXTM3U') or head.startswith(b'#EXT-X-')


def classify(body):
    probe = body[:4096]
    if probe.count(b'\x47') >= 3:
        return 'ts', True
    if any(tag in probe for tag in (b'ftyp', b'styp', b'moof', b'stmo', b'emsg')):
        return 'fmp4', True
    return None, False


AUDIO_EXT = ('.mp4a', '.aac', '.m4a', '.mp3', '.ac3', '.ec3')
AUDIO_CODECS = ('mp4a', 'ac-3', 'ec-3', 'opus')


def audio_only(text):
    """True se a rendition nao tem video (so audio)."""
    codecs = set()
    for c in re.findall(r'CODECS="([^"]+)"', text):
        codecs.update(x.strip().split('.')[0] for x in c.split(','))
    if codecs:
        has_video = any(c.startswith(('avc', 'hev', 'hvc', 'av01', 'vp9', 'vp0')) for c in codecs)
        has_audio = any(c.startswith(AUDIO_CODECS) for c in codecs)
        if not has_video and has_audio:
            return True

    segs = [l.strip() for l in text.splitlines()
            if l.strip() and not l.startswith('#')]
    if segs and all(s.lower().split('?')[0].endswith(AUDIO_EXT) for s in segs[:5]):
        return True
    return False


def drm_method(text):
    methods = {m for m in re.findall(r'#EXT-X-KEY:METHOD=([A-Z0-9\-]+)', text)
               if m != 'NONE'}
    return methods or None


def children(text, base):
    """Retorna (url, tipo) dos candidatos: variantes primeiro, depois segmentos."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines or not lines[0].startswith('#EXTM3U'):
        return []

    out = []

    if '#EXT-X-STREAM-INF' in text:
        variants = []
        pend = None
        for l in lines:
            if l.startswith('#EXT-X-STREAM-INF'):
                m = re.search(r'BANDWIDTH=(\d+)', l)
                res = re.search(r'RESOLUTION=(\d+)x(\d+)', l)
                bw = int(m.group(1)) if m else 0
                px = int(res.group(1)) * int(res.group(2)) if res else 0
                pend = (bw, px)
            elif not l.startswith('#') and pend is not None:
                variants.append((pend[0], pend[1], urljoin(base, l)))
                pend = None
        variants.sort(key=lambda x: (x[0], x[1]))
        out.extend((v[2], 'master') for v in variants)
        return out

    for l in lines:
        if l.startswith('#EXT-X-MAP'):
            m = re.search(r'URI="([^"]+)"', l)
            if m:
                out.append((urljoin(base, m.group(1)), 'fmp4'))
    for l in lines:
        if not l.startswith('#'):
            out.append((urljoin(base, l), 'ts'))
    out.sort(key=lambda c: 0 if c[1] == 'fmp4' else 1)
    return out


def with_parent_query(child, parent):
    """Akamai hdnea e tokens de sessao precisam ser repassados ao filho."""
    cq = urlsplit(child).query
    pq = urlsplit(parent).query
    if pq and not cq:
        return f'{child}?{pq}'
    return None


def test(url, depth=0, seen=None, drm=None, referer=None):
    """-> (funciona, motivo, eh_master)"""
    if seen is None:
        seen = set()
    if url in seen:
        return False, 'loop_de_url', False
    if depth > MAX_DEPTH:
        return False, 'profundidade_excedida', False
    seen.add(url)

    try:
        status, body = get(url, referer)
    except requests.exceptions.Timeout:
        return False, 'timeout', False
    except requests.exceptions.TooManyRedirects:
        return False, 'muitos_redirects', False
    except requests.exceptions.ConnectionError:
        return False, 'conexao_falha', False
    except requests.exceptions.SSLError:
        return False, 'ssl_invalido', False
    except Exception:
        return False, 'erro_rede', False

    if status in (401, 403):
        return False, f'http_{status}', False
    if status == 404:
        return False, 'http_404', False
    if status >= 400:
        return False, f'http_{status}', False
    if not body:
        return False, 'resposta_vazia', False

    if not is_playlist(body):
        kind, good = classify(body)
        if good:
            return True, f'ok_{kind}', False
        low = body[:80].lower()
        if b'<html' in low or b'<!doctype' in low:
            return False, 'html_em_vez_de_m3u8', False
        return False, 'resposta_nao_m3u8', False

    text = body.decode('utf-8', errors='replace')
    is_master = '#EXT-X-STREAM-INF' in text
    if '<html' in text[:600].lower():
        return False, 'html_em_vez_de_m3u8', is_master

    m = re.search(r'#EXT-X-KEY:METHOD=([A-Z0-9\-]+)', text)
    if m and m.group(1) != 'NONE':
        drm = drm or m.group(1)

    if audio_only(text):
        return False, 'som_audio_sem_video', is_master
    if drm and drm.startswith(('SAMPLE-AES', 'SAMPLE-AES-CTR')):
        return False, f'drm_{drm.lower()}', is_master

    kids = children(text, url)
    if not kids:
        return False, 'sem_variant_nem_segmento', is_master

    errors = []
    queue = []
    for cu, kind in kids[:5]:
        queue.append((cu, kind))
        alt = with_parent_query(cu, url)
        if alt:
            queue.append((alt, kind))

    for cu, kind in queue:
        try:
            sstatus, sbody = get(cu, referer=url)
        except requests.exceptions.Timeout:
            errors.append('seg_timeout')
            continue
        except requests.exceptions.MissingSchema:
            continue
        except Exception:
            errors.append('seg_erro_rede')
            continue

        if sstatus != 200:
            errors.append(f'seg_http_{sstatus}')
            continue
        if not sbody:
            continue

        if is_playlist(sbody):
            ok, reason, _m = test(cu, depth + 1, seen, drm, referer=url)
            if ok:
                return ok, reason, False
            errors.append(reason)
            continue

        mtype, good = classify(sbody)
        if good:
            return True, f'ok_{mtype}', is_master
        errors.append('segmento_nao_reconhecido')

    return False, next((e for e in errors if e.startswith(('seg_http', 'timeout'))),
                       errors[0] if errors else 'sem_candidatos_validos'), is_master


def parse_m3u(path):
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        lines = f.read().splitlines()

    header, entries, pending = [], [], []
    for line in lines:
        s = line.strip()
        if not s:
            continue
        if s.startswith('#EXTM3U'):
            header.append(line)
        elif s.startswith('#'):
            pending.append(line)
        elif s.startswith(('http://', 'https://')):
            entries.append({'meta': pending, 'url': line})
            pending = []
        else:
            pending.append(line)
    return header, entries


def channel_name(meta):
    """Nome do canal: tudo apos a primeira virgula fora de aspas."""
    for m in meta:
        if not m.startswith('#EXTINF'):
            continue
        in_q = False
        for i, ch in enumerate(m):
            if ch == '"':
                in_q = not in_q
            elif ch == ',' and not in_q:
                return m[i + 1:].strip()
    return '(sem nome)'


def label(u):
    parts = urlsplit(u)
    return f"{parts.netloc[:26]}/{parts.path.rstrip('/').split('/')[-1][:32]}"


def main():
    if not os.path.exists(M3U_FILE):
        print(f'Arquivo {M3U_FILE} nao encontrado')
        return 1

    shutil.copy2(M3U_FILE, BACKUP_FILE)
    header, entries = parse_m3u(M3U_FILE)
    uniq = sorted({e['url'].strip() for e in entries})

    print(f'Backup: {BACKUP_FILE}')
    print(f'Entradas: {len(entries)} | URLs unicas: {len(uniq)}')
    print(f'Testando com {MAX_WORKERS} workers (manifest + segmentos reais)...\n')

    results = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        for url, res in zip(uniq, ex.map(test, uniq)):
            results[url] = res

    ok_urls = [u for u in uniq if results[u][0]]
    print(f'FUNCIONANDO: {len(ok_urls)}/{len(uniq)}')
    print(f'QUEBRADOS:   {len(uniq) - len(ok_urls)}/{len(uniq)}\n')
    for u in uniq:
        ok, reason, master = results[u]
        tag = 'master' if master else '     '
        print(f"  {'[OK]' if ok else '[--]'} {label(u):<52} {tag}  {reason}")

    working = [e for e in entries if results.get(e['url'].strip(), (False, '', False))[0]]

    if COLLAPSE:
        groups = {}
        for e in working:
            groups.setdefault(channel_name(e['meta']), []).append(e)
        collapsed, redundant = [], 0
        for name, items in groups.items():
            masters = [e for e in items if results[e['url'].strip()][2]]
            keep = masters or items[:1]
            collapsed.extend(keep)
            redundant += len(items) - len(keep)
        working = collapsed
    else:
        redundant = 0

    order = {u: i for i, u in enumerate(uniq)}
    working.sort(key=lambda e: (order.get(e['url'].strip(), 1 << 30),
                                channel_name(e['meta'])))

    seen, out = set(), list(header) or ['#EXTM3U']
    kept = 0

    print('\n--- Removidos ---')
    dropped = {}
    for e in entries:
        u = e['url'].strip()
        ok, reason = results.get(u, (False, 'nao_testado', False))[:2]
        if not ok:
            dropped[channel_name(e['meta'])] = dropped.get(
                channel_name(e['meta']), reason)
    for name, reason in dropped.items():
        print(f'  {name[:66]:<68} {reason}')

    for e in working:
        u = e['url'].strip()
        if u in seen:
            continue
        seen.add(u)
        kept += 1
        out.extend(e['meta'])
        out.append(e['url'])

    with open(M3U_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(out) + '\n')

    print(f'\n--- Canais finais ({kept}) ---')
    for e in working:
        print(f"  {channel_name(e['meta'])[:60]:<62} {results[e['url'].strip()][1]}")

    print(f'\nEntradas antes: {len(entries)} | depois: {kept}')
    print(f'Removidos (nao funcionam): {len(entries) - len(entries)} '
          f'| Duplicados/renditions redundantes: {redundant}')
    print(f'Sobrescrito: {M3U_FILE}')
    return 0


if __name__ == '__main__':
    sys.exit(main())