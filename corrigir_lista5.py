#!/usr/bin/env python3
import re
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import base64
import hashlib

EPG_URLS = {
    "ABC News Live": "https://tvit.leicaflorianrobert.dev/epg/list.xml",
    "ABCNewsLive.us@SD": "https://tvit.leicaflorianrobert.dev/epg/list.xml",
    "ABC News Live - Beirut": "https://tvit.leicaflorianrobert.dev/epg/list.xml",
    "ABCNewsLiveBeirut.us@SD": "https://tvit.leicaflorianrobert.dev/epg/list.xml",
    "Fox News": "https://tvit.leicaflorianrobert.dev/epg/list.xml",
    "FoxBusiness": "https://tvit.leicaflorianrobert.dev/epg/list.xml",
    "CBS News 24/7": "https://tvit.leicaflorianrobert.dev/epg/list.xml",
    "CBSNews247.us@SD": "https://tvit.leicaflorianrobert.dev/epg/list.xml",
}

CHANNELS = [
    {
        "name": "ABC News Live",
        "url": "https://abcnews-livestreams.akamaized.net/out/v1/6a597119dbd5428a82dc11a2f514a1a2/abcn-live-10-cmaf-manifest/abcn-live-10-index.m3u8",
        "logo": "https://keyframe-cdn.abcnews.com/streamprovider10.jpg",
        "group": "NEWS WORLD",
        "tvg_id": "ABCNewsLive.us@SD"
    },
    {
        "name": "ABC News Live - Beirut",
        "url": "https://abcnews-livestreams.akamaized.net/out/v1/173a6e46d5c5423d9611bc7fb7899c73/abcn-live-05-cmaf-manifest/abcn-live-05-index.m3u8",
        "logo": "https://keyframe-cdn.abcnews.com/streamprovider5.jpg",
        "group": "NEWS WORLD",
        "tvg_id": "ABCNewsLiveBeirut.us@SD"
    },
    {
        "name": "Fox News Channel",
        "url": "https://247.foxnews.com/hls/live/2003586/FNCHLSv3/master.m3u8?hdnea=exp=1775403842~acl=/*~hmac=6073659006d08fc6fd8624b605a6c365236a950cb1257e712432e096b9595d44",
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/15de0523-3be4-4a9a-8159-7020114e7036/b6ff623a-26d6-4fd9-8bb8-0856adbf38ce/1280x720/match/676/380/image.jpg?ve=1&tl=1",
        "group": "NEWS WORLD",
        "tvg_id": "FoxNewsChannel.us@SD"
    },
    {
        "name": "Fox Business Network",
        "url": "https://247.foxbusiness.com/hls/live/2003756/FBNHLSv3/master.m3u8?hdnea=exp=1775403842~acl=/*~hmac=6073659006d08fc6fd8624b605a6c365236a950cb1257e712432e096b9595d44",
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/c9b2e2eb-7b87-435c-9510-eab2650ff944/8b584585-acf2-4c37-aa07-aaf2d077bb20/1280x720/match/676/380/image.jpg?ve=1&tl=1",
        "group": "NEWS WORLD",
        "tvg_id": "FoxBusinessNetwork.us@SD"
    },
    {
        "name": "CBS News 24/7",
        "url": "https://dai.google.com/linear/hls/pa/event/Sid4xiTQTkCT1SLu6rjUSQ/stream/39b29541-2fca-49d7-b17b-fc007c70bb17:ATL/master.m3u8",
        "logo": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
        "group": "NEWS WORLD",
        "tvg_id": "CBSNews247.us@SD"
    },
]

def testar_stream(url):
    try:
        response = requests.head(url, timeout=10, allow_redirects=True)
        return response.status_code == 200
    except:
        return False

def testar_epg(epg_url):
    try:
        response = requests.get(epg_url, timeout=30)
        response.raise_for_status()
        
        xml_content = response.text
        root = ET.fromstring(xml_content)
        
        programas = root.findall("programme")
        
        hoje = datetime.now().strftime("%Y%m%d")
        amanha = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
        depois_amanha = (datetime.now() + timedelta(days=2)).strftime("%Y%m%d")
        
        count_hoje = count_amanha = count_depois = 0
        
        for prog in programas:
            start = prog.get("start", "")[:8]
            if start == hoje:
                count_hoje += 1
            elif start == amanha:
                count_amanha += 1
            elif start == depois_amanha:
                count_depois += 1
        
        print(f"EPG Status: {len(programas)} programas encontrados")
        print(f"  Hoje: {count_hoje}")
        print(f"  Amanhã: {count_amanha}")
        print(f"  Depois de amanhã: {count_depois}")
        
        return count_hoje > 0 and count_amanha > 0
    except Exception as e:
        print(f"EPG Error: {e}")
        return False

def gerar_m3u():
    epg_principal = "https://tvit.leicaflorianrobert.dev/epg/list.xml"
    
    print("=" * 60)
    print("TESTANDO EPG")
    print("=" * 60)
    epg_ok = testar_epg(epg_principal)
    print(f"EPG Funcionando: {'SIM' if epg_ok else 'NAO'}\n")
    
    print("=" * 60)
    print("TESTANDO STREAMS")
    print("=" * 60)
    
    linhas = ['#EXTM3U']
    
    for canal in CHANNELS:
        print(f"\nTestando: {canal['name']}")
        stream_ok = testar_stream(canal['url'])
        print(f"  Stream OK: {'SIM' if stream_ok else 'NAO'}")
        
        if stream_ok:
            linha = f'#EXTINF:-1 tvg-id="{canal["tvg_id"]}" tvg-name="{canal["name"]}" tvg-logo="{canal["logo"]}" group-title="{canal["group"]}",{canal["name"]}'
            linhas.append(linha)
            linhas.append(canal['url'])
    
    return '\n'.join(linhas), epg_ok

if __name__ == "__main__":
    conteudo, epg_ok = gerar_m3u()
    
    with open('/home/runner/work/JCTV/JCTV/lista5_corrigida.m3u', 'w') as f:
        f.write(conteudo)
    
    print(f"\nArquivo lista5_corrigida.m3u gerado!")
    print(f"EPG configurado: {'SIM' if epg_ok else 'NAO'}")
