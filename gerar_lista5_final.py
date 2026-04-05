#!/usr/bin/env python3
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import base64
import hashlib

def testar_stream(url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        }
        response = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        return response.status_code == 200 and b'#EXTM3U' in response.content[:500]
    except:
        return False

def testar_epg(epg_url):
    try:
        response = requests.get(epg_url, timeout=30)
        response.raise_for_status()
        
        root = ET.fromstring(response.text)
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
        
        return True, len(programas), count_hoje, count_amanha, count_depois
    except Exception as e:
        return False, 0, 0, 0, 0

def gerar_m3u():
    epg_principal = "https://tvit.leicaflorianrobert.dev/epg/list.xml"
    
    print("=" * 60)
    print("TESTANDO EPG")
    print("=" * 60)
    epg_ok, total, hoje, amanha, depois = testar_epg(epg_principal)
    print(f"EPG Status: {total} programas")
    print(f"  Hoje: {hoje}")
    print(f"  Amanhã: {amanha}")
    print(f"  Depois de amanhã: {depois}")
    print(f"EPG Funcionando: {'SIM' if epg_ok else 'NAO'}\n")
    
    channels = [
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
            "url": "https://fox-foxnewsnow-vizio.amagi.tv/playlist.m3u8",
            "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/15de0523-3be4-4a9a-8159-7020114e7036/b6ff623a-26d6-4fd9-8bb8-0856adbf38ce/1280x720/match/676/380/image.jpg",
            "group": "NEWS WORLD",
            "tvg_id": "FoxNewsChannel.us@SD"
        },
        {
            "name": "Fox Business Network",
            "url": "http://41.205.93.154/FOXBUSINESS/index.m3u8",
            "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/c9b2e2eb-7b87-435c-9510-eab2650ff944/8b584585-acf2-4c37-aa07-aaf2d077bb20/1280x720/match/676/380/image.jpg",
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
    
    print("=" * 60)
    print("TESTANDO STREAMS")
    print("=" * 60)
    
    linhas = ['#EXTM3U']
    
    for canal in channels:
        print(f"\nTestando: {canal['name']}")
        stream_ok = testar_stream(canal['url'])
        print(f"  URL: {canal['url'][:60]}...")
        print(f"  Stream OK: {'SIM' if stream_ok else 'NAO'}")
        
        if stream_ok:
            linha = f'#EXTINF:-1 tvg-id="{canal["tvg_id"]}" tvg-name="{canal["name"]}" tvg-logo="{canal["logo"]}" group-title="{canal["group"]}",{canal["name"]}'
            linhas.append(linha)
            linhas.append(canal['url'])
    
    return '\n'.join(linhas), epg_ok, sum(1 for c in channels if testar_stream(c['url']))

if __name__ == "__main__":
    conteudo, epg_ok, canais_ok = gerar_m3u()
    
    with open('/home/runner/work/JCTV/JCTV/lista5.m3u', 'w') as f:
        f.write(conteudo)
    
    print(f"\n" + "=" * 60)
    print("RESUMO")
    print("=" * 60)
    print(f"Arquivo lista5.m3u gerado!")
    print(f"Canais funcionando: {canais_ok}/5")
    print(f"EPG configurado: {'SIM' if epg_ok else 'NAO'}")
