#!/usr/bin/env python3
"""Gera EPGFULL.xml.gz contendo SOMENTE os canais do NEWSWORLDNOVOS.m3u.

- Baixa a lista .m3u oficial (fonte da verdade dos tvg-ids).
- Baixa fontes de EPG, mantendo apenas canais cujo tvg-id/display-name
  corresponda a um canal da lista.
- Para canais da lista que nao tenham EPG em nenhuma fonte, cria uma
  grade generica de transmissao ao vivo (hoje/amanha/depois de amanha),
  garantindo que o guia nunca fique vazio.
- Sobrescreve EPGFULL.xml.gz.
"""
import gzip
import io
import os
import re
import sys
import copy
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET
from collections import OrderedDict
from datetime import datetime, timedelta, timezone

M3U_URL = "https://github.com/gratinomaster/JCTV/raw/refs/heads/main/NEWSWORLDNOVOS.m3u"
OUTPUT = "EPGFULL.xml.gz"

EPG_SOURCES = [
    "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_US1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_PT1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_MX1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_AR1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_CL1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_CO1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_FR1.xml.gz",
    "https://epg.pw/xmltv/epg_US.xml.gz",
]

# IDs de origem equivalentes a um tvg-id da lista quando o id exato nao existe.
# Ex.: a lista usa "USCapitol.us", mas as fontes publicam "CSPAN.us2"/"CSPAN.us".
MANUAL_SOURCE_TO_TARGET = {
    "CSPAN.us2": "USCapitol.us",
    "CSPAN2.us2": "USCapitol.us",
    "CSPAN.us": "USCapitol.us",
    "CSPAN2.us": "USCapitol.us",
}

UTC = timezone.utc
HOJE = datetime.now(UTC).date()
DIAS_MANTER = {HOJE + timedelta(days=d) for d in range(-2, 5)}
DIAS_PLACEHOLDER = [HOJE + timedelta(days=d) for d in range(-1, 4)]


def norm(s):
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def tokens(s):
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return {t for t in re.split(r"[^a-z0-9]+", s.lower()) if len(t) >= 3}


def download(url, timeout=180):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except Exception as e:
        print(f"    [aviso] falha ao baixar {url.split('/')[-1]}: {e}")
        return None


print("1. Baixando NEWSWORLDNOVOS.m3u...")
raw = download(M3U_URL, timeout=60)
if not raw:
    print("  ERRO: nao foi possivel baixar a lista.")
    sys.exit(1)
m3u_text = raw.decode("utf-8", errors="replace")

entries = []
seen_ids = set()
for line in m3u_text.splitlines():
    if not line.startswith("#EXTINF"):
        continue
    tid = re.search(r'tvg-id="([^"]*)"', line)
    tname = re.search(r'tvg-name="([^"]*)"', line)
    logo = re.search(r'tvg-logo="([^"]*)"', line)
    comma = re.search(r",([^,]+)$", line)
    tvg_id = (tid.group(1) if tid else "").strip()
    if not tvg_id or tvg_id in ("0", "(no tvg-id)") or tvg_id in seen_ids:
        continue
    seen_ids.add(tvg_id)
    display = (comma.group(1) if comma else "").strip() or tvg_id
    entries.append({
        "id": tvg_id,
        "name": (tname.group(1) if tname else "").strip(),
        "logo": (logo.group(1) if logo else "").strip(),
        "display": display,
    })

if not entries:
    print("  ERRO: a lista nao possui nenhum tvg-id valido.")
    sys.exit(1)

desired = {e["id"]: e for e in entries}
norm_to_id = {}
for e in entries:
    for value in (e["display"], e["name"]):
        if value:
            norm_to_id.setdefault(norm(value), e["id"])

print(f"  {len(entries)} canais com tvg-id: {[e['id'] for e in entries]}")


def name_confident(entry, source_names):
    """Evita casar um id com conteudo de outro canal (ex.: 464944)."""
    if not source_names:
        return True
    want = tokens(entry["display"]) | tokens(entry["name"])
    have = set()
    for n in source_names:
        have |= tokens(n)
    return bool(want & have)


def keep_day(start):
    if len(start) < 8 or not start[:8].isdigit():
        return False
    try:
        d = datetime.strptime(start[:8], "%Y%m%d").date()
    except ValueError:
        return False
    return d in DIAS_MANTER


channels_out = OrderedDict()
programmes_out = OrderedDict()
seen_prog = set()
id_map = {}
matched_targets = set()
real_days = {e["id"]: set() for e in entries}


def add_channel(target, source_channel=None):
    if target in channels_out:
        return
    e = desired[target]
    ch = ET.Element("channel", {"id": target})
    dn = ET.SubElement(ch, "display-name", {"lang": "pt"})
    dn.text = e["display"]
    if e["name"] and norm(e["name"]) != norm(e["display"]):
        dn2 = ET.SubElement(ch, "display-name", {"lang": "pt"})
        dn2.text = e["name"]
    icon = e["logo"]
    if not icon and source_channel is not None:
        ic = source_channel.find("icon")
        if ic is not None:
            icon = ic.get("src", "")
    if icon:
        ET.SubElement(ch, "icon", {"src": icon})
    channels_out[target] = ch


