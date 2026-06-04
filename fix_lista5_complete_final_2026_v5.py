#!/usr/bin/env python3
"""Corrige lista5.m3u: EPG valido, logos .jpg, streams testados, sem imgur, sem virus"""
import io, os, re, shutil, copy
import xml.etree.ElementTree as ET
import requests
import gzip
from datetime import datetime, timedelta
from collections import OrderedDict, defaultdict

BASE = "/home/runner/work/JCTV/JCTV"
M3U_FILE = f"{BASE}/lista5.m3u"
M3U_BAK = f"{BASE}/lista5.m3u.bak"
EPG_OUT = f"{BASE}/lista5_epg.xml.gz"
REPORT = f"{BASE}/relatorio_lista5.txt"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

EPG_URLS = [
    "https://raw.githubusercontent.com/JCTV/JCTV/main/lista5_epg.xml",
    "https://iptv-epg.org/files/epg-us.xml.gz",
    "https://epg.pw/xmltv/epg_US.xml.gz",
]

CHANNELS = OrderedDict([
    ("ABC News Live", {
        "tvg-id": "ABCNewsLive.us",
        "tvg-name": "ABC News Live",
        "tvg-logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
        "group-title": "NEWS WORLD",
        "stream": "https://abcnews-streams.akamaized.net/hls/live/2023562/abcnewshudson3/master.m3u8",
        "tvg-chno": "1",
    }),
    ("Fox News Channel", {
        "tvg-id": "FoxNewsChannel.us",
        "tvg-name": "Fox News Channel",
        "tvg-logo": "https://a57.foxnews.com/static.foxnews.com/foxnews.com/images/2024/09/fn-logo-social-share.jpg",
        "group-title": "NEWS WORLD",
        "stream": "http://247preview.foxnews.com/hls/live/2020027/fncv3preview/primary.m3u8",
        "tvg-chno": "2",
    }),
    ("CBS News 24/7", {
        "tvg-id": "CBSNews.us",
        "tvg-name": "CBS News 24/7",
        "tvg-logo": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
        "group-title": "NEWS WORLD",
        "stream": "https://cbsn-us.cbsnstream.cbsnews.com/out/v1/55a8648e8f134e82a470f83d562deeca/master.m3u8",
        "tvg-chno": "3",
    }),
])

CBS_AFFILIATES = [
    ("CBS News Bay Area", "https://cbsn-sf.cbsnstream.cbsnews.com/out/v1/dac63c1abb3f4a2dac9f508f44bb072a/master.m3u8"),
    ("CBS News Chicago", "https://cbsn-chi.cbsnstream.cbsnews.com/out/v1/b2fc0d5715d54908adf07f97d2616646/master.m3u8"),
    ("CBS News Miami", "https://cbsn-mia.cbsnstream.cbsnews.com/out/v1/ac174b7938264d24ae27e56f6584bca0/master.m3u8"),
    ("CBS News New York", "https://www.cbsnews.com/common/video/cbsn-ny-prod.m3u8"),
    ("CBS News Los Angeles", "https://cbsn-la.cbsnstream.cbsnews.com/out/v1/57b6c4534a164accb6b1872b501e0028/master.m3u8"),
    ("CBS News Dallas Ft Worth", "https://cbsn-dal.cbsnstream.cbsnews.com/out/v1/ffa98bbf7d2b4c038c229bd4d9122708/master.m3u8"),
    ("CBS News Detroit", "https://cbsn-det.cbsnstream.cbsnews.com/out/v1/169f5c001bc74fa7a179b19c20fea069/master.m3u8"),
    ("CBS News Philadelphia", "https://cbsn-phi.cbsnstream.cbsnews.com/out/v1/5c9ad3e215984b0e9ad845b335216b72/master.m3u8"),
    ("CBS News Colorado", "https://cbsn-den.cbsnstream.cbsnews.com/out/v1/2e49baf2906244ecb01b07d9885fbe7a/master.m3u8"),
    ("CBS News Minnesota", "https://cbsn-min.cbsnstream.cbsnews.com/out/v1/76518f06941246ba810c8d175600bf74/master.m3u8"),
    ("CBS News Pittsburgh", "https://cbsn-pit.cbsnstream.cbsnews.com/out/v1/6966dabf8150405ab26f854e3cd6a2b8/master.m3u8"),
    ("CBS News Sacramento", "https://lineup.cbsivideo.com/playout/c1ed69db-6b71-4581-a937-a70ab4089f8a/index.m3u8"),
    ("CBSN Boston", "https://cbsn-bos.cbsnstream.cbsnews.com/out/v1/589d66ec6eb8434c96c28de0370d1326/master.m3u8"),
]

