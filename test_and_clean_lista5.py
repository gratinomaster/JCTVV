#!/usr/bin/env python3
import requests
import re
import os
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed

M3U_FILE = 'lista5.m3u'
BACKUP_FILE = 'lista5.m3u.bak.pre_teste'
TIMEOUT = 10

def check_url(url):
    try:
        r = requests.get(url, timeout=TIMEOUT, stream=True, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        content = r.raw.read(1024)
        r.close()
        if r.status_code == 200 and len(content) > 0:
            text = content.decode('utf-8', errors='replace')
            if '#EXTM3U' in text or '#EXTINF' in text or text.startswith('#EXT'):
                return True, 'hls_playlist'
            return True, 'responded'
        return False, f'status_{r.status_code}'
    except requests.exceptions.Timeout:
        return False, 'timeout'
    except requests.exceptions.ConnectionError:
        return False, 'connection_error'
    except Exception as e:
        return False, str(e)[:50]

def parse_m3u(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    channels = []
    current_channel = None
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('#EXTINF:'):
            if current_channel:
                channels.append(current_channel)
            current_channel = {'extinf': line, 'urls': []}
        elif stripped.startswith('http') and current_channel is not None:
            current_channel['urls'].append(line)
        elif stripped == '' and current_channel is not None:
            pass
    if current_channel:
        channels.append(current_channel)
    return channels

def main():
    if not os.path.exists(M3U_FILE):
        print(f'File {M3U_FILE} not found')
        return

    shutil.copy2(M3U_FILE, BACKUP_FILE)
    print(f'Backup saved to {BACKUP_FILE}')

    channels = parse_m3u(M3U_FILE)
    total_urls = sum(len(c['urls']) for c in channels)
    print(f'Found {len(channels)} entries with {total_urls} URLs')

    all_urls = []
    url_index = {}
    idx = 0
    for ci, ch in enumerate(channels):
        for ui, url_line in enumerate(ch['urls']):
            url = url_line.strip()
            all_urls.append(url)
            url_index[url] = (ci, ui)
            idx += 1

    results = {}
    print(f'Testing {len(all_urls)} URLs...')
    with ThreadPoolExecutor(max_workers=15) as executor:
        futures = {executor.submit(check_url, url): url for url in all_urls}
        done = 0
        for future in as_completed(futures):
            url = futures[future]
            ok, reason = future.result()
            results[url] = (ok, reason)
            done += 1
            if done % 10 == 0 or done == len(all_urls):
                print(f'  Progress: {done}/{len(all_urls)}')

    working_count = sum(1 for v in results.values() if v[0])
    failed_count = sum(1 for v in results.values() if not v[0])
    print(f'\nWorking URLs: {working_count}')
    print(f'Failed URLs: {failed_count}')

    header = '#EXTM3U\n'
    new_lines = [header]
    removed_entries = 0
    kept_entries = 0

    for ci, ch in enumerate(channels):
        working_urls = []
        for url_line in ch['urls']:
            url = url_line.strip()
            ok, reason = results.get(url, (False, 'not_tested'))
            if ok:
                working_urls.append(url_line)

        if working_urls:
            kept_entries += 1
            new_lines.append(ch['extinf'])
            for wu in working_urls:
                new_lines.append(wu)
        else:
            removed_entries += 1
            ch_name = ch['extinf'].strip()
            print(f'  Removed: {ch_name}')

    with open(M3U_FILE, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

    print(f'\nKept: {kept_entries} entries')
    print(f'Removed: {removed_entries} entries')
    print(f'Sobrescrito: {M3U_FILE}')

if __name__ == '__main__':
    main()
