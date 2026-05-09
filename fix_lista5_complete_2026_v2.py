#!/usr/bin/env python3
"""Corrige lista5.m3u: EPG, logos, URLs, dedup - versão completa 2026"""
import gzip
import xml.etree.ElementTree as ET
from collections import OrderedDict
from datetime import datetime, timedelta
import copy
import re
import io
import requests

M3U_PATH = "/home/runner/work/JCTV/JCTV/lista5.m3u"
M3U_BAK = "/home/runner/work/JCTV/JCTV/lista5.m3u.bak"
EPG_SRC1 = "/home/runner/work/JCTV/JCTV/lista5_epg.xml.gz"
EPG_SRC2 = "/home/runner/work/JCTV/JCTV/EPGFULL.xml.gz"
EPG_OUT = "/home/runner/work/JCTV/JCTV/lista5_epg.xml.gz"
M3U_OUT = "/home/runner/work/JCTV/JCTV/lista5.m3u"

# Channel mapping: canonical name -> tvg-id, logo, group
CHANNEL_MAP = OrderedDict([
    ("ABC News Live", {
        "tvg_id": "465150",
        "logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
        "group": "NEWS WORLD",
        "names": ["ABCNL Prime", "ABC News Live", "ABCNL"],
        "primary_url": "https://abcnews-livestreams.akamaized.net/out/v1/6a597119dbd5428a82dc11a2f514a1a2/abcn-live-10-cmaf-manifest/abcn-live-10-index.m3u8",
    }),
    ("Fox Business", {
        "tvg_id": "464766",
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/519925b6-905d-47fa-bada-5e700a710dee/22ee56a5-9cee-46af-a739-c240172f2777/1280x720/match/1280/720/image.jpg",
        "group": "NEWS WORLD",
        "names": ["Fox Business", "Fox Business Go", "FBN"],
        "primary_url": "https://247.foxbusiness.com/hls/live/2003756/FBNHLSv3/master.m3u8",
    }),
    ("Fox News Channel", {
        "tvg_id": "465372",
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/15de0523-3be4-4a9a-8159-7020114e7036/b6ff623a-26d6-4fd9-8bb8-0856adbf38ce/1280x720/match/676/380/image.jpg",
        "group": "NEWS WORLD",
        "names": ["Fox News", "Fox News Channel", "FNC"],
        "primary_url": "https://247.foxnews.com/hls/live/2003586/FNCHLSv3/master.m3u8",
    }),
    ("CBS News 24/7", {
        "tvg_id": "464941",
        "logo": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
        "group": "NEWS WORLD",
        "names": ["CBS News", "CBS News 24/7", "CBS"],
        "primary_url": "https://dai.google.com/linear/hls/pa/event/Sid4xiTQTkCT1SLu6rjUSQ/stream/a52b73c7-c263-4ca0-a924-62b7efd0252a:ATL/master.m3u8",
    }),
])

def load_epg(path):
    """Carrega EPG de arquivo .xml.gz"""
    try:
        with gzip.open(path, 'rb') as f:
            content = f.read()
        root = ET.fromstring(content)
        channels = {}
        for ch in root.findall('channel'):
            channels[ch.get('id')] = ch
        programmes = root.findall('programme')
        print(f"  Carregado: {path} -> {len(channels)} canais, {len(programmes)} programas")
        return root, channels, programmes
    except Exception as e:
        print(f"  Erro ao carregar {path}: {e}")
        return None, {}, []

def generate_extended_programs(channels_dict, programme_list, target_date_str):
    """Gera programas estendidos para canais que nao tem programacao na data alvo"""
    from collections import defaultdict
    ch_progs = defaultdict(list)
    for p in programme_list:
        ch = p.get('channel')
        ch_progs[ch].append(p)
    
    today = datetime.now()
    target_date = datetime.strptime(target_date_str, '%Y%m%d')
    
    new_progs = []
    for ch_id, progs in ch_progs.items():
        has_target = any(p.get('start', '')[:8] == target_date_str for p in progs)
        if has_target:
            continue
        progs_by_day = defaultdict(list)
        for p in progs:
            day = p.get('start', '')[:8]
            progs_by_day[day].append(p)
        
        if not progs_by_day:
            continue
        
        best_day = max(progs_by_day.keys())
        ref_progs = progs_by_day[best_day]
        ref_date = datetime.strptime(best_day, '%Y%m%d')
        days_diff = (target_date - ref_date).days
        
        for p in ref_progs:
            start_orig = p.get('start', '')
            stop_orig = p.get('stop', '')
            if len(start_orig) < 14 or len(stop_orig) < 14:
                continue
            
            start_dt = datetime.strptime(start_orig[:14], '%Y%m%d%H%M%S')
            stop_dt = datetime.strptime(stop_orig[:14], '%Y%m%d%H%M%S')
            
            new_start = start_dt + timedelta(days=days_diff)
            new_stop = stop_dt + timedelta(days=days_diff)
            
            new_prog = copy.deepcopy(p)
            new_prog.set('start', new_start.strftime('%Y%m%d%H%M%S') + ' +0000')
            new_prog.set('stop', new_stop.strftime('%Y%m%d%H%M%S') + ' +0000')
            new_progs.append(new_prog)
    
    return new_progs

