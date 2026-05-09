#!/usr/bin/env python3
import gzip
import re
import xml.etree.ElementTree as ET

M3U_FILE = "NEWSWORLDNOVOS.m3u"
INPUT_EPG = "EPGFULL.xml.gz"
OUTPUT_EPG = "EPGFULL.xml.gz"

tvg_ids = set()
with open(M3U_FILE, "r", encoding="utf-8") as f:
    for line in f:
        m = re.search(r'tvg-id="(\d+)"', line)
        if m:
            tvg_ids.add(m.group(1))

print(f"Found {len(tvg_ids)} tvg-ids in M3U: {sorted(tvg_ids)}")

with gzip.open(INPUT_EPG, "rt", encoding="utf-8") as f:
    xml_content = f.read()

root = ET.fromstring(xml_content)
channels_to_keep = set()

for channel in root.findall("channel"):
    cid = channel.get("id")
    if cid in tvg_ids:
        channels_to_keep.add(cid)
    else:
        root.remove(channel)

print(f"Keeping {len(channels_to_keep)} channels: {sorted(channels_to_keep)}")

removed_count = 0
for programme in root.findall("programme"):
    ch = programme.get("channel")
    if ch not in channels_to_keep:
        root.remove(programme)
        removed_count += 1

print(f"Removed {removed_count} programme entries from excluded channels")

xml_bytes = ET.tostring(root, encoding="utf-8", xml_declaration=True)

with gzip.open(OUTPUT_EPG, "wt", encoding="utf-8") as f:
    f.write(xml_bytes.decode("utf-8"))

print(f"Written to {OUTPUT_EPG}")
