#!/usr/bin/env python3
import requests
import gzip
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import xml.etree.ElementTree as ET

EPG_URL = "https://iptv-epg.org/files/epg-us.xml.gz"

EPG_CHANNEL_MAPPING = {
    "ABCNewsLive.us@SD": {"name": "ABC News Live", "logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg"},
    "FoxBusiness.us": {"name": "Fox Business", "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/c9b2e2eb-7b87-435c-9510-eab2650ff944/8b584585-acf2-4c37-aa07-aaf2d077bb20/1280x720/match/676/380/image.jpg"},
    "FoxNewsChannel.us": {"name": "Fox News", "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/15de0523-3be4-4a9a-8159-7020114e7036/b6ff623a-26d6-4fd9-8bb8-0856adbf38ce/1280x720/match/676/380/image.jpg"},
    "CBSNews24/7.pluto": {"name": "CBS News 24/7", "logo": "https://www.cbsnews.com/bundles/cbsnewsvideo/images/cbsn--main-bg.jpg"},
}

EPG_ID_BY_KEYWORD = [
    ("abcnews", "ABCNewsLive.us@SD"),
    ("fox business", "FoxBusiness.us"),
    ("fox news channel", "FoxNewsChannel.us"),
    ("foxnews", "FoxNewsChannel.us"),
    ("cbs news 24/7", "CBSNews24/7.pluto"),
    ("cbsnews", "CBSNews24/7.pluto"),
]

def is_variant_url(url: str) -> bool:
    patterns = [
        "/variant/", "/bandwidth/", "_4_0.m3u8", "_3.m3u8",
        "/audio-", "_slide.m3u8", "64_slide", "128_slide"
    ]
    return any(p.lower() in url.lower() for p in patterns)

def clean_tvg_logo(logo: str) -> str:
    if not logo:
        return ""
    logo = logo.split('?')[0]
    if logo.lower().endswith('.png'):
        logo = logo.replace('.png', '.jpg')
    elif not logo.lower().endswith('.jpg'):
        logo = logo + '.jpg'
    return logo

def get_epg_id(name: str, current_tvg_id: str = None) -> Optional[str]:
    if current_tvg_id and current_tvg_id in EPG_CHANNEL_MAPPING:
        return current_tvg_id
    
    name_lower = name.lower()
    for keyword, epg_id in EPG_ID_BY_KEYWORD:
        if keyword in name_lower:
            return epg_id
    return None

def testar_epg(epg_url: str) -> Dict:
    resultado = {"status": "falhou", "hoje": 0, "amanha": 0, "depois": 0, "erro": None}
    try:
        response = requests.get(epg_url, timeout=120, headers={'Accept-Encoding': 'gzip'})
        response.raise_for_status()
        
        try:
            xml_content = gzip.decompress(response.content).decode('utf-8')
        except:
            xml_content = response.text
        
        root = ET.fromstring(xml_content)
        
        hoje = datetime.now().strftime("%Y%m%d")
        amanha = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
        depois = (datetime.now() + timedelta(days=2)).strftime("%Y%m%d")
        
        canais = {ch.get("id"): ch.find("display-name").text if ch.find("display-name") is not None else ch.get("id") 
                  for ch in root.findall("channel")}
        
        for prog in root.findall("programme"):
            channel = prog.get("channel", "")
            start = prog.get("start", "")[:8]
            
            if start[:8] == hoje:
                resultado["hoje"] += 1
            elif start[:8] == amanha:
                resultado["amanha"] += 1
            elif start[:8] == depois:
                resultado["depois"] += 1
        
        if resultado["hoje"] > 0 and resultado["amanha"] > 0:
            resultado["status"] = "ok"
        
        print(f"  Canais no EPG: {len(canais)}")
        
        return resultado
    except Exception as e:
        resultado["erro"] = str(e)
        return resultado

