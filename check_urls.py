#!/usr/bin/env python3
import requests
import re
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

def extract_urls(m3u_file):
    urls = []
    with open(m3u_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    for i, line in enumerate(lines):
        if line.startswith('http') and not line.startswith('#'):
            url = line.strip()
            urls.append(url)
    
    return urls

def check_url_responsive(url, timeout=10):
    try:
        response = requests.head(url, timeout=timeout, allow_redirects=True, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        return {
            'url': url,
            'status': response.status_code,
            'ok': response.status_code == 200
        }
    except requests.exceptions.Timeout:
        return {
            'url': url,
            'status': 'timeout',
            'ok': False
        }
    except requests.exceptions.ConnectionError:
        return {
            'url': url,
            'status': 'connection_error',
            'ok': False
        }
    except Exception as e:
        return {
            'url': url,
            'status': f'error: {str(e)}',
            'ok': False
        }

def check_virustotal(url):
    """Check URL against VirusTotal (requires API key)"""
    # This would require a VirusTotal API key
    # For now, we'll just check if the URL responds
    return check_url_responsive(url)

def main():
    urls = extract_urls('lista5.m3u')
    print(f"Total URLs to check: {len(urls)}")
    
    results = []
    bad_urls = []
    
    # Check first 50 URLs as sample
    sample_urls = urls[:50]
    
    print(f"Checking sample of {len(sample_urls)} URLs...")
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(check_url_responsive, url): url for url in sample_urls}
        
        for i, future in enumerate(as_completed(futures)):
            result = future.result()
            results.append(result)
            
            if not result['ok']:
                bad_urls.append(result)
            
            if (i + 1) % 10 == 0:
                print(f"Progress: {i+1}/{len(sample_urls)}")
    
    print(f"\nResults:")
    print(f"Total checked: {len(results)}")
    print(f"OK: {len([r for r in results if r['ok']])}")
    print(f"Failed: {len(bad_urls)}")
    
    if bad_urls:
        print(f"\nFailed URLs (sample):")
        for r in bad_urls[:10]:
            print(f"  {r['url']} - {r['status']}")
    
    # Save bad URLs for later removal
    with open('bad_urls.txt', 'w') as f:
        for url in bad_urls:
            f.write(f"{url['url']}\n")
    
    return bad_urls

if __name__ == "__main__":
    main()
