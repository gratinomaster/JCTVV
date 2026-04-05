#!/usr/bin/env python3
import requests
import gzip
import re
import base64
import json
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import xml.etree.ElementTree as ET

VIRUSTOTAL_API_URL = "https://www.virustotal.com/api/v3/urls"
EPG_US = "https://iptv-epg.org/files/epg-us.xml.gz"

TVG_IDS = {
    "ABC News Live": "ABCNewsLive.us",
    "ABC News": "ABCNewsLive.us",
    "Fox News": "FoxNewsChannel.us",
    "Fox Business": "FoxBusiness.us",
    "CBS News": "CBSNews.us",
}

LOGO_ALTERNATIVAS = {
    "ABCNews": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/07/ABC_News.svg/512px-ABC_News.svg.png",
    "FoxNews": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0c/Fox_News_Channel.svg/512px-Fox_News_Channel.svg.png",
    "FoxBusiness": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0c/Fox_News_Channel.svg/512px-Fox_News_Channel.svg.png",
    "CBSNews": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/CBS_News.svg/512px-CBS_News.svg.png",
}

def extract_channel_info(line: str) -> Dict:
    result = {
        "name": "",
        "tvg_id": "",
        "tvg_logo": "",
        "group": "",
        "raw": line
    }
    
    name_match = re.search(r',(.+)$', line)
    if name_match:
        result["name"] = name_match.group(1).strip()
    
    tvg_id_match = re.search(r'tvg-id="([^"]*)"', line)
    if tvg_id_match:
        result["tvg_id"] = tvg_id_match.group(1)
    
    tvg_logo_match = re.search(r'tvg-logo="([^"]*)"', line)
    if tvg_logo_match:
        result["tvg_logo"] = tvg_logo_match.group(1)
    
    group_match = re.search(r'group-title="([^"]*)"', line)
    if group_match:
        result["group"] = group_match.group(1)
    
    return result

def fix_logo_url(logo: str, channel_name: str) -> str:
    if not logo:
        for key, url in LOGO_ALTERNATIVAS.items():
            if key.lower() in channel_name.lower():
                return url
        return ""
    
    if "imgur.com" in logo.lower():
        return ""
    
    if not logo.lower().endswith('.jpg') and not logo.lower().endswith('.jpeg'):
        for key, url in LOGO_ALTERNATIVAS.items():
            if key.lower() in channel_name.lower():
                return url
        if logo.lower().endswith('.png'):
            return ""
        return logo
    
    return logo

def get_tvg_id(channel_name: str) -> str:
    name_lower = channel_name.lower()
    
    if "abc news" in name_lower:
        return "ABCNewsLive.us"
    if "fox business" in name_lower:
        return "FoxBusiness.us"
    if "fox news" in name_lower:
        return "FoxNewsChannel.us"
    if "cbs news" in name_lower:
        return "CBSNews.us"
    
    return ""

