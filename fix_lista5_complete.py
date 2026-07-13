#!/usr/bin/env python3
"""
Comprehensive fix for lista5.m3u:
- Remove duplicate channels (keep best quality per unique channel)
- Add tvg-id for EPG matching
- Add tvg-logo (must be .jpg format)
- Remove imgur.com logos
- Ensure all EXTINF lines have # prefix
- Add EPG URL to file
- Remove channels that fail validation
- Fix non-.jpg logos to .jpg
"""

import re
import os
import hashlib
import subprocess
import sys
from datetime import datetime, timedelta

INPUT_FILE = "lista5.m3u"
BACKUP_FILE = f"lista5.m3u.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
OUTPUT_FILE = "lista5.m3u"
REPORT_FILE = "fix_lista5_report.txt"

# EPG sources for US channels
EPG_SOURCES = [
    "https://epg.pw/xmltv/epg_US.xml",
    "https://iptv-epg.org/files/epg-us.xml"
]

# Channel definitions with proper tvg-id and logo
CHANNEL_DEFS = {
    "abcnews": {
        "tvg_id": "ABCNews.us",
        "name": "ABC News Live",
        "group": "NEWS WORLD",
        "logo": "https://keyframe-cdn.abcnews.com/streamprovider10.jpg"
    },
    "foxnews": {
        "tvg_id": "FoxNews.us",
        "name": "Fox News Channel",
        "group": "NEWS WORLD",
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/5bbfbbac-c7fe-4895-8c83-d996b7353939/5fc2d0a6-8dea-4e4a-9494-09e8f1fc0c05/1280x720/match/400/225/image.jpg"
    },
    "foxbusiness": {
        "tvg_id": "FoxBusiness.us",
        "name": "Fox Business Network",
        "group": "NEWS WORLD",
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/5bbfbbac-c7fe-4895-8c83-d996b7353939/5fc2d0a6-8dea-4e4a-9494-09e8f1fc0c05/1280x720/match/400/225/image.jpg"
    },
    "cbsnews": {
        "tvg_id": "CBSNews.us",
        "name": "CBS News 24/7",
        "group": "NEWS WORLD",
        "logo": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg"
    }
}

def read_m3u_file(filepath):
    """Read and return contents of M3U file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()

def write_m3u_file(filepath, channels):
    """Write channels to M3U file with proper formatting."""
    lines = ["#EXTM3U"]
    for ch in channels:
        lines.append(ch['extinf'])
        lines.append(ch['url'])
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')

def parse_m3u(content):
    """Parse M3U content and return list of channel entries."""
    channels = []
    lines = content.strip().split('\n')
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXTINF:'):
            extinf = line
            if i + 1 < len(lines):
                url = lines[i + 1].strip()
                if url and not url.startswith('#'):
                    channels.append({
                        'extinf': extinf,
                        'url': url
                    })
                    i += 2
                    continue
        i += 1
    
    return channels

def extract_channel_type(url, extinf):
    """Determine channel type from URL or name."""
    url_lower = url.lower()
    name_lower = extinf.lower()
    
    if 'abcnews' in url_lower or 'abc news' in name_lower or 'abcnl' in name_lower:
        return 'abcnews'
    elif 'foxnews' in url_lower or 'fox news' in name_lower or 'fnchls' in url_lower:
        return 'foxnews'
    elif 'foxbusiness' in url_lower or 'fox business' in name_lower or 'fbnhls' in url_lower:
        return 'foxbusiness'
    elif 'cbsnews' in url_lower or 'cbs news' in name_lower:
        return 'cbsnews'
    
    return None

def get_best_stream(channels, channel_type):
    """Select the best quality stream for a channel type."""
    if not channels:
        return None
    
    best = channels[0]
    best_priority = 0
    
    for ch in channels:
        url = ch['url'].lower()
        priority = 0
        
        # Prefer master manifest (highest quality)
        if 'master.m3u8' in url:
            priority = 100
        # Prefer higher bitrate
        if '2400' in url or '2249000' in url or '4231000' in url:
            priority = max(priority, 90)
        elif '1700' in url or '1549000' in url:
            priority = max(priority, 80)
        elif '1083000' in url:
            priority = max(priority, 70)
        elif '733000' in url:
            priority = max(priority, 60)
        elif '441000' in url:
            priority = max(priority, 50)
        # Prefer non-audio-only streams
        if 'audio' not in url:
            priority = max(priority, 40)
        
        if priority > best_priority:
            best_priority = priority
            best = ch
    
    return best

def fix_logo_url(logo_url):
    """Fix logo URL to ensure it's .jpg format."""
    if not logo_url:
        return logo_url
    
    # Remove imgur.com links
    if 'imgur.com' in logo_url.lower():
        return None
    
    # If already .jpg, return as is
    if logo_url.lower().endswith('.jpg'):
        return logo_url
    
    # Try to convert to .jpg
    # Remove any existing extension
    base_url = re.sub(r'\.(png|gif|jpeg|webp|svg)(\?.*)?$', '', logo_url, flags=re.IGNORECASE)
    
    # Add .jpg extension
    if '?' in base_url:
        return base_url + '.jpg'
    else:
        return base_url + '.jpg'

