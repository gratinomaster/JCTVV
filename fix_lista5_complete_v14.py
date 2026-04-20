#!/usr/bin/env python3
import re
import json

with open('lista5.m3u', 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')
new_lines = []

LOGOS_VALIDOS = {
    'ABC News': 'https://keyframe-cdn.abcnews.com/streamprovider11.jpg',
    'Fox News': 'https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/ee1fa2bb-133a-4f23-8102-894bc6a8021d/957a8e3d-9f4f-4257-96fe-075b3ecba18b/1280x720/match/384/216/image.jpg',
    'CBS News': 'https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg',
}

IGNORED_LOGO_DOMAINS = ['imgur.com']

for i, line in enumerate(lines):
    if line.startswith('#EXTINF:'):
        original_line = line
        
        tvg_logo_match = re.search(r'tvg-logo="([^"]+)"', line)
        if tvg_logo_match:
            current_logo = tvg_logo_match.group(1)
            needs_fix = False
            
            for domain in IGNORED_LOGO_DOMAINS:
                if domain in current_logo.lower():
                    needs_fix = True
                    break
            
            if needs_fix:
                name_match = re.search(r',(.+)$', line)
                if name_match:
                    name = name_match.group(1).strip()
                    for key, logo in LOGOS_VALIDOS.items():
                        if key.lower() in name.lower():
                            line = line.replace(tvg_logo_match.group(0), f'tvg-logo="{logo}"')
                            break
        
        new_lines.append(line)
    elif line.strip() and not line.startswith('#'):
        if not line.startswith('http'):
            new_lines.append('#' + line)
        else:
            new_lines.append(line)
    else:
        new_lines.append(line)

with open('lista5.m3u', 'w', encoding='utf-8') as f:
    f.write('\n'.join(new_lines))

print("Arquivo lista5.m3u corrigido!")