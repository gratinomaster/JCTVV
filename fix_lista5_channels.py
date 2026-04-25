#!/usr/bin/env python3
import re

def process_lista5():
    with open('lista5.m3u', 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    output_lines = []
    i = 0
    
    while i < len(lines):
        line = lines[i].rstrip('\n\r')
        
        if line.startswith('#EXTM3U'):
            output_lines.append(line)
            i += 1
            continue
        
        if line.startswith('#EXTINF:'):
            extinf = line
            
            if 'Fox Business' in extinf or 'FoxBusiness' in extinf or 'foxbusiness' in extinf.lower():
                extinf = re.sub(r'tvg-id="[^"]*"', 'tvg-id="FoxBusinessNetwork.us"', extinf)
                extinf = re.sub(r'tvg-logo="[^"]*"', 'tvg-logo="https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/c9b2e2eb-7b87-435c-9510-eab2650ff944/8b584585-acf2-4c37-aa07-aaf2d077bb20/1280x720/match/676/380/image.jpg"', extinf)
                if 'Fox Business' not in extinf.split(',')[-1]:
                    parts = extinf.rsplit(',', 1)
                    extinf = parts[0] + ',Fox Business'
            
            if 'CBS News' in extinf or 'cbsnews' in extinf.lower() or 'CBSNews' in extinf:
                extinf = re.sub(r'tvg-id="[^"]*"', 'tvg-id="CBSNews.us"', extinf)
                extinf = re.sub(r'tvg-logo="[^"]*"', 'tvg-logo="https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg"', extinf)
                if 'CBS News' not in extinf.split(',')[-1]:
                    parts = extinf.rsplit(',', 1)
                    extinf = parts[0] + ',CBS News'
            
            if 'Fox News' in extinf and 'Business' not in extinf:
                extinf = re.sub(r'tvg-id="[^"]*"', 'tvg-id="FoxNewsChannel.us"', extinf)
                extinf = re.sub(r'tvg-logo="[^"]*"', 'tvg-logo="https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/3b09e0ef-610a-43d4-960b-78dc97ae2bd2/dc2e6082-3de1-40e8-a3ab-b6a61b18c3b1/1280x720/match/400/225/image.jpg"', extinf)
                if 'Fox News' not in extinf.split(',')[-1]:
                    parts = extinf.rsplit(',', 1)
                    extinf = parts[0] + ',Fox News'
            
            if 'ABC News' in extinf or 'ABC News Live' in extinf:
                extinf = re.sub(r'tvg-id="[^"]*"', 'tvg-id="ABCNews.us"', extinf)
                extinf = re.sub(r'tvg-logo="[^"]*"', 'tvg-logo="https://keyframe-cdn.abcnews.com/streamprovider11.jpg"', extinf)
                if 'ABC News Live' not in extinf.split(',')[-1]:
                    parts = extinf.rsplit(',', 1)
                    extinf = parts[0] + ',ABC News Live'
            
            output_lines.append(extinf)
            
        elif line and line.startswith('http'):
            output_lines.append(line)
        
        i += 1
    
    with open('lista5.m3u', 'w', encoding='utf-8') as f:
        f.write('\n'.join(output_lines) + '\n')
    
    print("lista5.m3u corrigido!")

if __name__ == "__main__":
    process_lista5()