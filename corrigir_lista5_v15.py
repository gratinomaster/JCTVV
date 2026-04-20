#!/usr/bin/env python3
import re

M3U_FILE = 'lista5.m3u'

LOGOS = {
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
        
        extinf_attrs = '#EXTINF:-1'
        
        for key, logo in LOGOS.items():
            if key.lower() in channel_name.lower():
                extinf_attrs += f' tvg-logo="{logo}"'
                break
        
        if 'tvg-id=' not in line:
            clean_name = channel_name.split('|')[0].replace(' ', '_').replace('-', '_').replace('/', '_').replace('24/7', '24_7')
            clean_name = re.sub(r'[^a-zA-Z0-9_]', '', clean_name)
            extinf_attrs += f' tvg-id="{clean_name}"'
        
        if 'group-title=' in line:
            group_match = re.search(r'group-title="([^"]+)"', line)
            if group_match:
                extinf_attrs += f' group-title="{group_match.group(1)}"'
        
        extinf_attrs += ',' + channel_name
        new_lines.append(extinf_attrs)
    
    elif line.startswith('#'):
        new_lines.append(line)
    elif line.strip():
        new_lines.append('#' + line)
    else:
        new_lines.append(line)

content = '\n'.join(new_lines)
with open(M3U_FILE, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"Arquivo {M3U_FILE} corrigido!")

with open(M3U_FILE, 'r') as f:
    content = f.read()
    print(f"\nPrimeiras linhas:")
    for l in content.split('\n')[:20]:
        print(l)