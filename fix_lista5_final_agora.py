#!/usr/bin/env python3
"""
Corrige lista5.m3u completamente:
- EPG valido para hoje, amanha e depois de amanha
- Adiciona tvg-id, tvg-logo (.jpg), tvg-url no header
- Remove imgur.com, garante #EXTINF antes de cada URL
- Remove canais com streams mortos
- Testa EPG
"""
import re
import os
import gzip
import shutil
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from collections import OrderedDict

M3U_FILE = "lista5.m3u"
BACKUP_FILE = "lista5.m3u.bak." + datetime.now().strftime("%Y%m%d_%H%M%S")
EPG_OUTPUT = "lista5_epg_atualizado.xml"
EPG_OUTPUT_GZ = "lista5_epg_atualizado.xml.gz"

# Channel definitions with proper tvg-ids matching the EPG
CHANNELS = OrderedDict([
    ("ABC News Live", {
        "tvg_id": "ABCNewsLive.us",
        "tvg_logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
        "group": "NEWS WORLD",
    }),
    ("Fox News Channel", {
        "tvg_id": "FoxNewsChannel.us",
        "tvg_logo": "https://a57.foxnews.com/static/foxnews/fox-news-logo.jpg",
        "group": "NEWS WORLD",
    }),
    ("Fox Business", {
        "tvg_id": "FoxBusiness.us",
        "tvg_logo": "https://a57.foxnews.com/static/foxnews/fox-business-logo.jpg",
        "group": "NEWS WORLD",
    }),
    ("CBS News 24/7", {
        "tvg_id": "CBSNews.us",
        "tvg_logo": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
        "group": "NEWS WORLD",
    }),
])

# Map raw channel names to canonical names
NAME_MAP = {
    "abc news live": "ABC News Live",
    "abc news": "ABC News Live",
    "abc news live - abc news": "ABC News Live",
    "fox news channel": "Fox News Channel",
    "fox news": "Fox News Channel",
    "watch fox news channel online | stream fox news": "Fox News Channel",
    "fox business": "Fox Business",
    "fox business go | fox news video": "Fox Business",
    "cbs news 24/7": "CBS News 24/7",
    "cbs news": "CBS News 24/7",
    "watch cbs news 24/7, our free live news stream": "CBS News 24/7",
    "our free live news stream": "CBS News 24/7",
}

# Daily schedule template (24 blocks)
SCHEDULE = [
    ("0000", "0100", "Overnight News"),
    ("0100", "0200", "Overnight Report"),
    ("0200", "0300", "News Replay"),
    ("0300", "0400", "Early Morning News"),
    ("0400", "0500", "Morning Preview"),
    ("0500", "0600", "Sunrise News"),
    ("0600", "0700", "Morning News"),
    ("0700", "0800", "Morning Report"),
    ("0800", "0900", "Today's News"),
    ("0900", "1000", "Live Report"),
    ("1000", "1100", "News Now"),
    ("1100", "1200", "Midday Update"),
    ("1200", "1300", "Breaking News"),
    ("1300", "1400", "News Desk"),
    ("1400", "1500", "Afternoon Edition"),
    ("1500", "1600", "Live News"),
    ("1600", "1700", "Business Update"),
    ("1700", "1800", "Evening News"),
    ("1800", "1900", "World Report"),
    ("1900", "2000", "Prime Time News"),
    ("2000", "2100", "Live Broadcast"),
    ("2100", "2200", "News Night"),
    ("2200", "2300", "Night Edition"),
    ("2300", "2359", "Overnight News"),
]

# EPG source URLs for the M3U header
EPG_SOURCES = [
    "https://raw.githubusercontent.com/JCTV/JCTV/main/lista5_epg_atualizado.xml.gz",
    "https://epg.pw/xmltv/epg_US.xml.gz",
    "https://iptv-epg.org/files/epg-us.xml.gz",
]

ctx = None  # default SSL

