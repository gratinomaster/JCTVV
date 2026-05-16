#!/usr/bin/env python3
"""Corrige lista5.m3u: consolida canais, adiciona EPG, logos .jpg, testa EPG."""
import re, gzip, io, sys, os
import xml.etree.ElementTree as ET
import requests
from datetime import datetime, timedelta
from collections import OrderedDict

M3U_FILE = "/home/runner/work/JCTV/JCTV/lista5.m3u"
OUTPUT_M3U = "/home/runner/work/JCTV/JCTV/lista5.m3u"
OUTPUT_EPG = "/home/runner/work/JCTV/JCTV/lista5_epg.xml.gz"
BACKUP_M3U = "/home/runner/work/JCTV/JCTV/lista5.m3u.bak2"

def log(msg):
    print(msg)

def download_epg(url):
    log(f"  Baixando EPG: {url}")
    try:
        r = requests.get(url, timeout=300, allow_redirects=True, headers={'User-Agent': 'Mozilla/5.0'})
        if r.status_code != 200:
            log(f"    Skipped (status={r.status_code})")
            return None
        if len(r.content) < 1000:
            log(f"    Skipped (too small: {len(r.content)})")
            return None
        log(f"    Got {len(r.content)} bytes")
        return r.content
    except Exception as e:
        log(f"    Error: {e}")
        return None

def parse_epg(data):
    if data is None:
        return {}, []
    try:
        if data[:2] == b'\x1f\x8b':
            raw = gzip.GzipFile(fileobj=io.BytesIO(data)).read()
        else:
            raw = data
        root = ET.fromstring(raw)
        channels = {}
        for c in root.findall('channel'):
            cid = c.get('id', '')
            name = c.find('display-name')
            channels[cid] = name.text if name is not None else cid
        programmes = root.findall('programme')
        return channels, programmes
    except Exception as e:
        log(f"    Parse error: {e}")
        return {}, []

def filter_epg(programmes, valid_ids):
    matched = []
    seen = set()
    for p in programmes:
        ch = p.get('channel', '')
        if ch in valid_ids:
            start = p.get('start', '')
            stop = p.get('stop', '')
            key = f"{ch}|{start}|{stop}"
            if key not in seen:
                seen.add(key)
                matched.append(p)
    return matched

def test_epg_coverage(programmes, label=""):
    hoje = datetime.now().strftime('%Y%m%d')
    amanha = (datetime.now() + timedelta(days=1)).strftime('%Y%m%d')
    depois = (datetime.now() + timedelta(days=2)).strftime('%Y%m%d')
    
    c_hoje = c_amanha = c_depois = 0
    for p in programmes:
        s = p.get('start', '')[:8]
        if s == hoje: c_hoje += 1
        elif s == amanha: c_amanha += 1
        elif s == depois: c_depois += 1
    
    log(f"  {label}Programas hoje ({hoje}): {c_hoje}")
    log(f"  {label}Programas amanhã ({amanha}): {c_amanha}")
    log(f"  {label}Programas depois ({depois}): {c_depois}")
    
    return c_hoje, c_amanha, c_depois

def save_epg(programmes, channels_dict, output_path):
    root = ET.Element("tv", attrib={"generator-info-name": "lista5_epg"})
    for cid, cname in channels_dict.items():
        ch = ET.SubElement(root, "channel", attrib={"id": cid})
        dn = ET.SubElement(ch, "display-name")
        dn.text = cname
    for p in programmes:
        root.append(p)
    
    tree = ET.ElementTree(root)
    buf = io.BytesIO()
    tree.write(buf, encoding='utf-8', xml_declaration=True)
    xml_data = buf.getvalue()
    
    with gzip.open(output_path, 'wb') as f:
        f.write(xml_data)
    log(f"  EPG salvo: {output_path} ({len(xml_data)} bytes)")
    return xml_data

# ============================================================
# CANAIS DEFINIDOS (baseados na lista5.m3u original)
# ============================================================
# Mapeamento: nome_canal -> { tvg-id, tvg-name, tvg-logo, group-title, stream_url }
# Escolhemos a melhor stream de cada canal (maior qualidade)

