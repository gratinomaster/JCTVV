#!/usr/bin/env python3
"""Gera EPGFULL.xml.gz contendo SOMENTE os canais do NEWSWORLDNOVOS.m3u.

Regras:
  - toda entrada #EXTINF do m3u vira um <channel> (mesmo sem tvg-id);
  - nenhum canal de fora do m3u entra no guia;
  - entrada sem tvg-id recebe um id sintetico estavel (prefixo M3U.);
  - falhas de size/parse nao podem gerar guide vazio.
"""
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
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
M3U_PATH = os.path.join(BASE_DIR, "NEWSWORLDNOVOS.m3u")
OUTPUT = os.path.join(BASE_DIR, "EPGFULL.xml.gz")
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
    "https://iptv-epg.org/files/epg-us.xml.gz",
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
    os.path.join(BASE_DIR, "epgshare_US2.xml.gz"),
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
    # canais do m3u sem tvg-id em que so existe uma fonte: chave = alvo, valor = id da fonte
    "M3U.MEXICO.Maria.Vision.360p.Not.24.7": "Canal.María.Visión.mx",
    "M3U.MEXICO.Teleritmo.720p": "TeleRitmo.us",
    "M3U.MEXICO.The.Pet.Collective.720p": "ThePetCollective.us",
    "M3U.MEXICO.WeatherSpy.720p": "WeatherSpy.us",
}

QUALITY_RE = re.compile(r"\b(1080p|720p|576p|480p|360p|fhd|uhd|hdr|sd|hd|4k|hevc)\b", re.I)
BRACKET_RE = re.compile(r"[\(\[\{][^\)\]\}]*[\)\]\}]")
TAILNUM_RE = re.compile(r"\s+\d{1,3}([.,]\d{1,2})?$")
LEADPREFIX_RE = re.compile(r"^[A-Z]{2}\d?\s*[-–—]\s*")
SUFFIX_RE = re.compile(r"\.([a-z]{2,3})$", re.I)
GROUP_CC = [
    ("argentina", "ar"), ("mexico", "mx"), ("venezuela", "ve"),
    ("chile", "cl"), ("brasil", "br"), ("portugal", "pt"),
    ("france", "fr"), ("estados unidos", "us"), ("eeuu", "us"),
    ("usa", "us"), ("news world", ""),
]


def group_country(group):
    g = unicodedata.normalize("NFD", group or "")
    g = "".join(c for c in g if unicodedata.category(c) != "Mn").lower()
    for key, cc in GROUP_CC:
        if key in g:
            return cc
    return ""


def country_of(cid, names=(), group=""):
    """Pais do canal: sufixo do id (.ve/.cl), grupo do m3u ou prefixo do display-name ('VE - Name')."""
    m = SUFFIX_RE.search(cid or "")
    if m:
        return m.group(1).lower()
    cc = group_country(group)
    if cc:
        return cc
    for n in names:
        m = LEADPREFIX_RE.match(n or "")
        if m:
            return m.group(0).strip(" -–—").lower()
    return ""


def norm(s):
    if not s:
        return ""
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[\s\-_\.\+()\[\]]+", "", s).lower()
    return s


def name_keys(name):
    """Variantes normalizadas de um nome de canal, da mais especifica a mais generica."""
    keys = []
    base = (name or "").strip()
    if not base:
        return keys
    cand = {base, LEADPREFIX_RE.sub("", base)}
    for c in list(cand):
        cand.add(BRACKET_RE.sub(" ", c))
        cand.add(QUALITY_RE.sub(" ", c))
        cand.add(BRACKET_RE.sub(" ", QUALITY_RE.sub(" ", c)))
    for c in list(cand):
        cand.add(TAILNUM_RE.sub(" ", c))
    for c in cand:
        n = norm(re.sub(r"\s+", " ", c).strip())
        if n and n not in keys:
            keys.append(n)
    return keys


def slug(s):
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^0-9A-Za-z]+", ".", s).strip(".")
    return s or "x"


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
        with open(cache_path, "wb") as f:
            f.write(data)
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

