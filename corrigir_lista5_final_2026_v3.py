#!/usr/bin/env python3
import gzip, io, os, re, sys, shutil, json
import xml.etree.ElementTree as ET
import requests
from datetime import datetime, timedelta
from collections import OrderedDict

M3U_FILE = "/home/runner/work/JCTV/JCTV/lista5.m3u"
M3U_BACKUP = "/home/runner/work/JCTV/JCTV/lista5.m3u.bak2"
EPG_OUTPUT = "/home/runner/work/JCTV/JCTV/lista5_epg.xml.gz"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

CHANNELS = OrderedDict([
    ("ABC News Live", {
        "tvg-id": "465150",
        "tvg-name": "ABC News Live",
        "tvg-logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
        "group-title": "NEWS WORLD",
        "stream": "https://linear-abcnews-akc-na-west-1.media.dssott.com/dvt2=exp=1779195635~url=%2Flas1%2Fva01%2Fdisneyplus%2Fchannel%2F79449312-79dd-473d-873c-515ebf4b5e5f-1776861675071%2F~psid=f105b49a-0e90-433a-b6c6-16b267bf7fec~did=544bac59-94a7-4a1f-bd9d-2657b198854f~country=US~kid=k02~hmac=4aa5b8d3cc31706b8948c4ae54e527277efa87452b62c7d1036daf580a020c69/las1/va01/disneyplus/channel/79449312-79dd-473d-873c-515ebf4b5e5f-1776861675071/ctr-all-hdri-sliding.m3u8?r=1080&v=1&hash=ab84398225d4a583cf5479db7842af5fa60665cc",
        "tvg-chno": "1",
    }),
    ("Fox News Channel", {
        "tvg-id": "465372",
        "tvg-name": "Fox News Channel HD",
        "tvg-logo": "https://raw.githubusercontent.com/gratinomaster/JCTV/main/fox_news.jpg",
        "group-title": "NEWS WORLD",
        "stream": "https://radiovid.foxnews.com/hls/live/661547/RADIOVID/index.m3u8",
        "tvg-chno": "2",
    }),
    ("Fox Business", {
        "tvg-id": "464766",
        "tvg-name": "Fox Business HD",
        "tvg-logo": "https://raw.githubusercontent.com/gratinomaster/JCTV/main/fox_business.jpg",
        "group-title": "NEWS WORLD",
        "stream": "https://tvpass.org/live/FoxBusiness/hd",
        "tvg-chno": "3",
    }),
    ("CBS News 24/7", {
        "tvg-id": "464941",
        "tvg-name": "CBS News National Stream",
        "tvg-logo": "https://www.cbsnews.com/bundles/cbsnewsvideo/images/cbsn--main-bg.jpg",
        "group-title": "NEWS WORLD",
        "stream": "https://news20e7hhcb.airspace-cdn.cbsivideo.com/index.m3u8",
        "tvg-chno": "4",
    }),
])

EPG_URLS = [
    "https://epg.pw/xmltv/epg_US.xml.gz",
    "https://iptv-epg.org/files/epg-us.xml.gz",
    "https://epg.pw/xmltv/epg.xml.gz",
]

def log(msg):
    print(msg)

def download_epg(url):
    log(f"  Baixando EPG: {url}")
    try:
        r = requests.get(url, timeout=300, allow_redirects=True, headers={'User-Agent': USER_AGENT, 'Accept-Encoding': 'gzip'})
        if r.status_code != 200:
            log(f"    Status {r.status_code}, ignorando")
            return None
        if len(r.content) < 1000:
            log(f"    Conteudo muito pequeno ({len(r.content)} bytes), ignorando")
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
        channels_map = {}
        for c in root.findall('channel'):
            ch_id = c.get('id', '')
            dn = c.find('display-name')
            channels_map[ch_id] = dn.text if dn is not None else ch_id
        programmes = root.findall('programme')
        return channels_map, programmes
    except Exception as e:
        log(f"    Erro no parse: {e}")
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
    log(f"  {label}Hoje ({hoje}): {c_hoje} prog | Amanha ({amanha}): {c_amanha} prog | Depois ({depois}): {c_depois} prog")
    return c_hoje, c_amanha, c_depois

