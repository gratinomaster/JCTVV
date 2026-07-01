#!/usr/bin/env python3
import re, gzip, io, copy, sys, os
import xml.etree.ElementTree as ET
import requests
from collections import OrderedDict
from datetime import datetime, timedelta

M3U_URL = "https://github.com/gratinomaster/JCTV/raw/refs/heads/main/NEWSWORLDNOVOS.m3u"
OUTPUT = "/home/runner/work/JCTVV/JCTVV/EPGFULL.xml.gz"

def norm(s):
    return re.sub(r'[\s\-_\.]+', '', s).lower()

print("1. Baixando M3U...")
r = requests.get(M3U_URL, timeout=60, allow_redirects=True)
m3u_content = r.text

m3u_ids = set()
for match in re.finditer(r'tvg-id="([^"]*)"', m3u_content):
    tid = match.group(1).strip()
    if tid and tid != "0" and tid != "(no tvg-id)":
        m3u_ids.add(tid)

m3u_norm = {norm(t): t for t in m3u_ids}
m3u_norm_set = set(m3u_norm.keys())
print(f"  Encontrados {len(m3u_ids)} tvg-ids no M3U: {sorted(m3u_ids)}")

epg_urls = []
for match in re.finditer(r'(?:url-tvg|x-tvg-url)="([^"]*)"', m3u_content):
    for u in match.group(1).replace(',', ' ').split():
        u = u.strip()
        if u and u not in epg_urls:
            epg_urls.append(u)

print(f"2. Fontes EPG do M3U: {epg_urls}")

matched_ids = set()
seen_progs = set()
all_channels = OrderedDict()
all_programmes = OrderedDict()

def download_epg(url):
    print(f"  Baixando EPG: {url}")
    try:
        r = requests.get(url, timeout=300, allow_redirects=True)
        if r.status_code != 200:
            print(f"    Skipped (status={r.status_code})")
            return None
        if len(r.content) < 100:
            print(f"    Skipped (too small: {len(r.content)})")
            return None
        print(f"    Got {len(r.content)} bytes")
        return r.content
    except Exception as e:
        print(f"    Error: {e}")
        return None

def process_epg_xml(xml_bytes):
    new_ch = 0
    new_pr = 0
    try:
        if xml_bytes[:2] == b'\x1f\x8b':
            f = gzip.GzipFile(fileobj=io.BytesIO(xml_bytes))
        else:
            f = io.BytesIO(xml_bytes)

        id_remap = {}
        context = ET.iterparse(f, events=('end',))
        for event, elem in context:
            tag = elem.tag
            if tag == 'channel':
                cid = elem.get('id', '')
                if not cid:
                    elem.clear()
                    continue
                nc = norm(cid)
                m3u_id = None
                if cid in m3u_ids:
                    m3u_id = cid
                elif nc in m3u_norm_set:
                    m3u_id = m3u_norm[nc]

                if m3u_id:
                    id_remap[cid] = m3u_id
                    if m3u_id not in matched_ids:
                        matched_ids.add(m3u_id)
                        ch = copy.deepcopy(elem)
                        ch.set('id', m3u_id)
                        all_channels[m3u_id] = ch
                        new_ch += 1
            elif tag == 'programme':
                ch = elem.get('channel', '')
                if not ch:
                    elem.clear()
                    continue
                m3u_id = id_remap.get(ch)
                if m3u_id is None:
                    nc = norm(ch)
                    if ch in m3u_ids:
                        m3u_id = ch
                    elif nc in m3u_norm_set:
                        m3u_id = m3u_norm[nc]
                if m3u_id:
                    start = elem.get('start', '')
                    stop = elem.get('stop', '')
                    key = f"{m3u_id}|{start}|{stop}"
                    if key not in seen_progs:
                        seen_progs.add(key)
                        pr = copy.deepcopy(elem)
                        pr.set('channel', m3u_id)
                        all_programmes[key] = pr
                        new_pr += 1
            elem.clear()
    except ET.ParseError as e:
        print(f"    XML parse error: {e}")
    return new_ch, new_pr

print("\n3. Processando fontes EPG...")
for url in epg_urls:
    data = download_epg(url)
    if data is None:
        continue
    ch, pr = process_epg_xml(data)
    print(f"    -> {ch} novos canais, {pr} novos programas")

print(f"\n4. Total: {len(matched_ids)} canais, {len(all_programmes)} programas")

missing = [tid for tid in sorted(m3u_ids) if tid not in matched_ids]
if missing:
    print(f"  Canais não encontrados no EPG ({len(missing)}): {missing}")
else:
    print("  Todos os canais encontrados!")

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
print(f"\n5. Salvo: {OUTPUT} ({file_size} bytes)")

print("\n6. Testando EPG gerado...")
with gzip.open(OUTPUT, 'rb') as f:
    test_xml = f.read().decode('utf-8', errors='ignore')

test_root = ET.fromstring(test_xml)
canais = test_root.findall("channel")
programas = test_root.findall("programme")

print(f"  Canais no EPG: {len(canais)}")
print(f"  Programas no EPG: {len(programas)}")

hoje = datetime.now().strftime("%Y%m%d")
amanha = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")

prog_hoje = 0
prog_amanha = 0

for prog in programas:
    start = prog.get("start", "")[:8]
    if start == hoje:
        prog_hoje += 1
    elif start == amanha:
        prog_amanha += 1

print(f"  Programas hoje ({hoje}): {prog_hoje}")
print(f"  Programas amanhã ({amanha}): {prog_amanha}")

if prog_hoje > 0 and prog_amanha > 0:
    print("\n✓ EPG FUNCIONANDO! Programas para hoje e amanhã disponíveis.")
    sys.exit(0)
else:
    print("\n✗ EPG COM PROBLEMAS! Faltam programas para hoje ou amanhã.")
    sys.exit(1)
