#!/usr/bin/env python3
import re
from datetime import datetime

CHANNEL_CONFIG = {
    "ABCNewsLive.us@NewsWorld": {
        "tvg_id": "ABCNews.us",
        "logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
        "clean_name": "ABC News Live"
    },
    "ABCNL.us@NewsWorld": {
        "tvg_id": "ABCNews.us",
        "logo": "https://keyframe-cdn.abcnews.com/streamprovider10.jpg",
        "clean_name": "ABC News Live"
    },
    "FoxNews.us@NewsWorld": {
        "tvg_id": "FoxNewsChannel.us",
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/3b09e0ef-610a-43d4-960b-78dc97ae2bd2/dc2e6082-3de1-40e8-a3ab-b6a61b18c3b1/1280x720/match/400/225/image.jpg",
        "clean_name": "Fox News"
    },
    "FoxBusiness.us@NewsWorld": {
        "tvg_id": "FoxBusinessNetwork.us",
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/c9b2e2eb-7b87-435c-9510-eab2650ff944/8b584585-acf2-4c37-aa07-aaf2d077bb20/1280x720/match/676/380/image.jpg",
        "clean_name": "Fox Business"
    },
    "CBSNews.us@NewsWorld": {
        "tvg_id": "CBSNews.us",
        "logo": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
        "clean_name": "CBS News"
    },
}

LOGO_FALLBACKS = {
    "ABC": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
    "Fox": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/3b09e0ef-610a-43d4-960b-78dc97ae2bd2/dc2e6082-3de1-40e8-a3ab-b6a61b18c3b1/1280x720/match/400/225/image.jpg",
    "CBS": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
}

def detect_channel_type(name):
    name_lower = name.lower()
    if 'abc' in name_lower:
        return 'ABC'
    elif 'fox' in name_lower:
        if 'business' in name_lower:
            return 'FoxBusiness'
        return 'Fox'
    elif 'cbs' in name_lower:
        return 'CBS'
    return None

def fix_logo_url(logo_url, channel_type):
    if not logo_url:
        return LOGO_FALLBACKS.get(channel_type, LOGO_FALLBACKS['ABC'])
    
    logo_lower = logo_url.lower()
    if 'imgur.com' in logo_lower:
        return LOGO_FALLBACKS.get(channel_type, LOGO_FALLBACKS['ABC'])
    
    if logo_url.lower().endswith('.jpg') or logo_url.lower().endswith('.jpeg') or 'jpg' in logo_lower:
        return logo_url
    
    if any(ext in logo_lower for ext in ['.png', '.svg', '.webp', '.gif']):
        return LOGO_FALLBACKS.get(channel_type, LOGO_FALLBACKS['ABC'])
    
    if not any(ext in logo_lower for ext in ['.jpg', '.jpeg', '.png', '.svg', '.webp', '.gif']):
        return LOGO_FALLBACKS.get(channel_type, LOGO_FALLBACKS['ABC'])
    
    return logo_url

def process_m3u():
    print("Processando lista5.m3u...")
    
    with open('lista5.m3u', 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    output_lines = []
    i = 0
    
    while i < len(lines):
        line = lines[i].rstrip('\n\r')
        
        if line.startswith('#EXTM3U'):
            today = datetime.now()
            epg_url = "https://raw.githubusercontent.com/JCTV/JCTV/main/lista5_epg_news_world.xml"
            output_lines.append(f'#EXTM3U x-tvg-url="{epg_url}"')
            i += 1
            continue
        
        if line.startswith('#EXTINF:'):
            extinf = line
            
            tvg_logo_match = re.search(r'tvg-logo="([^"]*)"', extinf)
            existing_logo = tvg_logo_match.group(1) if tvg_logo_match else None
            
            group_title_match = re.search(r'group-title="([^"]*)"', extinf)
            group_title = group_title_match.group(1) if group_title_match else "NEWS WORLD"
            
            comma_parts = extinf.split(',')
            if len(comma_parts) > 1:
                channel_name = comma_parts[-1].strip()
            else:
                channel_name = "Unknown Channel"
            
            channel_type = detect_channel_type(channel_name)
            
            tvg_id = None
            clean_name = None
            for key, config in CHANNEL_CONFIG.items():
                for config_name in [config['clean_name'], key]:
                    if config_name.lower() in channel_name.lower() or channel_name.lower() in config_name.lower():
                        tvg_id = config['tvg_id']
                        clean_name = config['clean_name']
                        existing_logo = fix_logo_url(existing_logo, detect_channel_type(channel_name))
                        break
                if tvg_id:
                    break
            
            if not tvg_id:
                if 'abc' in channel_name.lower():
                    tvg_id = "ABCNews.us"
                    clean_name = "ABC News Live"
                    existing_logo = fix_logo_url(existing_logo, 'ABC')
                elif 'fox' in channel_name.lower():
                    if 'business' in channel_name.lower():
                        tvg_id = "FoxBusinessNetwork.us"
                        clean_name = "Fox Business"
                        existing_logo = fix_logo_url(existing_logo, 'FoxBusiness')
                    else:
                        tvg_id = "FoxNewsChannel.us"
                        clean_name = "Fox News"
                        existing_logo = fix_logo_url(existing_logo, 'Fox')
                elif 'cbs' in channel_name.lower():
                    tvg_id = "CBSNews.us"
                    clean_name = "CBS News"
                    existing_logo = fix_logo_url(existing_logo, 'CBS')
                else:
                    tvg_id = "NewsWorld.us"
                    clean_name = channel_name
                    existing_logo = fix_logo_url(existing_logo, 'ABC')
            
            extinf_parts = []
            extinf_parts.append(f'#EXTINF:-1')
            if tvg_id:
                extinf_parts.append(f'tvg-id="{tvg_id}"')
            if existing_logo:
                extinf_parts.append(f'tvg-logo="{existing_logo}"')
            if group_title:
                extinf_parts.append(f'group-title="{group_title}"')
            extinf_parts.append(clean_name)
            
            new_extinf = ' '.join(extinf_parts)
            output_lines.append(new_extinf)
            
        elif line and line.startswith('http'):
            output_lines.append(line)
        
        i += 1
    
    with open('lista5.m3u', 'w', encoding='utf-8') as f:
        f.write('\n'.join(output_lines) + '\n')
    
    print(f"Arquivo lista5.m3u atualizado com {len([l for l in output_lines if l.startswith('#EXTINF')])} canais")

if __name__ == "__main__":
    process_m3u()