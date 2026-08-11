#!/usr/bin/env python3
"""Test all streams in lista5.m3u, remove dead channels, overwrite the file."""

import subprocess
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

FILEPATH = '/home/runner/work/JCTVV/JCTVV/lista5.m3u'


def test_url(url, timeout=25):
    """Test if an HLS stream URL returns valid m3u8 content."""
    try:
        result = subprocess.run(
            ['curl', '-s', '-L', '--max-time', str(timeout),
             '--connect-timeout', '10', '-A',
             'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
             url],
            capture_output=True, text=True, timeout=timeout + 5
        )
        if result.returncode != 0:
            return False, f"curl error {result.returncode}"

        body = result.stdout.strip()
        if not body:
            return False, "empty response"

        # Valid m3u8 content indicators
        if '#EXTM3U' in body or '#EXT-X-' in body or '#EXTINF' in body:
            return True, "valid m3u8"
        if '.ts' in body or '.m3u8' in body:
            return True, "valid m3u8 (variant)"

        # Error pages
        if body.startswith('HTTP/'):
            code = body.split(' ')[1] if len(body.split(' ')) > 1 else '?'
            return False, f"HTTP {code}"
        if '<html' in body.lower() or '<!doctype' in body.lower():
            return False, "HTML error page"
        if 'error' in body.lower() and len(body) < 2000:
            return False, "error body"

        return False, f"unknown content: {body[:80]}"

    except subprocess.TimeoutExpired:
        return False, "timeout"
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
            while i < len(lines) and (lines[i].strip() == '' or lines[i].startswith('#')):
                i += 1
            if i < len(lines):
                url = lines[i].strip()
                entries.append((extinf, url))
        i += 1
    return entries


def main():
    entries = parse_m3u(FILEPATH)
    print(f"Total de entradas: {len(entries)}")

    unique_urls = list(set(url for _, url in entries))
    print(f"URLs únicas para testar: {len(unique_urls)}")

    results = {}
    with ThreadPoolExecutor(max_workers=8) as executor:
        future_to_url = {executor.submit(test_url, url): url for url in unique_urls}
        done = 0
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            ok, msg = future.result()
            results[url] = (ok, msg)
            done += 1
            name = ""
            for extinf, u in entries:
                if u == url:
                    m = re.search(r',([^,]+)$', extinf)
                    if m:
                        name = m.group(1).strip()[:50]
                    break
            status = "OK " if ok else "FALHOU"
            print(f"  [{done}/{len(unique_urls)}] {status} ({msg}) - {name}")

    new_entries = []
    removed = 0
    for extinf, url in entries:
        ok, _ = results.get(url, (False, "?"))
        if ok:
            new_entries.append((extinf, url))
        else:
            removed += 1

    print(f"\nMantidas: {len(new_entries)}")
    print(f"Removidas: {removed}")

    with open(FILEPATH, 'w') as f:
        f.write('#EXTM3U\n')
        for extinf, url in new_entries:
            f.write(extinf + '\n')
            f.write(url + '\n')

    print(f"Arquivo sobrescrito: {FILEPATH}")

    if removed > 0:
        print("\nCanais removidos:")
        seen = set()
        for extinf, url in entries:
            ok, reason = results.get(url, (False, "?"))
            if not ok and url not in seen:
                m = re.search(r',([^,]+)$', extinf)
                name = m.group(1).strip() if m else url[:80]
                print(f"  - {name}  [{reason}]")
                seen.add(url)


if __name__ == '__main__':
    main()
