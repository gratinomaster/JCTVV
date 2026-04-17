#!/usr/bin/env python3
import requests
import gzip
import xml.etree.ElementTree as ET
import re
import hashlib
import time
from datetime import datetime, timedelta
from urllib.parse import quote, urlparse

EPG_URL = "https://iptv-epg.org/files/epg-us.xml.gz"

CHANNEL_CONFIG = {
    "ABCNewsLive": {
        "epg_id": "ABCNewsLive.us",
        "logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
        "name": "ABC News Live",
        "keep_patterns": ["abcn-live-10-cmaf-manifest", "ctr-all-hdri-sliding"],
        "priority_patterns": ["abcn-live-10-cmaf-manifest"]
    },
    "ABC_GMA": {
        "epg_id": "ABCNewsLive.us",
        "logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
        "name": "ABC News Live",
        "keep_patterns": ["linear-abcnews-akc", "ctr-all-hdri-sliding"],
        "priority_patterns": ["ctr-all-hdri-sliding"]
    },
    "FoxNews": {
        "epg_id": "FoxNewsChannel.us",
        "logo": "https://a57.foxnews.com/static.foxnews.com/foxnews.com/images/2024/09/fn-logo-social-share.png",
        "name": "Fox News Channel",
        "keep_patterns": ["FNCHLSv3/master.m3u8"],
        "priority_patterns": ["FNCHLSv3/master.m3u8"]
    },
    "FoxBusiness": {
        "epg_id": "FoxBusiness.us",
        "logo": "https://a57.foxnews.com/static.foxbusiness.com/foxbusiness.com/2024/09/fb-logo-social-share.png",
        "name": "Fox Business",
        "keep_patterns": ["FBNHLSv3/master.m3u8"],
        "priority_patterns": ["FBNHLSv3/master.m3u8"]
    },
    "CBSNews": {
        "epg_id": "CBSNews.us",
        "logo": "https://tvu-assets-prod.s3.amazonaws.com/cbsn-logo.png",
        "name": "CBS News 24/7",
        "keep_patterns": ["dai.google.com/linear", "master.m3u8"],
        "priority_patterns": ["dai.google.com/linear", "master.m3u8"]
    }
}

def parse_m3u(content):
    channels = []
    lines = content.strip().split('\n')
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXTINF:'):
            extinf = line
            if i + 1 < len(lines) and not lines[i + 1].startswith('#'):
                url = lines[i + 1].strip()
                channels.append({"extinf": extinf, "url": url})
                i += 2
            else:
                i += 1
        else:
            i += 1
    return channels

def get_base_url(url):
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    return base

def get_channel_key(name, url):
    url_lower = url.lower()
    name_lower = name.lower()
    
    if 'fnchl' in url_lower and 'master.m3u8' in url_lower:
        return "FoxNews"
    if 'fbnhl' in url_lower and 'master.m3u8' in url_lower:
        return "FoxBusiness"
    if 'abcn-live-10' in url_lower:
        return "ABCNewsLive"
    if 'abcnews' in url_lower or 'abcn' in url_lower:
        return "ABC_GMA"
    if 'dai.google.com' in url_lower and 'master.m3u8' in url_lower:
        return "CBSNews"
    
    return None

def is_best_quality(key, url):
    if key and key in CHANNEL_CONFIG:
        patterns = CHANNEL_CONFIG[key]["priority_patterns"]
        url_lower = url.lower()
        for pattern in patterns:
            if pattern.lower() in url_lower:
                return True
    return False

