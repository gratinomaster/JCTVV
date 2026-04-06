#!/usr/bin/env python3
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import re
import base64
import hashlib
from typing import Dict, List, Optional, Tuple

class Channel:
    def __init__(self, extinf_line: str, url: str):
        self.extinf = extinf_line
        self.url = url
        self.name = self._extract_name()
        self.tvg_logo = self._extract_tvg_logo()
        self.group_title = self._extract_group_title()
        self.tvg_id = self._extract_tvg_id()
        
    def _extract_attr(self, pattern: str) -> Optional[str]:
        match = re.search(pattern, self.extinf)
        return match.group(1) if match else None
    
    def _extract_name(self) -> str:
        parts = self.extinf.split(',')
        return parts[-1].strip() if parts else ""
    
    def _extract_tvg_logo(self) -> Optional[str]:
        return self._extract_attr(r'tvg-logo="([^"]*)"')
    
    def _extract_group_title(self) -> Optional[str]:
        return self._extract_attr(r'group-title="([^"]*)"')
    
    def _extract_tvg_id(self) -> Optional[str]:
        return self._extract_attr(r'tvg-id="([^"]*)"')
    
    def set_epg_id(self, epg_id: str):
        if 'tvg-id=' in self.extinf:
            self.extinf = re.sub(r'tvg-id="[^"]*"', f'tvg-id="{epg_id}"', self.extinf)
        else:
            self.extinf = self.extinf.replace('#EXTINF:', f'#EXTINF:-1 tvg-id="{epg_id}" ')
    
    def fix_tvg_logo(self, new_logo: str):
        if new_logo:
            if 'tvg-logo=' in self.extinf:
                self.extinf = re.sub(r'tvg-logo="[^"]*"', f'tvg-logo="{new_logo}"', self.extinf)
            else:
                self.extinf = self.extinf.replace('#EXTINF:', f'#EXTINF:-1 tvg-logo="{new_logo}" ')
            self.tvg_logo = new_logo

EPG_CHANNEL_MAPPING = {
    "ABC News Live": {"epg_id": "ABCNewsLive.us@SD", "logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg"},
    "Fox Business Go": {"epg_id": "FoxBusiness.us", "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/c9b2e2eb-7b87-435c-9510-eab2650ff944/8b584585-acf2-4c37-aa07-aaf2d077bb20/1280x720/match/676/380/image.jpg"},
    "Fox News Channel": {"epg_id": "FoxNewsChannel.us", "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/15de0523-3be4-4a9a-8159-7020114e7036/b6ff623a-26d6-4fd9-8bb8-0856adbf38ce/1280x720/match/676/380/image.jpg"},
    "CBS News 24/7": {"epg_id": "CBSNewsNetwork.us", "logo": "https://www.cbsnews.com/bundles/cbsnewsvideo/images/cbsn--main-bg.jpg"},
}

MAIN_STREAM_PATTERNS = {
    "ABC News Live": [
        "abcn-live-05-cmaf-manifest",
        "abcn-live-10-cmaf-manifest"
    ],
    "Fox Business": ["FBNHLSv3/master.m3u8"],
    "Fox News": ["FNCHLSv3/master.m3u8"],
    "CBS News": ["master.m3u8"]
}

def parse_m3u(content: str) -> List[Channel]:
    channels = []
    lines = content.strip().split('\n')
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXTINF:'):
            if i + 1 < len(lines) and not lines[i + 1].startswith('#'):
                url = lines[i + 1].strip()
                channels.append(Channel(line, url))
                i += 2
            else:
                i += 1
        else:
            i += 1
    return channels

def is_main_stream(channel: Channel) -> bool:
    url_lower = channel.url.lower()
    name_lower = channel.name.lower()
    
    for main_name, patterns in MAIN_STREAM_PATTERNS.items():
        if main_name.lower() in name_lower:
            return any(p.lower() in url_lower for p in patterns)
    return True

def deduplicate_channels(channels: List[Channel]) -> List[Channel]:
    seen_urls = set()
    result = []
    
    for ch in channels:
        if ch.url not in seen_urls and is_main_stream(ch):
            seen_urls.add(ch.url)
            result.append(ch)
    
    return result

