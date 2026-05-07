#!/usr/bin/env python3
import re
import gzip
import io
import copy
import xml.etree.ElementTree as ET
import requests
from collections import OrderedDict

M3U_URL = "https://github.com/gratinomaster/1/raw/refs/heads/main/lista1.M3U"
OUTPUT = "/home/runner/work/JCTV/JCTV/EPGFULL.xml.gz"

def norm(s):
    return re.sub(r'[\s\-_\.]+', '', s).lower()

print("Downloading M3U...")
r = requests.get(M3U_URL, timeout=60, allow_redirects=True)
m3u_content = r.text

m3u_ids = set()
for match in re.finditer(r'tvg-id="([^"]*)"', m3u_content):
    tid = match.group(1).strip()
    if tid and tid != "0" and tid != "(no tvg-id)":
        m3u_ids.add(tid)

m3u_norm_ids = {norm(t) for t in m3u_ids}
print(f"Found {len(m3u_ids)} unique tvg-ids in M3U")

EPG_SOURCES = [
    "https://fastly.jsdelivr.net/gh/limaalef/BrazilTVEPG@main/epg.xml",
    "https://github.com/limaalef/BrazilTVEPG/raw/refs/heads/main/claro.xml",
    "https://github.com/limaalef/BrazilTVEPG/raw/refs/heads/main/vivoplay.xml",
    "https://github.com/limaalef/BrazilTVEPG/raw/refs/heads/main/globo.xml",
    "https://raw.githubusercontent.com/matthuisman/i.mjh.nz/master/PlutoTV/us.xml",
]

LARGE_SOURCES = [
    "https://epgshare01.online/epgshare01/epg_ripper_ALL_SOURCES1.xml.gz",
]

def download_epg(url):
    print(f"Downloading EPG: {url}")
    try:
        r = requests.get(url, timeout=300, allow_redirects=True)
        if r.status_code != 200:
            print(f"  Skipped (status={r.status_code})")
            return None
        if len(r.content) < 100:
            print(f"  Skipped (too small: {len(r.content)})")
            return None
        print(f"  Got {len(r.content)} bytes")
        return r.content
    except Exception as e:
        print(f"  Error: {e}")
        return None

matched_ids = set()
seen_progs = set()
all_channels = OrderedDict()
all_programmes = OrderedDict()

def process_epg_xml(xml_bytes, valid_ids, valid_norm):
    new_ch = 0
    new_pr = 0
    try:
        tree = ET.parse(io.BytesIO(xml_bytes))
        root = tree.getroot()

        for channel in root.findall('channel'):
            cid = channel.get('id', '')
            if cid in valid_ids or norm(cid) in valid_norm:
                if cid not in matched_ids:
                    matched_ids.add(cid)
                    all_channels[cid] = copy.deepcopy(channel)
                    new_ch += 1

        for prog in root.findall('programme'):
            ch = prog.get('channel', '')
            if ch in matched_ids:
                start = prog.get('start', '')
                stop = prog.get('stop', '')
                key = f"{ch}|{start}|{stop}"
                if key not in seen_progs:
                    seen_progs.add(key)
                    all_programmes[key] = copy.deepcopy(prog)
                    new_pr += 1
    except ET.ParseError as e:
        print(f"  XML parse error: {e}")
    return new_ch, new_pr

for url in EPG_SOURCES:
    data = download_epg(url)
    if data is None:
        continue
    ch, pr = process_epg_xml(data, m3u_ids, m3u_norm_ids)
    print(f"  -> {ch} new channels, {pr} new programmes")

def process_large_epg(url, valid_ids, valid_norm):
    print(f"Downloading large EPG: {url}")
    new_ch = 0
    new_pr = 0
    try:
        r = requests.get(url, timeout=600, allow_redirects=True)
        if r.status_code != 200:
            print(f"  Skipped (status={r.status_code})")
            return 0, 0

        raw = r.content
        print(f"  Got {len(raw)} bytes compressed")

        if raw[:2] == b'\x1f\x8b':
            f = gzip.GzipFile(fileobj=io.BytesIO(raw))
        else:
            f = io.BytesIO(raw)

        context = ET.iterparse(f, events=('end',))
        for event, elem in context:
            tag = elem.tag
            if tag == 'channel':
                cid = elem.get('id', '')
                if cid in valid_ids or norm(cid) in valid_norm:
                    if cid not in matched_ids:
                        matched_ids.add(cid)
                        all_channels[cid] = copy.deepcopy(elem)
                        new_ch += 1
            elif tag == 'programme':
                ch = elem.get('channel', '')
                if ch in matched_ids:
                    start = elem.get('start', '')
                    stop = elem.get('stop', '')
                    key = f"{ch}|{start}|{stop}"
                    if key not in seen_progs:
                        seen_progs.add(key)
                        all_programmes[key] = copy.deepcopy(elem)
                        new_pr += 1
            elem.clear()
    except Exception as e:
        print(f"  Error: {e}")
        import traceback
        traceback.print_exc()
    return new_ch, new_pr

for url in LARGE_SOURCES:
    ch, pr = process_large_epg(url, m3u_ids, m3u_norm_ids)
    print(f"  -> {ch} new channels, {pr} new programmes")

print(f"\nTotal matched: {len(matched_ids)} channels, {len(all_programmes)} programmes")

root_out = ET.Element("tv", attrib={"generator-info-name": "EPGFULL"})
for ch in all_channels.values():
    root_out.append(ch)
for prog in all_programmes.values():
    root_out.append(prog)

tree = ET.ElementTree(root_out)
buf = io.BytesIO()
tree.write(buf, encoding='utf-8', xml_declaration=True)
xml_data = buf.getvalue()

with gzip.open(OUTPUT, 'wb') as f:
    f.write(xml_data)

print(f"Saved {OUTPUT} ({len(xml_data)} bytes uncompressed)")
