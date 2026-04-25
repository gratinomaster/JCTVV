#!/usr/bin/env python3
import gzip
import requests
import io
import re
from datetime import datetime, timedelta
import hashlib
import urllib.parse
import xml.etree.ElementTree as ET

EPG_SOURCES = [
    "https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS2.xml.gz",
]

CHANNEL_MAPPING = {
    "ABCNewsLive.us@NewsWorld": {
        "names": ["ABC News Live - ABC News", "ABC News Live", "ABC News"],
        "tvg_id": "ABCNews.us",
        "epg_ids": ["WABC-DT.us_locals1", "KABC-DT.us_locals1", "ABCNews.us"],
        "logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg"
    },
    "ABCNL.us@NewsWorld": {
        "names": ["ABC News Prime", "ABCNL Prime", "ABCNL", "ABC News Live - Watch Live News on ABCNL", "ABCNL"],
        "tvg_id": "ABCNews.us",
        "epg_ids": ["WABC-DT.us_locals1", "KABC-DT.us_locals1", "ABCNews.us"],
        "logo": "https://keyframe-cdn.abcnews.com/streamprovider10.jpg"
    },
    "FoxNews.us@NewsWorld": {
        "names": ["Watch Fox News Channel Online | Stream Fox News", "Fox News"],
        "tvg_id": "FoxNewsChannel.us",
        "epg_ids": ["WFOX-DT.us_locals1", "KFOX-DT.us_locals1", "FoxNewsChannel.us"],
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/3b09e0ef-610a-43d4-960b-78dc97ae2bd2/dc2e6082-3de1-40e8-a3ab-b6a61b18c3b1/1280x720/match/400/225/image.jpg"
    },
    "FoxBusiness.us@NewsWorld": {
        "names": ["Fox Business Go | Fox News Video", "Fox Business", "FoxBusiness"],
        "tvg_id": "FoxBusinessNetwork.us",
        "epg_ids": ["WFOX-DT.us_locals1", "KFOX-DT.us_locals1", "FoxBusinessNetwork.us"],
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/c9b2e2eb-7b87-435c-9510-eab2650ff944/8b584585-acf2-4c37-aa07-aaf2d077bb20/1280x720/match/676/380/image.jpg"
    },
    "CBSNews.us@NewsWorld": {
        "names": ["Watch CBS News 24/7, our free live news stream", "CBS News", "CBSNews"],
        "tvg_id": "CBSNews.us",
        "epg_ids": ["WCBS-DT.us_locals1", "KCBS-DT.us_locals1", "WCBS-LD.us_locals1", "CBSNews.us"],
        "logo": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg"
    },
}

def download_epg_gz(url, timeout=180):
    print(f"Baixando EPG: {url}")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        if response.status_code == 200:
            print(f"  Baixado: {len(response.content)} bytes")
            content = response.content
            if url.endswith('.gz'):
                with gzip.open(io.BytesIO(content), 'rb') as f:
                    return f.read().decode('utf-8', errors='ignore').replace('\x00', '')
            return content.decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"  Erro: {e}")
    return None

def extract_programs_from_epg(xml_content, epg_ids, days=3):
    programs = []
    if not xml_content:
        return programs
    
    try:
        root = ET.fromstring(xml_content)
    except Exception as e:
        print(f"  Erro ao parsear EPG: {e}")
        return programs
    
    today = datetime.now()
    start_date = today.replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = start_date + timedelta(days=days)
    
    for programme in root.findall('programme'):
        channel_id = programme.get('channel', '')
        if not any(epg_id in channel_id or channel_id in epg_id for epg_id in epg_ids):
            continue
        
        start_str = programme.get('start', '')
        stop_str = programme.get('stop', '')
        
        if not start_str or not stop_str:
            continue
        
        try:
            start_dt = datetime.strptime(start_str[:14], '%Y%m%d%H%M%S')
            stop_dt = datetime.strptime(stop_str[:14], '%Y%m%d%H%M%S')
            
            if start_dt < start_date or start_dt >= end_date:
                continue
            
            title_elem = programme.find('title')
            title = title_elem.text if title_elem is not None and title_elem.text else 'Live News'
            
            desc_elem = programme.find('desc')
            desc = desc_elem.text if desc_elem is not None and desc_elem.text else 'Live news coverage'
            
            programs.append({
                'channel': channel_id,
                'start': start_dt,
                'stop': stop_dt,
                'title': title,
                'desc': desc
            })
        except Exception:
            continue
    
    return programs

