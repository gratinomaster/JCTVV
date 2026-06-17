#!/usr/bin/env python3
import re, gzip, io, os, sys
import xml.etree.ElementTree as ET
import requests
from collections import OrderedDict

M3U_URL = "https://github.com/gratinomaster/JCTV/raw/refs/heads/main/NEWSWORLDNOVOS.m3u"
OUTPUT_EPG = "EPGFULL.xml.gz"

EPG_SOURCES = [
    "https://iptv-epg.org/files/epg-mx.xml.gz",
    "https://iptv-epg.org/files/epg-us.xml.gz",
]

LARGE_SOURCES = [
    "https://epgshare01.online/epgshare01/epg_ripper_ALL_SOURCES1.xml.gz",
]

def norm(s):
    return re.sub(r'[\s\-_\.]+', '', s).lower()

def download(url, timeout=300):
    print(f"Downloading {url}")
    try:
        r = requests.get(url, timeout=timeout, allow_redirects=True)
        if r.status_code != 200:
            print(f"  Skipped (status={r.status_code})")
            return None
        if len(r.content) < 200:
            print(f"  Skipped (too small: {len(r.content)})")
            return None
        print(f"  Got {len(r.content)} bytes")
        return r.content
    except Exception as e:
        print(f"  Error: {e}")
        return None

print("=" * 60)
print("STEP 1: Load tvg-ids from M3U")
print("=" * 60)
r = requests.get(M3U_URL, timeout=60, allow_redirects=True)
m3u_content = r.text

tvg_ids = set()
tvg_norm = {}
tvg_names = {}

for line in m3u_content.splitlines():
    m = re.search(r'tvg-id="([^"]*)"', line)
    if m and m.group(1):
        tid = m.group(1)
        tvg_ids.add(tid)
        tvg_norm[norm(tid)] = tid
    mn = re.search(r'tvg-name="([^"]*)"', line)
    if mn:
        tvg_names[tid] = mn.group(1).lower().strip()

print(f"Found {len(tvg_ids)} tvg-ids: {sorted(tvg_ids)}")

if not tvg_ids:
    print("ERROR: No tvg-ids found!")
    sys.exit(1)

name_to_tvgid = {}
for tid, name in tvg_names.items():
    nname = norm(name)
    if nname:
        name_to_tvgid[nname] = tid

print("=" * 60)
print("STEP 2: Download and parse EPG sources")
print("=" * 60)

matched_ids = set()
seen_progs = set()
all_channels = OrderedDict()
all_programmes = OrderedDict()

def process_xml(data, is_gz=False):
    global matched_ids
    new_ch = 0
    new_pr = 0
    try:
        if is_gz or data[:2] == b'\x1f\x8b':
            f = gzip.GzipFile(fileobj=io.BytesIO(data))
        else:
            f = io.BytesIO(data)

        context = ET.iterparse(f, events=('end',))
        for event, elem in context:
            tag = elem.tag
            if tag == 'channel':
                cid = elem.get('id', '')
                key = None
                ncid = norm(cid)
                if cid in tvg_ids:
                    key = cid
                elif ncid in tvg_norm:
                    key = tvg_norm[ncid]
                if key is None:
                    dn = elem.find('display-name')
                    if dn is not None and dn.text:
                        ndn = norm(dn.text)
                        if ndn in name_to_tvgid:
                            key = name_to_tvgid[ndn]
                if key is not None and key not in matched_ids:
                    matched_ids.add(key)
                    all_channels[key] = ET.tostring(elem, encoding='unicode')
                    new_ch += 1
            elif tag == 'programme':
                ch = elem.get('channel', '')
                if ch in matched_ids:
                    start = elem.get('start', '')
                    stop = elem.get('stop', '')
                    pkey = f"{ch}|{start}|{stop}"
                    if pkey not in seen_progs:
                        seen_progs.add(pkey)
                        all_programmes[pkey] = ET.tostring(elem, encoding='unicode')
                        new_pr += 1
            elem.clear()
        f.close()
    except ET.ParseError as e:
        print(f"  XML parse error: {e}")
    except Exception as e:
        print(f"  Error during parse: {e}")
    return new_ch, new_pr

for url in EPG_SOURCES:
    data = download(url)
    if data:
        ch, pr = process_xml(data, is_gz=True)
        print(f"  -> {ch} new channels, {pr} new programmes")

for url in LARGE_SOURCES:
    data = download(url, timeout=600)
    if data:
        ch, pr = process_xml(data, is_gz=True)
        print(f"  -> {ch} new channels, {pr} new programmes")

print(f"\nSTEP 3: Summary")
print(f"  Matched: {len(matched_ids)}/{len(tvg_ids)} channels")
missing = [c for c in sorted(tvg_ids) if c not in matched_ids]
if missing:
    print(f"  Missing: {missing}")
print(f"  Programmes: {len(all_programmes)}")

print("=" * 60)
print("STEP 4: Writing filtered EPG")
print("=" * 60)

lines = ['<?xml version="1.0" encoding="utf-8"?>', '<tv generator-info-name="EPGFULL">']
for buf in all_channels.values():
    lines.append(buf)
for buf in all_programmes.values():
    lines.append(buf)
lines.append('</tv>')

xml_str = "\n".join(lines)

with gzip.open(OUTPUT_EPG, "wt", encoding="utf-8") as f:
    f.write(xml_str)

out_size = os.path.getsize(OUTPUT_EPG)
print(f"Written to {OUTPUT_EPG} ({out_size} bytes)")
