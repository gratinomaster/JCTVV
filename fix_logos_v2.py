#!/usr/bin/env python3
import re

with open("lista5.m3u", "r", encoding="utf-8") as f:
    content = f.read()

content = re.sub(r'tvg-logo="[^"]*\.svg[^"]*"', 'tvg-logo="https://raw.githubusercontent.com/LITUATUI/M3UPT/main/logos/TRT_World.jpg"', content)

content = re.sub(r'tvg-logo="[^"]*\.png[^"]*"', lambda m: m.group(0).replace('.png', '.jpg'), content)
content = re.sub(r'tvg-logo="[^"]*\.webp[^"]*"', lambda m: m.group(0).replace('.webp', '.jpg'), content)
content = re.sub(r'tvg-logo="[^"]*\.jpeg[^"]*"', lambda m: m.group(0).replace('.jpeg', '.jpg'), content)
content = re.sub(r'tvg-logo="[^"]*\.svg[^"]*"', lambda m: m.group(0).replace('.svg', '.jpg'), content)

content = re.sub(r'tvg-logo="([^"]*\.)(png|webp|svg|jpeg)(\?[^"]*)?"', r'tvg-logo="\1jpg\3"', content)

with open("lista5.m3u", "w", encoding="utf-8") as f:
    f.write(content)

print("Logos convertidos para .jpg")

with open("lista5.m3u", "r", encoding="utf-8") as f:
    content = f.read()

nao_jpg = re.findall(r'tvg-logo="[^"]*\.(png|webp|svg|jpeg)[^"]*"', content)
print(f"Logos ainda não .jpg: {len(nao_jpg)}")

png_count = len(re.findall(r'\.png', content))
print(f"Total de .png: {png_count}")
