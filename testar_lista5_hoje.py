#!/usr/bin/env python3
"""Test all channels in lista5.m3u and remove dead ones."""

import subprocess
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

FILEPATH = '/home/runner/work/JCTVV/JCTVV/lista5.m3u'


def test_url(url, timeout=20):
    """Test if an HLS stream URL returns valid m3u8 content."""
    try:
        result = subprocess.run(
            ['curl', '-s', '-L', '--max-time', str(timeout),
             '--connect-timeout', '10',
             '-H', 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
             url],
            capture_output=True, text=True, timeout=timeout + 5
        )
        if result.returncode != 0:
            return False, f"curl error {result.returncode}"
        body = result.stdout.strip()
        if not body:
            return False, "empty response"
        if '#EXTM3U' in body or '#EXT-X-' in body or '#EXTINF' in body:
            return True, "valid m3u8"
        if '.ts' in body or '.m3u8' in body:
            return True, "valid m3u8 (variant)"
        if '<html' in body.lower() or '<!doctype' in body.lower():
            return False, "HTML error page"
        if re.search(r'HTTP/\S+\s+(4|5)\d\d', body[:200]):
            return False, "HTTP error in body"
        return False, f"unknown content: {body[:80]}"
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except Exception as e:
        return False, str(e)[:80]


def parse_m3u(filepath):
    entries = []
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = [l.rstrip('\n') for l in f.readlines()]
    i = 0
    while i < len(lines):
        if lines[i].startswith('#EXTINF:'):
            extinf = lines[i]
            i += 1
            while i < len(lines) and lines[i].strip() and not lines[i].startswith('#'):
                entries.append((extinf, lines[i].strip()))
                i += 1
            i -= 1
        i += 1
    return entries


def name_of(extinf):
    m = re.search(r',(.+)$', extinf)
    return m.group(1).strip() if m else extinf


def main():
    entries = parse_m3u(FILEPATH)
    print(f"Total de entradas: {len(entries)}")

    unique_urls = list(dict.fromkeys(url for _, url in entries))
    print(f"URLs únicas para testar: {len(unique_urls)}")

    results = {}
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_url = {executor.submit(test_url, url): url for url in unique_urls}
        for i, future in enumerate(as_completed(future_to_url)):
            url = future_to_url[future]
            ok, msg = future.result()
            results[url] = (ok, msg)
            status = "OK" if ok else f"FALHOU ({msg})"
            print(f"  [{i+1}/{len(unique_urls)}] {status} - {name_of(next(e for e, u in entries if u == url))[:60]}")

    working = sum(1 for ok, _ in results.values() if ok)
    failed = sum(1 for ok, _ in results.values() if not ok)
    print(f"\nFuncionando: {working} URLs | Falhando: {failed} URLs")

    removed = 0
    kept = 0
    lines = ['#EXTM3U']
    for extinf, url in entries:
        if results.get(url, (False, 'not_tested'))[0]:
            lines.append(extinf)
            lines.append(url)
            kept += 1
        else:
            removed += 1

    print(f"\nMantidas: {kept} entradas | Removidas: {removed} entradas")

    with open(FILEPATH, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')

    print(f"Arquivo {FILEPATH} sobrescrito com sucesso!")

    if removed:
        print("\nCanais removidos:")
        seen = set()
        for extinf, url in entries:
            ok, msg = results.get(url, (False, 'not_tested'))
            if not ok and url not in seen:
                print(f"  - {name_of(extinf)} ({msg})")
                seen.add(url)


if __name__ == '__main__':
    main()
