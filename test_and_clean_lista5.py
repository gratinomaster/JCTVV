#!/usr/bin/env python3
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys

M3U_FILE = "lista5.m3u"

def parse_m3u(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    header = lines[0] if lines else ""
    entries = []
    i = 1
    while i < len(lines):
        line = lines[i]
        if line.startswith("#EXTINF"):
            if i + 1 < len(lines) and not lines[i+1].startswith("#"):
                extinf = line.rstrip("\n")
                url = lines[i+1].rstrip("\n")
                entries.append((extinf, url))
                i += 2
            else:
                i += 1
        elif line.startswith("#"):
            i += 1
        else:
            i += 1
    return header, entries

def check_url(url, timeout=10):
    try:
        resp = requests.head(url, timeout=timeout, allow_redirects=True, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        return url, resp.status_code == 200
    except Exception:
        return url, False

def main():
    print("Parsing lista5.m3u...")
    header, entries = parse_m3u(M3U_FILE)
    print(f"Found {len(entries)} entries")

    print("Testing URLs...")
    working = []
    failed = []
    with ThreadPoolExecutor(max_workers=20) as executor:
        future_map = {executor.submit(check_url, url): (extinf, url) for extinf, url in entries}
        for i, future in enumerate(as_completed(future_map)):
            url, ok = future.result()
            extinf, _ = future_map[future]
            if ok:
                working.append((extinf, url))
            else:
                failed.append((extinf, url))
            if (i + 1) % 10 == 0 or i == len(entries) - 1:
                print(f"  Progress: {i+1}/{len(entries)}")

    print(f"\nWorking: {len(working)}")
    print(f"Failed: {len(failed)}")

    if failed:
        print("\nRemoved channels:")
        for extinf, url in failed:
            name = extinf.split(",")[-1] if "," in extinf else extinf
            print(f"  {name}")

    print(f"\nWriting cleaned file ({len(working)} entries)...")
    with open(M3U_FILE, 'w', encoding='utf-8') as f:
        f.write(header)
        for extinf, url in working:
            f.write(extinf + "\n")
            f.write(url + "\n")

    print("Done! lista5.m3u updated.")

if __name__ == "__main__":
    main()
