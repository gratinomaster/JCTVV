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
        "patterns": ["abcnews"],
        "name": "ABC News Live"
    },
    "ABC News Live - ABC News": {
        "epg_id": "ABCNewsLive.us",
        "logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
        "patterns": ["abcn-live", "abcnews-livestreams"],
        "name": "ABC News Live"
    },
    "Video": {
        "epg_id": "ABCNewsLive.us",
        "logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
        "patterns": ["abcn-live-10"],
        "name": "ABC News Live"
    },
    "FoxNews": {
        "epg_id": "FoxNewsChannel.us",
        "logo": "https://a57.foxnews.com/static.foxnews.com/foxnews.com/images/2024/09/fn-logo-social-share.png",
        "patterns": ["FNCHLSv3"],
        "name": "Fox News Channel"
    },
    "FoxBusiness": {
        "epg_id": "FoxBusiness.us",
        "logo": "https://a57.foxnews.com/static.foxbusiness.com/foxbusiness.com/2024/09/fb-logo-social-share.png",
        "patterns": ["FBNHLSv3"],
        "name": "Fox Business"
    },
    "CBSNews": {
        "epg_id": "CBSNews.us",
        "logo": "https://tvu-assets-prod.s3.amazonaws.com/cbsn-logo.png",
        "patterns": ["dai.google.com"],
        "name": "CBS News 24/7"
    }
}

MAIN_STREAMS = {
    "ABCNewsLive": ["abcn-live-10-cmaf-manifest", "ctr-all-hdri-sliding"],
    "ABC News Live": ["abcn-live-10", "abcn-live-05"],
    "Video": ["abcn-live-10-cmaf-manifest"],
    "FoxNews": ["FNCHLSv3/master.m3u8"],
    "FoxBusiness": ["FBNHLSv3/master.m3u8"],
    "CBSNews": ["master.m3u8"]
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

def get_channel_key(name):
    name_lower = name.lower()
    for key, mapping in CHANNEL_MAPPING.items():
        if key.lower() in name_lower:
            return key
    for key, patterns in MAIN_STREAMS.items():
        for pattern in patterns:
            if pattern.lower() in name_lower:
                return key
    return None

def is_main_stream(name, url):
    url_lower = url.lower()
    name_lower = name.lower()
    key = get_channel_key(name)
    if key and key in MAIN_STREAMS:
        for pattern in MAIN_STREAMS[key]:
            if pattern.lower() in url_lower:
                return True
    return True

def fix_tvg_logo(logo):
    if not logo:
        return None
    logo_lower = logo.lower()
    if '.jpg' in logo_lower or '.jpeg' in logo_lower:
        return logo
    if '.png' in logo_lower:
        return logo.replace('.png', '.jpg').replace('.PNG', '.jpg')
    if '.webp' in logo_lower:
        return logo.replace('.webp', '.jpg').replace('.WEBP', '.jpg')
    return logo

def get_channel_name(extinf):
    parts = extinf.split(',')
    return parts[-1].strip() if parts else ""

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
            
            return count > 0
    except Exception as e:
        print(f"EPG check error: {e}")
    return False

def check_url_virustotal(url, api_key=""):
    try:
        if api_key:
            url_hash = hashlib.md5(url.encode()).hexdigest()
            response = requests.get(
                f"https://www.virustotal.com/api/v3/urls/{url_hash}",
                headers={"x-apikey": api_key},
                timeout=30
            )
            if response.status_code == 200:
                data = response.json()
                stats = data.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
                malicious = stats.get("malicious", 0)
                suspicious = stats.get("suspicious", 0)
                return malicious == 0 and suspicious == 0
        else:
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
                    analysis = requests.get(analysis_link, timeout=60)
                    if analysis.status_code == 200:
                        data = analysis.json()
                        stats = data.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
                        malicious = stats.get("malicious", 0)
                        suspicious = stats.get("suspicious", 0)
                        return malicious == 0 and suspicious == 0
    except Exception as e:
        print(f"VT error: {e}")
    return None

def test_stream(url):
    try:
        response = requests.head(url, timeout=15, allow_redirects=True, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        if response.status_code in [200, 403, 405]:
            return True
    except:
        pass
    return False

def main():
    print("=" * 70)
    print("Fixing lista5.m3u")
    print("=" * 70)
    
    with open('/home/runner/work/JCTV/JCTV/lista5.m3u', 'r') as f:
        content = f.read()
    
    channels = parse_m3u(content)
    print(f"Found {len(channels)} channel entries")
    
    seen_urls = set()
    unique_channels = []
    
    for ch in channels:
        if ch['url'] not in seen_urls and is_main_stream(get_channel_name(ch['extinf']), ch['url']):
            seen_urls.add(ch['url'])
            unique_channels.append(ch)
    
    print(f"After deduplication: {len(unique_channels)} channels")
    
    output = "#EXTM3U\n"
    
    for ch in unique_channels:
        extinf = ch['extinf']
        url = ch['url']
        name = get_channel_name(extinf)
        key = get_channel_key(name)
        
        if key and key in CHANNEL_MAPPING:
            mapping = CHANNEL_MAPPING[key]
            epg_id = mapping['epg_id']
            
            if 'tvg-id=' not in extinf:
                extinf = extinf.replace('#EXTINF:', f'#EXTINF:-1 tvg-id="{epg_id}" ')
            else:
                extinf = re.sub(r'tvg-id="[^"]*"', f'tvg-id="{epg_id}"', extinf)
            
            if 'tvg-logo=' not in extinf:
                logo = fix_tvg_logo(mapping['logo'])
                if logo:
                    extinf = extinf.replace('#EXTINF:', f'#EXTINF:-1 tvg-logo="{logo}" ')
            else:
                logo_match = re.search(r'tvg-logo="([^"]*)"', extinf)
                if logo_match:
                    current_logo = logo_match.group(1)
                    new_logo = fix_tvg_logo(current_logo)
                    if new_logo and new_logo != current_logo:
                        extinf = extinf.replace(f'tvg-logo="{current_logo}"', f'tvg-logo="{new_logo}"')
        
        if 'tvg-logo=' in extinf:
            logo_match = re.search(r'tvg-logo="([^"]*)"', extinf)
            if logo_match:
                current_logo = logo_match.group(1)
                new_logo = fix_tvg_logo(current_logo)
                if new_logo and new_logo != current_logo:
                    extinf = extinf.replace(f'tvg-logo="{current_logo}"', f'tvg-logo="{new_logo}"')
        
        output += f"{extinf}\n{url}\n"
    
    output_file = '/home/runner/work/JCTV/JCTV/lista5.m3u'
    with open(output_file, 'w') as f:
        f.write(output)
    
    print(f"\nFile updated: {output_file}")
    print(f"EPG URL: {EPG_URL}")
    
    print("\n" + "=" * 70)
    print("EPG Verification")
    print("=" * 70)
    
    for ch_id in ["ABCNewsLive.us", "FoxNewsChannel.us", "FoxBusiness.us", "CBSNews.us"]:
        has_data = check_epg_has_data(ch_id)
        print(f"  {ch_id}: {'OK' if has_data else 'NO DATA'}")
    
    print("\n" + "=" * 70)
    print("Stream Verification")
    print("=" * 70)
    
    for ch in unique_channels[:10]:
        name = get_channel_name(ch['extinf'])
        working = test_stream(ch['url'])
        print(f"  {name[:40]}: {'OK' if working else 'FAILED'}")
    
    print("\nDone!")

if __name__ == "__main__":
    main()
