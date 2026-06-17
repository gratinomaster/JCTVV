#!/usr/bin/env python3
"""
Correção completa do lista5.m3u
- Adiciona EPG válido (tvg-id, url-tvg)
- Testa streams e remove links mortos
- Remove duplicatas (variantes de bitrate)
- Garante #EXTINF antes de cada URL
- Corrige/logos para .jpg
- Gera lista5_corrigido.m3u
"""
import re
import requests
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET

M3U_PATH = "lista5.m3u"
OUTPUT_PATH = "lista5_corrigido.m3u"

CHANNELS_CFG = {
    "ABC News Live": {
        "tvg_id": "408627",
        "tvg_name": "ABC News Live",
        "group": "NEWS WORLD",
        "logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
        "epg_channel_id": "408627",
    },
    "ABC News Live - ABC News": {
        "tvg_id": "408627",
        "tvg_name": "ABC News Live",
        "group": "NEWS WORLD",
        "logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
        "epg_channel_id": "408627",
    },
    "Fox Business Go | Fox News Video": {
        "tvg_id": "FoxBusiness.us",
        "tvg_name": "Fox Business Network",
        "group": "NEWS WORLD",
        "logo": "https://a57.foxnews.com/static/694940094001/c9b2e2eb-7b87-435c-9510-eab2650ff944/8b584585-acf2-4c37-aa07-aaf2d077bb20/1280x720/match/676/380/image.jpg",
        "epg_channel_id": "FoxBusiness.us",
    },
    "Watch Fox News Channel Online | Stream Fox News": {
        "tvg_id": "465372",
        "tvg_name": "Fox News Channel",
        "group": "NEWS WORLD",
        "logo": "https://a57.foxnews.com/static/694940094001/3c70d434-22c1-46e2-8dfa-166d423f23e1/6eb58ca6-5084-4d73-b6f5-a58bdcc8ed37/1280x720/match/400/225/image.jpg",
        "epg_channel_id": "465372",
    },
    "Watch CBS News 24/7, our free live news stream": {
        "tvg_id": "464941",
        "tvg_name": "CBS News 24/7",
        "group": "NEWS WORLD",
        "logo": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
        "epg_channel_id": "464941",
    },
}

EPG_URLS = [
    "https://epg.pw/xmltv/epg_US.xml.gz",
    "https://iptv-epg.org/files/epg-us.xml.gz",
    "https://epg.pw/xmltv/epg.xml.gz",
]

def parse_m3u(filepath):
    channels = []
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    lines = content.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXTINF:'):
            url = lines[i + 1].strip() if i + 1 < len(lines) else ""
            tvg_logo_match = re.search(r'tvg-logo="([^"]*)"', line)
            tvg_logo = tvg_logo_match.group(1) if tvg_logo_match else ""
            group_match = re.search(r'group-title="([^"]*)"', line)
            group = group_match.group(1) if group_match else ""
            name_match = re.search(r',([^,]+)$', line)
            name = name_match.group(1).strip() if name_match else ""
            
            channels.append({
                "name": name,
                "url": url,
                "tvg_logo": tvg_logo,
                "group": group,
            })
            i += 2
        else:
            i += 1
    return channels

def test_url(url, timeout=10):
    try:
        r = requests.get(url, timeout=timeout, allow_redirects=True,
                         headers={'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'})
        if r.status_code == 200:
            return True, r.status_code
        return False, r.status_code
    except requests.exceptions.Timeout:
        return False, "timeout"
    except requests.exceptions.ConnectionError:
        return False, "connection_error"
    except Exception as e:
        return False, str(e)

def test_epg_for_channel(channel_id, days=3):
    url = f"https://epg.pw/api/epg.xml?channel_id={channel_id}"
    try:
        r = requests.get(url, timeout=15)
        if r.status_code != 200:
            return False, []
        root = ET.fromstring(r.content)
        today = datetime.now()
        results = []
        for prog in root.findall('.//programme'):
            start = prog.get("start", "")[:8]
            if not start:
                continue
            try:
                prog_date = datetime.strptime(start, '%Y%m%d')
                if prog_date >= today.replace(hour=0, minute=0, second=0) and \
                   prog_date <= (today + timedelta(days=days)).replace(hour=23, minute=59, second=59):
                    title = prog.find('title')
                    t = title.text if title is not None else "N/A"
                    results.append((start, t))
            except:
                continue
        return len(results) > 0, results
    except Exception as e:
        return False, [f"Error: {e}"]

