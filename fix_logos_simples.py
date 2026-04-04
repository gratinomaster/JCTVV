#!/usr/bin/env python3
import re

with open("lista5.m3u", "r") as f:
    content = f.read()

content = content.replace(".png", ".jpg")
content = content.replace(".webp", ".jpg")
content = content.replace(".svg", ".jpg")
content = content.replace(".jpeg", ".jpg")

with open("lista5.m3u", "w") as f:
    f.write(content)

print("Logos convertidos")

with open("lista5.m3u", "r") as f:
    content = f.read()

non_jpg = re.findall(r'tvg-logo="[^"]*\.(png|webp|svg)[^"]*"', content)
print(f"Logos não-.jpg: {len(non_jpg)}")
