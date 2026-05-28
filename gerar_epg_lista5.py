#!/usr/bin/env python3
from datetime import datetime, timedelta
import gzip
import requests
import io
import xml.etree.ElementTree as ET
import re

CHANNEL_MAPPING = {
    "ABCNewsLive.us": {
        "display": "ABC News Live",
        "names": ["ABC News Live", "ABCNewsLive.us"],
        "logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg"
    },
    "FoxNewsChannel.us": {
        "display": "Fox News Channel",
        "names": ["Fox News", "FoxNews", "FoxNewsChannel.us"],
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/5083aae4-b8c5-4708-ac25-f3c5ac554341/b17e991e-a824-4bf7-8e6b-885b7cd2bcf4/1280x720/match/400/225/image.jpg"
    },
    "FoxBusiness.us": {
        "display": "Fox Business",
        "names": ["Fox Business", "FoxBusiness", "FoxBusinessNetwork.us"],
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/5083aae4-b8c5-4708-ac25-f3c5ac554341/b17e991e-a824-4bf7-8e6b-885b7cd2bcf4/1280x720/match/400/225/image.jpg"
    },
    "CBSNews.us": {
        "display": "CBS News 24/7",
        "names": ["CBS News", "CBSNews", "CBSNewsNetwork.us"],
        "logo": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg"
    }
}

def get_affiliate_programmes(epg_content, channel_name, days=3):
    from datetime import datetime, timedelta
    today = datetime.now()
    programmes = []

    affiliate_ids = {
        "ABC News Live": ["WABC-DT.us_locals1", "KABC-DT.us_locals1"],
        "Fox News Channel": ["WFOX-DT.us_locals1", "KFOX-DT.us_locals1"],
        "Fox Business": ["WFOX-DT.us_locals1", "KFOX-DT.us_locals1"],
        "CBS News 24/7": ["WCBS-DT.us_locals1", "KCBS-DT.us_locals1"]
    }

    ids = affiliate_ids.get(channel_name, [])

    for affiliate_id in ids:
        if affiliate_id in epg_content:
            print(f"  Encontrado affiliate: {affiliate_id}")
            return get_programmes_from_affiliate(epg_content, affiliate_id, days)

    return generate_generic_programmes(channel_name, days)

def get_programmes_from_affiliate(epg_content, affiliate_id, days):
    from datetime import datetime, timedelta
    import re

    today = datetime.now()
    tomorrow = today + timedelta(days=1)
    day_after = today + timedelta(days=2)

    programmes = []
    pattern = rf'<programme[^>]+channel="{re.escape(affiliate_id)}"[^>]+start="(\d{14})\s*\+\d{4}"[^>]+stop="(\d{14})\s*\+\d{4}"[^>]*>.*?</programme>'

    matches = re.findall(pattern, epg_content, re.DOTALL)

    for start, stop in matches[:days * 6]:
        try:
            prog_date = datetime.strptime(start[:8], '%Y%m%d')
            if prog_date.date() <= day_after.date():
                programmes.append({
                    'start': start,
                    'stop': stop,
                    'start_dt': prog_date
                })
        except:
            continue

    return programmes[:days * 6]

def generate_generic_programmes(channel_name, days):
    from datetime import datetime, timedelta

    today = datetime.now()
    programmes = []

    shows = {
        "ABC News Live": ["Good Morning America", "World News This Morning", "ABC World News", "GMA3: What You Need To Know", "World News Tonight", "Nightline"],
        "Fox News Channel": ["Fox & Friends First", "America's Newsroom", "Happening Now", "The Story", "Fox News @ Night", "Tucker Carlson Tonight"],
        "Fox Business": ["Mornings with Maria", "Squawk Box", "Making Money", "The Claman Countdown", "Evening Edit", "Nightly Business Report"],
        "CBS News": ["CBS Mornings", "CBS News Mornings", "CBS Midday News", "CBS Afternoon News", "CBS Evening News", "CBS Night News"]
    }

    channel_shows = shows.get(channel_name, shows["ABC News Live"])

    for day_offset in range(days):
        current_day = today + timedelta(days=day_offset)
        day_str = current_day.strftime('%Y%m%d')

        times = ["060000", "090000", "120000", "130000", "180000", "220000"]
        next_times = ["090000", "120000", "130000", "180000", "220000", "060000"]

        for i, (start_t, show) in enumerate(zip(times, channel_shows)):
            end_t = next_times[i]

            if i == 5:
                next_day = current_day + timedelta(days=1)
                end_str = next_day.strftime('%Y%m%d') + "060000"
            else:
                end_str = day_str + end_t

            start_str = day_str + start_t

            programmes.append({
                'start': start_str,
                'stop': end_str
            })

    return programmes

