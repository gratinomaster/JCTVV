#!/usr/bin/env python3
"""
Process lista5.m3u to add proper EPG configuration and test channels.
"""
import requests
import gzip
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from collections import OrderedDict
import re
import hashlib
import time

EPG_SOURCES = [
    "https://iptv-epg.org/files/epg-us.xml.gz",
    "https://github.com/iptv-org/epg/raw/master/guide/us.xml.gz"
]

CHANNEL_EPG_MAP = {
    "ABC News Live": {"tvg_id": "ABCWBMA.us", "name": "ABC News Live"},
    "ABC News": {"tvg_id": "ABCWBMA.us", "name": "ABC News Live"},
    "Fox Business Go": {"tvg_id": "FoxBusiness.us", "name": "Fox Business"},
    "Fox Business": {"tvg_id": "FoxBusiness.us", "name": "Fox Business"},
    "Fox News": {"tvg_id": "FoxNewsChannel.us", "name": "Fox News"},
    "CBS News": {"tvg_id": "CBSNews.us", "name": "CBS News"},
    "CBS News 24/7": {"tvg_id": "CBSNews.us", "name": "CBS News"},
}

LOGO_MAP = {
    "ABCWBMA.us": "https://static.wikia.nocookie.net/logopedia/images/8/84/ABC_News_Live.png/revision/latest?path-is-filename&width=160&height=90",
    "FoxNewsChannel.us": "https://upload.wikimedia.org/wikipedia/commons/0/0c/Fox_News_Channel_logo.svg",
    "FoxBusiness.us": "https://upload.wikimedia.org/wikipedia/commons/2/23/Fox_Business_Logo.svg",
    "CBSNews.us": "https://upload.wikimedia.org/wikipedia/commons/7/76/CBS_News.svg",
}

def download_epg(url):
    """Download and decompress EPG data."""
    try:
        response = requests.get(url, timeout=60, headers={'Accept-Encoding': 'gzip'})
        if response.status_code == 200:
            if url.endswith('.gz'):
                return gzip.decompress(response.content)
            return response.content
    except Exception as e:
        print(f"Error downloading EPG from {url}: {e}")
    return None

def find_channel_in_epg(epg_content, tvg_id):
    """Search for channel in EPG and return its programmes."""
    if not epg_content:
        return []
    try:
        root = ET.fromstring(epg_content)
        channel_elems = root.findall(f".//channel[@id='{tvg_id}']")
        if channel_elems:
            channel_id = channel_elems[0].get('id')
            programmes = root.findall(f".//programme[@channel='{channel_id}']")
            return programmes
    except Exception as e:
        print(f"Error parsing EPG: {e}")
    return []

def check_programming(epg_content, tvg_id, days_ahead=0):
    """Check if there is programming for a specific day."""
    target_date = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y%m%d")
    programmes = find_channel_in_epg(epg_content, tvg_id)
    
    found_programs = []
    for prog in programmes:
        start = prog.get('start', '')
        if start.startswith(target_date):
            title = prog.find('title')
            if title is not None:
                found_programs.append(title.text)
    
    return len(found_programs) > 0, found_programs[:5]

def identify_channel(name):
    """Identify channel and return EPG info."""
    name_lower = name.lower()
    for key, info in CHANNEL_EPG_MAP.items():
        if key.lower() in name_lower:
            return info
    return None

def test_channel_url(url):
    """Test if channel URL is accessible."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, timeout=10, headers=headers, stream=True)
        return response.status_code < 400
    except:
        return False

def test_virustotal(url):
    """Test URL with VirusTotal (simulated - real API key needed)."""
    url_hash = hashlib.md5(url.encode()).hexdigest()
    return True, "URL scanned"

def clean_extinf(line):
    """Clean and standardize EXTINF line."""
    if not line.startswith('#EXTINF:'):
        return line
    
    base = '#EXTINF:-1'
    
    if 'tvg-logo=' in line:
        match = re.search(r'tvg-logo="([^"]+)"', line)
        if match:
            base += f' tvg-logo="{match.group(1)}"'
    
    if 'group-title=' in line:
        match = re.search(r'group-title="([^"]+)"', line)
        if match:
            base += f' group-title="{match.group(1)}"'
    
    name_match = re.search(r',([^,\n]+)$', line)
    name = name_match.group(1).strip() if name_match else ""
    
    return f"{base},{name}"

def process_m3u():
    """Process the M3U file and create corrected version."""
    with open('lista5.m3u', 'r') as f:
        lines = f.readlines()
    
    seen_channels = OrderedDict()
    current_extinf = None
    
    for i, line in enumerate(lines):
        line = line.strip()
        if line.startswith('#EXTINF:'):
            current_extinf = line
        elif line.startswith('http'):
            url = line
            if current_extinf:
                name_match = re.search(r',([^,\n]+)$', current_extinf)
                name = name_match.group(1).strip() if name_match else "Unknown"
                
                if name not in seen_channels:
                    seen_channels[name] = {
                        'extinf': current_extinf,
                        'url': url
                    }
            current_extinf = None
    
    return seen_channels

print("=== Processing lista5.m3u ===\n")

channels = process_m3u()
print(f"Found {len(channels)} unique channels\n")

epg_content = None
for epg_url in EPG_SOURCES:
    print(f"Testing EPG: {epg_url}")
    epg_content = download_epg(epg_url)
    if epg_content:
        print(f"  ✓ EPG downloaded successfully ({len(epg_content)} bytes)")
        break
    else:
        print(f"  ✗ Failed to download")

print("\n=== Testing EPG Programming ===\n")

if epg_content:
    for name, info in channels.items():
        epg_info = identify_channel(name)
        if epg_info:
            tvg_id = epg_info['tvg_id']
            
            today_ok, today_progs = check_programming(epg_content, tvg_id, 0)
            tomorrow_ok, tomorrow_progs = check_programming(epg_content, tvg_id, 1)
            day_after_ok, day_after_progs = check_programming(epg_content, tvg_id, 2)
            
            print(f"{name} ({tvg_id}):")
            print(f"  Today: {'✓' if today_ok else '✗'}")
            print(f"  Tomorrow: {'✓' if tomorrow_ok else '✗'}")
            print(f"  Day after: {'✓' if day_after_ok else '✗'}")

print("\n=== Testing Channel URLs ===\n")

for name, info in channels.items():
    url = info['url']
    status = "✓" if test_channel_url(url) else "✗"
    print(f"{name}: {status}")

print("\n=== Generating Corrected M3U ===\n")

output_lines = ["#EXTM3U"]

for name, info in channels.items():
    extinf = clean_extinf(info['extinf'])
    url = info['url']
    
    epg_info = identify_channel(name)
    if epg_info:
        tvg_id = epg_info['tvg_id']
        logo = LOGO_MAP.get(tvg_id, "")
        
        if 'tvg-logo=' in extinf:
            extinf = re.sub(r'tvg-logo="[^"]*"', f'tvg-logo="{logo}"', extinf)
        else:
            extinf = extinf.replace(',', f' tvg-logo="{logo}",', 1)
        
        extinf = f'{extinf} tvg-id="{tvg_id}" x-tvg-url="{EPG_SOURCES[0]}"'
    
    output_lines.append(extinf)
    output_lines.append(url)

with open('lista5_corrigida.m3u', 'w') as f:
    f.write('\n'.join(output_lines))

print(f"Created lista5_corrigida.m3u with {len(output_lines)//2} channels")