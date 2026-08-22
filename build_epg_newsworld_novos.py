#!/usr/bin/env python3
import gzip
import io
import re
import os
import sys
import copy
import unicodedata
import xml.etree.ElementTree as ET
from collections import OrderedDict
from datetime import datetime, timedelta
import urllib.request

M3U_URL = "https://github.com/gratinomaster/JCTV/raw/refs/heads/main/NEWSWORLDNOVOS.m3u"
OUTPUT = "EPGFULL.xml.gz"

# Fontes ordenadas: arquivos pequenos primeiro; epg-us (95MB) por ultimo,
# baixado apenas se ainda restarem canais sem dados.
EPG_SOURCES = [
    "https://iptv-epg.org/files/epg-ar.xml.gz",
    "https://iptv-epg.org/files/epg-cl.xml.gz",
    "https://iptv-epg.org/files/epg-mx.xml.gz",
    "https://iptv-epg.org/files/epg-il.xml.gz",
    "https://iptv-epg.org/files/epg-br.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_PT1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_FR1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_MX1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_AR1.xml.gz",
    "https://raw.githubusercontent.com/matthuisman/i.mjh.nz/master/PlutoTV/us.xml",
    "https://iptv-epg.org/files/epg-us.xml.gz",
]

# tvg-id do M3U -> id equivalente nas fontes (quando a grafia difere)
ALIASES = {
    'כאן.11.il': 'כאן11.il',
    'CGTNSpanish.cn': 'CGTNEspanol.us',
    'AlJazeera.Arabic.net': 'AlJazeera.us',
    'Canal.2.de.México.(Canal.Las.Estrellas.-.XEW).mx': 'LasEstrellas.mx',
    'Canal.Telefé.(Argentina).ar': 'Telefe.ar',
    'Rede.Vida.br': 'RedeVida.br',
    'Telesur.ve': 'teleSUR.ar',
    # Canal Pluto TV "Big Brother" (id interno do Pluto) atende BigBrother.us
    'BigBrother.us': '6661f11a41af6400080e90d8',
}


def norm(s):
    s = unicodedata.normalize('NFD', s)
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return re.sub(r'[\s\-_\.\+]+', '', s).lower()


def download(url, timeout=600):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except Exception as e:
        print(f"    Erro ao baixar {url.split('/')[-1]}: {e}")
        return None


