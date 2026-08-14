#!/usr/bin/env python3
"""Test all unique streams in lista5.m3u, keep working channels, rewrite file."""
import subprocess
import re
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

M3U_FILE = 'lista5.m3u'
TIMEOUT = 25

def parse_m3u(filepath):
    entries = []
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = [l.rstrip('\n') for l in f.readlines()]
    i = 0
    while i < len(lines):
        if lines[i].startswith('#EXTINF:'):
            extinf = lines[i]
            i += 1
            if i < len(lines) and lines[i].strip() and not lines[i].startswith('#'):
                url = lines[i].strip()
                entries.append((extinf, url))
        i += 1
    return entries

def test_url(url):
    try:
        result = subprocess.run(
            ['curl', '-s', '-L', '--max-time', str(TIMEOUT),
             '--connect-timeout', '10', '-A',
             'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
             '-w', '\n__HTTP_CODE:%{http_code}__', url],
            capture_output=True, text=True, timeout=TIMEOUT + 5
        )
        body = result.stdout
        m = re.search(r'__HTTP_CODE:(\d+)__$', body)
        code = int(m.group(1)) if m else 0
        content = body[:m.start()] if m else body
        if code == 200:
            if '#EXTM3U' in content or '#EXT-X-' in content or '#EXTINF' in content:
                return True, 'm3u8 válido'
            if content and '<html' not in content.lower() and '<!doctype' not in content.lower():
                return True, 'respondeu'
            return False, 'página HTML de erro'
        if code == 403:
            return False, '403 Forbidden'
        if code == 404:
            return False, '404 Not Found'
        return False, f'HTTP {code}'
    except subprocess.TimeoutExpired:
        return False, 'timeout'
    except Exception as e:
        return False, str(e)[:50]

def main():
    if not os.path.exists(M3U_FILE):
        print(f'{M3U_FILE} não encontrado')
        return

    backup = f"{M3U_FILE}.bak.{time.strftime('%Y%m%d_%H%M%S')}"
    os.system(f'cp {M3U_FILE} {backup}')
    print(f'Backup: {backup}')

    entries = parse_m3u(M3U_FILE)
    print(f'Total de entradas: {len(entries)}')

    unique_urls = list(dict.fromkeys(url for _, url in entries))
    print(f'URLs únicas a testar: {len(unique_urls)}')

    results = {}
    print('Testando streams...')
    with ThreadPoolExecutor(max_workers=8) as executor:
        future_to_url = {executor.submit(test_url, url): url for url in unique_urls}
        for i, future in enumerate(as_completed(future_to_url)):
            url = future_to_url[future]
            ok, msg = future.result()
            results[url] = (ok, msg)
            name = ''
            for extinf, u in entries:
                if u == url:
                    m2 = re.search(r',(.+)$', extinf)
                    if m2:
                        name = m2.group(1).strip()[:50]
                    break
            print(f'  [{i+1}/{len(unique_urls)}] {"OK" if ok else "FALHOU"} ({msg}) - {name}')

    new_entries = []
    removed = []
    for extinf, url in entries:
        ok, msg = results.get(url, (False, 'não testado'))
        if ok:
            new_entries.append((extinf, url))
        else:
            m2 = re.search(r',(.+)$', extinf)
            name = m2.group(1).strip() if m2 else url[:80]
            removed.append((name, msg))

    print(f'\nCanais mantidos: {len(new_entries)}')
    print(f'Canais removidos: {len(removed)}')
    for name, msg in removed:
        print(f'  - {name} ({msg})')

    with open(M3U_FILE, 'w', encoding='utf-8') as f:
        f.write('#EXTM3U\n')
        for extinf, url in new_entries:
            f.write(extinf + '\n')
            f.write(url + '\n')

    print(f'\n{os.path.abspath(M3U_FILE)} sobrescrito!')

if __name__ == '__main__':
    main()