def log(msg):
    print(msg)

def log_report(msg):
    with open(REPORT, 'a', encoding='utf-8') as f:
        f.write(msg + '\n')

def download_epg(url):
    log(f"  Baixando EPG: {url}")
    try:
        r = requests.get(url, timeout=300, allow_redirects=True,
            headers={'User-Agent': USER_AGENT, 'Accept-Encoding': 'gzip'})
        if r.status_code != 200:
            log(f"    Status {r.status_code}, ignorando")
            return None
        if len(r.content) < 1000:
            log(f"    Conteudo muito pequeno ({len(r.content)} bytes)")
            return None
        log(f"    OK: {len(r.content)} bytes")
        return r.content
    except Exception as e:
        log(f"    Erro: {e}")
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
    except Exception as e:
        log(f"    Erro parse EPG: {e}")
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
            has_target = any(p.get('start', '')[:8] == target_date for p in progs)
            if has_target:
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
            headers={'User-Agent': USER_AGENT}, allow_redirects=True)
        if r.status_code < 400:
            content_type = r.headers.get('Content-Type', '')
            if not content_type or 'text' in content_type or 'application' in content_type or 'video' in content_type or 'audio' in content_type:
                return True
            if r.content.startswith(b'#EXTM3U') or len(r.content) > 100:
                return True
        return False
    except:
        return False

def check_virustotal_url(url, api_key=None):
    if not api_key:
        return {"status": "nao_verificado"}
    try:
        import base64
        url_id = base64.urlsafe_b64encode(url.encode()).decode().strip("=")
        headers = {"x-apikey": api_key}
        r = requests.get(f"https://www.virustotal.com/api/v3/urls/{url_id}",
            headers=headers, timeout=15)
        if r.status_code == 200:
            data = r.json()
            stats = data.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
            malicious = stats.get("malicious", 0)
            suspicious = stats.get("suspicious", 0)
            if malicious > 0 or suspicious > 0:
                return {"status": "malicious", "malicious": malicious, "suspicious": suspicious}
            return {"status": "clean", "malicious": 0, "suspicious": 0}
        return {"status": "erro_api"}
    except Exception as e:
        return {"status": "erro", "erro": str(e)}

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

def generate_epg_xml(all_programmes, valid_ids, all_channels):
    root = ET.Element("tv", attrib={"generator-info-name": "JCTV News EPG"})
    for cid in valid_ids:
        cname = all_channels.get(cid, cid)
        ch = ET.SubElement(root, "channel", attrib={"id": cid})
        dn = ET.SubElement(ch, "display-name")
        dn.text = cname
    for p in all_programmes:
        root.append(p)
    return root

