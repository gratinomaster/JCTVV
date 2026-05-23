#!/usr/bin/env python3
import gzip
import re
import xml.etree.ElementTree as ET
import urllib.request
import os
import sys
import io
import shutil
import copy

M3U_FILE = "NEWSWORLDNOVOS.m3u"
OUTPUT_EPG = "EPGFULL.xml.gz"

def norm(s):
    return re.sub(r'[\s\-_\.]+', '', s).lower()

tvg_ids = set()
tvg_norm = set()
epg_urls = []

with open(M3U_FILE, "r", encoding="utf-8") as f:
    for line in f:
        m = re.search(r'tvg-id="([^"]*)"', line)
        if m and m.group(1):
            tid = m.group(1)
            tvg_ids.add(tid)
            tvg_norm.add(norm(tid))
        if line.startswith("#EXTM3U"):
            um = re.search(r'url-tvg="([^"]*)"', line)
            if um:
                epg_urls = [u.strip() for u in um.group(1).split(",") if u.strip()]

print(f"Found {len(tvg_ids)} tvg-ids in M3U")

if not tvg_ids:
    print("ERROR: No tvg-ids found in M3U!")
    sys.exit(1)

if not epg_urls:
    epg_urls = ["https://epgshare01.online/epgshare01/epg_ripper_ALL_SOURCES1.xml.gz"]

def download(url):
    print(f"Downloading {url}...")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"})
    resp = urllib.request.urlopen(req, timeout=600)
    data = resp.read()
    print(f"  {len(data)} bytes")
    return data

def parse_xml(data):
    if data[:2] == b'\x1f\x8b':
        f = gzip.GzipFile(fileobj=io.BytesIO(data))
    else:
        f = io.BytesIO(data)
    return ET.parse(f)

matched_ids = set()
all_channels = {}
all_programmes = {}
seen_progs = set()

for url in epg_urls:
    try:
        data = download(url)
        tree = parse_xml(data)
        root = tree.getroot()
    except Exception as e:
        print(f"  Failed: {e}")
        continue

    ch_count = 0
    for ch in root.findall("channel"):
        cid = ch.get("id")
        if not cid:
            continue
        ncid = norm(cid)
        # Check exact match first, then normalized
        if cid in tvg_ids:
            key = cid
        elif ncid in tvg_norm:
            key = next(t for t in tvg_ids if norm(t) == ncid)
        else:
            continue
        if key not in matched_ids:
            matched_ids.add(key)
            all_channels[key] = copy.deepcopy(ch)
            ch_count += 1
    print(f"  +{ch_count} new channels")

    pr_count = 0
    for prog in root.findall("programme"):
        ch = prog.get("channel")
        nch = norm(ch)
        # Find matching M3U id for this programme channel
        key = None
        if ch in tvg_ids:
            key = ch
        elif nch in tvg_norm:
            key = next((t for t in tvg_ids if norm(t) == nch), None)
        if key is None or key not in matched_ids:
            continue
        start = prog.get("start", "")
        stop = prog.get("stop", "")
        pkey = f"{key}|{start}|{stop}"
        if pkey not in seen_progs:
            seen_progs.add(pkey)
            all_programmes[pkey] = copy.deepcopy(prog)
            pr_count += 1
    print(f"  +{pr_count} new programmes")

print(f"\nTotal: {len(all_channels)} channels, {len(all_programmes)} programmes")

missing = [cid for cid in sorted(tvg_ids) if cid not in matched_ids]
if missing:
    print(f"Still missing ({len(missing)}): {missing}")

tv = ET.Element("tv")
for cid in sorted(all_channels.keys()):
    tv.append(all_channels[cid])
for prog_key in sorted(all_programmes.keys()):
    tv.append(all_programmes[prog_key])

xml_bytes = ET.tostring(tv, encoding="utf-8", xml_declaration=True)

with gzip.open(OUTPUT_EPG, "wt", encoding="utf-8") as f:
    f.write(xml_bytes.decode("utf-8"))

out_size = os.path.getsize(OUTPUT_EPG)
print(f"\nWritten to {OUTPUT_EPG} ({out_size} bytes)")
