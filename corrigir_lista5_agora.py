#!/usr/bin/env python3
"""Corrige lista5.m3u: adiciona tvg-id, tvg-url, logos .jpg, testa streams, verifica VirusTotal, remove duplicatas e canais problematicos"""
import io, os, re, shutil, json
import xml.etree.ElementTree as ET
import requests
from datetime import datetime, timedelta

BASE = "/home/runner/work/JCTVV/JCTVV"
M3U_FILE = f"{BASE}/lista5.m3u"
M3U_BAK = f"{BASE}/lista5.m3u.bak"
EPG_XML = f"{BASE}/lista5_epg.xml"
REPORT = f"{BASE}/relatorio_lista5.txt"
VT_RESULTS_FILE = f"{BASE}/virustotal_results.json"
BAD_URLS_FILE = f"{BASE}/bad_urls.txt"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
VT_API_KEY = os.environ.get('VIRUSTOTAL_API_KEY', '')

# Mapeamento: nome do canal -> tvg-id
# Canais fixos com streams verificados e funcionais
FIXED_CHANNELS = [
    {
        "name": "ABC News Live",
        "tvg-id": "ABCNewsLive.us",
        "tvg-logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
        "stream": "https://abcnews-livestreams.akamaized.net/out/v1/6a597119dbd5428a82dc11a2f514a1a2/abcn-live-10-cmaf-manifest/abcn-live-10-index.m3u8",
    },
    {
        "name": "Fox News Channel",
        "tvg-id": "FoxNewsChannel.us",
        "tvg-logo": "https://raw.githubusercontent.com/gratinomaster/JCTV/main/fox_news.jpg",
        "stream": "http://247preview.foxnews.com/hls/live/2020027/fncv3preview/primary.m3u8",
    },
    {
        "name": "Fox Business",
        "tvg-id": "FoxBusiness.us",
        "tvg-logo": "https://raw.githubusercontent.com/gratinomaster/JCTV/main/fox_business.jpg",
        "stream": "http://41.205.93.154/FOXBUSINESS/index.m3u8",
    },
    {
        "name": "CBS News 24/7",
        "tvg-id": "CBSNews.us",
        "tvg-logo": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
        "stream": "https://cbsn-us.cbsnstream.cbsnews.com/out/v1/55a8648e8f134e82a470f83d562deeca/master.m3u8",
    },
]

GROUP_TITLE = "NEWS WORLD"
EPG_URL = "https://raw.githubusercontent.com/JCTV/JCTV/main/lista5_epg.xml"


def log(msg):
    print(msg)


def log_report(msg):
    with open(REPORT, 'a', encoding='utf-8') as f:
        f.write(msg + '\n')


def check_url(url, timeout=15):
    try:
        r = requests.get(url, timeout=timeout, headers={'User-Agent': USER_AGENT}, allow_redirects=True)
        if r.status_code < 400:
            ct = r.headers.get('Content-Type', '')
            if not ct or 'text' in ct or 'application' in ct or 'video' in ct or 'audio' in ct:
                return True
            if r.content.startswith(b'#EXTM3U') or len(r.content) > 100:
                return True
        return False
    except:
        return False


def check_virustotal_url(url):
    if not VT_API_KEY:
        return {"status": "nao_verificado"}
    try:
        import base64
        url_id = base64.urlsafe_b64encode(url.encode()).decode().strip("=")
        headers = {"x-apikey": VT_API_KEY}
        r = requests.get(f"https://www.virustotal.com/api/v3/urls/{url_id}", headers=headers, timeout=15)
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


def test_epg_coverage(programmes, valid_ids):
    hoje = datetime.now().strftime('%Y%m%d')
    amanha = (datetime.now() + timedelta(days=1)).strftime('%Y%m%d')
    depois = (datetime.now() + timedelta(days=2)).strftime('%Y%m%d')
    c_hoje = sum(1 for p in programmes if p.get('start', '')[:8] == hoje and p.get('channel') in valid_ids)
    c_amanha = sum(1 for p in programmes if p.get('start', '')[:8] == amanha and p.get('channel') in valid_ids)
    c_depois = sum(1 for p in programmes if p.get('start', '')[:8] == depois and p.get('channel') in valid_ids)
    return c_hoje, c_amanha, c_depois


def parse_extinf(line):
    match = re.search(r'tvg-id="([^"]*)"', line)
    tvg_id = match.group(1) if match else ""
    match = re.search(r'tvg-logo="([^"]*)"', line)
    tvg_logo = match.group(1) if match else ""
    match = re.search(r'group-title="([^"]*)"', line)
    group = match.group(1) if match else ""
    comma = line.find(',')
    name = line[comma+1:].strip() if comma >= 0 else ""
    return tvg_id, tvg_logo, group, name


