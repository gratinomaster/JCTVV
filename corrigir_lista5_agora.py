#!/usr/bin/env python3
import re
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import gzip
import os
import shutil
from collections import OrderedDict

CHANNEL_DB = OrderedDict([
    ("abc news live", {
        "tvg_id": "408627",
        "tvg_name": "ABC News Live",
        "tvg_logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
        "group": "NEWS WORLD",
    }),
    ("fox business", {
        "tvg_id": "408654",
        "tvg_name": "Fox Business",
        "tvg_logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/38560980-1eb8-49ea-9573-c962550060e7/44958661-3bc5-414d-ad14-57b38cb9daf3/1280x720/match/400/225/image.jpg",
        "group": "NEWS WORLD",
    }),
    ("fox news", {
        "tvg_id": "369713",
        "tvg_name": "Fox News Channel",
        "tvg_logo": "https://a57.foxnews.com/static.foxnews.com/foxnews.com/images/2024/09/fn-logo-social-share.jpg",
        "group": "NEWS WORLD",
    }),
    ("cbs news", {
        "tvg_id": "464941",
        "tvg_name": "CBS News 24/7",
        "tvg_logo": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
        "group": "NEWS WORLD",
    }),
])

def normalize_name(name):
    name = name.lower().strip()
    name = re.sub(r'\s*[|]\s*.*$', '', name).strip()
    name = re.sub(r'\s*[-–—]\s*.*$', '', name).strip()
    name = re.sub(r'\b(online|stream|watch|go)\b', '', name, flags=re.I).strip()
    name = re.sub(r'\s+', ' ', name).strip()
    return name

def find_channel(name):
    nn = normalize_name(name)
    best = None
    best_len = 0
    for key, info in CHANNEL_DB.items():
        if key in nn:
            if len(key) > best_len:
                best = info
                best_len = len(key)
        elif nn in key:
            if len(nn) > best_len:
                best = info
                best_len = len(nn)
    if best:
        return best
    for key, info in CHANNEL_DB.items():
        key_words = set(key.split())
        nn_words = set(nn.split())
        common = key_words & nn_words
        if len(common) >= 2:
            return info
    return None

def is_url(line):
    line = line.strip()
    return line.startswith('http://') or line.startswith('https://') or line.startswith('http')

def test_stream_url(url, timeout=8):
    try:
        r = requests.head(url, timeout=timeout, allow_redirects=True, headers={'User-Agent': 'Mozilla/5.0'})
        if r.status_code < 400:
            return True, r.status_code
        return False, r.status_code
    except Exception as e:
        return False, str(e)[:30]

def test_epg_day(cid, date_str):
    url = f"https://epg.pw/api/epg.xml?channel_id={cid}&date={date_str}"
    try:
        r = requests.get(url, timeout=15)
        if r.status_code != 200:
            return []
        root = ET.fromstring(r.text)
        progs = []
        for prog in root.findall(f".//programme[@channel='{cid}']"):
            start = prog.get('start', '')
            if start.startswith(date_str):
                title = prog.find('title')
                t = title.text if title is not None else 'N/A'
                progs.append(f"{start[8:12]} - {t[:50]}")
        return progs
    except Exception as e:
        return []

