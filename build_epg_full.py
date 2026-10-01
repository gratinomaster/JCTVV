#!/usr/bin/env python3
import bisect
import copy
import difflib
import gzip
import io
import os
import re
import sys
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
M3U_URL = "https://github.com/gratinomaster/JCTV/raw/refs/heads/main/NEWSWORLDNOVOS.m3u"
M3U_LOCAL = os.path.join(BASE, "NEWSWORLDNOVOS.m3u")
OUTPUT = os.path.join(BASE, "EPGFULL.xml.gz")

EPG_SOURCES = [
    "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_AR1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_MX1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_BR1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_FR1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_PT1.xml.gz",
    "https://iptv-epg.org/files/epg-us.xml.gz",
    "https://iptv-epg.org/files/epg-ar.xml.gz",
    "https://iptv-epg.org/files/epg-mx.xml.gz",
    "https://iptv-epg.org/files/epg-cl.xml.gz",
    "https://iptv-epg.org/files/epg-br.xml.gz",
    "https://iptv-epg.org/files/epg-ve.xml.gz",
    "https://iptv-epg.org/files/epg-il.xml.gz",
    "https://raw.githubusercontent.com/matthuisman/i.mjh.nz/master/PlutoTV/us.xml",
]

VARIANT_TOKENS = {
    "feed", "hd", "fhd", "sd", "uhd", "4k", "ts", "alt", "backup",
    "east", "west", "north", "south", "raw",
}

GAP_MINUTES = 90
LOOKAHEAD_DAYS = 3

JUNK_TITLES = {"", "-", "--", "n/a", "na", "tbd", "nodata", "nodatos", "sindatos", "sininformacion", "programacion"}


def tokens(value):
    return [t.lower() for t in re.findall(r"[^\W_]+", value or "", re.UNICODE)]


def norm(value):
    return "".join(tokens(value))


ACCENTS = {
    "á": "a", "à": "a", "ã": "a", "â": "a", "ä": "a", "é": "e", "è": "e", "ê": "e",
    "ë": "e", "í": "i", "ì": "i", "î": "i", "ï": "i", "ó": "o", "ò": "o", "õ": "o",
    "ô": "o", "ö": "o", "ú": "u", "ù": "u", "û": "u", "ü": "u", "ç": "c", "ñ": "n",
    "ý": "y", "ÿ": "y", "¿": "", "¡": "", "–": "-", "—": "-",
}


def display_norm(value):
    text = unicodedata.normalize("NFKD", value or "").lower()
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    for src, dst in ACCENTS.items():
        text = text.replace(src, dst)
    return re.sub(r"[^0-9a-z\u0590-\u05ff\u0600-\u06ff]+", "", text)


def country_of(value):
    parts = [p.lower() for p in re.findall(r"[^\W_]+", value or "", re.UNICODE)]
    for part in reversed(parts):
        candidate = part[:2]
        rest = part[2:]
        if len(candidate) == 2 and candidate.isalpha() and (rest == "" or rest.isdigit()):
            return candidate
    return ""


def minutes(stamp):
    digits = re.sub(r"[^0-9]", "", stamp or "")
    if len(digits) < 12:
        return None
    return (
        int(digits[0:4]) * 525600
        + int(digits[4:6]) * 43200
        + int(digits[6:8]) * 1440
        + int(digits[8:10]) * 60
        + int(digits[10:12])
    )


def day_start(date_obj):
    return (
        date_obj.year * 525600
        + date_obj.month * 43200
        + date_obj.day * 1440
    )


def download(url, timeout=600):
    name = url.split("/")[-1]
    print(f"   {name} ... ", end=" ", flush=True)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
        if len(data) < 100:
            print("ignorado (vazio)")
            return None
        print(f"{len(data):,} bytes")
        return data
    except Exception as exc:
        print(f"erro: {exc}")
        return None


print("=" * 66)
print("1. Playlist M3U")
print("=" * 66)

m3u_text = None
m3u_data = download(M3U_URL, timeout=120)
if m3u_data and not m3u_data[:1] == b"<":
    m3u_text = m3u_data.decode("utf-8", errors="replace")
