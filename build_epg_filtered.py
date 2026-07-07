#!/usr/bin/env python3
import gzip
import io
import re
import os
import sys
import xml.etree.ElementTree as ET
from collections import OrderedDict
import urllib.request

M3U_URL = "https://github.com/gratinomaster/JCTV/raw/refs/heads/main/NEWSWORLDNOVOS.m3u"
OUTPUT = "/home/runner/work/JCTVV/JCTVV/EPGFULL.xml.gz"
EPG_SOURCES = [
    "https://epgshare01.online/epgshare01/epg_ripper_ALL_SOURCES1.xml.gz",
    "https://fastly.jsdelivr.net/gh/limaalef/BrazilTVEPG@main/epg.xml",
    "https://github.com/limaalef/BrazilTVEPG/raw/refs/heads/main/claro.xml",
    "https://raw.githubusercontent.com/matthuisman/i.mjh.nz/master/PlutoTV/us.xml",
]

def norm(s):
    return re.sub(r'[\s\-_\.]+', '', s).lower()

def download(url, timeout=120):
    print(f"Downloading {url}")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
        if len(data) < 100:
            print(f"  Too small ({len(data)} bytes), skipping")
            return None
        print(f"  Got {len(data)} bytes")
        return data
    except Exception as e:
        print(f"  Error: {e}")
        return None

print("=" * 60)
print("Loading M3U channel list")
print("=" * 60)

data = download(M3U_URL, timeout=30)
if data is None:
    print("ERROR: could not download M3U")
    sys.exit(1)
m3u_text = data.decode("utf-8", errors="replace")

tvg_ids = set()
for m in re.finditer(r'tvg-id="([^"]*)"', m3u_text):
    tid = m.group(1).strip()
    if tid and tid != "0" and tid != "(no tvg-id)":
        tvg_ids.add(tid)

tvg_norm = {norm(t): t for t in tvg_ids}
print(f"Found {len(tvg_ids)} tvg-ids in M3U: {sorted(tvg_ids)}")

print()
print("=" * 60)
print("Downloading and filtering EPG sources")
print("=" * 60)

matched_ids = set()
all_channels = OrderedDict()
all_programmes = OrderedDict()
seen_progs = set()

def process_epg_bytes(raw_bytes):
    ch_count = 0
    pr_count = 0
    try:
        is_gz = raw_bytes[:2] == b'\x1f\x8b'
        if is_gz:
            f = gzip.GzipFile(fileobj=io.BytesIO(raw_bytes))
        else:
            f = io.BytesIO(raw_bytes)

        context = ET.iterparse(f, events=('end',))
        for event, elem in context:
            tag = elem.tag
            if tag == 'channel':
                cid = elem.get('id', '')
                if not cid:
                    elem.clear()
                    continue
                if cid in tvg_ids or norm(cid) in tvg_norm:
                    actual_id = cid if cid in tvg_ids else tvg_norm[norm(cid)]
                    if actual_id not in matched_ids:
                        matched_ids.add(actual_id)
                        all_channels[actual_id] = ET.tostring(elem, encoding='unicode')
                        ch_count += 1
                elem.clear()
            elif tag == 'programme':
                ch = elem.get('channel', '')
                if not ch:
                    elem.clear()
                    continue
                key = None
                if ch in matched_ids:
                    key = ch
                elif norm(ch) in tvg_norm and tvg_norm[norm(ch)] in matched_ids:
                    key = tvg_norm[norm(ch)]
                if key is None:
                    elem.clear()
                    continue
                start = elem.get('start', '')
                stop = elem.get('stop', '')
                pkey = f"{key}|{start}|{stop}"
                if pkey not in seen_progs:
                    seen_progs.add(pkey)
                    all_programmes[pkey] = ET.tostring(elem, encoding='unicode')
                    pr_count += 1
                elem.clear()
    except Exception as e:
        print(f"  Parse error: {e}")
        import traceback
        traceback.print_exc()
    return ch_count, pr_count

for url in EPG_SOURCES:
    raw = download(url)
    if raw is None:
        continue
    ch, pr = process_epg_bytes(raw)
    print(f"  -> {ch} new channels, {pr} new programmes")

print()
print("=" * 60)
print(f"Results: {len(matched_ids)} channels matched, {len(all_programmes)} programmes")
print("=" * 60)

matched_list = sorted(matched_ids)
print(f"Matched channels: {matched_list}")
missing = sorted(set(tvg_ids) - matched_ids)
if missing:
    print(f"Missing (no EPG data): {missing}")

print()
print("=" * 60)
print("Writing filtered EPG")
print("=" * 60)

lines = ['<?xml version="1.0" encoding="utf-8"?>', '<tv generator-info-name="EPGFULL">']
for ch_id in sorted(all_channels.keys()):
    lines.append(all_channels[ch_id])
for prog in all_programmes.values():
    lines.append(prog)
lines.append("</tv>")

xml_str = "\n".join(lines)
xml_bytes = xml_str.encode("utf-8")

with gzip.open(OUTPUT, "wb") as f:
    f.write(xml_bytes)

file_size = os.path.getsize(OUTPUT)
print(f"Written: {OUTPUT} ({file_size} bytes, {len(xml_bytes)} uncompressed)")
