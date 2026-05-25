#!/usr/bin/env python3
from datetime import datetime, timedelta
import gzip
import xml.etree.ElementTree as ET
import re

today = datetime.now()
tomorrow = today + timedelta(days=1)
day_after = tomorrow + timedelta(days=1)

t_str = today.strftime('%Y%m%d')
tm_str = tomorrow.strftime('%Y%m%d')
da_str = day_after.strftime('%Y%m%d')

def esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')

tv = ET.Element('tv')
tv.set('date', today.strftime('%Y%m%d%H%M%S'))

channels = [
    {
        "id": "ABCNewsLive.us",
        "name": "ABC News Live",
        "icon": "https://keyframe-cdn.abcnews.com/streamprovider5.jpg",
        "shows": [
            ("060000", "090000", "Good Morning America", "Morning news coverage from ABC News"),
            ("090000", "120000", "ABC News Live - Morning", "Live morning news coverage"),
            ("120000", "130000", "ABC World News Midday", "Midday news update from ABC News"),
            ("130000", "163000", "ABC News Live - Afternoon", "Live afternoon news coverage"),
            ("163000", "180000", "ABC News Live - The Report", "In-depth news reporting"),
            ("180000", "183000", "ABC World News Tonight", "Evening news from ABC News"),
            ("183000", "230000", "ABC News Live - Primetime", "Prime time news coverage"),
        ]
    },
    {
        "id": "FoxNewsChannel.us",
        "name": "Fox News Channel",
        "icon": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/a6a5c792-7fc5-4cbd-a17f-5c17b855647d/d5bbc9d6-134a-4eb2-a923-931842d1e2dd/1280x720/match/400/225/image.jpg",
        "shows": [
            ("050000", "090000", "Fox & Friends First", "Early morning news on Fox News Channel"),
            ("090000", "120000", "America's Newsroom", "Morning news on Fox News Channel"),
            ("120000", "150000", "Happening Now", "Midday news on Fox News Channel"),
            ("150000", "170000", "The Story with Martha MacCallum", "Afternoon news on Fox News Channel"),
            ("170000", "180000", "Your World with Neil Cavuto", "Business and news on Fox News Channel"),
            ("180000", "200000", "The Ingraham Angle", "Evening news on Fox News Channel"),
            ("200000", "230000", "Fox News Primetime", "Prime time news on Fox News Channel"),
        ]
    },
    {
        "id": "FoxBusiness.us",
        "name": "Fox Business",
        "icon": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/a6a5c792-7fc5-4cbd-a17f-5c17b855647d/d5bbc9d6-134a-4eb2-a923-931842d1e2dd/1280x720/match/400/225/image.jpg",
        "shows": [
            ("060000", "090000", "Mornings with Maria", "Morning business news on Fox Business"),
            ("090000", "120000", "Fox Business - Morning", "Morning business coverage on Fox Business"),
            ("120000", "150000", "Making Money with Charles Payne", "Midday business news on Fox Business"),
            ("150000", "170000", "The Claman Countdown", "Afternoon business news on Fox Business"),
            ("170000", "180000", "WSJ at Large", "Business news on Fox Business"),
            ("180000", "200000", "Evening Edit", "Evening business news on Fox Business"),
            ("200000", "230000", "Fox Business Primetime", "Prime time business news on Fox Business"),
        ]
    },
    {
        "id": "CBSNews.us",
        "name": "CBS News 24/7",
        "icon": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
        "shows": [
            ("060000", "090000", "CBS Mornings", "Morning news on CBS News 24/7"),
            ("090000", "120000", "CBS News 24/7 - Morning", "Live morning news on CBS News 24/7"),
            ("120000", "130000", "CBS Midday News", "Midday news on CBS News 24/7"),
            ("130000", "163000", "CBS News 24/7 - Afternoon", "Live afternoon news on CBS News 24/7"),
            ("163000", "180000", "CBS News 24/7 - The Report", "In-depth news on CBS News 24/7"),
            ("180000", "183000", "CBS Evening News", "Evening news on CBS News 24/7"),
            ("183000", "220000", "CBS News 24/7 - Primetime", "Prime time news on CBS News 24/7"),
        ]
    },
]

for ch in channels:
    ch_el = ET.SubElement(tv, 'channel')
    ch_el.set('id', ch['id'])
    dn = ET.SubElement(ch_el, 'display-name')
    dn.set('lang', 'en')
    dn.text = ch['name']
    icon = ET.SubElement(ch_el, 'icon')
    icon.set('src', ch['icon'])

    for day_offset, date_str in enumerate([t_str, tm_str, da_str]):
        overnight_show = ch['shows'][-1]
        if day_offset >= 2:
            for k, (start, end, title, desc) in enumerate(ch['shows'][:3]):
                prog = ET.SubElement(tv, 'programme')
                prog.set('channel', ch['id'])
                prog.set('start', f"{date_str}{start}00 +0000")
                prog.set('stop', f"{date_str}{end}00 +0000")
                t_el = ET.SubElement(prog, 'title')
                t_el.set('lang', 'en')
                t_el.text = title
                d_el = ET.SubElement(prog, 'desc')
                d_el.set('lang', 'en')
                d_el.text = desc
            continue

        for k, (start, end, title, desc) in enumerate(ch['shows']):
            prog = ET.SubElement(tv, 'programme')
            prog.set('channel', ch['id'])

            if k == len(ch['shows']) - 1:
                next_date = [tm_str, da_str][day_offset]
                prog.set('start', f"{date_str}{start}00 +0000")
                prog.set('stop', f"{next_date}{end}00 +0000")
            else:
                prog.set('start', f"{date_str}{start}00 +0000")
                prog.set('stop', f"{date_str}{end}00 +0000")

            t_el = ET.SubElement(prog, 'title')
            t_el.set('lang', 'en')
            t_el.text = title
            d_el = ET.SubElement(prog, 'desc')
            d_el.set('lang', 'en')
            d_el.text = desc

xml_bytes = ET.tostring(tv, encoding='utf-8', xml_declaration=True)

with open('lista5_epg.xml', 'wb') as f:
    f.write(xml_bytes)

with gzip.open('lista5_epg.xml.gz', 'wb') as f:
    f.write(xml_bytes)

root = ET.fromstring(xml_bytes)
chs = root.findall('channel')
progs = root.findall('programme')
print(f"EPG gerado com {len(chs)} canais e {len(progs)} programas")
for ch in chs:
    cid = ch.get('id')
    tc = sum(1 for p in progs if p.get('channel')==cid and p.get('start','')[:8]==t_str)
    tmc = sum(1 for p in progs if p.get('channel')==cid and p.get('start','')[:8]==tm_str)
    dac = sum(1 for p in progs if p.get('channel')==cid and p.get('start','')[:8]==da_str)
    print(f"  {cid}: hoje={tc} amanhã={tmc} depois={dac}")
