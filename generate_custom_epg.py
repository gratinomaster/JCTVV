#!/usr/bin/env python3
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

CHANNELS = {
    "465150": {"name": "ABC News Live", "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f7/ABC_News_%282019%29.svg/200px-ABC_News_%282019%29.svg.jpg"},
    "412132": {"name": "Fox News Channel", "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/17/Fox_News_Channel_logo.svg/200px-Fox_News_Channel_logo.svg.jpg"},
    "464766": {"name": "Fox Business", "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/77/Fox_Business_logo.svg/200px-Fox_Business_logo.svg.jpg"},
    "464941": {"name": "CBS News 24/7", "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/43/CBS_News.svg/200px-CBS_News.svg.jpg"},
}

SCHEDULE = [
    ("060000", "090000", "Morning News", "Breaking news and updates from around the world"),
    ("090000", "110000", "Live Report", "Comprehensive news coverage with correspondents"),
    ("110000", "123000", "Midday Update", "Latest news developments and analysis"),
    ("123000", "140000", "Breaking News", "Live breaking news coverage as it happens"),
    ("140000", "160000", "Afternoon Edition", "News and current events coverage"),
    ("160000", "173000", "Business Update", "Financial news and market reports"),
    ("173000", "183000", "Evening News", "Daily news roundup and analysis"),
    ("183000", "190000", "World Report", "International news coverage"),
    ("190000", "200000", "Prime Time News", "In-depth news coverage and special reports"),
    ("200000", "220000", "Live Broadcast", "Live news programming"),
    ("220000", "230000", "Night Edition", "Late night news and headlines"),
    ("230000", "235959", "Overnight News", "News while you sleep"),
]

def create_epg(filename, days=3):
    root = ET.Element('tv')
    
    for ch_id, ch_info in CHANNELS.items():
        ch_elem = ET.SubElement(root, 'channel', id=ch_id)
        dn = ET.SubElement(ch_elem, 'display-name')
        dn.text = ch_info['name']
        icon = ET.SubElement(ch_elem, 'icon')
        icon.set('src', ch_info['logo'])
    
    today = datetime.now()
    for day_offset in range(days):
        current_day = today + timedelta(days=day_offset)
        date_str = current_day.strftime("%Y%m%d")
        
        for ch_id, ch_info in CHANNELS.items():
            for start_time, stop_time, title, desc in SCHEDULE:
                if day_offset == days - 1 and stop_time == "235959":
                    next_day = current_day + timedelta(days=1)
                    stop = f"{next_day.strftime('%Y%m%d')}060000 +0000"
                else:
                    stop = f"{date_str}{stop_time} +0000"
                
                prog = ET.SubElement(root, 'programme')
                prog.set('channel', ch_id)
                prog.set('start', f"{date_str}{start_time} +0000")
                prog.set('stop', stop)
                
                t = ET.SubElement(prog, 'title', lang='en')
                t.text = title
                d = ET.SubElement(prog, 'desc', lang='en')
                d.text = desc
    
    xml_str = ET.tostring(root, encoding='unicode')
    with open(filename, 'w') as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write(xml_str)
    
    print(f"EPG criado: {filename}")

def verify_epg(filename):
    print(f"\nVerificando EPG: {filename}")
    try:
        with open(filename, 'r') as f:
            content = f.read()
        
        root = ET.fromstring(content)
        today = datetime.now()
        
        for day_offset in range(3):
            check_date = (today + timedelta(days=day_offset)).strftime("%Y%m%d")
            count = 0
            for prog in root.findall('programme'):
                start = prog.get('start', '')[:8]
                if start == check_date:
                    count += 1
            
            day_names = ['Hoje', 'Amanha', 'Depois de amanha']
            print(f"  {day_names[day_offset]}: {count} programas")
        
        return True
    except Exception as e:
        print(f"  Erro: {e}")
        return False

if __name__ == '__main__':
    create_epg('lista5_epg.xml', days=3)
    verify_epg('lista5_epg.xml')