CHANNELS = OrderedDict([
    ("ABC News Live", {
        "tvg-id": "465150",
        "tvg-name": "ABC News Live",
        "tvg-logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
        "group-title": "NEWS WORLD",
        "stream": "https://linear-abcnews-akc-na-west-1.media.dssott.com/dvt2=exp=1778975138~url=%2Flas1%2Fva01%2Fdisneyplus%2Fchannel%2F79449312-79dd-473d-873c-515ebf4b5e5f-1776861675071%2F~psid=4ab90edf-c2dc-4ed4-9a05-6de84ab288eb~did=a9ff0e77-1315-49d7-809e-36578e2409fa~country=US~kid=k02~hmac=90cfeedebc34e3cae335415f21d4245e1ad12adc3d1cd8feaaf1b439f07c9117/las1/va01/disneyplus/channel/79449312-79dd-473d-873c-515ebf4b5e5f-1776861675071/cmaf-cenc-ctr-2400K/2400_hdri_slide.m3u8",
        "tvg-chno": "1",
    }),
    ("ABCNL Live", {
        "tvg-id": "465150",
        "tvg-name": "ABC News Live",
        "tvg-logo": "https://keyframe-cdn.abcnews.com/streamprovider10.jpg",
        "group-title": "NEWS WORLD",
        "stream": "https://abcnews-livestreams.akamaized.net/out/v1/6a597119dbd5428a82dc11a2f514a1a2/abcn-live-10-cmaf-manifest/abcn-live-10-index.m3u8",
        "tvg-chno": "2",
    }),
    ("Fox News Channel", {
        "tvg-id": "465372",
        "tvg-name": "Fox News Channel HD",
        "tvg-logo": "https://static.foxnews.com/foxnews.com/content/uploads/2020/03/fn-logo-og.jpg",
        "group-title": "NEWS WORLD",
        "stream": "https://247.foxnews.com/hls/live/2003586/FNCHLSv3/master.m3u8?hdnea=exp=1778892339~acl=/*~hmac=ff6b314c84911135732d7c65eef29398db47191018a7469fa6ee3a9745b64bcc",
        "tvg-chno": "3",
    }),
    ("Fox Business", {
        "tvg-id": "464766",
        "tvg-name": "Fox Business HD",
        "tvg-logo": "https://a57.foxnews.com/static.foxbusiness.com/foxbusiness.com/content/uploads/2021/03/0/0/Fox-Business-Logo-OG.jpg",
        "group-title": "NEWS WORLD",
        "stream": "https://247.foxbusiness.com/hls/live/2003756/FBNHLSv3/master.m3u8?hdnea=exp=1778892339~acl=/*~hmac=ff6b314c84911135732d7c65eef29398db47191018a7469fa6ee3a9745b64bcc",
        "tvg-chno": "4",
    }),
    ("CBS News 24/7", {
        "tvg-id": "464941",
        "tvg-name": "CBS News National Stream",
        "tvg-logo": "https://www.cbsnews.com/bundles/cbsnewsvideo/images/cbsn--main-bg.jpg",
        "group-title": "NEWS WORLD",
        "stream": "https://dai.google.com/linear/hls/pa/event/Sid4xiTQTkCT1SLu6rjUSQ/stream/4d5dd9f9-d68b-4aaa-8c26-15c4831487c2:DLS/master.m3u8",
        "tvg-chno": "5",
    }),
])

def generate_m3u(channels, epg_urls):
    lines = ['#EXTM3U']
    for epg_url in epg_urls:
        lines.append(f'#EXTVLCOPT:http-user-agent=Mozilla/5.0')
    
    for name, info in channels.items():
        tvg_id = info['tvg-id']
        tvg_name = info['tvg-name']
        tvg_logo = info['tvg-logo']
        group = info['group-title']
        stream = info['stream']
        chno = info.get('tvg-chno', '')
        
        attrs = f'tvg-id="{tvg_id}"'
        if tvg_name:
            attrs += f' tvg-name="{tvg_name}"'
        if tvg_logo:
            attrs += f' tvg-logo="{tvg_logo}"'
        if chno:
            attrs += f' tvg-chno="{chno}"'
        if group:
            attrs += f' group-title="{group}"'
        if epg_urls:
            attrs += f' url-tvg="{"|".join(epg_urls)}"'
        
        lines.append(f'#EXTINF:-1 {attrs},{name}')
        lines.append(stream)
    
    return '\n'.join(lines) + '\n'

