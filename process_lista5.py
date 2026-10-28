#!/usr/bin/env python3
import re
import os
import sys
import json
import time
import hashlib
from urllib.parse import urlparse, urljoin
from pathlib import Path

M3U_FILE = '/home/runner/work/JCTVV/JCTVV/lista5.m3u'
BACKUP = f'/home/runner/work/JCTVV/JCTVV/lista5.m3u.bak.pre_fullfix_{time.strftime("%Y%m%d_%H%M%S")}'

# Known EPG sources (free/public where possible)
EPG_SOURCES = [
    # Try common sources
    {'url': 'https://epgshare01.online/epgshare01/epg_ripper_US1.xml.gz', 'name': 'epgshare01_us1'},
    {'url': 'https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.xml.gz', 'name': 'epgshare01_us_locals1'},
    {'url': 'https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz', 'name': 'epgshare01_us2'},
    {'url': 'https://i.mjh.nz/PlutoTV/us.xml.gz', 'name': 'mjh_pluto'},
    {'url': 'https://i.mjh.nz/SamsungTVPlus/us.xml.gz', 'name': 'mjh_samsung'},
]

# Default EPG URLs to add to playlist header
DEFAULT_EPG_URLS = [
    'https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz',
    'https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.xml.gz',
]

# Channel mappings with known tvg-ids and logos
CHANNEL_MAPPINGS = {
    'abc news': {
        'tvg_id': 'ABCNewsLive.us',
        'logo': 'https://upload.wikimedia.org/wikipedia/commons/thumb/6/63/ABC_News_logo.svg/960px-ABC_News_logo.svg.png',
        'name': 'ABC News Live'
    },
    'fox news': {
        'tvg_id': 'FoxNewsChannel.us',
        'logo': 'https://upload.wikimedia.org/wikipedia/commons/thumb/6/67/Fox_News_Channel_logo.svg/960px-Fox_News_Channel_logo.svg.png',
        'name': 'Fox News Channel'
    },
    'fox business': {
        'tvg_id': 'FoxBusinessNetwork.us',
        'logo': 'https://upload.wikimedia.org/wikipedia/commons/thumb/8/8a/Fox_Business.svg/960px-Fox_Business.svg.png',
        'name': 'Fox Business Network'
    },
    'cbs news': {
        'tvg_id': 'CBSNews247.us',
        'logo': 'https://upload.wikimedia.org/wikipedia/commons/thumb/b/b0/CBS_News_247_logo.svg/960px-CBS_News_247_logo.svg.png',
        'name': 'CBS News 24/7'
    }
}

def backup_file():
    try:
        import shutil
        shutil.copy2(M3U_FILE, BACKUP)
        print(f'Backed up to {BACKUP}')
    except Exception as e:
        print(f'Backup failed: {e}')