if not m3u_text:
    if os.path.exists(M3U_PATH):
        with open(M3U_PATH, encoding="utf-8") as f:
            m3u_text = f.read()
        print(f"  usando copia local: {M3U_PATH}")

if not m3u_text or m3u_text.count("#EXTINF") == 0:
    print("  ERRO: M3U sem canais.")
    sys.exit(1)

with open(M3U_PATH, "w", encoding="utf-8") as f:
    f.write(m3u_text)

# cada entrada #EXTINF vira um canal-alvo
targets = OrderedDict()          # target_id -> dados do canal do m3u
used_ids = set()
seen_display = set()
entries = 0

m3u_lines = m3u_text.splitlines()
for idx, line in enumerate(m3u_lines):
    if not line.startswith("#EXTINF"):
        continue
    entries += 1
    tid_m = re.search(r'tvg-id="([^"]*)"', line)
    tname_m = re.search(r'tvg-name="([^"]*)"', line)
    logo_m = re.search(r'tvg-logo="([^"]*)"', line)
    grp_m = re.search(r'group-title="([^"]*)"', line)
    comma_m = re.search(r",([^,]+)$", line)
    if not comma_m:
        continue
    display = comma_m.group(1).strip()
    tvg_id = (tid_m.group(1) if tid_m else "").strip()
    tvg_name = (tname_m.group(1) if tname_m else "").strip()
    logo = (logo_m.group(1) if logo_m else "").strip()
    group = (grp_m.group(1) if grp_m else "").strip()
    url = m3u_lines[idx + 1].strip() if idx + 1 < len(m3u_lines) else ""
    if url.startswith("#"):
        url = ""

    if tvg_id:
        key = tvg_id
    else:
        # dedup por nome: entradas repetidas (mesmo nome, sem id) viram 1 canal
        nk = norm(display)
        if nk in seen_display:
            continue
        seen_display.add(nk)
        base = "M3U." + (slug(group) + "." if group else "") + slug(display)
        key = base
        n = 2
        while key in used_ids:
            key = f"{base}.{n}"
            n += 1
    used_ids.add(key)
    targets[key] = {
        "tvg_id": key,
        "real_id": bool(tvg_id),
        "tvg_name": tvg_name,
        "logo": logo,
        "group": group,
        "display": display,
        "url": url,
    }

print(f"  {entries} entradas #EXTINF -> {len(targets)} canais-alvo")
print(f"  com tvg-id: {sum(1 for t in targets.values() if t['real_id'])} | "
      f"id sintetico: {sum(1 for t in targets.values() if not t['real_id'])}")

tvg_ids = {k for k, t in targets.items() if t["real_id"]}
synth_ids = {k for k, t in targets.items() if not t["real_id"]}
tvg_norm = {norm(k): k for k in tvg_ids}
synth_norm = {norm(k): k for k in synth_ids}
alias_norm = {norm(v): k for k, v in ALIASES.items()}

m3u_logos = {k: (t["logo"] or t["tvg_name"]) for k, t in targets.items()}
m3u_displays = {k: t["display"] for k, t in targets.items()}
target_country = {k: country_of(k, [t["display"], t["tvg_name"]], t["group"]) for k, t in targets.items()}

# nome -> alvo, so quando inequivoco e do mesmo pais (evita EPG do canal errado)
name_to_target = {}
ambiguous = set()
for k, t in targets.items():
    cc = target_country[k]
    for label in (t["display"], t["tvg_name"]):
        for nk in name_keys(label):
            key = (nk, cc)
            if key in name_to_target and name_to_target[key] != k:
                ambiguous.add(key)
            else:
                name_to_target[key] = k
for key in ambiguous:
    name_to_target.pop(key, None)

print()
print("=" * 60)
print("2. Baixando e filtrando fontes EPG")
print("=" * 60)

matched_ids = set()
all_channels = OrderedDict()
all_programmes = OrderedDict()
seen_progs = set()
id_remap = {}
matched_pairs = {}


