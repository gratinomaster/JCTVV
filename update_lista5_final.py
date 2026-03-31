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

EPG_URL = "https://iptv-epg.org/files/epg-us.xml.gz"

STREAMS_FOX = {
    "fox news": [
        "http://41.205.93.154/FOX-NEWS/index.m3u8",
        "http://247preview.foxnews.com/hls/live/2020027/fncv3preview/primary.m3u8",
    ],
    "fox business": [
        "http://41.205.93.154/FOXBUSINESS/index.m3u8",
    ]
}

def download_epg() -> Optional[str]:
    try:
        print(f"Baixando EPG: {EPG_URL[:60]}...")
        response = requests.get(EPG_URL, timeout=120, headers={'Accept-Encoding': 'gzip'})
        response.raise_for_status()
        content = gzip.decompress(response.content).decode('utf-8')
        print(f"EPG OK: {len(content):,} bytes")
        return content
    except Exception as e:
        print(f"Erro EPG: {e}")
        return None

def test_epg_programming(epg_content: str, tvg_id: str) -> Dict:
    resultado = {"hoje": 0, "amanha": 0, "depois_amanha": 0, "status": "sem_programacao"}
    
    try:
        root = ET.fromstring(epg_content)
        hoje = datetime.now().strftime("%Y%m%d")
        amanha = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
        depois_amanha = (datetime.now() + timedelta(days=2)).strftime("%Y%m%d")
        
        for prog in root.findall("programme"):
            if prog.get("channel") == tvg_id:
                start = prog.get("start", "")[:8]
                if start == hoje:
                    resultado["hoje"] += 1
                elif start == amanha:
                    resultado["amanha"] += 1
                elif start == depois_amanha:
                    resultado["depois_amanha"] += 1
        
        if resultado["hoje"] > 0 and resultado["amanha"] > 0 and resultado["depois_amanha"] > 0:
            resultado["status"] = "completo"
        elif resultado["hoje"] > 0:
            resultado["status"] = "parcial"
    except Exception as e:
        print(f"Erro: {e}")
    
    return resultado

def check_url(url: str) -> bool:
    try:
        r = requests.head(url, timeout=10, allow_redirects=True, 
                         headers={'User-Agent': 'Mozilla/5.0'})
        return r.status_code in [200, 405]
    except:
        return False