def test_stream(url: str) -> bool:
    try:
        resp = requests.head(url, timeout=15, allow_redirects=True, 
                           headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
        return resp.status_code in [200, 301, 302, 405]
    except:
        return False

def check_virustotal(url: str, api_key: Optional[str] = None) -> Dict:
    result = {"malicious": False, "status": "unknown", "ratio": ""}
    
    if not api_key:
        result["status"] = "no_api_key"
        return result
    
    try:
        url_id = base64.urlsafe_b64encode(url.encode()).decode().strip("=")
        headers = {"x-apikey": api_key}
        resp = requests.get(f"{VIRUSTOTAL_API_URL}/{url_id}", headers=headers, timeout=30)
        
        if resp.status_code == 200:
            data = resp.json()
            stats = data.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
            malicious = stats.get("malicious", 0)
            total = sum(stats.values())
            result["malicious"] = malicious > 0
            result["status"] = "verified"
            result["ratio"] = f"{malicious}/{total}"
        elif resp.status_code == 404:
            result["status"] = "not_found"
        else:
            result["status"] = f"error_{resp.status_code}"
    except Exception as e:
        result["status"] = f"error: {e}"
    
    return result

def main():
    print("=" * 70)
    print("CORREÇÃO COMPLETA lista5.m3u")
    print("=" * 70)
    
    api_key = sys.argv[1] if len(sys.argv) > 1 else None
    if api_key:
        print(f"VirusTotal API: OK")
    else:
        print("VirusTotal API: NÃO CONFIGURADA")
    
    m3u_path = "lista5.m3u"
    
    with open(m3u_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    canais = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXTINF:'):
            info = extract_channel_info(line)
            url = lines[i + 1].strip() if i + 1 < len(lines) else ""
            canais.append({"info": info, "url": url})
            i += 2
        else:
            i += 1
    
    print(f"\nCanais encontrados: {len(canais)}")
    
    canais_unicos = {}
    for ch in canais:
        name = ch["info"]["name"]
        if name not in canais_unicos:
            canais_unicos[name] = ch
    
    canais = list(canais_unicos.values())
    print(f"Após remover duplicados: {len(canais)}")
    
    print("\n" + "-" * 70)
    print("TESTANDO STREAMS...")
    print("-" * 70)
    
    canais_validos = []
    canais_invalidos = []
    
    for ch in canais:
        name = ch["info"]["name"]
        url = ch["url"]
        
        print(f"Testando: {name[:40]:<40}", end=" ")
        
        if test_stream(url):
            print("OK")
            canais_validos.append(ch)
        else:
            print("FALHOU")
            canais_invalidos.append(ch)
    
    print(f"\nStreams válidos: {len(canais_validos)}")
    print(f"Streams inválidos: {len(canais_invalidos)}")
    
    if canais_invalidos:
        print("\nRemovendo streams inválidos...")
    
    print("\n" + "-" * 70)
    print("VERIFICANDO VIRUSTOTAL...")
    print("-" * 70)
    
    canais_seguros = []
    canais_maliciosos = []
    
    unique_urls = {}
    for ch in canais_validos:
        url = ch["url"]
        if url not in unique_urls:
            unique_urls[url] = []
        unique_urls[url].append(ch)
    
    print(f"URLs únicas para verificar: {len(unique_urls)}")
    
    for url, channels in unique_urls.items():
        name = channels[0]["info"]["name"]
        print(f"\nVerificando: {name[:50]}...")
        
        result = check_virustotal(url, api_key)
        
        if result["status"] == "verified":
            if result["malicious"]:
                print(f"  MALICIOSO ({result['ratio']}) - REMOVENDO")
                canais_maliciosos.extend(channels)
            else:
                print(f"  OK ({result['ratio']})")
                canais_seguros.extend(channels)
        elif result["status"] == "no_api_key":
            stream_ok = test_stream(url)
            if stream_ok:
                canais_seguros.extend(channels)
                print(f"  OK (stream válido)")
            else:
                canais_maliciosos.extend(channels)
                print(f"  REMOVIDO (stream não funciona)")
        else:
            stream_ok = test_stream(url)
            if stream_ok:
                canais_seguros.extend(channels)
                print(f"  OK (stream válido)")
            else:
                canais_maliciosos.extend(channels)
                print(f"  REMOVIDO (stream não funciona)")
    
    print("\n" + "-" * 70)
    print("CORRIGINDO LOGOS...")
    print("-" * 70)
    
    for ch in canais_seguros:
        info = ch["info"]
        name = info["name"]
        old_logo = info["tvg_logo"]
        new_logo = fix_logo_url(old_logo, name)
        
        if old_logo != new_logo:
            print(f"{name[:30]:<30} {old_logo[:40] if old_logo else '(vazio)':<40} -> {new_logo[:40] if new_logo else '(novo)':<40}")
        
        info["tvg_logo"] = new_logo
    
    print("\n" + "-" * 70)
    print("GERANDO lista5.m3u FINAL...")
    print("-" * 70)
    
    with open(m3u_path, 'w', encoding='utf-8') as f:
        f.write("#EXTM3U\n")
        
        for ch in canais_seguros:
            info = ch["info"]
            name = info["name"]
            tvg_id = get_tvg_id(name)
            logo = info["tvg_logo"]
            group = info["group"]
            
            attrs = []
            if tvg_id:
                attrs.append(f'tvg-id="{tvg_id}"')
            if logo:
                attrs.append(f'tvg-logo="{logo}"')
            if group:
                attrs.append(f'group-title="{group}"')
            attrs.append(f'x-tvg-url="{EPG_US}"')
            
            attrs_str = ' '.join(attrs)
            f.write(f"#EXTINF:-1 {attrs_str},{name}\n")
            f.write(f"{ch['url']}\n")
    
    print(f"\n" + "=" * 70)
    print("RESUMO")
    print("=" * 70)
    print(f"Canais originais: {len(canais_unicos)}")
    print(f"Canais com stream válido: {len(canais_validos)}")
    print(f"Canais removidos (stream inválido): {len(canais_invalidos)}")
    print(f"Canais removidos (maliciosos): {len(canais_maliciosos)}")
    print(f"Canais finais: {len(canais_seguros)}")
    print(f"\nEPG configurado: {EPG_US}")
    print(f"Arquivo: {m3u_path}")

if __name__ == "__main__":
    main()
