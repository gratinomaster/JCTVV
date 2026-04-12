#!/usr/bin/env python3
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from xml.dom import minidom

def generate_news_epg():
    channels = {
        "ABCNewsLive.us": "ABC News Live",
        "FoxNewsChannel.us": "Fox News Channel",
        "FoxBusinessNetwork.us": "Fox Business Network",
        "CBSNewsNetwork.us": "CBS News 24/7",
    }
    
    news_programs = {
        "ABCNewsLive.us": [
            ("ABC World News This Morning", "06:00", "09:00"),
            ("Good Morning America", "09:00", "11:00"),
            ("ABC World News Midday", "11:00", "12:30"),
            ("ABC Live Now", "12:30", "14:00"),
            ("ABC World News This Afternoon", "14:00", "17:00"),
            ("ABC World News Tonight", "17:00", "18:30"),
            ("ABC Evening News", "18:30", "19:00"),
            ("ABC Live Prime Time", "20:00", "22:00"),
            ("Nightline", "22:00", "23:00"),
            ("ABC World News Now", "23:00", "06:00"),
        ],
        "FoxNewsChannel.us": [
            ("Fox & Friends First", "06:00", "09:00"),
            ("Fox & Friends", "09:00", "11:00"),
            ("America's Newsroom", "11:00", "12:00"),
            ("Fox News @ Noon", "12:00", "13:00"),
            ("The Story", "13:00", "15:00"),
            ("The Five", "15:00", "17:00"),
            ("Fox News Tonight", "17:00", "20:00"),
            ("Tucker Carlson Tonight", "20:00", "21:00"),
            ("Hannity", "21:00", "22:00"),
            ("The Ingraham Angle", "22:00", "23:00"),
            ("Fox News @ Night", "23:00", "00:00"),
        ],
        "FoxBusinessNetwork.us": [
            ("Fox Business Morning", "06:00", "09:00"),
            ("Varney & Co.", "09:00", "11:00"),
            ("The Big Money Show", "11:00", "12:00"),
            ("Fox Business Midday", "12:00", "13:00"),
            ("The Claman Countdown", "13:00", "14:00"),
            ("Making Money", "14:00", "15:00"),
            ("Cavuto: Coast to Coast", "15:00", "17:00"),
            ("Fox Business Tonight", "17:00", "19:00"),
            ("Kudlow", "19:00", "20:00"),
            ("Fox Business @ Night", "20:00", "00:00"),
        ],
        "CBSNewsNetwork.us": [
            ("CBS Morning News", "06:00", "07:00"),
            ("CBS This Morning", "07:00", "09:00"),
            ("CBS News Daily", "09:00", "10:00"),
            ("CBS News Midday", "12:00", "12:30"),
            ("CBS News Update", "12:30", "13:30"),
            ("CBS News Afternoon", "13:30", "16:30"),
            ("CBS Evening News", "16:30", "17:30"),
            ("CBS World News Tonight", "18:30", "19:00"),
            ("60 Minutes", "19:00", "20:00"),
            ("CBS News Nightwatch", "22:00", "23:00"),
            ("CBS News Overnight", "23:00", "06:00"),
        ],
    }
    
    root = ET.Element('tv')
    root.set('generator-info-name', 'Custom News EPG Generator')
    root.set('generator-info-url', 'https://github.com/JCTV')
    
    today = datetime.now()
    
    for ch_id, ch_name in channels.items():
        channel = ET.SubElement(root, 'channel')
        channel.set('id', ch_id)
        
        display_name = ET.SubElement(channel, 'display-name')
        display_name.set('lang', 'en')
        display_name.text = ch_name
        
        icon = ET.SubElement(channel, 'icon')
        icon_url = f'https://raw.githubusercontent.com/tv-logo/tv-logos/main/united-states/{ch_id.lower().replace(".", "-")}.png'
        icon.set('src', icon_url)
    
    for day_offset in range(3):
        current_date = today + timedelta(days=day_offset)
        date_str = current_date.strftime('%Y%m%d')
        
        for ch_id, programs in news_programs.items():
            for prog_name, start_time, end_time in programs:
                programme = ET.SubElement(root, 'programme')
                programme.set('channel', ch_id)
                
                start_dt = f"{date_str}{start_time.replace(':', '')}00 +0000"
                
                if end_time == "00:00":
                    end_dt = f"{current_date.strftime('%Y%m%d')}235900 +0000"
                elif end_time < start_time:
                    end_date = current_date + timedelta(days=1)
                    end_dt = f"{end_date.strftime('%Y%m%d')}{end_time.replace(':', '')}00 +0000"
                else:
                    end_dt = f"{date_str}{end_time.replace(':', '')}00 +0000"
                
                programme.set('start', start_dt)
                programme.set('stop', end_dt)
                
                title = ET.SubElement(programme, 'title')
                title.set('lang', 'en')
                title.text = prog_name
                
                desc = ET.SubElement(programme, 'desc')
                desc.set('lang', 'en')
                desc.text = f"Live news coverage - {prog_name}"
    
    xml_str = ET.tostring(root, encoding='unicode')
    dom = minidom.parseString(xml_str)
    pretty_xml = dom.toprettyxml(indent="  ")
    
    lines = pretty_xml.split('\n')
    lines = [line for line in lines if line.strip()]
    result = '\n'.join(lines)
    
    with open('lista5_epg_custom_news.xml', 'w', encoding='utf-8') as f:
        f.write(result)
    
    print(f"EPG customizado gerado: lista5_epg_custom_news.xml")
    print(f"Canais: {len(channels)}")
    print(f"Programas por canal: {len(next(iter(news_programs.values())))} por dia x 3 dias")
    
    return result

if __name__ == "__main__":
    result = generate_news_epg()
    print("\n--- Preview do EPG ---")
    print(result[:2000])