def create_custom_epg():
    from datetime import datetime

    print("=" * 70)
    print("Criando EPG customizado para lista5.m3u")
    print("=" * 70)

    today = datetime.now()
    tomorrow = today + timedelta(days=1)
    day_after = today + timedelta(days=2)

    print(f"\nProgramação para:")
    print(f"  Hoje: {today.strftime('%Y-%m-%d')}")
    print(f"  Amanhã: {tomorrow.strftime('%Y-%m-%d')}")
    print(f"  Depois de amanhã: {day_after.strftime('%Y-%m-%d')}")

    xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<tv date="{today.strftime('%Y%m%d%H%M%S')}">
'''

    for ch_id, ch_info in CHANNEL_MAPPING.items():
        ch_id_esc = escape_xml(ch_id)
        display_esc = escape_xml(ch_info['display'])
        xml += f'''  <channel id="{ch_id_esc}">
    <display-name lang="en">{display_esc}</display-name>
    <icon src="{ch_info['logo']}" />
  </channel>
'''

    for ch_id, ch_info in CHANNEL_MAPPING.items():
        display_name = ch_info['display']
        print(f"\nProcessando: {display_name} ({ch_id})")
        programmes = generate_generic_programmes(display_name, 3)
        ch_id_esc = escape_xml(ch_id)

        for prog in programmes:
            start = prog['start'][:8] + 'T' + prog['start'][8:] + '00 +0000'
            stop = prog['stop'][:8] + 'T' + prog['stop'][8:] + '00 +0000'

            show_name = get_show_for_time(display_name, prog['start'])
            xml += f'''  <programme channel="{ch_id_esc}" start="{start}" stop="{stop}">
    <title lang="en">{show_name}</title>
    <desc lang="en">Live news coverage from {ch_info['display']}</desc>
  </programme>
'''

    xml += '</tv>\n'

    with open('lista5_epg.xml', 'w', encoding='utf-8') as f:
        f.write(xml)

    print(f"\nEPG salvo: lista5_epg.xml ({len(xml)} bytes)")

def escape_xml(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;').replace("'", '&apos;')

def get_show_for_time(channel, timestamp):
    hour = int(timestamp[8:10])

    shows = {
        "ABC News Live": {
            (6, 9): "Good Morning America",
            (9, 12): "World News This Morning",
            (12, 13): "ABC World News Midday",
            (13, 18): "GMA3: What You Need To Know",
            (18, 20): "World News Tonight",
            (20, 23): "Nightline",
            (23, 6): "Overnight News"
        },
        "Fox News Channel": {
            (6, 9): "Fox &amp; Friends First",
            (9, 12): "America's Newsroom",
            (12, 15): "Happening Now",
            (15, 17): "The Story",
            (17, 20): "Fox News @ Night",
            (20, 23): "Tucker Carlson Tonight",
            (23, 6): "Fox News Overnight"
        },
        "Fox Business": {
            (6, 9): "Mornings with Maria",
            (9, 12): "Squawk Box",
            (12, 15): "Making Money",
            (15, 18): "The Claman Countdown",
            (18, 20): "Evening Edit",
            (20, 23): "Nightly Business Report",
            (23, 6): "Markets After Hours"
        },
        "CBS News": {
            (6, 9): "CBS Mornings",
            (9, 12): "CBS News Mornings",
            (12, 13): "CBS Midday News",
            (13, 18): "CBS Afternoon News",
            (18, 19): "CBS Evening News",
            (19, 22): "CBS Prime News",
            (22, 23): "CBS Night News",
            (23, 6): "CBS Overnight"
        }
    }

    channel_shows = shows.get(channel, shows["ABC News Live"])

    for (start_h, end_h), show_name in channel_shows.items():
        if start_h <= hour < end_h:
            return show_name

    return "News Coverage"

if __name__ == "__main__":
    create_custom_epg()