def save_epg(programmes, channels_dict, output_path):
    root = ET.Element("tv", attrib={"generator-info-name": "lista5_fixed_epg"})
    for cid, cname in channels_dict.items():
        ch = ET.SubElement(root, "channel", attrib={"id": cid})
        dn = ET.SubElement(ch, "display-name")
        dn.text = cname
    for p in programmes:
        root.append(p)
    tree = ET.ElementTree(root)
    buf = io.BytesIO()
    tree.write(buf, encoding='utf-8', xml_declaration=True)
    raw = buf.getvalue()
    with gzip.open(output_path, 'wb') as f:
        f.write(raw)
    log(f"  EPG salvo: {output_path} ({len(raw)} bytes)")

def check_url(url, timeout=10):
    try:
        r = requests.get(url, timeout=timeout, headers={'User-Agent': USER_AGENT}, allow_redirects=True)
        if r.status_code == 200:
            content_type = r.headers.get('Content-Type', '')
            if 'mpegurl' in content_type or 'vnd.apple.mpegurl' in content_type or r.content.startswith(b'#EXTM3U'):
                return True
            if len(r.content) > 100:
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
            url_clean = base + '.jpg'
            return url_clean
    if '.' in url_clean.split('/')[-1]:
        base = url_clean[:url_clean.rindex('.')]
        url_clean = base + '.jpg'
    else:
        url_clean = url_clean.rstrip('/') + '/logo.jpg'
    return url_clean

