#!/usr/bin/env python3
import requests
import hashlib
import time

def check_virustotal(url, api_key):
    """Verifica URL no VirusTotal"""
    if not api_key:
        return {"error": "No API key"}
    
    url_hash = hashlib.md5(url.encode()).hexdigest()
    headers = {"x-apikey": api_key}
    
    try:
        resp = requests.get(
            f"https://www.virustotal.com/api/v3/urls/{url_hash}",
            headers=headers,
            timeout=15
        )
        if resp.status_code == 200:
            data = resp.json()
            stats = data.get('data', {}).get('attributes', {}).get('last_analysis_stats', {})
            return {
                'malicious': stats.get('malicious', 0),
                'suspicious': stats.get('suspicious', 0),
                'undetected': stats.get('undetected', 0),
                'harmless': stats.get('harmless', 0)
            }
        return {'status': resp.status_code}
    except Exception as e:
        return {'error': str(e)}

def test_stream(url):
    """Testa se stream está acessível"""
    try:
        base_url = url.split('?')[0] if '?' in url else url
        resp = requests.head(base_url, timeout=10, allow_redirects=True)
        return resp.status_code < 400, resp.status_code
    except Exception as e:
        return False, str(e)

def main():
    api_key = ""
    
    streams = [
        ("abcnews-livestreams.akamaized.net", "https://abcnews-livestreams.akamaized.net/out/v1/6a597119dbd5428a82dc11a2f514a1a2/abcn-live-10-cmaf-manifest/abcn-live-10-index.m3u8"),
        ("abcnews dssott", "https://linear-abcnews-akc-na-central-1.media.dssott.com/dvt2=exp=1777307045~url=%2Flas1%2Fva01%2Fdisneyplus%2Fchannel%2F79449312-79dd-473d-873c-515ebf4b5e5f-1776861675071%2F~psid=aed17fa7-fa25-4454-85b2-c9ea5bb5e7db~did=cb2150e2-9870-472c-a57d-d7a537fa8b2e~country=US~kid=k02~hmac=b13f3fb44230b594a62c96b98bdc2ee5063140f9faf64f4fe7e3428a9796c453/las1/va01/disneyplus/channel/79449312-79dd-473d-873c-515ebf4b5e5f-1776861675071/ctr-all-hdri-sliding.m3u8"),
    ]
    
    print("=== Teste de Streams ===")
    for name, url in streams:
        ok, status = test_stream(url)
        print(f"{name}: {'OK' if ok else 'FALHOU'} (status: {status})")
        
        if api_key:
            vt = check_virustotal(url, api_key)
            print(f"  VirusTotal: {vt}")

if __name__ == "__main__":
    main()