#!/usr/bin/env python3
import xml.etree.ElementTree as ET
from datetime import datetime

tree = ET.parse('lista5_epg_news_fixed.xml')
root = tree.getroot()

today = datetime.now()
dates = [
    today.strftime('%Y%m%d'),
    (today + __import__('datetime').timedelta(days=1)).strftime('%Y%m%d'),
    (today + __import__('datetime').timedelta(days=2)).strftime('%Y%m%d'),
]

programs_by_date = {}
for prog in root.findall('.//programme'):
    start = prog.get('start', '')[:8]
    if start in dates:
        ch = prog.get('channel')
        title = prog.find('.//title').text if prog.find('.//title') is not None else ''
        if start not in programs_by_date:
            programs_by_date[start] = []
        programs_by_date[start].append((ch, title))

print("=== Programação EPG ===")
for date in dates:
    dt = datetime.strptime(date, '%Y%m%d')
    print(f"\n{dt.strftime('%d/%m/%Y')}:")
    if date in programs_by_date:
        for ch, title in programs_by_date[date][:5]:
            print(f"  {ch}: {title}")