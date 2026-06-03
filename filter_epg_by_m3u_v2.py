#!/usr/bin/env python3
import gzip
import re
import xml.etree.ElementTree as ET
import os
import requests
from collections import OrderedDict

M3U_URL = "https://github.com/gratinomaster/JCTV/raw/refs/heads/main/NEWSWORLDNOVOS.m3u"
INPUT_EPG = "EPGFULL.xml.gz"
OUTPUT_EPG = "EPGFULL.xml.gz"

def norm(s):
    return re.sub(r'[\s\-_\.]+', '', s).lower()

print("Downloading M3U from GitHub...")
r = requests.get(M3U_URL, timeout=60, allow_redirects=True)
m3u_content = r.text

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

print(f"Found {len(tvg_ids)} tvg-ids in M3U")

if not tvg_ids:
    print("ERROR: No tvg-ids found in M3U!")
    exit(1)

name_to_tvgid = {}
for tid, name in tvg_names.items():
    nname = norm(name)
    if nname:
        name_to_tvgid[nname] = tid

matched_ids = set()
channel_elements = OrderedDict()
programme_elements = OrderedDict()
seen_progs = set()

def parse_existing_epg():
    global matched_ids, channel_elements, programme_elements, seen_progs
    if not os.path.exists(INPUT_EPG):
        print(f"  {INPUT_EPG} not found!")
        return

    print(f"Parsing {INPUT_EPG}...")
    f = gzip.open(INPUT_EPG, "rb")

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
            elem.clear()

    f.close()
    print(f"  {ch_count} channels matched, {len(programme_elements)} programmes")

parse_existing_epg()

print(f"\nFinal: {len(matched_ids)}/{len(tvg_ids)} channels, {len(programme_elements)} programmes")

missing = [cid for cid in sorted(tvg_ids) if cid not in matched_ids]
if missing:
    print(f"Missing tvg-ids ({len(missing)}): {missing}")

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
