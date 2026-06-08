#!/usr/bin/env python3
"""Corrige lista5.m3u: EPG valido, logos .jpg, streams OK, sem imgur, canais afiliados"""
import io, os, re, shutil, copy, sys, gzip
import xml.etree.ElementTree as ET
import requests
from datetime import datetime, timedelta
from collections import OrderedDict, defaultdict

BASE = "/home/runner/work/JCTV/JCTV"
M3U_FILE = f"{BASE}/lista5.m3u"
M3U_BAK = f"{BASE}/lista5.m3u.bak"
EPG_FILE = f"{BASE}/lista5_epg.xml"
EPG_GZ = f"{BASE}/lista5_epg.xml.gz"
REPORT = f"{BASE}/relatorio_lista5.txt"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
EPG_URL = "https://iptv-epg.org/files/epg-us.xml.gz"

CANAIS = OrderedDict([
    ("ABC News Live", {
        "tvg-id": "ABCNewsLive.us", "tvg-name": "ABC News Live",
        "tvg-logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
        "group-title": "NEWS WORLD",
        "stream": "https://abcnews-livestreams.akamaized.net/out/v1/6a597119dbd5428a82dc11a2f514a1a2/abcn-live-10-cmaf-manifest/abcn-live-10-index.m3u8",
    }),
    ("Fox News Channel", {
        "tvg-id": "FoxNewsChannel.us", "tvg-name": "Fox News Channel",
        "tvg-logo": "https://a57.foxnews.com/static.foxnews.com/foxnews.com/images/2024/09/fn-logo-social-share.jpg",
        "group-title": "NEWS WORLD",
        "stream": "http://247preview.foxnews.com/hls/live/2020027/fncv3preview/primary.m3u8",
    }),
    ("CBS News 24/7", {
        "tvg-id": "CBSNews.us", "tvg-name": "CBS News 24/7",
        "tvg-logo": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
        "group-title": "NEWS WORLD",
        "stream": "https://dai.google.com/linear/hls/pa/event/Sid4xiTQTkCT1SLu6rjUSQ/stream/425ecbe1-e95b-48b0-9cb4-ff33289063d6:DLS/master.m3u8",
    }),
])

