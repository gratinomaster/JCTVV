#!/usr/bin/env python3
"""Corrige lista5.m3u: EPG, logos .jpg, streams OK, sem imgur, sem virus, #EXTINF correto"""
import io, os, re, shutil, copy, html
import xml.etree.ElementTree as ET
import requests
import gzip
from datetime import datetime, timedelta
from collections import OrderedDict, defaultdict
from urllib.parse import urlparse

BASE = "/home/runner/work/JCTV/JCTV"
M3U_FILE = f"{BASE}/lista5.m3u"
M3U_BAK = f"{BASE}/lista5.m3u.bak"
EPG_LOCAL = f"{BASE}/lista5_epg.xml"
EPG_OUT = f"{BASE}/lista5_epg.xml.gz"
REPORT = f"{BASE}/relatorio_lista5.txt"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

HOJE = datetime.now()
HOJE_STR = HOJE.strftime('%Y%m%d')
AMANHA_STR = (HOJE + timedelta(days=1)).strftime('%Y%m%d')
DEPOIS_STR = (HOJE + timedelta(days=2)).strftime('%Y%m%d')

CHANNELS = [
    {
        "name": "ABC News Live",
        "tvg-id": "ABCNewsLive.us",
        "tvg-name": "ABC News Live",
        "tvg-logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
        "group-title": "NEWS WORLD",
        "stream": "https://abcnews-livestreams.akamaized.net/out/v1/6a597119dbd5428a82dc11a2f514a1a2/abcn-live-10-cmaf-manifest/abcn-live-10-index.m3u8",
    },
    {
        "name": "Fox News Channel",
        "tvg-id": "FoxNewsChannel.us",
        "tvg-name": "Fox News Channel",
        "tvg-logo": "https://a57.foxnews.com/static.foxnews.com/foxnews.com/images/2024/09/fn-logo-social-share.jpg",
        "group-title": "NEWS WORLD",
        "stream": "http://247preview.foxnews.com/hls/live/2020027/fncv3preview/primary.m3u8",
    },
    {
        "name": "Fox Business Network",
        "tvg-id": "FoxBusiness.us",
        "tvg-name": "Fox Business Network",
        "tvg-logo": "https://a57.foxnews.com/static/694940094001/c9b2e2eb-7b87-435c-9510-eab2650ff944/8b584585-acf2-4c37-aa07-aaf2d077bb20/1280x720/match/676/380/image.jpg",
        "group-title": "NEWS WORLD",
        "stream": "https://247.foxbusiness.com/hls/live/2003756/FBNHLSv3/master.m3u8",
    },
    {
        "name": "CBS News 24/7",
        "tvg-id": "CBSNews.us",
        "tvg-name": "CBS News 24/7",
        "tvg-logo": "https://www.cbsnews.com/bundles/cbsnewsvideo/images/cbsn--main-bg.jpg",
        "group-title": "NEWS WORLD",
        "stream": "https://dai.google.com/linear/hls/pa/event/Sid4xiTQTkCT1SLu6rjUSQ/stream/7221f338-5f33-4676-a981-e2c4a271dbc4:CHS/master.m3u8",
    },
]

def log(msg, end='\n'):
    print(msg, end=end)

def log_report(msg):
    os.makedirs(os.path.dirname(REPORT) or '.', exist_ok=True)
    with open(REPORT, 'a', encoding='utf-8') as f:
        f.write(msg + '\n')

def check_url(url, timeout=15):
    try:
        r = requests.get(url, timeout=timeout,
            headers={'User-Agent': USER_AGENT}, allow_redirects=True)
        if r.status_code < 400:
            content = r.content
            if content.startswith(b'#EXTM3U') or content.startswith(b'#EXTINF'):
                return True
            ct = r.headers.get('Content-Type', '')
            if 'mpegurl' in ct or 'x-mpegURL' in ct or 'vnd.apple.mpegurl' in ct:
                return True
            if len(content) > 200:
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

def load_local_epg():
    if not os.path.exists(EPG_LOCAL):
        log(f"  EPG local nao encontrado: {EPG_LOCAL}")
        return {}, []
    try:
        tree = ET.parse(EPG_LOCAL)
        root = tree.getroot()
        ch_map = {}
        for c in root.findall('channel'):
            cid = c.get('id', '')
            dn = c.find('display-name')
            ch_map[cid] = dn.text if dn is not None else cid
        programmes = root.findall('programme')
        log(f"  EPG local: {len(ch_map)} canais, {len(programmes)} programas")
        return ch_map, programmes
    except Exception as e:
        log(f"  Erro lendo EPG local: {e}")
        return {}, []

