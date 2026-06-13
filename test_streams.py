#!/usr/bin/env python3
import subprocess
import sys
from collections import OrderedDict

M3U_FILE = "/home/runner/work/JCTVV/JCTVV/lista5.m3u"

with open(M3U_FILE, "r") as f:
    lines = [line.rstrip("\n") for line in f]

if not lines or lines[0] != "#EXTM3U":
    print("ERROR: File does not start with #EXTM3U header")
    sys.exit(1)

# Parse entries: each entry = EXTINF line + URL line
entries = []  # list of (extinf_line, url_line)
url_to_entries = OrderedDict()  # url -> list of indices

i = 1
while i < len(lines):
    if not lines[i].startswith("#EXTINF"):
        print(f"WARNING: Expected #EXTINF at line {i+1}, got: {lines[i][:60]}")
        i += 1
        continue
    extinf = lines[i]
    if i + 1 >= len(lines):
        print(f"WARNING: Missing URL after #EXTINF at line {i+1}")
        break
    url = lines[i + 1]
    idx = len(entries)
    entries.append((extinf, url))
    if url not in url_to_entries:
        url_to_entries[url] = []
    url_to_entries[url].append(idx)
    i += 2

total = len(entries)
unique_urls = list(url_to_entries.keys())
print(f"Parsed {total} entries with {len(unique_urls)} unique URLs\n")

# Test unique URLs
working_urls = set()
for url in unique_urls:
    cmd = [
        "curl", "-o", "/dev/null", "-s", "-w", "%{http_code}",
        "--max-time", "15", "--connect-timeout", "10", "-L", url
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        http_code = result.stdout.strip()
        # Consider 2xx or 3xx as working
        if http_code and http_code[0] in ("2", "3"):
            working_urls.add(url)
            print(f"  OK   {http_code:>3s} | {url[:80]}...")
        elif result.returncode == 0 and http_code:
            # Some HLS streams return partial content or other codes
            working_urls.add(url)
            print(f"  OK   {http_code:>3s} (rc=0) | {url[:80]}...")
        else:
            print(f"  FAIL {http_code:>3s} (rc={result.returncode}) | {url[:80]}...")
    except subprocess.TimeoutExpired:
        print(f"  FAIL TIMEOUT | {url[:80]}...")
    except Exception as e:
        print(f"  FAIL ERROR: {e} | {url[:80]}...")

print()

# Filter entries: keep those whose URL is working
working_indices = set()
for url in working_urls:
    for idx in url_to_entries[url]:
        working_indices.add(idx)

kept_entries = [entries[i] for i in sorted(working_indices)]
removed_entries = [entries[i] for i in range(total) if i not in working_indices]

# Collect removed channel names (from EXTINF)
removed_channels = OrderedDict()
for extinf, url in removed_entries:
    # Extract channel name after the comma
    if "," in extinf:
        name = extinf.split(",")[-1].strip()
    else:
        name = extinf
    removed_channels[name] = url

# Write back
with open(M3U_FILE, "w") as f:
    f.write("#EXTM3U\n")
    for extinf, url in kept_entries:
        f.write(extinf + "\n")
        f.write(url + "\n")

print(f"Summary: {len(kept_entries)}/{total} entries working, {len(removed_entries)} removed")
if removed_channels:
    print(f"\nRemoved channels:")
    for name in removed_channels:
        print(f"  - {name}")