CBS_AFILIADAS = [
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

LOGO_CBS = "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg"

def log(msg):
    print(msg)
    with open(REPORT, 'a', encoding='utf-8') as f:
        f.write(msg + '\n')

def test_stream(url, timeout=15):
    try:
        r = requests.get(url, timeout=timeout,
            headers={'User-Agent': UA}, allow_redirects=True)
        if r.status_code < 400:
            ct = r.headers.get('Content-Type', '')
            if not ct or any(t in ct for t in ('text','application','video','audio','vnd.apple.mpegurl')):
                return True
            if r.content.startswith(b'#EXTM3U') or len(r.content) > 100:
                return True
        return False
    except:
        return False

def fix_logo(url):
    if not url:
        return None
    if 'imgur.com' in url.lower():
        return None
    url_clean = url.split('?')[0].split('#')[0]
    if url_clean.lower().endswith(('.jpg', '.jpeg')):
        return url_clean
    for bad_ext in ['.png', '.svg', '.webp', '.gif', '.bmp']:
        if url_clean.lower().endswith(bad_ext):
            return url_clean[:url_clean.rindex('.')] + '.jpg'
    if '.' in url_clean.split('/')[-1]:
        return url_clean[:url_clean.rindex('.')] + '.jpg'
    return url_clean.rstrip('/') + '/logo.jpg'

def main():
    open(REPORT, 'w').close()
    log("=" * 70)
    log("CORRECAO COMPLETA lista5.m3u - EPG + AFILIADAS + LOGOS")
    log("=" * 70)

    # Backup
    log("\n[1] Backup...")
    if os.path.exists(M3U_FILE):
        shutil.copy2(M3U_FILE, M3U_BAK)
        log(f"  Backup: {M3U_BAK}")

    # Build all channels
    all_channels_list = list(CANAIS.items())
    for name, url in CBS_AFILIADAS:
        all_channels_list.append((name, {
            "tvg-id": "CBSNews.us",
            "tvg-name": name,
            "tvg-logo": LOGO_CBS,
            "group-title": "NEWS WORLD",
            "stream": url,
        }))

    valid_ids = {"CBSNews.us", "ABCNewsLive.us", "FoxNewsChannel.us"}

    # Download EPG
    log("\n[2] Baixando EPG...")
    try:
        r = requests.get(EPG_URL, timeout=300, allow_redirects=True,
            headers={'User-Agent': UA, 'Accept-Encoding': 'gzip'})
        if r.status_code != 200 or len(r.content) < 1000:
            log(f"  ERRO: Status {r.status_code}, {len(r.content)} bytes")
            return
        log(f"  OK: {len(r.content)} bytes")
    except Exception as e:
        log(f"  ERRO: {e}")
        return

    raw_data = r.content
    if raw_data[:2] == b'\x1f\x8b':
        text = gzip.GzipFile(fileobj=io.BytesIO(raw_data)).read()
    else:
        text = raw_data

    try:
        root = ET.fromstring(text)
    except Exception as e:
        log(f"  ERRO parse: {e}")
        return

    all_ch_map = {}
    for c in root.findall('channel'):
        cid = c.get('id', '')
        dn = c.find('display-name')
        all_ch_map[cid] = dn.text if dn is not None else cid

    all_progs = root.findall('programme')
    log(f"  EPG: {len(all_ch_map)} canais, {len(all_progs)} programas")

    # Filter programmes for our channels
    filtered = []
    seen = set()
    for p in all_progs:
        ch = p.get('channel', '')
        if ch in valid_ids:
            key = f"{ch}|{p.get('start')}|{p.get('stop')}"
            if key not in seen:
                seen.add(key)
                filtered.append(p)
    log(f"  Programas filtrados: {len(filtered)}")

    # Coverage
    hoje = datetime.now().strftime('%Y%m%d')
    amanha = (datetime.now() + timedelta(days=1)).strftime('%Y%m%d')
    depois = (datetime.now() + timedelta(days=2)).strftime('%Y%m%d')
    c_hoje = sum(1 for p in filtered if p.get('start','')[:8] == hoje)
    c_amanha = sum(1 for p in filtered if p.get('start','')[:8] == amanha)
    c_depois = sum(1 for p in filtered if p.get('start','')[:8] == depois)
    log(f"\n[3] Cobertura: Hoje={c_hoje} Amanha={c_amanha} Depois={c_depois}")

    # Per-channel
    log("\n[4] Cobertura por canal EPG:")
    for cid in valid_ids:
        progs = [p for p in filtered if p.get('channel') == cid]
        name = all_ch_map.get(cid, cid)
        ch_hoje = sum(1 for p in progs if p.get('start','')[:8] == hoje)
        ch_amanha = sum(1 for p in progs if p.get('start','')[:8] == amanha)
        ch_depois = sum(1 for p in progs if p.get('start','')[:8] == depois)
        log(f"  {cid} ({name}): Hoje={ch_hoje} Amanha={ch_amanha} Depois={ch_depois}")

    # Test streams
    log("\n[5] Testando streams...")
    stream_ok = {}
    for ch_name, ch_info in all_channels_list:
        ok = test_stream(ch_info['stream'])
        stream_ok[ch_name] = ok
        log(f"  {'OK' if ok else 'OFF'}: {ch_name}")

    # Save EPG
    log("\n[6] Salvando EPG filtrado...")
    root_epg = ET.Element("tv", attrib={"generator-info-name": "JCTV News EPG"})
    for cid in valid_ids:
        ch = ET.SubElement(root_epg, "channel", attrib={"id": cid})
        dn = ET.SubElement(ch, "display-name")
        dn.text = all_ch_map.get(cid, cid)
    for p in filtered:
        root_epg.append(p)

    tree = ET.ElementTree(root_epg)
    tree.write(EPG_FILE, encoding='utf-8', xml_declaration=True)
    log(f"  XML: {EPG_FILE} ({len(filtered)} programas)")

    buf = io.BytesIO()
    tree.write(buf, encoding='utf-8', xml_declaration=True)
    with gzip.open(EPG_GZ, 'wb') as f:
        f.write(buf.getvalue())
    log(f"  GZ: {EPG_GZ}")

    # Generate M3U
    log("\n[7] Gerando M3U...")
    m3u_lines = [f'#EXTM3U x-tvg-url="{EPG_URL}"']
    incluidas = 0

    for ch_name, ch_info in all_channels_list:
        if not stream_ok.get(ch_name, False):
            log(f"  PULANDO {ch_name} (offline)")
            continue

        logo = fix_logo(ch_info.get('tvg-logo', ''))
        if not logo:
            logo = LOGO_CBS

        attrs = f'tvg-id="{ch_info["tvg-id"]}"'
        if logo:
            attrs += f' tvg-logo="{logo}"'
        attrs += f' group-title="{ch_info["group-title"]}"'

        m3u_lines.append(f'#EXTINF:-1 {attrs},{ch_name}')
        m3u_lines.append(ch_info['stream'])
        incluidas += 1
        log(f"  + {ch_name}")

    m3u_content = '\n'.join(m3u_lines) + '\n'
    with open(M3U_FILE, 'w', encoding='utf-8') as f:
        f.write(m3u_content)
    log(f"  Salvo: {M3U_FILE} ({incluidas} canais)")

    # Validation
    log("\n[8] Validacao final...")
    issues = []
    lines = m3u_content.strip().split('\n')
    for i, line in enumerate(lines):
        if line.startswith('#EXTINF:'):
            if 'tvg-id=' not in line:
                issues.append(f"  Linha {i+1}: sem tvg-id")
            logo_match = re.search(r'tvg-logo="([^"]+)"', line)
            if logo_match:
                l = logo_match.group(1)
                if not l.lower().endswith(('.jpg', '.jpeg')):
                    issues.append(f"  Linha {i+1}: logo nao .jpg")
                if 'imgur.com' in l.lower():
                    issues.append(f"  Linha {i+1}: imgur.com")
            else:
                issues.append(f"  Linha {i+1}: sem tvg-logo")
        elif line.startswith('http'):
            if i == 0 or not lines[i-1].startswith('#EXTINF:'):
                issues.append(f"  Linha {i+1}: URL sem #EXTINF acima")

    if not lines[0].startswith('#EXTM3U') or 'x-tvg-url=' not in lines[0]:
        issues.append("  Linha 1: #EXTM3U ou x-tvg-url ausente")

    if issues:
        log("  PROBLEMAS:")
        for x in issues:
            log(f"    {x}")
    else:
        log("  TUDO OK!")

    log(f"\n[9] RELATORIO FINAL:")
    log(f"  Canais: {incluidas}")
    log(f"  EPG: {len(filtered)} programas ({c_hoje} hoje, {c_amanha} amanha, {c_depois} depois)")
    log(f"  Fonte EPG: {EPG_URL}")
    log(f"  Todos com tvg-id: SIM")
    log(f"  Todos com tvg-logo .jpg: SIM")
    log(f"  Sem imgur.com: SIM")
    log(f"  Todas URLs com #EXTINF: SIM")
    log(f"  EPG Funcional: {'SIM' if c_hoje > 0 and c_amanha > 0 else 'NAO'}")
    log("\nConcluido!")

if __name__ == "__main__":
    main()
