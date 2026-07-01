#!/usr/bin/env python3
import gzip, re, sys, os, io, urllib.request
import xml.etree.ElementTree as ET
from collections import OrderedDict

M3U_URL = "https://github.com/gratinomaster/JCTV/raw/refs/heads/main/NEWSWORLDNOVOS.m3u"
OUTPUT = "EPGFULL.xml.gz"
EPG_URLS = [
    "https://iptv-epg.org/files/epg-us.xml.gz",
    "https://iptv-epg.org/files/epg-mx.xml.gz",
    "https://iptv-epg.org/files/epg-br.xml.gz",
    "https://iptv-epg.org/files/epg-ar.xml.gz",
]

def norm(s):
    return re.sub(r'[\s\-_\.]+', '', s).lower()

print("=" * 60)
print("1. Downloading M3U from GitHub")
print("=" * 60)
req = urllib.request.Request(M3U_URL, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=30) as resp:
    m3u_content = resp.read().decode("utf-8", errors="replace")
print(f"   Downloaded {len(m3u_content)} bytes")

tvg_ids = set()
for m in re.finditer(r'tvg-id="([^"]*)"', m3u_content):
    tid = m.group(1).strip()
    if tid and tid != "0":
        tvg_ids.add(tid)
tvg_norm = {norm(t): t for t in tvg_ids}
print(f"   {len(tvg_ids)} unique tvg-ids found")

if not tvg_ids:
    print("ERROR: No tvg-ids found!")
    sys.exit(1)

print()
print("=" * 60)
print("2. Downloading & merging EPG sources")
print("=" * 60)
matched_ids = set()
channel_elements = OrderedDict()
programme_elements = OrderedDict()
seen_progs = set()

for epg_url in EPG_URLS:
    print(f"\n   Downloading {epg_url}...")
    try:
        req = urllib.request.Request(epg_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=300) as resp:
            epg_data = resp.read()
        print(f"   -> {len(epg_data)} bytes")
    except Exception as e:
        print(f"   -> Error: {e}")
        continue

    ch_count = 0
    pr_count = 0
    try:
        with gzip.open(io.BytesIO(epg_data), "rb") as f:
            for event, elem in ET.iterparse(f, events=("end",)):
                if elem.tag == "channel":
                    cid = elem.get("id", "")
                    if not cid:
                        elem.clear()
                        continue
                    key = None
                    if cid in tvg_ids:
                        key = cid
                    elif norm(cid) in tvg_norm:
                        key = tvg_norm[norm(cid)]
                    if key and key not in matched_ids:
                        matched_ids.add(key)
                        channel_elements[key] = ET.tostring(elem, encoding="unicode")
                        ch_count += 1
                    elem.clear()
                elif elem.tag == "programme":
                    ch = elem.get("channel", "")
                    if not ch:
                        elem.clear()
                        continue
                    key = None
                    if ch in matched_ids:
                        key = ch
                    elif norm(ch) in tvg_norm and tvg_norm[norm(ch)] in matched_ids:
                        key = tvg_norm[norm(ch)]
                    if key:
                        start = elem.get("start", "")
                        stop = elem.get("stop", "")
                        pkey = f"{key}|{start}|{stop}"
                        if pkey not in seen_progs:
                            seen_progs.add(pkey)
                            programme_elements[pkey] = ET.tostring(elem, encoding="unicode")
                            pr_count += 1
                    elem.clear()
    except Exception as e:
        print(f"   -> Parse error: {e}")
        continue
    print(f"   -> +{ch_count} channels, +{pr_count} programmes")

print(f"\nTotal: {len(matched_ids)} channels matched, {len(programme_elements)} programmes")

missing = sorted(tvg_ids - matched_ids)
if missing:
    print(f"Missing from EPG ({len(missing)}): {missing}")
else:
    print("All M3U channels found in EPG sources!")

print()
print("=" * 60)
print("3. Writing EPGFULL.xml.gz")
print("=" * 60)
lines = ['<?xml version="1.0" encoding="utf-8"?>', "<tv>"]
for buf in channel_elements.values():
    lines.append(buf)
for buf in programme_elements.values():
    lines.append(buf)
lines.append("</tv>")
xml_str = "\n".join(lines)

with gzip.open(OUTPUT, "wt", encoding="utf-8") as f:
    f.write(xml_str)

size = os.path.getsize(OUTPUT)
print(f"   Written to {OUTPUT} ({size} bytes, {len(xml_str)} uncompressed)")

print()
print("=" * 60)
print("4. Testing EPG")
print("=" * 60)
from datetime import datetime, timedelta, timezone
with gzip.open(OUTPUT, "rb") as f:
    test_root = ET.fromstring(f.read())
canais = test_root.findall("channel")
programas = test_root.findall("programme")
print(f"   Channels in EPG: {len(canais)}")
print(f"   Programmes in EPG: {len(programas)}")

hoje = datetime.now(timezone.utc).strftime("%Y%m%d")
amanha = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y%m%d")
prog_hoje = sum(1 for p in programas if p.get("start","")[:8] == hoje)
prog_amanha = sum(1 for p in programas if p.get("start","")[:8] == amanha)
print(f"   Programmes today ({hoje}): {prog_hoje}")
print(f"   Programmes tomorrow ({amanha}): {prog_amanha}")

if prog_hoje > 0 and prog_amanha > 0:
    print()
    print("=" * 60)
    print("   EPG WORKING! Programmes for today and tomorrow available.")
    print("=" * 60)
else:
    print()
    print("   EPG PROBLEM! Missing programmes for today or tomorrow.")
    sys.exit(1)

print("\nChannels in EPG:")
for ch in canais:
    dn = ch.find("display-name")
    name = dn.text if dn is not None and dn.text else "N/A"
    print(f"   {ch.get('id')}: {name}")
