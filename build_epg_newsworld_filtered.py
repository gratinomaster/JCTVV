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
import requests

M3U_URL = "https://github.com/gratinomaster/JCTV/raw/refs/heads/main/NEWSWORLDNOVOS.m3u"
LOCAL_M3U = "NEWSWORLDNOVOS.m3u"
OUTPUT = "EPGFULL.xml.gz"

EPG_SOURCES = [
    "https://epgshare01.online/epgshare01/epg_ripper_ALL_SOURCES1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_AU1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_NL1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_UK1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_BR1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_JP1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_DE1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_FR1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_TR1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_IN1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_ES1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_IT1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_PL1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz",
]


def norm(s):
    return re.sub(r'[\s\-_\.]+', '', s).lower()


print("1. Baixando M3U...")
m3u_text = ""
try:
    r = requests.get(M3U_URL, timeout=60, allow_redirects=True)
    r.raise_for_status()
    m3u_text = r.text
    if m3u_text.count('#EXTINF') == 0:
        print("  M3U remoto sem canais, usando local...")
        m3u_text = ""
except Exception as e:
    print(f"  ERRO ao baixar M3U remoto: {e}")

if not m3u_text or m3u_text.count('#EXTINF') == 0:
    if os.path.exists(LOCAL_M3U):
        print(f"  Usando arquivo local: {LOCAL_M3U}")
        with open(LOCAL_M3U, 'r', encoding='utf-8') as f:
            m3u_text = f.read()
    else:
        print("  ERRO: Nenhum M3U disponivel!")
        sys.exit(1)

m3u_entries = []
seen_display = set()
for line in m3u_text.splitlines():
    if not line.startswith('#EXTINF'):
        continue
    tid_m = re.search(r'tvg-id="([^"]*)"', line)
    tname_m = re.search(r'tvg-name="([^"]*)"', line)
    logo_m = re.search(r'tvg-logo="([^"]*)"', line)
    comma_m = re.search(r',([^,]+)$', line)
    if not comma_m:
        continue
    tvg_id = (tid_m.group(1) if tid_m else "").strip()
    tvg_name = (tname_m.group(1) if tname_m else "").strip()
    logo = (logo_m.group(1) if logo_m else "").strip()
    display = comma_m.group(1).strip()
    if display in seen_display:
        continue
    seen_display.add(display)
    m3u_entries.append({'tvg_id': tvg_id, 'tvg_name': tvg_name, 'logo': logo, 'display': display})

tvg_ids = set(e['tvg_id'] for e in m3u_entries if e['tvg_id'])
tvg_norm = {norm(t): t for t in tvg_ids}

m3u_names = {}
m3u_logos = {}
m3u_displays = {}
for e in m3u_entries:
    if e['tvg_id']:
        name_base = re.sub(r'\s*\(.*$', '', e['display']).strip()
        m3u_names[e['tvg_id']] = name_base or e['display']
        m3u_logos[e['tvg_id']] = e['logo'] or e['tvg_name']
        m3u_displays[e['tvg_id']] = e['display']

print(f"  {len(m3u_entries)} canais, {len(tvg_ids)} tvg-ids unicos")

# Casamento ESTRITO: apenas igualdade exata (normalizada) do tvg-id do EPG
# ou do display-name do EPG contra o nome base do canal no M3U.
# Nada de substring: evita poluicao (ex: "TVI" em "UTV Iraq", "CTV" em "KCTV").
def strict_match(epg_cid, display_name):
    nc = norm(epg_cid)
    if nc in tvg_norm:
        return tvg_norm[nc]
    if display_name:
        ndn = norm(display_name)
        for tid in tvg_ids:
            if norm(m3u_names.get(tid, '')) == ndn:
                return tid
    return None

print("\n2. Baixando e filtrando fontes EPG...")
matched_ids = set()
all_channels = OrderedDict()
all_programmes = OrderedDict()
seen_progs = set()
id_remap = {}


def download(url, timeout=180):
    try:
        req = requests.get(url, timeout=timeout, allow_redirects=True,
                          headers={"User-Agent": "Mozilla/5.0"})
        if req.status_code != 200:
            print(f"    Skipped (status={req.status_code})")
            return None
        data = req.content
        if len(data) < 100:
            print(f"    Skipped (muito pequeno: {len(data)} bytes)")
            return None
        print(f"    {len(data):,} bytes")
        return data
    except Exception as e:
        print(f"    Erro: {e}")
        return None


