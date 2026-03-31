#!/usr/bin/env python3
import requests
import gzip
import re
import base64
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import xml.etree.ElementTree as ET

VIRUSTOTAL_API_URL = "https://www.virustotal.com/api/v3/urls"

EPG_SOURCES = [
    ("https://github.com/iptv-org/epg/raw/master/guide/us.xml.gz", "IPTV-ORG US"),
    ("https://iptv-epg.org/files/epg-us.xml.gz", "IPTV-EPG US"),
]

CHANNEL_MAPPING = {
    "ABC News Live": {"tvg_id": "ABCWBMA.us", "epg_channel": "ABC News"},
    "ABC News": {"tvg_id": "ABCWBMA.us", "epg_channel": "ABC News"},
    "Watch Fox News Channel Online": {"tvg_id": "FoxNewsChannel.us", "epg_channel": "Fox News Channel"},
    "Watch Fox News": {"tvg_id": "FoxNewsChannel.us", "epg_channel": "Fox News Channel"},
    "Fox News": {"tvg_id": "FoxNewsChannel.us", "epg_channel": "Fox News Channel"},
    "Fox Business Go": {"tvg_id": "FoxBusiness.us", "epg_channel": "Fox Business"},
    "Fox Business": {"tvg_id": "FoxBusiness.us", "epg_channel": "Fox Business"},
    "CBS News 24/7": {"tvg_id": "CBSNews.us", "epg_channel": "CBS News"},
    "CBS News": {"tvg_id": "CBSNews.us", "epg_channel": "CBS News"},
    "Fox Business Go | Fox News Video": {"tvg_id": "FoxBusiness.us", "epg_channel": "Fox Business"},
}

def extract_channel_name(line: str) -> str:
    line = line.strip()
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
        print(f"  Baixando: {epg_url[:60]}...")
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

def find_channel_in_epg(epg_content: str, tvg_id: str) -> Optional[Dict]:
    try:
        root = ET.fromstring(epg_content)
        for channel in root.findall("channel"):
            if channel.get("id") == tvg_id:
                display_name = channel.find("display-name")
                icon = channel.find("icon")
                return {
                    "id": channel.get("id"),
                    "name": display_name.text if display_name is not None else tvg_id,
                    "icon": icon.get("src") if icon is not None else ""
                }
        return None
    except Exception as e:
        print(f"  Erro ao buscar canal: {e}")
        return None

def test_epg_programming(epg_content: str, tvg_id: str) -> Dict:
    resultado = {
        "status": "sem_programacao",
        "hoje": 0,
        "amanha": 0,
        "depois_amanha": 0,
        "programas_hoje": [],
        "programas_amanha": [],
        "programas_depois_amanha": []
    }
    
    try:
        root = ET.fromstring(epg_content)
        
        hoje = datetime.now().strftime("%Y%m%d")
        amanha = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
        depois_amanha = (datetime.now() + timedelta(days=2)).strftime("%Y%m%d")
        
        hoje_str = datetime.now().strftime("%d/%m")
        amanha_str = (datetime.now() + timedelta(days=1)).strftime("%d/%m")
        depois_amanha_str = (datetime.now() + timedelta(days=2)).strftime("%d/%m")
        
        for prog in root.findall("programme"):
            channel = prog.get("channel", "")
            if channel == tvg_id:
                start = prog.get("start", "")[:8]
                title_elem = prog.find("title")
                title = title_elem.text if title_elem is not None else "Sem título"
                
                if start[:8] == hoje:
                    resultado["hoje"] += 1
                    resultado["programas_hoje"].append(title)
                elif start[:8] == amanha:
                    resultado["amanha"] += 1
                    resultado["programas_amanha"].append(title)
                elif start[:8] == depois_amanha:
                    resultado["depois_amanha"] += 1
                    resultado["programas_depois_amanha"].append(title)
        
        if resultado["hoje"] > 0 and resultado["amanha"] > 0 and resultado["depois_amanha"] > 0:
            resultado["status"] = "completo"
        elif resultado["hoje"] > 0 or resultado["amanha"] > 0:
            resultado["status"] = "parcial"
        
        return resultado
    except Exception as e:
        print(f"  Erro ao testar programação: {e}")
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
            resultado["detection_ratio"] = f"{malicious}/{total}"
            resultado["status"] = "verificado"
            
        elif response.status_code == 404:
            resultado["status"] = "nao_encontrado"
        else:
            resultado["error"] = f"HTTP {response.status_code}"
            
    except Exception as e:
        resultado["error"] = str(e)
    
    return resultado

