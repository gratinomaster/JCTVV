#!/usr/bin/env python3
import re, gzip, io, copy, sys
import xml.etree.ElementTree as ET
import requests
from collections import OrderedDict

M3U_URL = "https://github.com/gratinomaster/JCTV/raw/refs/heads/main/NEWSWORLDNOVOS.m3u"
OUTPUT = "/home/runner/work/JCTV/JCTV/EPGFULL.xml.gz"

def norm(s):
    return re.sub(r'[\s\-_\.]+', '', s).lower()

print("1. Baixando M3U...")
r = requests.get(M3U_URL, timeout=60, allow_redirects=True)
m3u_content = r.text

m3u_ids = set()
m3u_names = {}
for match in re.finditer(r'tvg-id="([^"]*)"', m3u_content):
    tid = match.group(1).strip()
    if tid and tid != "0" and tid != "(no tvg-id)":
        m3u_ids.add(tid)

for match in re.finditer(r'tvg-id="([^"]*)"[^>]*tvg-name="([^"]*)"', m3u_content):
    tid = match.group(1).strip()
    name = match.group(2).strip()
    if tid and name:
        m3u_names[tid] = name

m3u_norm_ids = {norm(t) for t in m3u_ids}
print(f"  Encontrados {len(m3u_ids)} tvg-ids no M3U")
for tid in sorted(m3u_ids):
    name = m3u_names.get(tid, '')
    print(f"    {tid}: {name}")

epg_urls_match = re.search(r'x-tvg-url="([^"]*)"', m3u_content)
if epg_urls_match:
    epg_urls = [u.strip() for u in epg_urls_match.group(1).split(',')]
else:
    epg_urls = [
        "https://epg.pw/xmltv/epg_US.xml.gz",
        "https://epg.pw/xmltv/epg_GB.xml.gz",
    ]

print(f"\n2. Fontes EPG: {len(epg_urls)} URLs")

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

def process_epg_xml(xml_bytes, valid_ids, valid_norm):
    new_ch = 0
    new_pr = 0
    try:
        if xml_bytes[:2] == b'\x1f\x8b':
            raw = gzip.GzipFile(fileobj=io.BytesIO(xml_bytes)).read()
        else:
            raw = xml_bytes

        tree = ET.parse(io.BytesIO(raw))
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
        print(f"    XML parse error: {e}")
    return new_ch, new_pr

print("\n3. Processando fontes EPG...")
for url in epg_urls:
    data = download_epg(url)
    if data is None:
        continue
    ch, pr = process_epg_xml(data, m3u_ids, m3u_norm_ids)
    print(f"    -> {ch} novos canais, {pr} novos programas")

print(f"\n4. Total: {len(matched_ids)} canais, {len(all_programmes)} programas")

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

print(f"\n5. Salvo: {OUTPUT} ({len(xml_data)} bytes uncompressed, {len(buf.getvalue())} compressed)")

print("\n6. Testando EPF gerado...")
import xml.etree.ElementTree as ET2
from datetime import datetime, timedelta

with gzip.open(OUTPUT, 'rb') as f:
    test_xml = f.read().decode('utf-8', errors='ignore')

test_root = ET2.fromstring(test_xml)
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
