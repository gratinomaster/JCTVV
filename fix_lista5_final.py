#!/usr/bin/env python3
"""Corrige lista5.m3u - canais de notícias dos EUA"""
import re
import requests
import time
from datetime import datetime, timedelta, timezone

CHANNELS = [
    {
        "name": "ABC News Live",
        "tvg_id": "ABCNewsLive.us@SD",
        "group": "NEWS WORLD",
        "logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
        "urls": [
            "https://linear-abcnews-ftc-na-east-1.media.dssott.com/dvt2=exp=1775400121~url=%2Fclt1%2Fva02%2Fdisneyplus%2Fchannel%2F79449312-79dd-473d-873c-515ebf4b5e5f-1773288443221%2F~psid=c00c5b15-af7a-4510-baa7-446159bb0189~did=dd318be2-cc11-4195-8556-b0591a839359~country=US~kid=k02~hmac=865fecd66c93e011d4170f79f9ef7d161776432dec202e8df2142a4f7ec43c52/clt1/va02/disneyplus/channel/79449312-79dd-473d-873c-515ebf4b5e5f-1773288443221/ctr-all-hdri-sliding.m3u8?r=1080&v=1&hash=6c5dec870ee1f02d60a0ceca893470b81b8622a3",
            "https://abcnews-livestreams.akamaized.net/out/v1/6a597119dbd5428a82dc11a2f514a1a2/abcn-live-10-cmaf-manifest/abcn-live-10-index.m3u8",
        ]
    },
    {
        "name": "ABC News Live - Beirut",
        "tvg_id": "ABCNewsLiveBeirut.us@SD",
        "group": "NEWS WORLD",
        "logo": "https://keyframe-cdn.abcnews.com/streamprovider5.jpg",
        "urls": [
            "https://abcnews-livestreams.akamaized.net/out/v1/173a6e46d5c5423d9611bc7fb7899c73/abcn-live-05-cmaf-manifest/abcn-live-05-index.m3u8",
        ]
    },
    {
        "name": "Fox News Channel",
        "tvg_id": "FoxNewsChannel.us@SD",
        "group": "NEWS WORLD",
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/15de0523-3be4-4a9a-8159-7020114e7036/b6ff623a-26d6-4fd9-8bb8-0856adbf38ce/1280x720/match/676/380/image.jpg?ve=1&tl=1",
        "urls": [
            "https://tvpass.org/live/FoxNewsChannel/hd",
        ]
    },
    {
        "name": "Fox Business Network",
        "tvg_id": "FoxBusinessNetwork.us@SD",
        "group": "NEWS WORLD",
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/c9b2e2eb-7b87-435c-9510-eab2650ff944/8b584585-acf2-4c37-aa07-aaf2d077bb20/1280x720/match/676/380/image.jpg?ve=1&tl=1",
        "urls": [
            "https://tvpass.org/live/FoxBusiness/hd",
        ]
    },
    {
        "name": "CBS News 24/7",
        "tvg_id": "CBSNews247.us@SD",
        "group": "NEWS WORLD",
        "logo": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
        "urls": [
            "https://jmp2.uk/plu-6350fdd266e9ea0007bedec5.m3u8",
        ]
    },
]

def test_url(url, timeout=10):
    try:
        resp = requests.get(url, timeout=timeout, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        })
        if resp.status_code == 200:
            ct = resp.headers.get('Content-Type', '')
            text = resp.text[:1000] if resp.text else ''
            is_hls = '#EXTM3U' in text or 'm3u8' in text
            return is_hls, resp.status_code
    except:
        pass
    return False, None

def generate_m3u():
    lines = ['#EXTM3U', '']
    
    for ch in CHANNELS:
        for url in ch['urls']:
            is_hls, status = test_url(url)
            if is_hls:
                line = f'#EXTINF:-1 tvg-id="{ch["tvg_id"]}" tvg-logo="{ch["logo"]}" group-title="{ch["group"]}",{ch["name"]}'
                lines.append(line)
                lines.append(url)
                break
        else:
            print(f"  [WARN] No working URL for {ch['name']}")
    
    return '\n'.join(lines)

