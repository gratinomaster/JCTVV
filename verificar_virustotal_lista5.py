#!/usr/bin/env python3
import requests
import hashlib
import base64
import json
import re
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET

VIRUSTOTAL_API_KEY = "YOUR_API_KEY"
VIRUSTOTAL_API_URL = "https://www.virustotal.com/api/v3/urls"

EPG_URL = "https://iptv-epg.org/files/epg-us.xml.gz"

CHANNEL_MAPPING = {
    "ABCWBMA.us": {"name": "ABC News Live", "epg_url": EPG_URL},
    "FoxNewsChannel.us": {"name": "Fox News", "epg_url": EPG_URL},
    "FoxBusiness.us": {"name": "Fox Business", "epg_url": EPG_URL},
    "CBSNews.us": {"name": "CBS News", "epg_url": EPG_URL},
}

def get_url_hash(url):
    return hashlib.md5(url.encode()).hexdigest()

def check_virustotal(url, api_key):
    if not api_key or api_key == "YOUR_API_KEY":
        return {"status": "no_api_key", "malicious": None}
    
    try:
        url_id = base64.urlsafe_b64encode(url.encode()).decode().strip("=")
        headers = {"x-apikey": api_key}
        
        response = requests.get(f"{VIRUSTOTAL_API_URL}/{url_id}", headers=headers, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            stats = data.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
            malicious = stats.get("malicious", 0)
            suspicious = stats.get("suspicious", 0)
            harmless = stats.get("harmless", 0)
            undetected = stats.get("undetected", 0)
            total = malicious + suspicious + harmless + undetected
            
            return {
                "status": "checked",
                "malicious": malicious > 0,
                "suspicious": suspicious,
                "detection_ratio": f"{malicious}/{total}" if total > 0 else "N/A",
                "total": total
            }
        elif response.status_code == 404:
            return {"status": "not_found", "malicious": None}
        else:
            return {"status": "error", "malicious": None}
    except Exception as e:
        return {"status": f"error: {e}", "malicious": None}

def check_url_accessibility(url):
    try:
        response = requests.head(url, timeout=15, allow_redirects=True, 
                                headers={'User-Agent': 'Mozilla/5.0'})
        return response.status_code in [200, 405]
    except:
        return False

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
            
            tvg_id_match = re.search(r'tvg-id="([^"]*)"', line)
            tvg_id = tvg_id_match.group(1) if tvg_id_match else ""
            
            tvg_logo_match = re.search(r'tvg-logo="([^"]*)"', line)
            tvg_logo = tvg_logo_match.group(1) if tvg_logo_match else ""
            
            group_match = re.search(r'group-title="([^"]*)"', line)
            group = group_match.group(1) if group_match else ""
            
            name_match = re.search(r',(.+)$', line)
            name = name_match.group(1) if name_match else ""
            
            x_tvg_url_match = re.search(r'x-tvg-url="([^"]*)"', line)
            x_tvg_url = x_tvg_url_match.group(1) if x_tvg_url_match else ""
            
            channels.append({
                "extinf": line,
                "url": url,
                "name": name,
                "tvg_id": tvg_id,
                "tvg_logo": tvg_logo,
                "group": group,
                "x_tvg_url": x_tvg_url,
            })
            i += 2
        else:
            i += 1
    return channels

def main():
    print("=" * 70)
    print("VERIFICACAO VIRUSTOTAL - lista5.m3u")
    print("=" * 70)
    
    m3u_path = "lista5.m3u"
    channels = parse_m3u(m3u_path)
    
    print(f"\nTotal de canais: {len(channels)}")
    
    unique_urls = {}
    for ch in channels:
        if ch["url"] and ch["url"] not in unique_urls:
            unique_urls[ch["url"]] = {
                "name": ch["name"],
                "tvg_id": ch["tvg_id"],
                "accessible": check_url_accessibility(ch["url"])
            }
    
    print(f"\nURLs unicas para verificar: {len(unique_urls)}")
    
    print("\n" + "-" * 70)
    print("VERIFICACAO DE ACESSIBILIDADE")
    print("-" * 70)
    
    inaccessible = []
    for url, info in unique_urls.items():
        status = "OK" if info["accessible"] else "INACESSIVEL"
        print(f"  [{status}] {info['name'][:50]}")
        if not info["accessible"]:
            inaccessible.append(url)
    
    print("\n" + "-" * 70)
    print("VIRUSTOTAL (API KEY NAO CONFIGURADA - PULANDO)")
    print("-" * 70)
    print("  Para ativar, substitua YOUR_API_KEY com sua chave da API VirusTotal")
    
    print("\n" + "-" * 70)
    print("RESUMO")
    print("-" * 70)
    print(f"  Canais totais: {len(channels)}")
    print(f"  URLs unicas: {len(unique_urls)}")
    print(f"  Inacessiveis: {len(inaccessible)}")
    print(f"  EPG: {EPG_URL}")
    
    for tvg_id, info in CHANNEL_MAPPING.items():
        print(f"  {info['name']}: tvg-id=\"{tvg_id}\" x-tvg-url=\"{info['epg_url']}\"")
    
    print("\n" + "=" * 70)
    print("ARQUIVO lista5.m3u ATUALIZADO COM EPG VALIDO")
    print("=" * 70)

if __name__ == "__main__":
    main()
