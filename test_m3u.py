#!/usr/bin/env python3
import subprocess, sys, os, json, re
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

INPUT = "lista5.m3u"

def load_entries(path):
    entries = []
    with open(path) as f:
        lines = f.readlines()
    if not lines or lines[0].strip() != "#EXTM3U":
        print("ERROR: invalid M3U header", file=sys.stderr)
        sys.exit(1)
    i = 1
    while i < len(lines):
        extinf = lines[i].strip()
        i += 1
        if i < len(lines):
            url = lines[i].strip()
            i += 1
            if extinf.startswith("#EXTINF:") and url:
                entries.append((extinf, url))
            elif not extinf:
                continue
            else:
                print(f"WARNING: skipping unexpected line: {extinf}", file=sys.stderr)
        else:
            print(f"WARNING: orphaned EXTINF: {extinf}", file=sys.stderr)
    return entries

def test_url(url, timeout=15):
    try:
        r = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "--connect-timeout", "10", "--max-time", str(timeout), "-L", url],
            capture_output=True, text=True, timeout=timeout + 5
        )
        code = r.stdout.strip()
        return code == "200"
    except Exception:
        return False

entries = load_entries(INPUT)
print(f"Loaded {len(entries)} entries")

results = {}
with ThreadPoolExecutor(max_workers=10) as pool:
    fut = {pool.submit(test_url, url): (ext, url) for ext, url in entries}
    for f in as_completed(fut):
        ext, url = fut[f]
        ok = f.result()
        results[url] = ok
        name = ext.split(",")[-1] if "," in ext else ext
        status = "OK" if ok else "FAIL"
        print(f"[{status}] {name}")

with open(INPUT + ".new", "w") as out:
    out.write("#EXTM3U\n")
    for ext, url in entries:
        if results.get(url, False):
            out.write(ext + "\n")
            out.write(url + "\n")

os.replace(INPUT + ".new", INPUT)
print(f"\nDone! Removed {sum(1 for v in results.values() if not v)} non-working entries. Updated {INPUT}")