def generate_epg():
    now = datetime.now(timezone.utc)
    
    programmes = {
        "ABCNewsLive.us@SD": [
            (6, 30, "ABC World News This Morning", "Morning news coverage"),
            (7, 30, "ABC World News This Morning", "Morning news coverage"),
            (8, 30, "ABC World News This Morning", "Morning news coverage"),
            (9, 30, "ABC Live - News Update", "Live news update"),
            (10, 30, "ABC Live - News Update", "Live news update"),
            (11, 30, "ABC World News Midday", "Midday news program"),
            (12, 30, "ABC World News Midday", "Midday news program"),
            (13, 30, "ABC Live - Afternoon Update", "Afternoon news coverage"),
            (14, 30, "ABC Live - Afternoon Update", "Afternoon news coverage"),
            (15, 30, "ABC Live - News Hour", "Hourly news coverage"),
            (16, 30, "ABC Live - News Hour", "Hourly news coverage"),
            (17, 30, "ABC World News Tonight", "Evening news program"),
            (18, 30, "ABC World News Tonight", "Evening news program"),
            (19, 30, "ABC Live - Evening Update", "Evening news coverage"),
            (20, 30, "ABC Live - Prime Time", "Prime time news coverage"),
            (21, 30, "ABC Nightline", "Late night news program"),
            (22, 30, "ABC Nightline", "Late night news program"),
            (23, 30, "ABC World News Now", "Overnight news coverage"),
            (0, 30, "ABC World News Now", "Overnight news coverage"),
            (1, 30, "ABC World News Now", "Overnight news coverage"),
            (2, 30, "ABC World News Now", "Overnight news coverage"),
            (3, 30, "ABC World News Now", "Overnight news coverage"),
            (4, 30, "ABC World News Now", "Overnight news coverage"),
            (5, 30, "ABC World News This Morning", "Early morning news"),
        ],
        "ABCNewsLiveBeirut.us@SD": [
            (0, 0, "Middle East News Update", "Live news from Beirut and the region"),
            (3, 0, "Middle East News Update", "Live news from Beirut and the region"),
            (6, 0, "Middle East Morning Report", "Morning news coverage"),
            (9, 0, "Beirut Live", "Live news feed"),
            (12, 0, "Middle East News Update", "Midday update"),
            (15, 0, "Beirut Live", "Live news feed"),
            (18, 0, "Middle East Evening Report", "Evening news program"),
            (21, 0, "Beirut Live", "Live news feed"),
        ],
        "FoxNewsChannel.us@SD": [
            (6, 0, "Fox & Friends", "Morning news show"),
            (7, 0, "Fox & Friends", "Morning news show"),
            (8, 0, "Fox & Friends", "Morning news show"),
            (9, 0, "America's Newsroom", "Morning news program"),
            (10, 0, "America's Newsroom", "Morning news program"),
            (11, 0, "Fox News Midday", "Midday news"),
            (12, 0, "Fox News @ Lunchtime", "Lunchtime news"),
            (13, 0, "Outnumbered", "Afternoon news show"),
            (14, 0, "One Nation", "Political news program"),
            (15, 0, "The Story", "News analysis program"),
            (16, 0, "Your World", "Evening news program"),
            (17, 0, "The Five", "Panel news show"),
            (18, 0, "Fox Report", "Evening news program"),
            (19, 0, "Special Report with Bret Baier", "Prime time news"),
            (20, 0, "The Story", "News analysis program"),
            (21, 0, "Hannity", "Political commentary show"),
            (22, 0, "The Ingraham Angle", "Late night news program"),
            (23, 0, "Fox News Night", "Late night news"),
            (0, 0, "Fox News Night", "Late night news"),
            (1, 0, "Fox News Primetime", "Prime time news coverage"),
            (2, 0, "Fox News Overnight", "Overnight news coverage"),
            (3, 0, "Fox News Overnight", "Overnight news coverage"),
            (4, 0, "Fox & Friends First", "Early morning news"),
            (5, 0, "Fox & Friends", "Morning news show"),
        ],
        "FoxBusinessNetwork.us@SD": [
            (5, 0, "Fox Business Morning", "Early morning business news"),
            (6, 0, "Mornings with Maria", "Business morning show"),
            (7, 0, "Mornings with Maria", "Business morning show"),
            (8, 0, "Mornings with Maria", "Business morning show"),
            (9, 0, "Varney & Co.", "Morning business program"),
            (10, 0, "The Liz Hunt Show", "Business program"),
            (11, 0, "Fox Business Midday", "Midday business news"),
            (12, 0, "Countdown to the Close", "Market coverage"),
            (13, 0, "The Claman Countdown", "Market closing program"),
            (14, 0, "Making Money", "Financial news program"),
            (15, 0, "The Claman Countdown", "Market closing program"),
            (16, 0, "Fox Business Evening", "Evening business news"),
            (17, 0, "The Claman Countdown", "Market closing program"),
            (18, 0, "Fox Business Tonight", "Evening business news"),
            (19, 0, "Kennedy", "Evening business show"),
            (20, 0, "Making Money", "Financial news program"),
            (21, 0, "Fox Business Late", "Late night business coverage"),
            (22, 0, "Fox Business After Hours", "After hours coverage"),
            (23, 0, "Fox Business Overnight", "Overnight business coverage"),
            (0, 0, "Fox Business Overnight", "Overnight business coverage"),
            (1, 0, "Fox Business Overnight", "Overnight business coverage"),
            (2, 0, "Fox Business Overnight", "Overnight business coverage"),
            (3, 0, "Fox Business Morning", "Early morning business news"),
            (4, 0, "Fox Business Morning", "Early morning business news"),
        ],
        "CBSNews247.us@SD": [
            (0, 0, "CBS News 24/7", "24-hour news coverage"),
            (1, 0, "CBS News 24/7", "24-hour news coverage"),
            (2, 0, "CBS News 24/7", "24-hour news coverage"),
            (3, 0, "CBS News 24/7", "24-hour news coverage"),
            (4, 0, "CBS News 24/7", "24-hour news coverage"),
            (5, 0, "CBS News 24/7", "24-hour news coverage"),
            (6, 0, "CBS Mornings", "Morning news program"),
            (7, 0, "CBS Mornings", "Morning news program"),
            (8, 0, "CBS Mornings", "Morning news program"),
            (9, 0, "CBS News 24/7", "24-hour news coverage"),
            (10, 0, "CBS News 24/7", "24-hour news coverage"),
            (11, 0, "CBS News 24/7", "24-hour news coverage"),
            (12, 0, "CBS News 24/7", "24-hour news coverage"),
            (13, 0, "CBS News 24/7", "24-hour news coverage"),
            (14, 0, "CBS News 24/7", "24-hour news coverage"),
            (15, 0, "CBS News 24/7", "24-hour news coverage"),
            (16, 0, "CBS News 24/7", "24-hour news coverage"),
            (17, 0, "CBS Evening News", "Evening news program"),
            (18, 0, "CBS Evening News", "Evening news program"),
            (19, 0, "CBS News 24/7", "24-hour news coverage"),
            (20, 0, "CBS News 24/7", "24-hour news coverage"),
            (21, 0, "CBS News 24/7", "24-hour news coverage"),
            (22, 0, "CBS News 24/7", "24-hour news coverage"),
            (23, 0, "CBS News 24/7", "24-hour news coverage"),
        ],
    }
    
    def escape_xml(s):
        return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
    
    xml_lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<tv>']
    
    for ch in CHANNELS:
        xml_lines.append(f'  <channel id="{escape_xml(ch["tvg_id"])}">')
        xml_lines.append(f'    <display-name>{escape_xml(ch["name"])}</display-name>')
        xml_lines.append(f'    <icon src="{escape_xml(ch["logo"])}"/>')
        xml_lines.append('  </channel>')
    
    xml_lines.append('')
    
    for ch in CHANNELS:
        tvg_id = ch["tvg_id"]
        slots = programmes.get(tvg_id, [(0, 0, "News", "Live news coverage")])
        
        for day_offset in range(3):
            base_date = now + timedelta(days=day_offset)
            
            for hour, minute, title, desc in slots:
                start = base_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
                duration_minutes = 60
                
                start_str = start.strftime('%Y%m%d%H%M%S')
                stop = start + timedelta(minutes=duration_minutes)
                stop_str = stop.strftime('%Y%m%d%H%M%S')
                
                xml_lines.append(f'  <programme channel="{escape_xml(tvg_id)}" start="{start_str} +0000" stop="{stop_str} +0000">')
                xml_lines.append(f'    <title lang="en">{escape_xml(title)}</title>')
                xml_lines.append(f'    <desc lang="en">{escape_xml(desc)}</desc>')
                xml_lines.append('  </programme>')
    
    xml_lines.append('</tv>')
    return '\n'.join(xml_lines)

if __name__ == '__main__':
    print("Testing URLs...")
    for ch in CHANNELS:
        for url in ch['urls']:
            is_hls, status = test_url(url)
            status_str = f"{status}" if status else "ERROR"
            print(f"  {ch['name']}: {url[:60]}... -> HLS={is_hls} ({status_str})")
    
    print("\nGenerating M3U...")
    m3u_content = generate_m3u()
    with open('/home/runner/work/JCTV/JCTV/lista5.m3u', 'w') as f:
        f.write(m3u_content)
    print("  lista5.m3u written")
    
    print("\nGenerating EPG...")
    epg_content = generate_epg()
    with open('/home/runner/work/JCTV/JCTV/lista5_epg.xml', 'w') as f:
        f.write(epg_content)
    print("  lista5_epg.xml written")
    
    print("\nDone!")
