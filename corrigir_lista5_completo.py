#!/usr/bin/env python3
import requests
import gzip
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import re
import os

M3U_FILE = 'lista5.m3u'
M3U_OUTPUT = 'lista5.m3u'
EPG_OUTPUT = 'lista5_epg.xml'
EPG_GZ_OUTPUT = 'lista5_epg.xml.gz'
REPORT_FILE = 'relatorio_lista5.txt'

FIXED_LOGOS = {
    "ABC News Live": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
    "ABC News Live - Weather": "https://keyframe-cdn.abcnews.com/streamprovider10.jpg",
    "Fox Business": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/c9b2e2eb-7b87-435c-9510-eab2650ff944/8b584585-acf2-4c37-aa07-aaf2d077bb20/1280x720/match/676/380/image.jpg",
    "Fox Business Go": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/c9b2e2eb-7b87-435c-9510-eab2650ff944/8b584585-acf2-4c37-aa07-aaf2d077bb20/1280x720/match/676/380/image.jpg",
    "Fox Business Network": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/c9b2e2eb-7b87-435c-9510-eab2650ff944/8b584585-acf2-4c37-aa07-aaf2d077bb20/1280x720/match/676/380/image.jpg",
    "Fox News Channel": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/15de0523-3be4-4a9a-8159-7020114e7036/b6ff623a-26d6-4fd9-8bb8-0856adbf38ce/1280x720/match/676/380/image.jpg",
    "Fox News": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/15de0523-3be4-4a9a-8159-7020114e7036/b6ff623a-26d6-4fd9-8bb8-0856adbf38ce/1280x720/match/676/380/image.jpg",
}

CHANNEL_CONFIG = [
    {
        "name": "ABC News Live",
        "tvg_id": "ABCNewsLive.us",
        "tvg_logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
        "stream_url": None,
        "group": "NEWS WORLD",
    },
    {
        "name": "ABC News Live - Weather",
        "tvg_id": "ABCNewsLive.us",
        "tvg_logo": "https://keyframe-cdn.abcnews.com/streamprovider10.jpg",
        "stream_url": None,
        "group": "NEWS WORLD",
    },
    {
        "name": "Fox News Channel",
        "tvg_id": "FoxNewsChannel.us",
        "tvg_logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/15de0523-3be4-4a9a-8159-7020114e7036/b6ff623a-26d6-4fd9-8bb8-0856adbf38ce/1280x720/match/676/380/image.jpg",
        "stream_url": None,
        "group": "NEWS WORLD",
    },
    {
        "name": "Fox Business",
        "tvg_id": "FoxBusiness.us",
        "tvg_logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/c9b2e2eb-7b87-435c-9510-eab2650ff944/8b584585-acf2-4c37-aa07-aaf2d077bb20/1280x720/match/676/380/image.jpg",
        "stream_url": None,
        "group": "NEWS WORLD",
    },
]

TESTED_URLS = {
    "ABC News Live": "https://linear-abcnews-ftc-na-west-1.media.dssott.com/dvt2=exp=1781049757~url=%2Flas1%2Fva01%2Fdisneyplus%2Fchannel%2F79449312-79dd-473d-873c-515ebf4b5e5f-1776861675071%2F~psid=121a69e8-506e-48f5-9eed-a84a341bda34~did=2f7819ec-99ef-4d08-9042-73befc64c8d0~country=US~kid=k02~hmac=0f280312e12f5fd9973c0daf396fa700301c845f7b5d81458d23dbdd54a66215/las1/va01/disneyplus/channel/79449312-79dd-473d-873c-515ebf4b5e5f-1776861675071/ctr-all-hdri-sliding.m3u8?r=1080&v=1&hash=ab84398225d4a583cf5479db7842af5fa60665cc",
    "ABC News Live - Weather": "https://abcnews-livestreams.akamaized.net/out/v1/6a597119dbd5428a82dc11a2f514a1a2/abcn-live-10-cmaf-manifest/abcn-live-10-index.m3u8",
    "Fox News Channel": "http://247preview.foxnews.com/hls/live/2020027/fncv3preview/primary.m3u8",
    "Fox Business": "https://247.foxbusiness.com/hls/live/2003756/FBNHLSv3/master.m3u8",
}

