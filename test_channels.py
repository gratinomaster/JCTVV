#!/usr/bin/env python3
import subprocess, sys, re, os, urllib.parse

M3U_FILE = "lista5.m3u"
TIMEOUT = 15

def test_url(url):
    try:
        r = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", str(TIMEOUT), url],
            capture_output=True, text=True, timeout=TIMEOUT+5
        )
        code = r.stdout.strip()
        if code and code[0] in ("2", "3"):
            return True, code
        return False, code
    except Exception as e:
        return False, str(e)

with open(M3U_FILE, "r") as f:
    lines = f.readlines()

entries = []
i = 0
while i < len(lines):
    line = lines[i]
    if line.startswith("#EXTINF:"):
        if i + 1 < len(lines) and not lines[i+1].startswith("#"):
            entries.append((line.rstrip(), lines[i+1].rstrip()))
            i += 2
        else:
            i += 1
    else:
        i += 1

print(f"Found {len(entries)} channel entries, {len(set(u for _,u in entries))} unique URLs")

tested = {}
working = []
failed = []

for extinf, url in entries:
    if url not in tested:
        print(f"  Testing: {url[:80]}...", end=" ", flush=True)
        ok, code = test_url(url)
        tested[url] = ok
        print(f"{'OK' if ok else 'FAIL'} ({code})")
    if tested[url]:
        working.append((extinf, url))
    else:
        failed.append((extinf, url))

print(f"\nWorking: {len(working)}, Failed: {len(failed)}")

deduped = []
seen = set()
for extinf, url in working:
    if url not in seen:
        seen.add(url)
        deduped.append((extinf, url))

print(f"After dedup: {len(deduped)} entries")

with open(M3U_FILE, "w") as f:
    f.write("#EXTM3U\n")
    for extinf, url in deduped:
        f.write(extinf + "\n")
        f.write(url + "\n")

print(f"Written to {M3U_FILE}")
