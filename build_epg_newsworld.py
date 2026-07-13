#!/usr/bin/env python3
import gzip
import re
import os
import xml.etree.ElementTree as ET
from collections import OrderedDict
from datetime import datetime, timedelta

M3U_FILE = "NEWSWORLDNOVOS.m3u"
EPG_SOURCE = "/tmp/epg_all.xml.gz"
OUTPUT = "EPGFULL.xml.gz"


def norm(s):
    return re.sub(r'[\s\-_\.]+', '', s).lower()


print("=" * 60)
print("Step 1: Parsing M3U file")
print("=" * 60)

with open(M3U_FILE, "r", encoding="utf-8", errors="replace") as f:
    m3u = f.read()

m3u_tvg_names = {}
m3u_display_names = {}
extinf_pattern = re.compile(
    r'#EXTINF:-1\s+'
    r'(?:tvg-id="([^"]*)"\s+)?'
    r'(?:tvg-name="([^"]*)"\s+)?'
    r'[^,]*,'
    r'(.+)$',
    re.MULTILINE
)

for m in extinf_pattern.finditer(m3u):
    tname = (m.group(2) or "").strip()
    display = m.group(3).strip()
    if tname:
        n = norm(tname)
        if n not in m3u_tvg_names:
            m3u_tvg_names[n] = tname
    if display:
        n = norm(display)
        if n not in m3u_display_names:
            m3u_display_names[n] = display

all_m3u_norms = set(m3u_tvg_names.keys()) | set(m3u_display_names.keys())
print(f"Unique M3U names to match: {len(all_m3u_norms)}")

print()
print("=" * 60)
print("Step 2: Filtering EPG from source (by name)")
print("=" * 60)

epg_channels_raw = OrderedDict()
epg_programmes = OrderedDict()
seen_progs = set()
matched_channel_ids = set()
ch_count = 0
pr_count = 0

# Pass 1: collect matching channels
for event, elem in ET.iterparse(gzip.open(EPG_SOURCE, "rb"), events=("end",)):
    if elem.tag == "channel":
        cid = elem.get("id", "")
        if not cid:
            elem.clear()
            continue
        matched = False
        for dn in elem.findall("display-name"):
            name = dn.text if dn.text else ""
            nn = norm(name)
            if nn in all_m3u_norms:
                matched = True
                break
        if matched:
            matched_channel_ids.add(cid)
            epg_channels_raw[cid] = ET.tostring(elem, encoding="unicode")
            ch_count += 1
        elem.clear()

    elif elem.tag == "programme":
        ch = elem.get("channel", "")
        if ch in matched_channel_ids:
            start = elem.get("start", "")
            stop = elem.get("stop", "")
            pkey = f"{ch}|{start}|{stop}"
            if pkey not in seen_progs:
                seen_progs.add(pkey)
                epg_programmes[pkey] = ET.tostring(elem, encoding="unicode")
                pr_count += 1
        elem.clear()

print(f"  Matched {ch_count} channels, {pr_count} programmes")

# Deduplicate channels by display-name (keep first match)
seen_names = set()
channels = OrderedDict()
for cid, xml_str in epg_channels_raw.items():
    root = ET.fromstring(xml_str)
    dn = root.find("display-name")
    name = dn.text if dn is not None and dn.text else cid
    nn = norm(name)
    if nn not in seen_names:
        seen_names.add(nn)
        channels[cid] = xml_str

# Deduplicate programmes to only keep unique ones for our channels
kept_channel_ids = set(channels.keys())
programmes = OrderedDict()
for pkey, xml_str in epg_programmes.items():
    ch = pkey.split("|")[0]
    if ch in kept_channel_ids:
        programmes[pkey] = xml_str

print(f"  After dedup: {len(channels)} channels, {len(programmes)} programmes")

print()
print("=" * 60)
print("Step 3: Writing filtered EPG")
print("=" * 60)

lines = ['<?xml version="1.0" encoding="utf-8"?>', "<tv>"]
lines.extend(channels.values())
lines.extend(programmes.values())
lines.append("</tv>")

xml_str = "\n".join(lines)

with gzip.open(OUTPUT, "wt", encoding="utf-8") as f:
    f.write(xml_str)

size = os.path.getsize(OUTPUT)
print(f"  Written: {OUTPUT} ({size:,} bytes)")

print()
print("=" * 60)
print("Step 4: Testing EPG")
print("=" * 60)

with gzip.open(OUTPUT, "rb") as f:
    test_root = ET.fromstring(f.read())

canais = test_root.findall("channel")
programas = test_root.findall("programme")
print(f"  Total channels: {len(canais)}")
print(f"  Total programmes: {len(programas)}")

hoje = datetime.now().strftime("%Y%m%d")
amanha = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
prog_hoje = sum(1 for p in programas if p.get("start", "")[:8] == hoje)
prog_amanha = sum(1 for p in programas if p.get("start", "")[:8] == amanha)
print(f"  Programas hoje ({hoje}): {prog_hoje}")
print(f"  Programas amanha ({amanha}): {prog_amanha}")

if canais:
    print()
    print("Canais no EPG:")
    for ch in canais[:30]:
        dn = ch.find("display-name")
        name = dn.text if dn is not None and dn.text else "N/A"
        print(f"  {ch.get('id')}: {name}")
    if len(canais) > 30:
        print(f"  ... e mais {len(canais) - 30} canais")

if prog_hoje > 0 and prog_amanha > 0:
    print()
    print("EPG FUNCIONANDO! Programas para hoje e amanha disponiveis.")
else:
    print()
    print("AVISO: Poucos programas para hoje/amanha.")
    sys.exit(1)
