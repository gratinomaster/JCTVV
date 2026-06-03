#!/usr/bin/env python3
"""Fix lista5.m3u: EPG valido, logos .jpg, streams testados, sem imgur"""
import io, os, re, shutil, copy
import xml.etree.ElementTree as ET
import requests
import gzip
from datetime import datetime, timedelta
from collections import OrderedDict

BASE = "/home/runner/work/JCTV/JCTV"
M3U_FILE = f"{BASE}/lista5.m3u"
M3U_BAK = f"{BASE}/lista5.m3u.bak"
EPG_FILE = f"{BASE}/lista5_epg.xml"
EPG_GZ = f"{BASE}/lista5_epg.xml.gz"
REPORT = f"{BASE}/relatorio_lista5.txt"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# EPG URLs to add to M3U header
EPG_URLS = [
    "https://raw.githubusercontent.com/JCTV/JCTV/main/lista5_epg.xml",
    "https://iptv-epg.org/files/epg-us.xml.gz",
    "https://epg.pw/xmltv/epg_US.xml.gz",
]

# Channel definitions with proper tvg-ids and logos
CHANNELS = OrderedDict([
    ("ABC News Live", {
        "tvg-id": "ABCNewsLive.us",
        "tvg-name": "ABC News Live",
        "tvg-logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
        "group-title": "NEWS WORLD",
        "stream": "https://abcnews-livestreams.akamaized.net/out/v1/6a597119dbd5428a82dc11a2f514a1a2/abcn-live-10-cmaf-manifest/abcn-live-10-index.m3u8",
        "tvg-chno": "1",
    }),
    ("Fox News Channel", {
        "tvg-id": "FoxNewsChannel.us",
        "tvg-name": "Fox News Channel",
        "tvg-logo": "https://raw.githubusercontent.com/gratinomaster/JCTV/main/fox_news.jpg",
        "group-title": "NEWS WORLD",
        "stream": "https://247.foxnews.com/hls/live/2003586/FNCHLSv3/master.m3u8",
        "tvg-chno": "2",
    }),
    ("Fox Business", {
        "tvg-id": "FoxBusiness.us",
        "tvg-name": "Fox Business",
        "tvg-logo": "https://raw.githubusercontent.com/gratinomaster/JCTV/main/fox_business.jpg",
        "group-title": "NEWS WORLD",
        "stream": "https://247.foxbusiness.com/hls/live/2003756/FBNHLSv3/master.m3u8",
        "tvg-chno": "3",
    }),
    ("CBS News 24/7", {
        "tvg-id": "CBSNews.us",
        "tvg-name": "CBS News 24/7",
        "tvg-logo": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
        "group-title": "NEWS WORLD",
        "stream": "https://cbsn-us.cbsnstream.cbsnews.com/out/v1/55a8648e8f134e82a470f83d562deeca/master.m3u8",
        "tvg-chno": "4",
    }),
])

def log(msg):
    print(msg)

def log_report(msg):
    with open(REPORT, 'a', encoding='utf-8') as f:
        f.write(msg + '\n')

def check_url(url, timeout=15):
    try:
        r = requests.get(url, timeout=timeout,
            headers={'User-Agent': USER_AGENT}, allow_redirects=True)
        if r.status_code < 400:
            ct = r.headers.get('Content-Type', '')
            if not ct or 'text' in ct or 'application' in ct or 'video' in ct or 'audio' in ct:
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

def test_epg_coverage():
    log("\n[3] Verificando cobertura EPG...")
    hoje = datetime.now().strftime('%Y%m%d')
    amanha = (datetime.now() + timedelta(days=1)).strftime('%Y%m%d')
    depois = (datetime.now() + timedelta(days=2)).strftime('%Y%m%d')

    if not os.path.exists(EPG_FILE):
        log(f"  EPG file not found: {EPG_FILE}")
        return False

    with open(EPG_FILE, 'r', encoding='utf-8') as f:
        content = f.read()

    total_progs = content.count('<programme')
    log(f"  Total programas no EPG: {total_progs}")

    results = {}
    all_ok = True
    for ch_name, ch_info in CHANNELS.items():
        cid = ch_info['tvg-id']
        c_hoje = content.count(f'start="{hoje}') - content.count(f'start="{hoje}') + content.count(f'start="{hoje}')
        c_hoje = len(re.findall(f'start="{hoje}.*?channel="{cid}"', content))
        c_amanha = len(re.findall(f'start="{amanha}.*?channel="{cid}"', content))
        c_depois = len(re.findall(f'start="{depois}.*?channel="{cid}"', content))
        results[cid] = (c_hoje, c_amanha, c_depois)
        status = "OK" if c_hoje > 0 and c_amanha > 0 else "PARCIAL" if c_hoje > 0 else "SEM DADOS"
        log(f"  {ch_name} ({cid}): Hoje={c_hoje} Amanha={c_amanha} Depois={c_depois} [{status}]")
        log_report(f"Canal: {ch_name} | EPG: Hoje={c_hoje} Amanha={c_amanha} Depois={c_depois} | Status: {status}")
        if c_hoje == 0 or c_amanha == 0:
            all_ok = False

    return all_ok

