#!/usr/bin/env python3
import re
import requests
from urllib.parse import urlparse

M3U_FILE = 'lista5.m3u'
EPG_URL = "https://epg.pw/xmltv/epg_BR.xml.gz"

LOGOS_CHANNEL = {
    'ABC News': 'https://keyframe-cdn.abcnews.com/streamprovider11.jpg',
    'Fox News': 'https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/ee1fa2bb-133a-4f23-8102-894bc6a8021d/957a8e3d-9f4f-4257-96fe-075b3ecba18b/1280x720/match/384/216/image.jpg',
    'Fox Business': 'https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/ee1fa2bb-133a-4f23-8102-894bc6a8021d/957a8e3d-9f4f-4257-96fe-075b3ecba18b/1280x720/match/384/216/image.jpg',
    'CBS News': 'https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg',
}

def add_tvg_id_channel_name(extinf_line):
    name_match = re.search(r',(.+)$', extinf_line)
    if not name_match:
        return extinf_line
    
    name = name_match.group(1).strip()
    
    tvg_id_match = re.search(r'tvg-id="[^"]*"', extinf_line)
    if tvg_id_match:
        return extinf_line
    
    channel_name = name.split('|')[0].strip()
    channel_name = re.sub(r'^Watch\s+', '', channel_name, flags=re.IGNORECASE)
    channel_name = channel_name.replace(' ', '_')
    
    return extinf_line

def fix_extinf_line(line, idx):
    if not line.startswith('#EXTINF:'):
        return line
    
    has_tvg_logo = 'tvg-logo=' in line
    has_tvg_id = 'tvg-id=' in line
    
    name_match = re.search(r',(.+)$', line)
    if name_match:
        channel_name = name_match.group(1).strip().split('|')[0].strip()
    
    if not has_tvg_logo:
        for key, logo in LOGOS_CHANNEL.items():
            if key.lower() in channel_name.lower():
                line = line.replace('#EXTINF:', f'#EXTINF:-1 tvg-logo="{logo}" tvg-id="{key.replace(" ", "_")}" ')
                break
    
    if not has_tvg_id:
        if 'tvg-id=' not in line:
            clean_name = channel_name.replace(' ', '_').replace('|', '').replace('-', '_')
            line = line.replace('#EXTINF:', f'#EXTINF:-1 tvg-id="{clean_name}" ')
    
    return line

print("="*60)
print("CORRIGINDO lista5.m3u")
print("="*60)

with open(M3U_FILE, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    original = line
    
    if line.startswith('#EXTINF:'):
        name_match = re.search(r',(.+)$', line)
        if name_match:
            channel_name = name_match.group(1).strip()
            
            has_tvg_logo = 'tvg-logo=' in line
            for key, logo in LOGOS_CHANNEL.items():
                if key.lower() in channel_name.lower():
                    if not has_tvg_logo:
                        line = line.replace('#EXTINF:', f'#EXTINF:-1 tvg-logo="{logo}" ')
                    else:
                        line = re.sub(r'tvg-logo="[^"]*"', f'tvg-logo="{logo}"', line)
                    break
            
            if 'tvg-id=' not in line:
                clean = channel_name.split('|')[0].replace(' ', '_').replace('-', '_')
                line = line.replace('#EXTINF:', f'#EXTINF:-1 tvg-id="{clean}" ')
    
    elif line.strip() and not line.startswith('#') and not line.startswith('#EXT'):
        if line.strip().startswith('http'):
            line = '#' + line
    
    new_lines.append(line.rstrip('\n'))

content = '\n'.join(new_lines)
with open(M3U_FILE, 'w', encoding='utf-8') as f:
    f.write(content)

print("\n" + "="*60)
print("ARQUIVO CORRIGIDO!")
print("="*60)

if EPG_URL:
    print(f"\nEPG configurado: {EPG_URL}")
    print("Testando EPG...")
    try:
        resp = requests.get(EPG_URL, timeout=60)
        if resp.status_code == 200:
            print(f"✓ EPG acessível ({len(resp.content)} bytes)")
    except Exception as e:
        print(f"✗ Erro ao acessar EPG: {e}")

print(f"\nArquivo salvo: {M3U_FILE}")