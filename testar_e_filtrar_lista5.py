#!/usr/bin/env python3
"""Testa todos os canais do lista5.m3u, remove os que nao funcionam e sobrescreve o arquivo."""

import re
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

FILE = Path(__file__).parent / 'lista5.m3u'
MAX_WORKERS = 10


from urllib.parse import urljoin


def fetch(url, timeout=15):
    result = subprocess.run(
        ['curl', '-s', '-L', '--max-time', str(timeout),
         '--connect-timeout', '8',
         '-A', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
         url],
        capture_output=True, text=True, timeout=timeout + 5
    )
    if result.returncode != 0:
        return None, f'curl error {result.returncode}'
    body = result.stdout.strip()
    if not body:
        return None, 'empty response'
    if '<html' in body.lower() or '<!doctype' in body.lower():
        return None, 'HTML error page'
    return body, None


def test_url_deep(url, timeout=15):
    body, err = fetch(url, timeout)
    if err:
        return False, err

    if not ('#EXTM3U' in body or '#EXT-X-' in body or '#EXTINF' in body or '.m3u8' in body):
        return False, f'unknown content: {body[:80]}'

    keys = re.findall(r'#EXT-X-KEY:METHOD=([^,]+)', body)
    if 'SAMPLE-AES-CTR' in keys or 'SAMPLE-AES' in keys:
        return False, 'DRM (SAMPLE-AES) - nao reproduzivel'

    variants = re.findall(r'#EXT-X-STREAM-INF:[^\n]*\n([^\n]+)', body)
    if variants:
        for var in variants[:4]:
            vbody, verr = fetch(urljoin(url, var.strip()), timeout)
            if verr:
                return False, f'variante falhou: {verr}'
            vkeys = re.findall(r'#EXT-X-KEY:METHOD=([^,]+)', vbody)
            if 'SAMPLE-AES-CTR' in vkeys or 'SAMPLE-AES' in vkeys:
                return False, 'DRM (SAMPLE-AES) nas variantes'
        return True, 'valid m3u8 (master)'

    codecs = re.findall(r'CODECS="([^"]+)"', body)
    if codecs and all('audio' in c.lower() and 'video' not in c.lower() for c in codecs):
        return False, 'audio-only (sem video)'
    if 'audio-aac-' in url.lower() and 'video' not in url.lower():
        return False, 'audio-only (sem video)'

    return True, 'valid m3u8'


def parse_m3u(filepath):
    lines = filepath.read_text(encoding='utf-8').splitlines()
    entries = []
    i = 0
    while i < len(lines):
        if lines[i].startswith('#EXTINF:'):
            extinf = lines[i]
            i += 1
            while i < len(lines) and (lines[i].startswith('#') and not lines[i].startswith('#EXTINF:')):
                i += 1
            if i < len(lines) and lines[i].strip() and not lines[i].startswith('#'):
                url = lines[i].strip()
                entries.append((extinf, url))
        i += 1
    return entries


def name_from(extinf):
    m = re.search(r',(.+)$', extinf)
    return m.group(1).strip() if m else '?'


def main():
    entries = parse_m3u(FILE)
    print(f'Total de entradas: {len(entries)}')

    unique_urls = list(dict.fromkeys(url for _, url in entries))
    print(f'URLs unicas para testar: {len(unique_urls)}')

    results = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_url = {executor.submit(test_url_deep, url): url for url in unique_urls}
        for i, future in enumerate(as_completed(future_to_url), 1):
            url = future_to_url[future]
            ok, msg = future.result()
            results[url] = (ok, msg)
            label = next((name_from(e) for e, u in entries if u == url), url[:60])
            status = 'OK' if ok else f'FALHOU ({msg})'
            print(f'  [{i}/{len(unique_urls)}] {status} - {label}')

    kept = []
    removed = []
    for extinf, url in entries:
        ok, msg = results.get(url, (False, 'unknown'))
        if ok:
            kept.append((extinf, url))
        else:
            removed.append((extinf, url, msg))

    print(f'\nRemovidas: {len(removed)}')
    print(f'Mantidas: {len(kept)}')

    if removed:
        print('\nCanais removidos:')
        seen = set()
        for extinf, url, msg in removed:
            if (extinf, url) in seen:
                continue
            seen.add((extinf, url))
            print(f'  - {name_from(extinf)} ({msg})')

    if kept:
        FILE.write_text('#EXTM3U\n' + ''.join(f'{e}\n{u}\n' for e, u in kept), encoding='utf-8')
        print(f'\nArquivo {FILE.name} sobrescrito com {len(kept)} canais.')
    else:
        print('\nNenhum canal funcionando, arquivo inalterado.')


if __name__ == '__main__':
    main()