def merge_epgs():
    """Merge lista5_epg + EPGFULL e estende para dia 11/05"""
    print("\n=== GERANDO EPG COMPLETO ===")
    
    root1, chans1, progs1 = load_epg(EPG_SRC1)
    root2, chans2, progs2 = load_epg(EPG_SRC2)
    
    today_str = datetime.now().strftime('%Y%m%d')
    tomorrow_str = (datetime.now() + timedelta(days=1)).strftime('%Y%m%d')
    dayafter_str = (datetime.now() + timedelta(days=2)).strftime('%Y%m%d')
    print(f"  Datas: hoje={today_str}, amanha={tomorrow_str}, depois={dayafter_str}")
    
    merged_channels = OrderedDict()
    seen_progs = set()
    merged_progs = []
    
    for root, chans, progs in [(root1, chans1, progs1), (root2, chans2, progs2)]:
        if root is None:
            continue
        for ch_id, ch_el in chans.items():
            if ch_id not in merged_channels:
                merged_channels[ch_id] = ch_el
        
        for p in progs:
            key = f"{p.get('channel')}|{p.get('start')}|{p.get('stop')}"
            if key not in seen_progs:
                seen_progs.add(key)
                merged_progs.append(p)
    
    print(f"  Merge: {len(merged_channels)} canais, {len(merged_progs)} programas")
    
    new_progs = generate_extended_programs(merged_channels, merged_progs, dayafter_str)
    print(f"  Programas gerados para {dayafter_str}: {len(new_progs)}")
    merged_progs.extend(new_progs)
    
    new_progs_tomorrow = generate_extended_programs(merged_channels, merged_progs, tomorrow_str)
    real_count_tomorrow = sum(1 for p in merged_progs if p.get('start', '')[:8] == tomorrow_str)
    if real_count_tomorrow == 0 and new_progs_tomorrow:
        merged_progs.extend(new_progs_tomorrow)
        print(f"  Programas gerados para {tomorrow_str}: {len(new_progs_tomorrow)}")
    
    new_progs_today = generate_extended_programs(merged_channels, merged_progs, today_str)
    real_count_today = sum(1 for p in merged_progs if p.get('start', '')[:8] == today_str)
    if real_count_today == 0 and new_progs_today:
        merged_progs.extend(new_progs_today)
        print(f"  Programas gerados para {today_str}: {len(new_progs_today)}")
    
    out_root = ET.Element('tv', {'generator-info-name': 'lista5_epg_merged'})
    for ch_id, ch_el in merged_channels.items():
        out_root.append(copy.deepcopy(ch_el))
    for p in merged_progs:
        out_root.append(copy.deepcopy(p))
    
    tree = ET.ElementTree(out_root)
    with gzip.open(EPG_OUT, 'wb') as f:
        tree.write(f, encoding='utf-8', xml_declaration=True)
    
    print(f"  EPG salvo: {EPG_OUT}")
    print(f"  Total final: {len(merged_channels)} canais, {len(merged_progs)} programas")
    
    count_today = sum(1 for p in merged_progs if p.get('start', '')[:8] == today_str)
    count_tomorrow = sum(1 for p in merged_progs if p.get('start', '')[:8] == tomorrow_str)
    count_dayafter = sum(1 for p in merged_progs if p.get('start', '')[:8] == dayafter_str)
    print(f"  Programas: hoje={count_today}, amanha={count_tomorrow}, depois={count_dayafter}")
    
    # Check per-channel coverage
    for ch_id in merged_channels:
        ch_today = sum(1 for p in merged_progs if p.get('channel') == ch_id and p.get('start', '')[:8] == today_str)
        ch_tomorrow = sum(1 for p in merged_progs if p.get('channel') == ch_id and p.get('start', '')[:8] == tomorrow_str)
        ch_dayafter = sum(1 for p in merged_progs if p.get('channel') == ch_id and p.get('start', '')[:8] == dayafter_str)
        print(f"    Canal {ch_id}: hoje={ch_today}, amanha={ch_tomorrow}, depois={ch_dayafter}")
    
    return True

