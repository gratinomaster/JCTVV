#!/usr/bin/env python3
"""Test all streams in lista5.m3u - deeper validation."""

import subprocess
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

def test_url_deep(url, timeout=20):
    """Test if an HLS stream URL returns valid m3u8 content."""
    try:
        result = subprocess.run(
            ['curl', '-s', '-L', '--max-time', str(timeout),
             '--connect-timeout', '10', url],
            capture_output=True, text=True, timeout=timeout + 5
        )
        if result.returncode != 0:
            return False, f"curl error {result.returncode}"

        body = result.stdout.strip()
        if not body:
            return False, "empty response"

        # Check for HTTP error in body
        if body.startswith('HTTP/') and '403' in body[:200]:
            return False, "403 Forbidden"
        if body.startswith('HTTP/') and '404' in body[:200]:
            return False, "404 Not Found"

        # Valid m3u8 content indicators
        if '#EXTM3U' in body or '#EXT-X-' in body or '#EXTINF' in body:
            return True, "valid m3u8"
        if '.ts' in body or '.m3u8' in body:
            return True, "valid m3u8 (variant)"

        # Check if it's an error page
        if '<html' in body.lower() or '<!doctype' in body.lower():
            return False, "HTML error page"

        return False, f"unknown content: {body[:100]}"

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
            if i < len(lines) and lines[i].strip() and not lines[i].startswith('#'):
                url = lines[i].strip()
                entries.append((extinf, url))
            else:
                i -= 1
        i += 1
    return entries

def main():
    filepath = '/home/runner/work/JCTVV/JCTVV/lista5.m3u'
    entries = parse_m3u(filepath)
    print(f"Total de entradas: {len(entries)}")

    unique_urls = list(set(url for _, url in entries))
    print(f"URLs únicas para testar: {len(unique_urls)}")

    results = {}
    with ThreadPoolExecutor(max_workers=8) as executor:
        future_to_url = {executor.submit(test_url_deep, url): url for url in unique_urls}
        for i, future in enumerate(as_completed(future_to_url)):
            url = future_to_url[future]
            ok, msg = future.result()
            results[url] = ok
            name = ""
            for extinf, u in entries:
                if u == url:
                    m = re.search(r',(.+)$', extinf)
                    if m:
                        name = m.group(1).strip()[:60]
                    break
            status = "OK" if ok else f"FALHOU ({msg})"
            print(f"  [{i+1}/{len(unique_urls)}] {status} - {name}")

    new_entries = []
    removed = 0
    for extinf, url in entries:
        if results.get(url, False):
            new_entries.append((extinf, url))
        else:
            removed += 1

    print(f"\nRemovidas: {removed} entradas mortas")
    print(f"Mantidas: {len(new_entries)} entradas")

    with open(filepath, 'w') as f:
        f.write('#EXTM3U\n')
        for extinf, url in new_entries:
            f.write(extinf + '\n')
            f.write(url + '\n')

    print(f"Arquivo {filepath} sobrescrito com sucesso!")

    if removed > 0:
        print(f"\nCanais removidos:")
        seen = set()
        for extinf, url in entries:
            if not results.get(url, False) and url not in seen:
                m = re.search(r',(.+)$', extinf)
                name = m.group(1).strip() if m else url[:80]
                _, reason = test_url_deep(url)
                print(f"  - {name} ({reason})")
                seen.add(url)

if __name__ == '__main__':
    main()
