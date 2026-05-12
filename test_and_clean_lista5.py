#!/usr/bin/env python3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

INPUT_FILE = "lista5.m3u"

def parse_m3u(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    header = None
    channels = []
    current_extinf = None
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('#EXTM3U'):
            header = line
        elif stripped.startswith('#EXTINF:'):
            current_extinf = stripped
        elif stripped and not stripped.startswith('#') and current_extinf:
            channels.append((current_extinf, stripped, line))
            current_extinf = None
    if not header:
        header = '#EXTM3U\n'
    return header, channels

def test_url(url, timeout=10):
    try:
        result = subprocess.run(
            ['curl', '-s', '-o', '/dev/null', '-w', '%{http_code}', '--max-time', str(timeout), url],
            capture_output=True, text=True, timeout=timeout + 5
        )
        code = result.stdout.strip()
        if code and code[0] in ('2', '3'):
            return True, code
        return False, code or 'no response'
    except subprocess.TimeoutExpired:
        return False, 'timeout'
    except Exception as e:
        return False, str(e)

def main():
    header, channels = parse_m3u(INPUT_FILE)
    print(f"Total entries: {len(channels)}")

    results = {}
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {}
        for i, (extinf, url, _) in enumerate(channels):
            ch_name = extinf.split(',')[-1].strip() if ',' in extinf else 'unknown'
            futures[executor.submit(test_url, url)] = (i, ch_name, url)

        for future in as_completed(futures):
            i, ch_name, url = futures[future]
            ok, code = future.result()
            status = 'OK' if ok else 'FAIL'
            print(f"[{status}] {ch_name[:50]:50s} HTTP {code}")
            results[i] = (ok, code)

    working_count = sum(1 for v in results.values() if v[0])
    print(f"\nWorking: {working_count}/{len(channels)}")

    with open(INPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(header.rstrip('\n') + '\n')
        for i, (extinf, url, _) in enumerate(channels):
            if results[i][0]:
                f.write(extinf + '\n')
                f.write(url + '\n')

    print(f"Saved {working_count} working channels to {INPUT_FILE}")

if __name__ == '__main__':
    main()