def identify_channel(extinf_line):
    """Identifica qual canal baseado na linha EXTINF"""
    line_lower = extinf_line.lower()
    channel_name = extinf_line.rsplit(',', 1)[-1].strip() if ',' in extinf_line else ''
    name_lower = channel_name.lower()
    
    if 'marine' in name_lower or 'traffic' in name_lower:
        return None, None, True
    
    for canonical, config in CHANNEL_MAP.items():
        for alt_name in config['names']:
            if alt_name.lower() in name_lower or alt_name.lower() in line_lower:
                return canonical, config, False
        if canonical.lower() in name_lower or canonical.lower() in line_lower:
            return canonical, config, False
    
    if 'abcnl' in name_lower:
        if 'marine' not in name_lower and 'traffic' not in name_lower:
            return 'ABC News Live', CHANNEL_MAP['ABC News Live'], False
    if 'abc news' in name_lower or 'abc' in name_lower:
        if 'marine' not in name_lower and 'traffic' not in name_lower:
            return 'ABC News Live', CHANNEL_MAP['ABC News Live'], False
    if 'fox business' in name_lower or 'fbn' in name_lower:
        return 'Fox Business', CHANNEL_MAP['Fox Business'], False
    if 'fox news' in name_lower or 'fnc' in name_lower:
        return 'Fox News Channel', CHANNEL_MAP['Fox News Channel'], False
    if 'cbs news' in name_lower:
        return 'CBS News 24/7', CHANNEL_MAP['CBS News 24/7'], False
    
    return None, None, False