print("1. Baixando M3U do GitHub...")
m3u_text = ""
try:
    req = urllib.request.Request(M3U_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        m3u_text = resp.read().decode('utf-8', errors='replace')
    if m3u_text.count('#EXTINF') == 0:
        m3u_text = ""
except Exception as e:
    print(f"  ERRO ao baixar M3U: {e}")

if not m3u_text or m3u_text.count('#EXTINF') == 0:
    print("  ERRO: M3U sem canais!")
    sys.exit(1)

m3u_entries = []
seen = set()
for line in m3u_text.splitlines():
    if not line.startswith('#EXTINF'):
        continue
    tid_m = re.search(r'tvg-id="([^"]*)"', line)
    tname_m = re.search(r'tvg-name="([^"]*)"', line)
    logo_m = re.search(r'tvg-logo="([^"]*)"', line)
    comma_m = re.search(r',([^,]+)$', line)
    tvg_id = (tid_m.group(1) if tid_m else "").strip()
    if not tvg_id or tvg_id in seen:
        continue
    seen.add(tvg_id)
    m3u_entries.append({
        'tvg_id': tvg_id,
        'tvg_name': (tname_m.group(1) if tname_m else "").strip(),
        'logo': (logo_m.group(1) if logo_m else "").strip(),
        'display': (comma_m.group(1) if comma_m else "").strip(),
    })

tvg_ids = set(e['tvg_id'] for e in m3u_entries)

m3u_names = {}
m3u_logos = {}
for e in m3u_entries:
    name_base = re.sub(r'\s*\(.*$', '', e['display']).strip()
    m3u_names[e['tvg_id']] = name_base or e['display']
    m3u_logos[e['tvg_id']] = e['logo'] or e['tvg_name']

print(f"  {len(m3u_entries)} canais no M3U")

# Mapa: id na fonte -> lista de tvg-ids do M3U que ele atende
source_to_targets = {}
for tid in tvg_ids:
    src_id = ALIASES.get(tid, tid)
    source_to_targets.setdefault(src_id, []).append(tid)

src_ids_exact = set(source_to_targets.keys())
tvg_norm = {norm(t): t for t in tvg_ids}


def source_match(cid, display_name):
    """Retorna lista de tvg-ids do M3U atendidos por um canal da fonte."""
    if cid in source_to_targets:
        return list(source_to_targets[cid])
    if display_name:
        ndn = norm(display_name)
        for tid in tvg_ids:
            if norm(m3u_names.get(tid, '')) == ndn:
                return [tid]
    return []


print("\n2. Baixando e filtrando fontes EPG...")
matched_ids = set()
all_channels = OrderedDict()
all_programmes = OrderedDict()
seen_progs = set()


def process_epg(raw_bytes):
    ch_count = 0
    pr_count = 0
    try:
        if raw_bytes[:2] == b'\x1f\x8b':
            f = gzip.GzipFile(fileobj=io.BytesIO(raw_bytes))
        else:
            f = io.BytesIO(raw_bytes)

        for event, elem in ET.iterparse(f, events=('end',)):
            tag = elem.tag
            if tag == 'channel':
                cid = elem.get('id', '')
                if not cid:
                    elem.clear()
                    continue
                dn = elem.find('display-name')
                display_name = dn.text.strip() if dn is not None and dn.text else ''
                targets = source_match(cid, display_name)
                for m3u_id in targets:
                    if m3u_id in matched_ids and m3u_id in all_channels:
                        continue
                    matched_ids.add(m3u_id)
                    ch = copy.deepcopy(elem)
                    ch.set('id', m3u_id)
                    for d in ch.findall('display-name'):
                        d.set('lang', 'pt')
                    if not ch.findall('icon') and m3u_logos.get(m3u_id):
                        ET.SubElement(ch, 'icon', attrib={'src': m3u_logos[m3u_id]})
                    all_channels[m3u_id] = ch
                    ch_count += 1
                elem.clear()
            elif tag == 'programme':
                ch = elem.get('channel', '')
                for m3u_id in source_to_targets.get(ch, []):
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
    nome = url.split('/')[-1]
    falta = len(tvg_ids - matched_ids)
    if falta == 0:
        print(f"  Todos os {len(tvg_ids)} canais encontrados - parando antes de {nome}")
        break
    print(f"  {nome} (faltam {falta}):")
    raw = download(url)
    if raw is None:
        continue
    ch, pr = process_epg(raw)
    print(f"    -> +{ch} canais, +{pr} programas")

print(f"\n3. Resultado: {len(matched_ids)}/{len(tvg_ids)} canais com EPG, {len(all_programmes)} programas")
missing = sorted(tvg_ids - matched_ids)
if missing:
    print(f"  SEM DADOS ({len(missing)}): {missing}")

print("\n4. Salvando EPGFULL.xml.gz (sobrescrevendo)...")
root_out = ET.Element("tv", attrib={"generator-info-name": "EPGFULL (NEWSWORLDNOVOS)"})
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

print(f"  {OUTPUT}: {os.path.getsize(OUTPUT):,} bytes (gzip), {len(xml_data):,} bytes (raw)")

print("\n5. Testando EPG...")
with gzip.open(OUTPUT, 'rb') as f:
    test_root = ET.fromstring(f.read())

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

for ch in canais:
    cid = ch.get('id')
    dn = ch.find("display-name")
    name = dn.text if dn is not None and dn.text else "N/A"
    ch_hoje = sum(1 for p in programas if p.get("channel") == cid and p.get("start", "")[:8] == hoje)
    ch_amanha = sum(1 for p in programas if p.get("channel") == cid and p.get("start", "")[:8] == amanha)
    print(f"    {cid}: {name} - hoje:{ch_hoje} amanha:{ch_amanha}")

print()
if len(canais) > 0 and prog_hoje > 0 and prog_amanha > 0:
    print(f"EPG FUNCIONANDO! {len(canais)}/{len(tvg_ids)} canais do M3U presentes, "
          f"programacao de hoje ({prog_hoje}) e amanha ({prog_amanha}) disponivel.")
    sys.exit(0)
else:
    print("AVISO: EPG incompleto.")
    sys.exit(1)
