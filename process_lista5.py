#!/usr/bin/env python3
import requests
import re
import hashlib
import time
import os
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

VIRUSTOTAL_API_KEY = os.environ.get("VT_API_KEY", "")

CHANNEL_EPG_MAP = {
    "abc news": {
        "channel_id": "408627",
        "tvg_id": "abcnews.us",
        "epg_url": "https://epg.pw/api/epg.xml?channel_id=408627",
    },
    "abcnl": {
        "channel_id": "408627",
        "tvg_id": "abcnews.us",
        "epg_url": "https://epg.pw/api/epg.xml?channel_id=408627",
    },
    "fox news": {
        "channel_id": "369713",
        "tvg_id": "foxnews.us",
        "epg_url": "https://epg.pw/api/epg.xml?channel_id=369713",
    },
    "fox business": {
        "channel_id": "369713",
        "tvg_id": "foxbusiness.us",
        "epg_url": "https://epg.pw/api/epg.xml?channel_id=369713",
    },
    "cbs news": {
        "channel_id": "464941",
        "tvg_id": "cbsnews.us",
        "epg_url": "https://epg.pw/api/epg.xml?channel_id=464941",
    },
}

def check_virustotal(url):
    if not VIRUSTOTAL_API_KEY:
        print("  VirusTotal API key not set - skipping check")
        return True, "SKIP - No API key"
    
    try:
        api_url = "https://www.virustotal.com/api/v3/urls"
        headers = {"x-apikey": VIRUSTOTAL_API_KEY, "Content-Type": "application/x-www-form-urlencoded"}
        data = f"url={requests.utils.quote(url)}"
        
        response = requests.post(api_url, headers=headers, data=data, timeout=60)
        if response.status_code == 200:
            result = response.json()
            analysis_url = result.get("data", {}).get("links", {}).get("self")
            if analysis_url:
                time.sleep(3)
                analysis = requests.get(analysis_url, headers=headers, timeout=30)
                if analysis.status_code == 200:
                    data = analysis.json()
                    stats = data.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
                    malicious = stats.get("malicious", 0)
                    suspicious = stats.get("suspicious", 0)
                    harmless = stats.get("harmless", 0)
                    undetected = stats.get("undetected", 0)
                    total = malicious + suspicious + harmless + undetected
                    if total > 0:
                        if malicious > 0:
                            return False, f"MALICIOUS: {malicious}/{total}"
                        elif suspicious > 0:
                            return False, f"SUSPICIOUS: {suspicious}/{total}"
                        else:
                            return True, f"CLEAN: {harmless}/{total}"
        elif response.status_code == 429:
            return None, "RATE LIMITED"
    except Exception as e:
        return None, f"ERROR: {str(e)}"
    return None, "UNKNOWN"

def identify_channel(name):
    name_lower = name.lower()
    for key, info in CHANNEL_EPG_MAP.items():
        if key in name_lower:
            return info
    return None

def parse_m3u(filepath):
    channels = []
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXTINF:'):
            extinf = line
            i += 1
            if i < len(lines):
                url = lines[i].strip()
                if url and not url.startswith('#'):
                    channels.append({'extinf': extinf, 'url': url})
        i += 1
    return channels

def format_extinf(extinf, epg_info):
    new_extinf = extinf.rstrip()
    
    if epg_info:
        tvg_id = epg_info['tvg_id']
        tvg_url = epg_info['epg_url']
        
        if 'tvg-id=' in new_extinf:
            new_extinf = re.sub(r'tvg-id="[^"]*"', f'tvg-id="{tvg_id}"', new_extinf)
        else:
            new_extinf = new_extinf + f' tvg-id="{tvg_id}"'
        
        if 'tvg-url=' in new_extinf:
            new_extinf = re.sub(r'tvg-url="[^"]*"', f'tvg-url="{tvg_url}"', new_extinf)
        else:
            new_extinf = new_extinf + f' tvg-url="{tvg_url}"'
    else:
        if 'tvg-id=' not in new_extinf:
            new_extinf = new_extinf + ' tvg-id=""'
        if 'tvg-url=' not in new_extinf:
            new_extinf = new_extinf + ' tvg-url=""'
    
    return new_extinf

def process_channels(channels, check_vt=True):
    results = []
    seen_urls = {}
    
    for ch in channels:
        name = re.search(r',(.+)$', ch['extinf'])
        channel_name = name.group(1) if name else "Unknown"
        
        url = ch['url']
        epg_info = identify_channel(channel_name)
        
        if url in seen_urls:
            vt_result, vt_msg = seen_urls[url]
        else:
            if check_vt and VIRUSTOTAL_API_KEY:
                print(f"Checking: {channel_name}")
                print(f"  URL: {url[:80]}...")
                vt_result, vt_msg = check_virustotal(url)
                seen_urls[url] = (vt_result, vt_msg)
                print(f"  Result: {vt_msg}")
            else:
                vt_result, vt_msg = True, "SKIP"
        
        new_extinf = format_extinf(ch['extinf'], epg_info)
        
        results.append({
            'extinf': new_extinf,
            'url': url,
            'name': channel_name,
            'epg_info': epg_info,
            'vt_result': vt_result,
            'vt_msg': vt_msg
        })
    
    return results

def main():
    input_file = 'lista5.m3u'
    output_file = 'lista5.m3u'
    backup_file = 'lista5_backup_' + datetime.now().strftime('%Y%m%d_%H%M%S') + '.m3u'
    
    print("=" * 60)
    print("Processando lista5.m3u")
    print("=" * 60)
    
    channels = parse_m3u(input_file)
    print(f"Encontrados {len(channels)} canais")
    
    print("\nFazendo backup...")
    with open(input_file, 'r', encoding='utf-8') as f:
        with open(backup_file, 'w', encoding='utf-8') as b:
            b.write(f.read())
    print(f"Backup salvo em: {backup_file}")
    
    print("\nProcessando canais...")
    results = process_channels(channels, check_vt=bool(VIRUSTOTAL_API_KEY))
    
    safe_channels = [r for r in results if r['vt_result'] is not False]
    removed_channels = [r for r in results if r['vt_result'] is False]
    
    print(f"\nCanais seguros: {len(safe_channels)}")
    print(f"Canais removidos (VirusTotal): {len(removed_channels)}")
    
    if removed_channels:
        print("\nCanais removidos:")
        for ch in removed_channels:
            print(f"  - {ch['name']}: {ch['vt_msg']}")
    
    print("\nGerando arquivo atualizado...")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('#EXTM3U\n')
        for r in safe_channels:
            f.write(r['extinf'] + '\n')
            f.write(r['url'] + '\n')
    
    print(f"\nArquivo {output_file} atualizado com sucesso!")
    print(f"Canais com EPG: {len([r for r in safe_channels if r['epg_info']])}")

if __name__ == "__main__":
    main()
