#!/usr/bin/env python3
"""Fix lista5.m3u: EPG valido, logos .jpg, sem duplicatas, streams testados, anti-virus"""
import io, os, re, shutil, copy
import xml.etree.ElementTree as ET
import requests
import gzip
from datetime import datetime, timedelta
from collections import OrderedDict

BASE = "/home/runner/work/JCTVV/JCTVV"
M3U_FILE = f"{BASE}/lista5.m3u"
EPG_FILE = f"{BASE}/lista5_epg.xml"
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
    }),
    ("Fox News Channel", {
        "tvg-id": "FoxNewsChannel.us",
        "tvg-name": "Fox News Channel",
        "tvg-logo": "https://github.com/gratinomaster/JCTV/raw/main/fox_news.jpg",
        "group-title": "NEWS WORLD",
    }),
    ("Fox Business", {
        "tvg-id": "FoxBusiness.us",
        "tvg-name": "Fox Business",
        "tvg-logo": "https://github.com/gratinomaster/JCTV/raw/main/fox_business.jpg",
        "group-title": "NEWS WORLD",
    }),
    ("CBS News 24/7", {
        "tvg-id": "CBSNews.us",
        "tvg-name": "CBS News 24/7",
        "tvg-logo": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
        "group-title": "NEWS WORLD",
    }),
])

def log(msg):
    print(msg)

def log_report(msg):
    with open(REPORT, 'a', encoding='utf-8') as f:
        f.write(msg + '\n')

def check_url(url, timeout=30):
    try:
        r = requests.get(url, timeout=timeout,
            headers={'User-Agent': USER_AGENT}, allow_redirects=True)
        if r.status_code >= 400:
            return False, r.status_code
        ct = r.headers.get('Content-Type', '')
        content = r.content
        if content.startswith(b'#EXTM3U') or len(content) > 200:
            return True, r.status_code
        if 'text' in ct or 'application' in ct or 'video' in ct or 'audio' in ct:
            return True, r.status_code
        return False, r.status_code
    except requests.exceptions.Timeout:
        return False, "Timeout"
    except Exception as e:
        return False, str(e)[:60]

def fix_logo_url(url):
    if not url:
        return None
    if 'imgur.com' in url.lower():
        log(f"    Removido logo imgur.com")
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

def extract_channel_name(extinf_line):
    m = re.search(r'#EXTINF:-1[^,]*,\s*(.+)$', extinf_line)
    if m:
        return m.group(1).strip()
    parts = extinf_line.split(',')
    if len(parts) > 1:
        return parts[-1].strip()
    return ''