def create_fallback_programs(tvg_id, channel_name, days=3):
    programs = []
    today = datetime.now()
    
    show_patterns = {
        "ABCNews": [
            ("06:00", "09:00", "ABC World News This Morning"),
            ("09:00", "11:00", "Good Morning America"),
            ("11:00", "12:30", "ABC World News Midday"),
            ("12:30", "14:00", "ABC Live Now"),
            ("14:00", "16:00", "The View"),
            ("16:00", "17:30", "ABC World News This Afternoon"),
            ("17:30", "18:30", "ABC World News Tonight"),
            ("18:30", "19:00", "ABC World News Prime"),
            ("19:00", "20:00", "ABC Evening News"),
            ("20:00", "22:00", "ABC Live Prime Time"),
            ("22:00", "23:00", "Nightline"),
            ("23:00", "06:00", "ABC World News Now"),
        ],
        "FoxNews": [
            ("06:00", "09:00", "Fox & Friends First"),
            ("09:00", "11:00", "Fox & Friends"),
            ("11:00", "12:00", "America's Newsroom"),
            ("12:00", "13:00", "Fox News @ Noon"),
            ("13:00", "15:00", "The Story"),
            ("15:00", "17:00", "The Five"),
            ("17:00", "18:00", "Fox News Tonight"),
            ("18:00", "19:00", "Fox News Sunday"),
            ("19:00", "20:00", "Tucker Carlson Tonight"),
            ("20:00", "21:00", "Hannity"),
            ("21:00", "22:00", "The Ingraham Angle"),
            ("22:00", "23:00", "Fox News @ Night"),
            ("23:00", "06:00", "Fox News Overnight"),
        ],
        "FoxBusiness": [
            ("06:00", "09:00", "Fox Business Morning"),
            ("09:00", "11:00", "Varney & Co."),
            ("11:00", "12:00", "The Big Money Show"),
            ("12:00", "13:00", "Fox Business Midday"),
            ("13:00", "14:00", "The Claman Countdown"),
            ("14:00", "15:00", "Making Money"),
            ("15:00", "17:00", "The Five"),
            ("17:00", "18:00", "Cavuto: Coast to Coast"),
            ("18:00", "19:00", "Fox Business Tonight"),
            ("19:00", "20:00", "Kudlow"),
            ("20:00", "21:00", "The Big Money Show"),
            ("21:00", "22:00", "Fox Business @ Night"),
            ("22:00", "06:00", "Fox Business Overnight"),
        ],
        "CBSNews": [
            ("06:00", "07:00", "CBS Morning News"),
            ("07:00", "09:00", "CBS This Morning"),
            ("09:00", "10:00", "CBS News Daily"),
            ("10:00", "12:00", "CBS This Morning"),
            ("12:00", "12:30", "CBS News Midday"),
            ("12:30", "13:30", "CBS News Update"),
            ("13:30", "14:00", "The Price Is Right"),
            ("14:00", "14:30", "CBS News Update"),
            ("14:30", "15:30", "The Young and the Restless"),
            ("15:30", "16:30", "CBS News Afternoon"),
            ("16:30", "17:30", "CBS Evening News"),
            ("17:30", "18:30", "CBS News Evening"),
            ("18:30", "19:00", "CBS World News Tonight"),
            ("19:00", "20:00", "60 Minutes"),
            ("20:00", "21:00", "CBS News Special"),
            ("21:00", "22:00", "CBS News Special"),
            ("22:00", "23:00", "CBS News Nightwatch"),
            ("23:00", "06:00", "CBS News Overnight"),
        ],
    }
    
    show_key = "ABCNews"
    for key in show_patterns:
        if key in tvg_id or key in channel_name:
            show_key = key
            break
    
    patterns = show_patterns.get(show_key, show_patterns["ABCNews"])
    
    for day_offset in range(days):
        current_day = today + timedelta(days=day_offset)
        for start_time, stop_time, title in patterns:
            start_h, start_m = map(int, start_time.split(':'))
            stop_h, stop_m = map(int, stop_time.split(':'))
            
            start_dt = current_day.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
            if stop_h < start_h:
                stop_dt = (current_day + timedelta(days=1)).replace(hour=stop_h, minute=stop_m, second=0, microsecond=0)
            else:
                stop_dt = current_day.replace(hour=stop_h, minute=stop_m, second=0, microsecond=0)
            
            if day_offset == 0 and start_dt < datetime.now():
                continue
            
            programs.append({
                'channel': tvg_id,
                'start': start_dt,
                'stop': stop_dt,
                'title': title,
                'desc': f'Live news coverage - {title}'
            })
    
    return programs