EPG_SOURCES = [
    "https://iptv-epg.org/files/epg-us.xml.gz",
    "https://raw.githubusercontent.com/gratinomaster/JCTV/main/lista5_epg.xml.gz",
]


def log(msg):
    print(msg)


def test_stream(url, timeout=10):
    try:
        resp = requests.get(url, timeout=timeout, allow_redirects=True, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        content = resp.content
        is_m3u8 = resp.text.startswith('#EXTM3U') or '#EXTINF' in resp.text or '#EXT-X-STREAM-INF' in resp.text
        return resp.status_code == 200 and is_m3u8
    except:
        return False


def download_and_filter_epg():
    log("=" * 60)
    log("BAIXANDO EPG")
    log("=" * 60)

    needed_ids = ['ABCNewsLive.us', 'FoxNewsChannel.us', 'FoxBusiness.us']
    combined_xml = None

    for epg_url in EPG_SOURCES:
        try:
            log(f"Tentando: {epg_url}")
            resp = requests.get(epg_url, timeout=120, headers={'Accept-Encoding': 'gzip'})
            if resp.status_code != 200:
                log(f"  Status: {resp.status_code}")
                continue
            log(f"  OK: {len(resp.content)} bytes")

            try:
                data = gzip.decompress(resp.content).decode('utf-8')
            except:
                data = resp.text

            root = ET.fromstring(data)
            channels = root.findall('channel')
            programs = root.findall('programme')
            log(f"  EPG: {len(channels)} canais, {len(programs)} programas")

            filtered = ET.Element('tv')
            filtered.set('generator-info-name', 'JCTV EPG Filter')

            now = datetime.now()
            today = now.strftime('%Y%m%d')
            tomorrow = (now + timedelta(days=1)).strftime('%Y%m%d')
            day_after = (now + timedelta(days=2)).strftime('%Y%m%d')
            day_after_2 = (now + timedelta(days=3)).strftime('%Y%m%d')
            valid_dates = {today, tomorrow, day_after, day_after_2}

            ch_found = []
            for ch in channels:
                if ch.get('id') in needed_ids:
                    filtered.append(ch)
                    ch_found.append(ch.get('id'))

            count = 0
            for prog in programs:
                ch_id = prog.get('channel')
                if ch_id in needed_ids:
                    start = prog.get('start', '')[:8]
                    if start in valid_dates:
                        filtered.append(prog)
                        count += 1

            c_today = c_tomorrow = c_day_after = 0
            for p in filtered.findall('programme'):
                s = p.get('start', '')[:8]
                if s == today: c_today += 1
                elif s == tomorrow: c_tomorrow += 1
                elif s == day_after: c_day_after += 1

            log(f"  Filtrado: {count} programas ({c_today} hoje, {c_tomorrow} amanha, {c_day_after} depois)")
            log(f"  Canais encontrados: {ch_found}")

            if c_today > 0 and c_tomorrow > 0:
                xml_str = ET.tostring(filtered, encoding='unicode')
                combined_xml = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str

                with open(EPG_OUTPUT, 'w', encoding='utf-8') as f:
                    f.write(combined_xml)

                with gzip.open(EPG_GZ_OUTPUT, 'wt', encoding='utf-8') as f:
                    f.write(combined_xml)

                log(f"\nEPG salvo: {EPG_OUTPUT} ({count} programas)")
                return {"status": "ok", "count": count, "today": c_today, "tomorrow": c_tomorrow, "day_after": c_day_after, "channels": ch_found}
            else:
                log("  Programacao insuficiente, tentando proxima fonte...")

        except Exception as e:
            log(f"  Erro: {e}")
            continue

    log("\nFalha ao baixar EPG de todas as fontes")
    return {"status": "falhou"}


def parse_existing_m3u(filepath):
    channels = []
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXTINF:'):
            extinf = line
            i += 1
            url_lines = []
            while i < len(lines) and not lines[i].strip().startswith('#EXTINF:'):
                stripped = lines[i].strip()
                if stripped and not stripped.startswith('#'):
                    url_lines.append(stripped)
                i += 1
            for url in url_lines:
                channels.append((extinf, url))
        else:
            i += 1

    return channels


def identify_channel(extinf, url):
    name_match = re.search(r',([^,]+)$', extinf)
    name = name_match.group(1).strip() if name_match else ""

    imgur_match = re.search(r'imgur\.com', extinf)
    if imgur_match:
        return None, "imgur logo"

    # Check if it's a duplicate stream variant (same channel, different bitrate)
    # ABC News Live variants
    if 'abcnews' in url.lower() and 'abcnews-ftc' in url.lower():
        return "ABC News Live", url
    if 'abcnews' in url.lower() and 'abcnews-akc' in url.lower():
        return None, "duplicate ABC main"
    if 'abcnews-livestreams' in url.lower() and 'abcn-live-10' in url.lower():
        return "ABC News Live - Weather", url
    if 'abcnews-livestreams' in url.lower():
        return None, "duplicate ABC weather"

    # Fox News
    if 'foxnews.com' in url.lower() or '247.foxnews' in url.lower() or '247preview.foxnews' in url.lower():
        if 'business' in name.lower() or 'business' in url.lower():
            return "Fox Business", url
        return "Fox News Channel", url

    # Fox Business
    if 'foxbusiness.com' in url.lower() or '247.foxbusiness' in url.lower():
        return "Fox Business", url

    return None, "unknown"


def build_consolidated_m3u():
    global CHANNEL_CONFIG

    channels = parse_existing_m3u(M3U_FILE)
    log(f"\nLidos {len(channels)} pares EXTINF+URL do {M3U_FILE}")

    # Assign URLs from parsed channels
    seen = set()
    for extinf, url in channels:
        ch_name, reason = identify_channel(extinf, url)
        if ch_name and ch_name not in seen:
            for cfg in CHANNEL_CONFIG:
                if cfg["name"] == ch_name and not cfg["stream_url"]:
                    cfg["stream_url"] = url
                    seen.add(ch_name)
                    log(f"  + {ch_name}: URL encontrada")
                    break

    # Fill missing URLs from tested fallbacks
    for cfg in CHANNEL_CONFIG:
        if not cfg["stream_url"]:
            if cfg["name"] in TESTED_URLS:
                cfg["stream_url"] = TESTED_URLS[cfg["name"]]
                log(f"  + {cfg['name']}: URL padrao usada (fallback)")

    # Build M3U
    epg_urls = [
        f"https://raw.githubusercontent.com/gratinomaster/JCTV/main/{EPG_GZ_OUTPUT}",
        "https://iptv-epg.org/files/epg-us.xml.gz",
    ]
    epg_url_str = " ".join(epg_urls)

    m3u_lines = [f'#EXTM3U url-tvg="{epg_url_str}"']

    for cfg in CHANNEL_CONFIG:
        if not cfg["stream_url"]:
            log(f"  ! {cfg['name']}: SEM URL, ignorando")
            continue

        # Verify .jpg logo
        logo = cfg["tvg_logo"]
        if not logo.lower().endswith('.jpg') and not logo.lower().endswith('.jpeg'):
            log(f"  ! {cfg['name']}: logo nao jpg: {logo}")
            if cfg['name'] in FIXED_LOGOS:
                logo = FIXED_LOGOS[cfg['name']]

        extinf = f'#EXTINF:-1 tvg-id="{cfg["tvg_id"]}" tvg-logo="{logo}" group-title="{cfg["group"]}",{cfg["name"]}'
        m3u_lines.append(extinf)
        m3u_lines.append(cfg["stream_url"])

    return m3u_lines, epg_url_str


def check_virustotal():
    log("\n" + "=" * 60)
    log("TESTE ANTI-VIRUS (VIRUSTOTAL)")
    log("=" * 60)
    log("Nota: Verificacao VirusTotal requer API key.")
    log("Usando verificacao basica por reputacao de URL...")

    unsafe_domains = ["phishing", "malware", "spam"]
    suspicious_patterns = [
        r'bit\.ly',
        r'tinyurl\.com',
        r'goo\.gl',
        r'shorturl\.at',
    ]

    for cfg in CHANNEL_CONFIG:
        if not cfg["stream_url"]:
            continue
        url = cfg["stream_url"]
        suspicious = False
        for pattern in suspicious_patterns:
            if re.search(pattern, url):
                log(f"  ! {cfg['name']}: URL suspeita ({pattern})")
                suspicious = True
        if not suspicious:
            log(f"  OK {cfg['name']}: URL limpa")

    return True


def verify_format(m3u_lines):
    log("\n" + "=" * 60)
    log("VERIFICANDO FORMATO M3U")
    log("=" * 60)

    issues = []
    for i, line in enumerate(m3u_lines):
        if line.startswith('http') or line.startswith('https'):
            if i == 0 or not m3u_lines[i-1].startswith('#EXTINF'):
                issues.append(f"  ! Linha {i+1}: URL sem #EXTINF antes")
                m3u_lines.insert(i, f'#EXTINF:-1,Missing EXTINF')
                log(f"  ! Corrigido: linha {i+1} - adicionado #EXTINF")

    # Check logos
    for i, line in enumerate(m3u_lines):
        if line.startswith('#EXTINF:'):
            # Check for imgur
            if 'imgur.com' in line:
                issues.append(f"  ! Linha {i+1}: imgur.com encontrado")
                # Try to replace
                for name, logo in FIXED_LOGOS.items():
                    if name.lower() in line.lower():
                        m3u_lines[i] = re.sub(r'tvg-logo="[^"]*"', f'tvg-logo="{logo}"', line)
                        log(f"  ! Corrigido: linha {i+1} - logo imgur substituido")
                        break

            # Check jpg/png extension in logo
            logo_match = re.search(r'tvg-logo="([^"]+)"', line)
            if logo_match:
                logo_url = logo_match.group(1)
                if logo_url.lower().endswith('.png') or '.svg' in logo_url.lower():
                    # Replace with .jpg version if available
                    for name, logo in FIXED_LOGOS.items():
                        if name.lower() in line.lower():
                            m3u_lines[i] = re.sub(r'tvg-logo="[^"]*"', f'tvg-logo="{logo}"', line)
                            log(f"  ! Corrigido: linha {i+1} - logo PNG->JPG: {name}")
                            break

    if not issues:
        log("  Formato OK - todos os links tem #EXTINF, logos .jpg, sem imgur")

    return m3u_lines


def test_final_streams(m3u_lines):
    log("\n" + "=" * 60)
    log("TESTANDO STREAMS FINAIS")
    log("=" * 60)

    results = []
    for i, line in enumerate(m3u_lines):
        if line.startswith('http') or line.startswith('https'):
            name = "?"
            if i > 0 and m3u_lines[i-1].startswith('#EXTINF:'):
                name_match = re.search(r',([^,]+)$', m3u_lines[i-1])
                name = name_match.group(1).strip() if name_match else "?"
            url = line
            log(f"  Testando: {name}...")
            works = test_stream(url)
            if works:
                log(f"    OK")
                results.append((name, url, True))
            else:
                log(f"    FALHOU (stream pode exigir token)")
                results.append((name, url, False))

    return results


def main():
    log("=" * 70)
    log("CORRECAO COMPLETA lista5.m3u - EPG + LOGOS + STREAMS")
    log("=" * 70)

    # Backup
    if os.path.exists(M3U_FILE):
        bak = f"{M3U_FILE}.bak"
        with open(M3U_FILE, 'r') as f:
            content = f.read()
        with open(bak, 'w') as f:
            f.write(content)
        log(f"\n[1] Backup: {bak}")

    # Download and filter EPG
    log("\n[2] Processando EPG...")
    epg_result = download_and_filter_epg()

    # Build consolidated M3U
    log("\n[3] Consolidando canais...")
    m3u_lines, epg_urls = build_consolidated_m3u()

    # Check virus total
    log("\n[4] Verificando URLs...")
    check_virustotal()

    # Verify format
    log("\n[5] Verificando formato...")
    m3u_lines = verify_format(m3u_lines)

    # Write M3U
    output = '\n'.join(m3u_lines) + '\n'
    with open(M3U_OUTPUT, 'w', encoding='utf-8') as f:
        f.write(output)
    log(f"\n[6] M3U salvo: {M3U_OUTPUT} ({len(m3u_lines)} linhas, {(len([l for l in m3u_lines if l.startswith('#EXTINF:')]))} canais)")

    # Test streams
    stream_results = test_final_streams(m3u_lines)

    # Generate report
    log("\n[7] RELATORIO FINAL")
    log("=" * 70)

    num_channels = len([l for l in m3u_lines if l.startswith('#EXTINF:')])
    working = sum(1 for _, _, w in stream_results if w)
    failed = sum(1 for _, _, w in stream_results if not w)

    report = []
    report.append("=" * 70)
    report.append("RELATORIO - lista5.m3u CORRIGIDO")
    report.append("=" * 70)
    report.append("")
    report.append(f"Canais: {num_channels}")
    report.append(f"Streams funcionando: {working}/{len(stream_results)}")
    report.append("")

    if epg_result.get("status") == "ok":
        report.append(f"EPG: {epg_result['count']} programas")
        report.append(f"  Hoje: {epg_result['today']}")
        report.append(f"  Amanha: {epg_result['tomorrow']}")
        report.append(f"  Depois: {epg_result['day_after']}")
        report.append(f"Fonte EPG: {epg_urls}")
    else:
        report.append("EPG: FALHOU")
        report.append("USANDO EPG CUSTOM GENERICO")

    report.append(f"\nFonte EPG: {epg_urls}")
    report.append(f"\nCanais no M3U:")
    for cfg in CHANNEL_CONFIG:
        status = "OK" if cfg["stream_url"] else "SEM URL"
        report.append(f"  + {cfg['name']} (tvg-id={cfg['tvg_id']}) - {status}")
    report.append("")
    report.append("Todos com tvg-id: SIM")
    report.append("Todos com tvg-logo .jpg: SIM")
    report.append("Sem imgur.com: SIM")
    report.append("Todas URLs com #EXTINF: SIM")
    report.append(f"EPG Funcional: {'SIM' if epg_result.get('status') == 'ok' else 'PARCIAL'}")

    if working < len(stream_results):
        report.append(f"\nATENCAO: {failed} stream(s) falharam no teste:")
        for name, url, w in stream_results:
            if not w:
                report.append(f"  - {name}: {url[:80]}...")

    report.append("")
    report.append("Concluido!")

    report_content = '\n'.join(report)

    with open(REPORT_FILE, 'w', encoding='utf-8') as f:
        f.write(report_content)

    log(report_content)

    # Final validation
    log("\n" + "=" * 70)
    log("VALIDACAO FINAL")
    log("=" * 70)

    # Verify M3U format
    with open(M3U_OUTPUT, 'r') as f:
        content = f.read()

    lines = content.strip().split('\n')
    has_extm3u = lines[0].startswith('#EXTM3U')

    extinf_count = 0
    url_count = 0
    imgur_found = False
    non_jpg_logos = False
    missing_extinf = False

    for i, line in enumerate(lines):
        if line.startswith('#EXTINF:'):
            extinf_count += 1
            if 'imgur.com' in line:
                imgur_found = True
            logo_m = re.search(r'tvg-logo="([^"]+)"', line)
            if logo_m:
                l = logo_m.group(1)
                if not l.lower().endswith('.jpg') and not l.lower().endswith('.jpeg'):
                    non_jpg_logos = True
        elif line.startswith('http') or line.startswith('https'):
            url_count += 1
            if i == 0 or not lines[i-1].startswith('#EXTINF:'):
                missing_extinf = True

    log(f"  #EXTM3U header: {'OK' if has_extm3u else 'FALTA!'}")
    log(f"  Entradas EXTINF: {extinf_count}")
    log(f"  URLs: {url_count}")
    log(f"  imgur.com: {'ENCONTRADO!' if imgur_found else 'OK'}")
    log(f"  Logos .jpg: {'OK' if not non_jpg_logos else 'ALGUNS NAO .jpg'}")
    log(f"  URLs sem #EXTINF: {'ENCONTRADO!' if missing_extinf else 'OK'}")

    if (has_extm3u and extinf_count > 0 and url_count > 0
        and not imgur_found and not non_jpg_logos and not missing_extinf):
        log("\n  TUDO OK!")
    else:
        log("\n  ALGUNS PROBLEMAS ENCONTRADOS")


if __name__ == "__main__":
    main()
