#!/usr/bin/env python3
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

def gerar_epg():
    """Gera EPG para os canais da lista5.m3u"""
    
    canais = [
        {
            "id": "ABCNewsLive.us@SD",
            "name": "ABC News Live",
            "logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg"
        },
        {
            "id": "FoxNewsChannel.us@SD",
            "name": "Fox News Channel",
            "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/15de0523-3be4-4a9a-8159-7020114e7036/b6ff623a-26d6-4fd9-8bb8-0856adbf38ce/1280x720/match/676/380/image.jpg"
        },
        {
            "id": "FoxWeather.us@SD",
            "name": "Fox Weather",
            "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/15de0523-3be4-4a9a-8159-7020114e7036/b6ff623a-26d6-4fd9-8bb8-0856adbf38ce/1280x720/match/676/380/image.jpg"
        },
        {
            "id": "CBSNews247.us@SD",
            "name": "CBS News 24/7",
            "logo": "https://www.cbsnews.com/bundles/cbsnewsvideo/images/cbsn--main-bg.jpg"
        },
    ]
    
    programas_templates = {
        "ABCNewsLive.us@SD": [
            ("ABC World News This Morning", "Morning news coverage with latest updates"),
            ("ABC World News Midday", "Midday news program"),
            ("ABC Live - Afternoon Update", "Afternoon news coverage"),
            ("ABC World News Tonight", "Evening news program"),
            ("ABC Live - Prime Time", "Prime time news coverage"),
            ("ABC Nightline", "Late night news program"),
            ("ABC World News Now", "Overnight news coverage"),
        ],
        "FoxNewsChannel.us@SD": [
            ("Fox & Friends First", "Morning news program"),
            ("Fox & Friends", "Morning news and talk show"),
            ("America's Newsroom", "News program with latest updates"),
            ("Hannity", "Political commentary and news"),
            ("The Ingraham Angle", "Evening news commentary"),
            ("Fox News @ Night", "Late night news program"),
            ("Gutfeld!", "Late night comedy news"),
        ],
        "FoxWeather.us@SD": [
            ("Weather Today Morning", "Morning weather updates"),
            ("Weather Midday Report", "Midday weather report"),
            ("Weather Alert Center", "Weather alerts and updates"),
            ("Evening Weather Report", "Evening weather coverage"),
            ("Weather Tonight", "Night weather forecast"),
            ("Overnight Weather Watch", "Overnight weather monitoring"),
            ("Early Morning Weather", "Early morning weather updates"),
        ],
        "CBSNews247.us@SD": [
            ("CBS News Mornings", "Morning news coverage"),
            ("CBS News Midday", "Midday news program"),
            ("CBS Evening News", "Evening news broadcast"),
            ("CBS News 24/7 Live", "Continuous news coverage"),
            ("Face the Nation", "Sunday morning news program"),
        ],
    }
    
    root = ET.Element("tv")
    now = datetime.now()
    
    for canal in canais:
        ch_elem = ET.SubElement(root, "channel")
        ch_elem.set("id", canal["id"])
        
        display_name = ET.SubElement(ch_elem, "display-name")
        display_name.text = canal["name"]
        
        icon = ET.SubElement(ch_elem, "icon")
        icon.set("src", canal["logo"])
        
        templates = programas_templates.get(canal["id"], [])
        
        for day_offset in range(3):
            current_date = now + timedelta(days=day_offset)
            date_str = current_date.strftime("%Y%m%d")
            
            for hour in range(24):
                for minute in [0, 30]:
                    start_time = f"{date_str}{hour:02d}{minute:02d}00"
                    end_hour = hour
                    end_minute = minute + 30
                    if end_minute >= 60:
                        end_hour += 1
                        end_minute = 0
                    end_time = f"{date_str}{end_hour:02d}{end_minute:02d}00"
                    
                    if end_hour >= 24:
                        continue
                    
                    prog_index = (hour * 2 + minute // 30) % len(templates)
                    title, desc = templates[prog_index]
                    
                    prog = ET.SubElement(root, "programme")
                    prog.set("channel", canal["id"])
                    prog.set("start", f"{start_time} +0000")
                    prog.set("stop", f"{end_time} +0000")
                    
                    title_elem = ET.SubElement(prog, "title")
                    title_elem.set("lang", "en")
                    title_elem.text = title
                    
                    desc_elem = ET.SubElement(prog, "desc")
                    desc_elem.set("lang", "en")
                    desc_elem.text = desc
    
    tree = ET.ElementTree(root)
    tree.write("/home/runner/work/JCTV/JCTV/lista5_epg.xml", encoding="UTF-8", xml_declaration=True)
    
    return len(root.findall("channel")), len(root.findall("programme"))

if __name__ == "__main__":
    canais, programas = gerar_epg()
    print(f"EPG gerado: {canais} canais, {programas} programas")
    
    now = datetime.now()
    print(f"\nDias cobertos: {now.strftime('%Y-%m-%d')} (hoje)")
    print(f"            : {(now + timedelta(days=1)).strftime('%Y-%m-%d')} (amanhã)")
    print(f"            : {(now + timedelta(days=2)).strftime('%Y-%m-%d')} (depois de amanhã)")
