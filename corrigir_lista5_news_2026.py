#!/usr/bin/env python3
import requests
import re
import gzip
import json
from datetime import datetime, timedelta
from xml.etree import ElementTree as ET
import time

VT_API_KEY = ""

EPG_SOURCES = {
    "ABC News Live": {
        "tvg_id": "ABCWBMA.us",
        "epg_urls": [
            "https://github.com/iptv-org/epg/raw/master/sites/abcnews.com.channels.xml",
            "https://epg-usa.vesta.sx/epg/us/epg.xml.gz",
            "https://tvit.leicaflorianrobert.dev/epg/list.xml"
        ]
    },
    "Fox News": {
        "tvg_id": "FoxNewsChannel.us",
        "epg_urls": [
            "https://github.com/iptv-org/epg/raw/master/sites/foxnews.com.channels.xml",
            "https://epg-usa.vesta.sx/epg/us/epg.xml.gz",
            "https://tvit.leicaflorianrobert.dev/epg/list.xml"
        ]
    },
    "Fox Business": {
        "tvg_id": "FoxBusiness.us",
        "epg_urls": [
            "https://github.com/iptv-org/epg/raw/master/sites/foxbusiness.com.channels.xml",
            "https://epg-usa.vesta.sx/epg/us/epg.xml.gz",
            "https://tvit.leicaflorianrobert.dev/epg/list.xml"
        ]
    },
    "CBS News": {
        "tvg_id": "CBSNews.us",
        "epg_urls": [
            "https://github.com/iptv-org/epg/raw/master/sites/cbsnews.com.channels.xml",
            "https://epg-usa.vesta.sx/epg/us/epg.xml.gz",
            "https://tvit.leicaflorianrobert.dev/epg/list.xml"
        ]
    }
}

GLOBAL_EPG_URL = "https://epg-usa.vesta.sx/epg/us/epg.xml.gz"

