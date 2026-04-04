#!/usr/bin/env python3
import re

def convert_logo_to_jpg(url):
    if not url:
        return url
    
    url = re.sub(r'\.(png|webp|svg|jpeg)(\?.*)?$', r'.jpg\2', url, flags=re.IGNORECASE)
    
    if not url.endswith('.jpg'):
        if '.png?' in url:
            url = url.replace('.png?', '.jpg?')
        elif '.webp?' in url:
            url = url.replace('.webp?', '.jpg?')
        elif '.svg?' in url:
            url = url.replace('.svg?', '.jpg?')
        elif '.jpeg?' in url:
            url = url.replace('.jpeg?', '.jpg?')
        elif url.endswith('.png'):
            url = url[:-4] + '.jpg'
        elif url.endswith('.webp'):
            url = url[:-5] + '.jpg'
        elif url.endswith('.svg'):
            url = url[:-4] + '.jpg'
        elif url.endswith('.jpeg'):
            url = url[:-5] + '.jpg'
    
    return url

def process_lista5():
    with open("lista5.m3u", "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.split('\n')
    output_lines = []
    
    for line in lines:
        if line.startswith("#EXTINF:"):
            match = re.search(r'tvg-logo="([^"]*)"', line)
            if match:
                old_logo = match.group(1)
                new_logo = convert_logo_to_jpg(old_logo)
                line = line.replace(f'tvg-logo="{old_logo}"', f'tvg-logo="{new_logo}"')
        
        output_lines.append(line)
    
    with open("lista5.m3u", "w", encoding="utf-8") as f:
        f.write('\n'.join(output_lines))
    
    print("Arquivo processado!")

if __name__ == "__main__":
    process_lista5()
