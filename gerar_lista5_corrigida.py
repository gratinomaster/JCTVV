#!/usr/bin/env python3
import requests
from datetime import datetime
import re
import html

EPG_URL = "https://raw.githubusercontent.com/SEU_USUARIO/JCTV/main/lista5_epg_custom.xml"

CANAIS_CONFIG = {
    "ABC News Live": {
        "tvg-id": "ABCWBMA.us",
        "logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
        "streams": [
            "https://abcnews-livestreams.akamaized.net/out/v1/6a597119dbd5428a82dc11a2f514a1a2/abcn-live-10-cmaf-manifest/abcn-live-10-index.m3u8",
        ]
    },
    "Fox News": {
        "tvg-id": "FoxNewsChannel.us",
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/15de0523-3be4-4a9a-8159-7020114e7036/b6ff623a-26d6-4fd9-8bb8-0856adbf38ce/1280x720/match/676/380/image.jpg",
        "streams": [
            "https://247.foxnews.com/hls/live/2003586/FNCHLSv3/master.m3u8",
        ]
    },
    "Fox Business": {
        "tvg-id": "FoxBusiness.us",
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/c9b2e2eb-7b87-435c-9510-eab2650ff944/8b584585-acf2-4c37-aa07-aaf2d077bb20/1280x720/match/676/380/image.jpg",
        "streams": [
            "https://247.foxbusiness.com/hls/live/2003756/FBNHLSv3/master.m3u8",
        ]
    },
    "CBS News 24/7": {
        "tvg-id": "CBSNews247.us",
        "logo": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
        "streams": [
            "https://dai.google.com/linear/hls/pa/event/Sid4xiTQTkCT1SLu6rjUSQ/stream/f13ba145-181f-4d22-8b23-78491c494d42:DLS/master.m3u8",
        ]
    }
}

def testar_stream(url):
    """Testa se um stream está acessível"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': '*/*'
        }
        response = requests.head(url, timeout=10, allow_redirects=True, headers=headers)
        if response.status_code == 200:
            return True, response.status_code
        elif response.status_code in [403, 405]:
            return True, response.status_code
        else:
            return False, response.status_code
    except Exception as e:
        return False, str(e)

def testar_logo(url):
    """Verifica se o logo existe e é .jpg"""
    try:
        if not url.endswith('.jpg') and not url.endswith('.jpeg'):
            return False, "Não é .jpg"
        
        response = requests.head(url, timeout=10, allow_redirects=True)
        if response.status_code == 200:
            return True, "OK"
        return False, f"HTTP {response.status_code}"
    except:
        return False, "Erro"

def gerar_lista():
    """Gera a lista M3U corrigida"""
    
    print("="*60)
    print("GERANDO LISTA5 CORRIGIDA")
    print("="*60)
    
    lines = []
    lines.append('#EXTM3U url-tvg="https://raw.githubusercontent.com/SEU_USUARIO/JCTV/main/lista5_epg_custom.xml"')
    
    canais_funcionando = []
    
    for nome, config in CANAIS_CONFIG.items():
        tvg_id = config["tvg-id"]
        logo = config["logo"]
        
        print(f"\n--- {nome} ---")
        
        is_logo_ok, logo_msg = testar_logo(logo)
        print(f"Logo: {logo_msg}")
        
        if not is_logo_ok:
            logo = None
            print(f"  Removendo logo: {logo_msg}")
        
        for stream_url in config["streams"]:
            print(f"Stream: {stream_url[:60]}...")
            ok, status = testar_stream(stream_url)
            
            if ok:
                print(f"  ✓ Stream funciona (HTTP {status})")
                
                logo_attr = f' tvg-logo="{logo}"' if logo else ''
                extinf = f'#EXTINF:-1 tvg-id="{tvg_id}"{logo_attr} group-title="NEWS WORLD",{nome}'
                lines.append(extinf)
                lines.append(stream_url)
                
                canais_funcionando.append({
                    "nome": nome,
                    "tvg_id": tvg_id,
                    "stream": stream_url,
                    "logo": logo,
                    "status": "ok"
                })
            else:
                print(f"  ✗ Stream não funciona (HTTP {status})")
                canais_funcionando.append({
                    "nome": nome,
                    "tvg_id": tvg_id,
                    "stream": stream_url,
                    "logo": logo,
                    "status": "falhou"
                })
    
    return lines, canais_funcionando

def main():
    lines, canais = gerar_lista()
    
    print("\n" + "="*60)
    print("RESUMO")
    print("="*60)
    
    total = len(canais)
    funcionando = sum(1 for c in canais if c["status"] == "ok")
    falhou = total - funcionando
    
    print(f"Total de canais: {total}")
    print(f"Funcionando: {funcionando}")
    print(f"Falhou: {falhou}")
    
    for c in canais:
        status = "✓" if c["status"] == "ok" else "✗"
        print(f"  {status} {c['nome']} ({c['tvg_id']})")
    
    if lines:
        with open("lista5_corrigida.m3u", "w", encoding="utf-8") as f:
            f.write('\n'.join(lines))
        print(f"\nLista salva em lista5_corrigida.m3u")
        print(f"Linhas: {len(lines)}")
    else:
        print("\n✗ Nenhuma linha gerada")

if __name__ == "__main__":
    main()