def check_virustotal(url: str, api_key: Optional[str] = None) -> Dict:
    resultado = {"status": "nao_verificado", "malicious": False, "detection_ratio": ""}
    
    if not api_key:
        return resultado
    
    try:
        url_id = base64.urlsafe_b64encode(url.encode()).decode().strip("=")
        headers = {"x-apikey": api_key}
        response = requests.get(f"{VIRUSTOTAL_API_URL}/{url_id}", headers=headers, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            stats = data.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
            malicious = stats.get("malicious", 0)
            total = sum(stats.values())
            resultado["malicious"] = malicious > 0
            resultado["detection_ratio"] = f"{malicious}/{total}"
            resultado["status"] = "verificado"
    except:
        pass
    
    return resultado

def main():
    print("=" * 70)
    print("CORRECAO lista5.m3u - EPG + STREAMS VALIDOS")
    print("=" * 70)
    
    api_key = sys.argv[1] if len(sys.argv) > 1 else None
    
    # Download EPG
    epg_content = download_epg()
    if not epg_content:
        print("ERRO: Nao foi possivel baixar EPG")
        return
    
    # Testar programacao EPG
    print("\n" + "-" * 70)
    print("TESTANDO PROGRAMACAO EPG:")
    print("-" * 70)
    
    canais_tvg = {
        "ABC News": "ABCWBMA.us",
        "Fox News": "FoxNewsChannel.us",
        "Fox Business": "FoxBusiness.us",
        "CBS News": "CBSNews.us",
    }
    
    for nome, tvg_id in canais_tvg.items():
        prog = test_epg_programming(epg_content, tvg_id)
        hoje = datetime.now().strftime("%d/%m")
        amanha = (datetime.now() + timedelta(days=1)).strftime("%d/%m")
        depois = (datetime.now() + timedelta(days=2)).strftime("%d/%m")
        print(f"\n{tvg_id} ({nome}):")
        print(f"  {hoje}: {prog['hoje']} | {amanha}: {prog['amanha']} | {depois}: {prog['depois_amanha']}")
        print(f"  Status: {prog['status']}")
    
    # Testar streams
    print("\n" + "-" * 70)
    print("TESTANDO STREAMS:")
    print("-" * 70)
    
    for tipo, urls in STREAMS_FOX.items():
        print(f"\n{tipo.upper()}:")
        for url in urls:
            ok = check_url(url)
            status = "OK" if ok else "FALHOU"
            print(f"  {status}: {url}")
    
    # Gerar lista final
    print("\n" + "-" * 70)
    print("GERANDO lista5.m3u:")
    print("-" * 70)
    
    # Usar apenas as URLs que funcionam
    fox_news_url = STREAMS_FOX["fox news"][0]
    fox_biz_url = STREAMS_FOX["fox business"][0]
    
    # Canais ABC News (manter os originais que funcionam)
    abc_news_channels = [
        {"logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg", "name": "ABC News Live - ABC News", "url": "https://abcnews-livestreams.akamaized.net/out/v1/173a6e46d5c5423d9611bc7fb7899c73/abcn-live-05-cmaf-manifest/abcn-live-05-index.m3u8"},
        {"logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg", "name": "ABC News Live - ABC News", "url": "https://abcnews-livestreams.akamaized.net/out/v1/6a597119dbd5428a82dc11a2f514a1a2/abcn-live-10-cmaf-manifest/abcn-live-10-index.m3u8"},
    ]
    
    # Canais CBS News
    cbs_news_channels = [
        {"logo": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg", "name": "CBS News 24/7", "url": "https://dai.google.com/linear/hls/pa/event/Sid4xiTQTkCT1SLu6rjUSQ/stream/a1adfa77-8929-44b5-8100-2c6e5befed4c:CHS/master.m3u8"},
    ]
    
    # Verificar VirusTotal se tiver API key
    if api_key:
        print("\nVerificando VirusTotal...")
        for url in [fox_news_url, fox_biz_url]:
            result = check_virustotal(url, api_key)
            if result["status"] == "verificado":
                if result["malicious"]:
                    print(f"  X MALICIOSO: {url[:50]} - {result['detection_ratio']}")
                else:
                    print(f"  OK: {url[:50]} - {result['detection_ratio']}")
    
    # Escrever lista
    with open("lista5.m3u", "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        
        # ABC News
        for ch in abc_news_channels:
            f.write(f'#EXTINF:-1 tvg-id="ABCWBMA.us" tvg-logo="{ch["logo"]}" group-title="NEWS WORLD",{ch["name"]}\n')
            f.write(f'{ch["url"]}\n')
        
        # Fox News
        f.write(f'#EXTINF:-1 tvg-id="FoxNewsChannel.us" tvg-logo="https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/15de0523-3be4-4a9a-8159-7020114e7036/b6ff623a-26d6-4fd9-8bb8-0856adbf38ce/1280x720/match/676/380/image.jpg" group-title="NEWS WORLD",Fox News Channel\n')
        f.write(f'{fox_news_url}\n')
        
        # Fox Business
        f.write(f'#EXTINF:-1 tvg-id="FoxBusiness.us" tvg-logo="https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/c9b2e2eb-7b87-435c-9510-eab2650ff944/8b584585-acf2-4c37-aa07-aaf2d077bb20/1280x720/match/676/380/image.jpg" group-title="NEWS WORLD",Fox Business Network\n')
        f.write(f'{fox_biz_url}\n')
        
        # CBS News
        for ch in cbs_news_channels:
            f.write(f'#EXTINF:-1 tvg-id="CBSNews.us" tvg-logo="{ch["logo"]}" group-title="NEWS WORLD",{ch["name"]}\n')
            f.write(f'{ch["url"]}\n')
    
    total = len(abc_news_channels) + 1 + 1 + len(cbs_news_channels)
    print(f"\nLista gerada com {total} canais")
    print(f"EPG: {EPG_URL}")
    print("\nATENCAO: Adicione x-tvg-url manualmente se necessario")
    print("Exemplo: #EXTINF:-1 tvg-id=\"...\" x-tvg-url=\"https://iptv-epg.org/files/epg-us.xml.gz\"...")

if __name__ == "__main__":
    main()