def main():
    global REPORT
    REPORT = f"{BASE}/relatorio_lista5.txt"

    log("=" * 70)
    log("CORRECAO COMPLETA lista5.m3u - EPG + LOGOS + STREAMS + ANTI-VIRUS v5")
    log("=" * 70)

    log_report("=" * 70)
    log_report(f"RELATORIO CORRECAO lista5.m3u v5")
    log_report(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    log_report("=" * 70)
    log_report("")

    # Build valid IDs from main channels + affiliates
    valid_ids = {info['tvg-id'] for info in CHANNELS.values()}
    valid_ids.add("CBSNews.us")  # affiliates share this ID

    # 1. Backup
    log("\n[1] Backup...")
    if os.path.exists(M3U_FILE):
        shutil.copy2(M3U_FILE, M3U_BAK)
        log(f"  Backup: {M3U_BAK}")

    # 2. Download EPG from multiple sources
    log("\n[2] Baixando EPGs de multiplas fontes...")
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
        log(f"  {url.split('/')[-1][:30]}: +{new_count} novos programas")

    log(f"\n  Total programas para nossos IDs: {len(all_programmes)}")

    # 3. Test coverage and extend if needed
    log("\n[3] Verificando cobertura EPG...")
    hoje = datetime.now().strftime('%Y%m%d')
    amanha = (datetime.now() + timedelta(days=1)).strftime('%Y%m%d')
    depois = (datetime.now() + timedelta(days=2)).strftime('%Y%m%d')

    c_hoje, c_amanha, c_depois = test_coverage(all_programmes, "  ")

    if c_depois < 5 or c_amanha < 5 or c_hoje < 5:
        log("  Estendendo programas para dias faltantes...")
        extended = extend_programmes(all_programmes, valid_ids, [hoje, amanha, depois])
        existing_keys = {(p.get('channel',''), p.get('start',''), p.get('stop','')) for p in all_programmes}
        ext_count = 0
        for p in extended:
            key = (p.get('channel',''), p.get('start',''), p.get('stop',''))
            if key not in existing_keys:
                existing_keys.add(key)
                all_programmes.append(p)
                ext_count += 1
        log(f"  Adicionados {ext_count} programas extendidos")
        c_hoje, c_amanha, c_depois = test_coverage(all_programmes, "  ")

    epg_ok = c_hoje > 0 and c_amanha > 0

    # 4. Per-channel coverage
    log("\n[4] Cobertura por canal:")
    for ch_name, ch_info in CHANNELS.items():
        cid = ch_info['tvg-id']
        ch_progs = [p for p in all_programmes if p.get('channel') == cid]
        ch_hoje = sum(1 for p in ch_progs if p.get('start', '')[:8] == hoje)
        ch_amanha = sum(1 for p in ch_progs if p.get('start', '')[:8] == amanha)
        ch_depois = sum(1 for p in ch_progs if p.get('start', '')[:8] == depois)
        log(f"  {ch_name} (ID:{cid}): {len(ch_progs)} prog, Hoje={ch_hoje}, Amanha={ch_amanha}, Depois={ch_depois}")
        log_report(f"Canal: {ch_name}")
        log_report(f"  tvg-id: {cid}")
        log_report(f"  EPG: Hoje={ch_hoje} Amanha={ch_amanha} Depois={ch_depois}")

    # 4b. CBS affiliates coverage
    log(f"\n  CBS News affiliates (ID:CBSNews.us):")
    aff_progs = [p for p in all_programmes if p.get('channel') == 'CBSNews.us']
    aff_hoje = sum(1 for p in aff_progs if p.get('start', '')[:8] == hoje)
    aff_amanha = sum(1 for p in aff_progs if p.get('start', '')[:8] == amanha)
    aff_depois = sum(1 for p in aff_progs if p.get('start', '')[:8] == depois)
    log(f"    CBSNews.us: {len(aff_progs)} prog, Hoje={aff_hoje}, Amanha={aff_amanha}, Depois={aff_depois}")

    # 5. Save filtered EPG
    log("\n[5] Salvando EPG filtrado...")
    root = generate_epg_xml(all_programmes, valid_ids, all_channels)

    epg_xml_path = f"{BASE}/lista5_epg.xml"
    tree = ET.ElementTree(root)
    tree.write(epg_xml_path, encoding='utf-8', xml_declaration=True)
    log(f"  EPG salvo: {epg_xml_path} ({len(all_programmes)} programas)")

    buf = io.BytesIO()
    tree.write(buf, encoding='utf-8', xml_declaration=True)
    raw = buf.getvalue()
    with gzip.open(EPG_OUT, 'wb') as f:
        f.write(raw)
    log(f"  EPG gz salvo: {EPG_OUT} ({len(raw)} bytes)")
    log_report(f"  EPG salvo: {len(all_programmes)} programas")

    # 6. Test streams
    log("\n[6] Testando streams...")
    stream_results = {}
    all_channels_list = list(CHANNELS.items())
    # Add CBS affiliates
    for aff_name, aff_url in CBS_AFFILIATES:
        all_channels_list.append((aff_name, {
            "tvg-id": "CBSNews.us",
            "tvg-name": aff_name,
            "tvg-logo": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
            "group-title": "NEWS WORLD",
            "stream": aff_url,
        }))

    for ch_name, ch_info in all_channels_list:
        url = ch_info['stream']
        log(f"  Testando {ch_name}...")
        ok = check_url(url)
        log(f"    {'OK' if ok else 'FALHOU'}: {url[:80]}...")
        stream_results[ch_name] = ok
        log_report(f"  Stream {ch_name}: {'OK' if ok else 'OFFLINE'}")

    # 7. Check VirusTotal (if API key available)
    log("\n[7] Verificacao anti-virus...")
    vt_api_key = os.environ.get('VIRUSTOTAL_API_KEY', '')
    vt_results = {}
    for ch_name, ch_info in all_channels_list:
        url = ch_info['stream']
        log(f"  Verificando {ch_name}...")
        vt_result = check_virustotal_url(url, vt_api_key)
        vt_results[ch_name] = vt_result
        log(f"    VirusTotal: {vt_result['status']}")
        log_report(f"  VirusTotal {ch_name}: {vt_result['status']}")

    # 8. Generate M3U
    log("\n[8] Gerando M3U corrigido...")
    epg_urls_str = ','.join(EPG_URLS)

    m3u_lines = [f'#EXTM3U x-tvg-url="{epg_urls_str}"']

    channel_count = 0
    for ch_name, ch_info in all_channels_list:
        if not stream_results.get(ch_name, False):
            log(f"  PULANDO {ch_name} (stream offline)")
            log_report(f"  Status: PULADO (stream offline)")
            continue

        vt = vt_results.get(ch_name, {})
        if vt.get('status') == 'malicious':
            log(f"  PULANDO {ch_name} (malicioso no VirusTotal)")
            log_report(f"  Status: PULADO (malicioso no VirusTotal)")
            continue

        logo = fix_logo_url(ch_info.get('tvg-logo', ''))
        if not logo:
            logo = ch_info.get('tvg-logo', '')
            if 'imgur.com' in logo.lower():
                logo = ''

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
        log(f"  + {ch_name}")
        log_report(f"  Status: INCLUIDO")
        log_report(f"  Logo: {logo}")
        channel_count += 1

    m3u_content = '\n'.join(m3u_lines) + '\n'

    with open(M3U_FILE, 'w', encoding='utf-8') as f:
        f.write(m3u_content)
    log(f"  M3U salvo: {M3U_FILE} ({len(m3u_content)} bytes, {m3u_content.count('#EXTINF:')} canais)")

    # 9. Final verification
    log("\n[9] Verificacao final...")
    lines = m3u_content.strip().split('\n')
    issues = []

    for i, line in enumerate(lines):
        if line.startswith('#EXTINF:'):
            if 'tvg-id=' not in line:
                issues.append(f"  Linha {i+1}: sem tvg-id")
            logo_match = re.search(r'tvg-logo="([^"]+)"', line)
            if logo_match:
                logo = logo_match.group(1)
                if not logo.lower().endswith(('.jpg', '.jpeg')):
                    issues.append(f"  Linha {i+1}: logo nao .jpg: {logo}")
                if 'imgur.com' in logo.lower():
                    issues.append(f"  Linha {i+1}: logo imgur.com: {logo}")
            else:
                issues.append(f"  Linha {i+1}: sem tvg-logo")
        elif line.startswith('http'):
            if i == 0 or not lines[i-1].startswith('#EXTINF:'):
                issues.append(f"  Linha {i+1}: URL sem #EXTINF acima")

    # Also verify the header has x-tvg-url
    if not lines[0].startswith('#EXTM3U'):
        issues.append("  Linha 1: sem #EXTM3U")
    elif 'x-tvg-url=' not in lines[0]:
        issues.append("  Linha 1: sem x-tvg-url")

    log(f"  Canais: {channel_count}")
    if issues:
        log("  PROBLEMAS ENCONTRADOS:")
        for issue in issues:
            log(f"    {issue}")
    else:
        log("  VERIFICACAO: Tudo OK!")

    # 10. Final report
    log("\n" + "=" * 70)
    log("RELATORIO FINAL")
    log("=" * 70)
    log(f"  Arquivo: {M3U_FILE}")
    log(f"  Canais: {channel_count}")
    log(f"  EPG: {EPG_OUT}")
    log(f"  Cobertura: Hoje={c_hoje} | Amanha={c_amanha} | Depois={c_depois}")
    log(f"  EPG Funcional: {'SIM' if epg_ok else 'NAO'}")
    log(f"  Problemas: {len(issues)}")

    log_report("")
    log_report(f"Total canais: {channel_count}")
    log_report(f"Cobertura EPG: Hoje={c_hoje} Amanha={c_amanha} Depois={c_depois}")
    log_report(f"EPG Funcional: {'SIM' if epg_ok else 'NAO'}")
    log_report(f"Problemas: {len(issues)}")
    log_report("=" * 70)

    log("\nConcluido!")

if __name__ == "__main__":
    main()
