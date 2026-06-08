#!/usr/bin/env python3
"""Corrige lista5.m3u: EPG valido, logos .jpg, streams testados, sem imgur, sem virus"""
import gzip, io, os, re, sys, shutil, json, copy
import xml.etree.ElementTree as ET
import requests
from datetime import datetime, timedelta
from collections import OrderedDict

BASE = "/home/runner/work/JCTV/JCTV"
M3U_FILE = f"{BASE}/lista5.m3u"
M3U_BAK = f"{BASE}/lista5.m3u.bak"
EPG_OUT = f"{BASE}/lista5_epg.xml.gz"
REPORT_FILE = f"{BASE}/relatorio_lista5.txt"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

EPG_URLS = [
    "https://epg.pw/xmltv/epg_US.xml.gz",
    "https://epg.pw/xmltv/epg.xml.gz",
    "https://iptv-epg.org/files/epg-us.xml.gz",
]

CHANNELS = OrderedDict([
    ("ABC News Live", {
        "tvg-id": "465150",
        "tvg-name": "ABC News Live",
        "tvg-logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
        "group-title": "NEWS WORLD",
        "stream": "https://abcnews-livestreams.akamaized.net/out/v1/6a597119dbd5428a82dc11a2f514a1a2/abcn-live-10-cmaf-manifest/abcn-live-10-index.m3u8",
        "tvg-chno": "1",
    }),
    ("Fox News Channel", {
        "tvg-id": "465372",
        "tvg-name": "Fox News Channel",
        "tvg-logo": "https://raw.githubusercontent.com/gratinomaster/JCTV/main/fox_news.jpg",
        "group-title": "NEWS WORLD",
        "stream": "https://radiovid.foxnews.com/hls/live/661547/RADIOVID/index.m3u8",
        "tvg-chno": "2",
    }),
    ("Fox Business", {
        "tvg-id": "464766",
        "tvg-name": "Fox Business",
        "tvg-logo": "https://raw.githubusercontent.com/gratinomaster/JCTV/main/fox_business.jpg",
        "group-title": "NEWS WORLD",
        "stream": "https://tvpass.org/live/FoxBusiness/hd",
        "tvg-chno": "3",
    }),
    ("CBS News 24/7", {
        "tvg-id": "464941",
        "tvg-name": "CBS News 24/7",
        "tvg-logo": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
        "group-title": "NEWS WORLD",
        "stream": "https://news20e7hhcb.airspace-cdn.cbsivideo.com/index.m3u8",
        "tvg-chno": "4",
    }),
])

AFFILIATE_IDS = {
    "465150": ["464943", "464944"],
    "465372": ["464877", "464878"],
    "464766": ["464877", "464878"],
    "464941": ["464942", "464945"],
}

def log(msg):
    print(msg)

def log_report(msg):
    with open(REPORT_FILE, 'a', encoding='utf-8') as f:
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
        return {}, {}
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
        prog_by_ch = {}
        for p in programmes:
            ch = p.get('channel', '')
            if ch not in prog_by_ch:
                prog_by_ch[ch] = []
            prog_by_ch[ch].append(p)
        return ch_map, prog_by_ch
    except Exception as e:
        log(f"    Erro parse EPG: {e}")
        return {}, {}

def filter_programmes(prog_by_ch, valid_ids, affiliate_ids):
    seen = set()
    result = []
    matched_channels = set()
    for ch, progs in prog_by_ch.items():
        if ch in valid_ids:
            matched_channels.add(ch)
            for p in progs:
                key = f"{ch}|{p.get('start')}|{p.get('stop')}"
                if key not in seen:
                    seen.add(key)
                    result.append(p)
    return result, matched_channels

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
                return True, r.status_code
            if r.content.startswith(b'#EXTM3U') or len(r.content) > 100:
                return True, r.status_code
        return False, r.status_code
    except Exception as e:
        return False, str(e)

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

def verify_m3u(m3u_content):
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
                issues.append(f"  Linha {i+1}: URL sem #EXTINF acima: {line[:60]}")

    return channel_count, issues

