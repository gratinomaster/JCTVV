#!/usr/bin/env python3
import requests
import json
import hashlib
import time
import re
from urllib.parse import quote
from datetime import datetime, timedelta

VT_API_KEY = ""

EPG_URLS = {
    "usa_news": "https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.xml.gz",
    "epg_hub": "https://epg.abb牜.com/epg_data/abb牜-us.xml.gz",
}

CHANNEL_EPG_IDS = {
    "ABC News Live": "ABCNewsLive.us",
    "ABC News": "ABCNewsLive.us",
    "ABC": "ABCNewsLive.us",
    "GMA": "ABCNewsLive.us",
    "Fox News": "FoxNewsChannel.us",
    "FoxBusiness": "FoxBusinessNetwork.us",
    "Fox Business": "FoxBusinessNetwork.us",
    "CBS News": "CBSNewsNetwork.us",
    "CBS": "CBSNewsNetwork.us",
}

LOGO_ALTERNATIVES = {
    "abcnews.com": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/63/ABC_logo_2023.svg/512px-ABC_logo_2023.svg.png",
    "foxnews.com": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/60/Fox_News_Channel_logo.svg/512px-Fox_News_Channel_logo.svg.png",
    "cbsnews.com": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5d/CBS_News_Logo.svg/512px-CBS_News_Logo.svg.png",
    "imgur.com": None,
}

SAFE_LOGOS = {
    "ABC News Live": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/63/ABC_logo_2023.svg/200px-ABC_logo_2023.svg.png",
    "ABC News": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/63/ABC_logo_2023.svg/200px-ABC_logo_2023.svg.png",
    "GMA": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6c/ABC_World_News_Tonight_Logo.svg/200px-ABC_World_News_Tonight_Logo.svg.png",
    "Fox News": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/60/Fox_News_Channel_logo.svg/200px-Fox_News_Channel_logo.svg.png",
    "Fox Business": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0c/Fox_Business.svg/200px-Fox_Business.svg.png",
    "CBS News": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5d/CBS_News_Logo.svg/200px-CBS_News_Logo.svg.png",
}

def get_safe_logo(channel_name, current_logo):
    for key, safe_url in SAFE_LOGOS.items():
        if key.lower() in channel_name.lower():
            return safe_url
    if current_logo and "imgur.com" in current_logo.lower():
        return None
    return current_logo

def get_epg_id(channel_name):
    for key, epg_id in CHANNEL_EPG_IDS.items():
        if key.lower() in channel_name.lower():
            return epg_id
    return None

def check_virustotal(url):
    try:
        url_hash = hashlib.md5(url.encode()).hexdigest()
        api_url = f"https://www.virustotal.com/api/v3/urls/{url_hash}"
        headers = {"x-apikey": VT_API_KEY} if VT_API_KEY else {}
        
        if not VT_API_KEY:
            try:
                public_url = "https://www.virustotal.com/api/v3/urls"
                response = requests.post(public_url, 
                                       headers={"Content-Type": "application/x-www-form-urlencoded"},
                                       data=f"url={quote(url)}",
                                       timeout=60)
                if response.status_code == 200:
                    result = response.json()
                    analysis_link = result.get("data", {}).get("links", {}).get("self")
                    if analysis_link:
                        time.sleep(3)
                        analysis = requests.get(analysis_link, headers={"x-apikey": VT_API_KEY} if VT_API_KEY else {}, timeout=60)
                        if analysis.status_code == 200:
                            data = analysis.json()
                            stats = data.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
                            malicious = stats.get("malicious", 0)
                            suspicious = stats.get("suspicious", 0)
                            return malicious, suspicious
            except Exception as e:
                print(f"  [VT Error] {e}")
        else:
            response = requests.get(api_url, headers=headers, timeout=30)
            if response.status_code == 200:
                data = response.json()
                stats = data.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
                malicious = stats.get("malicious", 0)
                suspicious = stats.get("suspicious", 0)
                return malicious, suspicious
    except Exception as e:
        print(f"  [VT Error] {e}")
    return None, None

