#!/usr/bin/env python3
import requests
import json
import hashlib
import time
import re
from urllib.parse import quote

VT_API_KEY = ""

def get_url_info(url):
    url_hash = hashlib.md5(url.encode()).hexdigest()
    api_url = f"https://www.virustotal.com/api/v3/urls/{url_hash}"
    headers = {"x-apikey": VT_API_KEY} if VT_API_KEY else {}
    
    if not VT_API_KEY:
        print("  [INFO] VirusTotal API key not set. Checking with public API...")
        try:
            public_url = f"https://www.virustotal.com/api/v3/urls"
            response = requests.post(public_url, 
                                   headers={"Content-Type": "application/x-www-form-urlencoded"},
                                   data=f"url={quote(url)}",
                                   timeout=60)
            if response.status_code == 200:
                result = response.json()
                analysis_link = result.get("data", {}).get("links", {}).get("self")
                if analysis_link:
                    time.sleep(3)
                    analysis = requests.get(analysis_link, headers={"x-apikey": VT_API_KEY} if VT_API_KEY else {}, timeout=60)
                    if analysis.status_code == 200:
                        data = analysis.json()
                        stats = data.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
                        malicious = stats.get("malicious", 0)
                        suspicious = stats.get("suspicious", 0)
                        harmless = stats.get("harmless", 0)
                        undetected = stats.get("undetected", 0)
                        total = malicious + suspicious + harmless + undetected
                        return malicious, suspicious, harmless, undetected, total
        except Exception as e:
            print(f"  [ERROR] {e}")
    else:
        try:
            response = requests.get(api_url, headers=headers, timeout=30)
            if response.status_code == 200:
                data = response.json()
                stats = data.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
                malicious = stats.get("malicious", 0)
                suspicious = stats.get("suspicious", 0)
                harmless = stats.get("harmless", 0)
                undetected = stats.get("undetected", 0)
                total = malicious + suspicious + harmless + undetected
                return malicious, suspicious, harmless, undetected, total
        except Exception as e:
            print(f"  [ERROR] {e}")
    return None, None, None, None, None

def parse_m3u_urls(filepath):
    urls = []
    seen = set()
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    for line in lines:
        line = line.strip()
        if line and not line.startswith('#'):
            base_url = line.split('?')[0] if '?' in line else line
            if base_url not in seen:
                seen.add(base_url)
                urls.append(line)
    return urls

def main():
    print("=" * 70)
    print("VirusTotal URL Checker for lista5.m3u")
    print("=" * 70)
    
    urls = parse_m3u_urls('lista5.m3u')
    print(f"\nFound {len(urls)} unique URLs to check\n")
    
    results = []
    for i, url in enumerate(urls, 1):
        print(f"[{i}/{len(urls)}] Checking URL...")
        print(f"  URL: {url[:80]}...")
        
        malicious, suspicious, harmless, undetected, total = get_url_info(url)
        
        if total is not None:
            if malicious > 0:
                status = "MALICIOUS"
                flag = False
            elif suspicious > 0:
                status = "SUSPICIOUS"
                flag = False
            else:
                status = "CLEAN"
                flag = True
            
            print(f"  Result: {status} (Malicious: {malicious}, Suspicious: {suspicious}, Clean: {harmless}, Undetected: {undetected}, Total: {total})")
            results.append({
                'url': url,
                'status': status,
                'malicious': malicious,
                'suspicious': suspicious,
                'harmless': harmless,
                'undetected': undetected,
                'total': total,
                'keep': flag
            })
        else:
            print(f"  Result: COULD NOT CHECK")
            results.append({
                'url': url,
                'status': 'UNKNOWN',
                'keep': True
            })
        
        time.sleep(1.5)
    
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    safe = [r for r in results if r.get('keep', True)]
    unsafe = [r for r in results if not r.get('keep', True)]
    
    print(f"\nTotal URLs checked: {len(results)}")
    print(f"Clean/Safe: {len(safe)}")
    print(f"Malicious/Suspicious: {len(unsafe)}")
    
    if unsafe:
        print("\nUnsafe URLs:")
        for r in unsafe:
            print(f"  - {r['url'][:60]}...")
            print(f"    Status: {r['status']}")
    
    return results

if __name__ == "__main__":
    main()