def testar_stream(url: str) -> Dict:
    resultado = {"status": "desconhecido", "http_code": None}
    try:
        response = requests.head(url, timeout=15, allow_redirects=True, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        resultado["http_code"] = response.status_code
        if response.status_code in [200, 301, 302, 403, 405]:
            resultado["status"] = "ok"
        elif response.status_code == 404:
            resultado["status"] = "404"
        return resultado
    except:
        resultado["status"] = "erro"
        return resultado

def main():
    print("="*70)
    print("CORRECAO COMPLETA lista5.m3u")
    print("="*70)
    
    print("\n--- Testando EPG ---")
    epg_result = testar_epg(EPG_URL)
    print(f"EPG: {EPG_URL}")
    print(f"Status: {epg_result['status']}")
    print(f"Hoje: {epg_result['hoje']} | Amanha: {epg_result['amanha']} | Depois: {epg_result['depois']}")
    
    if epg_result['status'] != 'ok':
        print("\nAVISO: EPG pode ter problemas de programacao")
    
    with open('/home/runner/work/JCTV/JCTV/lista5.m3u', 'r') as f:
        content = f.read()
    
    lines = content.strip().split('\n')
    
    channels = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXTINF:'):
            if i + 1 < len(lines) and not lines[i + 1].startswith('#'):
                url = lines[i + 1].strip()
                name_match = re.search(r',(.+)$', line)
                name = name_match.group(1).strip() if name_match else ""
                
                tvg_id_match = re.search(r'tvg-id="([^"]*)"', line)
                tvg_id = tvg_id_match.group(1) if tvg_id_match else ""
                
                tvg_logo_match = re.search(r'tvg-logo="([^"]*)"', line)
                tvg_logo = tvg_logo_match.group(1) if tvg_logo_match else ""
                
                channels.append({
                    "extinf": line,
                    "url": url,
                    "name": name,
                    "tvg_id": tvg_id,
                    "tvg_logo": tvg_logo
                })
                i += 2
            else:
                i += 1
        else:
            i += 1
    
    print(f"\nCanais encontrados: {len(channels)}")
    
    print("\n--- Filtrando e deduplicando ---")
    seen_urls = set()
    final_channels = []
    
    for ch in channels:
        url = ch["url"]
        name = ch["name"]
        
        if is_variant_url(url):
            print(f"  REMOVIDO (variant): {name[:40]}")
            continue
        
        if url in seen_urls:
            print(f"  REMOVIDO (duplicado): {name[:40]}")
            continue
        
        seen_urls.add(url)
        
        epg_id = get_epg_id(name, ch.get("tvg_id"))
        
        if epg_id:
            ch["tvg_id"] = epg_id
            mapping = EPG_CHANNEL_MAPPING.get(epg_id, {})
            if mapping.get("logo"):
                ch["tvg_logo"] = mapping["logo"]
        
        if ch["tvg_logo"]:
            ch["tvg_logo"] = clean_tvg_logo(ch["tvg_logo"])
        
        print(f"  KEEP: {name[:40]} [{epg_id or 'N/A'}]")
        final_channels.append(ch)
    
    print(f"\nCanais finais: {len(final_channels)}")
    
    print("\n--- Testando streams ---")
    for ch in final_channels:
        result = testar_stream(ch["url"])
        status = "OK" if result["status"] == "ok" else result["status"].upper()
        print(f"  {status}: {ch['name'][:40]}")
    
    print("\n--- Gerando arquivo final ---")
    output = f'#EXTM3U x-tvg-url="{EPG_URL}"\n'
    
    for ch in final_channels:
        attrs = []
        if ch.get("tvg_id"):
            attrs.append(f'tvg-id="{ch["tvg_id"]}"')
        if ch.get("tvg_logo"):
            attrs.append(f'tvg-logo="{ch["tvg_logo"]}"')
        attrs.append('group-title="NEWS WORLD"')
        
        attrs_str = " ".join(attrs)
        output += f'#EXTINF:-1 {attrs_str},{ch["name"]}\n'
        output += f'{ch["url"]}\n'
    
    with open('/home/runner/work/JCTV/JCTV/lista5.m3u', 'w', encoding='utf-8') as f:
        f.write(output)
    
    print(f"\n{'='*70}")
    print(f"ARQUIVO ATUALIZADO!")
    print(f"  Canais: {len(final_channels)}")
    print(f"  EPG: {EPG_URL}")
    print(f"{'='*70}")

if __name__ == "__main__":
    main()
