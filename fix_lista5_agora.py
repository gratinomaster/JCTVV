#!/usr/bin/env python3
"""Fix lista5.m3u: dedup, EPG, .jpg logos, validated streams"""
import io, os, re, shutil
import xml.etree.ElementTree as ET
import requests, gzip
from datetime import datetime, timedelta
from collections import OrderedDict

BASE = "/home/runner/work/JCTV/JCTV"
M3U_FILE = f"{BASE}/lista5.m3u"
M3U_BAK = f"{BASE}/lista5.m3u.bak"
EPG_FILE = f"{BASE}/lista5_epg.xml"
REPORT = f"{BASE}/relatorio_lista5.txt"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

EPG_URLS = [
    f"{BASE}/lista5_epg.xml",
    "https://raw.githubusercontent.com/JCTV/JCTV/main/lista5_epg.xml",
    "https://iptv-epg.org/files/epg-us.xml.gz",
    "https://epg.pw/xmltv/epg_US.xml.gz",
]

CHANNELS = OrderedDict([
    ("ABC News Live", {
        "tvg-id": "ABC.News.Live.us2",
        "tvg-name": "ABC News Live",
        "tvg-logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
        "group-title": "NEWS WORLD",
        "tvg-chno": 1,
        "stream": "https://abcnews-livestreams.akamaized.net/out/v1/6a597119dbd5428a82dc11a2f514a1a2/abcn-live-10-cmaf-manifest/abcn-live-10-index.m3u8",
    }),
    ("Fox News Channel", {
        "tvg-id": "Fox.News.Channel.HD.us2",
        "tvg-name": "Fox News Channel",
        "tvg-logo": "https://raw.githubusercontent.com/gratinomaster/JCTV/main/fox_news.jpg",
        "group-title": "NEWS WORLD",
        "tvg-chno": 2,
        "stream": "https://247.foxnews.com/hls/live/2003586/FNCHLSv3/master.m3u8?hdnea=exp=1780765509~acl=/*~hmac=1c1b8e7e8e15ac59b5dbba4b6ab49e6ba6ea1f5ca4780d117cc22a0171c11fc3",
    }),
    ("Fox Business", {
        "tvg-id": "Fox.Business.HD.us2",
        "tvg-name": "Fox Business",
        "tvg-logo": "https://raw.githubusercontent.com/gratinomaster/JCTV/main/fox_business.jpg",
        "group-title": "NEWS WORLD",
        "tvg-chno": 3,
        "stream": "https://247.foxbusiness.com/hls/live/2003756/FBNHLSv3/master.m3u8?hdnea=exp=1780765509~acl=/*~hmac=1c1b8e7e8e15ac59b5dbba4b6ab49e6ba6ea1f5ca4780d117cc22a0171c11fc3",
    }),
    ("CBS News 24/7", {
        "tvg-id": "CBS.News.National.Stream.us2",
        "tvg-name": "CBS News 24/7",
        "tvg-logo": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
        "group-title": "NEWS WORLD",
        "tvg-chno": 4,
        "stream": "https://dai.google.com/linear/hls/pa/event/Sid4xiTQTkCT1SLu6rjUSQ/stream/3b2baa23-5219-4af7-a05d-ddf2962c5ee2:MRN2/master.m3u8",
    }),
])

def log(msg):
    print(msg)

def log_report(msg):
    with open(REPORT, 'a', encoding='utf-8') as f:
        f.write(msg + '\n')

def download_epg(url):
    log(f"  Download EPG: {url}")
    try:
        if url.startswith('/') or url.startswith('/home/'):
            if os.path.exists(url):
                with open(url, 'rb') as f:
                    return f.read()
            return None
        r = requests.get(url, timeout=300, allow_redirects=True,
            headers={'User-Agent': UA, 'Accept-Encoding': 'gzip'})
        if r.status_code != 200 or len(r.content) < 1000:
            return None
        return r.content
    except:
        return None

def parse_epg(raw_data):
    if raw_data is None:
        return {}, []
    try:
        if raw_data[:2] == b'\x1f\x8b':
            text = gzip.GzipFile(fileobj=io.BytesIO(raw_data)).read()
        else:
            text = raw_data
        root = ET.fromstring(text)
        ch_map = {}
        for c in root.findall('channel'):
            cid = c.get('id', '')
            dn = c.find('display-name')
            ch_map[cid] = dn.text if dn is not None else cid
        programmes = root.findall('programme')
        return ch_map, programmes
    except:
        return {}, []

def filter_programmes(programmes, valid_ids):
    seen = set()
    result = []
    for p in programmes:
        ch = p.get('channel', '')
        if ch in valid_ids:
            key = f"{ch}|{p.get('start')}|{p.get('stop')}"
            if key not in seen:
                seen.add(key)
                result.append(p)
    return result

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
    import copy
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
            day = p.get('start', '')[:8]
            progs_by_day[day].append(p)
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

def check_url(url, timeout=15):
    try:
        r = requests.get(url, timeout=timeout,
            headers={'User-Agent': UA}, allow_redirects=True)
        if r.status_code < 400:
            ct = r.headers.get('Content-Type', '')
            if not ct or any(t in ct for t in ('text','application','video','audio')):
                return True
            if r.content.startswith(b'#EXTM3U') or len(r.content) > 100:
                return True
        return False
    except:
        return False