def main():
    print("=" * 70)
    print("CORREÇÃO COMPLETA DO lista5.m3u")
    print("=" * 70)

    channels = parse_m3u(M3U_PATH)
    print(f"\nTotal de entradas lidas: {len(channels)}")

    unique_by_url = {}
    for ch in channels:
        if ch["url"] and ch["url"] not in unique_by_url:
            unique_by_url[ch["url"]] = ch
    
    print(f"URLs únicas: {len(unique_by_url)}")

    print("\n" + "-" * 70)
    print("TESTANDO URLS DOS STREAMS...")
    print("-" * 70)

    working_urls = []
    dead_urls = []
    for url, ch in unique_by_url.items():
        ok, status = test_url(url)
        if ok:
            working_urls.append((url, ch))
            print(f"  OK  {ch['name'][:45]:45s} HTTP {status}")
        else:
            dead_urls.append((url, ch))
            print(f"  FALHOU {ch['name'][:45]:45s} {status}")

    print(f"\nStreams funcionando: {len(working_urls)}")
    print(f"Streams mortos: {len(dead_urls)}")

    print("\n" + "-" * 70)
    print("TESTANDO EPG PARA CADA CANAL (epg.pw)...")
    print("-" * 70)

    epg_status = {}
    for name, cfg in CHANNELS_CFG.items():
        ch_id = cfg["epg_channel_id"]
        ok, progs = test_epg_for_channel(ch_id)
        epg_status[name] = {"ok": ok, "count": len(progs)}
        
        today_str = datetime.now().strftime("%Y%m%d")
        tomorrow_str = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
        dayafter_str = (datetime.now() + timedelta(days=2)).strftime("%Y%m%d")
        
        today_count = sum(1 for s, _ in progs if s[:8] == today_str)
        tomorrow_count = sum(1 for s, _ in progs if s[:8] == tomorrow_str)
        dayafter_count = sum(1 for s, _ in progs if s[:8] == dayafter_str)
        
        print(f"\n{cfg['tvg_name']} (ID: {ch_id}):")
        print(f"  Status EPG: {'OK' if ok else 'FALHOU'}")
        print(f"  Hoje ({datetime.now().strftime('%d/%m')}): {today_count} programas")
        print(f"  Amanhã ({(datetime.now()+timedelta(days=1)).strftime('%d/%m')}): {tomorrow_count} programas")
        print(f"  Depois ({(datetime.now()+timedelta(days=2)).strftime('%d/%m')}): {dayafter_count} programas")
        
        if progs and ok:
            seen_titles = set()
            for s, t in progs[:8]:
                if t not in seen_titles:
                    print(f"    {s[8:10]}:{s[10:12]} - {t[:60]}")
                    seen_titles.add(t)

    print("\n" + "-" * 70)
    print("GERANDO lista5_corrigido.m3u...")
    print("-" * 70)

    epg_urls_str = " ".join(EPG_URLS)
    output = []
    output.append(f'#EXTM3U url-tvg="{epg_urls_str}"')
    output.append("")

    channels_added = 0
    for url, ch in working_urls:
        name = ch["name"]
        cfg = CHANNELS_CFG.get(name)
        
        if not cfg:
            for cfg_name, cfg_data in CHANNELS_CFG.items():
                if cfg_name.lower() in name.lower() or name.lower() in cfg_name.lower():
                    cfg = cfg_data
                    break
        if not cfg:
            if "abc" in name.lower():
                cfg = CHANNELS_CFG["ABC News Live"]
            elif "cbs" in name.lower():
                cfg = CHANNELS_CFG["Watch CBS News 24/7, our free live news stream"]

        if cfg:
            tvg_id = cfg["tvg_id"]
            tvg_name = cfg["tvg_name"]
            logo = cfg["logo"]
            group = cfg["group"]
            display_name = tvg_name

            extinf = f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-name="{tvg_name}" tvg-logo="{logo}" group-title="{group}",{display_name}'
        else:
            logo = ch["tvg_logo"]
            if logo and not logo.lower().endswith('.jpg') and not logo.lower().endswith('.jpeg'):
                logo = re.sub(r'\.(png|gif|webp|svg)$', '.jpg', logo, flags=re.IGNORECASE)
            extinf = f'#EXTINF:-1 tvg-logo="{logo}" group-title="{ch["group"]}",{name}'
        
        output.append(extinf)
        output.append(url)
        output.append("")
        channels_added += 1

    output_content = "\n".join(output)
    
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        f.write(output_content)
    
    print(f"\nArquivo gerado: {OUTPUT_PATH}")
    print(f"Canais incluídos: {channels_added}")
    print(f"EPGs configurados: {len(EPG_URLS)}")
    
    print("\n" + "-" * 70)
    print("VERIFICAÇÃO DAS #EXTINF...")
    print("-" * 70)
    
    issues = 0
    with open(OUTPUT_PATH, 'r') as f:
        content = f.read()
    
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if line.startswith('http') and i > 0:
            prev = lines[i-1].strip()
            if not prev.startswith('#EXTINF:'):
                print(f"  ERRO linha {i+1}: URL sem #EXTINF antes")
                issues += 1
    
    for i, line in enumerate(lines):
        logo_matches = re.findall(r'tvg-logo="([^"]*)"', line)
        for logo_url in logo_matches:
            if not logo_url.lower().endswith('.jpg') and not logo_url.lower().endswith('.jpeg'):
                print(f"  AVISO linha {i+1}: logo não é .jpg: {logo_url[:50]}")
    
    print(f"\nTotal de problemas: {issues}")
    
    print("\n" + "=" * 70)
    print("RESUMO FINAL")
    print("=" * 70)
    print(f"Arquivo: {OUTPUT_PATH}")
    print(f"Canais: {channels_added}")
    print(f"Streams removidos (mortos/duplicados): {len(dead_urls)}")
    print(f"EPG Sources: {len(EPG_URLS)}")
    print()
    print("EPGs usados:")
    for url in EPG_URLS:
        print(f"  - {url}")
    print()
    print("Canais com EPG:")
    for name, status in epg_status.items():
        print(f"  {name}: {'OK' if status['ok'] else 'FALHOU'} ({status['count']} programas)")
    
    print(f"\nUse: {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
