#!/usr/bin/env python3
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import os

M3U_FILE = 'lista5.m3u'
BACKUP_FILE = 'lista5.m3u.bak.' + os.path.splitext(M3U_FILE)[0]

def parse_m3u(filepath):
    entries = []
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line == '#EXTM3U':
            i += 1
            continue
        if line.startswith('#EXTINF'):
            extinf = line
            if i + 1 < len(lines):
                url = lines[i + 1].strip()
                if url and not url.startswith('#'):
                    entries.append((extinf, url))
                    i += 2
                    continue
        i += 1
    return entries

def test_url(url, timeout=10):
    try:
        resp = requests.head(url, timeout=timeout, allow_redirects=True, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        if resp.status_code < 400:
            return True
        return False
    except:
        return False

def main():
    print(f"Reading {M3U_FILE}...")
    entries = parse_m3u(M3U_FILE)
    print(f"Found {len(entries)} entries")

    urls = [url for _, url in entries]
    unique = len(set(urls))
    print(f"Unique URLs: {unique}")

    print("\nTesting URLs...")
    results = {}
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(test_url, url): url for url in set(urls)}
        for i, future in enumerate(as_completed(futures)):
            url = futures[future]
            ok = future.result()
            results[url] = ok
            if (i + 1) % 5 == 0:
                print(f"Progress: {i+1}/{len(set(urls))}")

    working_urls = {url for url, ok in results.items() if ok}
    failed_urls = {url for url, ok in results.items() if not ok}
    print(f"\nWorking URLs: {len(working_urls)}")
    print(f"Failed URLs: {len(failed_urls)}")

    for url in sorted(failed_urls):
        print(f"  FAILED: {url[:80]}")

    good_entries = [(e, u) for e, u in entries if u in working_urls]
    print(f"\nEntries to keep: {len(good_entries)}")

    with open(M3U_FILE, 'w', encoding='utf-8') as f:
        f.write('#EXTM3U\n')
        for extinf, url in good_entries:
            f.write(extinf + '\n')
            f.write(url + '\n')

    print(f"Written {len(good_entries)} entries to {M3U_FILE}")

if __name__ == '__main__':
    main()
