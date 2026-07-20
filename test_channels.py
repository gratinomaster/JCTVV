#!/usr/bin/env python3
import re
import subprocess
import sys
import urllib.parse

M3U_FILE = "lista5.m3u"

with open(M3U_FILE, "r") as f:
    lines = [l.rstrip("\n") for l in f]

# Parse: group lines into channel blocks (EXTINF + subsequent URL lines until next EXTINF or end)
channels = []
current_extinf = None
current_urls = []

for line in lines:
    if line.startswith("#EXTM3U"):
        continue
    if line.startswith("#EXTINF:"):
        if current_extinf is not None:
            channels.append((current_extinf, current_urls))
        current_extinf = line
        current_urls = []
    else:
        if current_extinf is not None:
            current_urls.append(line)

if current_extinf is not None:
    channels.append((current_extinf, current_urls))

print(f"Found {len(channels)} channel groups", file=sys.stderr)

# Deduplicate channels by name (extract name from EXTINF)
def get_channel_name(extinf):
    # Extract name after the last comma
    idx = extinf.rfind(",")
    if idx != -1:
        return extinf[idx+1:].strip()
    return extinf

def test_url(url, timeout=10):
    try:
        result = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", str(timeout), url],
            capture_output=True, text=True, timeout=timeout + 5
        )
        code = result.stdout.strip()
        if code.startswith("2") or code.startswith("3"):
            return True
        return False
    except:
        return False

seen_names = set()
unique_channels = []
dead_count = 0
alive_count = 0

for extinf, urls in channels:
    name = get_channel_name(extinf)
    if name not in seen_names:
        seen_names.add(name)
        unique_channels.append((extinf, urls))
    else:
        # Duplicate channel - we'll keep it only if the first occurrence is alive
        pass

print(f"Testing {len(unique_channels)} unique channels...", file=sys.stderr)

alive_channels = []
for extinf, urls in unique_channels:
    name = get_channel_name(extinf)
    # Test the first URL as the representative
    if urls:
        url_to_test = urls[0]
        if test_url(url_to_test):
            print(f"  ALIVE: {name}", file=sys.stderr)
            alive_channels.append((extinf, urls))
            alive_count += 1
        else:
            print(f"  DEAD:  {name}", file=sys.stderr)
            dead_count += 1
    else:
        print(f"  SKIP:  {name} (no URLs)", file=sys.stderr)

# Collect all groups (including dupes) where the channel name is in alive set
alive_names = {get_channel_name(e) for e, _ in alive_channels}
output_lines = ["#EXTM3U"]

for extinf, urls in channels:
    if get_channel_name(extinf) in alive_names:
        output_lines.append(extinf)
        output_lines.extend(urls)

with open(M3U_FILE, "w") as f:
    f.write("\n".join(output_lines) + "\n")

print(f"\nDone: {alive_count} alive, {dead_count} dead -> overwrote {M3U_FILE}", file=sys.stderr)
