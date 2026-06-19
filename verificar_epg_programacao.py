#!/usr/bin/env python3
"""Verifica se o EPG tem programacao para hoje, amanha e depois de amanha."""
import xml.etree.ElementTree as ET
import datetime
import sys

EPG_FILE = "lista5_epg_atualizado.xml"
today = datetime.datetime.now()
dates = [
    today.strftime("%Y%m%d"),
    (today + datetime.timedelta(days=1)).strftime("%Y%m%d"),
    (today + datetime.timedelta(days=2)).strftime("%Y%m%d"),
]

tree = ET.parse(EPG_FILE)
root = tree.getroot()

print(f"EPG: {EPG_FILE}")
print(f"Data atual: {today.strftime('%Y-%m-%d')}")
print(f"Datas para verificar: {', '.join(dates)}")
print()

all_ok = True
for ch in root.findall('channel'):
    ch_id = ch.get('id')
    name = ch.find('display-name').text if ch.find('display-name') is not None else ch_id
    print(f"Canal: {name} ({ch_id})")
    for d in dates:
        found = False
        for prog in root.findall('programme'):
            if prog.get('channel') == ch_id and prog.get('start', '').startswith(d):
                title = prog.find('title').text if prog.find('title') is not None else '?'
                start = prog.get('start', '')
                stop = prog.get('stop', '')
                print(f"  {d}: {start[9:13]}h-{stop[9:13]}h -> {title}")
                found = True
                break
        if not found:
            print(f"  {d}: SEM PROGRAMACAO!")
            all_ok = False
    print()

if all_ok:
    print("RESULTADO: EPG OK - Todos os canais tem programacao para hoje, amanha e depois!")
else:
    print("RESULTADO: EPG INCOMPLETO - Faltam dados para algumas datas")
    sys.exit(1)
