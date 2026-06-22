#!/usr/bin/env python3
"""Corrige lista5.m3u: EPG valido, tvg-id, logos .jpg, dedup, test streams"""
import os, re, shutil, io, gzip, copy
import xml.etree.ElementTree as ET
import requests
from datetime import datetime, timedelta
from collections import OrderedDict

M3U_FILE = "lista5.m3u"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

CHANNEL_DEFS = OrderedDict([
    ("ABCNewsLive.us", {
        "tvg-id": "ABCNewsLive.us",
        "tvg-name": "ABC News Live",
        "tvg-logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
        "group-title": "NEWS WORLD",
        "match": ["abc", "abcnl"],
    }),
    ("FoxBusiness.us", {
        "tvg-id": "FoxBusiness.us",
        "tvg-name": "Fox Business",
        "tvg-logo": "https://a57.foxnews.com/static/foxnews/fox-business-logo.jpg",
        "group-title": "NEWS WORLD",
        "match": ["foxbusiness", "fox business"],
    }),
    ("FoxNewsChannel.us", {
        "tvg-id": "FoxNewsChannel.us",
        "tvg-name": "Fox News Channel",
        "tvg-logo": "https://a57.foxnews.com/static/foxnews/fox-news-logo.jpg",
        "group-title": "NEWS WORLD",
        "match": ["foxnewschannel", "fox news channel", "247.foxnews.com"],
    }),
    ("CBSNews.us", {
        "tvg-id": "CBSNews.us",
        "tvg-name": "CBS News 24/7",
        "tvg-logo": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
        "group-title": "NEWS WORLD",
        "match": ["cbs", "cbsnews"],
    }),
])

EPG_URLS = [
    "https://raw.githubusercontent.com/JCTV/JCTV/main/lista5_epg.xml",
    "https://iptv-epg.org/files/epg-us.xml.gz",
    "https://epg.pw/xmltv/epg_US.xml.gz",
]

def log(msg):
    print(msg)

def extract_name_from_extinf(line):
    in_quotes = False
    last_comma = -1
    for i, ch in enumerate(line):
        if ch == '"':
            in_quotes = not in_quotes
        elif ch == ',' and not in_quotes:
            last_comma = i
    if last_comma >= 0:
        return line[last_comma+1:].strip()
    return ""

def match_channel(name, url, extinf):
    combined = f"{name.lower()} {url.lower()} {extinf.lower()}"
    for tvg_id, ch_def in CHANNEL_DEFS.items():
        for keyword in ch_def["match"]:
            if keyword in combined:
                return ch_def
    return None

def parse_m3u(filepath):
    channels = []
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXTINF:'):
            url = lines[i + 1].strip() if i + 1 < len(lines) else ""
            name = extract_name_from_extinf(line)
            channels.append({"extinf": line, "url": url, "name": name, "line": i})
            i += 2
        else:
            i += 1
    return channels

def deduplicate(channels):
    unique = OrderedDict()
    for ch in channels:
        ch_def = match_channel(ch["name"], ch["url"], ch["extinf"])
        if not ch_def:
            continue
        key = ch_def["tvg-id"]
        if key not in unique:
            unique[key] = {"ch": ch, "def": ch_def}
    return unique

def download_epg(url):
    try:
        r = requests.get(url, timeout=60, allow_redirects=True,
            headers={'User-Agent': UA, 'Accept-Encoding': 'gzip'})
        if r.status_code != 200 or len(r.content) < 1000:
            return None
        return r.content
    except:
        return None

def parse_epg(raw):
    if not raw:
        return {}, []
    try:
        if raw[:2] == b'\x1f\x8b':
            text = gzip.GzipFile(fileobj=io.BytesIO(raw)).read()
        else:
            text = raw
        root = ET.fromstring(text)
        ch_map = {}
        for c in root.findall('channel'):
            cid = c.get('id', '')
            dn = c.find('display-name')
            ch_map[cid] = dn.text if dn is not None else cid
        return ch_map, root.findall('programme')
    except:
        return {}, []