if m3u_text is None:
    if os.path.exists(M3U_LOCAL):
        with open(M3U_LOCAL, encoding="utf-8", errors="replace") as handle:
            m3u_text = handle.read()
        print(f"   usando copia local {M3U_LOCAL}")
    else:
        print("ERRO: nao foi possivel obter a playlist M3U")
        sys.exit(1)

m3u_ids = []
m3u_info = {}
for line in m3u_text.splitlines():
    if not line.startswith("#EXTINF"):
        continue
    found_id = re.search(r'tvg-id="([^"]*)"', line)
    if not found_id:
        continue
    tid = found_id.group(1).strip()
    if not tid or tid in ("0", "(no tvg-id)"):
        continue
    if tid in m3u_info:
        continue
    found_logo = re.search(r'tvg-logo="([^"]*)"', line)
    name = line.split(",", 1)[1].strip() if "," in line else ""
    m3u_info[tid] = {
        "name": name,
        "logo": found_logo.group(1).strip() if found_logo else "",
    }
    m3u_ids.append(tid)

m3u_norm = {}
for tid in m3u_ids:
    m3u_norm.setdefault(norm(tid), tid)

m3u_name_index = {}
for tid in m3u_ids:
    base = re.sub(r"\s*\(.*$", "", m3u_info[tid]["name"])
    key = display_norm(base)
    if len(key) >= 4:
        m3u_name_index.setdefault(key, tid)

m3u_country = {tid: country_of(tid) for tid in m3u_ids}

print(f"   canais com tvg-id: {len(m3u_ids)}")

match_cache = {}
match_origin = {}


def same_country(cid, tid):
    epg_country = country_of(cid)
    m3u_country_value = m3u_country.get(tid, "")
    if not epg_country or not m3u_country_value:
        return True
    return epg_country == m3u_country_value


def name_is_close(first, second):
    if first == second:
        return True
    shorter, longer = sorted((first, second), key=len)
    if len(shorter) < 6:
        return False
    if shorter in longer:
        return len(shorter) / len(longer) >= 0.8
    return False


def match_channel(cid, display_name=""):
    cache_key = (cid, display_name)
    if cache_key in match_cache:
        return match_cache[cache_key]

    result = None
    direct = norm(cid)
    if direct in m3u_norm:
        result = m3u_norm[direct]
    else:
        found = []
        parts = tokens(cid)
        for size in range(len(parts), 0, -1):
            head = norm(" ".join(parts[:size]))
            if head in m3u_norm:
                found.append(m3u_norm[head])
        reduced = [t for t in parts if t not in VARIANT_TOKENS]
        for size in range(len(reduced), 0, -1):
            head = norm(" ".join(reduced[:size]))
            if head in m3u_norm:
                found.append(m3u_norm[head])
        if found:
            result = max(set(found), key=found.count)

    if result is None and display_name:
        dn = display_norm(re.sub(r"\s*\(.*$", "", display_name))
        if dn in m3u_name_index and same_country(cid, m3u_name_index[dn]):
            result = m3u_name_index[dn]
        elif len(dn) >= 6:
            for name_key, tid in m3u_name_index.items():
                if same_country(cid, tid) and name_is_close(name_key, dn):
                    result = tid
                    break

    if result is None:
        probe = display_norm(display_name) or direct
        best_score = 0.0
        for tid in m3u_ids:
            if not same_country(cid, tid):
                continue
            score = difflib.SequenceMatcher(None, probe, norm(tid)).ratio()
            if score > best_score:
                best_score = score
                result = tid
        if best_score < 0.86:
            result = None

    match_cache[cache_key] = result
    return result


print()
print("=" * 66)
print("2. Fontes EPG")
print("=" * 66)

inverse = defaultdict(lambda: defaultdict(dict))
epg_meta = {}
epg_feed = {}

