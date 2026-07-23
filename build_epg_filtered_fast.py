#!/usr/bin/env python3
import gzip
import io
import re
import os
import sys
import copy
import xml.etree.ElementTree as ET
from collections import OrderedDict
from datetime import datetime, timedelta
import urllib.request

M3U_URL = "https://github.com/gratinomaster/JCTV/raw/refs/heads/main/NEWSWORLDNOVOS.m3u"
OUTPUT = "/home/runner/work/JCTVV/JCTVV/EPGFULL.xml.gz"

EPG_SOURCES = [
    "https://epgshare01.online/epgshare01/epg_ripper_NL1.xml.gz",
    "https://epg.pw/xmltv/epg_RU.xml.gz",
    "https://epg.pw/xmltv/epg_AU.xml.gz",
    "https://epg.pw/xmltv/epg_FR.xml.gz",
    "https://epg.pw/xmltv/epg_GB.xml.gz",
    "https://epg.pw/xmltv/epg_DE.xml.gz",
    "https://epg.pw/xmltv/epg_US.xml.gz",
    "https://epg.pw/xmltv/epg_BR.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_BR1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_UK1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_FR1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_DE1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_IN1.xml.gz",
    "https://www.programtv.ru/xmltv.xml.gz",
    "https://fastly.jsdelivr.net/gh/limaalef/BrazilTVEPG@main/epg.xml",
    "https://fastly.jsdelivr.net/gh/limaalef/BrazilTVEPG@main/claro.xml",
    "https://raw.githubusercontent.com/matthuisman/i.mjh.nz/master/PlutoTV/us.xml",
]

def norm(s):
    return re.sub(r'[\s\-_\.]+', '', s).lower()

def download(url, timeout=120):
    print(f"  Downloading: {url}")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
        if len(data) < 100:
            print(f"    Skipped (too small: {len(data)} bytes)")
            return None
        print(f"    Got {len(data):,} bytes")
        return data
    except Exception as e:
        print(f"    Error: {e}")
        return None

print("=" * 60)
print("1. Loading M3U channel list")
print("=" * 60)

data = download(M3U_URL, timeout=60)
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
tvg_norm_set = set(tvg_norm.keys())

m3u_names = {}
for line in m3u_text.splitlines():
    m = re.search(r'tvg-id="([^"]*)"', line)
    name_match = re.search(r',([^,]+)$', line)
    if m and name_match:
        tid = m.group(1).strip()
        name = name_match.group(1).strip()
        name_base = re.sub(r'\s*\(.*$', '', name).strip()
        m3u_names[tid] = name_base

print(f"  Found {len(tvg_ids)} tvg-ids")

print()
print("=" * 60)
print("2. Downloading and filtering EPG sources")
print("=" * 60)

matched_ids = set()
all_channels = OrderedDict()
all_programmes = OrderedDict()
seen_progs = set()

def strip_suffixes(s):
    return re.sub(r'(tv|channel|television|televisión|noticias|news|channel\s*\d*)$', '', s).strip()

def fuzzy_match(epg_cid, display_name):
    nc = norm(epg_cid)
    if nc in tvg_norm_set:
        return tvg_norm[nc]
    for tid in tvg_ids:
        nm = norm(tid)
        if nm in nc or nc in nm:
            return tid
    if display_name:
        ndn = norm(display_name)
        for tid, base_name in m3u_names.items():
            nb = norm(base_name)
            if nb == ndn or ndn in nb or nb in ndn:
                return tid
        ndn2 = strip_suffixes(ndn)
        for tid, base_name in m3u_names.items():
            nb = norm(base_name)
            nb2 = strip_suffixes(nb)
            if ndn2 == nb2 or ndn2 in nb2 or nb2 in ndn2:
                return tid
    for tid, base_name in m3u_names.items():
        nb = norm(base_name)
        if nb in nc:
            return tid
    nc2 = strip_suffixes(nc)
    for tid, base_name in m3u_names.items():
        nb = norm(base_name)
        nb2 = strip_suffixes(nb)
        if nc2 == nb2 or nc2 in nb2 or nb2 in nc2:
            return tid
    return None

