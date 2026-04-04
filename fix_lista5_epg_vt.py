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

EPG_SOURCES = [
    ("https://iptv-epg.org/files/epg-br.xml.gz", "IPTV-EPG BR"),
    ("https://iptv-epg.org/files/epg-es.xml.gz", "IPTV-EPG ES"),
    ("https://iptv-epg.org/files/epg-fr.xml.gz", "IPTV-EPG FR"),
    ("https://iptv-epg.org/files/epg-us.xml.gz", "IPTV-EPG US"),
    ("https://iptv-epg.org/files/epg-gb.xml.gz", "IPTV-EPG GB"),
    ("https://iptv-epg.org/files/epg-cl.xml.gz", "IPTV-EPG CL"),
    ("https://iptv-epg.org/files/epg-bo.xml.gz", "IPTV-EPG BO"),
    ("https://iptv-epg.org/files/epg-it.xml.gz", "IPTV-EPG IT"),
    ("https://iptv-epg.org/files/epg-de.xml.gz", "IPTV-EPG DE"),
]

CHANNEL_MAPPING = {
    "Al Jazeera Español": {"tvg_id": "AlJazeera.es", "epg_source": "es"},
    "Euronews Español": {"tvg_id": "Euronews.es", "epg_source": "es"},
    "BBC World News": {"tvg_id": "BBCWorldNews.gb", "epg_source": "gb"},
    "CNN Internacional": {"tvg_id": "CNNInternational.us", "epg_source": "us"},
    "France Info": {"tvg_id": "FranceInfo.fr", "epg_source": "fr"},
    "BFM TV": {"tvg_id": "BFMTV.fr", "epg_source": "fr"},
    "ETB Basque": {"tvg_id": "ETB1.es", "epg_source": "es"},
    "Galicia TV America": {"tvg_id": "TVGalicia.es", "epg_source": "es"},
    "Rai Italia": {"tvg_id": "RaiItalia.it", "epg_source": "it"},
    "TVE Internacional": {"tvg_id": "TVEInternacional.es", "epg_source": "es"},
    "TV5Monde Español": {"tvg_id": "TV5MondeEspañol.fr", "epg_source": "fr"},
    "Bolivia TV": {"tvg_id": "BoliviaTV.bo", "epg_source": "bo"},
    "TVN Chile": {"tvg_id": "TVNChile.cl", "epg_source": "cl"},
    "Telemundo Internacional": {"tvg_id": "Telemundo.us", "epg_source": "us"},
    "ESPN8 The Ocho": {"tvg_id": "ESPN8.us", "epg_source": "us"},
    "ESPN Deportes": {"tvg_id": "ESPNDeportes.us", "epg_source": "us"},
    "CBS Sports Golazo": {"tvg_id": "CBSSportsGolazo.us", "epg_source": "us"},
    "FanDuel TV": {"tvg_id": "FanDuelTV.us", "epg_source": "us"},
    "FIFA+": {"tvg_id": "FIFAPlus.us", "epg_source": "us"},
    "Red Bull TV": {"tvg_id": "RedBullTV.us", "epg_source": "us"},
    "beIN Sports XTRA": {"tvg_id": "beINSPORTSXtra.us", "epg_source": "us"},
    "VH1": {"tvg_id": "VH1.us", "epg_source": "us"},
    "VMusic": {"tvg_id": "VMusic.ar", "epg_source": "ar"},
    "M2O TV": {"tvg_id": "M2OTV.it", "epg_source": "it"},
    "Deluxe Music": {"tvg_id": "DeluxeMusic.de", "epg_source": "de"},
}

def extract_channel_name(line: str) -> str:
    match = re.search(r',(.+)$', line)
    if match:
        return match.group(1).strip()
    return ""

def parse_m3u(filepath: str) -> List[Dict]:
    channels = []
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXTINF:'):
            url = lines[i + 1].strip() if i + 1 < len(lines) else ""
            channel_name = extract_channel_name(line)
            
            tvg_id_match = re.search(r'tvg-id="([^"]*)"', line)
            tvg_id = tvg_id_match.group(1) if tvg_id_match else ""
            
            tvg_logo_match = re.search(r'tvg-logo="([^"]*)"', line)
            tvg_logo = tvg_logo_match.group(1) if tvg_logo_match else ""
            
            group_match = re.search(r'group-title="([^"]*)"', line)
            group = group_match.group(1) if group_match else ""
            
            channels.append({
                "extinf": line,
                "url": url,
                "name": channel_name,
                "tvg_id": tvg_id,
                "tvg_logo": tvg_logo,
                "group": group,
            })
            i += 2
        else:
            i += 1
    return channels

