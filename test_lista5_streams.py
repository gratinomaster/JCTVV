#!/usr/bin/env python3
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import sys

EPG_URL = "https://raw.githubusercontent.com/JCTV/JCTV/main/lista5_epg_news_fixed.xml"

def test_stream_url(url):
    """Testa se o stream URL está acessível"""
    try:
        # Remove params from URL for testing
        base_url = url.split('?')[0] if '?' in url else url
        resp = requests.head(base_url, timeout=10, allow_redirects=True)
        if resp.status_code < 400:
            return True, resp.status_code
        return False, resp.status_code
    except Exception as e:
        return False, str(e)

def check_epg_available():
    """Verifica se o EPG está disponível e tem dados de hoje, amanhã e depois de amanhã"""
    try:
        resp = requests.get(EPG_URL, timeout=15)
        if resp.status_code != 200:
            return False, f"EPG status: {resp.status_code}"
        
        root = ET.fromstring(resp.text)
        
        today = datetime.now()
        tomorrow = today + timedelta(days=1)
        after_tomorrow = today + timedelta(days=2)
        
        dates_found = set()
        for prog in root.findall('.//programme'):
            start = prog.get('start', '')[:8]
            if len(start) >= 8:
                try:
                    dt = datetime.strptime(start[:8], '%Y%m%d')
                    if dt.date() == today.date():
                        dates_found.add('today')
                    elif dt.date() == tomorrow.date():
                        dates_found.add('tomorrow')
                    elif dt.date() == after_tomorrow.date():
                        dates_found.add('after_tomorrow')
                except:
                    pass
        
        return True, f"Dates found: {dates_found}"
    except Exception as e:
        return False, str(e)

def main():
    print("=== Testando EPG ===")
    epg_ok, msg = check_epg_available()
    print(f"EPG Status: {epg_ok}")
    print(f"Mensagem: {msg}")
    
    print("\n=== Testando Streams da lista5.m3u ===")
    streams = [
        "https://linear-abcnews-akc-na-central-1.media.dssott.com/dvt2=exp=1777307045~url=%2Flas1%2Fva01%2Fdisneyplus%2Fchannel%2F79449312-79dd-473d-873c-515ebf4b5e5f-1776861675071%2F~psid=aed17fa7-fa25-4454-85b2-c9ea5bb5e7db~did=cb2150e2-9870-472c-a57d-d7a537fa8b2e~country=US~kid=k02~hmac=b13f3fb44230b594a62c96b98bdc2ee5063140f9faf64f4fe7e3428a9796c453/las1/va01/disneyplus/channel/79449312-79dd-473d-873c-515ebf4b5e5f-1776861675071/ctr-all-hdri-sliding.m3u8",
        "https://abcnews-livestreams.akamaized.net/out/v1/6a597119dbd5428a82dc11a2f514a1a2/abcn-live-10-cmaf-manifest/abcn-live-10-index.m3u8",
    ]
    
    for url in streams:
        ok, status = test_stream_url(url)
        print(f"Stream: {url[:60]}...")
        print(f"  Result: {ok}, Status: {status}")

if __name__ == "__main__":
    main()