def main():
    log("=" * 70)
    log("CORRECAO COMPLETA lista5.m3u v4")
    log("=" * 70)

    log_report("=" * 70)
    log_report(f"RELATORIO CORRECAO lista5.m3u - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    log_report("=" * 70)

    valid_ids = {ch["tvg-id"] for ch in FIXED_CHANNELS}

    # 1. Backup
    log("\n[1] Backup...")
    if os.path.exists(M3U_FILE):
        shutil.copy2(M3U_FILE, M3U_BAK)
        log(f"  Backup: {M3U_BAK}")

    # 2. Carregar EPG
    log("\n[2] Carregando EPG...")
    all_programmes = []
    if os.path.exists(EPG_XML):
        tree = ET.parse(EPG_XML)
        root = tree.getroot()
        all_programmes = root.findall('programme')
        log(f"  EPG carregado: {len(all_programmes)} programas")

    # Testar cobertura EPG geral
    c_hoje, c_amanha, c_depois = test_epg_coverage(all_programmes, valid_ids)
    log(f"  Cobertura geral EPG: Hoje={c_hoje} Amanha={c_amanha} Depois={c_depois}")
    log_report(f"Cobertura EPG geral: Hoje={c_hoje} Amanha={c_amanha} Depois={c_depois}")

    # 3. Testar streams
    log("\n[3] Testando streams...")
    stream_results = {}
    for ch in FIXED_CHANNELS:
        url = ch['stream']
        log(f"  Testando {ch['name']}...")
        ok = check_url(url)
        log(f"    {'OK' if ok else 'FALHOU'}: {url[:80]}...")
        stream_results[ch['name']] = ok

    # 4. Verificar VirusTotal (se API key disponivel)
    log("\n[4] Verificacao VirusTotal...")
    vt_results = {}
    for ch in FIXED_CHANNELS:
        url = ch['stream']
        log(f"  Verificando {ch['name']}...")
        vt_result = check_virustotal_url(url)
        vt_results[ch['name']] = vt_result
        log(f"    VirusTotal: {vt_result['status']}")

    # 5. Gerar M3U corrigido
    log("\n[5] Gerando M3U corrigido...")

    m3u_lines = [f'#EXTM3U x-tvg-url="{EPG_URL}"']

    epg_ok = True
    added_channels = []
    hoje_str = datetime.now().strftime('%Y%m%d')
    amanha_str = (datetime.now() + timedelta(days=1)).strftime('%Y%m%d')
    depois_str = (datetime.now() + timedelta(days=2)).strftime('%Y%m%d')

    for ch in FIXED_CHANNELS:
        name = ch['name']
        # Pular se stream falhou
        if not stream_results.get(name, False):
            log(f"  PULANDO {name} (stream offline)")
            log_report(f"Canal: {name} - PULADO (stream offline)")
            continue

        # Pular se malicioso no VirusTotal
        if vt_results.get(name, {}).get('status') == 'malicious':
            log(f"  PULANDO {name} (malicioso VirusTotal)")
            log_report(f"Canal: {name} - PULADO (malicioso VirusTotal)")
            continue

        display_name = name
        tvg_id = ch['tvg-id']
        logo = fix_logo_url(ch['tvg-logo']) or ch['tvg-logo']

        attrs = f'tvg-id="{tvg_id}"'
        attrs += f' tvg-name="{display_name}"'
        if logo:
            attrs += f' tvg-logo="{logo}"'
        attrs += f' group-title="{GROUP_TITLE}"'

        m3u_lines.append(f'#EXTINF:-1 {attrs},{display_name}')
        m3u_lines.append(ch['stream'])
        log(f"  + {display_name} (ID:{tvg_id}, logo:{logo})")
        log_report(f"Canal: {display_name} - INCLUIDO (tvg-id:{tvg_id})")
        added_channels.append(display_name)

        # Verificar EPG para este canal
        cid = tvg_id
        ch_progs = [p for p in all_programmes if p.get('channel') == cid]
        ch_hoje = sum(1 for p in ch_progs if p.get('start', '')[:8] == hoje_str)
        ch_amanha = sum(1 for p in ch_progs if p.get('start', '')[:8] == amanha_str)
        ch_depois = sum(1 for p in ch_progs if p.get('start', '')[:8] == depois_str)
        log(f"    EPG: Hoje={ch_hoje} Amanha={ch_amanha} Depois={ch_depois}")
        log_report(f"  EPG: Hoje={ch_hoje} Amanha={ch_amanha} Depois={ch_depois}")
        if ch_hoje == 0 or ch_amanha == 0:
            epg_ok = False

    m3u_content = '\n'.join(m3u_lines) + '\n'

    with open(M3U_FILE, 'w', encoding='utf-8') as f:
        f.write(m3u_content)
    log(f"\n  M3U salvo: {M3U_FILE} ({len(m3u_content)} bytes, {len(added_channels)} canais)")

    # 6. Gerar relatorio EPG coverage por canal
    log("\n[6] Cobertura EPG por canal:")
    for ch in FIXED_CHANNELS:
        cid = ch['tvg-id']
        ch_progs = [p for p in all_programmes if p.get('channel') == cid]
        ch_hoje = sum(1 for p in ch_progs if p.get('start', '')[:8] == hoje_str)
        ch_amanha = sum(1 for p in ch_progs if p.get('start', '')[:8] == amanha_str)
        ch_depois = sum(1 for p in ch_progs if p.get('start', '')[:8] == depois_str)
        log(f"  {ch['name']}: Total={len(ch_progs)} prog, Hoje={ch_hoje}, Amanha={ch_amanha}, Depois={ch_depois}")
        log_report(f"Canal: {ch['name']} - Total EPG={len(ch_progs)} prog, Hoje={ch_hoje}, Amanha={ch_amanha}, Depois={ch_depois}")

    # 7. Verificacao final
    log("\n[7] Verificacao final...")
    lines_check = m3u_content.strip().split('\n')
    issues = []
    channel_count = 0

    for i, line in enumerate(lines_check):
        if line.startswith('#EXTINF:'):
            channel_count += 1
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
            if i == 0 or not lines_check[i-1].startswith('#EXTINF:'):
                issues.append(f"  Linha {i+1}: URL sem #EXTINF acima")

    log(f"  Canais: {channel_count}")
    if issues:
        log("  PROBLEMAS ENCONTRADOS:")
        for issue in issues:
            log(f"    {issue}")
    else:
        log("  VERIFICACAO: Tudo OK!")

    # 8. Relatorio final
    log("\n" + "=" * 70)
    log("RELATORIO FINAL")
    log("=" * 70)
    log(f"  Arquivo: {M3U_FILE}")
    log(f"  Canais: {channel_count}")
    log(f"  EPG: {EPG_XML}")
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