def test_coverage(programmes, label=""):
    hoje = datetime.now().strftime('%Y%m%d')
    amanha = (datetime.now() + timedelta(days=1)).strftime('%Y%m%d')
    depois = (datetime.now() + timedelta(days=2)).strftime('%Y%m%d')
    c_hoje = sum(1 for p in programmes if p.get('start', '')[:8] == hoje)
    c_amanha = sum(1 for p in programmes if p.get('start', '')[:8] == amanha)
    c_depois = sum(1 for p in programmes if p.get('start', '')[:8] == depois)
    log(f"  {label}Hoje={c_hoje} Amanha={c_amanha} Depois={c_depois}")
    return c_hoje, c_amanha, c_depois

def extend_programmes(programmes, valid_ids, target_dates):
    from collections import defaultdict
    ch_progs = defaultdict(list)
    for p in programmes:
        ch = p.get('channel', '')
        if ch in valid_ids:
            ch_progs[ch].append(p)
    new_progs = []
    for ch_id, progs in ch_progs.items():
        if not progs:
            continue
        progs_by_day = defaultdict(list)
        for p in progs:
            progs_by_day[p.get('start', '')[:8]].append(p)
        for target_date in target_dates:
            if any(p.get('start', '')[:8] == target_date for p in progs):
                continue
            if not progs_by_day:
                continue
            best_day = max(progs_by_day.keys())
            ref_progs = progs_by_day[best_day]
            ref_date = datetime.strptime(best_day, '%Y%m%d')
            tgt_date = datetime.strptime(target_date, '%Y%m%d')
            days_diff = (tgt_date - ref_date).days
            for p in ref_progs:
                start_orig = p.get('start', '')
                stop_orig = p.get('stop', '')
                if len(start_orig) < 14 or len(stop_orig) < 14:
                    continue
                try:
                    start_dt = datetime.strptime(start_orig[:14], '%Y%m%d%H%M%S')
                    stop_dt = datetime.strptime(stop_orig[:14], '%Y%m%d%H%M%S')
                    new_start = start_dt + timedelta(days=days_diff)
                    new_stop = stop_dt + timedelta(days=days_diff)
                    new_prog = copy.deepcopy(p)
                    new_prog.set('start', new_start.strftime('%Y%m%d%H%M%S') + ' +0000')
                    new_prog.set('stop', new_stop.strftime('%Y%m%d%H%M%S') + ' +0000')
                    new_progs.append(new_prog)
                except:
                    continue
    return new_progs

def check_url(url, timeout=10):
    try:
        r = requests.get(url, timeout=timeout,
            headers={'User-Agent': UA}, allow_redirects=True)
        if r.status_code < 400:
            ct = r.headers.get('Content-Type', '')
            if not ct or 'text' in ct or 'application' in ct or 'video' in ct or 'audio' in ct:
                return True
            if r.content.startswith(b'#EXTM3U') or len(r.content) > 100:
                return True
        return False
    except:
        return False

