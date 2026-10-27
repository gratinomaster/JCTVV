#!/usr/bin/env python3
import re
import gzip
from datetime import datetime

m3u_path = '/home/runner/work/JCTVV/JCTVV/CABOBRASIL.m3u'
epg_path = '/tmp/epg_br1.xml'

with open(m3u_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Load BR1 EPG
with open(epg_path, 'r', encoding='utf-8', errors='ignore') as f:
    epg_data = f.read()

epg_channels = re.findall(r'<channel id="([^"]+)"', epg_data)
epg_set = set(epg_channels)

# Map common channels
mappings = {
    'GloboSP.br': 'São.Paulo/SP..Globo.br',
    'SBTBrasil.br': None,  # look for SBT
    'Record.br': 'São.Paulo/SP..Record.br',
    'BandBrasil.br': 'São.Paulo/SP..Band.br',
    'RedeTV.br': None,
    'CNNBrasil.br': 'São.Paulo/SP..CNN.Brasil',
    'JovemPanNews.br': 'Jovem.Pan.News.br',
    'RecordNews.br': 'São.Paulo/SP.Record.News.br',
    'TVBrasil.br': 'São.Paulo/SP..TV.Brasil.br',
    'TVCamara.br': None,
    'Cultura.br': None,
    'BandNews.br': None,
    'ESPN.br': None,
    'SporTV.br': None,
}

# Try to find SBT
for ch in epg_set:
    if 'SBT' in ch and 'SP' in ch:
        mappings['SBTBrasil.br'] = ch
        break

# Apply mappings
for old, new in mappings.items():
    if new and new in epg_set:
        pattern = f'tvg-id="{re.escape(old)}"'
        if pattern in content:
            content = content.replace(pattern, f'tvg-id="{new}"')
            print(f"Mapped {old} -> {new}")
    elif old in content and new is None:
        # Try to find any match
        print(f"No direct match found for {old}, trying fuzzy...")
        # Look for partial matches
        name_part = old.replace('.br', '').replace('Brasil', '')
        for ch in epg_set:
            if name_part in ch.replace('.', ' ').replace(' ', ''):
                content = content.replace(f'tvg-id="{old}"', f'tvg-id="{ch}"')
                print(f"  Fuzzy mapped {old} -> {ch}")
                break

with open(m3u_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Done")