def testar_epg(epg_url: str) -> Dict:
    resultado = {
        "status": "falhou",
        "programas_hoje": 0,
        "programas_amanha": 0,
        "programas_depois_amanha": 0,
        "erro": None
    }
    
    try:
        response = requests.get(epg_url, timeout=60, headers={'Accept-Encoding': 'gzip'})
        response.raise_for_status()
        
        try:
            import gzip
            xml_content = gzip.decompress(response.content).decode('utf-8')
        except:
            xml_content = response.text
        
        root = ET.fromstring(xml_content)
        programas = root.findall("programme")
        
        hoje = datetime.now().strftime("%Y%m%d")
        amanha = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
        depois_amanha = (datetime.now() + timedelta(days=2)).strftime("%Y%m%d")
        
        for prog in programas:
            start = prog.get("start", "")[:8]
            if start[:8] == hoje:
                resultado["programas_hoje"] += 1
            elif start[:8] == amanha:
                resultado["programas_amanha"] += 1
            elif start[:8] == depois_amanha:
                resultado["programas_depois_amanha"] += 1
        
        if resultado["programas_hoje"] > 0 and resultado["programas_amanha"] > 0:
            resultado["status"] = "ok"
        
        return resultado
        
    except Exception as e:
        resultado["erro"] = str(e)
        return resultado

def verificar_url_virustotal(url: str, api_key: Optional[str] = None) -> Dict:
    resultado = {
        "status": "nao_verificado",
        "malicious": False,
        "suspicious": 0,
        "erro": None
    }
    
    if not api_key:
        resultado["status"] = "sem_api_key"
        return resultado
    
    try:
        url_id = base64.urlsafe_b64encode(url.encode()).decode().strip("=")
        headers = {"x-apikey": api_key}
        
        response = requests.get(
            f"https://www.virustotal.com/api/v3/urls/{url_id}",
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            stats = data.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
            resultado["malicious"] = stats.get("malicious", 0) > 0
            resultado["suspicious"] = stats.get("suspicious", 0)
            resultado["status"] = "verificado"
        elif response.status_code == 404:
            resultado["status"] = "nao_encontrado"
        else:
            resultado["erro"] = f"HTTP {response.status_code}"
            
    except Exception as e:
        resultado["erro"] = str(e)
    
    return resultado

def testar_stream(url: str) -> Dict:
    resultado = {"status": "desconhecido", "http_code": None, "erro": None}
    
    try:
        response = requests.head(url, timeout=15, allow_redirects=True, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        resultado["http_code"] = response.status_code
        
        if response.status_code == 200:
            resultado["status"] = "ok"
        elif response.status_code in [403, 405]:
            resultado["status"] = "ok"
        elif response.status_code == 404:
            resultado["status"] = "404"
        else:
            resultado["status"] = f"http_{response.status_code}"
            
    except requests.exceptions.Timeout:
        resultado["status"] = "timeout"
    except Exception as e:
        resultado["status"] = "erro"
        resultado["erro"] = str(e)
    
    return resultado

def main():
    print("="*60)
    print("PROCESSAMENTO lista5.m3u")
    print("="*60)
    
    with open('/home/runner/work/JCTV/JCTV/lista5.m3u', 'r') as f:
        content = f.read()
    
    channels = parse_m3u(content)
    print(f"Canais encontrados: {len(channels)}")
    
    channels = deduplicate_channels(channels)
    print(f"Canais apos deduplicacao: {len(channels)}")
    
    print("\n--- Testando EPG ---")
    epg_urls = [
        "https://github.com/iptv-org/epg/raw/master/guide/us.xml.gz",
        "https://iptv-epg.org/files/epg-us.xml.gz",
    ]
    
    epg_funcionando = None
    for epg_url in epg_urls:
        print(f"Testando: {epg_url}")
        resultado = testar_epg(epg_url)
        print(f"  Status: {resultado['status']}")
        print(f"  Hoje: {resultado['programas_hoje']}, Amanha: {resultado['programas_amanha']}, Pos-amanha: {resultado['programas_depois_amanha']}")
        if resultado['status'] == 'ok':
            epg_funcionando = epg_url
            break
    
    if not epg_funcionando:
        epg_funcionando = epg_urls[0]
    
    print(f"\nEPG selecionado: {epg_funcionando}")
    
    print("\n--- Processando canais ---")
    for ch in channels:
        for name_key, mapping in EPG_CHANNEL_MAPPING.items():
            if name_key.lower() in ch.name.lower():
                ch.set_epg_id(mapping['epg_id'])
                if ch.tvg_logo and '.jpg' not in ch.tvg_logo.lower():
                    ch.fix_tvg_logo(mapping['logo'])
                break
    
    print("\n--- Testando streams ---")
    for ch in channels:
        resultado = testar_stream(ch.url)
        print(f"{ch.name}: {resultado['status']} (HTTP {resultado.get('http_code', 'N/A')})")
    
    output = "#EXTM3U\n"
    for ch in channels:
        output += f"{ch.extinf}\n{ch.url}\n"
    
    output_file = '/home/runner/work/JCTV/JCTV/lista5.m3u'
    with open(output_file, 'w') as f:
        f.write(output)
    
    print(f"\n--- ARQUIVO ATUALIZADO: {output_file} ---")
    print(f"EPG: {epg_funcionando}")

if __name__ == "__main__":
    main()
