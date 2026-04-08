#!/usr/bin/env python3
import requests
import json
import hashlib
import time
import re
import gzip
from datetime import datetime, timedelta
from urllib.parse import quote, urlparse
from io import BytesIO

VT_API_KEY = ""

CHANNEL_LOGOS = {
    "ABC News": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/14/American_Broadcasting_Company_Logo.svg/200px-American_Broadcasting_Company_Logo.svg.png",
    "Fox News": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0c/Fox_News_Channel_Logo.svg/200px-Fox_News_Channel_Logo.svg.png",
    "Fox Business": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b9/Fox_Business_Logo.svg/200px-Fox_Business_Logo.svg.png",
    "CBS News": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/00/CBS_Logo_-_2023.svg/200px-CBS_Logo_-_2023.svg.png",
}

EPG_SOURCES = {
    "ABC News": [
        ("https://raw.githubusercontent.com/usa-local-epg/usa-locals/main/usalocals.xml.gz", "abcn.us"),
    ],
    "Fox News": [
        ("https://raw.githubusercontent.com/usa-local-epg/usa-locals/main/usalocals.xml.gz", "foxnews.us"),
    ],
    "Fox Business": [
        ("https://raw.githubusercontent.com/usa-local-epg/usa-locals/main/usalocals.xml.gz", "foxbusiness.us"),
    ],
    "CBS News": [
        ("https://raw.githubusercontent.com/usa-local-epg/usa-locals/main/usalocals.xml.gz", "cbsnews.us"),
    ],
}

def get_url_info(url):
    url_hash = hashlib.md5(url.encode()).hexdigest()
    api_url = f"https://www.virustotal.com/api/v3/urls/{url_hash}"
    headers = {"x-apikey": VT_API_KEY} if VT_API_KEY else {}
    
    if not VT_API_KEY:
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

def fetch_epg(epg_url):
    try:
        response = requests.get(epg_url, timeout=60)
        if response.status_code == 200:
            if epg_url.endswith('.gz'):
                content = gzip.decompress(response.content)
            else:
                content = response.content
            return content.decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"  [ERROR] Fetching EPG: {e}")
    return None

def check_epg_programmes(epg_content, channel_id):
    if not epg_content:
        return False
    
    today = datetime.now()
    tomorrow = today + timedelta(days=1)
    day_after = today + timedelta(days=2)
    
    dates_to_check = [
        today.strftime("%Y%m%d"),
        tomorrow.strftime("%Y%m%d"),
        day_after.strftime("%Y%m%d")
    ]
    
    channel_pattern = rf'<channel\s+id="[^"]*{re.escape(channel_id)}[^"]*"\s*>'
    if not re.search(channel_pattern, epg_content, re.IGNORECASE):
        return False
    
    found_dates = set()
    for date in dates_to_check:
        if date in epg_content:
            found_dates.add(date)
    
    return len(found_dates) >= 1

def fix_logo_extension(logo_url):
    if not logo_url:
        return None
    
    if 'imgur.com' in logo_url.lower():
        return None
    
    if logo_url.lower().endswith('.png'):
        return logo_url
    
    if logo_url.lower().endswith('.jpg') or logo_url.lower().endswith('.jpeg'):
        return logo_url
    
    parsed = urlparse(logo_url)
    if parsed.path:
        path = parsed.path.lower()
        if path.endswith('.png'):
            return logo_url
        elif path.endswith('.jpg') or path.endswith('.jpeg'):
            return logo_url
        elif '.' in path and not path.endswith('.jpg'):
            base = path.rsplit('.', 1)[0]
            ext_match = re.search(r'\.(jpg|jpeg|png|gif|webp)$', path, re.IGNORECASE)
            if ext_match:
                return logo_url
    
    return logo_url

def get_best_logo(channel_name):
    for key, logo in CHANNEL_LOGOS.items():
        if key.lower() in channel_name.lower():
            return logo
    return None

def parse_m3u(filepath):
    channels = []
    current_channel = None
    
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    for i, line in enumerate(lines):
        line = line.strip()
        
        if line.startswith('#EXTINF:'):
            attrs = line[9:]
            tvg_logo = None
            group_title = None
            name = attrs
            
            logo_match = re.search(r'tvg-logo="([^"]*)"', attrs)
            if logo_match:
                tvg_logo = logo_match.group(1)
            
            group_match = re.search(r'group-title="([^"]*)"', attrs)
            if group_match:
                group_title = group_match.group(1)
            
            comma_idx = attrs.rfind(',')
            if comma_idx != -1:
                name = attrs[comma_idx+1:].strip()
            
            current_channel = {
                'name': name,
                'logo': tvg_logo,
                'group': group_title,
                'line_number': i + 1
            }
            
        elif line and not line.startswith('#'):
            if current_channel:
                current_channel['url'] = line
                
                if 'abcnews' in line.lower() or 'abc news' in current_channel.get('name', '').lower():
                    current_channel['type'] = 'ABC News'
                elif 'foxbusiness' in line.lower() or 'fox business' in current_channel.get('name', '').lower():
                    current_channel['type'] = 'Fox Business'
                elif 'foxnews' in line.lower() or 'fox news' in current_channel.get('name', '').lower():
                    current_channel['type'] = 'Fox News'
                elif 'cbsnews' in line.lower() or 'cbs news' in current_channel.get('name', '').lower():
                    current_channel['type'] = 'CBS News'
                else:
                    current_channel['type'] = 'Unknown'
                
                channels.append(current_channel)
                current_channel = None
    
    return channels