def fix_m3u():
    """Corrige e limpa o arquivo M3U"""
    print("\n=== CORRIGINDO M3U ===")
    
    with open(M3U_PATH, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    print(f"  Linhas originais: {len(lines)}")
    
    used_urls = set()
    used_channels = set()
    marine_added = False
    output_lines = []
    
    today_str = datetime.now().strftime('%Y%m%d')
    tomorrow_str = (datetime.now() + timedelta(days=1)).strftime('%Y%m%d')
    dayafter_str = (datetime.now() + timedelta(days=2)).strftime('%Y%m%d')
    
    for i, line in enumerate(lines):
        line = line.rstrip('\n')
        
        if line.startswith('#EXTM3U'):
            # Add EPG URL to header
            epg_url = "https://raw.githubusercontent.com/anomalyco/JCTV/main/lista5_epg.xml.gz"
            output_lines.append(f'#EXTM3U x-tvg-url="{epg_url}"')
            continue
        
        if line.startswith('#EXTINF:'):
            url_line = ''
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line and not next_line.startswith('#'):
                    url_line = next_line
            
            if url_line in used_urls:
                continue
            
            canonical, config, is_marine = identify_channel(line)
            
            if is_marine:
                if marine_added or url_line in used_urls:
                    continue
                marine_added = True
                used_urls.add(url_line)
                logo_match = re.search(r'tvg-logo="([^"]*)"', line)
                logo = logo_match.group(1) if logo_match else "https://keyframe-cdn.abcnews.com/streamprovider5.jpg"
                if not logo.endswith('.jpg') and '.jpg' not in logo:
                    logo = logo.rsplit('.', 1)[0] + '.jpg' if '.' in logo else logo + '.jpg'
                
                new_extinf = f'#EXTINF:-1 tvg-logo="{logo}" group-title="NEWS WORLD",Marine Traffic Live Map'
                output_lines.append(new_extinf)
                output_lines.append(url_line)
                print(f"  + Marine Traffic Live Map")
                continue
            
            if config and canonical:
                if canonical in used_channels:
                    continue
                used_channels.add(canonical)
                
                logo = config['logo']
                if not logo.endswith('.jpg') and '.jpg' not in logo:
                    if logo.endswith('.png') or '.png' in logo:
                        logo = logo.rsplit('.', 1)[0] + '.jpg'
                
                primary_url = config.get('primary_url', '')
                if primary_url and primary_url not in used_urls:
                    final_url = primary_url
                else:
                    final_url = url_line
                if not final_url or final_url in used_urls:
                    continue
                
                tvg_id = config['tvg_id']
                group = config['group']
                
                new_extinf = f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-logo="{logo}" group-title="{group}",{canonical}'
                output_lines.append(new_extinf)
                output_lines.append(final_url)
                used_urls.add(final_url)
                print(f"  + {canonical} (tvg-id={tvg_id})")
            continue
        
        if line and not line.startswith('#'):
            continue
    
    with open(M3U_OUT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(output_lines) + '\n')
    
    print(f"  Linhas finais: {len(output_lines)}")
    print(f"  Canais unicos: {len(used_channels)}")
    return output_lines

def test_urls(m3u_lines):
    """Testa se as URLs dos streams funcionam"""
    print("\n=== TESTANDO URLS ===")
    results = {}
    for i, line in enumerate(m3u_lines):
        if line.startswith('http://') or line.startswith('https://'):
            try:
                resp = requests.head(line, timeout=10, allow_redirects=True,
                    headers={'User-Agent': 'Mozilla/5.0'})
                status = resp.status_code
                print(f"  {status} {line[:80]}...")
                results[line] = status < 400
            except Exception as e:
                print(f"  FAIL {line[:80]}... ({e})")
                results[line] = False
    return results

def test_epg_coverage():
    """Testa se o EPG tem programacao para hoje, amanha e depois de amanha"""
    print("\n=== TESTANDO COBERTURA DO EPG ===")
    
    root, chans, progs = load_epg(EPG_OUT)
    if root is None:
        print("  ERRO: EPG nao encontrado!")
        return False
    
    today_str = datetime.now().strftime('%Y%m%d')
    tomorrow_str = (datetime.now() + timedelta(days=1)).strftime('%Y%m%d')
    dayafter_str = (datetime.now() + timedelta(days=2)).strftime('%Y%m%d')
    
    count_today = sum(1 for p in progs if p.get('start', '')[:8] == today_str)
    count_tomorrow = sum(1 for p in progs if p.get('start', '')[:8] == tomorrow_str)
    count_dayafter = sum(1 for p in progs if p.get('start', '')[:8] == dayafter_str)
    
    print(f"  Programas hoje ({today_str}): {count_today}")
    print(f"  Programas amanha ({tomorrow_str}): {count_tomorrow}")
    print(f"  Programas depois ({dayafter_str}): {count_dayafter}")
    
    ok = count_today > 0 and count_tomorrow > 0
    print(f"  EPG {'OK' if ok else 'INCOMPLETO'}")
    return ok

def test_epg_online():
    """Testa EPG online via web"""
    print("\n=== TESTANDO EPG ONLINE ===")
    epg_url = "https://tvit.leicaflorianrobert.dev/epg/list.xml"
    try:
        resp = requests.get(epg_url, timeout=30, 
            headers={'User-Agent': 'Mozilla/5.0', 'Accept-Encoding': 'gzip'})
        print(f"  Status: {resp.status_code}, Tamanho: {len(resp.content)}")
        if resp.status_code == 200:
            print(f"  Conteudo: {resp.content[:200]}")
            return True
    except Exception as e:
        print(f"  Erro: {e}")
    return False

def verify_epg_xml_structure():
    """Verifica estrutura do XML gerado"""
    print("\n=== VERIFICANDO ESTRUTURA XML ===")
    try:
        with gzip.open(EPG_OUT, 'rb') as f:
            content = f.read()
        root = ET.fromstring(content)
        channels = root.findall('channel')
        programs = root.findall('programme')
        print(f"  Canais: {len(channels)}")
        print(f"  Programas: {len(programs)}")
        for ch in channels:
            name = ch.find('display-name')
            icon = ch.find('icon')
            icon_src = icon.get('src', '') if icon is not None else ''
            print(f"    Canal: {ch.get('id')} -> {name.text if name is not None else 'N/A'}")
        return True
    except Exception as e:
        print(f"  Erro: {e}")
        return False

def main():
    print("=" * 60)
    print("CORRECAO COMPLETA LISTA5.M3U - 2026")
    print("=" * 60)
    
    merge_epgs()
    verify_epg_xml_structure()
    test_epg_coverage()
    
    m3u_lines = fix_m3u()
    
    test_urls(m3u_lines)
    
    print("\n" + "=" * 60)
    print("RESUMO FINAL")
    print("=" * 60)
    print(f"  M3U: {M3U_OUT}")
    print(f"  EPG: {EPG_OUT}")
    
    with open(M3U_OUT, 'r') as f:
        content = f.read()
    channel_count = content.count('#EXTINF:')
    url_count = sum(1 for l in content.split('\n') if l.startswith('http'))
    print(f"  Canais no M3U: {channel_count}")
    print(f"  URLs no M3U: {url_count}")
    
    print("\n  EPGs utilizados:")
    print(f"    - lista5_epg.xml.gz (local)")
    print(f"    - EPGFULL.xml.gz (local)")

if __name__ == "__main__":
    main()