for url in EPG_SOURCES:
    raw = download(url)
    if raw is None:
        continue
    source = url.split("/")[-1]
    cid_to_m3u = {}
    n_ch = 0
    n_pr = 0
    try:
        stream = gzip.GzipFile(fileobj=io.BytesIO(raw)) if raw[:2] == b"\x1f\x8b" else io.BytesIO(raw)
        for _event, elem in ET.iterparse(stream, events=("end",)):
            if elem.tag == "channel":
                cid = elem.get("id", "")
                if cid:
                    node = elem.find("display-name")
                    name = node.text.strip() if node is not None and node.text else ""
                    target = match_channel(cid, name)
                    if target:
                        cid_to_m3u[cid] = target
                        n_ch += 1
                        if not inverse[target][source]:
                            epg_feed[(target, source)] = cid
                        icon = elem.find("icon")
                        if target not in epg_meta:
                            epg_meta[target] = {
                                "name": name,
                                "icon": icon.get("src", "") if icon is not None else "",
                            }
                elem.clear()
            elif elem.tag == "programme":
                tid = cid_to_m3u.get(elem.get("channel", ""))
                if tid:
                    start = minutes(elem.get("start", ""))
                    stop = minutes(elem.get("stop", ""))
                    if start is not None and stop is not None and stop > start:
                        title = (elem.findtext("title", "") or "").strip()
                        if display_norm(title) in JUNK_TITLES:
                            elem.clear()
                            continue
                        inverse[tid][source][f"{start}|{stop}|{title}"] = (start, stop, copy.deepcopy(elem))
                        n_pr += 1
                elem.clear()
    except ET.ParseError as exc:
        print(f"     XML invalido: {exc}")
    print(f"     -> {n_ch} canais, {n_pr} programas")
    raw = None

print(f"   canais comprogramacao: {len(inverse)} / {len(m3u_ids)}")

print()
print("=" * 66)
print("3. Montagem da grade")
print("=" * 66)

now = datetime.now()
hoje_ini = day_start(now)
janela = LOOKAHEAD_DAYS * 1440

selected = {}
relatorio = []

for tid in m3u_ids:
    per_source = inverse.get(tid)
    if not per_source:
        continue
    ranked = []
    for source, progs in per_source.items():
        score = sum(1 for start, _stop, _elem in progs.values() if start < hoje_ini + janela)
        ranked.append((score, len(progs), source, progs))
    ranked.sort(key=lambda item: (-item[0], -item[1], item[2]))
    if not ranked[0][0]:
        continue

    chosen = sorted(ranked[0][3].values(), key=lambda item: item[0])
    starts = [item[0] for item in chosen]
    filled = 0
    for _score, _total, _source, progs in ranked[1:]:
        for value in sorted(progs.values(), key=lambda item: item[0]):
            start, stop, _elem = value
            pos = bisect.bisect_left(starts, start)
            if pos and chosen[pos - 1][1] > start:
                continue
            if pos < len(chosen) and chosen[pos][0] < stop:
                continue
            distancia = GAP_MINUTES
            if pos:
                distancia = min(distancia, min(abs(chosen[pos - 1][0] - stop), abs(start - chosen[pos - 1][1])))
            if pos < len(chosen):
                distancia = min(distancia, min(abs(chosen[pos][0] - stop), abs(start - chosen[pos][1])))
            if distancia < GAP_MINUTES:
                continue
            starts.insert(pos, start)
            chosen.insert(pos, value)
            filled += 1

    final = []
    last_stop = None
    for start, stop, elem in chosen:
        if last_stop is not None and start < last_stop:
            continue
        final.append((start, stop, elem))
        last_stop = stop

    selected[tid] = final
    relatorio.append((tid, ranked[0][2], len(final), filled))

total_programmes = sum(len(v) for v in selected.values())
print(f"   canais com grade: {len(selected)}")
print(f"   programas: {total_programmes}")

print()
print("=" * 66)
print("4. Gravando EPGFULL.xml.gz")
print("=" * 66)

partes = ['<?xml version="1.0" encoding="utf-8"?>', '<tv generator-info-name="EPGFULL">']

for tid in m3u_ids:
    info = m3u_info.get(tid, {})
    name = info.get("name") or epg_meta.get(tid, {}).get("name") or tid
    logo = info.get("logo") or ""
    if logo.lower().endswith(".svg") or not logo.startswith("http"):
        logo = epg_meta.get(tid, {}).get("icon", "")
    partes.append(f'  <channel id="{tid}">')
    partes.append(f"    <display-name lang=\"pt\">{name}</display-name>")
    if logo:
        partes.append(f'    <icon src="{logo}" />')
    partes.append("  </channel>")