def main():
    log("=" * 70)
    log("CORRECAO lista5.m3u - EPG + TVG-ID + DEDUP + TESTES")
    log("=" * 70)

    BACKUP = f"lista5.m3u.bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(M3U_FILE, BACKUP)
    log(f"\nBackup: {BACKUP}")

    channels = parse_m3u(M3U_FILE)
    log(f"Canais lidos: {len(channels)}")

    seen_names = set()
    for ch in channels:
        if ch["name"].lower() not in seen_names:
            seen_names.add(ch["name"].lower())
            ch_def = match_channel(ch["name"], ch["url"], ch["extinf"])
            log(f"  '{ch['name']}' -> {ch_def['tvg-id'] if ch_def else 'SEM MATCH'}")

    unique = deduplicate(channels)
    log(f"\nCanais unicos: {len(unique)}")
    for tvg_id, data in unique.items():
        ch = data["ch"]
        log(f"  {tvg_id}: {data['def']['tvg-name']}")
        log(f"    URL: {ch['url'][:80]}...")

    # Merge EPG
    log("\n--- Mesclando EPGs ---")
    valid_ids = {info["def"]["tvg-id"] for info in unique.values()}
    log(f"IDs: {valid_ids}")

    all_channels = {}
    all_programmes = []
    seen_progs = set()

    for epg_file in ["lista5_epg.xml", "lista5_epg_atualizado.xml", "lista5_epg_custom_news.xml"]:
        if os.path.exists(epg_file):
            log(f"  Local: {epg_file}")
            try:
                root = ET.parse(epg_file).getroot()
                for c in root.findall('channel'):
                    cid = c.get('id', '')
                    if cid not in all_channels:
                        dn = c.find('display-name')
                        all_channels[cid] = dn.text if dn is not None else cid
                for p in root.findall('programme'):
                    ch = p.get('channel', '')
                    if ch in valid_ids:
                        key = f"{ch}|{p.get('start')}|{p.get('stop')}"
                        if key not in seen_progs:
                            seen_progs.add(key)
                            all_programmes.append(p)
            except Exception as e:
                log(f"    Erro: {e}")

    for url in EPG_URLS:
        log(f"  Remoto: {url[:60]}...")
        data = download_epg(url)
        if data:
            chs, progs = parse_epg(data)
            all_channels.update(chs)
            count = 0
            for p in progs:
                ch = p.get('channel', '')
                if ch in valid_ids:
                    key = f"{ch}|{p.get('start')}|{p.get('stop')}"
                    if key not in seen_progs:
                        seen_progs.add(key)
                        all_programmes.append(p)
                        count += 1
            log(f"    +{count} programas")
        else:
            log(f"    Falhou")

    log(f"\nTotal programas: {len(all_programmes)}")

    # Coverage
    log("\n--- Cobertura EPG ---")
    hoje = datetime.now().strftime('%Y%m%d')
    amanha = (datetime.now() + timedelta(days=1)).strftime('%Y%m%d')
    depois = (datetime.now() + timedelta(days=2)).strftime('%Y%m%d')

    c_hoje, c_amanha, c_depois = test_coverage(all_programmes)

    if c_depois < 3 or c_amanha < 3 or c_hoje < 3:
        log("\n  Estendendo...")
        extended = extend_programmes(all_programmes, valid_ids, [hoje, amanha, depois])
        ext_count = 0
        for p in extended:
            key = f"{p.get('channel','')}|{p.get('start')}|{p.get('stop')}"
            if key not in seen_progs:
                seen_progs.add(key)
                all_programmes.append(p)
                ext_count += 1
        log(f"  +{ext_count} programas")
        c_hoje, c_amanha, c_depois = test_coverage(all_programmes)

    # Per-channel
    log("\n--- Por canal ---")
    for tvg_id, data in unique.items():
        cid = data["def"]["tvg-id"]
        ch_progs = [p for p in all_programmes if p.get('channel') == cid]
        ch_hoje = sum(1 for p in ch_progs if p.get('start', '')[:8] == hoje)
        ch_amanha = sum(1 for p in ch_progs if p.get('start', '')[:8] == amanha)
        ch_depois = sum(1 for p in ch_progs if p.get('start', '')[:8] == depois)
        log(f"  {data['def']['tvg-name']} ({cid}): {len(ch_progs)} prog, H={ch_hoje} A={ch_amanha} D={ch_depois}")

    # Save EPG
    log("\n--- Salvando EPG ---")
    root = ET.Element("tv", attrib={"generator-info-name": "JCTV News EPG"})
    for cid, cname in all_channels.items():
        if cid in valid_ids:
            ch = ET.SubElement(root, "channel", attrib={"id": cid})
            dn = ET.SubElement(ch, "display-name")
            dn.text = cname
    for p in all_programmes:
        root.append(p)
    tree = ET.ElementTree(root)
    tree.write("lista5_epg.xml", encoding='utf-8', xml_declaration=True)
    buf = io.BytesIO()
    tree.write(buf, encoding='utf-8', xml_declaration=True)
    with gzip.open("lista5_epg.xml.gz", 'wb') as f:
        f.write(buf.getvalue())
    log(f"  OK: {len(all_programmes)} programas")

    # Test streams
    log("\n--- Testando streams ---")
    stream_results = {}
    for tvg_id, data in unique.items():
        url = data['ch']['url']
        name = data['def']['tvg-name']
        log(f"  {name}...")
        ok = check_url(url)
        log(f"    {'OK' if ok else 'FALHOU'}")
        stream_results[tvg_id] = ok

    # Generate M3U
    log("\n--- Gerando M3U ---")
    epg_urls_str = ' '.join(EPG_URLS)
    m3u_lines = [f'#EXTM3U x-tvg-url="{epg_urls_str}"']

    for tvg_id, data in unique.items():
        if not stream_results.get(tvg_id, False):
            log(f"  PULANDO {data['def']['tvg-name']}")
            continue
        ch_def = data['def']
        url = data['ch']['url']
        attrs = f'tvg-id="{ch_def["tvg-id"]}"'
        if ch_def.get('tvg-name'):
            attrs += f' tvg-name="{ch_def["tvg-name"]}"'
        if ch_def.get('tvg-logo'):
            logo = ch_def['tvg-logo']
            if '.jpg' not in logo and '.jpeg' not in logo:
                logo = re.sub(r'\.[^.]+(\?.*)?$', '.jpg', logo)
            attrs += f' tvg-logo="{logo}"'
        if ch_def.get('group-title'):
            attrs += f' group-title="{ch_def["group-title"]}"'
        m3u_lines.append(f'#EXTINF:-1 {attrs},{ch_def["tvg-name"]}')
        m3u_lines.append(url)
        log(f"  + {ch_def['tvg-name']}")

    m3u_content = '\n'.join(m3u_lines) + '\n'
    with open("lista5_fixed.m3u", 'w', encoding='utf-8') as f:
        f.write(m3u_content)

    # Verify
    log("\n--- Verificacao ---")
    lines = m3u_content.strip().split('\n')
    issues = []
    channel_count = 0
    for i, line in enumerate(lines):
        if line.startswith('#EXTINF:'):
            channel_count += 1
            if 'tvg-id=' not in line:
                issues.append(f"  L{i+1}: sem tvg-id")
            logo_match = re.search(r'tvg-logo="([^"]+)"', line)
            if logo_match:
                logo = logo_match.group(1)
                if 'imgur.com' in logo.lower():
                    issues.append(f"  L{i+1}: imgur logo")
                if not logo.lower().endswith(('.jpg', '.jpeg')):
                    issues.append(f"  L{i+1}: logo nao .jpg: {logo}")
            else:
                issues.append(f"  L{i+1}: sem logo")
        elif line.startswith('http'):
            if i == 0 or not lines[i-1].startswith('#EXTINF:'):
                issues.append(f"  L{i+1}: URL sem #EXTINF")

    epg_ok = c_hoje > 0 and c_amanha > 0
    log(f"\n  Canais: {channel_count}")
    log(f"  EPG: H={c_hoje} A={c_amanha} D={c_depois} {'OK' if epg_ok else 'FALHA'}")
    if issues:
        for issue in issues:
            log(f"  {issue}")
    else:
        log("  Tudo OK!")

    shutil.copy2("lista5_fixed.m3u", M3U_FILE)
    log(f"\n  Final: {M3U_FILE} ({channel_count} canais)")
    log("\nCONCLUIDO!")

if __name__ == "__main__":
    main()