def process_source(data):
    added_ch = 0
    added_pr = 0
    try:
        if data[:2] == b"\x1f\x8b":
            stream = gzip.GzipFile(fileobj=io.BytesIO(data))
        else:
            stream = io.BytesIO(data)
        for event, elem in ET.iterparse(stream, events=("end",)):
            tag = elem.tag
            if tag == "channel":
                cid = (elem.get("id") or "").strip()
                names = [d.text.strip() for d in elem.findall("display-name") if d.text and d.text.strip()]
                target = None
                if cid in desired:
                    if name_confident(desired[cid], names):
                        target = cid
                if target is None and cid in MANUAL_SOURCE_TO_TARGET:
                    candidate = MANUAL_SOURCE_TO_TARGET[cid]
                    if candidate in desired:
                        target = candidate
                if target is None:
                    for n in names:
                        candidate = norm_to_id.get(norm(n))
                        if candidate:
                            target = candidate
                            break
                if target and target not in matched_targets:
                    id_map[cid] = target
                    matched_targets.add(target)
                    add_channel(target, elem)
                    added_ch += 1
                elem.clear()
            elif tag == "programme":
                target = id_map.get((elem.get("channel") or "").strip())
                if target:
                    start = elem.get("start", "")
                    stop = elem.get("stop", "")
                    if keep_day(start):
                        key = (target, start, stop)
                        if key not in seen_prog:
                            seen_prog.add(key)
                            pr = copy.deepcopy(elem)
                            pr.set("channel", target)
                            programmes_out[key] = pr
                            try:
                                real_days[target].add(
                                    datetime.strptime(start[:8], "%Y%m%d").date()
                                )
                            except ValueError:
                                pass
                            added_pr += 1
                elem.clear()
    except Exception as e:
        print(f"    [aviso] erro ao ler fonte: {e}")
    return added_ch, added_pr


print("\n2. Baixando fontes de EPG e filtrando pelos canais da lista...")
for url in EPG_SOURCES:
    data = download(url)
    if data is None:
        continue
    ch, pr = process_source(data)
    print(f"  {url.split('/')[-1]}: +{ch} canais, +{pr} programas")
    if len(matched_targets) >= len(desired):
        break

print("\n3. Completando canais sem EPG com grade de transmissao ao vivo...")
for e in entries:
    target = e["id"]
    add_channel(target)
    for day in DIAS_PLACEHOLDER:
        if day in real_days.get(target, set()):
            continue
        base = datetime(day.year, day.month, day.day, 0, 0, 0, tzinfo=UTC)
        for hour in range(24):
            start = base + timedelta(hours=hour)
            stop = start + timedelta(hours=1)
            key = (target, start.strftime("%Y%m%d%H%M%S +0000"),
                   stop.strftime("%Y%m%d%H%M%S +0000"))
            if key in seen_prog:
                continue
            seen_prog.add(key)
            pr = ET.Element("programme", {
                "start": key[1],
                "stop": key[2],
                "channel": target,
            })
            title = ET.SubElement(pr, "title", {"lang": "pt"})
            title.text = f"{e['display']} - Transmissao ao Vivo"
            desc = ET.SubElement(pr, "desc", {"lang": "pt"})
            desc.text = "Transmissao continua 24 horas."
            ET.SubElement(pr, "category", {"lang": "pt"}).text = "Noticias"
            programmes_out[key] = pr

print(f"  canais no guia: {len(channels_out)}")
print(f"  programas no guia: {len(programmes_out)}")

print("\n4. Gravando EPGFULL.xml.gz...")
root = ET.Element("tv", {"generator-info-name": "EPGFULL (NEWSWORLDNOVOS)"})
for ch in channels_out.values():
    root.append(ch)
for pr in programmes_out.values():
    root.append(pr)
buf = io.BytesIO()
ET.ElementTree(root).write(buf, encoding="utf-8", xml_declaration=True)
xml_data = buf.getvalue()
with gzip.open(OUTPUT, "wb", compresslevel=9) as f:
    f.write(xml_data)
print(f"  {OUTPUT}: {os.path.getsize(OUTPUT):,} bytes comprimidos / {len(xml_data):,} bytes XML")

print("\n5. Verificacao rapida (hoje/amanha)...")
hoje_s = HOJE.strftime("%Y%m%d")
amanha_s = (HOJE + timedelta(days=1)).strftime("%Y%m%d")
p_hoje = [p for p in programmes_out.values() if p.get("start", "")[:8] == hoje_s]
p_amanha = [p for p in programmes_out.values() if p.get("start", "")[:8] == amanha_s]
c_hoje = {p.get("channel") for p in p_hoje}
c_amanha = {p.get("channel") for p in p_amanha}
print(f"  hoje   ({hoje_s}): {len(p_hoje)} programas em {len(c_hoje)} canais {sorted(c_hoje)}")
print(f"  amanha ({amanha_s}): {len(p_amanha)} programas em {len(c_amanha)} canais {sorted(c_amanha)}")
if not p_hoje or not p_amanha:
    print("  AVISO: faltam programas para hoje ou amanha.")
    sys.exit(1)
print("  OK: EPG gerado com programacao de hoje e amanha.")
