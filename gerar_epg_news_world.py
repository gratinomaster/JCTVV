#!/usr/bin/env python3
import gzip
import requests
import io
import re
from datetime import datetime, timedelta
import hashlib
import urllib.parse

EPG_URLS = [
    "https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.xml.gz",
]

CHANNEL_MAPPING = {
    "ABCNL Prime": {
        "names": ["ABCNL Prime", "ABC News Prime", "Linsey Davis"],
        "epg_ids": ["WABC-DT.us_locals1", "KABC-DT.us_locals1"],
        "logo": "https://s.abcnews.com/images/Live/abc_news_live-abc-ml-250210_1739199021469_hpMain_16x9_608.jpg",
    },
    "ABC News Live": {
        "names": ["ABC News Live", "ABC News"],
        "epg_ids": ["WABC-DT.us_locals1", "KABC-DT.us_locals1"],
        "logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
    },
    "Fox News": {
        "names": ["Fox News", "FoxNews"],
        "epg_ids": ["WFOX-DT.us_locals1", "KFOX-DT.us_locals1"],
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/3b09e0ef-610a-43d4-960b-78dc97ae2bd2/dc2e6082-3de1-40e8-a3ab-b6a61b18c3b1/1280x720/match/400/225/image.jpg",
    },
    "Fox Business": {
        "names": ["Fox Business", "FoxBusiness", "Fox Business Go"],
        "epg_ids": ["WFOX-DT.us_locals1", "KFOX-DT.us_locals1"],
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/3b09e0ef-610a-43d4-960b-78dc97ae2bd2/dc2e6082-3de1-40e8-a3ab-b6a61b18c3b1/1280x720/match/400/225/image.jpg",
    },
    "CBS News": {
        "names": ["CBS News", "CBSNews"],
        "epg_ids": ["WCBS-DT.us_locals1", "KCBS-DT.us_locals1", "WCBS-LD.us_locals1"],
        "logo": "https://www.cbsnews.com/bundles/cbsnewsvideo/images/cbsn--main-bg.jpg",
    },
}

def download_epg(url):
    print(f"Baixando EPG: {url}")
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.get(url, headers=headers, timeout=180)
    if response.status_code == 200:
        print(f"  Baixado: {len(response.content)} bytes")
        with gzip.open(io.BytesIO(response.content), 'rb') as f:
            return f.read().decode('utf-8', errors='ignore').replace('\x00', '')
    return None

def create_epg_for_channel(channel_name, epg_ids, days=3):
    today = datetime.now()
    programs = []
    
    for day_offset in range(days):
        current_day = today + timedelta(days=day_offset)
        day_name = current_day.strftime('%A')
        
        programs.append({
            'start': current_day.replace(hour=6, minute=0, second=0),
            'stop': current_day.replace(hour=9, minute=0, second=0),
            'title': f'Morning Show - {day_name}',
            'desc': f'Notícias da manhã com as principais histórias do dia'
        })
        programs.append({
            'start': current_day.replace(hour=9, minute=0, second=0),
            'stop': current_day.replace(hour=12, minute=0, second=0),
            'title': f'News Morning - {day_name}',
            'desc': 'Cobertura completa das notícias da manhã'
        })
        programs.append({
            'start': current_day.replace(hour=12, minute=0, second=0),
            'stop': current_day.replace(hour=13, minute=0, second=0),
            'title': f' midday News - {day_name}',
            'desc': 'Edição do meio-dia com as principais notícias'
        })
        programs.append({
            'start': current_day.replace(hour=13, minute=0, second=0),
            'stop': current_day.replace(hour=18, minute=0, second=0),
            'title': f'Afternoon News - {day_name}',
            'desc': 'Cobertura das notícias da tarde'
        })
        programs.append({
            'start': current_day.replace(hour=18, minute=0, second=0),
            'stop': current_day.replace(hour=19, minute=0, second=0),
            'title': f'Evening News - {day_name}',
            'desc': 'Edição vespertina com as principais notícias'
        })
        programs.append({
            'start': current_day.replace(hour=19, minute=0, second=0),
            'stop': current_day.replace(hour=22, minute=0, second=0),
            'title': f'Prime Time News - {day_name}',
            'desc': 'Cobertura completa do noticiário da noite'
        })
        programs.append({
            'start': current_day.replace(hour=22, minute=0, second=0),
            'stop': (current_day + timedelta(days=1)).replace(hour=6, minute=0, second=0),
            'title': f'Night Edition - {day_name}',
            'desc': 'Últimas notícias do dia'
        })
    
    return programs

def generate_epg(listing_channels):
    today = datetime.now()
    epg_id = hashlib.md5(f"lista5_news_{today.strftime('%Y%m%d')}".encode()).hexdigest()[:12]
    
    xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<tv date="{today.strftime('%Y%m%d%H%M%S')}">
'''
    
    for ch_name, ch_info in listing_channels.items():
        channel_id = ch_name.lower().replace(' ', '').replace('&', '').replace('-', '')[:20]
        
        xml += f'''  <channel id="{channel_id}">
    <display-name lang="en">{ch_name}</display-name>
    <icon src="{ch_info['logo']}" />
  </channel>
'''
    
    for ch_name, ch_info in listing_channels.items():
        channel_id = ch_name.lower().replace(' ', '').replace('&', '').replace('-', '')[:20]
        programs = create_epg_for_channel(ch_name, ch_info.get('epg_ids', []))
        
        for prog in programs:
            start = prog['start'].strftime('%Y%m%d%H%M%S') + ' +0000'
            stop = prog['stop'].strftime('%Y%m%d%H%M%S') + ' +0000'
            xml += f'''  <programme channel="{channel_id}" start="{start}" stop="{stop}">
    <title lang="en">{prog['title']}</title>
    <desc lang="en">{prog['desc']}</desc>
  </programme>
'''
    
    xml += '</tv>'
    return xml

if __name__ == "__main__":
    print("=" * 60)
    print("Gerando EPG para lista5.m3u (NEWS WORLD)")
    print("=" * 60)
    
    listing_channels = {}
    
    for ch_name, ch_info in CHANNEL_MAPPING.items():
        listing_channels[ch_name] = ch_info
    
    epg_content = generate_epg(listing_channels)
    
    with open('lista5_epg.xml', 'w', encoding='utf-8') as f:
        f.write(epg_content)
    
    print(f"\nEPG gerado: lista5_epg.xml ({len(epg_content)} bytes)")
    print("Programação para os próximos 3 dias disponível")