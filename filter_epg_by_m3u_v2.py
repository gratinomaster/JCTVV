#!/usr/bin/env python3
import gzip, re, sys, os, io, urllib.request
import xml.etree.ElementTree as ET
from collections import OrderedDict
from datetime import datetime, timedelta

M3U_URL = "https://github.com/gratinomaster/JCTV/raw/refs/heads/main/NEWSWORLDNOVOS.m3u"
OUTPUT = "EPGFULL.xml.gz"
FRESH_EPG = "/tmp/epg_ripper.xml.gz"

def norm(s):
    return re.sub(r'[\s\-_\.]+', '', s).lower()

print("1. Baixando M3U do GitHub...")
req = urllib.request.Request(M3U_URL, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=30) as resp:
    m3u_content = resp.read().decode("utf-8", errors="replace")

tvg_ids = set()
for m in re.finditer(r'tvg-id="([^"]*)"', m3u_content):
    tid = m.group(1).strip()
    if tid and tid != "0":
        tvg_ids.add(tid)

tvg_norm = {norm(t): t for t in tvg_ids}
print(f"  {len(tvg_ids)} tvg-ids encontrados: {sorted(tvg_ids)}")

if not tvg_ids:
    print("ERRO: Nenhum tvg-id encontrado!")
    sys.exit(1)

print(f"2. Processando EPG fresco ({FRESH_EPG})...")
matched_ids = set()
channels = OrderedDict()
programmes = OrderedDict()
seen_progs = set()
ch_count = 0
prog_count = 0

with gzip.open(FRESH_EPG, "rb") as f:
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
                channels[key] = ET.tostring(elem, encoding="unicode")
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
                    programmes[pkey] = ET.tostring(elem, encoding="unicode")
                    prog_count += 1
            elem.clear()

print(f"  {ch_count} canais, {prog_count} programas")

print("3. Escrevendo EPGFULL.xml.gz...")
lines = ['<?xml version="1.0" encoding="utf-8"?>', "<tv>"]
lines.extend(channels.values())
lines.extend(programmes.values())
lines.append("</tv>")

xml_str = "\n".join(lines)
with gzip.open(OUTPUT, "wt", encoding="utf-8") as f:
    f.write(xml_str)

size = os.path.getsize(OUTPUT)
print(f"  {OUTPUT} ({size} bytes)")

print("\n4. Testando EPG...")
with gzip.open(OUTPUT, "rb") as f:
    test_root = ET.fromstring(f.read())

canais = test_root.findall("channel")
programas = test_root.findall("programme")
print(f"  Canais: {len(canais)}")
print(f"  Programas: {len(programas)}")

hoje = datetime.now().strftime("%Y%m%d")
amanha = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
prog_hoje = sum(1 for p in programas if p.get("start","")[:8]==hoje)
prog_amanha = sum(1 for p in programas if p.get("start","")[:8]==amanha)
print(f"  Programas hoje ({hoje}): {prog_hoje}")
print(f"  Programas amanhã ({amanha}): {prog_amanha}")

if prog_hoje > 0 and prog_amanha > 0:
    print("\n✓ EPG FUNCIONANDO! Programas para hoje e amanhã disponíveis.")
else:
    print("\n✗ EPG COM PROBLEMAS! Faltam programas para hoje ou amanhã.")
    sys.exit(1)

for ch in canais:
    dn = ch.find("display-name")
    name = dn.text if dn is not None and dn.text else "N/A"
    print(f"  {ch.get('id')}: {name}")
