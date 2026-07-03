#!/usr/bin/env python3
import gzip
import re
import xml.etree.ElementTree as ET
import os
from collections import OrderedDict
from datetime import datetime, timedelta
import urllib.request

M3U_URL = "https://github.com/gratinomaster/JCTV/raw/refs/heads/main/NEWSWORLDNOVOS.m3u"
INPUT_EPG = "EPGFULL.xml.gz"
OUTPUT_EPG = "EPGFULL.xml.gz"

def norm(s):
    return re.sub(r'[\s\-_\.]+', '', s).lower()

print("1. Baixando M3U...")
req = urllib.request.Request(M3U_URL, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=30) as resp:
    m3u_content = resp.read().decode("utf-8", errors="replace")

m3u_ids = set()
for m in re.finditer(r'tvg-id="([^"]*)"', m3u_content):
    tid = m.group(1).strip()
    if tid and tid != "0" and tid != "(no tvg-id)":
        m3u_ids.add(tid)

m3u_norm = {norm(t): t for t in m3u_ids}
print(f"  Encontrados {len(m3u_ids)} tvg-ids no M3U")

print("2. Filtrando EPG...")
matched_ids = set()
channel_elements = OrderedDict()
programme_elements = OrderedDict()
seen_progs = set()

with gzip.open(INPUT_EPG, "rb") as f:
    ch_count = 0
    prog_count = 0
    for event, elem in ET.iterparse(f, events=("end",)):
        if elem.tag == "channel":
            cid = elem.get("id")
            if not cid:
                elem.clear()
                continue
            key = None
            ncid = norm(cid)
            if cid in m3u_ids:
                key = cid
            elif ncid in m3u_norm:
                key = m3u_norm[ncid]
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
            elif nch in m3u_norm and m3u_norm[nch] in matched_ids:
                key = m3u_norm[nch]
            if key is None:
                elem.clear()
                continue
            start = elem.get("start", "")
            stop = elem.get("stop", "")
            pkey = f"{key}|{start}|{stop}"
            if pkey not in seen_progs:
                seen_progs.add(pkey)
                programme_elements[pkey] = ET.tostring(elem, encoding="unicode")
                prog_count += 1
            elem.clear()

print(f"  {ch_count} canais, {prog_count} programas mantidos")

print("3. Escrevendo EPGFULL.xml.gz...")
lines = ['<?xml version="1.0" encoding="utf-8"?>', "<tv>"]
for buf in channel_elements.values():
    lines.append(buf)
for buf in programme_elements.values():
    lines.append(buf)
lines.append("</tv>")

with gzip.open(OUTPUT_EPG, "wt", encoding="utf-8") as f:
    f.write("\n".join(lines))

out_size = os.path.getsize(OUTPUT_EPG)
print(f"  Salvo: {out_size} bytes")

print("4. Testando EPG...")
with gzip.open(OUTPUT_EPG, "rb") as f:
    test_xml = f.read().decode("utf-8", errors="ignore")

test_root = ET.fromstring(test_xml)
canais = test_root.findall("channel")
programas = test_root.findall("programme")
print(f"  Canais: {len(canais)}, Programas: {len(programas)}")

hoje = datetime.now().strftime("%Y%m%d")
amanha = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
prog_hoje = sum(1 for p in programas if p.get("start", "")[:8] == hoje)
prog_amanha = sum(1 for p in programas if p.get("start", "")[:8] == amanha)
print(f"  Programas hoje ({hoje}): {prog_hoje}")
print(f"  Programas amanhã ({amanha}): {prog_amanha}")

if prog_hoje > 0 and prog_amanha > 0:
    print("\n✓ EPG FUNCIONANDO! Programas para hoje e amanhã disponíveis.")
else:
    print("\n✗ EPG COM PROBLEMAS! Faltam programas para hoje ou amanhã.")