def fix_extinf(extinf, key):
    if not key or key not in CHANNEL_CONFIG:
        return extinf
    
    config = CHANNEL_CONFIG[key]
    
    if 'tvg-id=' in extinf:
        extinf = re.sub(r'tvg-id="[^"]*"', f'tvg-id="{config["epg_id"]}"', extinf)
    else:
        extinf = extinf.replace('#EXTINF:', f'#EXTINF:-1 tvg-id="{config["epg_id"]}" ')
    
    if 'tvg-logo=' in extinf:
        logo_match = re.search(r'tvg-logo="([^"]*)"', extinf)
        if logo_match:
            current_logo = logo_match.group(1)
            if '.jpg' not in current_logo.lower() and '.jpeg' not in current_logo.lower():
                extinf = extinf.replace(f'tvg-logo="{current_logo}"', f'tvg-logo="{config["logo"]}"')
    else:
        extinf = extinf.replace('#EXTINF:', f'#EXTINF:-1 tvg-logo="{config["logo"]}" ')
    
    extinf = re.sub(r'group-title="[^"]*"', 'group-title="NEWS WORLD"', extinf)
    
    parts = extinf.split(',')
    if len(parts) > 1:
        extinf = ','.join(parts[:-1]) + f',{config["name"]}'
    
    return extinf

def check_epg_has_data(channel_id):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(EPG_URL, headers=headers, timeout=120)
        if response.status_code == 200:
            xml_content = gzip.decompress(response.content).decode('utf-8')
            xml_content = xml_content.replace('\x00', '')
            root = ET.fromstring(xml_content)
            
            today = datetime.now().strftime('%Y%m%d')
            tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y%m%d')
            day_after = (datetime.now() + timedelta(days=2)).strftime('%Y%m%d')
            
            count_today = 0
            count_tomorrow = 0
            count_day_after = 0
            
            for prog in root.findall('programme'):
                if prog.get('channel') == channel_id:
                    start = prog.get('start', '')[:8]
                    if start == today:
                        count_today += 1
                    elif start == tomorrow:
                        count_tomorrow += 1
                    elif start == day_after:
                        count_day_after += 1
            
            return count_today > 0 and count_tomorrow > 0, count_today, count_tomorrow, count_day_after
    except Exception as e:
        print(f"EPG check error: {e}")
    return False, 0, 0, 0

def main():
    print("=" * 70)
    print("Fixing lista5.m3u - Final Version")
    print("=" * 70)
    
    with open('/home/runner/work/JCTV/JCTV/lista5.m3u', 'r') as f:
        content = f.read()
    
    channels = parse_m3u(content)
    print(f"Found {len(channels)} channel entries")
    
    seen_keys = {}
    final_channels = []
    
    for ch in channels:
        name_match = re.search(r',(.+)$', ch['extinf'])
        name = name_match.group(1).strip() if name_match else ""
        url = ch['url']
        key = get_channel_key(name, url)
        
        if key:
            if key not in seen_keys:
                if is_best_quality(key, url):
                    seen_keys[key] = {"extinf": ch['extinf'], "url": url, "key": key}
                elif key not in seen_keys:
                    seen_keys[key] = {"extinf": ch['extinf'], "url": url, "key": key}
            else:
                if is_best_quality(key, url) and not is_best_quality(key, seen_keys[key]['url']):
                    seen_keys[key] = {"extinf": ch['extinf'], "url": url, "key": key}
        else:
            base = get_base_url(url)
            if base not in seen_keys:
                seen_keys[base] = {"extinf": ch['extinf'], "url": url, "key": None}
    
    final_channels = list(seen_keys.values())
    print(f"After deduplication: {len(final_channels)} channels")
    
    output = "#EXTM3U\n"
    
    for ch in final_channels:
        extinf = ch['extinf']
        url = ch['url']
        key = ch['key']
        
        extinf = fix_extinf(extinf, key)
        
        output += f"{extinf}\n{url}\n"
    
    output_file = '/home/runner/work/JCTV/JCTV/lista5.m3u'
    with open(output_file, 'w') as f:
        f.write(output)
    
    print(f"\nFile updated: {output_file}")
    print(f"EPG URL: {EPG_URL}")
    
    print("\n" + "=" * 70)
    print("EPG Verification - Next 3 Days")
    print("=" * 70)
    
    for key, config in CHANNEL_CONFIG.items():
        has_data, today, tomorrow, day_after = check_epg_has_data(config["epg_id"])
        print(f"  {config['name']}: {'OK' if has_data else 'NO DATA'} (Today: {today}, Tomorrow: {tomorrow}, Day after: {day_after})")
    
    print("\nDone!")

if __name__ == "__main__":
    main()
