#!/usr/bin/env python3
import gzip
import io
import re
import os
import urllib.request
import xml.etree.ElementTree as ET
from collections import OrderedDict
from datetime import datetime, timedelta

M3U_FILE = "NEWSWORLDNOVOS.m3u"
OUTPUT = "EPGFULL.xml.gz"

EPG_SOURCES = [
    "https://epgshare01.online/epgshare01/epg_ripper_ALL_SOURCES1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_BR1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_AR1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_MX1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_UK1.xml.gz",
    "https://fastly.jsdelivr.net/gh/limaalef/BrazilTVEPG@main/epg.xml",
]

MANUAL_MAP = {
    "ABC News Live - ABC News": ["ABC News Live"],
    "Fox Business Go | Fox News Video": ["Fox Business HD", "Fox Business"],
    "Watch Fox News Channel Online | Stream Fox News": ["Fox News Channel", "Fox News"],
    "Watch CBS News 24/7, our free live news stream": ["CBS News"],
    "Video Tracking flood threats in Texas": [],
    "El Trece": ["Canal 13 de Argentina (El Trece)"],
    "América TV": ["Canal America TV (Argentina)", "América TV"],
    "Azteca Uno (-1h)": ["Canal Azteca Uno"],
    "Azteca Uno - 1H": ["Canal Azteca Uno -1 Hora"],
    "ADN 40 (1080p)": ["Canal ADN 40", "ADN 40"],
    "Imagen TV+ (720p)": ["Imagen TV"],
    "Milenio Televisión (720p)": ["Milenio Televisión"],
    "Canal 14 (1080p)": ["Canal 14 de México"],
    "TV UNAM (1080p)": ["Canal TVUNAM"],
    "Canal del Congreso": ["Canal del Congreso"],
    "Justicia TV": ["Justicia TV"],
    "ENCUENTRO": ["Encuentro"],
    "PAKAPAKA": ["Pakapaka"],
    "TYC SPORTS": ["TyC Sports"],
    "Canal 26 HD": ["Canal 26"],
    "Canal 22": ["Canal 22 de México"],
    "VOLVER": ["Volver"],
    "CANAL LUZ": ["Canal Luz"],
    "CANAL DE LA MÚSICA": ["Canal de la Música"],
    "CANAL ORBE 21": ["Canal Orbe 21"],
    "TELSUR": ["Telesur"],
    "Canal Rural": ["Canal Rural"],
    "A24": ["A24"],
    "C5N": ["C5N"],
    "TN - Todo Noticias": ["TN"],
    "Crónica TV": ["Crónica TV"],
    "Canal de la Ciudad": ["Canal de la Ciudad"],
    "Disney Channel Latin America": ["Disney Channel"],
    "Disney Jr. Latin America": ["Disney Jr."],
    "Sony Channel (1080p)": ["Sony Channel"],
    "Bravo TV": ["Bravo TV"],
    "Telemundo Internacional (1080p)": ["Telemundo Internacional"],
    "AMC Latin America (1080p) AR": ["AMC"],
    "MTV Latin America (1080p) AR": ["MTV"],
    "El Gourmet (1080p)": ["El Gourmet"],
    "Comedy Central Latin America (1080p) AR": ["Comedy Central"],
    "E! Latin America (1080p) AR": ["E! Entertainment Television"],
    "DSports (1080p) AR": ["DSports Argentina"],
    "Radio Maria TV (1080p)": ["Radio Maria"],
    "LN+": ["LN+"],
    "CANAL 10 MAR DEL PLATA": [],
    "CANAL E": ["Canal E"],
    "CANAL 5 ROSARIO": [],
    "Teste Live CDN Google": [],
    "Telefe Buenos Aires": ["Telefe"],
    "Telefe Jujuy": ["Telefe"],
    "Telefe Neuquén": ["Telefe"],
    "El Nueve": ["El Nueve"],
    "24/7 Canal de Noticias": [],
    "NET TV 27.2 - TDA 27.2": ["NET TV"],
    "Ciudad Magazine": ["Ciudad Magazine"],
    "Argentinísima Satelital": [],
    "Telemax": ["Telemax"],
    "GARAGE TV": ["Garage TV"],
    "MusicTop": ["Music Top"],
    "Canal 10 Cordoba": [],
    "TV Universidad": [],
    "Canal 9 Litoral": [],
    "Canal 13 Jujuy TV": [],
    "América Canal 4 Posadas": [],
    "Aire de Santa Fe": [],
    "5TV Corrientes": [],
    "UNIFE 25.1 - TDA 25.1": [],
    "Norte": [],
    "Camaras de Villa Gesell": [],
    "Construir TV": ["Construir TV"],
    "América Sports": [],
    "IP Noticias": [],
    "CANAL 8 SAN JUAN": [],
    "CANAL 6 DIGITAL": [],
    "CANAL 79 MAR DEL PLATA": [],
    "CANAL 4 JUJUY": [],
    "CANAL 3 LA PAMPA": [],
    "CANAL 3 LAS HERAS": [],
    "CANAL 2 GUALEGUAY": [],
    "CANAL 9 TELEVIDA": [],
    "CANAL DE LA CIUDAD": ["Canal de la Ciudad"],
    "CARAS TV": [],
    "ECO TV": [],
    "AUNAR": [],
    "CADENA 103": [],
    "CATAMARCA TV": [],
    "LITUS TV": [],
    "ALTERNA TV": [],
    "INCAA TV": [],
    "TV MANÁ ARGENTINA": [],
    "UNIFE TV": [],
    "QUIERO MÚSICA TV": [],
    "ARGENTINA 12": [],
    "CN23": [],
    "SAN PEDRO TV": [],
    "TV SOLIDARIA": [],
    "Radio Sublime Gracia TV": [],
    "Radio UP": [],
    "Unife TV": [],
    "VTV": ["VTV"],
    "CANAL DE LA MÚSICA": ["Canal de la Música"],
    "RT EN ESPAÑOL": ["RT"],
    "EL DESTAPE TV": [],
    "FRANCE 24 ESPAÑOL": ["France 24"],
    "BRAVO TV": ["Bravo TV"],
    "TN": ["TN"],
    "CRÓNICA TV": ["Crónica TV"],
    "CANAL 5 TV Cozumel (1080p)": [],
    "Disney Channel Latin America (1080p) RAW": ["Disney Channel"],
    "Disney Channel Latin America Center (1080p)": ["Disney Channel"],
    "Disney Channel Latin America Panregional HD (1080p)": ["Disney Channel"],
    "Disney Channel Latin America Panregional HD (1080p) RAW": ["Disney Channel"],
    "Disney Jr. Latin America North HD (1080p)": ["Disney Jr."],
    "Disney Jr. Latin America North HD (1080p) RAW": ["Disney Jr."],
    "Disney Jr. Latin America South (1080p)": ["Disney Jr."],
    "Disney Jr. Latin America South HD (1080p)": ["Disney Jr."],
    "Disney Jr. Latin America South HD (1080p) RAW": ["Disney Jr."],
    "Quiero Musica en mi Idioma (1080p)": [],
    "Transmissão Ao Vivo ABTV": [],
}


