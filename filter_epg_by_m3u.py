#!/usr/bin/env python3
import gzip
import re
import xml.etree.ElementTree as ET
import os
import sys
import io
from collections import OrderedDict

M3U_FILE = "NEWSWORLDNOVOS.m3u"
OUTPUT_EPG = "EPGFULL.xml.gz"
EPG_SOURCES = [
    ("epg.pw full", "/tmp/epg.xml"),
    ("epg.pw US", "/tmp/epg_US.xml.gz"),
    ("epg.pw BR", "/tmp/epg_BR.xml"),
]

def norm(s):
    return re.sub(r'[\s\-_\.]+', '', s).lower()

# Load M3U data
tvg_ids = set()
tvg_norm = {}
tvg_names = {}
tvg_logo_ids = {}

with open(M3U_FILE, "r", encoding="utf-8") as f:
    for line in f:
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

print(f"Found {len(tvg_ids)} tvg-ids in M3U")

if not tvg_ids:
    print("ERROR: No tvg-ids found in M3U!")
    sys.exit(1)

# Build reverse name lookup from M3U
name_to_tvgid = {}
for tid, name in tvg_names.items():
    nname = norm(name)
    if nname:
        name_to_tvgid[nname] = tid

matched_ids = set()
channel_elements = OrderedDict()
programme_elements = OrderedDict()
seen_progs = set()

def parse_epg_source(name, path, match_mode="id"):
    global matched_ids, channel_elements, programme_elements, seen_progs
    if not os.path.exists(path):
        print(f"  {name}: file not found, skipping")
        return

    print(f"Parsing {name}...")
    try:
        if path.endswith(".gz"):
            f = gzip.open(path, "rb")
        else:
            f = open(path, "rb")
    except Exception as e:
        print(f"  Error opening: {e}")
        return

    ch_count = 0
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

            # Try matching by logo ID (epg.pw logo filename)
            if key is None:
                for tid, lid in tvg_logo_ids.items():
                    if norm(cid) == norm(lid):
                        key = tid
                        break

            # Try matching by display-name
            if key is None and match_mode == "name":
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
            elem.clear()

    f.close()
    print(f"  +{ch_count} new channels, {sum(1 for p in programme_elements if p.startswith('|'))} programmes")

# Primary pass: exact ID match on all sources
for src_name, src_path in EPG_SOURCES:
    parse_epg_source(src_name, src_path, match_mode="id")

print(f"\nAfter primary pass: {len(matched_ids)}/{len(tvg_ids)} channels matched")

# Secondary pass: try name matching for missing channels
missing = [cid for cid in sorted(tvg_ids) if cid not in matched_ids]
if missing:
    print(f"Missing channels ({len(missing)}): {missing}")
    print("Trying name-based matching...")
    for src_name, src_path in EPG_SOURCES:
        parse_epg_source(f"{src_name} (name match)", src_path, match_mode="name")

print(f"\nFinal: {len(matched_ids)}/{len(tvg_ids)} channels, {len(programme_elements)} programmes")

missing = [cid for cid in sorted(tvg_ids) if cid not in matched_ids]
if missing:
    print(f"Still missing ({len(missing)}): {missing}")

# Build XML
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
print(f"\nWritten to {OUTPUT_EPG} ({out_size} bytes)")
print(f"File overwritten successfully")
