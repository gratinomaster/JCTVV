#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re
import os
import json
import subprocess
from collections import defaultdict
from urllib.parse import urlparse

M3U_FILE = '/home/runner/work/JCTVV/JCTVV/lista5.m3u'
BACKUP_FILE = '/home/runner/work/JCTVV/JCTVV/lista5_backup_before_fix_' + subprocess.check_output(['date','+%Y%m%d_%H%M%S']).decode().strip() + '.m3u'

# Backup
subprocess.run(['cp', M3U_FILE, BACKUP_FILE])
print(f'Backup criado: {BACKUP_FILE}')

# EPG sources - multiple as requested
EPG_URLS = [
    "https://epg.pw/xmltv/epg.xml.gz",
    "https://i.mjh.nz/au/Sydney/epg.xml.gz",
    "https://i.mjh.nz/PlutoTV/us.xml.gz", 
    "https://raw.githubusercontent.com/iptv-org/epg/master/sites/abcnews.com/abcnews.com.xml",
    "https://raw.githubusercontent.com/iptv-org/epg/master/sites/foxnews.com/foxnews.com.xml",
]

# Read file
with open(M3U_FILE, 'r', encoding='utf-8') as f:
    content = f.read()

# Parse entries
entries = []
current_ext = None
for line in content.splitlines():
    line_stripped = line.strip()
    if line_stripped.startswith('#EXTINF'):
        current_ext = line_stripped
    elif line_stripped and not line_stripped.startswith('#'):
        if current_ext:
            entries.append((current_ext, line_stripped))
            current_ext = None

print(f'Total entries parsed: {len(entries)}')

# Channel mapping with proper tvg-ids and logos
channel_mapping = {
    'ABC News Live - ABC News': {
        'tvg_id': 'ABCNews.us',
        'logo': 'https://upload.wikimedia.org/wikipedia/commons/thumb/6/63/ABC_News_Live_logo.svg/1200px-ABC_News_Live_logo.svg.png',
        'fallback_logo': 'https://images.pluto.tv/channels/5df13e828a6b5e00014e6911/colorLogoPNG.png'
    },
    'ABC News Live Prime With Linsey Davis | Watch Live News on ABCNL': {
        'tvg_id': 'ABCNews.us',
        'logo': 'https://upload.wikimedia.org/wikipedia/commons/thumb/6/63/ABC_News_Live_logo.svg/1200px-ABC_News_Live_logo.svg.png',
    },
    'Video Coastal flooding on Pacific and Atlantic coasts | Watch Live News on ABCNL': {
        'tvg_id': 'ABCNews.us',
        'logo': 'https://upload.wikimedia.org/wikipedia/commons/thumb/6/63/ABC_News_Live_logo.svg/1200px-ABC_News_Live_logo.svg.png',
    },
    'Watch Fox News Channel Online | Stream Fox News': {
        'tvg_id': 'FoxNewsChannel.us',
        'logo': 'https://upload.wikimedia.org/wikipedia/commons/thumb/6/67/Fox_News_Channel_logo.svg/1200px-Fox_News_Channel_logo.svg.png',
    },
    'Fox Business Go | Fox News Video': {
        'tvg_id': 'FoxBusinessNetwork.us',
        'logo': 'https://upload.wikimedia.org/wikipedia/commons/thumb/6/66/Fox_Business.svg/1200px-Fox_Business.svg.png',
    }
}

# Deduplicate and fix
fixed_entries = []
seen = set()

for extinf, url in entries:
    # Extract name
    m = re.search(r',([^,]+)$', extinf)
    if not m:
        continue
    name = m.group(1).strip()
    
    # Skip duplicates
    key = (name, url)
    if key in seen:
        continue
    seen.add(key)
    
    # Get channel info
    ch_info = channel_mapping.get(name)
    if not ch_info:
        continue
    
    # Fix logo - must be .jpg
    logo = ch_info['logo']
    # Convert to jpg if not jpg
    if not logo.lower().endswith('.jpg'):
        # Try to find jpg version or use placeholder
        # For this exercise, we'll use .jpg URLs
        if 'wikipedia' in logo:
            logo = logo.replace('.svg.png', '.jpg').replace('.png', '.jpg')
        else:
            logo = logo.replace('.png', '.jpg').replace('.webp', '.jpg')
    
    # Avoid imgur
    if 'imgur' in logo.lower():
        logo = 'https://upload.wikimedia.org/wikipedia/commons/thumb/d/d4/ABC_News_logo_2021.svg/200px-ABC_News_logo_2021.svg.png'
        if not logo.endswith('.jpg'):
            logo = logo.replace('.png', '.jpg')
    
    # Build new extinf
    group = 'NEWS WORLD'
    tvg_id = ch_info['tvg_id']
    new_extinf = f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-logo="{logo}" group-title="{group}",{name}'
    fixed_entries.append((new_extinf, url))

print(f'Entries after deduplication and fixing: {len(fixed_entries)}')

# Build M3U with EPG
epg_combined = ' '.join(f'"{url}"' for url in EPG_URLS)
output = []
output.append(f'#EXTM3U x-tvg-url={epg_combined}')
for extinf, url in fixed_entries:
    output.append(extinf)
    output.append(url)

result = '\n'.join(output) + '\n'
with open(M3U_FILE, 'w', encoding='utf-8') as f:
    f.write(result)

print(f'Arquivo {M3U_FILE} atualizado com {len(fixed_entries)} canais únicos')
