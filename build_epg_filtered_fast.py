import gzip, io, re, os, sys, copy
import xml.etree.ElementTree as ET
from collections import OrderedDict
from datetime import datetime, timedelta
import urllib.request

M3U_LOCAL = "/home/runner/work/JCTVV/JCTVV/NEWSWORLDNOVOS.m3u"
OUTPUT = "/home/runner/work/JCTVV/JCTVV/EPGFULL.xml.gz"

EPG_SOURCES = [
    "https://epgshare01.online/epgshare01/epg_ripper_ALL_SOURCES1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_MX1.xml.gz",
    "https://iptv-epg.org/files/epg-br.xml.gz",
    "https://iptv-epg.org/files/epg-ar.xml.gz",
    "https://iptv-epg.org/files/epg-mx.xml.gz",
    "https://iptv-epg.org/files/epg-us.xml.gz",
    "https://fastly.jsdelivr.net/gh/limaalef/BrazilTVEPG@main/epg.xml",
]

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

print("Carregando M3U...")
if os.path.exists(M3U_LOCAL):
    with open(M3U_LOCAL, "r", encoding="utf-8", errors="replace") as f:
        m3u_text = f.read()
else:
    print("M3U local nao encontrado")
    sys.exit(1)

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

matched_ids = set()
seen_progs = set()
all_channels = OrderedDict()
all_programmes = OrderedDict()

MANUAL_ID_MAP = {
    "aljazeeraenglish.qa": "AlJazeera.qa",
    "nhkworld.japan": "NHKWorld.jp",
    "nhkworld.jp": "NHKWorld.jp",
    "thaipbs.th": "ThaiPBS.th",
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
                    elem.clear(); continue
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
                    elem.clear(); continue
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

print("Baixando EPG...")
for url in EPG_SOURCES:
    data = download(url)
    if data is None:
        continue
    ch, pr = process_epg_bytes(data)
    print(f"    -> +{ch} canais, +{pr} programas")

print(f"Total: {len(matched_ids)} canais, {len(all_programmes)} programas")

print("Gerando EPGFULL.xml.gz...")
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
print(f"Salvo: {OUTPUT} ({file_size:,} bytes)")

print("Testando EPG...")
with gzip.open(OUTPUT, 'rb') as f:
    test_xml = f.read().decode('utf-8', errors='ignore')
test_root = ET.fromstring(test_xml)
canais = test_root.findall("channel")
programas = test_root.findall("programme")
print(f"  Canais: {len(canais)}")
print(f"  Programas: {len(programas)}")

hoje = datetime.now().strftime("%Y%m%d")
amanha = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
prog_hoje = 0; prog_amanha = 0
canais_hoje = set(); canais_amanha = set()
for prog in programas:
    start = prog.get("start", "")[:8]
    ch = prog.get("channel", "")
    if start == hoje:
        prog_hoje += 1; canais_hoje.add(ch)
    elif start == amanha:
        prog_amanha += 1; canais_amanha.add(ch)

print(f"  Programas hoje ({hoje}): {prog_hoje} em {len(canais_hoje)} canais")
print(f"  Programas amanha ({amanha}): {prog_amanha} em {len(canais_amanha)} canais")
if canais_hoje:
    print(f"  Canais hoje: {sorted(canais_hoje)[:10]}")

if prog_hoje > 0 and prog_amanha > 0:
    print("  EPG FUNCIONANDO! Programas para hoje e amanha disponiveis.")
    sys.exit(0)
else:
    print("  AVISO: Poucos programas para hoje/amanha.")
    sys.exit(1)