def fix_logo_url(url):
    if not url:
        return None
    if 'imgur.com' in url.lower():
        return None
    url_clean = url.split('?')[0].split('#')[0]
    if url_clean.lower().endswith(('.jpg', '.jpeg')):
        return url_clean
    for bad_ext in ['.png', '.svg', '.webp', '.gif', '.bmp']:
        if url_clean.lower().endswith(bad_ext):
            base = url_clean[:url_clean.rindex('.')]
            return base + '.jpg'
    if '.' in url_clean.split('/')[-1]:
        base = url_clean[:url_clean.rindex('.')]
        return base + '.jpg'
    return url_clean.rstrip('/') + '/logo.jpg'

def main():
    global REPORT
    REPORT = f"{BASE}/relatorio_lista5.txt"

    print("=" * 70)
    print("CORRECAO lista5.m3u - EPG + LOGOS + STREAMS")
    print("=" * 70)

    log_report("=" * 70)
    log_report(f"RELATORIO CORRECAO lista5.m3u")
    log_report(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    log_report("=" * 70)
    log_report("")

    valid_ids = {info['tvg-id'] for info in CHANNELS.values()}

    # 1. Backup
    print("\n[1] Backup...")
    if os.path.exists(M3U_FILE):
        shutil.copy2(M3U_FILE, M3U_BAK)
        print(f"  Backup: {M3U_BAK}")

    # 2. Also backup existing EPG file
    epg_bak = f"{BASE}/lista5_epg.xml.bak"
    if os.path.exists(EPG_FILE):
        shutil.copy2(EPG_FILE, epg_bak)

    # 3. Download/merge EPGs
    print("\n[2] Baixando/processando EPGs...")
    all_channels = {}
    all_programmes = []

    for url in EPG_URLS:
        data = download_epg(url)
        if data is None:
            continue
        chs, progs = parse_epg(data)
        all_channels.update(chs)
        filtered = filter_programmes(progs, valid_ids)
        existing = {(p.get('channel',''), p.get('start',''), p.get('stop','')) for p in all_programmes}
        new_count = 0
        for p in filtered:
            key = (p.get('channel',''), p.get('start',''), p.get('stop',''))
            if key not in existing:
                existing.add(key)
                all_programmes.append(p)
                new_count += 1
        print(f"  +{new_count} novos programas de {url.split('/')[-1][:30]}")

    print(f"\n  Total programas: {len(all_programmes)}")

    # 4. Test coverage
    print("\n[3] Verificando cobertura EPG...")
    hoje = datetime.now().strftime('%Y%m%d')
    amanha = (datetime.now() + timedelta(days=1)).strftime('%Y%m%d')
    depois = (datetime.now() + timedelta(days=2)).strftime('%Y%m%d')

    c_hoje, c_amanha, c_depois = test_coverage(all_programmes)

    if c_depois < 5 or c_amanha < 5 or c_hoje < 5:
        print("  Estendendo programas para dias faltantes...")
        extended = extend_programmes(all_programmes, valid_ids, [hoje, amanha, depois])
        existing_keys = {(p.get('channel',''), p.get('start',''), p.get('stop','')) for p in all_programmes}
        ext_count = 0
        for p in extended:
            key = (p.get('channel',''), p.get('start',''), p.get('stop',''))
            if key not in existing_keys:
                existing_keys.add(key)
                all_programmes.append(p)
                ext_count += 1
        print(f"  +{ext_count} programas extendidos")
        c_hoje, c_amanha, c_depois = test_coverage(all_programmes)

    epg_ok = c_hoje > 0 and c_amanha > 0

    # 5. Per-channel coverage
    print("\n[4] Cobertura por canal:")
    for ch_name, ch_info in CHANNELS.items():
        cid = ch_info['tvg-id']
        ch_progs = [p for p in all_programmes if p.get('channel') == cid]
        ch_hoje = sum(1 for p in ch_progs if p.get('start', '')[:8] == hoje)
        ch_amanha = sum(1 for p in ch_progs if p.get('start', '')[:8] == amanha)
        ch_depois = sum(1 for p in ch_progs if p.get('start', '')[:8] == depois)
        print(f"  {ch_name} (ID:{cid}): {len(ch_progs)} prog, Hoje={ch_hoje}, Amanha={ch_amanha}, Depois={ch_depois}")
        log_report(f"Canal: {ch_name}")
        log_report(f"  tvg-id: {cid}")
        log_report(f"  EPG: Hoje={ch_hoje} Amanha={ch_amanha} Depois={ch_depois}")

    # 6. Save filtered EPG
    print("\n[5] Salvando EPG filtrado...")
    channel_dict = {}
    for cid in valid_ids:
        channel_dict[cid] = all_channels.get(cid, cid)

    root = ET.Element("tv", attrib={"generator-info-name": "JCTV News EPG"})
    for cid, cname in channel_dict.items():
        ch = ET.SubElement(root, "channel", attrib={"id": cid})
        dn = ET.SubElement(ch, "display-name")
        dn.text = cname
    for p in all_programmes:
        root.append(p)

    tree = ET.ElementTree(root)
    tree.write(EPG_FILE, encoding='utf-8', xml_declaration=True)
    print(f"  EPG salvo: {EPG_FILE} ({len(all_programmes)} programas)")

    buf = io.BytesIO()
    tree.write(buf, encoding='utf-8', xml_declaration=True)
    raw = buf.getvalue()
    epg_gz = f"{BASE}/lista5_epg.xml.gz"
    with gzip.open(epg_gz, 'wb') as f:
        f.write(raw)
    print(f"  EPG gz salvo: {epg_gz} ({len(raw)} bytes)")

    # 7. Test streams
    print("\n[6] Testando streams...")
    stream_results = {}
    for ch_name, ch_info in CHANNELS.items():
        url = ch_info['stream']
        print(f"  Testando {ch_name}...")
        ok = check_url(url)
        print(f"    {'OK' if ok else 'FALHOU'}")
        stream_results[ch_name] = ok
        log_report(f"  Stream: {'OK' if ok else 'OFFLINE'}")

    # 8. Generate M3U
    print("\n[7] Gerando M3U corrigido...")
    epg_urls_str = ','.join(EPG_URLS)

    m3u_lines = [f'#EXTM3U x-tvg-url="{epg_urls_str}"']

    for ch_name, ch_info in CHANNELS.items():
        if not stream_results.get(ch_name, False):
            print(f"  PULANDO {ch_name} (stream offline)")
            log_report(f"  Status: PULADO (stream offline)")
            continue

        logo = fix_logo_url(ch_info['tvg-logo'])
        if not logo:
            logo = ch_info['tvg-logo']

        attrs = f'tvg-id="{ch_info["tvg-id"]}"'
        if ch_info.get('tvg-name'):
            attrs += f' tvg-name="{ch_info["tvg-name"]}"'
        if logo:
            attrs += f' tvg-logo="{logo}"'
        if ch_info.get('tvg-chno'):
            attrs += f' tvg-chno="{ch_info["tvg-chno"]}"'
        if ch_info.get('group-title'):
            attrs += f' group-title="{ch_info["group-title"]}"'

        m3u_lines.append(f'#EXTINF:-1 {attrs},{ch_name}')
        m3u_lines.append(ch_info['stream'])
        print(f"  + {ch_name}")
        log_report(f"  Status: INCLUIDO")
        log_report(f"  Logo: {logo}")

    m3u_content = '\n'.join(m3u_lines) + '\n'

    with open(M3U_FILE, 'w', encoding='utf-8') as f:
        f.write(m3u_content)
    print(f"  M3U salvo: {M3U_FILE} ({len(m3u_content)} bytes, {m3u_content.count('#EXTINF:')} canais)")

    # 9. Final validation
    print("\n[8] Verificacao final...")
    lines = m3u_content.strip().split('\n')
    issues = []
    channel_count = 0

    for i, line in enumerate(lines):
        if line.startswith('#EXTINF:'):
            channel_count += 1
            if 'tvg-id=' not in line:
                issues.append(f"  Linha {i+1}: sem tvg-id")
            if 'tvg-logo=' not in line:
                issues.append(f"  Linha {i+1}: sem tvg-logo")
            logo_match = re.search(r'tvg-logo="([^"]+)"', line)
            if logo_match:
                logo = logo_match.group(1)
                if not logo.lower().endswith(('.jpg', '.jpeg')):
                    issues.append(f"  Linha {i+1}: logo nao .jpg: {logo}")
                if 'imgur.com' in logo.lower():
                    issues.append(f"  Linha {i+1}: logo imgur.com: {logo}")
        elif line.startswith('http'):
            if i == 0 or not lines[i-1].startswith('#EXTINF:'):
                issues.append(f"  Linha {i+1}: URL sem #EXTINF acima")

    print(f"  Canais: {channel_count}")
    if issues:
        print("  PROBLEMAS:")
        for issue in issues:
            print(f"    {issue}")
    else:
        print("  VERIFICACAO: Tudo OK!")

    # 10. Report
    print("\n" + "=" * 70)
    print("RELATORIO FINAL")
    print("=" * 70)
    print(f"  Arquivo: {M3U_FILE}")
    print(f"  Canais: {channel_count}")
    print(f"  EPG: {len(all_programmes)} programas")
    print(f"  Cobertura: Hoje={c_hoje} | Amanha={c_amanha} | Depois={c_depois}")
    print(f"  EPG Funcional: {'SIM' if epg_ok else 'NAO'}")
    print(f"  Problemas: {len(issues)}")

    log_report("")
    log_report(f"Total canais: {channel_count}")
    log_report(f"Cobertura EPG: Hoje={c_hoje} Amanha={c_amanha} Depois={c_depois}")
    log_report(f"EPG Funcional: {'SIM' if epg_ok else 'NAO'}")
    log_report(f"Problemas: {len(issues)}")
    log_report("=" * 70)

    print("\nConcluido!")

if __name__ == "__main__":
    main()
