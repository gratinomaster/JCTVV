#!/usr/bin/env python3
"""
Extend the existing EPG XML to include programming for more days.
Appends generated programmes for missing dates to keep real data intact.
"""
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
import copy

EPG_FILE = "/home/runner/work/JCTVV/JCTVV/lista5_epg.xml"

SCHEDULE = [
    ("000000", "010000", "Overnight News", "Late night news coverage"),
    ("010000", "020000", "Overnight Report", "News updates through the night"),
    ("020000", "030000", "News Replay", "Replay of top stories"),
    ("030000", "040000", "Early Morning News", "Early morning headlines"),
    ("040000", "050000", "Morning Preview", "Preview of today's top stories"),
    ("050000", "060000", "Sunrise News", "Morning news coverage"),
    ("060000", "070000", "Morning News", "Breaking news and updates from around the world"),
    ("070000", "080000", "Morning Report", "Morning news and analysis"),
    ("080000", "090000", "Today's News", "Comprehensive morning news coverage"),
    ("090000", "100000", "Live Report", "Comprehensive news coverage with correspondents"),
    ("100000", "110000", "News Now", "Continuous news coverage"),
    ("110000", "120000", "Midday Update", "Latest news developments and analysis"),
    ("120000", "130000", "Breaking News", "Live breaking news coverage as it happens"),
    ("130000", "140000", "News Desk", "News coverage and updates"),
    ("140000", "150000", "Afternoon Edition", "News and current events coverage"),
    ("150000", "160000", "Live News", "Live news broadcast"),
    ("160000", "170000", "Business Update", "Financial news and market reports"),
    ("170000", "180000", "Evening News", "Daily news roundup and analysis"),
    ("180000", "190000", "World Report", "International news coverage"),
    ("190000", "200000", "Prime Time News", "In-depth news coverage and special reports"),
    ("200000", "210000", "Live Broadcast", "Live news programming"),
    ("210000", "220000", "News Night", "Evening news coverage"),
    ("220000", "230000", "Night Edition", "Late night news and headlines"),
    ("230000", "235959", "Overnight News", "News while you sleep"),
]

def extend_epg(days_to_add=4):
    """Extend EPG to cover more days."""
    tree = ET.parse(EPG_FILE)
    root = tree.getroot()

    # Get existing channel IDs
    channels = {}
    for ch in root.findall('channel'):
        ch_id = ch.get('id')
        dn = ch.find('display-name')
        channels[ch_id] = dn.text if dn is not None else ch_id

    # Get existing dates
    existing_dates = set()
    for p in root.findall('programme'):
        start = p.get('start', '')
        if start:
            existing_dates.add(start[:8])

    today = datetime.now(timezone.utc)
    print(f"Today: {today.strftime('%Y%m%d')}")
    print(f"Existing dates in EPG: {sorted(existing_dates)}")

    # Determine which dates need to be added
    needed_dates = []
    for i in range(days_to_add):
        date_str = (today + timedelta(days=i)).strftime('%Y%m%d')
        if date_str not in existing_dates:
            needed_dates.append(date_str)

    if not needed_dates:
        print("All dates already covered.")
        return

    print(f"Dates to add: {needed_dates}")
    total_added = 0

    for date_str in needed_dates:
        for ch_id, ch_name in channels.items():
            for start_time, stop_time, title, desc in SCHEDULE:
                prog = ET.SubElement(root, 'programme')
                prog.set('channel', ch_id)
                prog.set('start', f"{date_str}{start_time} +0000")
                prog.set('stop', f"{date_str}{stop_time} +0000")
                t = ET.SubElement(prog, 'title', lang='en')
                t.text = title
                d = ET.SubElement(prog, 'desc', lang='en')
                d.text = desc
                total_added += 1

    # Write updated XML
    xml_str = ET.tostring(root, encoding='unicode')
    with open(EPG_FILE, 'w', encoding='utf-8') as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write(xml_str)

    print(f"Added {total_added} programmes for {len(needed_dates)} new date(s)")

    # Verify
    tree2 = ET.parse(EPG_FILE)
    root2 = tree2.getroot()
    all_dates = set()
    for p in root2.findall('programme'):
        start = p.get('start', '')
        if start:
            all_dates.add(start[:8])
    print(f"All dates now: {sorted(all_dates)}")
    print(f"Total programmes: {len(root2.findall('programme'))}")

if __name__ == '__main__':
    extend_epg(days_to_add=4)