def download_epg(epg_url: str) -> Optional[str]:
    try:
        print(f"  Baixando: {epg_url[:70]}...")
        response = requests.get(epg_url, timeout=120, headers={'Accept-Encoding': 'gzip'})
        response.raise_for_status()
        
        if epg_url.endswith('.gz'):
            content = gzip.decompress(response.content).decode('utf-8')
        else:
            content = response.text
        return content
    except Exception as e:
        print(f"  Erro: {e}")
        return None

def test_epg_programming(epg_content: str, tvg_id: str) -> Dict:
    resultado = {
        "status": "sem_programacao",
        "hoje": 0,
        "amanha": 0,
        "depois_amanha": 0,
        "programas_hoje": [],
    }
    
    try:
        root = ET.fromstring(epg_content)
        
        hoje = datetime.now().strftime("%Y%m%d")
        amanha = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
        depois_amanha = (datetime.now() + timedelta(days=2)).strftime("%Y%m%d")
        
        for prog in root.findall("programme"):
            channel = prog.get("channel", "")
            if channel == tvg_id:
                start = prog.get("start", "")[:8]
                title_elem = prog.find("title")
                title = title_elem.text if title_elem is not None else "Sem título"
                
                if start[:8] == hoje:
                    resultado["hoje"] += 1
                    if len(resultado["programas_hoje"]) < 3:
                        resultado["programas_hoje"].append(title)
                elif start[:8] == amanha:
                    resultado["amanha"] += 1
                elif start[:8] == depois_amanha:
                    resultado["depois_amanha"] += 1
        
        if resultado["hoje"] > 0 and resultado["amanha"] > 0 and resultado["depois_amanha"] > 0:
            resultado["status"] = "completo"
        elif resultado["hoje"] > 0 or resultado["amanha"] > 0:
            resultado["status"] = "parcial"
        
    except Exception as e:
        resultado["error"] = str(e)
    
    return resultado

def check_virustotal(url: str, api_key: Optional[str] = None) -> Dict:
    resultado = {
        "status": "nao_verificado",
        "malicious": False,
        "suspicious": 0,
        "detection_ratio": "",
        "error": None
    }
    
    if not api_key:
        resultado["status"] = "sem_api_key"
        return resultado
    
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
            
            resultado["malicious"] = malicious > 0
            resultado["suspicious"] = suspicious
            resultado["detection_ratio"] = f"{malicious}/{total}" if total > 0 else "N/A"
            resultado["status"] = "verificado"
            
        elif response.status_code == 404:
            resultado["status"] = "nao_encontrado"
        else:
            resultado["error"] = f"HTTP {response.status_code}"
            
    except Exception as e:
        resultado["error"] = str(e)
    
    return resultado

def check_url_accessible(url: str) -> bool:
    try:
        response = requests.head(url, timeout=10, allow_redirects=True, 
                               headers={'User-Agent': 'Mozilla/5.0'})
        return response.status_code in [200, 301, 302, 405]
    except:
        return False

def get_epg_source_for_channel(channel_name: str) -> Tuple[Optional[str], Optional[str]]:
    if channel_name in CHANNEL_MAPPING:
        return (CHANNEL_MAPPING[channel_name]["tvg_id"], 
                CHANNEL_MAPPING[channel_name]["epg_source"])
    
    name_lower = channel_name.lower()
    if "espn" in name_lower:
        return "ESPN.us", "us"
    if "cnn" in name_lower:
        return "CNNInternational.us", "us"
    if "bbc" in name_lower:
        return "BBCWorldNews.gb", "gb"
    
    return None, None

def get_epg_url_for_source(epg_source: str, epg_sources: Dict) -> Optional[str]:
    source_map = {
        "br": ["IPTV-EPG BR"],
        "us": ["IPTV-EPG US"],
        "es": ["IPTV-EPG ES"],
        "gb": ["IPTV-EPG GB"],
        "fr": ["IPTV-EPG FR"],
        "it": ["IPTV-EPG IT"],
        "de": ["IPTV-EPG DE"],
        "cl": ["IPTV-EPG CL"],
        "bo": ["IPTV-EPG BO"],
        "ar": ["IPTV-EPG AR"],
    }
    
    preferred = source_map.get(epg_source, [])
    for name, url in epg_sources.items():
        if name in preferred:
            return url
    
    for name, url in epg_sources.items():
        if any(p in name for p in preferred):
            return url
    
    return None