def norm(s):
    return re.sub(r'[\s\-_\.]+', '', s).lower()


def download(url, timeout=120):
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


def parse_m3u():
    with open(M3U_FILE, "r", encoding="utf-8", errors="replace") as f:
        m3u = f.read()

    extinf_pattern = re.compile(
        r'#EXTINF:-1\s+'
        r'(?:tvg-id="([^"]*)"\s+)?'
        r'(?:tvg-name="([^"]*)"\s+)?'
        r'[^,]*,'
        r'(.+)$',
        re.MULTILINE
    )

    entries = []
    seen_display = set()
    for m in extinf_pattern.finditer(m3u):
        tvg_id = (m.group(1) or "").strip()
        tname = (m.group(2) or "").strip()
        display = m.group(3).strip()
        if display in seen_display:
            continue
        seen_display.add(display)
        entries.append({
            'tvg_id': tvg_id,
            'tvg_name': tname,
            'display': display,
        })

    return entries


def find_best_match(names, cid, entry):
    display = entry['display']
    tvg_id = entry['tvg_id']
    tvg_name = entry['tvg_name']

    if display in MANUAL_MAP:
        targets = MANUAL_MAP[display]
        if not targets:
            return False
        for target in targets:
            tn = norm(target)
            if norm(cid) == tn:
                return True
            for name in names:
                if norm(name) == tn:
                    return True

    if tvg_id:
        if norm(tvg_id) == norm(cid):
            return True

    if tvg_name:
        tn = norm(tvg_name)
        if tn == norm(cid):
            return True
        for name in names:
            if norm(name) == tn:
                return True

    for name in names:
        nn = norm(name)
        dn = norm(display)
        if len(nn) >= 6 and nn == dn:
            return True

    return False


print("=" * 60)
print("FILTRANDO EPG PELO M3U: NEWSWORLDNOVOS.m3u")
print("=" * 60)

m3u_entries = parse_m3u()
print(f"Canais unicos no M3U: {len(m3u_entries)}")

print()
print("=" * 60)
print("Step 1: Baixando EPG e filtrando em unico passo")
print("=" * 60)

