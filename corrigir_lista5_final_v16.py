#!/usr/bin/env python3
import re
import requests

M3U_FILE = 'lista5.m3u'

LOGOS = {
    'ABC News Live': 'https://keyframe-cdn.abcnews.com/streamprovider11.jpg',
    'ABC News': 'https://keyframe-cdn.abcnews.com/streamprovider11.jpg',
    'Fox News': 'https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/ee1fa2bb-133a-4f23-8102-894bc6a8021d/957a8e3d-9f4f-4257-96fe-075b3ecba18b/1280x720/match/384/216/image.jpg',
    'Fox Business': 'https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/ee1fa2bb-133a-4f23-8102-894bc6a8021d/957a8e3d-9f4f-4257-96fe-075b3ecba18b/1280x720/match/384/216/image.jpg',
    'CBS News': 'https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg',
}

with open(M3U_FILE, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    line = line.rstrip('\n')
    
    if line.startswith('#EXTINF:'):
        name_match = re.search(r',(.+)$', line)
        channel_name = name_match.group(1).strip() if name_match else ''
        
        has_tvg_logo = 'tvg-logo=' in line
        has_tvg_id = 'tvg-id=' in line
        
        if not has_tvg_logo:
            for key, logo in LOGOS.items():
                if key.lower() in channel_name.lower():
                    line = re.sub(r'#EXTINF:-1', f'#EXTINF:-1 tvg-logo="{logo}"', line)
                    break
        
        if not has_tvg_id:
            base_name = channel_name.split('|')[0].strip()
            base_name = base_name.replace(' ', '_').replace('-', '_')
            base_name = re.sub(r'[^a-zA-Z0-9_]', '', base_name)
            line = re.sub(r'#EXTINF:-1', f'#EXTINF:-1 tvg-id="{base_name}"', line)
        
        new_lines.append(line)
    
    elif line.strip() and not line.startswith('#') and not line.startswith('#EXT'):
        if line.strip().startswith('http'):
            new_lines.append('#' + line)
        else:
            new_lines.append(line)
    else:
        new_lines.append(line)

content = '\n'.join(new_lines)
with open(M3U_FILE, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"Arquivo {M3U_FILE} corrigido!")

epg_url = "https://epg.pw/xmltv/epg_BR.xml.gz"
print(f"\nTestando EPG: {epg_url}")
try:
    resp = requests.get(epg_url, timeout=30)
    if resp.status_code == 200:
        print(f"✓ EPG funcionando ({len(resp.content)} bytes)")
except Exception as e:
    print(f"✗ Erro: {e}")

print(f"\nPrimeiras linhas do arquivo corrigido:")
with open(M3U_FILE, 'r') as f:
    for i, l in enumerate(f.readlines()[:15]):
        print(l.rstrip())