def test_epg_url(epg_url):
    """Testa se o EPG funciona e tem programação para hoje, amanhã e depois de amanhã."""
    try:
        headers = {'Accept-Encoding': 'gzip', 'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(epg_url, timeout=60, headers=headers)
        if resp.status_code != 200:
            return None
        
        content = resp.content
        if epg_url.endswith('.gz'):
            try:
                content = gzip.decompress(content)
            except:
                pass
        
        root = ET.fromstring(content)
        today = datetime.now().date()
        tomorrow = today + timedelta(days=1)
        day_after = today + timedelta(days=2)
        
        dates_found = set()
        for programme in root.findall('.//programme'):
            start = programme.get('start', '')
            if start:
                try:
                    date = datetime.strptime(start[:8], '%Y%m%d').date()
                    dates_found.add(date)
                except:
                    pass
        
        has_today = today in dates_found
        has_tomorrow = tomorrow in dates_found
        has_day_after = day_after in dates_found
        
        if has_today or has_tomorrow:
            return {
                'ok': True,
                'today': has_today,
                'tomorrow': has_tomorrow,
                'day_after': has_day_after,
                'content': content.decode('utf-8', errors='ignore') if isinstance(content, bytes) else content
            }
        return None
    except Exception as e:
        return None

def find_best_epg():
    """Encontra o melhor EPG que funciona."""
    print("Procurando EPG válido...")
    
    epg_urls = [
        ("https://epg-usa.vesta.sx/epg/us/epg.xml.gz", "Vesta SX US"),
        ("https://tvit.leicaflorianrobert.dev/epg/list.xml", "Leica Florian"),
        ("https://github.com/iptv-org/epg/raw/master/guide/us.xml.gz", "IPTV-ORG US"),
    ]
    
    for url, name in epg_urls:
        print(f"Testando {name}: {url[:60]}...")
        result = test_epg_url(url)
        if result and result.get('ok'):
            print(f"✓ EPG encontrado: {name}")
            return url
    return None

def check_virustotal(url):
    """Verifica URL no VirusTotal (sem API key, usa API pública)."""
    try:
        public_url = "https://www.virustotal.com/api/v3/urls"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = f"url={requests.utils.quote(url)}"
        resp = requests.post(public_url, headers=headers, data=data, timeout=30)
        if resp.status_code == 200:
            result = resp.json()
            analysis_link = result.get("data", {}).get("links", {}).get("self")
            if analysis_link:
                time.sleep(3)
                analysis = requests.get(analysis_link, timeout=30)
                if analysis.status_code == 200:
                    data = analysis.json()
                    stats = data.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
                    malicious = stats.get("malicious", 0)
                    suspicious = stats.get("suspicious", 0)
                    return malicious == 0 and suspicious == 0
    except Exception as e:
        print(f"VT error: {e}")
    return True

def parse_m3u(filepath):
    channels = []
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXTINF:'):
            info = line
            next_line = lines[i+1].strip() if i+1 < len(lines) else ''
            if next_line and not next_line.startswith('#'):
                channels.append({'info': info, 'url': next_line})
                i += 2
            else:
                i += 1
        else:
            i += 1
    return channels

def extract_channel_name(info_line):
    """Extrai o nome do canal do EXTINF."""
    match = re.search(r',(.+)$', info_line)
    if match:
        return match.group(1).strip()
    return None

def fix_channel_info(info_line, tvg_id=None, epg_url=None, logo=None):
    """Corrige o EXTINF com EPG e logo."""
    new_info = info_line
    
    if tvg_id and epg_url:
        new_info = re.sub(r'tvg-id="[^"]*"', '', new_info)
        new_info = re.sub(r'x-tvg-url="[^"]*"', '', new_info)
        new_info = re.sub(r'\s+', ' ', new_info).strip()
        if not new_info.endswith(' '):
            new_info += ' '
        new_info = f'{new_info}tvg-id="{tvg_id}" x-tvg-url="{epg_url}"'
    
    if logo:
        new_info = re.sub(r'tvg-logo="[^"]*"', f'tvg-logo="{logo}"', new_info)
    
    return new_info

def get_channel_epg_info(name):
    """Retorna info de EPG para o canal."""
    name_lower = name.lower()
    
    if 'abc news' in name_lower:
        return EPG_SOURCES.get("ABC News Live")
    elif 'fox news' in name_lower and 'business' not in name_lower:
        return EPG_SOURCES.get("Fox News")
    elif 'fox business' in name_lower:
        return EPG_SOURCES.get("Fox Business")
    elif 'cbs news' in name_lower:
        return EPG_SOURCES.get("CBS News")
    
    return None

def fix_logo_url(logo):
    """Garante que o logo seja .jpg."""
    if not logo:
        return None
    
    if 'imgur.com' in logo:
        return None
    
    logo_lower = logo.lower()
    if not logo_lower.endswith('.jpg') and not logo_lower.endswith('.jpeg'):
        if '.png' in logo_lower:
            return logo.replace('.png', '.jpg').replace('.PNG', '.jpg')
        elif '.webp' in logo_lower:
            return logo.replace('.webp', '.jpg').replace('.WEBP', '.jpg')
        elif '.svg' in logo_lower:
            return None
    
    return logo

def get_default_logo(name):
    """Retorna logo padrão para o canal."""
    name_lower = name.lower()
    
    if 'abc news' in name_lower:
        return "https://keyframe-cdn.abcnews.com/streamprovider11.jpg"
    elif 'fox news' in name_lower and 'business' not in name_lower:
        return "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/15de0523-3be4-4a9a-8159-7020114e7036/b6ff623a-26d6-4fd9-8bb8-0856adbf38ce/1280x720/match/676/380/image.jpg"
    elif 'fox business' in name_lower:
        return "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/c9b2e2eb-7b87-435c-9510-eab2650ff944/8b584585-acf2-4c37-aa07-aaf2d077bb20/1280x720/match/676/380/image.jpg"
    elif 'cbs news' in name_lower:
        return "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg"
    
    return None

def main():
    print("=" * 70)
    print("CORREÇÃO lista5.m3u")
    print("=" * 70)
    
    epg_url = find_best_epg()
    if not epg_url:
        print("ERRO: Nenhum EPG válido encontrado")
        return
    
    print(f"\nUsando EPG: {epg_url}")
    
    channels = parse_m3u('lista5.m3u')
    print(f"\nCanais encontrados: {len(channels)}")
    
    seen_urls = set()
    result_channels = []
    removed_urls = []
    
    for ch in channels:
        url = ch['url']
        info = ch['info']
        name = extract_channel_name(info)
        
        if url in seen_urls:
            continue
        
        logo_match = re.search(r'tvg-logo="([^"]+)"', info)
        current_logo = logo_match.group(1) if logo_match else None
        
        if current_logo and 'imgur.com' in current_logo:
            current_logo = None
        
        fixed_logo = fix_logo_url(current_logo)
        if not fixed_logo:
            fixed_logo = get_default_logo(name)
        
        epg_info = get_channel_epg_info(name)
        if epg_info:
            fixed_info = fix_channel_info(info, epg_info['tvg_id'], epg_url, fixed_logo)
        else:
            fixed_info = fix_channel_info(info, None, None, fixed_logo)
            fixed_info = re.sub(r'tvg-id="[^"]*"', '', fixed_info)
            fixed_info = re.sub(r'x-tvg-url="[^"]*"', '', fixed_info)
            fixed_info = re.sub(r'\s+', ' ', fixed_info).strip()
        
        result_channels.append({
            'info': fixed_info,
            'url': url,
            'name': name,
            'logo': fixed_logo
        })
        seen_urls.add(url)
    
    print(f"Canais após remover duplicatas: {len(result_channels)}")
    
    output = "#EXTM3U\n"
    for ch in result_channels:
        output += ch['info'] + "\n"
        output += ch['url'] + "\n"
    
    with open('lista5.m3u', 'w', encoding='utf-8') as f:
        f.write(output)
    
    print(f"\n✓ Arquivo lista5.m3u atualizado")
    print(f"  - {len(result_channels)} canais")
    print(f"  - EPG: {epg_url}")
    
    print("\n" + "=" * 70)
    print("RESUMO DOS CANAIS")
    print("=" * 70)
    for ch in result_channels:
        logo_status = "✓" if ch['logo'] else "✗ SEM LOGO"
        print(f"  {ch['name']}: {logo_status}")

if __name__ == "__main__":
    main()