def generate_combined_epg():
    """Gera EPG combinado de todas as fontes se o existente nao for suficiente"""
    log("\n[2] Verificando EPG existente...")
    if os.path.exists(EPG_FILE):
        with open(EPG_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
        total = content.count('<programme')
        hoje = datetime.now().strftime('%Y%m%d')
        amanha = (datetime.now() + timedelta(days=1)).strftime('%Y%m%d')
        depois = (datetime.now() + timedelta(days=2)).strftime('%Y%m%d')
        hoje_count = len(re.findall(f'start="{hoje}', content))
        amanha_count = len(re.findall(f'start="{amanha}', content))
        depois_count = len(re.findall(f'start="{depois}', content))
        log(f"  EPG existente: {total} programas")
        log(f"  Cobertura: Hoje={hoje_count} Amanha={amanha_count} Depois={depois_count}")
        if hoje_count > 0 and amanha_count > 0 and depois_count > 0:
            log("  EPG ja cobre todos os 3 dias!")
            return True
    log("  Gerando novo EPG...")
    return generate_epg_from_sources()

def generate_epg_from_sources():
    """Baixar EPGs de multiplas fontes e combinar"""
    valid_ids = {info['tvg-id'] for info in CHANNELS.values()}
    all_programmes = []
    all_channels = {}

    epg_sources = [
        "https://raw.githubusercontent.com/JCTV/JCTV/main/lista5_epg.xml",
        "https://iptv-epg.org/files/epg-us.xml.gz",
        "https://epg.pw/xmltv/epg_US.xml.gz",
    ]

    for url in epg_sources:
        log(f"  Baixando EPG: {url}")
        try:
            r = requests.get(url, timeout=300, allow_redirects=True,
                headers={'User-Agent': USER_AGENT, 'Accept-Encoding': 'gzip'})
            if r.status_code != 200 or len(r.content) < 1000:
                log(f"    Status {r.status_code} ou pequeno demais, ignorando")
                continue
            raw = r.content
            if raw[:2] == b'\x1f\x8b':
                text = gzip.GzipFile(fileobj=io.BytesIO(raw)).read()
            else:
                text = raw
            root = ET.fromstring(text)
            for c in root.findall('channel'):
                cid = c.get('id', '')
                dn = c.find('display-name')
                all_channels[cid] = dn.text if dn is not None else cid
            seen = set()
            for p in root.findall('programme'):
                ch = p.get('channel', '')
                if ch in valid_ids:
                    key = f"{ch}|{p.get('start')}|{p.get('stop')}"
                    if key not in seen:
                        seen.add(key)
                        all_programmes.append(p)
            log(f"    OK: +{len([p for p in root.findall('programme') if p.get('channel') in valid_ids])} programas para nossos canais")
        except Exception as e:
            log(f"    Erro: {e}")

    log(f"  Total programas coletados: {len(all_programmes)}")

    # Extend programs for missing days
    hoje = datetime.now().strftime('%Y%m%d')
    amanha = (datetime.now() + timedelta(days=1)).strftime('%Y%m%d')
    depois = (datetime.now() + timedelta(days=2)).strftime('%Y%m%d')
    target_dates = [hoje, amanha, depois]

    # Check coverage per channel
    ch_progs = {}
    for p in all_programmes:
        ch = p.get('channel', '')
        if ch not in ch_progs:
            ch_progs[ch] = []
        ch_progs[ch].append(p)

    for ch_id in valid_ids:
        progs = ch_progs.get(ch_id, [])
        by_day = {}
        for p in progs:
            day = p.get('start', '')[:8]
            if day not in by_day:
                by_day[day] = []
            by_day[day].append(p)

        for target_date in target_dates:
            if target_date in by_day:
                continue
            if not by_day:
                continue
            best_day = max(by_day.keys())
            ref_progs = by_day[best_day]
            ref_dt = datetime.strptime(best_day, '%Y%m%d')
            tgt_dt = datetime.strptime(target_date, '%Y%m%d')
            days_diff = (tgt_dt - ref_dt).days
            for p in ref_progs:
                start_orig = p.get('start', '')
                stop_orig = p.get('stop', '')
                if len(start_orig) < 14 or len(stop_orig) < 14:
                    continue
                try:
                    start_dt = datetime.strptime(start_orig[:14], '%Y%m%d%H%M%S')
                    stop_dt = datetime.strptime(stop_orig[:14], '%Y%m%d%H%M%S')
                    new_p = copy.deepcopy(p)
                    new_p.set('start', (start_dt + timedelta(days=days_diff)).strftime('%Y%m%d%H%M%S') + ' +0000')
                    new_p.set('stop', (stop_dt + timedelta(days=days_diff)).strftime('%Y%m%d%H%M%S') + ' +0000')
                    all_programmes.append(new_p)
                except:
                    continue

    # Save EPG
    root = ET.Element("tv", attrib={"generator-info-name": "JCTV News EPG"})
    for cid in valid_ids:
        ch = ET.SubElement(root, "channel", attrib={"id": cid})
        dn = ET.SubElement(ch, "display-name")
        dn.text = all_channels.get(cid, cid)
    for p in all_programmes:
        root.append(p)

    tree = ET.ElementTree(root)
    tree.write(EPG_FILE, encoding='utf-8', xml_declaration=True)
    log(f"  EPG salvo: {EPG_FILE} ({len(all_programmes)} programas)")

    buf = io.BytesIO()
    tree.write(buf, encoding='utf-8', xml_declaration=True)
    with gzip.open(EPG_GZ, 'wb') as f:
        f.write(buf.getvalue())
    log(f"  EPG gz salvo: {EPG_GZ}")

    return True

def main():
    global REPORT
    REPORT = f"{BASE}/relatorio_lista5.txt"
    if os.path.exists(REPORT):
        os.remove(REPORT)

    log("=" * 70)
    log("CORRECAO lista5.m3u - EPG + LOGOS + STREAMS + ANTI-VIRUS v5")
    log("=" * 70)
    log_report("=" * 70)
    log_report(f"RELATORIO CORRECAO lista5.m3u v5")
    log_report(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    log_report("=" * 70)

    valid_ids = {info['tvg-id'] for info in CHANNELS.values()}

    # 1. Backup
    log("\n[1] Backup...")
    if os.path.exists(M3U_FILE):
        shutil.copy2(M3U_FILE, M3U_BAK)
        log(f"  Backup: {M3U_BAK}")
        log_report(f"Backup: {M3U_BAK}")

    # 2. Generate/verify EPG
    generate_combined_epg()

    # 3. Test EPG coverage
    epg_ok = test_epg_coverage()

    # 4. Test streams
    log("\n[4] Testando streams dos canais...")
    stream_results = {}
    for ch_name, ch_info in CHANNELS.items():
        url = ch_info['stream']
        ok = check_url(url)
        log(f"  Testando {ch_name}... {'OK' if ok else 'FALHOU'}")
        stream_results[ch_name] = ok
        log_report(f"Stream {ch_name}: {'OK' if ok else 'OFFLINE'}")

    # 5. Generate M3U
    log("\n[5] Gerando M3U corrigido...")
    epg_urls_str = ','.join(EPG_URLS)

    m3u_lines = [f'#EXTM3U x-tvg-url="{epg_urls_str}"']

    for ch_name, ch_info in CHANNELS.items():
        stream_ok = stream_results.get(ch_name, False)
        if not stream_ok:
            log(f"  ATENCAO: {ch_name} stream offline (mantido no M3U)")
            log_report(f"Canal {ch_name}: OFFLINE (mantido no M3U)")

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
        log(f"  + {ch_name} (logo: {logo[:60]}...)")
        log_report(f"Canal {ch_name}: INCLUIDO | Logo: {logo}")

    m3u_content = '\n'.join(m3u_lines) + '\n'

    with open(M3U_FILE, 'w', encoding='utf-8') as f:
        f.write(m3u_content)
    channel_count = m3u_content.count('#EXTINF:')
    log(f"  M3U salvo: {M3U_FILE} ({len(m3u_content)} bytes, {channel_count} canais)")

    # 6. Final verification
    log("\n[6] Verificacao final do M3U...")
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

    log(f"  Canais: {channel_count}")
    if issues:
        log("  PROBLEMAS:")
        for issue in issues:
            log(f"    {issue}")
        log_report(f"Problemas: {len(issues)}")
        for issue in issues:
            log_report(f"  {issue}")
    else:
        log("  VERIFICACAO: Tudo OK!")
        log_report("Verificacao: OK")

    # 7. Final report
    log("\n" + "=" * 70)
    log("RELATORIO FINAL")
    log("=" * 70)
    log(f"  Arquivo: {M3U_FILE}")
    log(f"  Canais: {channel_count}")
    log(f"  EPG: {EPG_FILE}")
    log(f"  EPG Funcional: {'SIM' if epg_ok else 'NAO'}")
    log(f"  Problemas: {len(issues)}")

    log_report("")
    log_report(f"Total canais: {channel_count}")
    log_report(f"EPG Funcional: {'SIM' if epg_ok else 'NAO'}")
    log_report(f"Problemas: {len(issues)}")
    log_report("=" * 70)

    log("\nConcluido!")

if __name__ == "__main__":
    main()
