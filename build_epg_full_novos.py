#!/usr/bin/env python3
import gzip
import io
import os
import re
import sys
import copy
import unicodedata
import xml.etree.ElementTree as ET
from collections import OrderedDict
from datetime import datetime, timedelta
import urllib.request

M3U_URL = "https://github.com/gratinomaster/JCTV/raw/refs/heads/main/NEWSWORLDNOVOS.m3u"
OUTPUT = "/home/runner/work/JCTVV/JCTVV/EPGFULL.xml.gz"
CACHE_DIR = "/tmp/opencode"

EPG_SOURCES = [
    "https://iptv-epg.org/files/epg-ar.xml.gz",
    "https://iptv-epg.org/files/epg-mx.xml.gz",
    "https://iptv-epg.org/files/epg-cl.xml.gz",
    "https://iptv-epg.org/files/epg-ve.xml.gz",
    "https://iptv-epg.org/files/epg-il.xml.gz",
    "https://iptv-epg.org/files/epg-br.xml.gz",
    "https://iptv-epg.org/files/epg-pt.xml.gz",
    "https://iptv-epg.org/files/epg-fr.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_BR1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_PT1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_FR1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_MX1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_AR1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_CL1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_CO1.xml.gz",
    "https://raw.githubusercontent.com/matthuisman/i.mjh.nz/master/PlutoTV/us.xml",
]

LOCAL_FILES = [
    "/home/runner/work/JCTVV/JCTVV/epgshare_US2.xml.gz",
]

# ids do M3U que divergem das fontes
ALIASES = {
    "13Rec.cl": "Canal13.cl",
    "AlJazeera.Arabic.net": "AlJazeera.us",
    "AztecaInternacional.us": "Azteca.Mundial.us2",
    "BigBrother.us": "6661f11a41af6400080e90d8",
    "CGTNSpanish.cn": "CGTNEspanol.us",
    "DePelícula.mx": "DePelicula.mx",
    "EstrellaTV.us": "Estrella.TV.us2",
    "HispanTV.ir": "PressTV.ir",
    "Rede.Vida.br": "RedeVida.br",
    "Telesur.ve": "TeleSUR.pt",
    "TVChile.cl": "TV.Chile.us2",
    "Telefe.ar": "Telefe.ar",
    "TMC.fr": "TMC.fr",
    "כאן.11.il": "כאן11.il",
    "מכאן.il": "מכאן.il",
    "Canal.Telefé.(Argentina).ar": "Telefe.ar",
    "Canal.2.de.México.(Canal.Las.Estrellas.-.XEW).mx": "Canal.2.de.México.(Canal.Las.Estrellas.-.XEW).mx",
    "CBS.Streaming.SD.East.feed.us2": "CBS.Streaming.SD.East.feed.us2",
}

# aliases no formato (normalizado -> tvg_id do M3U)
def norm(s):
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[\s\-_\.\+()\[\]]+", "", s).lower()


def download(url, timeout=300):
    name = url.split("/")[-1]
    cache_path = os.path.join(CACHE_DIR, name)
    for candidate in os.listdir(CACHE_DIR) if os.path.isdir(CACHE_DIR) else []:
        if name.replace("epg-", "epg_") == candidate:
            cache_path = os.path.join(CACHE_DIR, candidate)
            break
    print(f"  {name}:", end=" ", flush=True)
    if os.path.exists(cache_path):
        with open(cache_path, "rb") as f:
            data = f.read()
        print(f"(cache {len(data):,} bytes)")
        return data
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
        if len(data) < 100:
            print("(pulado)")
            return None
        print(f"({len(data):,} bytes)")
        return data
    except Exception as e:
        print(f"(erro: {e})")
        return None


