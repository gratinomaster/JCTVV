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
        "logo": "https://keyframe-cdn.abcnews.com/streamprovider10.jpg",
        "name": "ABC News Live",
        "keep_pattern": "abcn-live-10",
    },
    "ABC_GMA": {
        "epg_id": "ABCNewsLive.us",
        "logo": "https://keyframe-cdn.abcnews.com/streamprovider10.jpg",
        "name": "ABC News Live",
        "keep_pattern": "ctr-all-hdri-sliding",
    },
    "FoxNews": {
        "epg_id": "FoxNewsChannel.us",
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/ddf75165-e42b-482d-9255-434b80dcb2ec/53d05f4b-4872-4c8a-a5c3-08ceca360729/1280x720/match/400/225/image.jpg",
        "name": "Fox News Channel",
        "keep_pattern": "FNCHLSv3/master.m3u8",
    },
    "FoxBusiness": {
        "epg_id": "FoxBusiness.us",
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/c9b2e2eb-7b87-435c-9510-eab2650ff944/8b584585-acf2-4c37-aa07-aaf2d077bb20/1280x720/match/676/380/image.jpg",
        "name": "Fox Business",
        "keep_pattern": "FBNHLSv3/master.m3u8",
    },
    "CBSNews": {
        "epg_id": "CBSNews.us",
        "logo": "https://www.cbsnews.com/bundles/cbsnewsvideo/images/cbsn--main-bg.jpg",
        "name": "CBS News 24/7",
        "keep_pattern": "master.m3u8",
    }
}

# Map to unified EPG IDs
EPG_MAPPING = {
    "ABCNewsLive": "ABCNewsLive.us",
    "ABC_GMA": "ABCNewsLive.us",
    "FoxNews": "FoxNewsChannel.us",
    "FoxBusiness": "FoxBusiness.us",
    "CBSNews": "CBSNews.us",
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
    # For Disney+ URLs - mark as dead since streams expire
    if 'dssott.com' in url:
        if 'linear-abcnews' in url:
            return "dssott.com/abcnews-DEAD"
    
    # For Google DAI URLs
    if 'dai.google.com' in url:
        if '/stream/' in url:
            parts = url.split('/stream/')
            if len(parts) > 1:
                stream_id = parts[1].split('/')[0]
                return f"dai.google.com/stream/{stream_id}"
    
    # For akamaized ABC News
    if 'abcnews-livestreams.akamaized.net' in url:
        if 'abcn-live-10' in url:
            return "abcnews-livestreams.akamaized.net/abcn-live-10"
    
    # For Fox
    if '247.foxnews.com' in url:
        if 'FNCHLSv3/master.m3u8' in url:
            return "247.foxnews.com/FNCHLSv3"
    if '247.foxbusiness.com' in url:
        if 'FBNHLSv3/master.m3u8' in url:
            return "247.foxbusiness.com/FBNHLSv3"
    
    # Fallback
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".split('?')[0]

def get_channel_key(url):
    url_lower = url.lower()
    
    if 'fnchl' in url_lower and 'master.m3u8' in url_lower:
        return "FoxNews"
    if 'fbnhl' in url_lower and 'master.m3u8' in url_lower:
        return "FoxBusiness"
    if 'abcn-live-10' in url_lower:
        return "ABCNewsLive"
    if 'abcnews' in url_lower:
        return "ABC_GMA"
    if 'dai.google.com' in url_lower:
        return "CBSNews"
    
    return None

def is_best_stream(key, url):
    if key and key in CHANNEL_CONFIG:
        pattern = CHANNEL_CONFIG[key]["keep_pattern"]
        return pattern.lower() in url.lower()
    return False

def fix_extinf(extinf, config):
    extinf = re.sub(r'#EXTINF:-1\s+-1', '#EXTINF:-1', extinf)
    extinf = re.sub(r' -1', '', extinf)
    
    if not config:
        return extinf
    
    header = f'#EXTINF:-1 tvg-id="{config["epg_id"]}" tvg-logo="{config["logo"]}" group-title="NEWS WORLD",{config["name"]}'
    return header

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
    print("Fixing lista5.m3u - Complete Final Version")
    print("=" * 70)
    
    with open('/home/runner/work/JCTV/JCTV/lista5.m3u', 'r') as f:
        content = f.read()
    
    channels = parse_m3u(content)
    print(f"Found {len(channels)} channel entries")
    
    # Group channels by base URL
    url_groups = {}
    for ch in channels:
        url = ch['url']
        base = get_base_url(url)
        key = get_channel_key(url)
        
        if base not in url_groups:
            url_groups[base] = []
        url_groups[base].append((key, ch))
    
    # For each URL group, keep only the best stream
    final_channels = []
    for base, ch_list in url_groups.items():
        # Skip dead streams
        if 'DEAD' in base:
            print(f"  Skipping dead stream: {base}")
            continue
            
        best = None
        for key, ch in ch_list:
            if is_best_stream(key, ch['url']):
                best = ch
                break
        if best is None:
            key, ch = ch_list[0]
            best = ch
        final_channels.append(best)
    
    print(f"After deduplication: {len(final_channels)} channels")
    
    output = "#EXTM3U\n"
    
    for ch in final_channels:
        extinf = ch['extinf']
        url = ch['url']
        key = get_channel_key(url)
        
        config = CHANNEL_CONFIG.get(key)
        extinf = fix_extinf(extinf, config)
        
        output += f"{extinf}\n{url}\n"
    
    output_file = '/home/runner/work/JCTV/JCTV/lista5.m3u'
    with open(output_file, 'w') as f:
        f.write(output)
    
    print(f"\nFile updated: {output_file}")
    print(f"EPG URL: {EPG_URL}")
    
    print("\n" + "=" * 70)
    print("EPG Verification - Next 3 Days")
    print("=" * 70)
    
    unique_epg_ids = set()
    for ch in final_channels:
        key = get_channel_key(ch['url'])
        if key in EPG_MAPPING:
            unique_epg_ids.add(EPG_MAPPING[key])
    
    for epg_id in unique_epg_ids:
        has_data, today, tomorrow, day_after = check_epg_has_data(epg_id)
        print(f"  {epg_id}: {'OK' if has_data else 'NO DATA'} (Today: {today}, Tomorrow: {tomorrow}, Day after: {day_after})")
    
    print("\nDone!")

if __name__ == "__main__":
    main()
