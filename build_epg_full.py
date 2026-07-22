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
import urllib.request

M3U_URL = "https://github.com/gratinomaster/JCTV/raw/refs/heads/main/NEWSWORLDNOVOS.m3u"
M3U_LOCAL = "/tmp/NEWSWORLDNOVOS.m3u"
OUTPUT = "EPGFULL.xml.gz"

EPG_SOURCES = [
    "https://epgshare01.online/epgshare01/epg_ripper_ALL_SOURCES1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_BR1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_AR1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_MX1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_UK1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_FR1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_DE1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_ES1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_IT1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_NL1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_JP1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_AU1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_IN1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_PT1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_ZA1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_KR1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_TR1.xml.gz",
    "https://fastly.jsdelivr.net/gh/limaalef/BrazilTVEPG@main/epg.xml",
    "https://github.com/limaalef/BrazilTVEPG/raw/refs/heads/main/claro.xml",
    "https://github.com/limaalef/BrazilTVEPG/raw/refs/heads/main/vivoplay.xml",
    "https://github.com/limaalef/BrazilTVEPG/raw/refs/heads/main/globo.xml",
    "https://iptv-epg.org/files/epg-us.xml.gz",
    "https://iptv-epg.org/files/epg-br.xml.gz",
    "https://iptv-epg.org/files/epg-ar.xml.gz",
    "https://iptv-epg.org/files/epg-mx.xml.gz",
    "https://iptv-epg.org/files/epg-ve.xml.gz",
    "https://iptv-epg.org/files/epg-by.xml.gz",
    "https://iptv-epg.org/files/epg-ru.xml.gz",
    "https://iptv-epg.org/files/epg-ua.xml.gz",
    "https://iptv-epg.org/files/epg-nl.xml.gz",
    "https://iptv-epg.org/files/epg-jp.xml.gz",
    "https://iptv-epg.org/files/epg-th.xml.gz",
    "https://iptv-epg.org/files/epg-au.xml.gz",
    "https://iptv-epg.org/files/epg-qa.xml.gz",
]


def norm(s):
    return re.sub(r'[\s\-_\.]+', '', s).lower()


def download(url, timeout=300):
    print(f"  Baixando: {url.split('/')[-1]}", end=" ", flush=True)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
        if len(data) < 100:
            print(f"(pulado: {len(data)} bytes)")
            return None
        print(f"({len(data):,} bytes)")
        return data
    except Exception as e:
        print(f"(erro: {e})")
        return None


print("=" * 60)
print("0. Baixando lista M3U do GitHub")
print("=" * 60)

m3u_data = download(M3U_URL)
if m3u_data is None:
    print("ERRO: Nao foi possivel baixar a M3U")
    sys.exit(1)
m3u_text = m3u_data.decode("utf-8", errors="replace")

print()
print("=" * 60)
print("1. Carregando lista M3U")
print("=" * 60)

m3u_tvg_ids = set()
for m in re.finditer(r'tvg-id="([^"]*)"', m3u_text):
    tid = m.group(1).strip()
    if tid and tid != "0" and tid != "(no tvg-id)":
        m3u_tvg_ids.add(tid)

m3u_norm = {norm(t): t for t in m3u_tvg_ids}
m3u_norm_set = set(m3u_norm.keys())

m3u_names = {}
m3u_display_all = {}
for line in m3u_text.splitlines():
    m = re.search(r'tvg-id="([^"]*)"', line)
    name_match = re.search(r',([^,]+)$', line)
    if name_match:
        name = name_match.group(1).strip()
        display_norm = norm(name)
        if m:
            tid = m.group(1).strip()
            name_base = re.sub(r'\s*\(.*$', '', name).strip()
            m3u_names[tid] = name_base
            m3u_display_all[display_norm] = tid

print(f"  tvg-ids: {len(m3u_tvg_ids)}")
print(f"  canais: {len(m3u_names)}")

matched_ids = set()
seen_progs = set()
all_channels = OrderedDict()
all_programmes = OrderedDict()


MANUAL_ID_MAP = {
    "aljazeeraenglish.qa": "AlJazeera.qa",
    "aljazeera.qa": "AlJazeera.qa",
    "nhkworld.japan": "NHKWorld.jp",
    "nhkworld.jp": "NHKWorld.jp",
    "nhkworld.jpn": "NHKWorld.jp",
    "thaipbs.th": "ThaiPBS.th",
    "thai.pbs.th": "ThaiPBS.th",
    "rtvnoord.nl": "RTVNoord.nl",
    "rtvoost.nl": "RTVOost.nl",
    "rtvutrecht.nl": "RTVUtrecht.nl",
    "rtvdrenthe.nl": "RTVDrenthe.nl",
    "rtvmaastricht.nl": "RTVMaastricht.nl",
    "rtvrijnmond.nl": "RTVRijnmond.nl",
    "rtvpurmerend.nl": "RTVPurmerend.nl",
    "rtvwesterwolde.nl": "RTVWesterwolde.nl",
    "rtvrijnstreektv.nl": "RTVRijnstreekTV.nl",
    "mtvvolgograd.ru": "MTVVolgograd.ru",
    "maturtv.ru": "MaturTV.ru",
    "muzsoyuz.ru": "MuzSoyuz.ru",
    "ntm.ru": "NTM.ru",
    "nts.ru": "NTS.ru",
    "nizhniynovgorod24.ru": "NizhniyNovgorod24.ru",
    "prosveshchenie.ru": "Prosveshchenie.ru",
    "firstmusicchannel.by": "FirstMusicChannel.by",
    "lanettv.ua": "LanetTV.ua",
    "horseandcountry.au": "HorseandCountry.au",
}