def generate_epg(listing_channels, days=3):
    today = datetime.now()
    all_programs = []
    
    print("\nBaixando EPG de fontes externas...")
    for source_url in EPG_SOURCES:
        xml_content = download_epg_gz(source_url)
        if xml_content:
            for channel_key, channel_info in listing_channels.items():
                epg_programs = extract_programs_from_epg(xml_content, channel_info['epg_ids'], days)
                if epg_programs:
                    print(f"  Encontrados {len(epg_programs)} programas de {source_url.split('/')[-1]} para {channel_key}")
                    all_programs.extend(epg_programs)
    
    xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<tv date="{today.strftime('%Y%m%d%H%M%S')} +0000" source-info="JCTV News World" source-info-url="https://github.com/JCTV/JCTV">
'''
    
    for channel_key, channel_info in listing_channels.items():
        channel_id = channel_info['tvg_id']
        xml += f'''  <channel id="{channel_id}">
    <display-name lang="en">{channel_info['names'][0]}</display-name>
    <icon src="{channel_info['logo']}" />
  </channel>
'''
    
    channel_programs = {}
    for ch_key, ch_info in listing_channels.items():
        tvg_id = ch_info['tvg_id']
        if tvg_id not in channel_programs:
            channel_programs[tvg_id] = []
        channel_programs[tvg_id].extend([p for p in all_programs if p['channel'] == tvg_id])
    
    for channel_key, channel_info in listing_channels.items():
        tvg_id = channel_info['tvg_id']
        ch_name = channel_info['names'][0]
        
        if channel_programs.get(tvg_id):
            existing_starts = set(p['start'] for p in channel_programs[tvg_id])
        else:
            existing_starts = set()
        
        fallback_programs = create_fallback_programs(tvg_id, ch_name, days)
        for prog in fallback_programs:
            if prog['start'] not in existing_starts:
                all_programs.append(prog)
    
    for prog in sorted(all_programs, key=lambda x: (x['channel'], x['start'])):
        start_str = prog['start'].strftime('%Y%m%d%H%M%S') + ' +0000'
        stop_str = prog['stop'].strftime('%Y%m%d%H%M%S') + ' +0000'
        title = prog['title'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        desc = prog['desc'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        xml += f'''  <programme channel="{prog['channel']}" start="{start_str}" stop="{stop_str}">
    <title lang="en">{title}</title>
    <desc lang="en">{desc}</desc>
  </programme>
'''
    
    xml += '</tv>'
    return xml

def main():
    print("=" * 60)
    print("Gerando EPG para lista5.m3u (NEWS WORLD)")
    print("=" * 60)
    
    listing_channels = {}
    for ch_key, ch_info in CHANNEL_MAPPING.items():
        listing_channels[ch_key] = ch_info
    
    epg_content = generate_epg(listing_channels, days=3)
    
    output_file = 'lista5_epg_news_world.xml'
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(epg_content)
    
    print(f"\nEPG gerado: {output_file}")
    print(f"Tamanho: {len(epg_content)} bytes")
    print("Programação para hoje, amanhã e depois de amanhã disponível")
    
    print(f"\nURL do EPG para usar no M3U:")
    print(f"x-tvg-url=\"file://$PWD/{output_file}\"")

if __name__ == "__main__":
    main()