def main():
    print("=" * 70)
    print("Lista5 M3U Corrector - News Channels")
    print("=" * 70)
    
    channels = parse_m3u('lista5.m3u')
    print(f"\nFound {len(channels)} channels")
    
    unique_urls = {}
    for ch in channels:
        base_url = ch['url'].split('?')[0] if '?' in ch['url'] else ch['url']
        if base_url not in unique_urls:
            unique_urls[base_url] = ch
    
    print(f"Found {len(unique_urls)} unique stream URLs")
    
    print("\n" + "=" * 70)
    print("Testing VirusTotal for unique URLs...")
    print("=" * 70)
    
    url_results = {}
    for i, (base_url, ch) in enumerate(unique_urls.items(), 1):
        print(f"\n[{i}/{len(unique_urls)}] Checking: {base_url[:70]}...")
        
        malicious, suspicious, harmless, undetected, total = get_url_info(ch['url'])
        
        if total is not None:
            if malicious > 0:
                status = "MALICIOUS"
                keep = False
            elif suspicious > 0:
                status = "SUSPICIOUS"
                keep = False
            else:
                status = "CLEAN"
                keep = True
            
            print(f"  Result: {status} (M:{malicious}, S:{suspicious}, C:{harmless}, U:{undetected})")
            url_results[base_url] = {'keep': keep, 'status': status}
        else:
            print(f"  Result: UNKNOWN - keeping for safety")
            url_results[base_url] = {'keep': True, 'status': 'UNKNOWN'}
        
        time.sleep(1.5)
    
    print("\n" + "=" * 70)
    print("Testing EPG sources...")
    print("=" * 70)
    
    epg_cache = {}
    for ch_type, sources in EPG_SOURCES.items():
        print(f"\nTesting EPG for {ch_type}...")
        for epg_url, channel_id in sources:
            if epg_url not in epg_cache:
                print(f"  Fetching {epg_url[:60]}...")
                content = fetch_epg(epg_url)
                if content:
                    epg_cache[epg_url] = content
                    print(f"  EPG fetched successfully ({len(content)} bytes)")
                else:
                    print(f"  Failed to fetch EPG")
                    continue
            
            content = epg_cache.get(epg_url)
            if content:
                has_programs = check_epg_programmes(content, channel_id)
                if has_programs:
                    print(f"  Channel {channel_id} has programme data for today/tomorrow/day-after")
                    epg_cache[f"{ch_type}_url"] = epg_url
                    epg_cache[f"{ch_type}_id"] = channel_id
                else:
                    print(f"  Channel {channel_id} - limited/no programme data")
    
    print("\n" + "=" * 70)
    print("Generating corrected lista5.m3u...")
    print("=" * 70)
    
    output_lines = ["#EXTM3U"]
    
    seen_urls = set()
    channel_count = 0
    
    for ch in channels:
        base_url = ch['url'].split('?')[0] if '?' in ch['url'] else ch['url']
        
        if base_url in seen_urls:
            continue
        
        if not url_results.get(base_url, {}).get('keep', True):
            print(f"  Removing {ch['name']} - {url_results[base_url]['status']}")
            continue
        
        seen_urls.add(base_url)
        
        logo = ch.get('logo')
        if not logo or logo == "":
            logo = get_best_logo(ch['name'])
        
        if logo:
            logo = fix_logo_extension(logo)
        
        if not logo:
            logo = get_best_logo(ch['name'])
        
        group = ch.get('group') or "NEWS WORLD"
        
        ch_type = ch.get('type', 'Unknown')
        epg_line = ""
        if ch_type in EPG_SOURCES and f"{ch_type}_url" in epg_cache:
            epg_url = epg_cache[f"{ch_type}_url"]
            epg_line = f'\n#EXTVLCOPT:epg={epg_url}'
        
        output_lines.append(f"#EXTINF:-1 tvg-logo=\"{logo}\" group-title=\"{group}\",{ch['name']}")
        if epg_line:
            output_lines.append(epg_line)
        output_lines.append(ch['url'])
        
        channel_count += 1
    
    print(f"\nFinal channel count: {channel_count}")
    
    with open('lista5.m3u', 'w', encoding='utf-8') as f:
        f.write('\n'.join(output_lines))
    
    print(f"\nSaved corrected lista5.m3u")
    
    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)
    safe_count = sum(1 for r in url_results.values() if r.get('keep', True))
    unsafe_count = len(url_results) - safe_count
    print(f"URLs checked: {len(url_results)}")
    print(f"Kept (safe): {safe_count}")
    print(f"Removed (unsafe): {unsafe_count}")
    print(f"Channels in final list: {channel_count}")

if __name__ == "__main__":
    main()