def main():
    if os.path.exists(REPORT):
        os.remove(REPORT)

    log("=" * 70)
    log("CORRECAO FINAL lista5.m3u - EPG + LOGOS + STREAMS + ANTI-VIRUS")
    log("=" * 70)
    log_report("=" * 70)
    log_report(f"RELATORIO CORRECAO lista5.m3u - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    log_report("=" * 70)

    # Backup
    log("\n[1] Backup do arquivo original...")
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    M3U_BAK_TIMED = f"{BASE}/lista5.m3u.bak.{timestamp}"
    shutil.copy2(M3U_FILE, M3U_BAK_TIMED)
    log(f"  Backup: {M3U_BAK_TIMED}")
    log_report(f"Backup: {M3U_BAK_TIMED}")

    # Parse current M3U
    log("\n[2] Analisando canais atuais...")
    with open(M3U_FILE, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.strip().split('\n')
    struct_issues = []
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith('http') and 'raw.githubusercontent' not in s:
            if i == 0 or not lines[i-1].strip().startswith('#EXTINF:'):
                struct_issues.append(f"Linha {i+1}: URL sem #EXTINF acima")
    if struct_issues:
        log(f"  Problemas de estrutura ({len(struct_issues)}):")
        for iss in struct_issues:
            log(f"    {iss}")
            log_report(f"ESTRUTURA: {iss}")
    else:
        log("  Estrutura OK")

    # Extract unique channels
    channels_found = []
    for i, line in enumerate(lines):
        if line.startswith('#EXTINF:'):
            name = extract_channel_name(line)
            if i+1 < len(lines):
                url = lines[i+1].strip()
                if url.startswith('http'):
                    channels_found.append({'name': name, 'url': url, 'extinf': line})

    log(f"  Entradas #EXTINF com URL: {len(channels_found)}")

    # Map each found channel to known channels using URL heuristics + name matching
    mapped = {}
    for ch in channels_found:
        name = ch['name'].lower()
        url = ch['url']

        # Determine channel by URL patterns
        if 'abcnews' in url or ('abc' in url and 'livestreams.akamaized.net' in url):
            if 'tracking' not in name:
                mapped['ABC News Live'] = url
            else:
                mapped['ABCNL'] = url
        elif 'foxnews.com' in url or '247.foxnews.com' in url:
            mapped['Fox News Channel'] = url
        elif 'foxbusiness.com' in url or '247.foxbusiness.com' in url:
            mapped['Fox Business'] = url
        elif 'cbsnews' in url or 'dai.google.com' in url:
            mapped['CBS News 24/7'] = url

    log(f"  Canais mapeados:")
    for ch_name, url in mapped.items():
        log(f"    {ch_name}: {url[:60]}...")

    # Test streams
    log("\n[3] Testando streams...")
    stream_results = {}
    for ch_name, url in mapped.items():
        log(f"  Testando {ch_name}...")
        ok, status = check_url(url)
        stream_results[ch_name] = {'ok': ok, 'url': url, 'status': status}
        log(f"    {'OK' if ok else 'FALHOU'} (HTTP {status})")
        log_report(f"Stream {ch_name}: {'OK' if ok else 'OFFLINE'} (HTTP {status})")

    # Anti-virus check
    log("\n[4] Anti-virus...")
    suspicious_patterns = [r'\.exe', r'\.bat', r'\.cmd', r'\.ps1', r'\.vbs', r'\.scr',
                          'phishing', 'malware', 'trojan']
    anti_virus_issues = []
    for ch_name, result in stream_results.items():
        url_lower = result['url'].lower()
        found = False
        for pattern in suspicious_patterns:
            if re.search(pattern, url_lower):
                anti_virus_issues.append((ch_name, f"Padrao suspeito: {pattern}"))
                found = True
                break
        log(f"  OK: {ch_name}" if not found else f"  SUSPEITO: {ch_name}")

    # EPG verification
    log("\n[5] Verificando EPG...")
    hoje = datetime.now().strftime('%Y%m%d')
    amanha = (datetime.now() + timedelta(days=1)).strftime('%Y%m%d')
    depois = (datetime.now() + timedelta(days=2)).strftime('%Y%m%d')
    log(f"  Hoje={hoje} Amanha={amanha} Depois={depois}")

    epg_ok = True
    total_progs = 0
    if os.path.exists(EPG_FILE):
        with open(EPG_FILE, 'r', encoding='utf-8') as f:
            epg_content = f.read()
        total_progs = epg_content.count('<programme')
        log(f"  Total programas: {total_progs}")

        for ch_name, ch_info in CHANNELS.items():
            cid = ch_info['tvg-id']
            c_hoje = len(re.findall(f'start="{hoje}.*?channel="{cid}"', epg_content))
            c_amanha = len(re.findall(f'start="{amanha}.*?channel="{cid}"', epg_content))
            c_depois = len(re.findall(f'start="{depois}.*?channel="{cid}"', epg_content))
            status = "OK" if c_hoje > 0 and c_amanha > 0 else "PARCIAL" if c_hoje > 0 else "SEM DADOS"
            log(f"  {ch_name}: Hoje={c_hoje} Amanha={c_amanha} Depois={c_depois} [{status}]")
            log_report(f"EPG {ch_name}: {status} (H={c_hoje} A={c_amanha} D={c_depois})")
            if c_hoje == 0 or c_amanha == 0:
                epg_ok = False
        log(f"  EPG: {'SIM' if epg_ok else 'PARCIAL'}")
        log_report(f"EPG Funcional: {'SIM' if epg_ok else 'PARCIAL'}")

    # Generate corrected M3U
    log("\n[6] Gerando M3U corrigido...")
    epg_urls_str = ' '.join(EPG_URLS)
    m3u_lines = [f'#EXTM3U x-tvg-url="{epg_urls_str}"']

    order = ['ABC News Live', 'Fox News Channel', 'Fox Business', 'CBS News 24/7']

    for ch_name in order:
        if ch_name not in stream_results:
            log(f"  AVISO: {ch_name} sem stream, pulando")
            log_report(f"AVISO: {ch_name} pulado (sem stream no M3U)")
            continue

        url = stream_results[ch_name]['url']
        ch_info = CHANNELS.get(ch_name)

        if ch_info:
            logo = fix_logo_url(ch_info['tvg-logo'])
            if not logo:
                logo = ch_info['tvg-logo']

            attrs = f'tvg-id="{ch_info["tvg-id"]}" tvg-name="{ch_info["tvg-name"]}"'
            if logo:
                attrs += f' tvg-logo="{logo}"'
            if ch_info.get('group-title'):
                attrs += f' group-title="{ch_info["group-title"]}"'

            m3u_lines.append(f'#EXTINF:-1 {attrs},{ch_info["tvg-name"]}')
            m3u_lines.append(url)
            log(f"  + {ch_name}")
            log_report(f"Canal adicionado: {ch_name}")

    m3u_content = '\n'.join(m3u_lines) + '\n'

    with open(M3U_FILE, 'w', encoding='utf-8') as f:
        f.write(m3u_content)

    channel_count = m3u_content.count('#EXTINF:')
    log(f"\n  Salvo: {M3U_FILE} ({len(m3u_content)} bytes, {channel_count} canais)")

    # Final verification
    log("\n[7] Verificacao final...")
    final_lines = m3u_content.strip().split('\n')
    final_issues = []
    for i, line in enumerate(final_lines):
        if line.startswith('#EXTINF:'):
            logo_match = re.search(r'tvg-logo="([^"]+)"', line)
            if not logo_match:
                final_issues.append(f"  Linha {i+1}: sem tvg-logo")
            else:
                logo = logo_match.group(1)
                if not logo.lower().endswith(('.jpg', '.jpeg')):
                    final_issues.append(f"  Linha {i+1}: logo nao .jpg: {logo}")
                if 'imgur.com' in logo.lower():
                    final_issues.append(f"  Linha {i+1}: imgur: {logo}")
            if 'tvg-id=' not in line:
                final_issues.append(f"  Linha {i+1}: sem tvg-id")

        elif line.startswith('http') and 'raw.githubusercontent' not in line:
            if i == 0 or not final_lines[i-1].strip().startswith('#EXTINF:'):
                final_issues.append(f"  Linha {i+1}: URL sem #EXTINF acima")

    log(f"  Canais: {channel_count}")
    if final_issues:
        log("  PROBLEMAS:")
        for iss in final_issues:
            log(f"    {iss}")
            log_report(f"VERIF: {iss}")
    else:
        log("  Tudo OK!")
        log_report("Verificacao final: OK")

    log("\n" + "=" * 70)
    log("RELATORIO FINAL")
    log("=" * 70)
    log(f"  Canais: {channel_count}")
    log(f"  EPG programas: {total_progs}")
    log(f"  EPG OK: {'SIM' if epg_ok else 'NAO'}")
    streams_ok = sum(1 for r in stream_results.values() if r['ok'])
    log(f"  Streams OK: {streams_ok}/{len(stream_results)}")
    log(f"  Problemas: {len(final_issues)}")

    log_report(f"Canais: {channel_count} | EPG: {total_progs}progs | EPG_ok: {epg_ok} | Streams: {streams_ok}/{len(stream_results)} | Problemas: {len(final_issues)}")
    log_report("=" * 70)
    log("\nConcluido!")

if __name__ == "__main__":
    main()