for tid in m3u_ids:
    if tid not in selected:
        continue
    for start, stop, source_elem in selected[tid]:
        elem = copy.deepcopy(source_elem)
        elem.set("channel", tid)
        bloco = ET.tostring(elem, encoding="unicode")
        bloco = re.sub(r"\s+>", ">", bloco.replace("\n", "").replace("  ", " "))
        partes.append("  " + bloco)

partes.append("</tv>")
xml_str = "\n".join(partes)

if os.path.exists(OUTPUT):
    print(f"   anterior: {os.path.getsize(OUTPUT):,} bytes (sera sobrescrito)")

with gzip.open(OUTPUT, "wt", encoding="utf-8") as handle:
    handle.write(xml_str)

print(f"   {OUTPUT}")
print(f"   {os.path.getsize(OUTPUT):,} bytes comprimidos / {len(xml_str):,} bytes XML")
print(f"   canais: {len(selected)} | programas: {total_programmes}")

print()
print("=" * 66)
print("5. Teste do EPG")
print("=" * 66)

with gzip.open(OUTPUT, "rb") as handle:
    root = ET.fromstring(handle.read())

canais_xml = root.findall("channel")
programmes_xml = root.findall("programme")
ids_xml = {c.get("id") for c in canais_xml}
orfas = [p for p in programmes_xml if p.get("channel") not in ids_xml]

conflitos = 0
ultimo = {}
for prog in programmes_xml:
    cid = prog.get("channel")
    start = minutes(prog.get("start", ""))
    stop = minutes(prog.get("stop", ""))
    if start is None or stop is None or stop <= start:
        conflitos += 1
        continue
    anterior = ultimo.get(cid)
    if anterior is not None and start < anterior:
        conflitos += 1
    ultimo[cid] = stop

hoje = now.strftime("%Y%m%d")
amanha = (now + timedelta(days=1)).strftime("%Y%m%d")
prog_hoje = [p for p in programmes_xml if p.get("start", "")[:8] == hoje]
prog_amanha = [p for p in programmes_xml if p.get("start", "")[:8] == amanha]
can_hoje = {p.get("channel") for p in prog_hoje}
can_amanha = {p.get("channel") for p in prog_amanha}
extra = [c for c in ids_xml if c not in m3u_norm and norm(c) not in m3u_norm]
sem_epg = [t for t in m3u_ids if t not in selected]

print(f"   XML valido .............. sim")
print(f"   canais no EPG ............ {len(canais_xml)} (M3U: {len(m3u_ids)})")
print(f"   canais fora da M3U ....... {len(extra)}")
print(f"   programas ................ {len(programmes_xml)}")
print(f"   programas sem <channel> .. {len(orfas)}")
print(f"   conflitos de horario ..... {conflitos}")
print(f"   hoje ({hoje}) ...... {len(prog_hoje)} programas em {len(can_hoje)} canais")
print(f"   amanha ({amanha}) .... {len(prog_amanha)} programas em {len(can_amanha)} canais")
print(f"   canais da M3U sem EPG .... {len(sem_epg)}")

print()
print("   Conference por canal (fonte EPG usada):")
por_canal_hoje = defaultdict(list)
for prog in prog_hoje:
    por_canal_hoje[prog.get("channel")].append(prog)
for tid, source, _total, _filled in relatorio:
    lista = sorted(por_canal_hoje.get(tid, []), key=lambda p: minutes(p.get("start")))
    amostra = " | ".join(
        f"{((minutes(p.get('start')) - hoje_ini) // 60) % 24:02d}h {p.findtext('title', '')[:24]}"
        for p in lista[:2]
    )
    print(
        f"     {tid:30s} {m3u_info.get(tid, {}).get('name', '')[:24]:24s} "
        f"{len(lista):3d} prog  {epg_feed.get((tid, source), '?')[:26]:26s} {amostra}"
    )

print()
if not orfas and conflitos == 0 and not extra and prog_hoje and prog_amanha:
    print("   RESULTADO: EPG OK - apenas canais da M3U, sem conflitos,")
    print("              com programacao de hoje e amanha.")
    sys.exit(0)

print("   RESULTADO: EPG com pendencias.")
sys.exit(1)
