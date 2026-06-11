#!/usr/bin/env python3
import gzip
import re
import xml.etree.ElementTree as ET
import os
import sys
import urllib.request
from collections import OrderedDict

M3U_URL = "https://github.com/gratinomaster/JCTV/raw/refs/heads/main/NEWSWORLDNOVOS.m3u"
LOCAL_M3U = "NEWSWORLDNOVOS.m3u"
OUTPUT_EPG = "EPGFULL.xml.gz"
FRESH_EPG = "/tmp/epg_ripper.xml.gz"

def norm(s):
    return re.sub(r'[\s\-_\.]+', '', s).lower()

# --- Step 1: Load tvg-ids from M3U ---
print("=" * 60)
print("STEP 1: Loading M3U channel list")
print("=" * 60)

print("Downloading M3U from GitHub...")
try:
    req = urllib.request.Request(M3U_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        m3u_content = resp.read().decode("utf-8", errors="replace")
    print(f"  Downloaded {len(m3u_content)} bytes")
except Exception as e:
    print(f"  Error downloading: {e}, using local file")
    with open(LOCAL_M3U, "r", encoding="utf-8") as f:
        m3u_content = f.read()

tvg_ids = set()
tvg_norm = {}
tvg_names = {}
tvg_logo_ids = {}

for line in m3u_content.splitlines():
    m = re.search(r'tvg-id="([^"]*)"', line)
    if m and m.group(1):
        tid = m.group(1)
        tvg_ids.add(tid)
        tvg_norm[norm(tid)] = tid
    mn = re.search(r'tvg-name="([^"]*)"', line)
    if mn:
        tvg_names[tid] = mn.group(1).lower().strip()
    ml = re.search(r'epg\.pw/media/logos/tvg-id/(.+)\.png', line)
    if ml:
        tvg_logo_ids[tid] = ml.group(1)

print(f"Found {len(tvg_ids)} tvg-ids from GitHub M3U")

if os.path.exists(LOCAL_M3U):
    with open(LOCAL_M3U, "r", encoding="utf-8") as f:
        local_content = f.read()
    extra = 0
    for line in local_content.splitlines():
        m = re.search(r'tvg-id="([^"]*)"', line)
        if m and m.group(1) and m.group(1) not in tvg_ids:
            tid = m.group(1)
            tvg_ids.add(tid)
            tvg_norm[norm(tid)] = tid
            extra += 1
        mn = re.search(r'tvg-name="([^"]*)"', line)
        if mn and m and m.group(1):
            tid = m.group(1)
            if tid not in tvg_names:
                tvg_names[tid] = mn.group(1).lower().strip()
        ml = re.search(r'epg\.pw/media/logos/tvg-id/(.+)\.png', line)
        if ml and m and m.group(1):
            tid = m.group(1)
            if tid not in tvg_logo_ids:
                tvg_logo_ids[tid] = ml.group(1)
    print(f"Added {extra} more from local M3U, total: {len(tvg_ids)}")

if not tvg_ids:
    print("ERROR: No tvg-ids found!")
    sys.exit(1)

name_to_tvgid = {norm(name): tid for tid, name in tvg_names.items() if name}

# --- Step 2: Parse fresh EPG and filter ---
print()
print("=" * 60)
print("STEP 2: Parsing fresh EPG and filtering by M3U channels")
print("=" * 60)

matched_ids = set()
channel_elements = OrderedDict()
programme_elements = OrderedDict()
seen_progs = set()

if not os.path.exists(FRESH_EPG):
    print(f"ERROR: {FRESH_EPG} not found!")
    sys.exit(1)

print(f"Parsing {FRESH_EPG}...")
f = gzip.open(FRESH_EPG, "rb")
ch_count = 0
prog_count = 0
for event, elem in ET.iterparse(f, events=("end",)):
    if elem.tag == "channel":
        cid = elem.get("id")
        if not cid:
            elem.clear()
            continue
        key = None
        ncid = norm(cid)
        if cid in tvg_ids:
            key = cid
        elif ncid in tvg_norm:
            key = tvg_norm[ncid]
        if key is None:
            for tid, lid in tvg_logo_ids.items():
                if norm(cid) == norm(lid):
                    key = tid
                    break
        if key is None:
            dn = elem.find("display-name")
            if dn is not None and dn.text:
                ndn = norm(dn.text)
                if ndn in name_to_tvgid:
                    key = name_to_tvgid[ndn]
        if key is not None and key not in matched_ids:
            matched_ids.add(key)
            channel_elements[key] = ET.tostring(elem, encoding="unicode")
            ch_count += 1
        elem.clear()
    elif elem.tag == "programme":
        ch = elem.get("channel")
        if not ch:
            elem.clear()
            continue
        key = None
        nch = norm(ch)
        if ch in matched_ids:
            key = ch
        elif nch in tvg_norm and tvg_norm[nch] in matched_ids:
            key = tvg_norm[nch]
        if key is None:
            elem.clear()
            continue
        start = elem.get("start", "")
        stop = elem.get("stop", "")
        pkey = f"{key}|{start}|{stop}"
        if pkey not in seen_progs:
            seen_progs.add(pkey)
            programme_elements[pkey] = ET.tostring(elem, encoding="unicode")
            prog_count += 1
            if prog_count % 50000 == 0:
                print(f"  ... {prog_count} programmes collected")
        elem.clear()

f.close()
print(f"\n  {ch_count} channels matched, {prog_count} programmes")

print(f"\nFinal: {len(matched_ids)}/{len(tvg_ids)} channels, {len(programme_elements)} programmes")

missing = [cid for cid in sorted(tvg_ids) if cid not in matched_ids]
if missing:
    print(f"Missing tvg-ids ({len(missing)}): {missing[:30]}...")

# --- Step 3: Write output ---
print()
print("=" * 60)
print("STEP 3: Writing filtered EPG")
print("=" * 60)

lines = ['<?xml version="1.0" encoding="utf-8"?>', "<tv>"]
for buf in channel_elements.values():
    lines.append(buf)
for buf in programme_elements.values():
    lines.append(buf)
lines.append("</tv>")

xml_str = "\n".join(lines)

with gzip.open(OUTPUT_EPG, "wt", encoding="utf-8") as f:
    f.write(xml_str)

out_size = os.path.getsize(OUTPUT_EPG)
print(f"Written to {OUTPUT_EPG} ({out_size} bytes)")
