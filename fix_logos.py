#!/usr/bin/env python3
import re

LOGOS = {
    "abcnews.com": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/united-states/abcnewslive-us.png",
    "keyframe-cdn.abcnews.com": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/united-states/abcnewslive-us.png",
    "www.cbsnews.com": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/united-states/cbsnewsnetwork-us.png",
    "a57.foxnews.com": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/united-states/foxnewschannel-us.png",
    "assets.bloomberg.tv": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/united-states/bloombergtv-us.png",
    "cfvod.kaltura.com": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/united-states/newsmax-us.png",
    "upload.wikimedia.org": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/united-kingdom/bbc-news-uk.png",
}

def fix_logos(content):
    for old_domain, new_logo in LOGOS.items():
        if old_domain in content and ".jpg" not in content.lower():
            content = content.replace(old_domain, new_logo)
    return content

with open('lista5.m3u', 'r') as f:
    content = f.read()

fixed = fix_logos(content)

with open('lista5.m3u', 'w') as f:
    f.write(fixed)

print("Logos corrigidos para .png (mais compatível)")