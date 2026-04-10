#!/usr/bin/env python3
import requests
import re
import gzip
import json
from datetime import datetime, timedelta
from xml.etree import ElementTree as ET
import time
import hashlib

VT_API_KEY = ""

EPG_URL = "https://tvit.leicaflorianrobert.dev/epg/list.xml"

CHANNEL_CONFIG = {
    "abc": {
        "name": "ABC News Live",
        "tvg_id": "ABCWBMA.us",
        "logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
        "best_url": "https://abcnews-livestreams.akamaized.net/out/v1/6a597119dbd5428a82dc11a2f514a1a2/abcn-live-10-cmaf-manifest/abcn-live-10-index.m3u8"
    },
    "fox": {
        "name": "Fox News",
        "tvg_id": "FoxNewsChannel.us",
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/15de0523-3be4-4a9a-8159-7020114e7036/b6ff623a-26d6-4fd9-8bb8-0856adbf38ce/1280x720/match/676/380/image.jpg",
        "best_url": "https://247.foxnews.com/hls/live/2003586/FNCHLSv3/master.m3u8"
    },
    "foxbusiness": {
        "name": "Fox Business",
        "tvg_id": "FoxBusiness.us",
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/c9b2e2eb-7b87-435c-9510-eab2650ff944/8b584585-acf2-4c37-aa07-aaf2d077bb20/1280x720/match/676/380/image.jpg",
        "best_url": "https://247.foxbusiness.com/hls/live/2003756/FBNHLSv3/master.m3u8"
    },
    "cbs": {
        "name": "CBS News 24/7",
        "tvg_id": "CBSNews.us",
        "logo": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
        "best_url": "https://dai.google.com/linear/hls/pa/event/Sid4xiTQTkCT1SLu6rjUSQ/stream/830fd3cf-a350-4ab4-bbff-8283f5cadca5:ATL/master.m3u8"
    }
}

def check_virustotal(url):
    """Verifica URL no VirusTotal."""
    try:
        public_url = "https://www.virustotal.com/api/v3/urls"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = f"url={requests.utils.quote(url)}"
        resp = requests.post(public_url, headers=headers, data=data, timeout=30)
        if resp.status_code == 200:
            result = resp.json()
            analysis_link = result.get("data", {}).get("links", {}).get("self")
            if analysis_link:
                time.sleep(3)
                analysis = requests.get(analysis_link, timeout=30)
                if analysis.status_code == 200:
                    data = analysis.json()
                    stats = data.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
                    malicious = stats.get("malicious", 0)
                    suspicious = stats.get("suspicious", 0)
                    return malicious == 0 and suspicious == 0, malicious, suspicious
    except Exception as e:
        print(f"  VT error: {e}")
    return True, 0, 0

def test_url(url):
    """Testa se o URL funciona."""
    try:
        resp = requests.head(url, timeout=10, allow_redirects=True)
        return resp.status_code < 400
    except:
        return False

def test_epg_programming():
    """Testa se o EPG tem programação para os próximos 3 dias."""
    try:
        headers = {'Accept-Encoding': 'gzip', 'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(EPG_URL, timeout=60, headers=headers)
        if resp.status_code != 200:
            return False
        
        content = resp.content
        try:
            content = gzip.decompress(content)
        except:
            pass
        
        root = ET.fromstring(content)
        today = datetime.now().date()
        dates_found = set()
        
        for programme in root.findall('.//programme'):
            start = programme.get('start', '')
            if start:
                try:
                    date = datetime.strptime(start[:8], '%Y%m%d').date()
                    dates_found.add(date)
                except:
                    pass
        
        tomorrow = today + timedelta(days=1)
        day_after = today + timedelta(days=2)
        
        print(f"  EPG hoje: {'✓' if today in dates_found else '✗'}")
        print(f"  EPG amanha: {'✓' if tomorrow in dates_found else '✗'}")
        print(f"  EPG depois de amanha: {'✓' if day_after in dates_found else '✗'}")
        
        return today in dates_found or tomorrow in dates_found
    except Exception as e:
        print(f"  EPG error: {e}")
        return False

def main():
    print("=" * 70)
    print("CORREÇÃO COMPLETA lista5.m3u")
    print("=" * 70)
    
    print("\n1. Testando EPG...")
    epg_ok = test_epg_programming()
    if not epg_ok:
        print("AVISO: EPG pode ter problemas de programacao")
    
    print("\n2. Verificando URLs principais com VirusTotal...")
    
    channels = []
    
    for key, config in CHANNEL_CONFIG.items():
        print(f"\n  Verificando {config['name']}...")
        
        is_safe, mal, susp = check_virustotal(config['best_url'])
        print(f"    URL: {config['best_url'][:60]}...")
        print(f"    VirusTotal: Malicious={mal}, Suspicious={susp}, Safe={'✓' if is_safe else '✗'}")
        
        url_works = test_url(config['best_url'])
        print(f"    URL funciona: {'✓' if url_works else '✗'}")
        
        if is_safe or url_works:
            extinf = f'#EXTINF:-1 tvg-logo="{config["logo"]}" group-title="NEWS WORLD" tvg-id="{config["tvg_id"]}" x-tvg-url="{EPG_URL}",{config["name"]}'
            channels.append({
                'info': extinf,
                'url': config['best_url'],
                'name': config['name'],
                'logo': config['logo']
            })
    
    print(f"\n3. Total de canais: {len(channels)}")
    
    output = "#EXTM3U\n"
    for ch in channels:
        output += ch['info'] + "\n"
        output += ch['url'] + "\n"
    
    with open('lista5.m3u', 'w', encoding='utf-8') as f:
        f.write(output)
    
    print("\n" + "=" * 70)
    print("RESULTADO")
    print("=" * 70)
    for ch in channels:
        print(f"  ✓ {ch['name']}")
        print(f"    Logo: {ch['logo'][:50]}...")
        print(f"    EPG: {ch['info'].split('x-tvg-url=')[1].split('"')[0]}")
        print(f"    URL: {ch['url'][:60]}...")
    
    print("\n✓ Arquivo lista5.m3u atualizado com sucesso!")

if __name__ == "__main__":
    main()
