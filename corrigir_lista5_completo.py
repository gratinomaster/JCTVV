#!/usr/bin/env python3
import os, re, shutil, gzip, io, xml.etree.ElementTree as ET, urllib.request, ssl
from datetime import datetime, timedelta
from collections import OrderedDict

BASE = "/home/runner/work/JCTV/JCTV"
M3U_FILE = f"{BASE}/lista5.m3u"
M3U_BAK = f"{BASE}/lista5.m3u.bak2"
EPG_FILE = f"{BASE}/lista5_epg.xml.gz"
REPORT = f"{BASE}/relatorio_lista5.txt"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

EPG_URL = "https://raw.githubusercontent.com/anomalyco/JCTV/main/lista5_epg.xml.gz"

CHANNELS = OrderedDict([
    ("ABC News Live", {
        "tvg-id": "ABCNewsLive.us",
        "tvg-name": "ABC News Live",
        "tvg-logo": "https://keyframe-cdn.abcnews.com/streamprovider10.jpg",
        "group-title": "NEWS WORLD",
        "stream": "https://abcnews-livestreams.akamaized.net/out/v1/6a597119dbd5428a82dc11a2f514a1a2/abcn-live-10-cmaf-manifest/abcn-live-10-index.m3u8",
    }),
    ("ABC News All Access", {
        "tvg-id": "ABCNewsLive.us",
        "tvg-name": "ABC News All Access",
        "tvg-logo": "https://s.abcnews.com/images/Live/abc_news_live-abc-ml-250210_1739199021469_hpMain_16x9_608.jpg",
        "group-title": "NEWS WORLD",
        "stream": "https://linear-abcnews-akc-na-central-1.media.dssott.com/dvt2=exp=1779580934~url=%2Flas1%2Fva01%2Fdisneyplus%2Fchannel%2F79449312-79dd-473d-873c-515ebf4b5e5f-1776861675071%2F~psid=fbf25610-7404-4de3-a101-3e32de5b6620~did=885c965e-20f5-45b9-852e-473c862e37bd~country=US~kid=k02~hmac=a531ab4b1be31b377f6b1455e84db8935c46eb24f4ce966d5bb528c8f5d8e682/las1/va01/disneyplus/channel/79449312-79dd-473d-873c-515ebf4b5e5f-1776861675071/ctr-all-hdri-sliding.m3u8?r=1080&v=1&hash=ab84398225d4a583cf5479db7842af5fa60665cc",
    }),
    ("Fox News Channel", {
        "tvg-id": "FoxNewsChannel.us",
        "tvg-name": "Fox News Channel",
        "tvg-logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/249abc91-065d-4ca4-8555-c3aef5325a86/d5e3f528-0299-4308-ac83-6ec25d839a90/1280x720/match/400/225/image.jpg",
        "group-title": "NEWS WORLD",
        "stream": "https://radiovid.foxnews.com/hls/live/661547/RADIOVID/index.m3u8",
    }),
    ("Fox Business", {
        "tvg-id": "FoxBusiness.us",
        "tvg-name": "Fox Business",
        "tvg-logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/249abc91-065d-4ca4-8555-c3aef5325a86/d5e3f528-0299-4308-ac83-6ec25d839a90/1280x720/match/400/225/image.jpg",
        "group-title": "NEWS WORLD",
        "stream": "https://tvpass.org/live/FoxBusiness/hd",
    }),
    ("CBS News 24/7", {
        "tvg-id": "CBSNews.us",
        "tvg-name": "CBS News 24/7",
        "tvg-logo": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
        "group-title": "NEWS WORLD",
        "stream": "https://news20e7hhcb.airspace-cdn.cbsivideo.com/index.m3u8",
    }),
])

def log(msg):
    print(msg)

def log_report(msg):
    with open(REPORT, 'a', encoding='utf-8') as f:
        f.write(msg + '\n')

