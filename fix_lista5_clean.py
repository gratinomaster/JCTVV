#!/usr/bin/env python3
import requests
import gzip
import xml.etree.ElementTree as ET
import re
import hashlib
import time
from datetime import datetime, timedelta
from urllib.parse import quote

EPG_URL = "https://iptv-epg.org/files/epg-us.xml.gz"

CHANNEL_MAPPING = {
    "ABCNewsLive": {
        "epg_id": "ABCNewsLive.us",
        "logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
        "name": "ABC News Live",
        "keep_patterns": ["abcn-live-10-cmaf-manifest"]
    },
    "FoxNews": {
        "epg_id": "FoxNewsChannel.us",
        "logo": "https://a57.foxnews.com/static.foxnews.com/foxnews.com/images/2024/09/fn-logo-social-share.png",
        "name": "Fox News Channel",
        "keep_patterns": ["FNCHLSv3/master.m3u8"]
    },
    "FoxBusiness": {
        "epg_id": "FoxBusiness.us",
        "logo": "https://a57.foxnews.com/static.foxbusiness.com/foxbusiness.com/2024/09/fb-logo-social-share.png",
        "name": "Fox Business",
        "keep_patterns": ["FBNHLSv3/master.m3u8"]
    },
    "CBSNews": {
        "epg_id": "CBSNews.us",
        "logo": "https://tvu-assets-prod.s3.amazonaws.com/cbsn-logo.png",
        "name": "CBS News 24/7",
        "keep_patterns": ["dai.google.com/linear"]
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

def get_channel_key(name, url):
    url_lower = url.lower()
    name_lower = name.lower()
    
    for key, mapping in CHANNEL_MAPPING.items():
        if key.lower() in name_lower or key.lower() in url_lower:
            return key
    return None

def should_keep_stream(key, url):
    if key and key in CHANNEL_MAPPING:
        patterns = CHANNEL_MAPPING[key]["keep_patterns"]
        url_lower = url.lower()
        return any(p.lower() in url_lower for p in patterns)
    return True

def fix_extinf(extinf, key):
    if not key or key not in CHANNEL_MAPPING:
        return extinf
    
    mapping = CHANNEL_MAPPING[key]
    
    extinf = re.sub(r' -1', '', extinf)
    
    if 'tvg-id=' not in extinf:
        extinf = f'#EXTINF:-1 tvg-id="{mapping["epg_id"]}" tvg-logo="{mapping["logo"]}" group-title="NEWS WORLD",{mapping["name"]}'
    else:
        extinf = re.sub(r'tvg-id="[^"]*"', f'tvg-id="{mapping["epg_id"]}"', extinf)
        extinf = re.sub(r'group-title="[^"]*"', 'group-title="NEWS WORLD"', extinf)
        
        if 'tvg-logo=' not in extinf:
            extinf = extinf.replace('#EXTINF:', f'#EXTINF:-1 tvg-logo="{mapping["logo"]}" ')
        else:
            logo_match = re.search(r'tvg-logo="([^"]*)"', extinf)
            if logo_match:
                current_logo = logo_match.group(1)
                if '.jpg' not in current_logo.lower() and '.jpeg' not in current_logo.lower():
                    extinf = extinf.replace(f'tvg-logo="{current_logo}"', f'tvg-logo="{mapping["logo"]}"')
    
    parts = extinf.split(',')
    if len(parts) > 1:
        extinf = ','.join(parts[:-1]) + f',{mapping["name"]}'
    
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
            
            count = 0
            for prog in root.findall('programme'):
                if prog.get('channel') == channel_id:
                    start = prog.get('start', '')[:8]
                    if start in [today, tomorrow, day_after]:
                        count += 1
            
            return count > 0, count
    except Exception as e:
        print(f"EPG check error: {e}")
    return False, 0

def main():
    print("=" * 70)
    print("Fixing lista5.m3u - Proper Deduplication")
    print("=" * 70)
    
    with open('/home/runner/work/JCTV/JCTV/lista5.m3u', 'r') as f:
        content = f.read()
    
    channels = parse_m3u(content)
    print(f"Found {len(channels)} channel entries")
    
    seen_keys = set()
    final_channels = []
    
    for ch in channels:
        name_match = re.search(r',(.+)$', ch['extinf'])
        name = name_match.group(1).strip() if name_match else ""
        url = ch['url']
        key = get_channel_key(name, url)
        
        if key:
            if key not in seen_keys:
                if should_keep_stream(key, url):
                    seen_keys.add(key)
                    final_channels.append({"extinf": ch['extinf'], "url": url, "key": key})
        else:
            final_channels.append({"extinf": ch['extinf'], "url": url, "key": None})
    
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
    
    for key, mapping in CHANNEL_MAPPING.items():
        has_data, count = check_epg_has_data(mapping["epg_id"])
        print(f"  {mapping['name']}: {'OK' if has_data else 'NO DATA'} ({count} programmes)")
    
    print("\nDone!")

if __name__ == "__main__":
    main()