def main():
    print("=" * 70)
    print("CORREÇÃO lista5.m3u - EPG + VIRUSTOTAL")
    print("=" * 70)
    
    m3u_path = "lista5.m3u"
    api_key = sys.argv[1] if len(sys.argv) > 1 else None
    
    if api_key:
        print(f"API Key VirusTotal: configurada")
    else:
        print("API Key VirusTotal: NAO CONFIGURADA (usando apenas verificacao de acessibilidade)")
    
    channels = parse_m3u(m3u_path)
    print(f"\nCanais encontrados: {len(channels)}")
    
    print("\n" + "-" * 70)
    print("BAIXANDO EPGs...")
    print("-" * 70)
    
    epg_contents = {}
    epg_urls = {}
    
    for epg_url, name in EPG_SOURCES:
        print(f"\nTestando: {name}")
        content = download_epg(epg_url)
        if content and len(content) > 1000:
            epg_contents[name] = content
            epg_urls[name] = epg_url
            print(f"  OK! Tamanho: {len(content):,} bytes")
        else:
            print(f"  FALHOU")
    
    print("\n" + "-" * 70)
    print("TESTANDO CANAIS COM EPG...")
    print("-" * 70)
    
    channels_with_epg = []
    channels_without_epg = []
    epg_test_results = {}
    
    for ch in channels:
        channel_name = ch["name"]
        tvg_id, epg_source = get_epg_source_for_channel(channel_name)
        
        if not tvg_id:
            tvg_id = ch.get("tvg_id", "")
        
        epg_url = get_epg_url_for_source(epg_source, epg_urls) if epg_source else None
        
        attrs = []
        if tvg_id:
            attrs.append(f'tvg-id="{tvg_id}"')
        if ch["tvg_logo"]:
            attrs.append(f'tvg-logo="{ch["tvg_logo"]}"')
        if ch["group"]:
            attrs.append(f'group-title="{ch["group"]}"')
        if epg_url:
            attrs.append(f'x-tvg-url="{epg_url}"')
        
        attrs_str = ' '.join(attrs)
        new_extinf = f'#EXTINF:-1 {attrs_str},{channel_name}'
        
        epg_result = {"status": "sem_epg", "hoje": 0, "amanha": 0, "depois_amanha": 0}
        
        if tvg_id and epg_url and epg_url in epg_contents:
            epg_content = epg_contents[epg_url]
            epg_result = test_epg_programming(epg_content, tvg_id)
        
        if epg_result["status"] in ["completo", "parcial"]:
            channels_with_epg.append({
                "extinf": new_extinf,
                "url": ch["url"],
                "name": channel_name,
                "tvg_id": tvg_id,
                "epg_source": epg_source,
                "epg_result": epg_result
            })
            status_icon = "OK" if epg_result["status"] == "completo" else "PAR"
            print(f"  {status_icon} {channel_name[:35]:<35} [{tvg_id[:25] if tvg_id else 'N/A':<25}] Hoje:{epg_result['hoje']:>3} Ama:{epg_result['amanha']:>3} Dep:{epg_result['depois_amanha']:>3}")
        else:
            channels_without_epg.append({
                "extinf": new_extinf,
                "url": ch["url"],
                "name": channel_name,
                "tvg_id": tvg_id,
                "epg_result": epg_result
            })
            print(f"  --- {channel_name[:35]:<35} [{tvg_id[:25] if tvg_id else 'N/A':<25}] Hoje:{epg_result['hoje']:>3} Ama:{epg_result['amanha']:>3} Dep:{epg_result['depois_amanha']:>3}")
    
    print(f"\nCanais com EPG valido: {len(channels_with_epg)}")
    print(f"Canais sem EPG valido: {len(channels_without_epg)}")
    
    print("\n" + "-" * 70)
    print("VERIFICANDO URLs (VIRUSTOTAL + ACESSIBILIDADE)...")
    print("-" * 70)
    
    all_channels = channels_with_epg + channels_without_epg
    unique_urls = {}
    for ch in all_channels:
        url = ch["url"]
        if url and url not in unique_urls:
            unique_urls[url] = ch["name"]
    
    print(f"URLs unicas para verificar: {len(unique_urls)}")
    
    malicious_channels = []
    suspicious_channels = []
    inaccessible_channels = []
    safe_channels = []
    
    print("\nVerificando VirusTotal...")
    for url, name in list(unique_urls.items()):
        result = check_virustotal(url, api_key)
        if result["status"] == "verificado":
            if result["malicious"]:
                malicious_channels.append(name)
                print(f"  MALICIOSO {name[:40]:<40} {result['detection_ratio']}")
            elif result["suspicious"] > 0:
                suspicious_channels.append(name)
                print(f"  SUSPEITO  {name[:40]:<40} {result['detection_ratio']}")
            else:
                safe_channels.append(name)
                print(f"  OK        {name[:40]:<40} {result['detection_ratio']}")
        elif result["status"] == "sem_api_key":
            pass
        elif result["status"] == "nao_encontrado":
            accessible = check_url_accessible(url)
            if not accessible:
                inaccessible_channels.append(name)
                print(f"  INACC    {name[:40]:<40} (nao verificado + inacessivel)")
            else:
                safe_channels.append(name)
                print(f"  OK*      {name[:40]:<40} (nao verificado + acessivel)")
        else:
            print(f"  ERRO     {name[:40]:<40} {result.get('error', 'unknown')}")
    
    print("\n" + "-" * 70)
    print("RESULTADOS FINAIS...")
    print("-" * 70)
    
    print(f"\nCanais MALICIOSOS (removidos): {len(malicious_channels)}")
    for name in malicious_channels:
        print(f"  - {name}")
    
    print(f"\nCanais SUSPEITOS: {len(suspicious_channels)}")
    for name in suspicious_channels:
        print(f"  - {name}")
    
    print(f"\nCanais INACCESIVEIS (removidos): {len(inaccessible_channels)}")
    for name in inaccessible_channels:
        print(f"  - {name}")
    
    print("\n" + "-" * 70)
    print("GERANDO lista5.m3u FINAL...")
    print("-" * 70)
    
    final_channels = []
    removed_count = 0
    
    for ch in all_channels:
        name = ch["name"]
        if name in malicious_channels:
            removed_count += 1
            print(f"  - Removido (VirusTotal): {name}")
        elif name in inaccessible_channels:
            removed_count += 1
            print(f"  - Removido (inacessivel): {name}")
        else:
            final_channels.append(ch)
    
    unique_final = {}
    for ch in final_channels:
        key = ch["extinf"] + ch["url"]
        if key not in unique_final:
            unique_final[key] = ch
    
    print(f"\nCanais removidos: {removed_count}")
    print(f"Canais finais: {len(unique_final)}")
    
    with open(m3u_path, 'w', encoding='utf-8') as f:
        f.write("#EXTM3U\n")
        for key, ch in unique_final.items():
            f.write(ch["extinf"] + "\n")
            f.write(ch["url"] + "\n")
    
    print(f"\nOK! lista5.m3u atualizada!")
    print(f"  - Canais finais: {len(unique_final)}")
    
    with open("lista5_epg_report.txt", "w", encoding="utf-8") as f:
        f.write("=" * 70 + "\n")
        f.write("RELATORIO lista5.m3u - EPG + VIRUSTOTAL\n")
        f.write("=" * 70 + "\n\n")
        f.write(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        f.write(f"Canais com EPG valido: {len(channels_with_epg)}\n")
        f.write(f"Canais sem EPG valido: {len(channels_without_epg)}\n")
        f.write(f"Canais removidos (maliciosos): {len(malicious_channels)}\n")
        f.write(f"Canais removidos (inacessiveis): {len(inaccessible_channels)}\n")
        f.write(f"Canais finais: {len(unique_final)}\n\n")
        
        f.write("-" * 70 + "\n")
        f.write("CANAIS COM EPG VALIDO:\n")
        f.write("-" * 70 + "\n")
        for ch in channels_with_epg:
            prog = ch.get("epg_result", {})
            f.write(f"  {ch['name']} - {ch.get('tvg_id', 'N/A')} | Hoje:{prog.get('hoje',0)} Ama:{prog.get('amanha',0)} Dep:{prog.get('depois_amanha',0)}\n")
        
        f.write("\n" + "-" * 70 + "\n")
        f.write("CANAIS SEM EPG VALIDO:\n")
        f.write("-" * 70 + "\n")
        for ch in channels_without_epg:
            prog = ch.get("epg_result", {})
            f.write(f"  {ch['name']} - {ch.get('tvg_id', 'N/A')} | Status: {prog.get('status','unknown')}\n")
    
    print("\nRelatorio salvo em: lista5_epg_report.txt")

if __name__ == "__main__":
    main()
