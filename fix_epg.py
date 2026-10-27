#!/usr/bin/env python3
import re
import gzip
import shutil
from datetime import datetime
import requests
from urllib.parse import urlparse

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

m3u_path = '/home/runner/work/JCTVV/JCTVV/CABOBRASIL.m3u'
epg_path = '/home/runner/work/JCTVV/JCTVV/EPGFULL.xml.gz'

# Load current m3u
with open(m3u_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Load EPG
with gzip.open(epg_path, 'rt', encoding='utf-8', errors='ignore') as f:
    epg_data = f.read()

epg_channels = set(re.findall(r'<channel id="([^"]+)"', epg_data))
print(f"EPG has {len(epg_channels)} channels")

# Check each channel in m3u
lines = content.split('\n')
new_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    if line.strip().startswith('#EXTINF'):
        # Check tvg-id
        m = re.search(r'tvg-id="([^"]+)"', line)
        if m:
            tvg_id = m.group(1)
            # Check if it exists in EPG
            if tvg_id not in epg_channels or not re.search(f'channel="{re.escape(tvg_id)}"[^>]*start="{datetime.now().strftime("%Y%m%d")}', epg_data):
                print(f"Channel {tvg_id} needs EPG fix - not found or no programming today")
                # Try to find a better matching tvg-id or add a working one
                # For Brazilian channels, common mappings
                replacements = {
                    'RedeBrasil.br': 'RedeBrasil.br',  # might not exist
                    'RITtv.br': 'RITtv.br',
                    'TVACritica.br': 'TVACritica.br',
                    'Record.br': 'RecordTV.br',  # try alternative
                }
                # Look for similar
                if tvg_id == 'Record.br' and 'RecordTV.br' in epg_channels:
                    line = line.replace('tvg-id="Record.br"', 'tvg-id="RecordTV.br"')
                    print(f"  Replaced with RecordTV.br")
                elif tvg_id not in epg_channels:
                    # Try without .br or different formats
                    alt = tvg_id.replace('.br', '.BR').replace('Brasil', 'BR')
                    if alt in epg_channels:
                        line = line.replace(f'tvg-id="{tvg_id}"', f'tvg-id="{alt}"')
                        print(f"  Replaced with {alt}")
                    else:
                        # For Brazilian open TV, maybe use a common EPG or remove/fix
                        # Try to find any matching channel name
                        pass
        new_lines.append(line)
        i += 1
        continue
    new_lines.append(line)
    i += 1

content_new = '\n'.join(new_lines)
with open(m3u_path, 'w', encoding='utf-8') as f:
    f.write(content_new)

print("EPG fixes applied")
