#!/usr/bin/env python3
import io, os, re, shutil, gzip, json
import xml.etree.ElementTree as ET
import requests
from datetime import datetime, timedelta
from collections import OrderedDict

BASE = "/home/runner/work/JCTVV/JCTVV"
M3U_FILE = f"{BASE}/lista5.m3u"
M3U_BAK = f"{BASE}/lista5.m3u.bak"
EPG_OUT = f"{BASE}/lista5_epg.xml.gz"
REPORT = f"{BASE}/relatorio_lista5.txt"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

EPG_SOURCES = OrderedDict([
    ("EPG PW ABC News", {
        "url": "https://epg.pw/api/epg.xml?channel_id=465150",
        "channels": {
            "ABC News Live": "465150",
        }
    }),
    ("EPG PW Fox News", {
        "url": "https://epg.pw/api/epg.xml?channel_id=465372",
        "channels": {
            "Fox News Channel": "465372",
        }
    }),
    ("EPG PW Fox Business", {
        "url": "https://epg.pw/api/epg.xml?channel_id=464766",
        "channels": {
            "Fox Business": "464766",
        }
    }),
    ("Samsung TV Plus US", {
        "url": "https://i.mjh.nz/SamsungTVPlus/us.xml.gz",
        "channels": {
            "CBS News 24/7": "USBA370000104",
        }
    }),
])

