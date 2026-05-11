#!/usr/bin/env python3
import gzip
import re
import xml.etree.ElementTree as ET
import urllib.request
import os
import sys
import io
import shutil

M3U_FILE = "NEWSWORLDNOVOS.m3u"
INPUT_EPG_URL = "https://epgshare01.online/epgshare01/epg_ripper_ALL_SOURCES1.xml.gz"
OUTPUT_EPG = "EPGFULL.xml.gz"
TEMP_GZ = "/tmp/epg_full_download.xml.gz"

tvg_ids = set()
with open(M3U_FILE, "r", encoding="utf-8") as f:
    for line in f:
        m = re.search(r'tvg-id="([^"]*)"', line)
        if m and m.group(1):
            tvg_ids.add(m.group(1))

print(f"Found {len(tvg_ids)} tvg-ids in M3U: {sorted(tvg_ids)}")

if not tvg_ids:
    print("ERROR: No tvg-ids found in M3U!")
    sys.exit(1)

# Download EPG
req = urllib.request.Request(
    INPUT_EPG_URL,
    headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
)
print(f"Downloading from {INPUT_EPG_URL}...")
resp = urllib.request.urlopen(req)
with open(TEMP_GZ, "wb") as f:
    shutil.copyfileobj(resp, f)
file_size = os.path.getsize(TEMP_GZ)
print(f"Downloaded {file_size} bytes to {TEMP_GZ}")

# Build filtered EPG in memory using streaming parse
# First pass: collect matching channels
with gzip.open(TEMP_GZ, "rb") as f:
    tree = ET.parse(f)
    root = tree.getroot()

all_channels = {}
for ch in root.findall("channel"):
    cid = ch.get("id")
    all_channels[cid] = ch

kept = sum(1 for cid in tvg_ids if cid in all_channels)
missing = [cid for cid in tvg_ids if cid not in all_channels]
print(f"Channels kept: {kept}/{len(tvg_ids)}")
if missing:
    print(f"Missing from EPG: {missing}")

# Build new XML
tv = ET.Element("tv")
for cid in tvg_ids:
    if cid in all_channels:
        tv.append(all_channels[cid])

prog_count = 0
for prog in root.findall("programme"):
    ch = prog.get("channel")
    if ch in tvg_ids:
        tv.append(prog)
        prog_count += 1

print(f"Kept {prog_count} programme entries")

xml_bytes = ET.tostring(tv, encoding="utf-8", xml_declaration=True)

with gzip.open(OUTPUT_EPG, "wt", encoding="utf-8") as f:
    f.write(xml_bytes.decode("utf-8"))

out_size = os.path.getsize(OUTPUT_EPG)
print(f"Written to {OUTPUT_EPG} ({out_size} bytes)")

os.unlink(TEMP_GZ)
print("Temp file cleaned up")