def source_match(cid, display_names):
    nc = norm(cid)
    if nc in tvg_norm:
        return tvg_norm[nc]
    if nc in alias_norm:
        return alias_norm[nc]
    if nc in synth_norm:
        return synth_norm[nc]
    cc = country_of(cid, display_names)
    if not cc:
        return None
    for name in display_names:
        for nk in name_keys(name):
            tgt = name_to_target.get((nk, cc))
            if tgt is not None:
                return tgt
    return None


def make_channel(target_id):
    ch = ET.Element("channel", attrib={"id": target_id})
    dn = ET.SubElement(ch, "display-name", attrib={"lang": "pt"})
    dn.text = m3u_displays.get(target_id, target_id)
    if m3u_logos.get(target_id):
        ET.SubElement(ch, "icon", attrib={"src": m3u_logos[target_id]})
    return ch


def process_epg(raw_bytes, src_name):
    ch_count = 0
    pr_count = 0
    try:
        if raw_bytes[:2] == b"\x1f\x8b":
            f = gzip.GzipFile(fileobj=io.BytesIO(raw_bytes))
        else:
            f = io.BytesIO(raw_bytes)

        for event, elem in ET.iterparse(f, events=("end",)):
            tag = elem.tag
            if tag == "channel":
                cid = elem.get("id", "")
                if not cid:
                    elem.clear()
                    continue
                names = [(d.text or "").strip() for d in elem.findall("display-name")]
                names = [n for n in names if n]
                m3u_id = source_match(cid, names)
                if m3u_id and m3u_id in targets and cid not in id_remap:
                    id_remap[cid] = m3u_id
                    matched_ids.add(m3u_id)
                    matched_pairs.setdefault(m3u_id, (cid, src_name))
                    if m3u_id not in all_channels:
                        ch = make_channel(m3u_id)
                        for extra in names[1:]:
                            d = ET.SubElement(ch, "display-name", attrib={"lang": "en"})
                            d.text = extra
                        for ic in elem.findall("icon"):
                            src = ic.get("src", "")
                            if src and not any(x.get("src") == src for x in ch.findall("icon")):
                                ET.SubElement(ch, "icon", attrib={"src": src})
                        for u in elem.findall("url"):
                            ch.append(copy.deepcopy(u))
                        all_channels[m3u_id] = ch
                        ch_count += 1
                elem.clear()
            elif tag == "programme":
                cid = elem.get("channel", "")
                m3u_id = id_remap.get(cid)
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


for url in EPG_SOURCES:
    nome = url.split("/")[-1]
    raw = download(url)
    if raw is None:
        continue
    ch, pr = process_epg(raw, nome)
    print(f"    -> +{ch} canais, +{pr} programas (total {len(matched_ids)}/{len(targets)})")

for path in LOCAL_FILES:
    if not os.path.exists(path):
        continue
    nome = os.path.basename(path)
    print(f"  {nome} (local):")
    with open(path, "rb") as f:
        raw = f.read()
    ch, pr = process_epg(raw, nome)
    print(f"    -> +{ch} canais, +{pr} programas (total {len(matched_ids)}/{len(targets)})")

today_str = datetime.now().strftime("%Y%m%d")
expired = [k for k, p in all_programmes.items() if (p.get("stop") or "")[:8] < today_str]
for k in expired:
    del all_programmes[k]
if expired:
    print(f"  {len(expired)} programa(s) ja encerrados removidos "
          f"({len(expired)*100.0/max(len(all_programmes)+len(expired),1):.1f}% de desperdicio)")
    matched_ids = {p.get("channel") for p in all_programmes.values()}

print()
print("=" * 60)
print("3. Resultado: %d/%d canais com EPG, %d programas"
      % (len(matched_ids), len(targets), len(all_programmes)))
print("=" * 60)

if not matched_ids:
    print("  ERRO: nenhuma fonte respondeu, EPG ficaria vazio. Mantendo arquivo atual.")
    sys.exit(1)

# o mesmo stream aparece no m3u com ids diferentes -> mesmo EPG
by_url = {}
for k, t in targets.items():
    if t["url"]:
        by_url.setdefault(t["url"], []).append(k)