def process_epg_bytes(raw_bytes):
    ch_count = 0
    pr_count = 0
    id_remap = {}
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
                dn = elem.find('display-name')
                display_name = dn.text.strip() if dn is not None and dn.text else ''
                m3u_id = fuzzy_match(cid, display_name)
                if m3u_id:
                    id_remap[cid] = m3u_id
                    if m3u_id not in matched_ids:
                        matched_ids.add(m3u_id)
                        ch = copy.deepcopy(elem)
                        ch.set('id', m3u_id)
                        all_channels[m3u_id] = ch
                        ch_count += 1
                elem.clear()
            elif tag == 'programme':
                ch = elem.get('channel', '')
                if not ch:
                    elem.clear()
                    continue
                m3u_id = id_remap.get(ch)
                if m3u_id is None:
                    m3u_id = fuzzy_match(ch, '')
                if m3u_id:
                    start = elem.get('start', '')
                    stop = elem.get('stop', '')
                    pkey = f"{m3u_id}|{start}|{stop}"
                    if pkey not in seen_progs:
                        seen_progs.add(pkey)
                        pr = copy.deepcopy(elem)
                        pr.set('channel', m3u_id)
                        all_programmes[pkey] = pr
                        pr_count += 1
                elem.clear()
    except Exception as e:
        print(f"    Parse error: {e}")
    return ch_count, pr_count

for url in EPG_SOURCES:
    raw = download(url)
    if raw is None:
        continue
    ch, pr = process_epg_bytes(raw)
    print(f"    -> {ch} new channels, {pr} new programmes")
    if len(matched_ids) >= len(tvg_ids):
        print(f"    All {len(tvg_ids)} channels matched, skipping remaining sources")
        break

print()
print("=" * 60)
print(f"3. Results: {len(matched_ids)}/{len(tvg_ids)} channels matched, {len(all_programmes)} programmes")
print("=" * 60)

matched_list = sorted(matched_ids)
print(f"  Matched: {matched_list}")
missing = sorted(set(tvg_ids) - matched_ids)
if missing:
    print(f"  Missing (no EPG data): {missing}")

print()
print("=" * 60)
print("4. Writing filtered EPG")
print("=" * 60)

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

file_size = os.path.getsize(OUTPUT)
print(f"  Written: {OUTPUT} ({file_size:,} bytes compressed, {len(xml_data):,} uncompressed)")

print()
print("=" * 60)
print("5. Testing EPG")
print("=" * 60)

with gzip.open(OUTPUT, 'rb') as f:
    test_xml = f.read().decode('utf-8', errors='ignore')

test_root = ET.fromstring(test_xml)
canais = test_root.findall("channel")
programas = test_root.findall("programme")

print(f"  Channels in EPG: {len(canais)}")
print(f"  Programmes in EPG: {len(programas)}")

hoje = datetime.now().strftime("%Y%m%d")
amanha = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")

prog_hoje = 0
prog_amanha = 0
canais_hoje = set()
canais_amanha = set()

for prog in programas:
    start = prog.get("start", "")[:8]
    ch = prog.get("channel", "")
    if start == hoje:
        prog_hoje += 1
        canais_hoje.add(ch)
    elif start == amanha:
        prog_amanha += 1
        canais_amanha.add(ch)

print(f"  Programmes today ({hoje}): {prog_hoje} in {len(canais_hoje)} channels")
print(f"  Programmes tomorrow ({amanha}): {prog_amanha} in {len(canais_amanha)} channels")

if canais_hoje:
    print(f"  Channels with today's data: {sorted(canais_hoje)[:15]}{'...' if len(canais_hoje) > 15 else ''}")
if canais_amanha:
    print(f"  Channels with tomorrow's data: {sorted(canais_amanha)[:15]}{'...' if len(canais_amanha) > 15 else ''}")

if prog_hoje > 0 and prog_amanha > 0:
    print("\n  EPG OK! Programmes available for today and tomorrow.")
    sys.exit(0)
else:
    print("\n  EPG WARNING! Missing programmes for today or tomorrow.")
    sys.exit(1)