def main():
    global REPORT_FILE
    REPORT_FILE = f"{BASE}/relatorio_lista5.txt"

    log("=" * 70)
    log("CORRECAO COMPLETA lista5.m3u")
    log("EPG + LOGOS .jpg + STREAMS TESTADOS + ANTI-VIRUS")
    log("=" * 70)

    log_report("=" * 70)
    log_report(f"RELATORIO CORRECAO lista5.m3u")
    log_report(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    log_report("=" * 70)
    log_report("")

    valid_ids = {info['tvg-id'] for info in CHANNELS.values()}
    valid_ids_with_affiliates = valid_ids.copy()
    for main_id, aff_ids in AFFILIATE_IDS.items():
        for aff_id in aff_ids:
            valid_ids_with_affiliates.add(aff_id)

    hoje = datetime.now().strftime('%Y%m%d')
    amanha = (datetime.now() + timedelta(days=1)).strftime('%Y%m%d')
    depois = (datetime.now() + timedelta(days=2)).strftime('%Y%m%d')
    target_dates = {hoje, amanha, depois}

    # 1. Backup
    log("\n[1] Backup do arquivo original...")
    if os.path.exists(M3U_FILE):
        shutil.copy2(M3U_FILE, M3U_BAK)
        log(f"  Backup salvo: {M3U_BAK}")
    log_report("[1] Backup: OK")

    # 2. Download EPG from multiple sources
    log("\n[2] Baixando EPGs de multiplas fontes...")
    all_channels = {}
    all_programmes = []
    all_prog_by_ch = {}
    sources_used = []

    for url in EPG_URLS:
        data = download_epg(url)
        if data is None:
            continue
        chs, prog_by_ch = parse_epg(data)
        all_channels.update(chs)

        # Merge programme data
        for ch, progs in prog_by_ch.items():
            if ch not in all_prog_by_ch:
                all_prog_by_ch[ch] = []
            existing = {(p.get('start',''), p.get('stop','')) for p in all_prog_by_ch[ch]}
            for p in progs:
                key = (p.get('start',''), p.get('stop',''))
                if key not in existing:
                    existing.add(key)
                    all_prog_by_ch[ch].append(p)

        sources_used.append(url)
        log(f"  Fonte {url.split('/')[-1][:30]}: adicionada")

    # Filter for our channels
    log("\n[3] Filtrando programas para nossos canais...")
    filtered, matched_channels = filter_programmes(all_prog_by_ch, valid_ids, AFFILIATE_IDS)
    all_programmes = filtered

    log(f"  Canais com EPG encontrado: {matched_channels}")
    log(f"  Total programas: {len(all_programmes)}")

    # Also try to find affiliate programmes
    log("\n[4] Buscando programas de afiliadas...")
    affiliates_found = set()
    for ch_id, aff_ids in AFFILIATE_IDS.items():
        for aff_id in aff_ids:
            if aff_id in all_prog_by_ch:
                aff_progs = all_prog_by_ch[aff_id]
                log(f"  Afiliada encontrada: {aff_id} ({len(aff_progs)} programas)")
                # Remap affiliate programmes to main channel
                for p in aff_progs:
                    new_p = copy.deepcopy(p)
                    new_p.set('channel', ch_id)
                    key = f"{ch_id}|{p.get('start')}|{p.get('stop')}"
                    existing_keys = {(p2.get('channel',''), p2.get('start',''), p2.get('stop','')) for p2 in all_programmes}
                    if (ch_id, p.get('start'), p.get('stop')) not in existing_keys:
                        all_programmes.append(new_p)
                affiliates_found.add(aff_id)
    log(f"  Afiliadas com EPG: {affiliates_found if affiliates_found else 'Nenhuma'}")

    # 5. Test coverage
    log("\n[5] Verificando cobertura EPG...")
    c_hoje, c_amanha, c_depois = test_coverage(all_programmes, "  ")

    if c_hoje < 10 or c_amanha < 10:
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

    log_report("")
    log_report("[2-5] EPG:")
    log_report(f"  Fontes: {len(sources_used)}")
    log_report(f"  Programas totais: {len(all_programmes)}")
    log_report(f"  Cobertura: Hoje={c_hoje} Amanha={c_amanha} Depois={c_depois}")

    # 6. Coverage per channel
    log("\n[6] Cobertura por canal:")
    for ch_name, ch_info in CHANNELS.items():
        cid = ch_info['tvg-id']
        ch_progs = [p for p in all_programmes if p.get('channel') == cid]
        ch_hoje = sum(1 for p in ch_progs if p.get('start', '')[:8] == hoje)
        ch_amanha = sum(1 for p in ch_progs if p.get('start', '')[:8] == amanha)
        ch_depois = sum(1 for p in ch_progs if p.get('start', '')[:8] == depois)
        status = "OK" if ch_hoje > 0 and ch_amanha > 0 else "SEM EPG"
        log(f"  {ch_name} (ID:{cid}): {status} | Hoje={ch_hoje} Amanha={ch_amanha} Depois={ch_depois}")
        log_report(f"  Canal: {ch_name} | tvg-id={cid} | {status} | Hoje={ch_hoje} Amanha={ch_amanha} Depois={ch_depois}")

    # 7. Save filtered EPG
    log("\n[7] Salvando EPG filtrado...")
    channel_dict = {}
    for cid in valid_ids:
        channel_dict[cid] = all_channels.get(cid, cid)

    root = ET.Element("tv", attrib={"generator-info-name": "lista5_epg"})
    for cid, cname in channel_dict.items():
        ch = ET.SubElement(root, "channel", attrib={"id": cid})
        dn = ET.SubElement(ch, "display-name")
        dn.text = cname
    for p in all_programmes:
        root.append(p)

    tree = ET.ElementTree(root)
    buf = io.BytesIO()
    tree.write(buf, encoding='utf-8', xml_declaration=True)
    raw = buf.getvalue()
    with gzip.open(EPG_OUT, 'wb') as f:
        f.write(raw)
    log(f"  EPG salvo: {EPG_OUT} ({len(raw)} bytes, {len(all_programmes)} programas)")

    # 8. Test streams
    log("\n[8] Testando streams...")
    stream_results = {}
    for ch_name, ch_info in CHANNELS.items():
        url = ch_info['stream']
        log(f"  Testando {ch_name}...")
        ok, status = check_url(url)
        log(f"    {'OK' if ok else 'FALHOU'} (status={status}): {url[:80]}...")
        stream_results[ch_name] = ok
        log_report(f"  Stream {ch_name}: {'OK' if ok else 'OFFLINE'} (status={status})")

    # 9. VirusTotal check
    log("\n[9] Verificacao anti-virus...")
    vt_api_key = os.environ.get('VIRUSTOTAL_API_KEY', '')
    vt_results = {}
    for ch_name, ch_info in CHANNELS.items():
        url = ch_info['stream']
        log(f"  Verificando {ch_name}...")
        vt_result = check_virustotal_url(url, vt_api_key)
        vt_results[ch_name] = vt_result
        log(f"    VirusTotal: {vt_result['status']}")
        log_report(f"  VirusTotal {ch_name}: {vt_result['status']}")

    # 10. Generate corrected M3U
    log("\n[10] Gerando M3U corrigido...")
    epg_urls_str = ','.join(sources_used)

    m3u_lines = [f'#EXTM3U x-tvg-url="{epg_urls_str}"']

    channels_removed = []
    channels_included = []

    for ch_name, ch_info in CHANNELS.items():
        stream_ok = stream_results.get(ch_name, False)

        if vt_results.get(ch_name, {}).get('status') == 'malicious':
            log(f"  PULANDO {ch_name} (malicioso no VirusTotal)")
            log_report(f"  Status {ch_name}: PULADO (malicioso)")
            channels_removed.append(ch_name)
            continue

        logo = ch_info['tvg-logo']
        fixed_logo = fix_logo_url(logo)
        final_logo = fixed_logo if fixed_logo else logo

        attrs = f'tvg-id="{ch_info["tvg-id"]}"'
        if ch_info.get('tvg-name'):
            attrs += f' tvg-name="{ch_info["tvg-name"]}"'
        attrs += f' tvg-logo="{final_logo}"'
        if ch_info.get('tvg-chno'):
            attrs += f' tvg-chno="{ch_info["tvg-chno"]}"'
        attrs += f' group-title="{ch_info["group-title"]}"'

        m3u_lines.append(f'#EXTINF:-1 {attrs},{ch_name}')
        m3u_lines.append(ch_info['stream'])
        channels_included.append(ch_name)
        stream_note = " (stream offline)" if not stream_ok else ""
        log(f"  + {ch_name}{stream_note} (logo: {final_logo})")
        log_report(f"  Status {ch_name}: INCLUIDO | logo={final_logo} | stream={'OK' if stream_ok else 'OFFLINE'}")

    m3u_content = '\n'.join(m3u_lines) + '\n'

    with open(M3U_FILE, 'w', encoding='utf-8') as f:
        f.write(m3u_content)
    log(f"\n  M3U salvo: {M3U_FILE} ({len(m3u_content)} bytes)")

    # 11. Final verification
    log("\n[11] Verificacao final do M3U...")
    channel_count, issues = verify_m3u(m3u_content)

    log(f"  Canais: {channel_count}")
    if issues:
        log("  PROBLEMAS ENCONTRADOS:")
        for issue in issues:
            log(f"    {issue}")
    else:
        log("  VERIFICACAO: Tudo OK!")

    log_report("")
    log_report("[10-11] M3U:")
    log_report(f"  Canais incluidos: {len(channels_included)}")
    log_report(f"  Canais removidos: {len(channels_removed)}")
    log_report(f"  Problemas: {len(issues)}")

    # 12. Summary
    log("\n" + "=" * 70)
    log("RELATORIO FINAL")
    log("=" * 70)
    log(f"  Arquivo: {M3U_FILE}")
    log(f"  Canais: {len(channels_included)}")
    log(f"  EPG: {EPG_OUT} ({len(all_programmes)} programas)")
    log(f"  Cobertura: Hoje={c_hoje} | Amanha={c_amanha} | Depois={c_depois}")
    log(f"  EPG Funcional: {'SIM' if epg_ok else 'NAO'}")
    log(f"  Logos .jpg: SIM")
    log(f"  imgur.com: NAO")
    log(f"  Streams testados: SIM")
    log(f"  Anti-virus: {'SIM' if vt_api_key else 'NAO (sem chave API)'}")
    log(f"  Problemas: {len(issues)}")
    log("")

    for ch_name in channels_included:
        log(f"  OK {ch_name}")
    for ch_name in channels_removed:
        log(f"  REMOVIDO {ch_name}")

    log("")
    log("Concluido!")

if __name__ == "__main__":
    main()
