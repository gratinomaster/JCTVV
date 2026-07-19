#!/usr/bin/env python3
import requests
import re
import os
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import sys

M3U_FILE = 'lista5.m3u'
BACKUP_FILE = f'lista5.m3u.bak.{time.strftime("%Y%m%d_%H%M%S")}'
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
        for chunk in r.iter_content(chunk_size=2048):
            content += chunk
            if len(content) >= 2048:
                break
        r.close()

        if r.status_code != 200:
            return False, f'HTTP {r.status_code}'

        if len(content) == 0:
            return False, 'empty_response'

        text = content.decode('utf-8', errors='replace')

        if '#EXTM3U' in text or '#EXT-X-' in text:
            if '#EXT-X-ENDLIST' in text and len(content) < 500:
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
        lines = f.readlines()

    channels = []
    current_extinf = None
    current_urls = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith('#EXTINF:'):
            if current_extinf is not None:
                channels.append({'extinf': current_extinf, 'urls': current_urls})
            current_extinf = line
            current_urls = []
        elif stripped.startswith('http') and current_extinf is not None:
            current_urls.append(stripped)

    if current_extinf is not None:
        channels.append({'extinf': current_extinf, 'urls': current_urls})

    return channels


def get_channel_name(extinf):
    match = re.search(r',(.+)$', extinf)
    return match.group(1).strip() if match else 'Unknown'


def main():
    if not os.path.exists(M3U_FILE):
        print(f'Arquivo {M3U_FILE} nao encontrado.')
        return

    shutil.copy2(M3U_FILE, BACKUP_FILE)
    print(f'Backup: {BACKUP_FILE}')

    channels = parse_m3U_file(M3U_FILE)
    total_urls = sum(len(c['urls']) for c in channels)
    print(f'Canais: {len(channels)} | URLs totais: {total_urls}')

    all_urls = []
    for ci, ch in enumerate(channels):
        for url in ch['urls']:
            all_urls.append((ci, url))

    results = {}
    print(f'\nTestando {len(all_urls)} URLs (timeout={TIMEOUT}s, workers={MAX_WORKERS})...\n')

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(check_url, url): (ci, url) for ci, url in all_urls}
        done = 0
        for future in as_completed(futures):
            ci, url = futures[future]
            ok, reason = future.result()
            results[(ci, url)] = (ok, reason)
            done += 1
            status = 'OK' if ok else 'FAIL'
            name = get_channel_name(channels[ci]['extinf'])
            print(f'  [{done}/{len(all_urls)}] {status} | {reason:20s} | {name}')
            if not ok:
                print(f'         URL: {url[:100]}...')

    working = 0
    failed = 0
    for v in results.values():
        if v[0]:
            working += 1
        else:
            failed += 1

    print(f'\n--- Resultado ---')
    print(f'Funcionando: {working}')
    print(f'Com erro:    {failed}')

    header = '#EXTM3U\n'
    new_lines = [header]
    removed = 0
    kept = 0
    removed_names = []

    for ci, ch in enumerate(channels):
        working_urls = []
        for url in ch['urls']:
            ok, reason = results.get((ci, url), (False, 'not_tested'))
            if ok:
                working_urls.append(url)

        if working_urls:
            kept += 1
            new_lines.append(ch['extinf'] + '\n' if not ch['extinf'].endswith('\n') else ch['extinf'])
            for wu in working_urls:
                new_lines.append(wu + '\n')
        else:
            removed += 1
            name = get_channel_name(ch['extinf'])
            removed_names.append(name)

    with open(M3U_FILE, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

    print(f'\nMantidos:  {kept} canais')
    print(f'Removidos: {removed} canais')
    if removed_names:
        print(f'\nCanais removidos:')
        for n in removed_names:
            print(f'  - {n}')
    print(f'\nArquivo {M3U_FILE} sobrescrito com sucesso.')


def parse_m3U_file(filepath):
    return parse_m3u(filepath)


if __name__ == '__main__':
    main()