def check_url(url, timeout=15):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)
        if resp.status < 400:
            body = resp.read(500)
            if b'#EXTM3U' in body:
                return True
            ct = resp.headers.get('Content-Type', '')
            if 'mpegurl' in ct or 'x-mpegURL' in ct or 'vnd.apple.mpegurl' in ct:
                return True
            return len(body) > 100
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

def load_epg_data():
    valid_ids = {info['tvg-id'] for info in CHANNELS.values()}
    channels_map = {}
    all_programmes = []
    
    if os.path.exists(EPG_FILE):
        with gzip.open(EPG_FILE, 'rt', encoding='utf-8') as f:
            text = f.read()
        root = ET.fromstring(text)
        for c in root.findall('channel'):
            cid = c.get('id', '')
            dn = c.find('display-name')
            channels_map[cid] = dn.text if dn is not None else cid
        all_programmes = [p for p in root.findall('programme') if p.get('channel', '') in valid_ids]
        log(f"  EPG carregado: {len(channels_map)} canais, {len(all_programmes)} programas")
    else:
        log(f"  EPG {EPG_FILE} nao encontrado, tentando download...")
        try:
            req = urllib.request.Request(EPG_URL, headers={'User-Agent': USER_AGENT})
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            resp = urllib.request.urlopen(req, timeout=30, context=ctx)
            raw = resp.read()
            if raw[:2] == b'\x1f\x8b':
                text = gzip.GzipFile(fileobj=io.BytesIO(raw)).read()
            else:
                text = raw
            root = ET.fromstring(text)
            for c in root.findall('channel'):
                cid = c.get('id', '')
                dn = c.find('display-name')
                channels_map[cid] = dn.text if dn is not None else cid
            all_programmes = [p for p in root.findall('programme') if p.get('channel', '') in valid_ids]
            log(f"  EPG baixado: {len(channels_map)} canais, {len(all_programmes)} programas")
        except Exception as e:
            log(f"  Erro ao baixar EPG: {e}")
    
    return channels_map, all_programmes

def test_coverage(programmes):
    hoje = datetime.now().strftime('%Y%m%d')
    amanha = (datetime.now() + timedelta(days=1)).strftime('%Y%m%d')
    depois = (datetime.now() + timedelta(days=2)).strftime('%Y%m%d')
    c_hoje = sum(1 for p in programmes if p.get('start', '')[:8] == hoje)
    c_amanha = sum(1 for p in programmes if p.get('start', '')[:8] == amanha)
    c_depois = sum(1 for p in programmes if p.get('start', '')[:8] == depois)
    return c_hoje, c_amanha, c_depois

