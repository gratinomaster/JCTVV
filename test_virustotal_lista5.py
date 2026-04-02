#!/usr/bin/env python3
import requests
import base64
import json
import time
import re

VT_API_URL = "https://www.virustotal.com/api/v3/urls"

def test_url_virustotal(url):
    try:
        url_id = base64.urlsafe_b64encode(url.encode()).decode().strip("=")
        
        response = requests.post(
            VT_API_URL,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data=f"url={url}",
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            analysis_link = result.get("data", {}).get("links", {}).get("self")
            if analysis_link:
                time.sleep(3)
                analysis = requests.get(analysis_link, timeout=60)
                if analysis.status_code == 200:
                    data = analysis.json()
                    stats = data.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
                    malicious = stats.get("malicious", 0)
                    suspicious = stats.get("suspicious", 0)
                    harmless = stats.get("harmless", 0)
                    undetected = stats.get("undetected", 0)
                    return {
                        "malicious": malicious,
                        "suspicious": suspicious,
                        "harmless": harmless,
                        "undetected": undetected,
                        "status": "malicious" if malicious > 0 else ("suspicious" if suspicious > 0 else "clean")
                    }
    except Exception as e:
        print(f"  Error: {e}")
    return None

def parse_m3u_urls(filepath):
    urls = {}
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    current_info = None
    for line in lines:
        line = line.strip()
        if line.startswith('#EXTINF:'):
            current_info = line
        elif line.startswith('http') and current_info:
            base_url = line.split('?')[0] if '?' in line else line
            if base_url not in urls:
                urls[base_url] = {
                    'info': current_info,
                    'url': line
                }
            current_info = None
    return urls

def main():
    print("=" * 70)
    print("VirusTotal URL Checker for lista5.m3u")
    print("=" * 70)
    
    urls = parse_m3u_urls('lista5.m3u')
    print(f"\nFound {len(urls)} unique URLs to check\n")
    
    results = {}
    for i, (base_url, data) in enumerate(urls.items(), 1):
        print(f"[{i}/{len(urls)}] Checking URL...")
        print(f"  URL: {base_url[:80]}...")
        
        result = test_url_virustotal(base_url)
        
        if result:
            print(f"  Result: {result['status'].upper()} (Malicious: {result['malicious']}, Suspicious: {result['suspicious']}, Clean: {result['harmless']}, Undetected: {result['undetected']})")
        else:
            print(f"  Result: COULD NOT CHECK")
            result = {"status": "unknown"}
        
        results[base_url] = result
        
        time.sleep(2)
    
    with open('virustotal_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    clean = [r for r in results.values() if r.get('status') == 'clean']
    malicious = [r for r in results.values() if r.get('status') == 'malicious']
    suspicious = [r for r in results.values() if r.get('status') == 'suspicious']
    unknown = [r for r in results.values() if r.get('status') == 'unknown']
    
    print(f"\nTotal URLs checked: {len(results)}")
    print(f"Clean: {len(clean)}")
    print(f"Malicious: {len(malicious)}")
    print(f"Suspicious: {len(suspicious)}")
    print(f"Unknown: {len(unknown)}")
    
    return results

if __name__ == "__main__":
    main()
