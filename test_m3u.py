#!/usr/bin/env python3
import urllib.request
import urllib.error
import ssl
import sys
import time
import re

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

input_file = "lista5.m3u"
output_file = "lista5.m3u"

with open(input_file, "r") as f:
    lines = f.readlines()

entries = []  # list of (extinf_line, url_line)
i = 0
while i < len(lines):
    line = lines[i].strip()
    if line.startswith("#EXTINF:"):
        if i + 1 < len(lines):
            entries.append((lines[i], lines[i + 1]))
            i += 2
        else:
            i += 1
    elif line.startswith("#EXTM3U"):
        i += 1
    else:
        i += 1

print(f"Found {len(entries)} entries to test")

working_entries = []
for idx, (extinf, url) in enumerate(entries):
    url = url.strip()
    ch_name = extinf.strip().split('"')[-1] if '"' in extinf else extinf.strip()
    print(f"[{idx+1}/{len(entries)}] Testing: {ch_name[:60]}...", end=" ", flush=True)
    try:
        req = urllib.request.Request(url, method="HEAD")
        # Some servers block HEAD, try GET with range
        try:
            resp = urllib.request.urlopen(req, timeout=10, context=ssl_ctx)
            status = resp.status
            resp.close()
        except urllib.error.HTTPError:
            # Try GET with small range
            req2 = urllib.request.Request(url, headers={"Range": "bytes=0-0"})
            resp = urllib.request.urlopen(req2, timeout=10, context=ssl_ctx)
            status = resp.status
            resp.close()
        if status < 400:
            print("OK")
            working_entries.append((extinf, lines[lines.index(extinf) + 1]))
        else:
            print(f"FAIL (HTTP {status})")
    except Exception as e:
        print(f"FAIL ({type(e).__name__})")

print(f"\nWorking: {len(working_entries)}/{len(entries)}")

with open(output_file, "w") as f:
    f.write("#EXTM3U\n")
    for extinf, url_line in working_entries:
        f.write(extinf.rstrip('\n') + '\n')
        f.write(url_line.rstrip('\n') + '\n')

print(f"Written to {output_file}")
