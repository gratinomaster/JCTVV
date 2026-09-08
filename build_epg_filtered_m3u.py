#!/usr/bin/env python3
import gzip
import re
import os
import sys
import xml.etree.ElementTree as ET
from collections import OrderedDict
from datetime import datetime, timedelta

M3U = "NEWSWORLDNOVOS.m3u"
SOURCE_EPG = "EPGFULL.xml"
OUTPUT = "EPGFULL.xml.gz"

def norm(s):
    return re.sub(r'[\s\-_\.]+', '', s).lower()

print("STEP 1: Loading tvg-ids from M3U")
tvg_ids = set()
for line in open(M3U, encoding="utf-8"):
    for m in re.finditer(r'tvg-id="([^"]*)"', line):
        t = m.group(1).strip()
        if t and t != "0" and t != "(no tvg-id)":
            tvg_ids.add(t)
tvg_norm = {norm(t): t for t in tvg_ids}
print(f"  {len(tvg_ids)} tvg-ids from M3U")

print("STEP 2: Filtering EPGFULL.xml by M3U channels")
wanted = set()
for cid in tvg_ids:
    wanted.add(norm(cid))

matched_ids = set()
channel_elements = OrderedDict()
programme_elements = OrderedDict()
seen_progs = set()

ctx = ET.iterparse(SOURCE_EPG, events=("end",))
for event, elem in ctx:
    if elem.tag == "channel":
        cid = elem.get("id", "")
        key = cid if cid in tvg_ids else tvg_norm.get(norm(cid))
        if key is not None and key not in matched_ids:
            matched_ids.add(key)
            channel_elements[key] = ET.tostring(elem, encoding="unicode")
        elem.clear()
    elif elem.tag == "programme":
        ch = elem.get("channel", "")
        key = ch if ch in matched_ids else tvg_norm.get(norm(ch))
        if key is not None and key in matched_ids:
            start = elem.get("start", "")
            stop = elem.get("stop", "")
            pkey = f"{key}|{start}|{stop}"
            if pkey not in seen_progs:
                seen_progs.add(pkey)
                programme_elements[pkey] = ET.tostring(elem, encoding="unicode")
        elem.clear()

print(f"  {len(matched_ids)} channels matched, {len(programme_elements)} programmes")
missing = sorted(set(tvg_ids) - matched_ids)
if missing:
    print(f"  Channels in M3U without EPG data: {missing}")

print("STEP 3: Writing EPGFULL.xml.gz (overwrite)")
lines = ['<?xml version="1.0" encoding="utf-8"?>', "<tv>"]
for buf in channel_elements.values():
    lines.append(buf)
for buf in programme_elements.values():
    lines.append(buf)
lines.append("</tv>")
xml_str = "\n".join(lines)

with gzip.open(OUTPUT, "wt", encoding="utf-8") as f:
    f.write(xml_str)
print(f"  Written {OUTPUT} ({os.path.getsize(OUTPUT):,} bytes compressed, {len(xml_str):,} uncompressed)")

print("STEP 4: Testing EPG")
root = ET.fromstring(xml_str)
canais = root.findall("channel")
programas = root.findall("programme")
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

sample = 0
if canais_hoje:
    for ch_id in sorted(canais_hoje):
        if sample >= 5:
            break
        titles = [p.findtext('title', '?') for p in programas if p.get("channel") == ch_id and p.get("start", "")[:8] == hoje][:3]
        print(f"    {ch_id}: {', '.join(titles)}")
        sample += 1

if prog_hoje > 0 and prog_amanha > 0:
    print(f"  EPG OK! {prog_hoje} programmes for today, {prog_amanha} for tomorrow.")
    sys.exit(0)
else:
    print("  EPG WARNING! Missing programmes for today or tomorrow.")
    sys.exit(1)