def process_epg(raw_bytes):
    ch_count = 0
    pr_count = 0
    try:
        if raw_bytes[:2] == b'\x1f\x8b':
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
                m3u_id = strict_match(cid, display_name)
                if m3u_id and m3u_id not in id_remap:
                    id_remap[cid] = m3u_id
                    matched_ids.add(m3u_id)
                    ch = copy.deepcopy(elem)
                    ch.set('id', m3u_id)
                    all_channels[m3u_id] = ch
                    ch_count += 1
                elem.clear()
            elif tag == 'programme':
                ch = elem.get('channel', '')
                m3u_id = id_remap.get(ch)
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
        print(f"    Erro parse: {e}")
    return ch_count, pr_count


for url in EPG_SOURCES:
    print(f"  {url.split('/')[-1]}:")
    raw = download(url)
    if raw is None:
        continue
    ch, pr = process_epg(raw)
    print(f"    -> +{ch} canais, +{pr} programas")
    if len(matched_ids) >= len(tvg_ids):
        print(f"  Todos os {len(tvg_ids)} canais match!")
        break

print(f"\n3. Resultado: {len(matched_ids)}/{len(tvg_ids)} canais, {len(all_programmes)} programas")

matched_list = sorted(matched_ids)
print(f"  Canais com EPG: {matched_list}")
missing = sorted(set(tvg_ids) - matched_ids)
if missing:
    print(f"  Sem EPG ({len(missing)}): {missing}")

# Canais do M3U sem dados no EPG entram como <channel> simples (sem programas
# inventados), para que o guia reconheca o canal sem poluir a programacao.
for tid in sorted(tvg_ids):
    if tid not in all_channels:
        ch = ET.Element("channel", attrib={"id": tid})
        dn = ET.SubElement(ch, "display-name")
        dn.text = m3u_displays.get(tid, m3u_names.get(tid, tid))
        if m3u_logos.get(tid):
            ET.SubElement(ch, "icon", attrib={"src": m3u_logos[tid]})
        all_channels[tid] = ch
        print(f"  Canal {tid} incluido sem programacao (sem dados disponiveis)")

print("\n4. Salvando EPGFULL.xml.gz...")
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
print(f"  {OUTPUT}: {file_size:,} bytes (comprimido), {len(xml_data):,} bytes (raw)")

print("\n5. Testando EPG...")
with gzip.open(OUTPUT, 'rb') as f:
    test_xml = f.read().decode('utf-8', errors='ignore')

test_root = ET.fromstring(test_xml)
canais = test_root.findall("channel")
programas = test_root.findall("programme")

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

print(f"  Canais no EPG: {len(canais)}")
print(f"  Programas no EPG: {len(programas)}")
print(f"  Programas hoje ({hoje}): {prog_hoje} em {len(canais_hoje)} canais")
print(f"  Programas amanha ({amanha}): {prog_amanha} em {len(canais_amanha)} canais")

if canais_hoje:
    print(f"  Canais com dados de hoje: {sorted(canais_hoje)[:15]}{'...' if len(canais_hoje) > 15 else ''}")
if canais_amanha:
    print(f"  Canais com dados de amanha: {sorted(canais_amanha)[:15]}{'...' if len(canais_amanha) > 15 else ''}")

print("\n  Detalhes por canal:")
for ch in canais:
    cid = ch.get('id')
    dn = ch.find("display-name")
    name = dn.text if dn is not None and dn.text else "N/A"
    ch_progs = sum(1 for p in programas if p.get("channel") == cid)
    ch_hoje = sum(1 for p in programas if p.get("channel") == cid and p.get("start", "")[:8] == hoje)
    ch_amanha = sum(1 for p in programas if p.get("channel") == cid and p.get("start", "")[:8] == amanha)
    print(f"    {cid}: {name} - total:{ch_progs} hoje:{ch_hoje} amanha:{ch_amanha}")

print()
if prog_hoje > 0 and prog_amanha > 0:
    print("EPG FUNCIONANDO! Programas para hoje e amanha disponiveis.")
else:
    print("AVISO: Faltam programas para hoje ou amanha.")
