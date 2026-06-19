#!/usr/bin/env python3
import gzip
import io
import re
import xml.etree.ElementTree as ET
from collections import OrderedDict

M3U_URL = "https://github.com/gratinomaster/JCTV/raw/refs/heads/main/NEWSWORLDNOVOS.m3u"
OUTPUT = "EPGFULL.xml.gz"
EPG_SOURCES = [
    "/tmp/epg_mx.xml.gz",
    "/tmp/epg_us.xml.gz",
]

def norm(s):
    return re.sub(r'[\s\-_\.]+', '', s).lower()

print("=" * 60)
print("Step 1: Downloading M3U from GitHub")
print("=" * 60)

import urllib.request
req = urllib.request.Request(M3U_URL, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=30) as resp:
    m3u = resp.read().decode("utf-8", errors="replace")
print(f"Downloaded {len(m3u)} bytes")

tvg_ids = set()
for m in re.finditer(r'tvg-id="([^"]*)"', m3u):
    tid = m.group(1).strip()
    if tid and tid != "0" and tid != "(no tvg-id)":
        tvg_ids.add(tid)

tvg_norm = {norm(t): t for t in tvg_ids}
print(f"Found {len(tvg_ids)} tvg-ids in M3U")

print()
print("=" * 60)
print("Step 2: Parsing EPG sources and filtering")
print("=" * 60)

matched_ids = set()
channel_elements = OrderedDict()
programme_elements = OrderedDict()
seen_progs = set()

for src in EPG_SOURCES:
    print(f"\nProcessing {src}...")
    try:
        with gzip.open(src, "rb") as f:
            tree = ET.parse(f)
            root = tree.getroot()
    except Exception as e:
        print(f"  Error: {e}")
        continue

    ch_count = 0
    pr_count = 0

    for channel in root.findall("channel"):
        cid = channel.get("id", "")
        if cid in tvg_ids or norm(cid) in tvg_norm:
            key = cid if cid in tvg_ids else tvg_norm[norm(cid)]
            if key not in matched_ids:
                matched_ids.add(key)
                channel_elements[key] = ET.tostring(channel, encoding="unicode")
                ch_count += 1

    for prog in root.findall("programme"):
        ch = prog.get("channel", "")
        if ch in matched_ids:
            start = prog.get("start", "")
            stop = prog.get("stop", "")
            pkey = f"{ch}|{start}|{stop}"
            if pkey not in seen_progs:
                seen_progs.add(pkey)
                programme_elements[pkey] = ET.tostring(prog, encoding="unicode")
                pr_count += 1

    print(f"  -> {ch_count} channels, {pr_count} programmes")

print(f"\nTotal: {len(matched_ids)} channels, {len(programme_elements)} programmes")

missing = [tid for tid in sorted(tvg_ids) if tid not in matched_ids]
if missing:
    print(f"Missing from EPG ({len(missing)}): {missing}")
else:
    print("All M3U channels found in EPG sources!")

print()
print("=" * 60)
print("Step 3: Writing filtered EPG")
print("=" * 60)

lines = ['<?xml version="1.0" encoding="utf-8"?>', "<tv>"]
for buf in channel_elements.values():
    lines.append(buf)
for buf in programme_elements.values():
    lines.append(buf)
lines.append("</tv>")

xml_str = "\n".join(lines)

with gzip.open(OUTPUT, "wt", encoding="utf-8") as f:
    f.write(xml_str)

import os
size = os.path.getsize(OUTPUT)
print(f"Written to {OUTPUT} ({size} bytes, {len(xml_str)} uncompressed)")