def read_m3u():
    with open(M3U_FILE, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    return content

def parse_m3u(content):
    lines = content.splitlines()
    entries = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXTM3U'):
            i += 1
            continue
        if line.startswith('#EXTINF'):
            extinf = line
            # Look for next non-empty line that's a URL
            j = i + 1
            while j < len(lines) and lines[j].strip() == '':
                j += 1
            if j < len(lines):
                url_line = lines[j].strip()
                if url_line and not url_line.startswith('#'):
                    entries.append({
                        'extinf': extinf,
                        'url': url_line,
                        'start_idx': i,
                        'url_idx': j
                    })
                    i = j + 1
                    continue
            i += 1
            continue
        # Check if it's a URL without preceding EXTINF - flag it
        if line and not line.startswith('#') and '://' in line:
            # This is bad - URL without EXTINF
            entries.append({
                'extinf': None,
                'url': line,
                'orphan': True,
                'start_idx': i,
                'url_idx': i
            })
        i += 1
    return entries, lines

def is_jpg_url(url):
    if not url:
        return False
    url_lower = url.lower()
    # Check if ends with .jpg or .jpeg
    if url_lower.endswith('.jpg') or url_lower.endswith('.jpeg'):
        return True
    # Check if contains .jpg in path
    if '.jpg' in url_lower or '.jpeg' in url_lower:
        # Make sure it's not just in query params oddly
        parsed = urlparse(url)
        path = parsed.path.lower()
        if path.endswith('.jpg') or path.endswith('.jpeg'):
            return True
    return False

def convert_to_jpg_url(logo_url):
    if not logo_url:
        return logo_url
    if is_jpg_url(logo_url):
        return logo_url
    # Try to convert common cases
    # For example, replace .png with .jpg if possible, or just add .jpg
    parsed = urlparse(logo_url)
    path = parsed.path
    if path.lower().endswith(('.png', '.gif', '.webp', '.svg')):
        new_path = re.sub(r'\.(png|gif|webp|svg)$', '.jpg', path, flags=re.IGNORECASE)
        new_url = logo_url.replace(path, new_path)
        return new_url
    # If no extension, try to append .jpg
    if '.' not in os.path.basename(path):
        new_url = logo_url.rstrip('/') + '.jpg'
        return new_url
    return logo_url

def fix_extinf(extinf, entry_name, logo_url=None):
    # Extract existing attributes
    tvg_id_match = re.search(r'tvg-id="([^"]*)"', extinf)
    tvg_name_match = re.search(r'tvg-name="([^"]*)"', extinf)
    tvg_logo_match = re.search(r'tvg-logo="([^"]*)"', extinf)
    group_title_match = re.search(r'group-title="([^"]*)"', extinf)
    
    # Determine channel type and get mapping
    name_lower = entry_name.lower()
    mapping = None
    for key, m in CHANNEL_MAPPINGS.items():
        if key in name_lower:
            mapping = m
            break
    
    # Build new extinf
    # Keep duration and other parts
    duration_match = re.match(r'#EXTINF:(-?\d+)', extinf)
    duration = duration_match.group(1) if duration_match else '-1'
    
    new_attrs = []
    new_attrs.append(f'-{duration}')
    
    # Set tvg-id
    if mapping and mapping['tvg_id']:
        new_attrs.append(f'tvg-id="{mapping["tvg_id"]}"')
    elif tvg_id_match and tvg_id_match.group(1):
        new_attrs.append(f'tvg-id="{tvg_id_match.group(1)}"')
    else:
        # Generate a tvg-id based on name
        clean_name = re.sub(r'[^a-zA-Z0-9]', '', entry_name)
        if mapping:
            new_attrs.append(f'tvg-id="{mapping["tvg_id"]}"')
        else:
            new_attrs.append(f'tvg-id="{clean_name}.us"')
    
    # Set tvg-name
    if mapping and mapping['name']:
        new_attrs.append(f'tvg-name="{mapping["name"]}"')
    elif tvg_name_match and tvg_name_match.group(1):
        new_attrs.append(f'tvg-name="{tvg_name_match.group(1)}"')
    else:
        new_attrs.append(f'tvg-name="{entry_name}"')
    
    # Set tvg-logo - must be .jpg
    logo_to_use = logo_url
    if mapping and mapping['logo']:
        logo_to_use = mapping['logo']
    elif tvg_logo_match and tvg_logo_match.group(1):
        logo_to_use = tvg_logo_match.group(1)
    
    if logo_to_use:
        # Convert to jpg if not already
        logo_to_use = convert_to_jpg_url(logo_to_use)
        # Avoid imgur
        if 'imgur.com' in logo_to_use.lower():
            # Use fallback
            if mapping and mapping['logo']:
                logo_to_use = convert_to_jpg_url(mapping['logo'])
            else:
                logo_to_use = convert_to_jpg_url('https://upload.wikimedia.org/wikipedia/commons/thumb/6/63/TV_icon.svg/240px-TV_icon.svg.jpg')
        new_attrs.append(f'tvg-logo="{logo_to_use}"')
    else:
        # Add default logo
        if mapping and mapping['logo']:
            logo_to_use = convert_to_jpg_url(mapping['logo'])
            new_attrs.append(f'tvg-logo="{logo_to_use}"')
    
    # Set group-title
    if group_title_match and group_title_match.group(1):
        new_attrs.append(f'group-title="{group_title_match.group(1)}"')
    else:
        new_attrs.append(f'group-title="NEWS WORLD"')
    
    # Channel name
    new_extinf = '#EXTINF:' + ' '.join(new_attrs) + f',{entry_name}'
    return new_extinf

def process_m3u():
    backup_file()
    content = read_m3u()
    entries, lines = parse_m3u(content)
    
    print(f'Found {len(entries)} entries')
    
    # Build new content
    new_lines = []
    # Add header with EPG URLs
    epg_header = '#EXTM3U'
    for epg_url in DEFAULT_EPG_URLS:
        epg_header += f' url-tvg="{epg_url}"'
    new_lines.append(epg_header)
    
    processed_urls = set()
    for entry in entries:
        if entry.get('orphan'):
            # Skip orphan URLs without EXTINF
            print(f'Skipping orphan URL: {entry["url"][:60]}...')
            continue
        
        extinf = entry['extinf']
        url = entry['url']
        
        # Skip duplicates of same URL
        if url in processed_urls:
            continue
        processed_urls.add(url)
        
        # Extract channel name from EXTINF
        name_match = re.search(r',(.+)$', extinf)
        channel_name = name_match.group(1).strip() if name_match else 'Unknown'
        
        # Check logo
        logo_match = re.search(r'tvg-logo="([^"]*)"', extinf)
        logo_url = logo_match.group(1) if logo_match else None
        
        # Fix EXTINF
        fixed_extinf = fix_extinf(extinf, channel_name, logo_url)
        new_lines.append(fixed_extinf)
        new_lines.append(url)
    
    new_content = '\n'.join(new_lines) + '\n'
    
    with open(M3U_FILE, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f'Processed M3U written. Total lines: {len(new_lines)}')
    return new_content

if __name__ == '__main__':
    process_m3u()