def test_stream(url, timeout=10):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': '*/*'
        }
        response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        if response.status_code == 200:
            return True, "OK"
        elif response.status_code in [301, 302]:
            return True, f"Redirect ({response.status_code})"
        else:
            return False, f"HTTP {response.status_code}"
    except requests.exceptions.Timeout:
        return False, "Timeout"
    except requests.exceptions.ConnectionError:
        return False, "Connection Error"
    except Exception as e:
        return False, str(e)[:50]

def parse_m3u(filepath):
    channels = []
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXTINF:'):
            extinf = line
            i += 1
            if i < len(lines):
                url = lines[i].strip()
                if url and not url.startswith('#'):
                    channels.append({
                        'extinf': extinf,
                        'url': url
                    })
        i += 1
    return channels

def create_channel_line(extinf, url, epg_url):
    tvg_id = None
    channel_name = None
    current_logo = None
    
    logo_match = re.search(r'tvg-logo="([^"]*)"', extinf)
    if logo_match:
        current_logo = logo_match.group(1)
    
    name_match = re.search(r',(.+)$', extinf)
    if name_match:
        channel_name = name_match.group(1).strip()
    
    epg_id = get_epg_id(channel_name) if channel_name else None
    
    safe_logo = get_safe_logo(channel_name, current_logo) if current_logo else None
    
    new_parts = ['#EXTM3U']
    
    new_extinf = '#EXTINF:-1'
    
    if epg_id:
        new_extinf += f' tvg-id="{epg_id}"'
    
    if safe_logo:
        new_extinf += f' tvg-logo="{safe_logo}"'
    elif channel_name:
        logo = SAFE_LOGOS.get(channel_name.split('|')[0].strip())
        if logo:
            new_extinf += f' tvg-logo="{logo}"'
    
    group_match = re.search(r'group-title="([^"]*)"', extinf)
    if group_match:
        new_extinf += f' group-title="{group_match.group(1)}"'
    
    if channel_name:
        new_extinf += f',{channel_name}'
    
    return new_extinf, url

def main():
    print("=" * 70)
    print("Correção completa do lista5.m3u")
    print("=" * 70)
    
    channels = parse_m3u('lista5.m3u')
    print(f"\nTotal de canais encontrados: {len(channels)}")
    
    unique_channels = {}
    for ch in channels:
        name_match = re.search(r',(.+)$', ch['extinf'])
        name = name_match.group(1).strip() if name_match else "Unknown"
        base_url = ch['url'].split('?')[0] if '?' in ch['url'] else ch['url']
        
        if name not in unique_channels:
            unique_channels[name] = ch
    
    print(f"Canais únicos: {len(unique_channels)}")
    
    safe_urls = set()
    unsafe_urls = set()
    untested_urls = set()
    
    print("\n[Testando streams e verificando VirusTotal...]")
    results = []
    
    for i, (name, ch) in enumerate(unique_channels.items(), 1):
        url = ch['url']
        base_url = url.split('?')[0] if '?' in url else url
        
        print(f"\n[{i}/{len(unique_channels)}] {name[:50]}...")
        
        works, status = test_stream(url)
        
        if works:
            malicious, suspicious = check_virustotal(url)
            
            if malicious is None:
                print(f"  Stream: OK | VT: Não verificado (mantido)")
                untested_urls.add(base_url)
                results.append(ch)
            elif malicious > 0 or suspicious > 0:
                print(f"  Stream: OK | VT: MALICIOUS/SUSPICIOUS ({malicious}/{suspicious}) - REMOVIDO")
                unsafe_urls.add(base_url)
            else:
                print(f"  Stream: OK | VT: CLEAN")
                safe_urls.add(base_url)
                results.append(ch)
        else:
            print(f"  Stream: FALHOU ({status})")
            unsafe_urls.add(base_url)
        
        time.sleep(1)
    
    print("\n" + "=" * 70)
    print("RESUMO")
    print("=" * 70)
    print(f"Canais seguros para manter: {len(results)}")
    print(f"Canais inseguros/removidos: {len(unsafe_urls)}")
    print(f"Canais não verificados: {len(untested_urls)}")
    
    print("\nGerando lista5.m3u corrigido...")
    
    with open('lista5_fixed.m3u', 'w', encoding='utf-8') as f:
        f.write('#EXTM3U\n')
        f.write(f'#EXTINF:-1 tvg-name="EPG USA News" tvg-id="EPG_USA" tvg-logo="https://upload.wikimedia.org/wikipedia/commons/thumb/2/2f/TV_logo.svg/200px-TV_logo.svg.png" group-title="EPG",EPG USA News\n')
        f.write(f'#URL:https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.xml.gz\n')
        
        for ch in results:
            extinf, url = create_channel_line(ch['extinf'], ch['url'], EPG_URLS["usa_news"])
            f.write(f'{extinf}\n')
            f.write(f'{url}\n')
    
    print(f"\nArquivo gerado: lista5_fixed.m3u")
    print(f"EPG URL para adicionar: {EPG_URLS['usa_news']}")
    
    with open('lista5_fixed.m3u', 'r') as f:
        content = f.read()
    print(f"\nConteúdo gerado ({len(content)} bytes):")
    print("-" * 50)
    print(content[:2000])
    print("-" * 50)

if __name__ == "__main__":
    main()
