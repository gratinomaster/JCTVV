#!/usr/bin/env python3
"""
Final script to properly format lista5.m3u with correct EPG, logos, and structure.
"""
import requests
import gzip
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import re

EPG_URL = "https://iptv-epg.org/files/epg-us.xml.gz"

CHANNEL_EPG_MAP = {
    "ABC News Live": {"tvg_id": "ABCWBMA.us"},
    "Fox Business Go": {"tvg_id": "FoxBusiness.us"},
    "Fox News": {"tvg_id": "FoxNewsChannel.us"},
    "CBS News": {"tvg_id": "CBSNews.us"},
    "our free live news stream": {"tvg_id": "CBSNews.us"},
}

LOGO_MAP = {
    "ABCWBMA.us": "https://pbs.twimg.com/profile_images/506771501949218816/x3cY4Z0S_normal.jpeg",
    "FoxNewsChannel.us": "https://pbs.twimg.com/profile_images/871939640722137088/_pMxMJOd_normal.jpg",
    "FoxBusiness.us": "https://pbs.twimg.com/profile_images/871939640722137088/_pMxMJOd_normal.jpg",
    "CBSNews.us": "https://pbs.twimg.com/profile_images/1456632014592237569/wzq8cNds_normal.jpg",
}

def download_epg(url):
    try:
        response = requests.get(url, timeout=60, headers={'Accept-Encoding': 'gzip'})
        if response.status_code == 200:
            return gzip.decompress(response.content) if url.endswith('.gz') else response.content
    except Exception as e:
        print(f"Error: {e}")
    return None

def identify_channel(name):
    for key, info in CHANNEL_EPG_MAP.items():
        if key.lower() in name.lower():
            return info
    return None

def get_logo(tvg_id):
    return LOGO_MAP.get(tvg_id, "")

def check_programming(epg_content, tvg_id, days_ahead=0):
    if not epg_content:
        return False, []
    try:
        root = ET.fromstring(epg_content)
        target_date = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y%m%d")
        channel_elems = root.findall(f".//channel[@id='{tvg_id}']")
        if not channel_elems:
            return False, []
        channel_id = channel_elems[0].get('id')
        programmes = root.findall(f".//programme[@channel='{channel_id}']")
        found = []
        for prog in programmes:
            if prog.get('start', '').startswith(target_date):
                title = prog.find('title')
                if title is not None:
                    found.append(title.text)
        return len(found) > 0, found[:5]
    except:
        return False, []

def test_url(url):
    try:
        response = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'}, stream=True)
        return response.status_code < 400
    except:
        return False

print("=== Downloading EPG ===\n")
epg_content = download_epg(EPG_URL)
if epg_content:
    print(f"✓ EPG downloaded ({len(epg_content)} bytes)\n")

print("=== Testing EPG Programming ===\n")

channels_data = [
    ("ABC News Live - ABC News", "ABCWBMA.us"),
    ("Fox Business Go | Fox News Video", "FoxBusiness.us"),
    ("Watch Fox News Channel Online | Stream Fox News", "FoxNewsChannel.us"),
    ("our free live news stream", "CBSNews.us"),
]

channel_urls = [
    "https://linear-abcnews-akc-na-east-1.media.dssott.com/dvt2=exp=1776613622~url=%2Fclt1%2Fva02%2Fdisneyplus%2Fchannel%2F79449312-79dd-473d-873c-515ebf4b5e5f-1776498800636%2F~psid=6f528a16-5c63-4f1e-a46b-afab250508ff~did=6bd5928c-5aae-460a-a7d0-332e95a3d060~country=US~kid=k02~hmac=0d7fd07a3cd23c7a36126ca4e7a12b8152f1d7ecfad1b4bd3eeea6a7b12e28b4/clt1/va02/disneyplus/channel/79449312-79dd-473d-873c-515ebf4b5e5f-1776498800636/ctr-all-hdri-sliding.m3u8?r=1080&v=1&hash=71f3e26f3e0f7896c16e16a8a321ba96b894c95c",
    "https://247.foxbusiness.com/hls/live/2003756/FBNHLSv3/master.m3u8?hdnea=exp=1776530820~acl=/*~hmac=1a932c3ac51cfc1bc340d895f27000327189edee72a0f1b7d8c89b5aa14c0e20",
    "https://247.foxnews.com/hls/live/2003586/FNCHLSv3/master.m3u8?hdnea=exp=1776530820~acl=/*~hmac=1a932c3ac51cfc1bc340d895f27000327189edee72a0f1b7d8c89b5aa14c0e20",
    "https://dai.google.com/linear/hls/pa/event/Sid4xiTQTkCT1SLu6rjUSQ/stream/c9f52ff4-4025-4bf0-84de-e63ebdd4f20e:CHS/master.m3u8",
]

for i, (name, tvg_id) in enumerate(channels_data):
    logo = get_logo(tvg_id)
    url = channel_urls[i]
    
    today_ok, today_progs = check_programming(epg_content, tvg_id, 0) if epg_content else (False, [])
    tomorrow_ok, tomorrow_progs = check_programming(epg_content, tvg_id, 1) if epg_content else (False, [])
    day_after_ok, day_after_progs = check_programming(epg_content, tvg_id, 2) if epg_content else (False, [])
    
    url_ok = test_url(url)
    
    print(f"Channel: {name}")
    print(f"  tvg-id: {tvg_id}")
    print(f"  Logo: {logo}")
    print(f"  Today: {'✓' if today_ok else '✗'} | Tomorrow: {'✓' if tomorrow_ok else '✗'} | Day after: {'✓' if day_after_ok else '✗'}")
    print(f"  URL OK: {'✓' if url_ok else '✗'}")
    print()

output_lines = [f"#EXTM3U url-tvg=\"{EPG_URL}\""]

for i, (name, tvg_id) in enumerate(channels_data):
    logo = get_logo(tvg_id)
    url = channel_urls[i]
    
    extinf = f'#EXTINF:-1 tvg-logo="{logo}" group-title="NEWS WORLD" tvg-id="{tvg_id}",{name}'
    output_lines.append(extinf)
    output_lines.append(url)

with open('lista5_corrigida.m3u', 'w') as f:
    f.write('\n'.join(output_lines))

print("=== File Created ===")
print("✓ lista5_corrigida.m3u saved")