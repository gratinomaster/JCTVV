#!/usr/bin/env python3
import re
import gzip
import io
import sys
import os
import requests
import xml.etree.ElementTree as ET
from collections import OrderedDict

M3U_FILE = "NEWSWORLDNOVOS.m3u"
OUTPUT_EPG = "EPGFULL.xml.gz"

def norm(s):
    return re.sub(r'[\s\-_\.]+', '', s).lower()

# ---- Step 1: extract tvg-ids and names from M3U ----
tvg_ids = set()
tvg_norm = {}
tvg_names = {}

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

print(f"Found {len(tvg_ids)} unique tvg-ids in M3U")

# ---- Step 2: EPG source URLs ----
EPG_URLS = [
    "https://epg.pw/xmltv/epg.xml",
    "https://epg.pw/xmltv/epg_US.xml.gz",
    "https://epg.pw/xmltv/epg_BR.xml",
    "https://epgshare01.online/epgshare01/epg_ripper_ALL_SOURCES1.xml.gz",
]

def download(url):
    print(f"Downloading {url} ...")
    try:
        r = requests.get(url, timeout=300, allow_redirects=True)
        if r.status_code != 200:
            print(f"  Skipped (HTTP {r.status_code})")
            return None
        if len(r.content) < 200:
            print(f"  Skipped (too small: {len(r.content)} bytes)")
            return None
        print(f"  Got {len(r.content)} bytes")
        return r.content
    except Exception as e:
        print(f"  Error: {e}")
        return None

matched_ids = set()
channel_elements = OrderedDict()
programme_elements = OrderedDict()
seen_progs = set()

def process_epg(xml_bytes, name="epg"):
    global matched_ids, channel_elements, programme_elements, seen_progs
    ch_count = 0
    pr_count = 0
    try:
        if xml_bytes[:2] == b'\x1f\x8b':
            f = gzip.GzipFile(fileobj=io.BytesIO(xml_bytes))
        else:
            f = io.BytesIO(xml_bytes)

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
                if ch in matched_ids or norm(ch) in tvg_norm:
                    actual_ch = ch if ch in matched_ids else tvg_norm.get(norm(ch))
                    if actual_ch and actual_ch in matched_ids:
                        start = elem.get("start", "")
                        stop = elem.get("stop", "")
                        pkey = f"{actual_ch}|{start}|{stop}"
                        if pkey not in seen_progs:
                            seen_progs.add(pkey)
                            programme_elements[pkey] = ET.tostring(elem, encoding="unicode")
                            pr_count += 1
                elem.clear()
        f.close()
    except Exception as e:
        print(f"  Parse error in {name}: {e}")
        import traceback
        traceback.print_exc()
    print(f"  {name}: +{ch_count} channels, +{pr_count} programmes")
    return ch_count, pr_count

# ---- Step 3: download and process each EPG source ----
for url in EPG_URLS:
    data = download(url)
    if data:
        fname = os.path.basename(url.split("?")[0])
        process_epg(data, name=fname)

print(f"\nFinal: {len(matched_ids)}/{len(tvg_ids)} channels matched, {len(programme_elements)} programmes")

missing = [cid for cid in sorted(tvg_ids) if cid not in matched_ids]
if missing:
    print(f"Missing ({len(missing)}): {missing}")

# ---- Step 4: build filtered XML ----
lines = ['<?xml version="1.0" encoding="utf-8"?>', "<tv>"]
for buf in channel_elements.values():
    lines.append(buf)
for buf in programme_elements.values():
    lines.append(buf)
lines.append("</tv>")

xml_str = "\n".join(lines)
xml_bytes = xml_str.encode("utf-8")

with gzip.open(OUTPUT_EPG, "wb") as f:
    f.write(xml_bytes)

out_size = os.path.getsize(OUTPUT_EPG)
print(f"\nWritten to {OUTPUT_EPG} ({out_size} bytes, {len(xml_bytes)} uncompressed)")
