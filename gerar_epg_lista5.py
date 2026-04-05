#!/usr/bin/env python3
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import requests

def gerar_epg_lista5():
    """Gera EPG para os canais da lista5.m3u"""
    
    canais = [
        {
            "id": "ABCNewsLive.us@SD",
            "name": "ABC News Live",
            "logo": "https://keyframe-cdn.abcnews.com/streamprovider10.jpg"
        },
        {
            "id": "ABCNewsLiveBeirut.us@SD",
            "name": "ABC News Live - Beirut",
            "logo": "https://keyframe-cdn.abcnews.com/streamprovider5.jpg"
        },
        {
            "id": "FoxNewsChannel.us@SD",
            "name": "Fox News Channel",
            "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/15de0523-3be4-4a9a-8159-7020114e7036/b6ff623a-26d6-4fd9-8bb8-0856adbf38ce/1280x720/match/676/380/image.jpg"
        },
        {
            "id": "FoxBusinessNetwork.us@SD",
            "name": "Fox Business Network",
            "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/c9b2e2eb-7b87-435c-9510-eab2650ff944/8b584585-acf2-4c37-aa07-aaf2d077bb20/1280x720/match/676/380/image.jpg"
        },
        {
            "id": "CBSNews247.us@SD",
            "name": "CBS News 24/7",
            "logo": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg"
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
        "ABCNewsLiveBeirut.us@SD": [
            ("Live Coverage from Beirut", "On-the-ground reporting from Beirut"),
            ("Middle East Update", "Latest news from the Middle East region"),
            ("Breaking News Coverage", "Breaking news updates"),
            ("International News Report", "International news coverage"),
            ("Live from Beirut", "Live reporting from Beirut"),
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
        "FoxBusinessNetwork.us@SD": [
            ("Mornings with Maria", "Morning business news program"),
            ("Fox Business Morning", "Business news coverage"),
            ("Making Money", "Financial news and advice"),
            ("The Claman Countdown", "Market closing coverage"),
            ("Cavuto: Coast to Coast", "Business news program"),
            ("Fox Business Tonight", "Evening business coverage"),
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
            
            if canal["id"] in ["ABCNewsLive.us@SD", "ABCNewsLiveBeirut.us@SD", "CBSNews247.us@SD"]:
                # Streams 24/7 - programas a cada 30 minutos
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
            else:
                # Programas fixos durante o dia
                times = [
                    ("060000", "090000"),
                    ("090000", "120000"),
                    ("120000", "150000"),
                    ("150000", "180000"),
                    ("180000", "210000"),
                    ("210000", "000000"),
                ]
                
                for i, (start, stop) in enumerate(times):
                    if i >= len(templates):
                        break
                    
                    start_time = f"{date_str}{start}"
                    end_date = date_str
                    if stop == "000000":
                        end_date = (current_date + timedelta(days=1)).strftime("%Y%m%d")
                    
                    prog = ET.SubElement(root, "programme")
                    prog.set("channel", canal["id"])
                    prog.set("start", f"{start_time} +0000")
                    prog.set("stop", f"{end_date}{stop} +0000")
                    
                    title, desc = templates[i]
                    
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
    canais, programas = gerar_epg_lista5()
    print(f"EPG gerado: {canais} canais, {programas} programas")
    print("Arquivo: lista5_epg.xml")
