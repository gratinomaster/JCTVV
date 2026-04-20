#!/usr/bin/env python3
import re

M3U_FILE = 'lista5.m3u'
EPG_URL = "https://epg.pw/xmltv/epg.xml.gz"

with open(M3U_FILE, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if line.startswith('#EXTM3U'):
        new_lines.append(f'#EXTM3U x-tvg-url="{EPG_URL}"\n')
    else:
        new_lines.append(line.rstrip('\n'))

content = '\n'.join(new_lines)
with open(M3U_FILE, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"EPGURL adicionada ao arquivo {M3U_FILE}")
print(f"EPG: {EPG_URL}")

with open(M3U_FILE, 'r') as f:
    print(f"\nPrimeira linha: {f.readline().strip()}")