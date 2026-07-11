#!/usr/bin/env python3
import re, gzip, io, copy, sys, os
import xml.etree.ElementTree as ET
import requests
from collections import OrderedDict
from datetime import datetime, timedelta

M3U_URL = "https://github.com/gratinomaster/JCTV/raw/refs/heads/main/NEWSWORLDNOVOS.m3u"
OUTPUT = "/home/runner/work/JCTVV/JCTVV/EPGFULL.xml.gz"

EPG_SOURCES = [
    "https://epgshare01.online/epgshare01/epg_ripper_ALL_SOURCES1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS2.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_UK1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_FR1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_DE1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_IT1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_ES1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_AR1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_AU1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_BR1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_IN1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_PT1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_ZA1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_KR1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_JP1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_TR1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_MX1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_PL1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_NL1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_SE1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_NO1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_AL1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_CO1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_PT1.xml.gz",
    "https://fastly.jsdelivr.net/gh/limaalef/BrazilTVEPG@main/epg.xml",
    "https://github.com/limaalef/BrazilTVEPG/raw/refs/heads/main/claro.xml",
    "https://github.com/limaalef/BrazilTVEPG/raw/refs/heads/main/vivoplay.xml",
    "https://github.com/limaalef/BrazilTVEPG/raw/refs/heads/main/globo.xml",
    "https://raw.githubusercontent.com/matthuisman/i.mjh.nz/master/PlutoTV/us.xml",
]

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

m3u_names = {}
for line in m3u_content.splitlines():
    m = re.search(r'tvg-id="([^"]*)"', line)
    name_match = re.search(r',([^,]+)$', line)
    if m and name_match:
        tid = m.group(1).strip()
        name = name_match.group(1).strip()
        name_base = re.sub(r'\s*\(.*$', '', name).strip()
        m3u_names[tid] = name_base

print(f"  Encontrados {len(m3u_ids)} tvg-ids no M3U")

epg_urls_from_m3u = []
for match in re.finditer(r'(?:url-tvg|x-tvg-url)="([^"]*)"', m3u_content):
    for u in match.group(1).replace(',', ' ').split():
        u = u.strip()
        if u and u not in epg_urls_from_m3u:
            epg_urls_from_m3u.append(u)

all_sources = epg_urls_from_m3u + [u for u in EPG_SOURCES if u not in epg_urls_from_m3u]
print(f"2. Fontes EPG: {len(all_sources)} URLs")

matched_ids = set()
seen_progs = set()
all_channels = OrderedDict()
all_programmes = OrderedDict()

def fuzzy_match_m3u_id(epg_cid, epg_display_name):
    nc = norm(epg_cid)
    if nc in m3u_norm_set:
        return m3u_norm[nc]
    for m3u_id in m3u_ids:
        nm = norm(m3u_id)
        if nm in nc or nc in nm:
            return m3u_id
    if epg_display_name:
        ndn = norm(epg_display_name)
        for tid, base_name in m3u_names.items():
            nb = norm(base_name)
            if nb == ndn or ndn in nb or nb in ndn:
                return tid
    for tid, base_name in m3u_names.items():
        nb = norm(base_name)
        if nb in nc:
            return tid
    return None

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
                dn = elem.find('display-name')
                display_name = dn.text.strip() if dn is not None and dn.text else ''
                m3u_id = fuzzy_match_m3u_id(cid, display_name)

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
                    m3u_id = fuzzy_match_m3u_id(ch, '')
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
for url in all_sources:
    data = download_epg(url)
    if data is None:
        continue
    ch, pr = process_epg_xml(data)
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

print(f"  Programas hoje ({hoje}): {prog_hoje} em {len(canais_hoje)} canais")
print(f"  Programas amanhã ({amanha}): {prog_amanha} em {len(canais_amanha)} canais")

if prog_hoje > 0 and prog_amanha > 0:
    print("\nEPG FUNCIONANDO! Programas para hoje e amanhã disponíveis.")
    sys.exit(0)
else:
    print("\nEPG COM PROBLEMAS! Faltam programas para hoje ou amanhã.")
    sys.exit(1)
