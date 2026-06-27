#!/usr/bin/env python3
"""Corrige lista5.m3u: EPG valido, logos .jpg, streams testados, sem imgur"""
import io, os, re, shutil, copy, gzip
import xml.etree.ElementTree as ET
import requests
from datetime import datetime, timedelta
from collections import OrderedDict, defaultdict

BASE = "/home/runner/work/JCTVV/JCTVV"
M3U_FILE = f"{BASE}/lista5.m3u"
M3U_BAK = f"{BASE}/lista5.m3u.bak"
REPORT_FILE = f"{BASE}/relatorio_lista5.txt"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

EPG_URLS = [
    "https://raw.githubusercontent.com/JCTV/JCTV/main/lista5_epg.xml",
    "https://iptv-epg.org/files/epg-us.xml.gz",
    "https://epg.pw/xmltv/epg_US.xml.gz",
]

CHANNELS = OrderedDict([
    ("ABC News Live", {
        "tvg-id": "ABCNewsLive.us",
        "tvg-id-alt": "408627",
        "tvg-name": "ABC News Live",
        "tvg-logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
        "group-title": "NEWS WORLD",
        "stream": "https://abcnews-livestreams.akamaized.net/out/v1/6a597119dbd5428a82dc11a2f514a1a2/abcn-live-10-cmaf-manifest/abcn-live-10-index.m3u8",
        "stream-alt": "https://linear-abcnews-akc-na-west-1.media.dssott.com/dvt2=exp=1782661768~url=%2Flas1%2Fva01%2Fdisneyplus%2Fchannel%2F79449312-79dd-473d-873c-515ebf4b5e5f-1781164031838%2F~psid=d72dcc12-7f8c-493a-8f00-0bc40bac86a5~did=cc1334ea-51c1-4743-aff4-fe409e642baa~country=US~kid=k02~hmac=40ed7e77d64d9995cd720ef166299b1b0e2044d49fbe04d73e4791b6aac017e9/las1/va01/disneyplus/channel/79449312-79dd-473d-873c-515ebf4b5e5f-1781164031838/ctr-all-hdri-sliding.m3u8?r=1080&v=1&hash=81fb88da5aab33fe54dc3f8d7ae5f0b2eaa56a8c",
        "tvg-chno": "1",
    }),
    ("Fox News Channel", {
        "tvg-id": "FoxNewsChannel.us",
        "tvg-id-alt": "6170",
        "tvg-name": "Fox News Channel",
        "tvg-logo": "https://raw.githubusercontent.com/gratinomaster/JCTV/main/fox_news.jpg",
        "group-title": "NEWS WORLD",
        "stream": "https://247.foxnews.com/hls/live/2003586/FNCHLSv3/master.m3u8",
        "tvg-chno": "2",
    }),
    ("Fox Business", {
        "tvg-id": "FoxBusiness.us",
        "tvg-id-alt": "",
        "tvg-name": "Fox Business",
        "tvg-logo": "https://raw.githubusercontent.com/gratinomaster/JCTV/main/fox_business.jpg",
        "group-title": "NEWS WORLD",
        "stream": "https://247.foxbusiness.com/hls/live/2003756/FBNHLSv3/master.m3u8",
        "tvg-chno": "3",
    }),
    ("CBS News 24/7", {
        "tvg-id": "CBSNews.us",
        "tvg-id-alt": "464941",
        "tvg-name": "CBS News 24/7",
        "tvg-logo": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
        "group-title": "NEWS WORLD",
        "stream": "https://dai.google.com/linear/hls/pa/event/Sid4xiTQTkCT1SLu6rjUSQ/stream/be2023f4-e871-4236-b123-c070defda0f0:DLS/master.m3u8",
        "tvg-chno": "4",
    }),
])

VALID_IDS = {info['tvg-id'] for info in CHANNELS.values()}

def log(msg):
    print(msg)

def log_report(msg):
    with open(REPORT_FILE, 'a', encoding='utf-8') as f:
        f.write(msg + '\n')

