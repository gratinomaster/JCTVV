#!/usr/bin/env python3
import requests
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

M3U_FILE = 'lista5.m3u'
BACKUP_FILE = 'lista5_backup_original.m3u'
MAX_WORKERS = 10
REQUEST_TIMEOUT = 15

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': '*/*'
})

def parse_m3u(filepath):
    entries = []
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    header = lines[0] if lines and lines[0].startswith('#EXTM3U') else '#EXTM3U\n'
    i = 1
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXTINF:'):
            extinf = lines[i]
            i += 1
            if i < len(lines):
                url = lines[i]
                entries.append({'extinf': extinf, 'url': url})
            i += 1
        else:
            i += 1
    return header, entries

def test_url(entry):
    url = entry['url'].strip()
    try:
        resp = session.get(url, timeout=REQUEST_TIMEOUT, stream=True)
        content_start = resp.raw.read(100)
        resp.close()
        ok = resp.status_code == 200
        return {**entry, 'ok': ok, 'status': resp.status_code}
    except requests.exceptions.Timeout:
        return {**entry, 'ok': False, 'status': 'timeout'}
    except requests.exceptions.ConnectionError:
        return {**entry, 'ok': False, 'status': 'connection_error'}
    except Exception as e:
        return {**entry, 'ok': False, 'status': f'error: {str(e)}'}

def main():
    if not os.path.exists(M3U_FILE):
        print(f"File {M3U_FILE} not found!")
        return

    header, entries = parse_m3u(M3U_FILE)
    total = len(entries)
    print(f"Found {total} entries in {M3U_FILE}")

    if os.path.exists(BACKUP_FILE):
        os.remove(BACKUP_FILE)
    os.rename(M3U_FILE, BACKUP_FILE)
    print(f"Backup saved as {BACKUP_FILE}")

    results = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(test_url, e): e for e in entries}
        for i, future in enumerate(as_completed(futures), 1):
            result = future.result()
            results.append(result)
            status = 'OK' if result['ok'] else 'FAIL'
            name = result['extinf'].strip()[:60]
            print(f"[{i}/{total}] {status} {result['status']} | {name}")

    working = [r for r in results if r['ok']]
    failed = [r for r in results if not r['ok']]
    print(f"\nResults: {len(working)} working, {len(failed)} failed out of {total}")

    with open(M3U_FILE, 'w', encoding='utf-8') as f:
        f.write(header)
        for entry in working:
            f.write(entry['extinf'])
            f.write(entry['url'])
    print(f"Written {len(working)} working entries to {M3U_FILE}")

if __name__ == '__main__':
    main()
