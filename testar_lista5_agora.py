#!/usr/bin/env python3
"""Testa todos os canais de lista5.m3u e remove os que nao funcionam."""

import subprocess
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

FILE = 'lista5.m3u'
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/125.0 Safari/537.36')


def test_url(url, timeout=25):
    """Busca a URL e verifica se responde um m3u8 valido."""
    try:
        result = subprocess.run(
            ['curl', '-s', '-L', '--max-time', str(timeout),
             '--connect-timeout', '10', '-A', UA, '-o', '-', '-w',
             '\n__HTTP__%{http_code}', url],
            capture_output=True, text=True, timeout=timeout + 5
        )
    except subprocess.TimeoutExpired:
        return False, 'timeout'

    if result.returncode != 0:
        return False, f'curl error {result.returncode}'

    body = result.stdout
    http_code = ''
    m = re.search(r'__HTTP__(\d+)', body)
    if m:
        http_code = m.group(1)
        body = body[:m.start()]

    if http_code not in ('200', '206'):
        return False, f'HTTP {http_code or "?"}'

    if '#EXTM3U' in body or '#EXT-X-' in body or '#EXTINF' in body:
        return True, f'HTTP {http_code} (m3u8 ok)'

    low = body.lower()
    if '<html' in low or '<!doctype' in low or 'error' in low[:500]:
        return False, f'HTTP {http_code} mas conteudo nao e m3u8'

    if body.strip():
        return True, f'HTTP {http_code} (conteudo nao-vazio)'
    return False, f'HTTP {http_code} vazio'


def parse_m3u(filepath):
    """Retorna lista de grupos (extinf, [urls])."""
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = [l.rstrip('\n') for l in f]

    groups = []
    cur_extinf = None
    cur_urls = []
    for line in lines:
        if line.startswith('#EXTM3U'):
            continue
        if line.startswith('#EXTINF:'):
            if cur_extinf is not None:
                groups.append((cur_extinf, cur_urls))
            cur_extinf = line
            cur_urls = []
        elif line.startswith('http://') or line.startswith('https://'):
            cur_urls.append(line)
    if cur_extinf is not None:
        groups.append((cur_extinf, cur_urls))
    return groups


def name_of(extinf):
    m = re.search(r',(.+)$', extinf)
    return m.group(1).strip() if m else extinf


def main():
    groups = parse_m3u(FILE)
    if not groups:
        print('Nenhum grupo encontrado em', FILE)
        sys.exit(1)

    urls = []
    for _, us in groups:
        for u in us:
            if u not in urls:
                urls.append(u)

    print(f'Grupos: {len(groups)} | URLs unicas: {len(urls)}')

    results = {}
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(test_url, u): u for u in urls}
        for i, fut in enumerate(as_completed(futs), 1):
            u = futs[fut]
            ok, msg = fut.result()
            results[u] = (ok, msg)
            print(f'  [{i}/{len(urls)}] {"OK " if ok else "FAIL"} - {msg[:60]}')

    kept = []
    removed = []
    for extinf, us in groups:
        working = [u for u in us if results.get(u, (False, ''))[0]]
        if working:
            kept.append((extinf, working))
        else:
            removed.append((extinf, us))

    print(f'\nMantidos: {len(kept)} grupos | Removidos: {len(removed)} grupos')

    with open(FILE, 'w', encoding='utf-8') as f:
        f.write('#EXTM3U\n')
        for extinf, us in kept:
            f.write(extinf + '\n')
            for u in us:
                f.write(u + '\n')

    print('lista5.m3u sobrescrito.')

    if removed:
        print('\nCanais removidos:')
        for extinf, us in removed:
            reasons = '; '.join(results.get(u, (False, 'nao testado'))[1] for u in us)
            print(f'  - {name_of(extinf)[:70]} [{reasons[:70]}]')


if __name__ == '__main__':
    main()
