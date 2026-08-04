#!/usr/bin/env python3
import requests
import re
import os
import shutil
import time
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed

M3U_FILE = 'lista5.m3u'
BACKUP_FILE = f'lista5.m3u.bak.pre_teste_{time.strftime("%Y%m%d_%H%M%S")}'
TIMEOUT = 12
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36',
    'Accept': '*/*',
    'Accept-Encoding': 'gzip, deflate'
}

def check_url(url):
    try:
        r = requests.get(url, timeout=TIMEOUT, stream=True, headers=HEADERS)
        if r.status_code != 200:
            r.close()
            return False, f'status_{r.status_code}'
        text = r.content.decode('utf-8', errors='replace')
        r.close()
        if not text.lstrip().startswith('#'):
            return False, 'not_hls'

        seg = None
        for line in text.splitlines():
            ls = line.strip()
            if ls and not ls.startswith('#') and not ls.startswith('http'):
                seg = urljoin(url, ls)
                break
        if seg is None:
            m = re.search(r'^https?://\S+', text, re.M)
            seg = m.group(0) if m else None
        if seg is None:
            return False, 'no_segments'

        r2 = requests.get(seg, timeout=TIMEOUT, stream=True, headers=HEADERS)
        c = r2.raw.read(32)
        ok = r2.status_code == 200 and len(c) > 0
        r2.close()
        if not ok:
            return False, f'segment_{r2.status_code}'
        return True, 'hls_playlist'
    except requests.exceptions.Timeout:
        return False, 'timeout'
    except requests.exceptions.ConnectionError:
        return False, 'connection_error'
    except Exception as e:
        return False, str(e)[:60]

def parse_m3u(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    entries = []
    current = None
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('#EXTINF:'):
            if current:
                entries.append(current)
            current = {'extinf': line, 'url': None}
        elif stripped.startswith('http') and current is not None:
            if current['url'] is None:
                current['url'] = line
    if current:
        entries.append(current)
    return entries

def main():
    if not os.path.exists(M3U_FILE):
        print(f'File {M3U_FILE} not found')
        return

    shutil.copy2(M3U_FILE, BACKUP_FILE)
    print(f'Backup saved to {BACKUP_FILE}')

    entries = parse_m3u(M3U_FILE)
    print(f'Found {len(entries)} entries')

    results = {}
    with ThreadPoolExecutor(max_workers=12) as executor:
        futures = {}
        for i, entry in enumerate(entries):
            if entry['url']:
                futures[executor.submit(check_url, entry['url'].strip())] = i
        for future in as_completed(futures):
            idx = futures[future]
            ok, reason = future.result()
            results[idx] = (ok, reason)
            print(f'  [{idx+1}/{len(entries)}] {ok}: {entries[idx]["extinf"].strip()[:80]} ({reason})')

    working = 0
    removed = 0
    new_lines = ['#EXTM3U\n']
    removed_names = []
    for i, entry in enumerate(entries):
        ok, reason = results.get(i, (False, 'not_tested'))
        if ok:
            working += 1
            new_lines.append(entry['extinf'])
            new_lines.append(entry['url'])
        else:
            removed += 1
            name = entry['extinf'].strip()
            removed_names.append(name)
            print(f'  REMOVED: {name}')

    with open(M3U_FILE, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

    print(f'\nWorking: {working}')
    print(f'Removed: {removed}')
    print(f'Sobrescrito: {M3U_FILE}')

if __name__ == '__main__':
    main()