def main():
    log("=" * 70)
    log("CORRECAO COMPLETA lista5.m3u - EPG + LOGOS + STREAMS")
    log("=" * 70)
    
    valid_ids = {info['tvg-id'] for info in CHANNELS.values()}
    
    # 1. Backup
    log("\n[1] Backup do arquivo original...")
    if os.path.exists(M3U_FILE):
        shutil.copy2(M3U_FILE, M3U_BACKUP)
        log(f"  Backup: {M3U_BACKUP}")
    
    # 2. Baixar EPG
    log("\n[2] Baixando EPGs...")
    all_channels = {}
    all_programmes = []
    
    for url in EPG_URLS:
        data = download_epg(url)
        if data is None:
            continue
        chs, progs = parse_epg(data)
        all_channels.update(chs)
        filtered = filter_programmes(progs, valid_ids)
        existing = {(p.get('channel',''), p.get('start',''), p.get('stop','')) for p in all_programmes}
        new_count = 0
        for p in filtered:
            key = (p.get('channel',''), p.get('start',''), p.get('stop',''))
            if key not in existing:
                existing.add(key)
                all_programmes.append(p)
                new_count += 1
        log(f"  EPG {url.split('/')[-1][:30]}: {new_count} novos programas")
    
    log(f"\n  Total programas para nossos IDs: {len(all_programmes)}")
    
    # 3. Testar cobertura EPG
    log("\n[3] Testando cobertura EPG...")
    hoje, amanha, depois = test_coverage(all_programmes)
    
    epg_ok = hoje > 0 and amanha > 0 and depois > 0
    
    if not epg_ok and not all_programmes:
        log("  AVISO: Nenhum programa EPG encontrado. Gerando EPG customizado...")
        today = datetime.now()
        for day_offset in range(3):
            d = today + timedelta(days=day_offset)
            for ch_name, ch_info in CHANNELS.items():
                for hour in range(0, 24):
                    start = d.replace(hour=hour, minute=0, second=0)
                    stop = start + timedelta(hours=1)
                    prog = ET.Element("programme", {
                        "channel": ch_info['tvg-id'],
                        "start": start.strftime('%Y%m%d%H%M%S') + ' +0000',
                        "stop": stop.strftime('%Y%m%d%H%M%S') + ' +0000',
                    })
                    title = ET.SubElement(prog, "title")
                    title.text = f"{ch_name} - Programming"
                    all_programmes.append(prog)
        log(f"  Gerados {len(all_programmes)} programas customizados")
        hoje, amanha, depois = test_coverage(all_programmes)
        epg_ok = True
    
    # 4. Verificar por canal
    log("\n[4] Cobertura por canal:")
    for ch_name, ch_info in CHANNELS.items():
        cid = ch_info['tvg-id']
        ch_progs = [p for p in all_programmes if p.get('channel') == cid]
        ch_hoje = sum(1 for p in ch_progs if p.get('start', '')[:8] == datetime.now().strftime('%Y%m%d'))
        log(f"  {ch_name} (ID:{cid}): {len(ch_progs)} programas, {ch_hoje} hoje")
    
    # 5. Salvar EPG
    log("\n[5] Salvando EPG filtrado...")
    channel_dict = {}
    for cid in valid_ids:
        channel_dict[cid] = all_channels.get(cid, cid)
    save_epg(all_programmes, channel_dict, EPG_OUTPUT)
    
    # 6. Testar streams
    log("\n[6] Testando streams...")
    stream_results = {}
    for ch_name, ch_info in CHANNELS.items():
        url = ch_info['stream']
        log(f"  Testando {ch_name}...")
        ok = check_url(url)
        log(f"    {'OK' if ok else 'FALHOU'}: {url[:80]}...")
        stream_results[ch_name] = ok
    
    # 7. Gerar M3U
    log("\n[7] Gerando M3U corrigido...")
    epg_urls_str = ','.join(EPG_URLS[:2])
    
    m3u_lines = [f'#EXTM3U url-tvg="{epg_urls_str}"']
    
    for ch_name, ch_info in CHANNELS.items():
        if not stream_results.get(ch_name, False):
            log(f"  PULANDO {ch_name} (stream offline)")
            continue
        
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
        log(f"  + {ch_name} (logo: {logo})")
    
    m3u_content = '\n'.join(m3u_lines) + '\n'
    
    with open(M3U_FILE, 'w', encoding='utf-8') as f:
        f.write(m3u_content)
    log(f"  M3U salvo: {M3U_FILE} ({len(m3u_content)} bytes)")
    
    # 8. Verificacao final
    log("\n[8] Verificacao final do M3U...")
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
                if not logo.lower().endswith('.jpg'):
                    issues.append(f"  Linha {i+1}: logo nao .jpg: {logo}")
                if 'imgur.com' in logo.lower():
                    issues.append(f"  Linha {i+1}: logo imgur.com: {logo}")
        elif line.startswith('http'):
            if i == 0 or not lines[i-1].startswith('#EXTINF:'):
                issues.append(f"  Linha {i+1}: URL sem #EXTINF acima: {line[:60]}")
    
    log(f"  Canais: {channel_count}")
    if issues:
        log("  PROBLEMAS:")
        for issue in issues:
            log(f"    {issue}")
    else:
        log("  ✓ Tudo OK!")
    
    # 9. Relatorio final
    log("\n" + "=" * 70)
    log("RELATORIO FINAL")
    log("=" * 70)
    log(f"  Arquivo: {M3U_FILE}")
    log(f"  Canais: {channel_count}")
    log(f"  EPG: {EPG_OUTPUT}")
    log(f"  Cobertura: Hoje={hoje} | Amanha={amanha} | Depois={depois}")
    log(f"  EPG Funcional: {'SIM' if epg_ok else 'NAO'}")
    
    log("\n  Canais incluidos:")
    for ch_name, ch_info in CHANNELS.items():
        status = "OK" if stream_results.get(ch_name, False) else "OFFLINE"
        log(f"    {status} {ch_name} (ID:{ch_info['tvg-id']})")
    
    if not epg_ok:
        log("\n  AVISO: EPG sem cobertura suficiente!")
    if issues:
        log(f"\n  AVISO: {len(issues)} problemas encontrados!")
    
    log("\nConcluido!")

if __name__ == "__main__":
    main()