progs_by_channel = {}
for pkey, p in all_programmes.items():
    progs_by_channel.setdefault(p.get("channel"), []).append(pkey)
shared = 0
for url, group in by_url.items():
    if len(group) < 2:
        continue
    with_prog = [k for k in group if progs_by_channel.get(k)]
    without = [k for k in group if not progs_by_channel.get(k)]
    if not with_prog or not without:
        continue
    src = with_prog[0]
    for k in without:
        for pkey in progs_by_channel[src]:
            newkey = pkey.replace(src + "|", k + "|", 1)
            if newkey in all_programmes:
                continue
            pr = copy.deepcopy(all_programmes[pkey])
            pr.set("channel", k)
            all_programmes[newkey] = pr
        matched_ids.add(k)
        matched_pairs.setdefault(k, (src, "stream duplicado no m3u"))
        shared += 1
    print(f"  stream duplicado -> EPG compartilhado: {without[0]} <- {src}")
if shared:
    print(f"  {shared} canal(is) recuperado(s) por stream duplicado")

missing = [k for k in targets if k not in matched_ids]
if missing:
    print(f"  Sem programacao ({len(missing)}): {missing}")

print()
print("=" * 60)
print("4. Garantindo todos os canais do M3U no EPG")
print("=" * 60)
for tid in sorted(targets):
    if tid not in all_channels:
        all_channels[tid] = make_channel(tid)

extra = [k for k in all_channels if k not in targets]
if extra:
    print(f"  DESCARTADOS (fora do M3U): {extra}")
    for k in extra:
        del all_channels[k]

print(f"  Total de canais no EPG: {len(all_channels)} (m3u: {len(targets)})")

print()
print("=" * 60)
print("5. Salvando EPGFULL.xml.gz (sobrescrevendo)")
print("=" * 60)

root_out = ET.Element("tv", attrib={"generator-info-name": "EPGFULL (NEWSWORLDNOVOS)"})
for k in sorted(all_channels):
    root_out.append(all_channels[k])
for k in sorted(all_programmes):
    root_out.append(all_programmes[k])

buf = io.BytesIO()
ET.ElementTree(root_out).write(buf, encoding="utf-8", xml_declaration=True)
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
    test_root = ET.fromstring(f.read().decode("utf-8", errors="ignore"))
canais = test_root.findall("channel")
programas = test_root.findall("programme")
epg_ids = {c.get("id") for c in canais}

hoje = datetime.now().strftime("%Y%m%d")
amanha = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")

prog_hoje = prog_amanha = 0
canais_hoje, canais_amanha = set(), set()
for p in programas:
    d = p.get("start", "")[:8]
    if d == hoje:
        prog_hoje += 1
        canais_hoje.add(p.get("channel"))
    elif d == amanha:
        prog_amanha += 1
        canais_amanha.add(p.get("channel"))

print(f"  XML valido: sim | gzip valido: sim")
print(f"  Canais no EPG: {len(canais)} | Programas: {len(programas)}")
print(f"  Programas hoje ({hoje}): {prog_hoje} em {len(canais_hoje)} canais")
print(f"  Programas amanha ({amanha}): {prog_amanha} em {len(canais_amanha)} canais")
print(f"  Canais do EPG fora do m3u: {sorted(epg_ids - set(targets)) or 'NENHUM'}")
print(f"  Canais do m3u fora do EPG: {sorted(set(targets) - epg_ids) or 'NENHUM'}")
print(f"  Canais SEM dados hoje: {len(set(targets) - canais_hoje)}")
print(f"  Canais SEM dados amanha: {len(set(targets) - canais_amanha)}")

if len(epg_ids) != len(targets) or epg_ids != set(targets):
    print("FALHA: conjunto de canais nao bate com o m3u.")
    sys.exit(1)
if prog_hoje > 0 and prog_amanha > 0:
    print("EPG FUNCIONANDO! Programas para hoje e amanha disponiveis.")
    sys.exit(0)
print("AVISO: Faltam programas para hoje ou amanha.")
sys.exit(1)