def check_url_head(url: str) -> bool:
    try:
        response = requests.head(url, timeout=10, allow_redirects=True, 
                                 headers={'User-Agent': 'Mozilla/5.0'})
        return response.status_code in [200, 405]
    except:
        return False

def get_unique_urls(channels: List[Dict]) -> List[Tuple[str, str]]:
    seen = set()
    unique = []
    for ch in channels:
        if ch["url"] and ch["url"] not in seen:
            seen.add(ch["url"])
            unique.append((ch["name"], ch["url"]))
    return unique

def main():
    print("=" * 70)
    print("CORREÇÃO lista5.m3u - EPG + VIRUSTOTAL")
    print("=" * 70)
    
    m3u_path = "lista5.m3u"
    api_key = sys.argv[1] if len(sys.argv) > 1 else None
    
    channels = parse_m3u(m3u_path)
    print(f"\nCanais encontrados: {len(channels)}")
    
    unique_channels = {}
    for ch in channels:
        name = ch["name"]
        if name not in unique_channels:
            unique_channels[name] = ch
    
    print(f"Canais únicos: {len(unique_channels)}")
    
    print("\n" + "-" * 70)
    print("BAIXANDO EPG...")
    print("-" * 70)
    
    epg_content = None
    epg_source = None
    for url, name in EPG_SOURCES:
        print(f"\nTestando: {name}")
        content = download_epg(url)
        if content and len(content) > 1000:
            epg_content = content
            epg_source = url
            print(f"  OK! Tamanho: {len(content):,} bytes")
            break
        else:
            print(f"  FALHOU")
    
    if not epg_content:
        print("\nERRO: Não foi possível baixar nenhum EPG")
        return
    
    print("\n" + "-" * 70)
    print("ADICIONANDO EPG AOS CANAIS...")
    print("-" * 70)
    
    updated_channels = []
    epg_info = {}
    
    for name, ch in unique_channels.items():
        tvg_id = None
        
        for key, mapping in CHANNEL_MAPPING.items():
            if key.lower() in name.lower() or name.lower() in key.lower():
                tvg_id = mapping["tvg_id"]
                break
        
        if not tvg_id:
            name_lower = name.lower()
            if "abc" in name_lower:
                tvg_id = "ABCWBMA.us"
            elif "fox news" in name_lower:
                tvg_id = "FoxNewsChannel.us"
            elif "fox business" in name_lower:
                tvg_id = "FoxBusiness.us"
            elif "cbs" in name_lower:
                tvg_id = "CBSNews.us"
        
        if tvg_id and tvg_id not in epg_info:
            info = find_channel_in_epg(epg_content, tvg_id)
            epg_info[tvg_id] = info
            if info:
                print(f"  {tvg_id}: {info['name']}")
            else:
                print(f"  {tvg_id}: NAO ENCONTRADO NO EPG")
        
        for orig_ch in channels:
            if orig_ch["name"] == name:
                attrs = []
                if tvg_id:
                    attrs.append(f'tvg-id="{tvg_id}"')
                if orig_ch["tvg_logo"]:
                    attrs.append(f'tvg-logo="{orig_ch["tvg_logo"]}"')
                if orig_ch["group"]:
                    attrs.append(f'group-title="{orig_ch["group"]}"')
                if epg_source:
                    attrs.append(f'x-tvg-url="{epg_source}"')
                
                attrs_str = ' '.join(attrs)
                new_extinf = f'#EXTINF:-1 {attrs_str},{orig_ch["name"]}'
                
                updated_channels.append({
                    "extinf": new_extinf,
                    "url": orig_ch["url"],
                    "name": orig_ch["name"],
                    "tvg_id": tvg_id
                })
    
    print("\n" + "-" * 70)
    print("TESTANDO PROGRAMACAO EPG (HOJE/AMANHA/DEPOIS DE AMANHA)...")
    print("-" * 70)
    
    hoje_str = datetime.now().strftime("%d/%m/%Y")
    amanha_str = (datetime.now() + timedelta(days=1)).strftime("%d/%m/%Y")
    depois_amanha_str = (datetime.now() + timedelta(days=2)).strftime("%d/%m/%Y")
    
    for tvg_id in epg_info.keys():
        info = epg_info[tvg_id]
        if info:
            prog = test_epg_programming(epg_content, tvg_id)
            print(f"\n{tvg_id} ({info['name']}):")
            print(f"  Status: {prog['status']}")
            print(f"  {hoje_str}: {prog['hoje']} programas")
            print(f"  {amanha_str}: {prog['amanha']} programas")
            print(f"  {depois_amanha_str}: {prog['depois_amanha']} programas")
            
            if prog['programas_hoje']:
                print(f"  Exemplos hoje: {prog['programas_hoje'][:3]}")
            if prog['programas_amanha']:
                print(f"  Exemplos amanha: {prog['programas_amanha'][:3]}")
    
    print("\n" + "-" * 70)
    print("VERIFICANDO URLs (VIRUSTOTAL + ACESSIBILIDADE)...")
    print("-" * 70)
    
    unique_urls = get_unique_urls(updated_channels)
    print(f"URLs unicas para verificar: {len(unique_urls)}")
    
    if api_key:
        print("\nVerificando VirusTotal...")
        malicious_urls = []
        for name, url in unique_urls[:15]:
            result = check_virustotal(url, api_key)
            if result["status"] == "verificado":
                if result["malicious"]:
                    print(f"  X {name[:40]}: {result['detection_ratio']} - MALICIOSO!")
                    malicious_urls.append(name)
                elif result["suspicious"] > 0:
                    print(f"  ! {name[:40]}: {result['detection_ratio']} - SUSPEITO")
                else:
                    print(f"  OK {name[:40]}: {result['detection_ratio']}")
            else:
                print(f"  - {name[:40]}: {result['status']}")
    else:
        print("\nSem API key do VirusTotal - verificando apenas acessibilidade")
        malicious_urls = []
    
    print("\nVerificando acessibilidade das URLs...")
    bad_urls = []
    for name, url in unique_urls:
        if not check_url_head(url):
            bad_urls.append(name)
            print(f"  X {name[:40]} - inacessivel")
    
    print("\n" + "-" * 70)
    print("ATUALIZANDO lista5.m3u...")
    print("-" * 70)
    
    channels_to_keep = []
    for ch in updated_channels:
        name = ch["name"]
        if name not in bad_urls and name not in malicious_urls:
            channels_to_keep.append(ch)
        else:
            print(f"  Removendo: {ch['name']}")
    
    unique_channels_final = {}
    for ch in channels_to_keep:
        key = ch["extinf"] + ch["url"]
        if key not in unique_channels_final:
            unique_channels_final[key] = ch
    
    print(f"\nCanais finais: {len(unique_channels_final)}")
    
    with open(m3u_path, 'w', encoding='utf-8') as f:
        f.write("#EXTM3U\n")
        for key, ch in unique_channels_final.items():
            f.write(ch["extinf"] + "\n")
            f.write(ch["url"] + "\n")
    
    print(f"\nOK lista5.m3u atualizada!")
    print(f"  EPG: {epg_source[:60] if epg_source else 'N/A'}...")
    print(f"  Canais: {len(unique_channels_final)}")
    
    print("\n" + "=" * 70)
    print("EPG ATTRIBUTES:")
    print("=" * 70)
    for tvg_id, info in epg_info.items():
        if info:
            print(f"  {tvg_id} -> {epg_source or 'N/A'}")

if __name__ == "__main__":
    main()
