#!/usr/bin/env python3
import re, gzip, io, copy, sys, os
import xml.etree.ElementTree as ET
import urllib.request
from collections import OrderedDict
from datetime import datetime, timedelta

M3U_URL = "https://github.com/gratinomaster/JCTV/raw/refs/heads/main/NEWSWORLDNOVOS.m3u"
CURRENT_EPG = "EPGFULL.xml.gz"
OUTPUT = "EPGFULL.xml.gz"
FRESH_EPG_URL = "https://epgshare01.online/epgshare01/epg_ripper_ALL_SOURCES1.xml.gz"

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
print(f"  {len(m3u_ids)} tvg-ids no M3U")

print("\n2. Lendo EPG atual...")
with gzip.open(CURRENT_EPG, "rb") as f:
    tree = ET.parse(f)
root = tree.getroot()

matched_ids = set()
channel_elems = OrderedDict()
programme_elems = OrderedDict()
seen_progs = set()

for channel in root.findall("channel"):
    cid = channel.get("id", "")
    if not cid:
        continue
    nc = norm(cid)
    if cid in m3u_ids:
        key = cid
    elif nc in m3u_norm:
        key = m3u_norm[nc]
    else:
        continue
    if key not in matched_ids:
        matched_ids.add(key)
        channel_elems[key] = channel

for prog in root.findall("programme"):
    ch = prog.get("channel", "")
    nc = norm(ch)
    if ch in matched_ids or nc in m3u_norm and m3u_norm[nc] in matched_ids:
        key = ch if ch in matched_ids else m3u_norm[nc]
        start = prog.get("start", "")
        stop = prog.get("stop", "")
        pkey = f"{key}|{start}|{stop}"
        if pkey not in seen_progs:
            seen_progs.add(pkey)
            programme_elems[pkey] = prog

print(f"  {len(matched_ids)} canais, {len(programme_elems)} programas do EPG atual")

missing = sorted(m3u_ids - matched_ids)
print(f"\n3. Canais faltando no EPG: {missing if missing else 'nenhum'}")

if missing:
    print(f"\n4. Baixando EPG fresco para tentar encontrar canais faltando...")
    try:
        req = urllib.request.Request(FRESH_EPG_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=600) as resp:
            fresh_data = resp.read()
        print(f"  Baixado {len(fresh_data)} bytes")

        if fresh_data[:2] == b'\x1f\x8b':
            f = gzip.GzipFile(fileobj=io.BytesIO(fresh_data))
        else:
            f = io.BytesIO(fresh_data)

        new_channels = 0
        new_progs = 0
        id_remap = {}

        for event, elem in ET.iterparse(f, events=("end",)):
            if elem.tag == "channel":
                cid = elem.get("id", "")
                if not cid:
                    elem.clear()
                    continue
                nc = norm(cid)
                if cid in m3u_ids:
                    m3u_id = cid
                elif nc in m3u_norm:
                    m3u_id = m3u_norm[nc]
                else:
                    elem.clear()
                    continue
                if m3u_id and m3u_id not in matched_ids:
                    id_remap[cid] = m3u_id
                    matched_ids.add(m3u_id)
                    ch = copy.deepcopy(elem)
                    ch.set("id", m3u_id)
                    channel_elems[m3u_id] = ch
                    new_channels += 1
                elem.clear()
            elif elem.tag == "programme":
                ch = elem.get("channel", "")
                if not ch:
                    elem.clear()
                    continue
                nc = norm(ch)
                m3u_id = id_remap.get(ch)
                if m3u_id is None:
                    if ch in matched_ids:
                        m3u_id = ch
                    elif nc in m3u_norm and m3u_norm[nc] in matched_ids:
                        m3u_id = m3u_norm[nc]
                if m3u_id:
                    start = elem.get("start", "")
                    stop = elem.get("stop", "")
                    pkey = f"{m3u_id}|{start}|{stop}"
                    if pkey not in seen_progs:
                        seen_progs.add(pkey)
                        pr = copy.deepcopy(elem)
                        pr.set("channel", m3u_id)
                        programme_elems[pkey] = pr
                        new_progs += 1
                elem.clear()

        print(f"  Adicionados {new_channels} canais e {new_progs} programas do EPG fresco")
    except Exception as e:
        print(f"  Erro baixando EPG fresco: {e}")

still_missing = sorted(m3u_ids - matched_ids)
if still_missing:
    print(f"\n  Ainda faltando: {still_missing}")
else:
    print(f"\n  Todos os canais encontrados!")

print(f"\n5. Salvando EPG filtrado...")
root_out = ET.Element("tv", attrib={"generator-info-name": "EPGFULL"})
for ch in channel_elems.values():
    root_out.append(ch)
for prog in programme_elems.values():
    root_out.append(prog)

tree_out = ET.ElementTree(root_out)
buf = io.BytesIO()
tree_out.write(buf, encoding="utf-8", xml_declaration=True)

with gzip.open(OUTPUT, "wb") as f:
    f.write(buf.getvalue())

file_size = os.path.getsize(OUTPUT)
print(f"  Salvo: {OUTPUT} ({file_size} bytes)")

print(f"\n6. Testando EPG...")
with gzip.open(OUTPUT, "rb") as f:
    test_xml = f.read().decode("utf-8", errors="ignore")
test_root = ET.fromstring(test_xml)
canais = test_root.findall("channel")
programas = test_root.findall("programme")
print(f"  Canais: {len(canais)}")
print(f"  Programas: {len(programas)}")

hoje = datetime.now().strftime("%Y%m%d")
amanha = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
prog_hoje = sum(1 for p in programas if p.get("start", "")[:8] == hoje)
prog_amanha = sum(1 for p in programas if p.get("start", "")[:8] == amanha)

print(f"  Programas hoje ({hoje}): {prog_hoje}")
print(f"  Programas amanhã ({amanha}): {prog_amanha}")

if prog_hoje > 0 and prog_amanha > 0:
    print("\n✓ EPG FUNCIONANDO! Programas para hoje e amanhã disponíveis.")
    sys.exit(0)
else:
    print("\n✗ EPG COM PROBLEMAS! Faltam programas para hoje ou amanhã.")
    sys.exit(1)
