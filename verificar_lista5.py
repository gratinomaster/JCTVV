#!/usr/bin/env python3
import os
import re
import shutil
import sys
import time
import requests
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin, urlparse

M3U_FILE = 'lista5.m3u'
BACKUP_FILE = 'lista5.m3u.bak.pre_teste'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36'
HDRS = {'User-Agent': UA}
TIMEOUT = 12


def get(url, timeout=TIMEOUT, read=200000):
    r = requests.get(url, headers=HDRS, timeout=timeout, stream=True)
    data = b''
    try:
        for chunk in r.iter_content(4096):
            data += chunk
            if len(data) >= read:
                break
    finally:
        r.close()
    return r.status_code, data.decode('utf-8', errors='replace')


def is_master(text):
    return '#EXT-X-STREAM-INF' in text


def variants(text, base):
    out = []
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        if ln.startswith('#EXT-X-STREAM-INF'):
            for nxt in lines[i + 1:]:
                nxt = nxt.strip()
                if not nxt or nxt.startswith('#'):
                    continue
                out.append(urljoin(base, nxt))
                break
    return out


def segments(text, base):
    segs = []
    in_target = None
    for ln in text.splitlines():
        ln = ln.strip()
        if ln.startswith('#EXT-X-MEDIA-SEQUENCE:'):
            in_target = None
        elif ln.startswith('#EXTINF:'):
            in_target = ln
        elif in_target is not None and not ln.startswith('#'):
            segs.append(urljoin(base, ln))
            in_target = None
            if len(segs) >= 3:
                break
    if segs:
        return segs
    return [urljoin(base, ln.strip()) for ln in text.splitlines()
            if ln.strip() and not ln.strip().startswith('#')][:3]


def segment_ok(url):
    try:
        code, body = get(url, timeout=10, read=512)
        if code != 200 or not body:
            return False
        low = body[:64].lower()
        if low.startswith('#extm3u'):
            return get(url, timeout=8, read=400)[0] == 200
        return b'\x00' in body.encode('utf-8', errors='ignore') or len(body) > 128
    except Exception:
        return False


def test_entry(url, depth=0):
    if depth > 2:
        return False, 'profundidade'
    try:
        code, text = get(url)
    except requests.exceptions.Timeout:
        return False, 'timeout'
    except requests.exceptions.TooManyRedirects:
        return False, 'redirect_loop'
    except Exception as e:
        return False, type(e).__name__

    if code in (401, 403):
        return False, f'http_{code}'
    if code == 404 or code == 410:
        return False, f'http_{code}'
    if code != 200:
        return False, f'http_{code}'
    if '#EXTM3U' not in text:
        return False, 'sem_manifest'

    if is_master(text):
        vs = variants(text, url)
        if not vs:
            return False, 'master_sem_variantes'
        for v in vs[:6]:
            ok, why = test_entry(v, depth + 1)
            if ok:
                return True, 'master_ok'
        return False, f'master_falhou({why})'

    segs = segments(text, url)
    if not segs:
        return False, 'media_sem_segmentos'
    if segment_ok(segs[0]):
        return True, 'media_ok'
    return False, 'segmento_invalido'


def parse_m3u(path):
    with open(path, 'r', encoding='utf-8') as f:
        raw = f.read().splitlines()

    entries = []
    pending = []
    extinf = None
    for line in raw:
        s = line.strip()
        if not s:
            continue
        if s.startswith('#EXTM3U'):
            continue
        if s.startswith('#EXTINF:'):
            extinf = line
            continue
        if s.startswith('#'):
            if extinf and not entries:
                pending.append(line)
            continue
        if extinf is not None:
            entries.append({'extinf': extinf, 'pre': pending, 'url': s})
            extinf, pending = None, []
    return entries


def main():
    if not os.path.exists(M3U_FILE):
        print('Arquivo nao encontrado')
        sys.exit(1)

    entries = parse_m3u(M3U_FILE)
    print(f'Entradas encontradas: {len(entries)}')

    shutil.copy2(M3U_FILE, BACKUP_FILE)
    print(f'Backup: {BACKUP_FILE}\n')

    urls = [e['url'] for e in entries]
    results = {}
    done = 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        for url, (ok, why) in zip(urls, ex.map(lambda u: test_entry(u), urls)):
            results[url] = (ok, why)
            done += 1
            status = 'OK  ' if ok else 'FAIL'
            print(f'[{done:>3}/{len(urls)}] {status} {why:<24} {url[:110]}')

    seen = set()
    kept = []
    removed = []
    for e in entries:
        ok, why = results[e['url']]
        if not ok:
            removed.append((e, why))
            continue
        key = e['url']
        if key in seen:
            removed.append((e, 'duplicado'))
            continue
        seen.add(key)
        kept.append(e)

    out = ['#EXTM3U']
    for e in kept:
        out.extend(e['pre'])
        out.append(e['extinf'])
        out.append(e['url'])

    with open(M3U_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(out) + '\n')

    print('\n' + '=' * 60)
    print(f'Mantidos:  {len(kept)}')
    print(f'Removidos: {len(removed)}')
    print(f'Sobrescrito: {M3U_FILE}')
    print('=' * 60)
    for e, why in removed:
        name = re.sub(r'.*,', '', e['extinf'])[:70]
        print(f'  - {name}  [{why}]')

    by_reason = {}
    for _, why in removed:
        by_reason[why] = by_reason.get(why, 0) + 1
    if by_reason:
        print('\nResumo de falhas:')
        for r, c in sorted(by_reason.items(), key=lambda x: -x[1]):
            print(f'  {r}: {c}')


if __name__ == '__main__':
    main()