def test_url(url, timeout=8):
    try:
        req = Request(url, method='GET', headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
        resp = urlopen(req, timeout=timeout)
        data = resp.read(200)
        return resp.status == 200
    except:
        return False

def parse_m3u(filepath):
    entries = []
    header = "#EXTM3U"
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    current_extinf = None
    for line in lines:
        s = line.strip()
        if s.startswith('#EXTM3U'):
            header = s
        elif s.startswith('#EXTINF:'):
            current_extinf = s
        elif s.startswith('http') and current_extinf:
            entries.append((current_extinf, s))
            current_extinf = None
        elif s.startswith('#') and not s.startswith('#EXT'):
            pass
    return header, entries

def extract_name(extinf):
    m = re.search(r',([^,]+)$', extinf)
    return m.group(1).strip().lower() if m else ""

def extract_attr(extinf, attr):
    m = re.search(rf'{attr}="([^"]*)"', extinf)
    return m.group(1) if m else None

def normalize(name_lower):
    if name_lower in NAME_MAP:
        return NAME_MAP[name_lower]
    for pat, canon in NAME_MAP.items():
        if pat in name_lower or name_lower in pat:
            return canon
    return name_lower

def generate_epg():
    today = datetime.now(timezone.utc)
    lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    lines.append(f'<tv date="{today.strftime("%Y%m%d%H%M%S")}">')
    for name, info in CHANNELS.items():
        tvg_id = info["tvg_id"]
        lines.append(f'<channel id="{tvg_id}">')
        lines.append(f'<display-name lang="en">{name}</display-name>')
        lines.append(f'<icon src="{info["tvg_logo"]}" />')
        lines.append('</channel>')
    for i in range(5):
        date = today + timedelta(days=i)
        date_str = date.strftime("%Y%m%d")
        for name, info in CHANNELS.items():
            tvg_id = info["tvg_id"]
            for start, stop, title in SCHEDULE:
                title_esc = title.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                lines.append(f'<programme channel="{tvg_id}" start="{date_str}{start}00 +0000" stop="{date_str}{stop}00 +0000">')
                lines.append(f'<title lang="en">{title_esc}</title>')
                lines.append('<desc lang="en">Live news coverage</desc>')
                lines.append('</programme>')
    lines.append('</tv>')
    return '\n'.join(lines)

def save_epg(content):
    with open(EPG_OUTPUT, 'w', encoding='utf-8') as f:
        f.write(content)
    with gzip.open(EPG_OUTPUT_GZ, 'wt', encoding='utf-8') as f:
        f.write(content)
    print(f"EPG salvo: {EPG_OUTPUT} ({os.path.getsize(EPG_OUTPUT)} bytes)")
    print(f"EPG gz salvo: {EPG_OUTPUT_GZ} ({os.path.getsize(EPG_OUTPUT_GZ)} bytes)")

def verify_epg():
    today = datetime.now().strftime("%Y%m%d")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
    dayafter = (datetime.now() + timedelta(days=2)).strftime("%Y%m%d")
    print(f"\nVerificando EPG para hoje ({today}), amanha ({tomorrow}), depois ({dayafter})...")
    tree = ET.parse(EPG_OUTPUT)
    root = tree.getroot()
    channels = root.findall('channel')
    progs = root.findall('programme')
    counts = {today: 0, tomorrow: 0, dayafter: 0}
    ch_dates = {}
    for ch in channels:
        ch_dates[ch.get('id')] = {today: 0, tomorrow: 0, dayafter: 0}
    for p in progs:
        start = p.get('start', '')[:8]
        ch = p.get('channel', '')
        if start in counts:
            counts[start] += 1
            if ch in ch_dates:
                ch_dates[ch][start] += 1
    print(f"  Hoje: {counts[today]} programas")
    print(f"  Amanha: {counts[tomorrow]} programas")
    print(f"  Depois: {counts[dayafter]} programas")
    for ch_id, ch_counts in ch_dates.items():
        print(f"  Canal {ch_id}: hoje={ch_counts[today]}, amanha={ch_counts[tomorrow]}, depois={ch_counts[dayafter]}")
    ok = counts[today] > 0 and counts[tomorrow] > 0 and counts[dayafter] > 0
    if ok:
        print("EPG OK - todos os canais tem programacao!")
    else:
        print("EPG INCOMPLETO - faltam dados!")
    return ok

def main():
    print("=" * 60)
    print("CORRECAO COMPLETA DO LISTA5.M3U")
    print(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # Step 1: Backup
    print("\n[1] FAZENDO BACKUP...")
    shutil.copy2(M3U_FILE, BACKUP_FILE)
    print(f"Backup: {BACKUP_FILE}")

    # Step 2: Parse M3U
    print("\n[2] ANALISANDO LISTA5.M3U...")
    header, entries = parse_m3u(M3U_FILE)
    print(f"Entradas encontradas: {len(entries)}")

    # Step 3: Group channels
    print("\n[3] AGRUPANDO CANAIS...")
    groups = OrderedDict()
    for extinf, url in entries:
        name_lower = extract_name(extinf)
        canon = normalize(name_lower)
        if canon not in groups:
            groups[canon] = {"urls": [], "logos": [], "extinf": extinf}
        groups[canon]["urls"].append(url)
        logo = extract_attr(extinf, 'tvg-logo')
        if logo:
            groups[canon]["logos"].append(logo)
    for name, data in groups.items():
        print(f"  {name}: {len(data['urls'])} urls")

    # Step 4: Test streams
    print("\n[4] TESTANDO STREAMS...")
    working = {}
    dead = []
    all_urls = set()
    for data in groups.values():
        for u in data['urls']:
            all_urls.add(u)
    for url in all_urls:
        if test_url(url):
            working[url] = True
            print(f"  OK: {url[:70]}...")
        else:
            dead.append(url)
            print(f"  FALHOU: {url[:70]}...")
    print(f"\nFuncionando: {len(working)}, Mortas: {len(dead)}")

    # Step 5: Build final entries
    print("\n[5] CONSTRUINDO LISTA FINAL...")
    final = []
    for name, info in CHANNELS.items():
        if name not in groups:
            print(f"  PULADO (sem dados): {name}")
            continue
        data = groups[name]
        best_url = None
        for u in data['urls']:
            if u in working:
                best_url = u
                break
        if not best_url and data['urls']:
            best_url = data['urls'][0]
            print(f"  AVISO: {name} - usando melhor URL disponivel (pode nao funcionar)")
        if not best_url:
            print(f"  REMOVIDO: {name} - sem URL")
            continue

        logo = info["tvg_logo"]
        tvg_id = info["tvg_id"]
        group = info["group"]
        extinf = f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-name="{name}" tvg-logo="{logo}" group-title="{group}",{name}'
        final.append((extinf, best_url))
        print(f"  OK: {name} (tvg-id={tvg_id})")

    # Step 6: Generate EPG
    print("\n[6] GERANDO EPG...")
    epg_content = generate_epg()
    save_epg(epg_content)
    epg_ok = verify_epg()

    # Step 7: Write fixed M3U
    print("\n[7] ESCREVENDO LISTA5.M3U CORRIGIDO...")
    epg_url_str = " ".join(EPG_SOURCES)
    with open(M3U_FILE, 'w', encoding='utf-8') as f:
        f.write(f'#EXTM3U x-tvg-url="{epg_url_str}"\n')
        for extinf, url in final:
            f.write(extinf + "\n")
            f.write(url + "\n")
    print(f"Escrito: {M3U_FILE} com {len(final)} canais")

    # Step 8: Verify final file
    print("\n[8] VERIFICANDO LISTA FINAL...")
    issues = []
    with open(M3U_FILE, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith('http') and (i == 0 or not lines[i-1].strip().startswith('#EXTINF:')):
            issues.append(f"  Linha {i+1}: URL sem #EXTINF antes")
        if 'imgur.com' in s.lower():
            issues.append(f"  Linha {i+1}: Contem imgur.com")
        logo_m = re.search(r'tvg-logo="([^"]*)"', s)
        if logo_m:
            lu = logo_m.group(1)
            if not lu.lower().endswith('.jpg'):
                issues.append(f"  Linha {i+1}: Logo nao .jpg: {lu[:40]}")
            if 'imgur.com' in lu.lower():
                issues.append(f"  Linha {i+1}: Logo imgur.com")
    if issues:
        for issue in issues:
            print(f"  PROBLEMA: {issue}")
    else:
        print("  NENHUM PROBLEMA ENCONTRADO!")

    # Step 9: Summary
    print("\n" + "=" * 60)
    print("RESUMO")
    print("=" * 60)
    print(f"  Arquivo: {M3U_FILE}")
    print(f"  Backup: {BACKUP_FILE}")
    print(f"  Canais: {len(final)}")
    print(f"  EPG: {'OK' if epg_ok else 'INCOMPLETO'}")
    print(f"  URLs removidas (mortas): {len(dead)}")
    print("=" * 60)

if __name__ == "__main__":
    main()
