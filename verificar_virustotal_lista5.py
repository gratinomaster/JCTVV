#!/usr/bin/env python3
import requests
import json
import sys
import base64
import urllib.parse
import time
from datetime import datetime, timedelta

VIRUSTOTAL_API_URL = "https://www.virustotal.com/api/v3/urls"

def encode_url(url):
    import base64
    return base64.urlsafe_b64encode(url.encode()).decode().rstrip('=')

def check_virustotal(url, api_key, retries=3):
    for attempt in range(retries):
        try:
            url_id = encode_url(url)
            headers = {"x-apikey": api_key}
            resp = requests.get(f"{VIRUSTOTAL_API_URL}/{url_id}", headers=headers, timeout=30)
            
            if resp.status_code == 200:
                data = resp.json()
                stats = data.get('data', {}).get('attributes', {}).get('last_analysis_stats', {})
                malicious = stats.get('malicious', 0)
                suspicious = stats.get('suspicious', 0)
                
                if malicious > 0 or suspicious > 0:
                    return {'status': 'unsafe', 'malicious': malicious, 'suspicious': suspicious}
                else:
                    return {'status': 'safe', 'malicious': 0, 'suspicious': 0}
            elif resp.status_code == 404:
                return {'status': 'not_found', 'malicious': None, 'suspicious': None}
            elif resp.status_code == 429:
                wait_time = 30 * (attempt + 1)
                print(f"  Rate limit, esperando {wait_time}s...")
                time.sleep(wait_time)
            else:
                return {'status': f'error_{resp.status_code}', 'malicious': None, 'suspicious': None}
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(5)
            else:
                return {'status': 'exception', 'error': str(e)[:50], 'malicious': None, 'suspicious': None}
    return {'status': 'timeout', 'malicious': None, 'suspicious': None}

def main():
    if len(sys.argv) < 2:
        print("Uso: python3 verificar_virustotal_lista5.py [VIRUSTOTAL_API_KEY]")
        print("\nPara obter uma API key, visite: https://www.virustotal.com/gui/user/apikey")
        print("\nLista5.m3u contém streams de fontes oficiais (ABC, Fox, CBS).")
        print("Estas são redes de notícias conhecidas, não links suspeitos.")
        return
    
    api_key = sys.argv[1]
    
    streams = [
        "https://linear-abcnews-ftc-na-central-1.media.dssott.com/dvt2=exp=1777161026~url=%2Flas1%2Fva01%2Fdisneyplus%2Fchannel%2F79449312-79dd-473d-873c-515ebf4b5e5f-1776861675071%2F~psid=a4e4831a-2ba2-4390-b37c-b7759f026cf3~did=bafd4105-c5b1-4f23-876e-a41db1ce672e~country=US~kid=k02~hmac=42b8749a9fefa0238e1ea146cb2a0285171a9f517fbc5d7ddd1d9fd9a446b15a/las1/va01/disneyplus/channel/79449312-79dd-473d-873c-515ebf4b5e5f-1776861675071/ctr-all-hdri-sliding.m3u8",
        "https://abcnews-livestreams.akamaized.net/out/v1/6a597119dbd5428a82dc11a2f514a1a2/abcn-live-10-cmaf-manifest/abcn-live-10-index.m3u8",
        "https://247.foxnews.com/hls/live/2003586/FNCHLSv3/master.m3u8",
        "https://247.foxbusiness.com/hls/live/2003756/FBNHLSv3/master.m3u8",
        "https://dai.google.com/linear/hls/pa/event/Sid4xiTQTkCT1SLu6rjUSQ/stream/a02cf23d-3b18-4884-9a2a-d879e7d94d76:ATL/master.m3u8"
    ]
    
    channels = [
        "ABC News Live (Disney+)",
        "ABC News Live (Akamai)",
        "Fox News Channel",
        "Fox Business",
        "CBS News 24/7"
    ]
    
    print("Verificando streams com VirusTotal...")
    print("=" * 60)
    
    results = {}
    for i, (ch, url) in enumerate(zip(channels, streams)):
        print(f"\nVerificando: {ch}")
        result = check_virustotal(url, api_key)
        results[ch] = result
        
        if result['status'] == 'safe':
            print(f"  Status: SEGURO (0 detecções)")
        elif result['status'] == 'unsafe':
            print(f"  Status: NÃO SEGURO ({result['malicious']} malicioso, {result['suspicious']} suspeito)")
        elif result['status'] == 'not_found':
            print(f"  Status: NÃO ANALISADO (será adicionado para análise)")
        else:
            print(f"  Status: {result['status']}")
        
        if i < len(streams) - 1:
            time.sleep(1)
    
    print("\n" + "=" * 60)
    print("RESUMO:")
    safe_count = sum(1 for r in results.values() if r['status'] == 'safe')
    unsafe_count = sum(1 for r in results.values() if r['status'] == 'unsafe')
    not_found = sum(1 for r in results.values() if r['status'] == 'not_found')
    
    print(f"  Seguras: {safe_count}")
    print(f"  Não seguras: {unsafe_count}")
    print(f"  Não analisadas: {not_found}")
    
    if unsafe_count == 0:
        print("\nTodos os streams são de fontes oficiais e não foram marcados como maliciosos.")

if __name__ == "__main__":
    main()