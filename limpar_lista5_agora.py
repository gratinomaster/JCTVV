#!/usr/bin/env python3
"""Testa todos os canais de lista5.m3u e remove os que nao funcionam."""

import re
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

FILE = '/home/runner/work/JCTVV/JCTVV/lista5.m3u'


def test_url(url, timeout=15):
    try:
        result = subprocess.run(
            ['curl', '-s', '-L', '--max-time', str(timeout),
             '--connect-timeout', '8',
             '-A', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
             url],
            capture_output=True, text=True, timeout=timeout + 5
        )
        if result.returncode != 0:
            return False, f'curl error {result.returncode}'

        body = result.stdout.strip()
        if not body:
            return False, 'resposta vazia'

        low = body[:500].lower()
        if low.startswith('http/'):
            if ' 200 ' not in low:
                return False, low.split('\r\n')[0]

        if '#extm3u' in low or '#ext-x-' in low or '#extinf' in low:
            return True, 'm3u8 valido'
        if '.ts' in body or '.m3u8' in body:
            return True, 'm3u8 variante'

        if '<html' in low or '<!doctype' in low or '<head' in low:
            return False, 'página HTML de erro'

        return False, f'conteúdo desconhecido: {body[:80]}'

    except subprocess.TimeoutExpired:
        return False, 'timeout'
    except Exception as e:
        return False, str(e)


def parse_m3u(filepath):
    entries = []
    with open(filepath, 'r') as f:
        lines = [l.rstrip('\n') for l in f.readlines()]
    i = 0
    while i < len(lines):
        if lines[i].startswith('#EXTINF:'):
            extinf = lines[i]
            i += 1
            if i < len(lines) and lines[i].strip() and not lines[i].startswith('#'):
                entries.append((extinf, lines[i].strip()))
            else:
                i -= 1
        i += 1
    return entries


def main():
    entries = parse_m3u(FILE)
    print(f'Total de entradas: {len(entries)}')

    unique_urls = list(set(url for _, url in entries))
    print(f'URLs unicas para testar: {len(unique_urls)}')

    results = {}
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_url = {executor.submit(test_url, url): url for url in unique_urls}
        for i, future in enumerate(as_completed(future_to_url)):
            url = future_to_url[future]
            ok, msg = future.result()
            results[url] = (ok, msg)
            name = ''
            for extinf, u in entries:
                if u == url:
                    m = re.search(r',(.+)$', extinf)
                    if m:
                        name = m.group(1).strip()[:60]
                    break
            status = 'OK' if ok else f'FALHOU ({msg})'
            print(f'  [{i+1}/{len(unique_urls)}] {status} - {name}')

    new_entries = []
    removed = []
    for extinf, url in entries:
        ok, msg = results.get(url, (False, 'nao testado'))
        if ok:
            new_entries.append((extinf, url))
        else:
            removed.append((extinf, url, msg))

    print(f'\nRemovidas: {len(removed)} entradas')
    print(f'Mantidas: {len(new_entries)} entradas')

    if removed:
        print('\nCanais removidos:')
        seen = set()
        for extinf, url, msg in removed:
            if url in seen:
                continue
            seen.add(url)
            m = re.search(r',(.+)$', extinf)
            name = m.group(1).strip() if m else url[:80]
            print(f'  - {name} ({msg})')

    if not new_entries:
        print('Nenhum canal valido, arquivo nao alterado.')
        return

    with open(FILE, 'w') as f:
        f.write('#EXTM3U\n')
        for extinf, url in new_entries:
            f.write(extinf + '\n')
            f.write(url + '\n')

    print(f'\nArquivo {FILE} sobrescrito com sucesso!')


if __name__ == '__main__':
    main()
