#!/usr/bin/env python3
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from collections import defaultdict

CHANNELS = [
    ("ABCNewsLive.us", "ABC News Live", "https://raw.githubusercontent.com/tv-logo/tv-logos/main/united-states/abcnewslive-us.png"),
    ("FoxNewsChannel.us", "Fox News Channel", "https://raw.githubusercontent.com/tv-logo/tv-logos/main/united-states/foxnewschannel-us.png"),
    ("FoxBusinessNetwork.us", "Fox Business Network", "https://raw.githubusercontent.com/tv-logo/tv-logos/main/united-states/foxbusinessnetwork-us.png"),
    ("CBSNewsNetwork.us", "CBS News 24/7", "https://raw.githubusercontent.com/tv-logo/tv-logos/main/united-states/cbsnewsnetwork-us.png"),
]

ABC_PROGRAMS = [
    ("06:00", "09:00", "ABC World News This Morning"),
    ("09:00", "11:00", "Good Morning America"),
    ("11:00", "12:30", "ABC World News Midday"),
    ("12:30", "14:00", "ABC Live Now"),
    ("14:00", "17:00", "ABC World News This Afternoon"),
    ("17:00", "18:30", "ABC World News Tonight"),
    ("18:30", "19:00", "ABC Evening News"),
    ("19:00", "20:00", "ABC World News Prime"),
    ("20:00", "22:00", "ABC Live Prime Time"),
    ("22:00", "23:00", "Nightline"),
    ("23:00", "06:00", "ABC World News Now"),
]

FOX_PROGRAMS = [
    ("06:00", "09:00", "Fox & Friends First"),
    ("09:00", "11:00", "Fox & Friends"),
    ("11:00", "12:00", "America's Newsroom"),
    ("12:00", "13:00", "Fox News @ Noon"),
    ("13:00", "15:00", "The Story"),
    ("15:00", "17:00", "The Five"),
    ("17:00", "20:00", "Fox News Tonight"),
    ("20:00", "21:00", "Tucker Carlson Tonight"),
    ("21:00", "22:00", "Hannity"),
    ("22:00", "23:00", "The Ingraham Angle"),
    ("23:00", "00:00", "Fox News @ Night"),
]

FOX_BUSINESS_PROGRAMS = [
    ("06:00", "09:00", "Mornings with Maria"),
    ("09:00", "12:00", "Varney & Co"),
    ("12:00", "14:00", "The Cash Flow"),
    ("14:00", "17:00", "Making Money with Charles Payne"),
    ("17:00", "20:00", "The Evening Edit"),
    ("20:00", "21:00", "Kudlow"),
    ("21:00", "22:00", "The Claman Countdown"),
    ("22:00", "23:00", "Mornings with Maria (Replay)"),
    ("23:00", "00:00", "Fox Business @ Night"),
]

CBS_PROGRAMS = [
    ("06:00", "07:00", "CBS Morning News"),
    ("07:00", "09:00", "CBS This Morning"),
    ("09:00", "10:00", "CBS News Daily"),
    ("10:00", "12:00", "CBS News NOW"),
    ("12:00", "12:30", "CBS News Midday"),
    ("12:30", "13:30", "CBS News Update"),
    ("13:30", "16:30", "CBS News Afternoon"),
    ("16:30", "17:30", "CBS Evening News"),
    ("17:30", "18:30", "CBS World News Tonight"),
    ("18:30", "19:00", "CBS 60"),
    ("19:00", "22:00", "CBS News Prime"),
    ("22:00", "23:00", "CBS News Nightwatch"),
    ("23:00", "06:00", "CBS News Overnight"),
]

PROGRAMS_MAP = {
    "ABCNewsLive.us": ABC_PROGRAMS,
    "FoxNewsChannel.us": FOX_PROGRAMS,
    "FoxBusinessNetwork.us": FOX_BUSINESS_PROGRAMS,
    "CBSNewsNetwork.us": CBS_PROGRAMS,
}

def create_epg():
    root = ET.Element('tv')
    root.set('generator-info-name', 'News World EPG')
    root.set('generator-info-url', 'https://github.com/JCTV')
    
    today = datetime.now()
    
    for ch_id, ch_name, ch_icon in CHANNELS:
        ch = ET.SubElement(root, 'channel')
        ch.set('id', ch_id)
        disp = ET.SubElement(ch, 'display-name')
        disp.set('lang', 'en')
        disp.text = ch_name
        icon = ET.SubElement(ch, 'icon')
        icon.set('src', ch_icon)
    
    for day_offset in range(3):
        dt = today + timedelta(days=day_offset)
        date_str = dt.strftime('%Y%m%d')
        
        for ch_id, ch_name, ch_icon in CHANNELS:
            programs = PROGRAMS_MAP.get(ch_id, ABC_PROGRAMS)
            
            for start_time, end_time, title in programs:
                prog = ET.SubElement(root, 'programme')
                prog.set('channel', ch_id)
                prog.set('start', f"{date_str}{start_time.replace(':','')}00 +0000")
                prog.set('stop', f"{date_str}{end_time.replace(':','')}00 +0000")
                
                title_elem = ET.SubElement(prog, 'title')
                title_elem.set('lang', 'en')
                title_elem.text = title
                
                desc = ET.SubElement(prog, 'desc')
                desc.set('lang', 'en')
                desc.text = f"Live news coverage - {title}"
    
    return root

def main():
    root = create_epg()
    tree = ET.ElementTree(root)
    ET.indent(tree, space='  ')
    tree.write('lista5_epg_news_fixed.xml', encoding='UTF-8', xml_declaration=True)
    
    today = datetime.now()
    tomorrow = today + timedelta(days=1)
    after = today + timedelta(days=2)
    
    print(f"EPG gerado com sucesso!")
    print(f"Programação para:")
    print(f"  - Hoje: {today.strftime('%d/%m/%Y')}")
    print(f"  - Amanhã: {tomorrow.strftime('%d/%m/%Y')}")
    print(f"  - Depois de amanhã: {after.strftime('%d/%m/%Y')}")
    
    with open('lista5_epg_news_fixed.xml', 'r') as f:
        content = f.read()
    import io
    with io.StringIO() as s:
        tree.write(s, encoding='unicode')
        lines = s.getvalue().count('\n')
    print(f"\nArquivo: lista5_epg_news_fixed.xml ({lines} linhas)")

if __name__ == "__main__":
    main()