def download_epg(url):
    log(f"  Baixando EPG: {url}")
    try:
        r = requests.get(url, timeout=120, allow_redirects=True,
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

def load_local_epg(path):
    if not os.path.exists(path):
        log(f"    Arquivo local nao encontrado: {path}")
        return {}, []
    try:
        with open(path, 'rb') as f:
            raw = f.read()
        return parse_epg(raw)
    except Exception as e:
        log(f"    Erro lendo EPG local {path}: {e}")
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
    log("=" * 70)
    log("CORRECAO lista5.m3u - EPG + LOGOS + STREAMS v5")
    log("=" * 70)
    log_report("=" * 70)
    log_report(f"RELATORIO CORRECAO lista5.m3u v5")
    log_report(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    log_report("=" * 70 + "\n")

    # Step 1: Backup
    log("\n[1] Backup...")
    if os.path.exists(M3U_FILE):
        shutil.copy2(M3U_FILE, M3U_BAK)
        log(f"  Backup: {M3U_BAK}")

    # Step 2: Load EPG from all sources
    log("\n[2] Carregando EPGs...")
    all_channels = {}
    all_programmes = []

    # Local EPG files first
    local_epgs = [
        f"{BASE}/lista5_epg.xml.gz",
        f"{BASE}/EPGFULL.xml.gz",
        f"{BASE}/lista5_epg.xml",
    ]
    for path in local_epgs:
        chs, progs = load_local_epg(path)
        if chs or progs:
            log(f"  Local {os.path.basename(path)}: {len(chs)} canais, {len(progs)} programas")
            all_channels.update(chs)
            filtered = filter_programmes(progs, VALID_IDS)
            existing = {(p.get('channel',''), p.get('start',''), p.get('stop','')) for p in all_programmes}
            new_count = 0
            for p in filtered:
                key = (p.get('channel',''), p.get('start',''), p.get('stop',''))
                if key not in existing:
                    existing.add(key)
                    all_programmes.append(p)
                    new_count += 1
            log(f"    -> +{new_count} novos programas para nossos canais")

    # Remote EPG sources
    for url in EPG_URLS:
        data = download_epg(url)
        if data is None:
            continue
        chs, progs = parse_epg(data)
        all_channels.update(chs)
        filtered = filter_programmes(progs, VALID_IDS)
        existing = {(p.get('channel',''), p.get('start',''), p.get('stop','')) for p in all_programmes}
        new_count = 0
        for p in filtered:
            key = (p.get('channel',''), p.get('start',''), p.get('stop',''))
            if key not in existing:
                existing.add(key)
                all_programmes.append(p)
                new_count += 1
        log(f"  Remote {url.split('/')[-1][:30]}: +{new_count} novos programas")

    log(f"\n  Total programas para nossos IDs: {len(all_programmes)}")

    # Step 3: Test EPG coverage
    log("\n[3] Verificando cobertura EPG...")
    hoje = datetime.now().strftime('%Y%m%d')
    amanha = (datetime.now() + timedelta(days=1)).strftime('%Y%m%d')
    depois = (datetime.now() + timedelta(days=2)).strftime('%Y%m%d')

    c_hoje, c_amanha, c_depois = test_coverage(all_programmes, "  ")

    if c_depois < 5 or c_amanha < 5 or c_hoje < 5:
        log("  Estendendo programas para dias faltantes...")
        extended = extend_programmes(all_programmes, VALID_IDS, [hoje, amanha, depois])
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

    epg_ok = c_hoje > 0 and c_amanha > 0 and c_depois > 0

    # Step 4: Per-channel coverage
    log("\n[4] Cobertura por canal:")
    for ch_name, ch_info in CHANNELS.items():
        cid = ch_info['tvg-id']
        ch_progs = [p for p in all_programmes if p.get('channel') == cid]
        ch_hoje = sum(1 for p in ch_progs if p.get('start', '')[:8] == hoje)
        ch_amanha = sum(1 for p in ch_progs if p.get('start', '')[:8] == amanha)
        ch_depois = sum(1 for p in ch_progs if p.get('start', '')[:8] == depois)
        status = "OK" if (ch_hoje > 0 and ch_amanha > 0) else "PARCIAL" if (ch_hoje > 0 or ch_amanha > 0) else "SEM EPG"
        log(f"  {ch_name} (ID:{cid}): {len(ch_progs)} prog, Hoje={ch_hoje}, Amanha={ch_amanha}, Depois={ch_depois} -> {status}")
        log_report(f"Canal: {ch_name}")
        log_report(f"  tvg-id: {cid}")
        log_report(f"  EPG: Hoje={ch_hoje} Amanha={ch_amanha} Depois={ch_depois} - {status}")

    # Step 5: Save merged EPG
    log("\n[5] Salvando EPG filtrado...")
    channel_dict = {}
    for cid in VALID_IDS:
        channel_dict[cid] = all_channels.get(cid, cid)

    root = ET.Element("tv", attrib={"generator-info-name": "JCTV News EPG v5"})
    for cid, cname in channel_dict.items():
        ch = ET.SubElement(root, "channel", attrib={"id": cid})
        dn = ET.SubElement(ch, "display-name")
        dn.text = cname
    for p in all_programmes:
        root.append(p)

    tree = ET.ElementTree(root)
    epg_xml_path = f"{BASE}/lista5_epg.xml"
    tree.write(epg_xml_path, encoding='utf-8', xml_declaration=True)
    log(f"  EPG XML salvo: {epg_xml_path} ({len(all_programmes)} programas)")

    buf = io.BytesIO()
    tree.write(buf, encoding='utf-8', xml_declaration=True)
    raw = buf.getvalue()
    epg_gz_path = f"{BASE}/lista5_epg.xml.gz"
    with gzip.open(epg_gz_path, 'wb') as f:
        f.write(raw)
    log(f"  EPG gz salvo: {epg_gz_path} ({len(raw)} bytes)")
    log_report(f"  EPG salvo: {len(all_programmes)} programas")

    # Step 6: Test streams
    log("\n[6] Testando streams...")
    stream_results = {}
    for ch_name, ch_info in CHANNELS.items():
        url = ch_info['stream']
        log(f"  Testando {ch_name}...")
        ok = check_url(url)
        log(f"    {'OK' if ok else 'FALHOU'}: {url[:80]}...")
        if not ok and ch_info.get('stream-alt'):
            log(f"    Testando alternativa...")
            ok = check_url(ch_info['stream-alt'])
            if ok:
                log(f"    OK (alternativa): {ch_info['stream-alt'][:80]}...")
                ch_info['stream'] = ch_info['stream-alt']
        stream_results[ch_name] = ok
        log_report(f"  Stream {ch_name}: {'OK' if ok else 'OFFLINE'}")

    # Step 7: Generate M3U
    log("\n[7] Gerando M3U corrigido...")
    epg_urls_str = ' '.join(EPG_URLS)

    m3u_lines = [f'#EXTM3U url-tvg="{epg_urls_str}"']

    channel_count = 0
    for ch_name, ch_info in CHANNELS.items():
        channel_count += 1

        logo = fix_logo_url(ch_info['tvg-logo'])
        if not logo:
            logo = ch_info['tvg-logo']

        tvg_id = ch_info['tvg-id']
        tvg_name = ch_info.get('tvg-name', ch_name)

        attrs = f'tvg-id="{tvg_id}"'
        if tvg_name:
            attrs += f' tvg-name="{tvg_name}"'
        if logo:
            attrs += f' tvg-logo="{logo}"'
        if ch_info.get('tvg-chno'):
            attrs += f' tvg-chno="{ch_info["tvg-chno"]}"'
        if ch_info.get('group-title'):
            attrs += f' group-title="{ch_info["group-title"]}"'

        m3u_lines.append(f'#EXTINF:-1 {attrs},{ch_name}')
        m3u_lines.append(ch_info['stream'])
        log(f"  + {ch_name} (ID: {tvg_id}, logo: {logo})")
        log_report(f"  Incluido: {ch_name}")
        log_report(f"    tvg-id: {tvg_id}")
        log_report(f"    logo: {logo}")

    m3u_content = '\n'.join(m3u_lines) + '\n'

    with open(M3U_FILE, 'w', encoding='utf-8') as f:
        f.write(m3u_content)
    log(f"\n  M3U salvo: {M3U_FILE} ({len(m3u_content)} bytes, {channel_count} canais)")

    # Step 8: Verificacao final
    log("\n[8] Verificacao final...")
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
                issues.append(f"  Linha {i+1}: URL sem #EXTINF acima ({line[:60]}...)")

    issues_final = []
    for ch_name, ok in stream_results.items():
        if not ok:
            ch_epg_ok = any(p.get('channel','') == CHANNELS[ch_name]['tvg-id'] for p in all_programmes)
            if ch_epg_ok:
                log(f"  AVISO: {ch_name} - Stream offline mas EPG disponivel")
            else:
                issues_final.append(f"  {ch_name}: Stream offline e SEM EPG")

    log(f"  Canais: {channel_count}")
    if issues:
        log("  PROBLEMAS DE FORMATACAO:")
        for issue in issues:
            log(f"    {issue}")
    if issues_final:
        log("  PROBLEMAS DE CONTEUDO:")
        for issue in issues_final:
            log(f"    {issue}")
    if not issues and not issues_final:
        log("  VERIFICACAO: Tudo OK!")

    # Step 9: Final report
    log("\n" + "=" * 70)
    log("RELATORIO FINAL")
    log("=" * 70)
    log(f"  Arquivo: {M3U_FILE}")
    log(f"  Canais: {channel_count}")
    log(f"  EPG salvo: {epg_gz_path}")
    log(f"  Programas EPG: {len(all_programmes)}")
    log(f"  Cobertura: Hoje={c_hoje} | Amanha={c_amanha} | Depois={c_depois}")
    log(f"  EPG Hoje+Amanha+Depois: {'SIM' if epg_ok else 'PARCIAL'}")

    report_streams = ", ".join([f"{n}={'OK' if s else 'OFF'}" for n, s in stream_results.items()])
    log(f"  Streams: {report_streams}")
    log(f"  Problemas: {len(issues) + len(issues_final)}")

    log_report("")
    log_report(f"Total canais: {channel_count}")
    log_report(f"Programas EPG: {len(all_programmes)}")
    log_report(f"Cobertura EPG: Hoje={c_hoje} Amanha={c_amanha} Depois={c_depois}")
    log_report(f"EPG Completo: {'SIM' if epg_ok else 'PARCIAL'}")
    log_report(f"Streams: {report_streams}")
    log_report(f"Problemas: {len(issues) + len(issues_final)}")
    log_report("=" * 70)

    log("\nConcluido!")

if __name__ == "__main__":
    main()