def main():
    with open(REPORT, 'w', encoding='utf-8') as f:
        f.write('')
    
    log("=" * 70)
    log("CORRECAO lista5.m3u - EPG + LOGOS + STREAMS + ANTI-VIRUS")
    log("=" * 70)
    log_report("=" * 70)
    log_report(f"RELATORIO CORRECAO lista5.m3u")
    log_report(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    log_report("=" * 70)
    log_report("")
    
    if os.path.exists(M3U_FILE):
        shutil.copy2(M3U_FILE, M3U_BAK)
        log(f"Backup: {M3U_BAK}")
    
    log("\n[1] Carregando EPG...")
    channels_map, programmes = load_epg_data()
    
    hoje_dt = datetime.now().strftime('%Y%m%d')
    amanha_dt = (datetime.now() + timedelta(days=1)).strftime('%Y%m%d')
    depois_dt = (datetime.now() + timedelta(days=2)).strftime('%Y%m%d')
    
    c_hoje, c_amanha, c_depois = test_coverage(programmes)
    log(f"\n[2] Cobertura EPG: Hoje={c_hoje} Amanha={c_amanha} Depois={c_depois}")
    epg_ok = c_hoje > 0 and c_amanha > 0
    
    log(f"\n[3] Cobertura por canal:")
    for ch_name, ch_info in CHANNELS.items():
        cid = ch_info['tvg-id']
        ch_progs = [p for p in programmes if p.get('channel') == cid]
        ch_hoje = sum(1 for p in ch_progs if p.get('start', '')[:8] == hoje_dt)
        ch_amanha = sum(1 for p in ch_progs if p.get('start', '')[:8] == amanha_dt)
        ch_depois = sum(1 for p in ch_progs if p.get('start', '')[:8] == depois_dt)
        log(f"  {ch_name} (ID:{cid}): {len(ch_progs)} prog, Hoje={ch_hoje}, Amanha={ch_amanha}, Depois={ch_depois}")
        log_report(f"Canal: {ch_name}: tvg-id={cid}, EPG Hoje={ch_hoje} Amanha={ch_amanha} Depois={ch_depois}")
    
    log(f"\n[4] Testando streams...")
    stream_results = {}
    for ch_name, ch_info in CHANNELS.items():
        url = ch_info['stream']
        ok = check_url(url)
        log(f"  Testando {ch_name}... {'OK' if ok else 'FALHOU'}")
        stream_results[ch_name] = ok
        log_report(f"Stream {ch_name}: {'OK' if ok else 'OFFLINE'}")
    
    log(f"\n[5] Gerando M3U corrigido...")
    m3u_lines = [f'#EXTM3U x-tvg-url="{EPG_URL}"']
    
    for ch_name, ch_info in CHANNELS.items():
        if not stream_results.get(ch_name, False):
            log(f"  PULANDO {ch_name} (stream offline)")
            log_report(f"Status {ch_name}: PULADO (stream offline)")
            continue
        
        logo = fix_logo_url(ch_info['tvg-logo'])
        if not logo:
            logo = ch_info['tvg-logo']
        
        attrs = f'tvg-id="{ch_info["tvg-id"]}"'
        if ch_info.get('tvg-name'):
            attrs += f' tvg-name="{ch_info["tvg-name"]}"'
        if logo:
            attrs += f' tvg-logo="{logo}"'
        if ch_info.get('group-title'):
            attrs += f' group-title="{ch_info["group-title"]}"'
        
        m3u_lines.append(f'#EXTINF:-1 {attrs},{ch_name}')
        m3u_lines.append(ch_info['stream'])
        log(f"  + {ch_name}")
        log_report(f"Status {ch_name}: INCLUIDO")
    
    m3u_content = '\n'.join(m3u_lines) + '\n'
    
    with open(M3U_FILE, 'w', encoding='utf-8') as f:
        f.write(m3u_content)
    log(f"\n  M3U salvo: {M3U_FILE} ({len(m3u_content)} bytes, {m3u_content.count('#EXTINF:')} canais)")
    
    log(f"\n[6] Verificacao final...")
    lines = m3u_content.strip().split('\n')
    issues = []
    channel_count = 0
    
    for i, line in enumerate(lines):
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
            if i == 0 or not lines[i-1].startswith('#EXTINF:'):
                issues.append(f"  Linha {i+1}: URL sem #EXTINF acima")
    
    log(f"  Canais: {channel_count}")
    if issues:
        log("  PROBLEMAS:")
        for issue in issues:
            log(f"    {issue}")
    else:
        log("  VERIFICACAO: Tudo OK!")
    
    log(f"\n[7] Relatorio: {REPORT}")
    log("=" * 70)
    log(f"RESUMO: {channel_count} canais, EPG {'OK' if epg_ok else 'FALHA'}")
    log(f"Cobertura: Hoje={c_hoje} | Amanha={c_amanha} | Depois={c_depois}")
    log("=" * 70)
    
    log_report("")
    log_report(f"Total canais: {channel_count}")
    log_report(f"Cobertura EPG: Hoje={c_hoje} Amanha={c_amanha} Depois={c_depois}")
    log_report(f"EPG Funcional: {'SIM' if epg_ok else 'NAO'}")
    log_report(f"Problemas: {len(issues)}")
    log_report("=" * 70)

if __name__ == "__main__":
    main()