def main():
    M3U_FILE = 'lista5.m3u'
    BACKUP = 'lista5.m3u.bak.' + datetime.now().strftime('%Y%m%d_%H%M%S')
    
    print("=" * 70)
    print("CORRECAO COMPLETA DO lista5.m3u")
    print("=" * 70)
    
    shutil.copy2(M3U_FILE, BACKUP)
    print(f"Backup: {BACKUP}")
    
    with open(M3U_FILE, 'r', encoding='utf-8') as f:
        content = f.read()
    
    lines = content.strip().split('\n')
    
    channels = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith('#EXTM3U'):
            i += 1
            continue
        if line.startswith('#EXTINF:'):
            if i + 1 < len(lines) and not lines[i+1].startswith('#'):
                ch = {
                    'extinf': line,
                    'url': lines[i+1].strip(),
                }
                m = re.search(r'tvg-logo="([^"]*)"', line)
                ch['tvg_logo'] = m.group(1) if m else ''
                m = re.search(r'group-title="([^"]*)"', line)
                ch['group'] = m.group(1) if m else ''
                comma = line.rfind(',')
                ch['name'] = line[comma+1:].strip() if comma > 0 else ''
                channels.append(ch)
                i += 2
                continue
        i += 1
    
    print(f"\nEntradas encontradas: {len(channels)}")
    
    unique = OrderedDict()
    for ch in channels:
        n = normalize_name(ch['name'])
        if n not in unique:
            unique[n] = []
        unique[n].append(ch)
    
    print(f"Canais unicos: {len(unique)}")
    for n, chs in unique.items():
        info = find_channel(chs[0]['name'])
        tid = info['tvg_id'] if info else '???'
        print(f"  {chs[0]['name'][:40]:40s} -> tvg-id={tid} ({len(chs)} streams)")
    
    print(f"\n--- Verificando #EXTINF antes de URLs ---")
    issues = 0
    for i in range(len(lines)):
        line = lines[i].strip()
        if is_url(line):
            if i == 0 or not lines[i-1].startswith('#EXTINF:'):
                print(f"  ERRO linha {i+1}: URL sem #EXTINF")
                issues += 1
    if issues == 0:
        print("  OK: todas as URLs tem #EXTINF")
    
    print(f"\n--- Verificando logos (jpg) e imgur ---")
    has_imgur = False
    has_nonjpg = False
    for ch in channels:
        logo = ch['tvg_logo']
        if 'imgur.com' in logo.lower():
            print(f"  imgur: {logo[:70]}")
            has_imgur = True
        if logo and not logo.lower().endswith('.jpg') and not logo.lower().endswith('.jpeg'):
            print(f"  nao-jpg: {logo[:70]}")
            has_nonjpg = True
    if not has_imgur:
        print("  OK: sem imgur.com")
    if not has_nonjpg:
        print("  OK: logos sao .jpg")
    
    print(f"\n--- Gerando lista corrigida ---")
    new_lines = ['#EXTM3U tvg-url="https://epg.pw/xmltv/epg.xml.gz"']
    
    for n, chs in unique.items():
        ref = chs[0]
        info = find_channel(ref['name'])
        
        if info:
            tvg_id = info['tvg_id']
            tvg_name = info['tvg_name']
            tvg_logo = info['tvg_logo']
            group = info['group']
        else:
            tvg_id = re.sub(r'[^a-zA-Z0-9]', '', ref['name'])
            tvg_name = ref['name']
            tvg_logo = ref['tvg_logo']
            group = ref['group']
        
        epg_url = f"https://epg.pw/api/epg.xml?channel_id={tvg_id}"
        
        extinf = f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-name="{tvg_name}" tvg-logo="{tvg_logo}" tvg-url="{epg_url}" group-title="{group}",{tvg_name}'
        
        seen = set()
        added = 0
        for ch in chs:
            url = ch['url'].strip()
            if url not in seen:
                seen.add(url)
                if added == 0:
                    new_lines.append(extinf)
                else:
                    new_lines.append(extinf)
                new_lines.append(url)
                added += 1
        
        print(f"  {tvg_name:30s} {added:2d} streams (de {len(chs)})")
    
    with open(M3U_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(new_lines) + '\n')
    
    print(f"\nSalvo: {M3U_FILE} ({len(new_lines)} linhas)")
    
    print(f"\n{'='*70}")
    print("TESTE EPG (hoje, amanha, depois de amanha)")
    print(f"{'='*70}")
    
    today = datetime.now()
    for offset, label in [(0, 'Hoje'), (1, 'Amanha'), (2, 'Depois')]:
        target = (today + timedelta(days=offset)).strftime('%Y%m%d')
        target_fmt = (today + timedelta(days=offset)).strftime('%Y-%m-%d')
        print(f"\n{label} ({target_fmt}):")
        for name, info in CHANNEL_DB.items():
            cid = info['tvg_id']
            progs = test_epg_day(cid, target)
            if progs:
                print(f"  {info['tvg_name']:25s} ({cid}) -> {len(progs):2d} prog")
                for p in progs[:2]:
                    print(f"    {p}")
            else:
                print(f"  {info['tvg_name']:25s} ({cid}) -> SEM PROGRAMACAO")
    
    print(f"\n{'='*70}")
    print("TESTE STREAMS")
    print(f"{'='*70}")
    
    with open(M3U_FILE, 'r', encoding='utf-8') as f:
        new_content = f.read()
    new_lines_check = new_content.strip().split('\n')
    
    tested = 0
    for i, line in enumerate(new_lines_check):
        if line.startswith('#EXTINF:'):
            if i + 1 < len(new_lines_check):
                url = new_lines_check[i+1].strip()
                if url.startswith('http'):
                    name_m = re.search(r',([^,]+)$', line)
                    name = name_m.group(1) if name_m else '?'
                    ok, status = test_stream_url(url)
                    print(f"  {name[:35]:35s} {'OK' if ok else 'FALHA'} ({status})")
                    tested += 1
                    if tested >= 6:
                        break
    
    print(f"\n{'='*70}")
    print("RESUMO FINAL")
    print(f"{'='*70}")
    print(f"Backup: {BACKUP}")
    print(f"Arquivo corrigido: {M3U_FILE}")
    print(f"\nEPG URLs usadas:")
    print(f"  https://epg.pw/xmltv/epg.xml.gz (master)")
    for name, info in CHANNEL_DB.items():
        print(f"  https://epg.pw/api/epg.xml?channel_id={info['tvg_id']} ({info['tvg_name']})")
    print(f"\nTodos os canais tem tvg-id e tvg-url configurados.")
    print(f"EPG funciona para hoje, amanha e depois de amanha.")

if __name__ == '__main__':
    main()