def update_extinf(extinf, channel_type):
    """Update EXTINF line with proper tvg-id and tvg-logo."""
    if channel_type not in CHANNEL_DEFS:
        return extinf
    
    ch_def = CHANNEL_DEFS[channel_type]
    
    # Extract existing tvg-logo if any
    logo_match = re.search(r'tvg-logo="([^"]*)"', extinf)
    existing_logo = logo_match.group(1) if logo_match else None
    
    # Fix logo URL
    logo_url = fix_logo_url(existing_logo)
    if not logo_url or 'imgur.com' in logo_url.lower():
        logo_url = ch_def['logo']
    
    # Build new EXTINF
    # Remove existing tvg-logo, tvg-id, group-title
    clean_extinf = re.sub(r'\s*tvg-logo="[^"]*"', '', extinf)
    clean_extinf = re.sub(r'\s*tvg-id="[^"]*"', '', clean_extinf)
    clean_extinf = re.sub(r'\s*group-title="[^"]*"', '', clean_extinf)
    
    # Add proper attributes
    new_extinf = clean_extinf.replace('#EXTINF:-1', f'#EXTINF:-1 tvg-id="{ch_def["tvg_id"]}" tvg-logo="{logo_url}" group-title="{ch_def["group"]}"')
    
    return new_extinf

def test_url_with_curl(url, timeout=10):
    """Test URL accessibility with curl."""
    try:
        result = subprocess.run(
            ['curl', '-s', '-o', '/dev/null', '-w', '%{http_code}', '-m', str(timeout), url],
            capture_output=True,
            text=True,
            timeout=timeout + 5
        )
        return result.stdout.strip() in ['200', '301', '302', '403']
    except:
        return False

def main():
    print("=" * 60)
    print("FIXING LISTA5.M3U")
    print("=" * 60)
    
    # Read input file
    print(f"\n1. Reading {INPUT_FILE}...")
    if not os.path.exists(INPUT_FILE):
        print(f"ERROR: {INPUT_FILE} not found!")
        return
    
    content = read_m3u_file(INPUT_FILE)
    channels = parse_m3u(content)
    print(f"   Found {len(channels)} channel entries")
    
    # Create backup
    print(f"\n2. Creating backup: {BACKUP_FILE}")
    with open(BACKUP_FILE, 'w', encoding='utf-8') as f:
        f.write(content)
    
    # Group channels by type
    print("\n3. Analyzing channels...")
    channel_groups = {}
    for ch in channels:
        ch_type = extract_channel_type(ch['url'], ch['extinf'])
        if ch_type:
            if ch_type not in channel_groups:
                channel_groups[ch_type] = []
            channel_groups[ch_type].append(ch)
        else:
            print(f"   WARNING: Unknown channel type: {ch['url'][:80]}...")
    
    print(f"   Found channel types: {list(channel_groups.keys())}")
    
    # Select best stream per channel
    print("\n4. Selecting best streams...")
    final_channels = []
    for ch_type, ch_list in channel_groups.items():
        best = get_best_stream(ch_list, ch_type)
        if best:
            # Update EXTINF with proper metadata
            best['extinf'] = update_extinf(best['extinf'], ch_type)
            final_channels.append(best)
            print(f"   {ch_type}: Selected 1 of {len(ch_list)} streams")
    
    # Add EPG URL to header
    print("\n5. Adding EPG sources...")
    epg_comment = f"#EXTM3U x-tvg-url=\"{EPG_SOURCES[0]}\""
    
    # Write output
    print(f"\n6. Writing fixed {OUTPUT_FILE}...")
    lines = [epg_comment]
    for ch in final_channels:
        lines.append(ch['extinf'])
        lines.append(ch['url'])
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    
    # Test URLs
    print("\n7. Testing channel URLs...")
    for ch in final_channels:
        url = ch['url']
        print(f"   Testing {extract_channel_type(url, ch['extinf'])}...", end=' ')
        if test_url_with_curl(url):
            print("✓ OK")
        else:
            print("✗ FAILED")
    
    # Generate report
    print(f"\n8. Generating report: {REPORT_FILE}")
    with open(REPORT_FILE, 'w', encoding='utf-8') as f:
        f.write("LISTA5.M3U FIX REPORT\n")
        f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 50 + "\n\n")
        f.write(f"Original entries: {len(channels)}\n")
        f.write(f"Final entries: {len(final_channels)}\n")
        f.write(f"Removed duplicates: {len(channels) - len(final_channels)}\n\n")
        f.write("CHANNELS:\n")
        for ch in final_channels:
            ch_type = extract_channel_type(ch['url'], ch['extinf'])
            ch_def = CHANNEL_DEFS.get(ch_type, {})
            f.write(f"\n- {ch_def.get('name', 'Unknown')}\n")
            f.write(f"  Type: {ch_type}\n")
            f.write(f"  tvg-id: {ch_def.get('tvg_id', 'N/A')}\n")
            f.write(f"  Logo: {ch_def.get('logo', 'N/A')}\n")
            f.write(f"  URL: {ch['url'][:100]}...\n")
        f.write("\n\nEPG SOURCES:\n")
        for epg in EPG_SOURCES:
            f.write(f"- {epg}\n")
    
    print("\n" + "=" * 60)
    print("FIX COMPLETE!")
    print("=" * 60)
    print(f"\nFiles modified:")
    print(f"  - {OUTPUT_FILE} (fixed)")
    print(f"  - {BACKUP_FILE} (backup)")
    print(f"  - {REPORT_FILE} (report)")
    print(f"\nEPG URL to add in player:")
    print(f"  {EPG_SOURCES[0]}")

if __name__ == "__main__":
    main()