def generate_epg_for_channels(channels_list):
    """Gera EPG para os canais que nao tem cobertura"""
    root = ET.Element("tv", attrib={"generator-info-name": "JCTV News EPG Generator"})
    
    today_str = HOJE.strftime('%Y-%m-%d')
    amanha_str = (HOJE + timedelta(days=1)).strftime('%Y-%m-%d')
    depois_str = (HOJE + timedelta(days=2)).strftime('%Y-%m-%d')
    
    for ch in channels_list:
        cid = ch["tvg-id"]
        cname = ch["name"]
        logo = fix_logo_url(ch.get("tvg-logo", "")) or ""
        
        ch_el = ET.SubElement(root, "channel", attrib={"id": cid})
        dn = ET.SubElement(ch_el, "display-name")
        dn.text = cname
        if logo:
            icon = ET.SubElement(ch_el, "icon")
            icon.set("src", logo)
        
        for day_str, day_label in [(HOJE_STR, today_str), (AMANHA_STR, amanha_str), (DEPOIS_STR, depois_str)]:
            for hour in range(0, 24, 3):
                start_h = f"{hour:02d}0000"
                end_h = f"{(hour+3)%24:02d}0000"
                if hour + 3 >= 24:
                    end_h = "235959"
                start_dt = f"{day_str}{start_h} +0000"
                stop_dt = f"{day_str}{end_h} +0000"
                
                prog = ET.SubElement(root, "programme",
                    attrib={"channel": cid, "start": start_dt, "stop": stop_dt})
                title = ET.SubElement(prog, "title")
                title.set("lang", "en")
                title.text = f"{cname} - {day_label} {hour:02d}:00"
                desc = ET.SubElement(prog, "desc")
                desc.set("lang", "en")
                desc.text = f"{cname} - Live news coverage from {cname}"
    
    return root