def main():
    log("="*60)
    log("CORREÇÃO DO lista5.m3u")
    log("="*60)
    
    # 1. Backup do arquivo original
    log("\n1. Backup do arquivo original...")
    if os.path.exists(M3U_FILE):
        import shutil
        shutil.copy2(M3U_FILE, BACKUP_M3U)
        log(f"   Backup criado: {BACKUP_M3U}")
    
    # 2. Fontes EPG
    log("\n2. Baixando fontes EPG...")
    epg_urls = [
        "https://epg.pw/xmltv/epg_US.xml.gz",
    ]
    
    all_channels = {}
    all_programmes = []
    valid_ids = {info['tvg-id'] for info in CHANNELS.values()}
    
    for url in epg_urls:
        data = download_epg(url)
        if data is None:
            continue
        chs, progs = parse_epg(data)
        all_channels.update(chs)
        
        filtered = filter_epg(progs, valid_ids)
        all_programmes.extend(filtered)
        log(f"    -> {len(filtered)} programas para nossos canais")
    
    # 3. Verificar cobertura
    log("\n3. Verificando cobertura EPG...")
    hoje_str = datetime.now().strftime('%Y%m%d')
    amanha_str = (datetime.now() + timedelta(days=1)).strftime('%Y%m%d')
    depois_str = (datetime.now() + timedelta(days=2)).strftime('%Y%m%d')
    
    c_hoje, c_amanha, c_depois = test_epg_coverage(all_programmes)
    
    epg_ok = c_hoje > 0 and c_amanha > 0
    if epg_ok:
        log("\n   ✓ EPG com programação para hoje e amanhã!")
    else:
        log("\n   ⚠ EPG sem programação suficiente. Tentando fontes adicionais...")
        # Try backup EPG source
        backup_urls = ["https://epg.pw/xmltv/epg.xml.gz"]
        for url in backup_urls:
            data = download_epg(url)
            if data is None:
                continue
            chs, progs = parse_epg(data)
            all_channels.update(chs)
            filtered = filter_epg(progs, valid_ids)
            # Add only new programs
            existing = {(p.get('channel',''), p.get('start',''), p.get('stop','')) for p in all_programmes}
            new_count = 0
            for p in filtered:
                key = (p.get('channel',''), p.get('start',''), p.get('stop',''))
                if key not in existing:
                    existing.add(key)
                    all_programmes.append(p)
                    new_count += 1
            log(f"    -> {new_count} novos programas adicionados")
        
        c_hoje, c_amanha, c_depois = test_epg_coverage(all_programmes)
        epg_ok = c_hoje > 0 and c_amanha > 0
        if epg_ok:
            log("\n   ✓ EPG OK após segunda fonte!")
        else:
            log("\n   ✗ EPG ainda insuficiente. Continuando mesmo assim...")
    
    # 4. Salvar EPG filtrado
    log("\n4. Salvando EPG filtrado...")
    channel_dict = {}
    for cid in valid_ids:
        channel_dict[cid] = all_channels.get(cid, cid)
    save_epg(all_programmes, channel_dict, OUTPUT_EPG)
    
    # 5. Gerar M3U corrigido
    log("\n5. Gerando M3U corrigido...")
    m3u_content = generate_m3u(CHANNELS, epg_urls)
    
    with open(OUTPUT_M3U, 'w', encoding='utf-8') as f:
        f.write(m3u_content)
    log(f"   M3U salvo: {OUTPUT_M3U} ({len(m3u_content)} bytes)")
    
    # 6. Verificar M3U
    log("\n6. Verificando M3U gerado...")
    lines = m3u_content.strip().split('\n')
    channel_count = 0
    issues = []
    for i, line in enumerate(lines):
        if line.startswith('#EXTINF:'):
            channel_count += 1
            if 'tvg-id=' not in line:
                issues.append(f"   Linha {i+1}: sem tvg-id")
            if 'tvg-logo=' in line:
                logo_match = re.search(r'tvg-logo="([^"]*)"', line)
                if logo_match:
                    logo = logo_match.group(1)
                    if not logo.lower().endswith('.jpg') and not logo.lower().endswith('.jpeg'):
                        issues.append(f"   Linha {i+1}: logo não é .jpg: {logo}")
            if 'url-tvg=' not in line:
                issues.append(f"   Linha {i+1}: sem url-tvg")
        elif line.startswith('#') or line.startswith('http'):
            continue
        else:
            if i > 0:  # skip first line (#EXTM3U)
                issues.append(f"   Linha {i+1}: formato inesperado: {line[:80]}")
    
    log(f"   Canais no M3U: {channel_count}")
    for issue in issues:
        log(issue)
    if not issues:
        log("   ✓ Nenhum problema encontrado!")
    
    # 7. Verificar que todos os canais têm #EXTINF antes da URL
    log("\n7. Verificando estrutura #EXTINF...")
    good = True
    for i, line in enumerate(lines):
        if line.startswith('http') and (i == 0 or not lines[i-1].startswith('#EXTINF:')):
            log(f"   ✗ Linha {i+1}: URL sem #EXTINF antes")
            good = False
    if good:
        log("   ✓ Todas as URLs têm #EXTINF antes")
    
    # 8. Mostrar resultado final
    log("\n" + "="*60)
    log("RESULTADO FINAL")
    log("="*60)
    log(f"  Arquivo: {OUTPUT_M3U}")
    log(f"  Canais únicos: {channel_count}")
    log(f"  EPG: {OUTPUT_EPG}")
    log(f"  Cobertura EPG - hoje: {c_hoje} prog, amanhã: {c_amanha} prog, depois: {c_depois} prog")
    
    # Show channels in M3U
    log("\n  Canais no M3U:")
    for name, info in CHANNELS.items():
        log(f"    • {name}")
        log(f"      tvg-id: {info['tvg-id']}")
        log(f"      tvg-logo: {info['tvg-logo']}")
    
    if epg_ok:
        log("\n  ✓ EPG FUNCIONANDO!")
    else:
        log("\n  ✗ EPG COM PROBLEMAS - programação insuficiente")
    
    log("\nConcluído!")

if __name__ == "__main__":
    main()
