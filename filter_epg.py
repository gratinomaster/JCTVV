#!/usr/bin/env python3
"""Filter EPGFULL.xml.gz to only include channels present in NEWSWORLDNOVOS.m3u"""
import gzip
import re
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime, timedelta

M3U_FILE = "/tmp/NEWSWORLDNOVOS.m3u"
EPG_IN = "/home/runner/work/JCTV/JCTV/EPGFULL.xml.gz"
EPG_OUT = "/home/runner/work/JCTV/JCTV/EPGFULL.xml.gz"

# Read M3U tvg-ids
m3u_ids = set()
with open(M3U_FILE) as f:
    for line in f:
        m = re.search(r'tvg-id="([^"]*)"', line)
        if m and m.group(1):
            m3u_ids.add(m.group(1))

print(f"M3U tvg-ids: {len(m3u_ids)}")

# Read existing EPG
with gzip.open(EPG_IN, 'rt', encoding='utf-8') as f:
    xml_content = f.read()

# Parse XML
root = ET.fromstring(xml_content)

# Filter channels
channels_to_keep = []
channels_removed = 0
for channel in root.findall('channel'):
    cid = channel.get('id')
    if cid in m3u_ids:
        channels_to_keep.append(cid)
    else:
        channels_removed += 1

print(f"Channels to keep: {len(channels_to_keep)}")
print(f"Channels removed: {channels_removed}")

# Build new XML
tv = ET.Element("tv")
for key, val in root.attrib.items():
    tv.set(key, val)

keep_set = set(channels_to_keep)

# Add channels
for channel in root.findall('channel'):
    if channel.get('id') in keep_set:
        tv.append(channel)

# Add programmes
progs_added = 0
progs_removed = 0
for prog in root.findall('programme'):
    if prog.get('channel') in keep_set:
        tv.append(prog)
        progs_added += 1
    else:
        progs_removed += 1

print(f"Programmes kept: {progs_added}")
print(f"Programmes removed: {progs_removed}")

# Write output
xml_str = ET.tostring(tv, encoding='utf-8')
parsed = minidom.parseString(xml_str)
pretty = parsed.toprettyxml(indent="  ")

with gzip.open(EPG_OUT, 'wt', encoding='utf-8') as f:
    f.write(pretty)

import os
size = os.path.getsize(EPG_OUT)
print(f"\nSaved: {EPG_OUT} ({size:,} bytes)")

# Test
today = datetime.now().strftime("%Y%m%d")
tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")

today_count = len(re.findall(r'<programme[^>]*start="' + today, pretty))
tomorrow_count = len(re.findall(r'<programme[^>]*start="' + tomorrow, pretty))

print(f"\n=== TEST RESULTS ===")
print(f"Today ({today}): {today_count} programmes")
print(f"Tomorrow ({tomorrow}): {tomorrow_count} programmes")

if today_count > 0 and tomorrow_count > 0:
    print("✓ EPG is working and has programmes for today AND tomorrow!")
else:
    print("✗ EPG missing programmes for today or tomorrow!")
    if today_count == 0:
        print("  - No programmes for today found!")
    if tomorrow_count == 0:
        print("  - No programmes for tomorrow found!")