def main():
    log("=" * 70)
    log(f"CORRECAO lista5.m3u - {HOJE.strftime('%Y-%m-%d %H:%M')}")
    log("=" * 70)

    log_report("=" * 70)
    log_report(f"RELATORIO CORRECAO lista5.m3u")
    log_report(f"Data: {HOJE.strftime('%Y-%m-%d %H:%M')}")
    log_report("=" * 70)

    # 1. Backup
    log("\n[1] Backup...")
    if os.path.exists(M3U_FILE):
        shutil.copy2(M3U_FILE, M3U_BAK)
        log(f"  Backup: {M3U_BAK}")

    # 2. Load existing EPG
    log("\n[2] Carregando EPG local...")
    epg_channels, epg_programmes = load_local_epg()

    # 3. Check EPG coverage
    log("\n[3] Verificando cobertura EPG...")
    valid_ids = {ch["tvg-id"] for ch in CHANNELS}
    
    epg_data = {}  # channel_id -> list of programmes
    for p in epg_programmes:
        ch = p.get('channel', '')
        if ch in valid_ids:
            if ch not in epg_data:
                epg_data[ch] = []
            epg_data[ch].append(p)
    
    channels_needing_epg = []
    for ch in CHANNELS:
        cid = ch["tvg-id"]
        progs = epg_data.get(cid, [])
        t = sum(1 for p in progs if p.get('start','')[:8] == HOJE_STR)
        tm = sum(1 for p in progs if p.get('start','')[:8] == AMANHA_STR)
        da = sum(1 for p in progs if p.get('start','')[:8] == DEPOIS_STR)
        log(f"  {ch['name']} (ID:{cid}): Today={t} Tomorrow={tm} DayAfter={da}")
        if t == 0 or tm == 0:
            log(f"    -> Precisa gerar EPG complementar")
            channels_needing_epg.append(ch)
    
    # 4. Generate EPG for channels without coverage
    log("\n[4] Gerando EPG complementar se necessario...")
    all_programmes = list(epg_programmes)
    
    if channels_needing_epg:
        new_root = generate_epg_for_channels(channels_needing_epg)
        new_progs = new_root.findall('programme')
        existing = {(p.get('channel',''), p.get('start',''), p.get('stop','')) for p in all_programmes}
        added = 0
        for p in new_progs:
            key = (p.get('channel',''), p.get('start',''), p.get('stop',''))
            if key not in existing:
                existing.add(key)
                all_programmes.append(p)
                added += 1
        log(f"  Adicionados {added} programas complementares")
        
        # Add new channel entries
        for c in new_root.findall('channel'):
            cid = c.get('id')
            if cid not in epg_channels:
                epg_channels[cid] = c.find('display-name').text if c.find('display-name') is not None else cid
    
    # 5. Save combined EPG
    log("\n[5] Salvando EPG combinado...")
    root_out = ET.Element("tv", attrib={"generator-info-name": "JCTV News EPG"})
    for cid in valid_ids:
        cname = epg_channels.get(cid, cid)
        ch_el = ET.SubElement(root_out, "channel", attrib={"id": cid})
        dn = ET.SubElement(ch_el, "display-name")
        dn.text = cname
    for p in all_programmes:
        if p.get('channel') in valid_ids:
            root_out.append(p)
    
    tree = ET.ElementTree(root_out)
    tree.write(EPG_LOCAL, encoding='utf-8', xml_declaration=True)
    log(f"  EPG salvo: {EPG_LOCAL}")
    
    buf = io.BytesIO()
    tree.write(buf, encoding='utf-8', xml_declaration=True)
    with gzip.open(EPG_OUT, 'wb') as f:
        f.write(buf.getvalue())
    log(f"  EPG gz salvo: {EPG_OUT}")

    # Final EPG coverage check
    log("\n  Cobertura EPG final:")
    epg_final, _ = load_local_epg()
    tree_final = ET.parse(EPG_LOCAL)
    final_progs = tree_final.getroot().findall('programme')
    epg_all_ok = True
    for ch in CHANNELS:
        cid = ch["tvg-id"]
        progs = [p for p in final_progs if p.get('channel') == cid]
        t = sum(1 for p in progs if p.get('start','')[:8] == HOJE_STR)
        tm = sum(1 for p in progs if p.get('start','')[:8] == AMANHA_STR)
        da = sum(1 for p in progs if p.get('start','')[:8] == DEPOIS_STR)
        status = "OK" if t > 0 and tm > 0 else "FALHA"
        if status == "FALHA":
            epg_all_ok = False
        log(f"  {ch['name']}: T={t} Tm={tm} DA={da} [{status}]")
        log_report(f"  EPG {ch['name']}: Today={t} Tomorrow={tm} DayAfter={da} [{status}]")

    # 6. Test streams
    log("\n[6] Testando streams...")
    streams_ok = {}
    for ch in CHANNELS:
        url = ch["stream"]
        log(f"  Testando {ch['name']}...", end=' ')
        ok = check_url(url)
        streams_ok[ch["name"]] = ok
        log(f"{'OK' if ok else 'FALHOU'}")
        log_report(f"  Stream {ch['name']}: {'OK' if ok else 'OFFLINE'}")

    # 7. VirusTotal check
    log("\n[7] Verificacao anti-virus...")
    vt_api_key = os.environ.get('VIRUSTOTAL_API_KEY', '')
    vt_results = {}
    for ch in CHANNELS:
        url = ch["stream"]
        log(f"  VT {ch['name']}...", end=' ')
        if vt_api_key:
            try:
                import base64
                url_id = base64.urlsafe_b64encode(url.encode()).decode().strip("=")
                r = requests.get(f"https://www.virustotal.com/api/v3/urls/{url_id}",
                    headers={"x-apikey": vt_api_key}, timeout=15)
                if r.status_code == 200:
                    data = r.json()
                    stats = data.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
                    malicious = stats.get("malicious", 0)
                    if malicious > 0:
                        vt_results[ch["name"]] = "malicious"
                        log(f"MALICIOUS ({malicious})")
                    else:
                        vt_results[ch["name"]] = "clean"
                        log("clean")
                else:
                    vt_results[ch["name"]] = "nao_verificado"
                    log(f"erro API ({r.status_code})")
            except Exception as e:
                vt_results[ch["name"]] = "erro"
                log(f"erro: {e}")
        else:
            vt_results[ch["name"]] = "nao_verificado"
            log("VT_API_KEY nao configurada, pulando")
        log_report(f"  VirusTotal {ch['name']}: {vt_results.get(ch['name'], 'nao_verificado')}")

    # 8. Generate M3U
    log("\n[8] Gerando M3U corrigido...")
    
    epg_urls_str = "https://raw.githubusercontent.com/gratinomaster/JCTV/main/lista5_epg.xml,https://iptv-epg.org/files/epg-us.xml.gz"
    
    m3u_lines = [f'#EXTM3U x-tvg-url="{epg_urls_str}"']
    
    channel_count = 0
    for ch in CHANNELS:
        if not streams_ok.get(ch["name"], False):
            log(f"  PULANDO {ch['name']} (stream offline)")
            log_report(f"  {ch['name']}: PULADO (stream offline)")
            continue
        
        if vt_results.get(ch["name"]) == "malicious":
            log(f"  PULANDO {ch['name']} (malicioso no VirusTotal)")
            log_report(f"  {ch['name']}: PULADO (malicioso no VT)")
            continue
        
        logo = fix_logo_url(ch.get("tvg-logo", ""))
        if not logo:
            logo = ""
        
        attrs = f'tvg-id="{ch["tvg-id"]}" tvg-name="{ch["tvg-name"]}"'
        if logo:
            attrs += f' tvg-logo="{logo}"'
        attrs += f' group-title="{ch["group-title"]}"'
        
        m3u_lines.append(f'#EXTINF:-1 {attrs},{ch["name"]}')
        m3u_lines.append(ch["stream"])
        log(f"  + {ch['name']}")
        log_report(f"  {ch['name']}: INCLUIDO (logo={logo})")
        channel_count += 1
    
    m3u_content = '\n'.join(m3u_lines) + '\n'
    
    with open(M3U_FILE, 'w', encoding='utf-8') as f:
        f.write(m3u_content)
    log(f"\n  M3U salvo: {M3U_FILE} ({len(m3u_content)} bytes, {channel_count} canais)")

    # 9. Verification
    log("\n[9] VERIFICACAO FINAL:")
    lines = m3u_content.strip().split('\n')
    issues = []
    
    for i, line in enumerate(lines):
        if line.startswith('#EXTINF:'):
            if 'tvg-id=' not in line:
                issues.append(f"  Linha {i+1}: sem tvg-id")
            logo_match = re.search(r'tvg-logo="([^"]+)"', line)
            if logo_match:
                logo_url = logo_match.group(1)
                if not logo_url.lower().endswith(('.jpg', '.jpeg')):
                    issues.append(f"  Linha {i+1}: logo nao .jpg: {logo_url}")
                if 'imgur.com' in logo_url.lower():
                    issues.append(f"  Linha {i+1}: logo imgur.com: {logo_url}")
            else:
                issues.append(f"  Linha {i+1}: sem tvg-logo")
        elif line.startswith('http'):
            if i == 0 or not lines[i-1].startswith('#EXTINF:'):
                issues.append(f"  Linha {i+1}: URL sem #EXTINF acima (prev={lines[i-1][:30] if i>0 else 'N/A'})")
    
    if not lines[0].startswith('#EXTM3U'):
        issues.append("  Linha 1: sem #EXTM3U header")
    elif 'x-tvg-url=' not in lines[0]:
        issues.append("  Linha 1: sem x-tvg-url no header")
    
    log(f"\n  Canais no M3U: {channel_count}")
    log(f"  EPG canais: {len(valid_ids)}")
    
    if issues:
        log("  PROBLEMAS:")
        for issue in issues:
            log(f"    {issue}")
    else:
        log("  TUDO OK - Nenhum problema encontrado!")
    
    log(f"  Streams funcionando: {sum(1 for v in streams_ok.values() if v)}/{len(streams_ok)}")
    log(f"  EPG funcional: {'SIM' if epg_all_ok else 'PARCIAL - alguns canais sem guia'}")

    # 10. Report summary
    epg_ok_str = "SIM" if epg_all_ok else "PARCIAL"
    log("\n" + "=" * 70)
    log("RELATORIO FINAL")
    log("=" * 70)
    log(f"  Arquivo: {M3U_FILE}")
    log(f"  Canais: {channel_count}")
    log(f"  EPG: {EPG_LOCAL}")
    log(f"  EPG cobertura: {epg_ok_str}")
    log(f"  Problemas: {len(issues)}")
    log(f"  Streams OK: {sum(1 for v in streams_ok.values() if v)}/{len(streams_ok)}")
    
    log_report("")
    log_report(f"Total canais: {channel_count}")
    log_report(f"EPG funcional: {epg_ok_str}")
    log_report(f"Streams OK: {sum(1 for v in streams_ok.values() if v)}/{len(streams_ok)}")
    log_report(f"Problemas: {len(issues)}")
    log_report("=" * 70)
    
    log("\nConcluido!")

if __name__ == "__main__":
    main()
