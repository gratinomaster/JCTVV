#!/usr/bin/env python3
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import re
import sys
import os

OUTPUT_FILE = "globo_epg.xml"
IMPRENSA_URL = "https://imprensa.globo.com/programacao-semanal/grade-de-programacao/"

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
}

def fetch_imprensa_programation():
    print("Buscando programacao no site Globo Imposto...")
    
    try:
        response = requests.get(IMPRENSA_URL, headers=headers, timeout=30)
        response.raise_for_status()
        
        html = response.text
        
        match = re.search(r'<div id="1052" class="tabcontent"[^>]*>(.+?)</div>\s*</section>', html, re.DOTALL)
        if not match:
            print("Nao encontrou o conteudo da programacao")
            return None
        
        content = match.group(1)
        
        programs = []
        current_date = None
        
        lines = content.split('<div>')
        for line in lines:
            line = line.strip()
            if not line or '&nbsp;' in line:
                continue
            
            line = re.sub(r'<[^>]+>', '', line)
            line = line.strip()
            
            if not line:
                continue
            
            date_match = re.match(r'^(\w+), (\d{2})/(\d{2})/(\d{4})$', line)
            if date_match:
                day = int(date_match.group(2))
                month = int(date_match.group(3))
                year = int(date_match.group(4))
                try:
                    current_date = datetime(year, month, day)
                except:
                    current_date = None
                continue
            
            if current_date:
                time_match = re.match(r'^(\d{2}):(\d{2})\s+(.+)$', line)
                if time_match:
                    hour, minute, title = time_match.groups()
                    time_str = f"{hour}:{minute}"
                    
                    title = title.strip()
                    title = title.replace('&amp;', '&')
                    
                    if title:
                        programs.append({
                            'date': current_date,
                            'time': time_str,
                            'title': title
                        })
        
        if programs:
            print(f"✓ {len(programs)} programas encontrados")
            return programs
        
    except Exception as e:
        print(f"Erro: {e}")
    
    return None

def generate_epg_xml(programs, output_file):
    root = ET.Element('tv')
    root.set('generator-info-name', 'Globo EPG Generator - Globo Imposto')
    root.set('generated-date', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    root.set('source-url', IMPRENSA_URL)
    
    channel_ids = {
        "GloboSP.br": "Globo Sao Paulo",
        "globonews": "GloboNews",
        "cbn-sp": "CBN Sao Paulo",
    }
    
    for tvg_id, channel_name in channel_ids.items():
        channel_elem = ET.SubElement(root, 'channel')
        channel_elem.set('id', tvg_id)
        
        display_name = ET.SubElement(channel_elem, 'display-name')
        display_name.set('lang', 'pt')
        display_name.text = channel_name
    
    unique_programs = []
    seen = set()
    for p in programs:
        key = (p['date'].strftime('%Y%m%d'), p['time'], p['title'])
        if key not in seen:
            seen.add(key)
            unique_programs.append(p)
    
    programs = unique_programs
    
    for tvg_id, channel_name in channel_ids.items():
        date_programs = {}
        
        for prog in programs:
            date_key = prog['date'].strftime('%Y%m%d')
            if date_key not in date_programs:
                date_programs[date_key] = []
            date_programs[date_key].append(prog)
        
        for date_str, day_programs in date_programs.items():
            day_programs.sort(key=lambda x: x['time'])
            
            for i, prog in enumerate(day_programs):
                try:
                    start_datetime = prog['date'].strftime('%Y%m%d') + prog['time'].replace(':', '') + '00 -0300'
                except:
                    continue
                
                if i + 1 < len(day_programs):
                    end_time = day_programs[i + 1]['time']
                    end_date = prog['date']
                else:
                    end_time = "04:00"
                    end_date = prog['date'] + timedelta(days=1)
                
                try:
                    end_datetime = end_date.strftime('%Y%m%d') + end_time.replace(':', '') + '00 -0300'
                except:
                    end_datetime = prog['date'].strftime('%Y%m%d') + '040000 -0300'
                
                prog_elem = ET.SubElement(root, 'programme')
                prog_elem.set('start', start_datetime)
                prog_elem.set('stop', end_datetime)
                prog_elem.set('channel', tvg_id)
                
                title_elem = ET.SubElement(prog_elem, 'title')
                title_elem.set('lang', 'pt')
                title_elem.text = prog['title']
    
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(output_file, encoding='UTF-8', xml_declaration=True)
    
    print(f"\n✓ Arquivo EPG gerado: {output_file}")

def main():
    print("=" * 60)
    print("GLOBO EPG GENERATOR - Globo Imposto")
    print("=" * 60)
    
    programs = fetch_imprensa_programation()
    
    if programs:
        generate_epg_xml(programs, OUTPUT_FILE)
    else:
        print("✗ Sem programacao disponivel")
        return 1
    
    print("\nConcluido!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
