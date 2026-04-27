#!/usr/bin/env python3
import re

EPG_URL = "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz"

LOGO_ALTERNATIVES = {
    "ABC News": "https://keyframe-cdn.abcnews.com/streamprovider9.jpg",
    "Fox News": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/f2121dc1-8a3e-4ec6-8b9e-302f8430a4c8/8bb59dab-fdb5-4129-aab5-ef44efbd2858/1280x720/match/400/225/image.jpg",
    "Fox Business": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/c9b2e2eb-7b87-435c-9510-eab2650ff944/8b584585-acf2-4c37-aa07-aaf2d077bb20/1280x720/match/676/380/image.jpg?ve=1&tl=1",
    "CBS News": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
}

def get_channel_key(url):
    url_lower = url.lower()
    
    if 'abcnews' in url_lower or 'abcn-live' in url_lower:
        if 'dssott' in url_lower:
            return 'abc_disneyplus'
        elif 'akamaized' in url_lower:
            return 'abc_akamai'
    elif 'foxnews' in url_lower:
        return 'foxnews'
    elif 'foxbusiness' in url_lower:
        return 'foxbusiness'
    elif 'cbsnews' in url_lower or 'dai.google' in url_lower:
        return 'cbsnews'
    
    return url

def normalize_name(name):
    name = name.strip()
    name = re.sub(r'\s*[-|]\s*Watch.*$', '', name)
    name = re.sub(r'\s*[-|]\s*Stream.*$', '', name)
    name = re.sub(r'\s*[-|]\s*Go\s*$', '', name)
    name = re.sub(r'\s*[-|].*live news stream.*$', '', name)
    name = re.sub(r'\s*[-|].*$', '', name)
    return name.strip()

def process_m3u(input_file, output_file):
    with open(input_file, 'r') as f:
        content = f.read()
    
    lines = content.split('\n')
    
    seen_keys = set()
    channels = []
    current_info = None
    
    for line in lines:
        line = line.rstrip('\r')
        
        if line.startswith('#EXTM3U'):
            continue
        
        if line.startswith('#EXTINF:'):
            current_info = line
            continue
        
        if line.startswith('http') and current_info:
            url = line.strip()
            
            key = get_channel_key(url)
            
            if key in seen_keys:
                current_info = None
                continue
            seen_keys.add(key)
            
            name_match = re.search(r',([^,]+)$', current_info)
            name = name_match.group(1) if name_match else "Unknown"
            name = normalize_name(name)
            
            logo_match = re.search(r'tvg-logo="([^"]*)"', current_info)
            current_logo = logo_match.group(1) if logo_match else ""
            
            if 'abcnews' in url.lower() or 'abcn-live' in url.lower():
                current_logo = LOGO_ALTERNATIVES["ABC News"]
                name = "ABC News Live"
            elif 'foxnews' in url.lower() and 'foxbusiness' not in url.lower():
                current_logo = LOGO_ALTERNATIVES["Fox News"]
                name = "Fox News"
            elif 'foxbusiness' in url.lower():
                current_logo = LOGO_ALTERNATIVES["Fox Business"]
                name = "Fox Business"
            elif 'cbsnews' in url.lower() or 'dai.google' in url.lower():
                current_logo = LOGO_ALTERNATIVES["CBS News"]
                name = "CBS News 24/7"
            
            channels.append({
                'name': name,
                'url': url,
                'logo': current_logo
            })
            
            current_info = None
    
    output_lines = ['#EXTM3U\n', '#EPGURL:' + EPG_URL + '\n', '\n']
    
    for ch in channels:
        output_lines.append(f'#EXTINF:-1 tvg-logo="{ch["logo"]}" group-title="NEWS WORLD",{ch["name"]}\n')
        output_lines.append(ch['url'] + '\n')
    
    with open(output_file, 'w') as f:
        f.writelines(output_lines)
    
    print(f"Original lines: {len(lines)}")
    print(f"Unique channels: {len(channels)}")
    print(f"EPG URL: {EPG_URL}")
    print(f"Output written to: {output_file}")
    
    for ch in channels:
        print(f"  - {ch['name']}: {ch['logo']}")

if __name__ == "__main__":
    process_m3u('/home/runner/work/JCTV/JCTV/lista5.m3u', '/home/runner/work/JCTV/JCTV/lista5.m3u.new')