print("=" * 60)
print("1. Baixando M3U do GitHub")
print("=" * 60)
m3u_text = ""
try:
    req = urllib.request.Request(M3U_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        m3u_text = resp.read().decode("utf-8", errors="replace")
    if m3u_text.count("#EXTINF") == 0:
        m3u_text = ""
except Exception as e:
    print(f"  ERRO ao baixar M3U: {e}")

if not m3u_text or m3u_text.count("#EXTINF") == 0:
    print("  ERRO: M3U sem canais.")
    sys.exit(1)

with open("/home/runner/work/JCTVV/JCTVV/NEWSWORLDNOVOS.m3u", "w", encoding="utf-8") as f:
    f.write(m3u_text)

m3u_entries = []
seen_display = set()
for line in m3u_text.splitlines():
    if not line.startswith("#EXTINF"):
        continue
    tid_m = re.search(r'tvg-id="([^"]*)"', line)
    tname_m = re.search(r'tvg-name="([^"]*)"', line)
    logo_m = re.search(r'tvg-logo="([^"]*)"', line)
    comma_m = re.search(r",([^,]+)$", line)
    if not comma_m:
        continue
    tvg_id = (tid_m.group(1) if tid_m else "").strip()
    tvg_name = (tname_m.group(1) if tname_m else "").strip()
    logo = (logo_m.group(1) if logo_m else "").strip()
    display = comma_m.group(1).strip()
    if display in seen_display:
        continue
    seen_display.add(display)
    m3u_entries.append({"tvg_id": tvg_id, "tvg_name": tvg_name, "logo": logo, "display": display})

tvg_ids = set(e["tvg_id"] for e in m3u_entries if e["tvg_id"])
tvg_norm = {norm(t): t for t in tvg_ids}

m3u_names = {}
m3u_logos = {}
m3u_displays = {}
for e in m3u_entries:
    if e["tvg_id"]:
        name_base = re.sub(r"\s*\(.*$|\s*\[.*$", "", e["display"]).strip()
        m3u_names[e["tvg_id"]] = name_base or e["display"]
        m3u_logos[e["tvg_id"]] = e["logo"] or e["tvg_name"]
        m3u_displays[e["tvg_id"]] = e["display"]

print(f"  {len(m3u_entries)} canais, {len(tvg_ids)} tvg-ids unicos")

alias_norm = {norm(v): k for k, v in ALIASES.items()}

name_to_tvgid = {norm(n): tid for tid, n in m3u_names.items() if n}


def source_match(cid, display_name):
    nc = norm(cid)
    if nc in tvg_norm:
        return tvg_norm[nc]
    if nc in alias_norm:
        return alias_norm[nc]
    if display_name:
        ndn = norm(display_name)
        if ndn in name_to_tvgid:
            return name_to_tvgid[ndn]
    return None


print()
print("=" * 60)
print("2. Baixando e filtrando fontes EPG")
print("=" * 60)

matched_pairs = {}  # tvg_id -> (origem_cid, origem)
matched_ids = set()
all_channels = OrderedDict()
all_programmes = OrderedDict()
seen_progs = set()
id_remap = {}  # origem_cid -> tvg_id


def process_epg(raw_bytes, src_name):
    ch_count = 0
    pr_count = 0
    try:
        if raw_bytes[:2] == b"\x1f\x8b":
            f = gzip.GzipFile(fileobj=io.BytesIO(raw_bytes))
        else:
            f = io.BytesIO(raw_bytes)

        context = ET.iterparse(f, events=("end",))
        for event, elem in context:
            tag = elem.tag
            if tag == "channel":
                cid = elem.get("id", "")
                if not cid:
                    elem.clear()
                    continue
                dn = elem.find("display-name")
                display_name = dn.text.strip() if dn is not None and dn.text else ""
                m3u_id = source_match(cid, display_name)
                if m3u_id and m3u_id not in id_remap:
                    id_remap[cid] = m3u_id
                    matched_ids.add(m3u_id)
                    matched_pairs[m3u_id] = (cid, src_name)
                    ch = copy.deepcopy(elem)
                    ch.set("id", m3u_id)
                    if ch.find("display-name") is not None:
                        for d in ch.findall("display-name"):
                            d.set("lang", "pt")
                    if not ch.findall("icon") and m3u_logos.get(m3u_id):
                        ET.SubElement(ch, "icon", attrib={"src": m3u_logos[m3u_id]})
                    all_channels[m3u_id] = ch
                    ch_count += 1
                elem.clear()
            elif tag == "programme":
                ch = elem.get("channel", "")
                m3u_id = id_remap.get(ch)
                if m3u_id:
                    start = elem.get("start", "")
                    stop = elem.get("stop", "")
                    pkey = f"{m3u_id}|{start}|{stop}"
                    if pkey not in seen_progs:
                        seen_progs.add(pkey)
                        pr = copy.deepcopy(elem)
                        pr.set("channel", m3u_id)
                        all_programmes[pkey] = pr
                        pr_count += 1
                elem.clear()
    except Exception as e:
        print(f"    Erro parse {src_name}: {e}")
    return ch_count, pr_count


sources_processed = []

for url in EPG_SOURCES:
    nome = url.split("/")[-1]
    raw = download(url)
    if raw is None:
        continue
    ch, pr = process_epg(raw, nome)
    sources_processed.append(nome)
    print(f"    -> +{ch} canais, +{pr} programas")
    if len(matched_ids) >= len(tvg_ids):
        print(f"  Todos os {len(tvg_ids)} canais encontrados!")
        break

for path in LOCAL_FILES:
    nome = os.path.basename(path)
    if not os.path.exists(path):
        continue
    print(f"  {nome} (local):")
    with open(path, "rb") as f:
        raw = f.read()
    ch, pr = process_epg(raw, nome)
    sources_processed.append(nome)
    print(f"    -> +{ch} canais, +{pr} programas")

print()
print("=" * 60)
print(f"3. Resultado: {len(matched_ids)}/{len(tvg_ids)} canais com EPG, {len(all_programmes)} programas")
print("=" * 60)

matched_list = sorted(matched_ids)
missing = sorted(set(tvg_ids) - matched_ids)
if missing:
    print(f"  Sem dados ({len(missing)}): {missing}")

print()
print("=" * 60)
print("4. Incluindo canais do M3U sem programacao (apenas <channel>)")
print("=" * 60)
for tid in sorted(tvg_ids):
    if tid not in all_channels:
        ch = ET.Element("channel", attrib={"id": tid})
        dn = ET.SubElement(ch, "display-name", attrib={"lang": "pt"})
        dn.text = m3u_displays.get(tid, m3u_names.get(tid, tid))
        if m3u_logos.get(tid):
            ET.SubElement(ch, "icon", attrib={"src": m3u_logos[tid]})
        all_channels[tid] = ch

print(f"  Total de canais no EPG: {len(all_channels)}")

print()
print("=" * 60)
print("5. Salvando EPGFULL.xml.gz (sobrescrevendo)")
print("=" * 60)

root_out = ET.Element("tv", attrib={"generator-info-name": "EPGFULL (NEWSWORLDNOVOS)"})
for ch in all_channels.values():
    root_out.append(ch)
for prog in all_programmes.values():
    root_out.append(prog)

tree = ET.ElementTree(root_out)
buf = io.BytesIO()
tree.write(buf, encoding="utf-8", xml_declaration=True)
xml_data = buf.getvalue()

with gzip.open(OUTPUT, "wb") as f:
    f.write(xml_data)

print(f"  {OUTPUT}: {os.path.getsize(OUTPUT):,} bytes (gzip), {len(xml_data):,} bytes (raw)")
print(f"  Canais: {len(all_channels)} | Programas: {len(all_programmes)}")

print()
print("=" * 60)
print("6. Testando EPG")
print("=" * 60)

with gzip.open(OUTPUT, "rb") as f:
    test_xml = f.read().decode("utf-8", errors="ignore")
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

com_canais_hoje = sorted(canais_hoje)
com_canais_amanha = sorted(canais_amanha)
print(f"  Canais com dados de hoje: {com_canais_hoje if com_canais_hoje else 'NENHUM'}")
print(f"  Canais com dados de amanha: {com_canais_amanha if com_canais_amanha else 'NENHUM'}")

sem_dados_hoje = sorted(set(all_channels.keys()) - canais_hoje)
sem_dados_amanha = sorted(set(all_channels.keys()) - canais_amanha)
print(f"  Canais SEM dados hoje ({len(sem_dados_hoje)}): {sem_dados_hoje}")
print(f"  Canais SEM dados amanha ({len(sem_dados_amanha)}): {sem_dados_amanha}")

print()
if prog_hoje > 0 and prog_amanha > 0:
    print("EPG FUNCIONANDO! Programas para hoje e amanha disponiveis.")
    sys.exit(0)
else:
    print("AVISO: Faltam programas para hoje ou amanha.")
    sys.exit(1)