def fuzzy_match(epg_cid, epg_display_name):
    nc = norm(epg_cid)
    if nc in MANUAL_ID_MAP:
        return MANUAL_ID_MAP[nc]
    if nc in m3u_norm_set:
        return m3u_norm[nc]
    for m3u_id in m3u_tvg_ids:
        nm = norm(m3u_id)
        if nm in nc or nc in nm:
            return m3u_id
    if epg_display_name:
        ndn = norm(epg_display_name)
        if ndn in MANUAL_ID_MAP:
            return MANUAL_ID_MAP[ndn]
        if ndn in m3u_display_all:
            return m3u_display_all[ndn]
        for tid, base_name in m3u_names.items():
            nb = norm(base_name)
            if nb == ndn or ndn in nb or nb in ndn:
                return tid
    for tid, base_name in m3u_names.items():
        nb = norm(base_name)
        if nb in nc:
            return tid
    return None


def process_epg_bytes(raw_bytes):
    new_ch = 0
    new_pr = 0
    id_remap = {}
    try:
        is_gz = raw_bytes[:2] == b'\x1f\x8b'
        if is_gz:
            f = gzip.GzipFile(fileobj=io.BytesIO(raw_bytes))
        else:
            f = io.BytesIO(raw_bytes)

        context = ET.iterparse(f, events=('end',))
        for event, elem in context:
            tag = elem.tag
            if tag not in ('channel', 'programme'):
                continue
            if tag == 'channel':
                cid = elem.get('id', '')
                if not cid:
                    elem.clear()
                    continue
                dn = elem.find('display-name')
                display_name = dn.text.strip() if dn is not None and dn.text else ''
                m3u_id = fuzzy_match(cid, display_name)
                if m3u_id:
                    id_remap[cid] = m3u_id
                    if m3u_id not in matched_ids:
                        matched_ids.add(m3u_id)
                        ch = copy.deepcopy(elem)
                        ch.set('id', m3u_id)
                        all_channels[m3u_id] = ch
                        new_ch += 1
                elem.clear()
            elif tag == 'programme':
                ch = elem.get('channel', '')
                if not ch:
                    elem.clear()
                    continue
                m3u_id = id_remap.get(ch)
                if m3u_id is None:
                    m3u_id = fuzzy_match(ch, '')
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
        print(f"    Erro XML: {e}")
    return new_ch, new_pr


print()
print("=" * 60)
print("2. Baixando e filtrando fontes EPG")
print("=" * 60)

for url in EPG_SOURCES:
    data = download(url)
    if data is None:
        continue
    ch, pr = process_epg_bytes(data)
    print(f"    -> +{ch} canais, +{pr} programas")

print()
print(f"3. Total: {len(matched_ids)} canais, {len(all_programmes)} programas")

print()
print("=" * 60)
print("4. Gerando EPGFULL.xml.gz")
print("=" * 60)

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
print(f"  Salvo: {OUTPUT} ({file_size:,} bytes)")

print()
print("=" * 60)
print("5. Testando EPG")
print("=" * 60)

with gzip.open(OUTPUT, 'rb') as f:
    test_xml = f.read().decode('utf-8', errors='ignore')

test_root = ET.fromstring(test_xml)
canais = test_root.findall("channel")
programas = test_root.findall("programme")

print(f"  Canais: {len(canais)}")
print(f"  Programas: {len(programas)}")

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
print(f"  Programas amanha ({amanha}): {prog_amanha} em {len(canais_amanha)} canais")

if canais_hoje:
    sample = sorted(canais_hoje)[:10]
    print(f"  Canais com dados hoje: {sample}{'...' if len(canais_hoje) > 10 else ''}")
if canais_amanha:
    sample = sorted(canais_amanha)[:10]
    print(f"  Canais com dados amanha: {sample}{'...' if len(canais_amanha) > 10 else ''}")

print()
if prog_hoje > 0 and prog_amanha > 0:
    print("  EPG FUNCIONANDO! Programas para hoje e amanha disponiveis.")
    sys.exit(0)
else:
    print("  AVISO: Poucos programas para hoje/amanha.")
    sys.exit(1)