all_epg_names = {}
channels_out = OrderedDict()
programmes_out = OrderedDict()
seen_progs = set()
matched_epg_ids = set()
m3u_matched = []
m3u_unmatched = []

for url in EPG_SOURCES:
    data = download(url)
    if data is None:
        continue
    try:
        if url.endswith('.gz'):
            xml_data = gzip.decompress(data)
        else:
            xml_data = data if isinstance(data, bytes) else data.encode()

        current_cid = None
        current_names = []
        current_xml_str = None

        for event, elem in ET.iterparse(io.BytesIO(xml_data), events=("start", "end")):
            if event == "start":
                if elem.tag == "channel":
                    current_cid = elem.get("id", "")
                    current_names = []
                    current_xml_str = None
                continue

            if event == "end":
                if elem.tag == "display-name" and current_cid is not None:
                    text = elem.text or ""
                    if text:
                        current_names.append(text)

                elif elem.tag == "channel":
                    if current_cid:
                        if current_cid not in all_epg_names:
                            all_epg_names[current_cid] = current_names[:]
                        for entry in m3u_entries:
                            if find_best_match(current_names, current_cid, entry):
                                if current_cid not in matched_epg_ids:
                                    matched_epg_ids.add(current_cid)
                                    m3u_matched.append((entry['display'], current_cid, current_names[0] if current_names else current_cid))
                                if current_cid not in channels_out:
                                    channels_out[current_cid] = ET.tostring(elem, encoding="unicode")
                                break
                    current_cid = None
                    current_names = []

                elif elem.tag == "programme":
                    ch = elem.get("channel", "")
                    if ch in matched_epg_ids:
                        start = elem.get("start", "")
                        stop = elem.get("stop", "")
                        pkey = f"{ch}|{start}|{stop}"
                        if pkey not in seen_progs:
                            seen_progs.add(pkey)
                            programmes_out[pkey] = ET.tostring(elem, encoding="unicode")

    except Exception as e:
        print(f"    Erro: {e}")
        import traceback; traceback.print_exc()

print(f"\n  Total canais EPG indexados: {len(all_epg_names)}")
print(f"  Canais M3U com match: {len(m3u_matched)}")
print(f"  Canais no EPG filtrado: {len(channels_out)}")
print(f"  Programas no EPG filtrado: {len(programmes_out)}")

if m3u_matched:
    print("\n  Matches encontrados:")
    for display, cid, epg_name in m3u_matched:
        print(f"    {display} -> {cid} ({epg_name})")

m3u_unmatched = [e['display'] for e in m3u_entries if e['display'] not in [m[0] for m in m3u_matched]]
if m3u_unmatched:
    print(f"\n  Sem match ({len(m3u_unmatched)}):")
    for display in m3u_unmatched:
        print(f"    {display}")

print()
print("=" * 60)
print("Step 2: Salvando EPGFULL.xml.gz")
print("=" * 60)

lines = ['<?xml version="1.0" encoding="utf-8"?>', "<tv>"]
lines.extend(channels_out.values())
lines.extend(programmes_out.values())
lines.append("</tv>")
xml_str = "\n".join(lines)

with gzip.open(OUTPUT, "wt", encoding="utf-8") as f:
    f.write(xml_str)

size = os.path.getsize(OUTPUT)
print(f"  Salvo: {OUTPUT} ({size:,} bytes)")

print()
print("=" * 60)
print("Step 3: Testando EPG")
print("=" * 60)

with gzip.open(OUTPUT, "rb") as f:
    test_root = ET.fromstring(f.read())

canais = test_root.findall("channel")
programas = test_root.findall("programme")
print(f"  Total canais no EPG: {len(canais)}")
print(f"  Total programas no EPG: {len(programas)}")

hoje = datetime.now().strftime("%Y%m%d")
amanha = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
prog_hoje = sum(1 for p in programas if p.get("start", "")[:8] == hoje)
prog_amanha = sum(1 for p in programas if p.get("start", "")[:8] == amanha)
print(f"  Programas hoje ({hoje}): {prog_hoje}")
print(f"  Programas amanha ({amanha}): {prog_amanha}")

print()
print("Canais no EPG gerado:")
for ch in canais:
    dn = ch.find("display-name")
    name = dn.text if dn is not None and dn.text else "N/A"
    ch_progs = sum(1 for p in programas if p.get("channel") == ch.get("id"))
    print(f"  {ch.get('id')}: {name} ({ch_progs} programas)")

print()
if prog_hoje > 0 and prog_amanha > 0:
    print("EPG FUNCIONANDO! Programas para hoje e amanha disponiveis.")
else:
    print("AVISO: Poucos programas para hoje/amanha.")
