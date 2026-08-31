#!/usr/bin/env python3
import requests
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

M3U_FILE = 'lista5.m3u'
TIMEOUT = 15
MAX_WORKERS = 10

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': '*/*',
    'Accept-Language': 'en-US,en;q=0.9',
}


def check_url(url):
    try:
        r = requests.get(url, timeout=TIMEOUT, stream=True, headers=HEADERS)
        content = b''
        for chunk in r.iter_content(chunk_size=4096):
            content += chunk
            if len(content) >= 4096:
                break
        r.close()

        if r.status_code != 200:
            return False, f'HTTP {r.status_code}'

        if len(content) == 0:
            return False, 'empty_response'

        text = content.decode('utf-8', errors='replace')

        if '#EXTM3U' in text or '#EXT-X-' in text:
            if '#EXT-X-ENDLIST' in text and len(content) < 1000:
                return False, 'ended_stream'
            return True, 'hls_playlist'
        if text.strip().startswith('{') or text.strip().startswith('<'):
            return False, 'not_stream'

        if len(content) >= 100:
            return True, 'binary_data'

        return False, f'too_small_{len(content)}b'

    except requests.exceptions.Timeout:
        return False, 'timeout'
    except requests.exceptions.ConnectionError as e:
        err = str(e).lower()
        if 'refused' in err:
            return False, 'connection_refused'
        if 'reset' in err:
            return False, 'connection_reset'
        return False, 'connection_error'
    except requests.exceptions.TooManyRedirects:
        return False, 'too_many_redirects'
    except Exception as e:
        return False, str(e)[:40]


def parse_m3u(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        raw = f.read()
    lines = raw.splitlines()

    channels = []
    cur = None

    for line in lines:
        stripped = line.strip()
        if stripped.startswith('#EXTM3U'):
            continue
        if stripped.startswith('#EXTINF:'):
            if cur is not None:
                channels.append(cur)
            cur = {'extinf': stripped, 'urls': []}
        elif stripped.startswith('http') and cur is not None:
            cur['urls'].append(stripped)

    if cur is not None:
        channels.append(cur)

    return channels


def channel_name(extinf):
    m = re.search(r',(.+)$', extinf)
    return m.group(1).strip() if m else 'Unknown'


def main():
    channels = parse_m3u(M3U_FILE)
    print(f'Canais/entradas: {len(channels)}')

    all_urls = []
    for ci, ch in enumerate(channels):
        for url in ch['urls']:
            all_urls.append((ci, url))

    results = {}
    print(f'Testando {len(all_urls)} URLs (workers={MAX_WORKERS}, timeout={TIMEOUT}s)...')

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(check_url, url): (ci, url) for ci, url in all_urls}
        done = 0
        for future in as_completed(futures):
            ci, url = futures[future]
            ok, reason = future.result()
            results[(ci, url)] = (ok, reason)
            done += 1

    working = sum(1 for v in results.values() if v[0])
    failed = sum(1 for v in results.values() if not v[0])
    print(f'Funcionando: {working} | Com erro: {failed}')

    removed = 0
    kept = 0
    removed_entries = []

    header = '#EXTM3U'
    new_lines = [header]

    for ci, ch in enumerate(channels):
        working_urls = []
        for url in ch['urls']:
            ok, reason = results.get((ci, url), (False, 'not_tested'))
            if ok:
                working_urls.append(url)
            else:
                print(f'  REMOVE [{reason}] {channel_name(ch["extinf"])} | {url[:90]}...')

        if working_urls:
            kept += 1
            new_lines.append(ch['extinf'])
            for wu in working_urls:
                new_lines.append(wu)
        else:
            removed += 1
            removed_entries.append(channel_name(ch['extinf']))

    with open(M3U_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(new_lines) + '\n')

    print(f'\nMantidos:  {kept}')
    print(f'Removidos: {removed}')
    if removed_entries:
        print('Entradas removidas:')
        for n in removed_entries:
            print(f'  - {n}')
    print(f'Arquivo {M3U_FILE} sobrescrito.')


if __name__ == '__main__':
    main()