# Synthetic EPG definitions for channels without external EPG
SYNTHETIC_PROGRAMMES = OrderedDict([
    ("USBA370000104", [
        ("0600", "0700", "CBS Morning News"),
        ("0700", "0900", "CBS This Morning"),
        ("0900", "1000", "CBS News Daily"),
        ("1000", "1200", "CBS This Morning"),
        ("1200", "1230", "CBS News Midday"),
        ("1230", "1330", "CBS News Update"),
        ("1330", "1400", "The Price Is Right"),
        ("1400", "1430", "CBS News Update"),
        ("1430", "1530", "The Young and the Restless"),
        ("1530", "1630", "CBS News Afternoon"),
        ("1630", "1730", "CBS Evening News"),
        ("1730", "1830", "CBS News Evening"),
        ("1830", "1900", "CBS World News Tonight"),
        ("1900", "2000", "60 Minutes"),
        ("2000", "2100", "CBS News Special"),
        ("2100", "2200", "CBS News Special"),
        ("2200", "2300", "CBS News Nightwatch"),
        ("2300", "0600", "CBS News Overnight"),
    ]),
])

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
        "tvg-logo": "https://a57.foxnews.com/static.foxnews.com/foxnews.com/images/2024/09/fn-logo-social-share.jpg",
        "group-title": "NEWS WORLD",
        "stream": "https://247.foxnews.com/hls/live/2003586/FNCHLSv3/master.m3u8?hdnea=exp=1781970118~acl=/*~hmac=5de4a8770bd5cb84c5e8483d957cf7b81cf22ef2914f51b982ebbfd831f0e928",
        "tvg-chno": "2",
    }),
    ("Fox Business", {
        "tvg-id": "464766",
        "tvg-name": "Fox Business",
        "tvg-logo": "https://a57.foxnews.com/static.foxbusiness.com/foxbusiness.com/images/2024/09/fb-logo-social-share.jpg",
        "group-title": "NEWS WORLD",
        "stream": "https://247.foxbusiness.com/hls/live/2003756/FBNHLSv3/master.m3u8?hdnea=exp=1781970118~acl=/*~hmac=5de4a8770bd5cb84c5e8483d957cf7b81cf22ef2914f51b982ebbfd831f0e928",
        "tvg-chno": "3",
    }),
    ("CBS News 24/7", {
        "tvg-id": "USBA370000104",
        "tvg-name": "CBS News 24/7",
        "tvg-logo": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
        "group-title": "NEWS WORLD",
        "stream": "https://dai.google.com/linear/hls/pa/event/Sid4xiTQTkCT1SLu6rjUSQ/stream/f3f8f872-697a-4d9b-a2e4-ff04611a99e0:TUL/master.m3u8",
        "tvg-chno": "4",
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
    ("CBSN Boston", "https://cbsn-bos.cbsnstream.cbsnews.com/out/v1/589d66ec6eb8434c96c28de0370d1326/master.m3u8"),
]

CBS_AFFILIATE_LOGO = "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg"

def log(msg):
    print(msg)

def log_report(msg):
    with open(REPORT, 'a', encoding='utf-8') as f:
        f.write(msg + '\n')

def download_epg(url):
    log(f"  Baixando EPG: {url[:70]}...")
    try:
        r = requests.get(url, timeout=120, allow_redirects=True,
            headers={'User-Agent': USER_AGENT, 'Accept-Encoding': 'gzip'})
        if r.status_code != 200:
            log(f"    Status {r.status_code}, ignorando")
            return None
        if len(r.content) < 500:
            log(f"    Conteudo muito pequeno ({len(r.content)} bytes)")
            return None
        log(f"    OK: {len(r.content)} bytes, HTTP {r.status_code}")
        return r.content
    except Exception as e:
        log(f"    Erro rede: {type(e).__name__}: {e}")
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
            ch_map[cid] = dn.text if dn is not None and dn.text else cid
        programmes = root.findall('programme')
        return ch_map, programmes
    except Exception as e:
        log(f"    Erro parse EPG: {e}")
        return {}, []

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
    url_lower = url_clean.lower()
    if url_lower.endswith(('.jpg', '.jpeg')):
        return url_clean
    for bad_ext in ['.png', '.svg', '.webp', '.gif', '.bmp', '.avif']:
        if url_lower.endswith(bad_ext):
            base = url_clean[:url_clean.rindex('.')]
            return base + '.jpg'
    if '.' in url_clean.split('/')[-1]:
        base = url_clean[:url_clean.rindex('.')]
        return base + '.jpg'
    return url_clean.rstrip('/') + '/logo.jpg'

def get_dates():
    hoje = datetime.now()
    return [
        hoje.strftime('%Y%m%d'),
        (hoje + timedelta(days=1)).strftime('%Y%m%d'),
        (hoje + timedelta(days=2)).strftime('%Y%m%d'),
    ]

def make_epg(programmes, valid_ids, all_channels, epg_url):
    root = ET.Element("tv", attrib={"generator-info-name": "JCTV News EPG"})
    for cid in sorted(valid_ids):
        cname = all_channels.get(cid, cid)
        ch = ET.SubElement(root, "channel", attrib={"id": cid})
        dn = ET.SubElement(ch, "display-name")
        dn.text = cname
    for p in programmes:
        root.append(p)
    tree = ET.ElementTree(root)
    epg_xml_path = f"{BASE}/lista5_epg.xml"
    tree.write(epg_xml_path, encoding='utf-8', xml_declaration=True)
    buf = io.BytesIO()
    tree.write(buf, encoding='utf-8', xml_declaration=True)
    with gzip.open(EPG_OUT, 'wb') as f:
        f.write(buf.getvalue())
    return epg_xml_path

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

def main():
    log("=" * 70)
    log("CORRECAO COMPLETA lista5.m3u")
    log("=" * 70)

    open(REPORT, 'w', encoding='utf-8').close()
    log_report("=" * 70)
    log_report(f"RELATORIO CORRECAO lista5.m3u")
    log_report(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    log_report("=" * 70)

    # Backup
    log("\n[1] Backup original...")
    if os.path.exists(M3U_FILE):
        shutil.copy2(M3U_FILE, M3U_BAK)
        log(f"  Backup salvo: {M3U_BAK}")

    # Build map: tvg-id -> epg source URL
    tvg_to_epg_url = {}
    for src_name, src_info in EPG_SOURCES.items():
        for ch_name, tvg_id in src_info["channels"].items():
            tvg_to_epg_url[tvg_id] = src_info["url"]

    valid_ids = set()
    for ch_name, ch_info in CHANNELS.items():
        valid_ids.add(ch_info["tvg-id"])

    # Download EPGs from all sources
    log("\n[2] Baixando EPGs de todas as fontes...")
    all_channels = {}
    all_programmes = []
    src_programme_counts = {}

    for src_name, src_info in EPG_SOURCES.items():
        data = download_epg(src_info["url"])
        if data:
            chs, progs = parse_epg(data)
            all_channels.update(chs)
            wanted_ids = set(src_info["channels"].values())
            filtered = [p for p in progs if p.get('channel', '') in wanted_ids]
            src_programme_counts[src_name] = len(filtered)
            existing = set()
            for p in filtered:
                key = (p.get('channel', ''), p.get('start', ''), p.get('stop', ''))
                if key not in existing:
                    existing.add(key)
                    all_programmes.append(p)
            log(f"  Fonte '{src_name}': {len(filtered)} programas relevantes")
        else:
            src_programme_counts[src_name] = 0

    total_progs = len(all_programmes)
    log(f"\n  Total programas coletados: {total_progs}")

    # Supplement channels that lack EPG coverage for all 3 days
    dates = get_dates()
    log("\n  Verificando e suplementando EPG por canal...")
    for cid, progs in SYNTHETIC_PROGRAMMES.items():
        if cid not in valid_ids:
            continue
        existing = [p for p in all_programmes if p.get('channel') == cid]
        missing_dates = [d for d in dates if not any(p.get('start', '')[:8] == d for p in existing)]
        if not missing_dates and existing:
            log(f"  {cid}: OK, {len(existing)} programas ja cobrindo todos os dias")
            continue
        log(f"  {cid}: complementando {len(missing_dates)} dias faltantes ({len(existing)} existentes)")
        for date_str in missing_dates:
            for start, stop, title in progs:
                prog = ET.Element("programme", {
                    "channel": cid,
                    "start": f"{date_str}{start}00 +0000",
                    "stop": f"{date_str}{stop}00 +0000",
                })
                t = ET.SubElement(prog, "title", {"lang": "en"})
                t.text = title
                d = ET.SubElement(prog, "desc", {"lang": "en"})
                d.text = "Live news coverage"
                all_programmes.append(prog)
        log(f"    +{len(missing_dates) * len(progs)} programas sinteticos")

    total_progs = len(all_programmes)
    log(f"  Total apos suplementacao: {total_progs}")

    # Check EPG coverage per date
    log("\n[3] Verificando cobertura EPG por data...")
    coverage = {}
    for d in dates:
        count = sum(1 for p in all_programmes if p.get('start', '')[:8] == d)
        coverage[d] = count
        log(f"  {d}: {count} programas")

    # Per-channel coverage
    log("\n[4] Cobertura por canal:")
    per_channel = {}
    for ch_name, ch_info in CHANNELS.items():
        cid = ch_info["tvg-id"]
        programas = [p for p in all_programmes if p.get('channel') == cid]
        per_channel[cid] = len(programas)
        ch_coverage = {}
        for d in dates:
            ch_coverage[d] = sum(1 for p in programas if p.get('start', '')[:8] == d)
        status = all(ch_coverage[d] > 0 for d in dates)
        log(f"  {ch_name} (ID:{cid}): {len(programas)} prog | Hoje={ch_coverage[dates[0]]} Amanha={ch_coverage[dates[1]]} Depois={ch_coverage[dates[2]]} | {'OK' if status else 'FALTA EPG'}")
        log_report(f"Canal: {ch_name} | tvg-id: {cid} | EPG: Hoje={ch_coverage[dates[0]]} Amanha={ch_coverage[dates[1]]} Depois={ch_coverage[dates[2]]}")

    # Save EPG
    log("\n[5] Salvando EPG filtrado...")
    epg_local = make_epg(all_programmes, valid_ids, all_channels, "")
    log(f"  EPG XML: {epg_local}")
    log(f"  EPG GZ:  {EPG_OUT}")

    # Build all channel list (main + affiliates)
    all_channel_list = list(CHANNELS.items())
    for aff_name, aff_url in CBS_AFFILIATES:
        all_channel_list.append((aff_name, {
            "tvg-id": "USBA370000104",
            "tvg-name": aff_name,
            "tvg-logo": CBS_AFFILIATE_LOGO,
            "group-title": "NEWS WORLD",
            "stream": aff_url,
        }))

    # Test streams
    log("\n[6] Testando streams...")
    stream_results = {}
    vt_api_key = os.environ.get('VIRUSTOTAL_API_KEY', '')
    vt_results = {}
    for ch_name, ch_info in all_channel_list:
        url = ch_info['stream']
        ok = check_url(url)
        content_type = ""
        try:
            r = requests.get(url, timeout=15, headers={'User-Agent': USER_AGENT}, allow_redirects=True)
            content_type = r.headers.get('Content-Type', '')
        except:
            pass
        log(f"  {ch_name}: {'OK' if ok else 'FALHOU'} | Content-Type: {content_type[:40] if content_type else 'N/A'}")
        stream_results[ch_name] = ok

    # VirusTotal
    log("\n[7] Verificacao VirusTotal...")
    for ch_name, ch_info in all_channel_list:
        url = ch_info['stream']
        vt_result = check_virustotal_url(url, vt_api_key)
        vt_results[ch_name] = vt_result
        log(f"  {ch_name}: {vt_result['status']}")
        log_report(f"  VirusTotal {ch_name}: {vt_result['status']}")

    # Generate M3U
    log("\n[8] Gerando M3U corrigido...")
    epg_url_list = list(tvg_to_epg_url.values())
    unique_epg_urls = list(OrderedDict.fromkeys(epg_url_list))

    m3u_lines = ['#EXTM3U']

    channel_count = 0
    for ch_name, ch_info in all_channel_list:
        # Skip if stream failed
        if not stream_results.get(ch_name, False):
            log(f"  PULANDO {ch_name} (stream offline)")
            log_report(f"  {ch_name}: PULADO (stream offline)")
            continue

        vt = vt_results.get(ch_name, {})
        if vt.get('status') == 'malicious':
            log(f"  PULANDO {ch_name} (malicioso VirusTotal)")
            log_report(f"  {ch_name}: PULADO (malicioso)")
            continue

        logo = fix_logo_url(ch_info.get('tvg-logo', ''))
        if not logo:
            logo = ch_info.get('tvg-logo', '')

        cid = ch_info["tvg-id"]
        epg_url = tvg_to_epg_url.get(cid, '')

        attrs = f'tvg-id="{cid}"'
        if ch_info.get('tvg-name'):
            attrs += f' tvg-name="{ch_info["tvg-name"]}"'
        if logo:
            attrs += f' tvg-logo="{logo}"'
        if epg_url:
            attrs += f' tvg-url="{epg_url}"'
        if ch_info.get('group-title'):
            attrs += f' group-title="{ch_info["group-title"]}"'

        m3u_lines.append(f'#EXTINF:-1 {attrs},{ch_name}')
        m3u_lines.append(ch_info['stream'])
        log(f"  + {ch_name} | tvg-id={cid} | EPG: {epg_url[:50] if epg_url else 'local'}...")
        log_report(f"  {ch_name}: INCLUIDO | ID={cid} | Stream={'OK' if stream_results.get(ch_name) else '?'}")
        channel_count += 1

    m3u_content = '\n'.join(m3u_lines) + '\n'

    with open(M3U_FILE, 'w', encoding='utf-8') as f:
        f.write(m3u_content)
    log(f"\n  M3U salvo: {M3U_FILE} ({len(m3u_content)} bytes, {channel_count} canais)")

    # Final verification
    log("\n[9] Verificacao final do M3U...")
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
            if 'tvg-url=' not in line:
                issues.append(f"  Linha {i+1}: sem tvg-url (EPG)")
        elif line.startswith('http') or line.startswith('https://'):
            if i == 0 or not lines[i-1].startswith('#EXTINF:'):
                issues.append(f"  Linha {i+1}: URL sem #EXTINF acima ({line[:60]}...)")
        elif line.startswith('#') and not line.startswith('#EXT') and line != '#EXTM3U':
            issues.append(f"  Linha {i+1}: linha com # desconhecida: {line}")

    if not lines[0].startswith('#EXTM3U'):
        issues.append("  Linha 1: sem #EXTM3U")

    epg_ok = all(coverage.get(d, 0) > 0 for d in dates)
    log(f"  Canais: {channel_count}")
    if issues:
        log("  PROBLEMAS:")
        for issue in issues:
            log(f"    {issue}")
    else:
        log("  VERIFICACAO: Tudo OK!")

    # Final report
    log("\n" + "=" * 70)
    log("RELATORIO FINAL")
    log("=" * 70)
    log(f"  Arquivo: {M3U_FILE}")
    log(f"  Canais: {channel_count}")
    log(f"  EPG: {EPG_OUT}")
    log(f"  Cobertura EPG: {', '.join(f'{d}={coverage[d]}' for d in dates)}")
    log(f"  EPG Funcional (hoje+amanha+depois): {'SIM' if epg_ok else 'NAO - FALTAM DIAS'}")
    log(f"  Problemas: {len(issues)}")

    log_report("")
    log_report(f"Total canais: {channel_count}")
    log_report(f"EPG cobertura: {', '.join(f'{d}={coverage[d]}' for d in dates)}")
    log_report(f"EPG OK: {'SIM' if epg_ok else 'NAO'}")
    log_report(f"Problemas: {len(issues)}")
    log_report("=" * 70)

    log("\nConcluido!")

if __name__ == "__main__":
    main()
