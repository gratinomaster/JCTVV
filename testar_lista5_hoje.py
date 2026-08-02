#!/usr/bin/env python3
import re
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

INPUT = "lista5.m3u"
OUTPUT = "lista5.m3u"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36",
    "Accept": "*/*",
}

def parse_m3u(path):
    entries = []
    current = None
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith("#EXTM3U"):
                continue
            if line.startswith("#EXTINF:"):
                if current:
                    entries.append(current)
                current = {"extinf": line, "url": None}
            elif line.startswith("http://") or line.startswith("https://"):
                if current:
                    current["url"] = line
                else:
                    entries.append({"extinf": None, "url": line})
        if current:
            entries.append(current)
    return entries

def check_url(url, timeout=15):
    try:
        r = requests.get(url, timeout=timeout, allow_redirects=True, headers=HEADERS, stream=True)
        r.close()
        code = r.status_code
        if code in (200, 206):
            return True, code
        return False, code
    except requests.exceptions.Timeout:
        return False, "timeout"
    except requests.exceptions.ConnectionError:
        return False, "conn_err"
    except requests.exceptions.HTTPError:
        return False, "http_err"
    except Exception as e:
        return False, f"err:{type(e).__name__}"

def main():
    entries = parse_m3u(INPUT)
    print(f"Total channels: {len(entries)}")

    working = []
    failed = []

    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = {ex.submit(check_url, e["url"]): i for i, e in enumerate(entries)}
        for fut in as_completed(futures):
            idx = futures[fut]
            ok, code = fut.result()
            name = entries[idx]["extinf"].split(",")[-1] if entries[idx]["extinf"] else entries[idx]["url"]
            if ok:
                working.append(idx)
                print(f"[OK {code}] {name}")
            else:
                failed.append((idx, code, name))
                print(f"[FAIL {code}] {name}")

    failed.sort()
    working.sort()

    print(f"\nWorking: {len(working)}/{len(entries)}")
    print(f"Failed ({len(failed)}):")
    for idx, code, name in failed:
        print(f"  {code} - {name}")

    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for idx in working:
            f.write(entries[idx]["extinf"] + "\n")
            f.write(entries[idx]["url"] + "\n")

    print(f"\nWritten to {OUTPUT}")

if __name__ == "__main__":
    main()
