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
    ("https://iptv-epg.org/files/epg-es.xml.gz", "IPTV-EPG ES", "ES"),
    ("https://iptv-epg.org/files/epg-fr.xml.gz", "IPTV-EPG FR", "FR"),
    ("https://iptv-epg.org/files/epg-us.xml.gz", "IPTV-EPG US", "US"),
    ("https://iptv-epg.org/files/epg-gb.xml.gz", "IPTV-EPG GB", "GB"),
    ("https://iptv-epg.org/files/epg-it.xml.gz", "IPTV-EPG IT", "IT"),
    ("https://iptv-epg.org/files/epg-de.xml.gz", "IPTV-EPG DE", "DE"),
    ("https://iptv-epg.org/files/epg-cl.xml.gz", "IPTV-EPG CL", "CL"),
    ("https://iptv-epg.org/files/epg-bo.xml.gz", "IPTV-EPG BO", "BO"),
]

CHANNEL_MAPPING = {
    "Al Jazeera Español": {"tvg_id": "AlJazeeraEnglish.es", "epg_country": "ES"},
    "Euronews Español": {"tvg_id": "Euronews.es", "epg_country": "ES"},
    "BBC World News": {"tvg_id": "BBCWorldNews.fr", "epg_country": "FR"},
    "CNN Internacional": {"tvg_id": "CNNInternational.fr", "epg_country": "FR"},
    "France Info": {"tvg_id": "FranceInfo.fr", "epg_country": "FR"},
    "BFM TV": {"tvg_id": "BFMTV.fr", "epg_country": "FR"},
    "ETB Basque": {"tvg_id": "ETB1.es", "epg_country": "ES"},
    "Galicia TV America": {"tvg_id": "TVG-TVGalicia.es", "epg_country": "ES"},
    "Rai Italia": {"tvg_id": "RaiItalia.us", "epg_country": "US"},
    "TVE Internacional": {"tvg_id": "TVEInternacional.es", "epg_country": "ES"},
    "TV5Monde Español": {"tvg_id": "TV5Monde.fr", "epg_country": "FR"},
    "Bolivia TV": {"tvg_id": "BoliviaTV.bo", "epg_country": "BO"},
    "TVN Chile": {"tvg_id": "TVNChile.cl", "epg_country": "CL"},
    "Telemundo Internacional": {"tvg_id": "Telemundo.us", "epg_country": "US"},
    "ESPN8 The Ocho": {"tvg_id": "ESPN8TheOcho.us", "epg_country": "US"},
    "ESPN Deportes": {"tvg_id": "ESPNDeportes.us", "epg_country": "US"},
    "CBS Sports Golazo": {"tvg_id": "CBSSportsGolazoNetwork.us", "epg_country": "US"},
    "FanDuel TV": {"tvg_id": "FanDuelTV.us", "epg_country": "US"},
    "FIFA+": {"tvg_id": "FIFA+.us", "epg_country": "US"},
    "Red Bull TV": {"tvg_id": "RedBullTV.us", "epg_country": "US"},
    "beIN Sports XTRA": {"tvg_id": "beINSPORTSXtra.us", "epg_country": "US"},
    "VH1": {"tvg_id": "VH1.us", "epg_country": "US"},
    "VMusic": {"tvg_id": "VMusic.ar", "epg_country": "US"},
    "M2O TV": {"tvg_id": "M2OTV.it", "epg_country": "IT"},
    "Deluxe Music": {"tvg_id": "DeluxeMusic.de", "epg_country": "DE"},
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

def download_epg(epg_url: str, country_code: str) -> Optional[str]:
    cache_file = f"/tmp/epg_{country_code}.xml"
    try:
        with open(cache_file, 'r') as f:
            content = f.read()
            if len(content) > 1000:
                return content
    except:
        pass
    
    try:
        response = requests.get(epg_url, timeout=180, headers={'Accept-Encoding': 'gzip'})
        response.raise_for_status()
        
        if epg_url.endswith('.gz'):
            content = gzip.decompress(response.content).decode('utf-8')
        else:
            content = response.text
        
        with open(cache_file, 'w') as f:
            f.write(content)
        
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

def main():
    print("=" * 70)
    print("CORREÇÃO lista5.m3u - EPG + VIRUSTOTAL")
    print("=" * 70)
    
    m3u_path = "lista5.m3u"
    api_key = sys.argv[1] if len(sys.argv) > 1 else None
    
    if api_key:
        print(f"API Key VirusTotal: configurada")
    else:
        print("API Key VirusTotal: NAO CONFIGURADA")
    
    channels = parse_m3u(m3u_path)
    print(f"\nCanais encontrados: {len(channels)}")
    
    print("\n" + "-" * 70)
    print("BAIXANDO/CARREGANDO EPGs...")
    print("-" * 70)
    
    epg_contents = {}
    epg_urls = {}
    
    for epg_url, name, country in EPG_SOURCES:
        print(f"\nCarregando: {name} ({country})")
        content = download_epg(epg_url, country)
        if content and len(content) > 1000:
            epg_contents[country] = content
            epg_urls[country] = epg_url
            print(f"  OK! Tamanho: {len(content):,} bytes")
        else:
            print(f"  FALHOU")
    
    print("\n" + "-" * 70)
    print("ATUALIZANDO CANAIS COM EPG...")
    print("-" * 70)
    
    channels_with_epg = []
    channels_without_epg = []
    
    for ch in channels:
        channel_name = ch["name"]
        mapping = CHANNEL_MAPPING.get(channel_name)
        
        tvg_id = mapping["tvg_id"] if mapping else ch.get("tvg_id", "")
        epg_country = mapping["epg_country"] if mapping else None
        
        epg_url = epg_urls.get(epg_country) if epg_country else None
        
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
        
        if tvg_id and epg_country and epg_country in epg_contents:
            epg_content = epg_contents[epg_country]
            epg_result = test_epg_programming(epg_content, tvg_id)
        
        if epg_result["status"] in ["completo", "parcial"]:
            channels_with_epg.append({
                "extinf": new_extinf,
                "url": ch["url"],
                "name": channel_name,
                "tvg_id": tvg_id,
                "epg_country": epg_country,
                "epg_url": epg_url,
                "epg_result": epg_result
            })
            status_icon = "OK" if epg_result["status"] == "completo" else "PAR"
            programas = epg_result['programas_hoje'][:2] if epg_result['programas_hoje'] else []
            prog_str = f" | {', '.join(programas)}" if programas else ""
            print(f"  {status_icon} {channel_name[:35]:<35} [{tvg_id[:25] if tvg_id else 'N/A':<25}] Hoje:{epg_result['hoje']:>3} Ama:{epg_result['amanha']:>3} Dep:{epg_result['depois_amanha']:>3}{prog_str}")
        else:
            channels_without_epg.append({
                "extinf": new_extinf,
                "url": ch["url"],
                "name": channel_name,
                "tvg_id": tvg_id,
                "epg_result": epg_result
            })
            print(f"  --- {channel_name[:35]:<35} [{tvg_id[:25] if tvg_id else 'N/A':<25}] Sem prog. EPG: {epg_country or 'N/A'}")
    
    print(f"\nCanais com EPG valido: {len(channels_with_epg)}")
    print(f"Canais sem EPG valido: {len(channels_without_epg)}")
    
    print("\n" + "-" * 70)
    print("VERIFICANDO URLs COM VIRUSTOTAL...")
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
    vt_results = {}
    
    if api_key:
        print("\nVerificando VirusTotal...")
        for url, name in list(unique_urls.items())[:20]:
            result = check_virustotal(url, api_key)
            vt_results[name] = result
            if result["status"] == "verificado":
                if result["malicious"]:
                    malicious_channels.append(name)
                    print(f"  MALICIOSO {name[:40]:<40} {result['detection_ratio']}")
                elif result["suspicious"] > 0:
                    suspicious_channels.append(name)
                    print(f"  SUSPEITO  {name[:40]:<40} {result['detection_ratio']}")
                else:
                    print(f"  OK        {name[:40]:<40} {result['detection_ratio']}")
            else:
                print(f"  -         {name[:40]:<40} {result['status']}")
    else:
        print("\nSem API key - VirusTotal nao verificado")
    
    print("\n" + "-" * 70)
    print("RESULTADOS FINAIS...")
    print("-" * 70)
    
    print(f"\nCanais MALICIOSOS (removidos): {len(malicious_channels)}")
    for name in malicious_channels:
        print(f"  - {name}")
    
    print(f"\nCanais SUSPEITOS: {len(suspicious_channels)}")
    for name in suspicious_channels:
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
        else:
            final_channels.append(ch)
    
    unique_final = {}
    for ch in final_channels:
        key = ch["extinf"] + ch["url"]
        if key not in unique_final:
            unique_final[key] = ch
    
    print(f"\nCanais removidos: {removed_count}")
    print(f"Canais finais: {len(unique_final)}")
    
    epg_urls_list = list(set(ch["epg_url"] for ch in channels_with_epg if ch.get("epg_url")))
    epg_header = ",".join(epg_urls_list) if epg_urls_list else ""
    
    with open(m3u_path, 'w', encoding='utf-8') as f:
        if epg_header:
            f.write(f"#EXTM3U x-tvg-url=\"{epg_header}\"\n")
        else:
            f.write("#EXTM3U\n")
        for key, ch in unique_final.items():
            f.write(ch["extinf"] + "\n")
            f.write(ch["url"] + "\n")
    
    print(f"\nOK! lista5.m3u atualizada!")
    print(f"  - Canais finais: {len(unique_final)}")
    print(f"  - EPGs incluidos: {len(epg_urls_list)}")
    
    with open("lista5_epg_report.txt", "w", encoding="utf-8") as f:
        f.write("=" * 70 + "\n")
        f.write("RELATORIO lista5.m3u - EPG + VIRUSTOTAL\n")
        f.write("=" * 70 + "\n\n")
        f.write(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"Total de canais: {len(channels)}\n")
        f.write(f"Canais com EPG valido: {len(channels_with_epg)}\n")
        f.write(f"Canais sem EPG valido: {len(channels_without_epg)}\n")
        f.write(f"Canais removidos (maliciosos): {len(malicious_channels)}\n")
        f.write(f"Canais finais: {len(unique_final)}\n\n")
        
        f.write("EPG URLs:\n")
        for url in epg_urls_list:
            f.write(f"  {url}\n")
        f.write("\n")
        
        f.write("-" * 70 + "\n")
        f.write("CANAIS COM EPG VALIDO (PROGRAMACAO):\n")
        f.write("-" * 70 + "\n")
        for ch in channels_with_epg:
            prog = ch.get("epg_result", {})
            f.write(f"\n{ch['name']}\n")
            f.write(f"  ID: {ch.get('tvg_id', 'N/A')}\n")
            f.write(f"  EPG: {ch.get('epg_country','N/A')}\n")
            f.write(f"  Programacao: Hoje:{prog.get('hoje',0)} Amanha:{prog.get('amanha',0)} Depois:{prog.get('depois_amanha',0)}\n")
            if prog.get('programas_hoje'):
                f.write(f"  Programas de hoje: {', '.join(prog['programas_hoje'][:5])}\n")
        
        f.write("\n" + "-" * 70 + "\n")
        f.write("CANAIS SEM EPG VALIDO:\n")
        f.write("-" * 70 + "\n")
        for ch in channels_without_epg:
            f.write(f"\n{ch['name']}\n")
            f.write(f"  ID: {ch.get('tvg_id', 'N/A')}\n")
            f.write(f"  Status: {ch.get('epg_result',{}).get('status','unknown')}\n")
    
    print("\nRelatorio salvo em: lista5_epg_report.txt")
    
    print("\n" + "=" * 70)
    print("ARQUIVO lista5.m3u ATUALIZADO COM SUCESSO!")
    print("=" * 70)

if __name__ == "__main__":
    main()
