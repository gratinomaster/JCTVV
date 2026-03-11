#!/usr/bin/env python3
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import time
import json
import os

options = Options()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-gpu")
options.add_argument("--window-size=1280,720")
options.add_argument("--disable-infobars")
options.add_argument("--disable-dev-shm-usage")

OUTPUT_FILE = "globo_epg_sp.xml"

CHANNELS = {
    "GloboSP.br": {
        "name": "Globo São Paulo",
        "url": "https://redeglobo.globo.com/sao-paulo/programacao/"
    },
    "eptv-campinas": {
        "name": "EPTV Campinas",
        "url": "https://redeglobo.globo.com/sp/eptv/programacao/"
    },
    "eptv-ribeirao": {
        "name": "EPTV Ribeirão Preto",
        "url": "https://redeglobo.globo.com/sp/eptv/programacao/"
    },
    "tv-tribuna": {
        "name": "TV Tribuna",
        "url": "https://redeglobo.globo.com/sp/tvtribuna/programacao/"
    },
    "tv-vanguarda": {
        "name": "TV Vanguarda",
        "url": "https://redeglobo.globo.com/sp/tvvanguarda/programacao/"
    },
    "tv-diario": {
        "name": "TV Diário",
        "url": "https://redeglobo.globo.com/sp/tvdiario/programacao/"
    },
}

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
}

def fetch_programation_with_selenium(url, channel_name):
    programs = []
    driver = None
    
    try:
        print(f"  Acessando: {channel_name}")
        driver = webdriver.Chrome(options=options)
        driver.get(url)
        
        time.sleep(5)
        
        program_items = driver.find_elements(By.CSS_SELECTOR, '.programation-grid__item, .programation-list__item, .program-card, article.program, [class*="program"], [class*="programacao"]')
        
        if not program_items:
            page_source = driver.page_source
            if 'application/ld+json' in page_source:
                try:
                    scripts = driver.find_elements(By.CSS_SELECTOR, 'script[type="application/ld+json"]')
                    for script in scripts:
                        data = json.loads(script.get_attribute('innerHTML'))
                        if isinstance(data, list):
                            for item in data:
                                if isinstance(item, dict):
                                    name = item.get('name', '')
                                    start = item.get('startDate', '') or item.get('partOfSeason', {}).get('startDate', '')
                                    if name and start:
                                        try:
                                            dt = datetime.fromisoformat(start.replace('Z', '-03:00'))
                                            programs.append({
                                                'time': dt.strftime("%H:%M"),
                                                'title': name
                                            })
                                        except:
                                            pass
                except Exception as e:
                    print(f"    Erro ao processar JSON-LD: {e}")
        
        for item in program_items:
            try:
                title_elem = item.find_elements(By.CSS_SELECTOR, 'h2, h3, span[class*="title"], [class*="title"]')
                time_elem = item.find_elements(By.CSS_SELECTOR, 'time, span[class*="time"], [class*="time"]')
                
                title = title_elem[0].text.strip() if title_elem else ""
                time_str = ""
                
                if time_elem:
                    time_attr = time_elem[0].get_attribute('datetime')
                    if time_attr:
                        try:
                            dt = datetime.fromisoformat(time_attr.replace('Z', '-03:00'))
                            time_str = dt.strftime("%H:%M")
                        except:
                            time_str = time_elem[0].text.strip()
                    else:
                        time_str = time_elem[0].text.strip()
                
                if title and time_str and time_str not in ["", ":"]:
                    programs.append({'time': time_str, 'title': title})
            except:
                continue
        
        if programs:
            print(f"    ✓ {len(programs)} programas encontrados")
            return programs
        
        print(f"    ⚠ Tentando método alternativo...")
        
        all_text = driver.find_elements(By.CSS_SELECTOR, 'body *')
        for elem in all_text:
            try:
                text = elem.text.strip()
                if text and ':' in text[:5] and len(text) < 100:
                    parts = text.split(':', 1)
                    if len(parts) == 2:
                        time_str = parts[0].strip()
                        title = parts[1].strip()
                        if time_str.replace(':', '').isdigit() and len(time_str) == 5:
                            programs.append({'time': time_str, 'title': title})
            except:
                continue
        
        if programs:
            print(f"    ✓ {len(programs)} programas encontrados (método alternativo)")
            return programs
            
    except Exception as e:
        print(f"    ✗ Erro: {e}")
    finally:
        if driver:
            driver.quit()
    
    return None

def get_generic_programation(channel_name):
    if 'CBN' in channel_name:
        return [
            {"time": "05:00", "title": "CBN No Ar"},
            {"time": "08:00", "title": "CBN Entrevista"},
            {"time": "09:00", "title": "CBN Dinheiro"},
            {"time": "10:00", "title": "CBN Tecnologia"},
            {"time": "11:00", "title": "CBN No Caminho"},
            {"time": "12:00", "title": "CBN Esportes"},
            {"time": "13:00", "title": "CBN No Ar"},
            {"time": "16:00", "title": "CBN Dinheiro"},
            {"time": "18:00", "title": "CBN Brasil"},
            {"time": "19:00", "title": "CBN No Ar"},
            {"time": "22:00", "title": "CBN Late Night"},
        ]
    
    return [
        {"time": "04:00", "title": "Hora 1"},
        {"time": "05:00", "title": "Globo"},
        {"time": "07:00", "title": "Bom Dia Brasil"},
        {"time": "09:00", "title": "Mais Você"},
        {"time": "10:00", "title": "Encontro com Patrícia Poeta"},
        {"time": "11:00", "title": "Jornal Hoje"},
        {"time": "12:00", "title": "SPTV 1ª Edição"},
        {"time": "13:00", "title": "Jornal da Globo"},
        {"time": "14:00", "title": "Novela das 14h"},
        {"time": "15:00", "title": "Vale a Pena Ver de Novo"},
        {"time": "17:00", "title": "SPTV 2ª Edição"},
        {"time": "18:00", "title": "Globo Rural"},
        {"time": "19:00", "title": "Jornal Nacional"},
        {"time": "20:00", "title": "Novela das 20h"},
        {"time": "21:00", "title": "Globo Especial"},
        {"time": "22:00", "title": "Fantástico"},
        {"time": "00:00", "title": "Globo Repórter"},
        {"time": "01:00", "title": "Combate"},
    ]

def fetch_api_programation(url, channel_name):
    try:
        channel_slug = channel_name.lower().replace(' ', '-').replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u')
        
        api_url = f"https://redeglobo.globo.com/{channel_slug}/programacao/data"
        
        response = requests.get(api_url, headers=headers, timeout=30)
        if response.status_code == 200:
            data = response.json()
            programs = []
            
            for day in data.get('dias', []):
                for program in day.get('programas', []):
                    hora = program.get('hora', '')
                    titulo = program.get('titulo', '')
                    if hora and titulo:
                        programs.append({'time': hora, 'title': titulo})
            
            if programs:
                print(f"    ✓ {len(programs)} programas da API")
                return programs
    except Exception as e:
        print(f"    API error: {e}")
    
    return None

def generate_epg_xml(programs_dict, output_file):
    root = ET.Element('tv')
    root.set('generator-info-name', 'Globo São Paulo EPG Generator')
    root.set('generated-date', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    root.set('source-url', 'https://redeglobo.globo.com/sao-paulo/programacao/')
    
    base_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    for tvg_id, channel_info in programs_dict.items():
        channel_elem = ET.SubElement(root, 'channel')
        channel_elem.set('id', tvg_id)
        
        display_name = ET.SubElement(channel_elem, 'display-name')
        display_name.set('lang', 'pt')
        display_name.text = channel_info['name']
        
        programs_list = channel_info.get('programs', [])
        
        if not programs_list:
            continue
        
        for day_offset in range(7):
            current_date = base_date + timedelta(days=day_offset)
            date_str = current_date.strftime("%Y%m%d")
            
            for i, prog in enumerate(programs_list):
                time_str = prog['time']
                title = prog['title']
                
                try:
                    start_time = f"{date_str}{time_str.replace(':', '')}0000 -0300"
                except:
                    start_time = f"{date_str}050000 -0300"
                
                if i + 1 < len(programs_list):
                    end_time_str = programs_list[i + 1]['time']
                else:
                    end_time_str = "04:00"
                
                end_date = current_date
                try:
                    if int(time_str.replace(':', '')) > int(end_time_str.replace(':', '')):
                        end_date = current_date + timedelta(days=1)
                except:
                    pass
                
                try:
                    end_time = f"{end_date.strftime('%Y%m%d')}{end_time_str.replace(':', '')}0000 -0300"
                except:
                    end_time = f"{end_date.strftime('%Y%m%d')}040000 -0300"
                
                prog_elem = ET.SubElement(root, 'programme')
                prog_elem.set('start', start_time)
                prog_elem.set('stop', end_time)
                prog_elem.set('channel', tvg_id)
                
                title_elem = ET.SubElement(prog_elem, 'title')
                title_elem.set('lang', 'pt')
                title_elem.text = title
    
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(output_file, encoding='UTF-8', xml_declaration=True)
    
    print(f"\n✓ Arquivo EPG gerado: {output_file}")
    print(f"  Canais: {len(programs_dict)}")
    print(f"  Total programas: {sum(len(p.get('programs', [])) for p in programs_dict.values())}")

def main():
    print("=" * 60)
    print("GLOBO SÃO PAULO EPG - Gerador de Programação")
    print("=" * 60)
    
    programs = {}
    
    for tvg_id, channel_info in CHANNELS.items():
        print(f"\nProcessando: {channel_info['name']}")
        
        programs_list = fetch_api_programation(channel_info['url'], channel_info['name'])
        
        if not programs_list:
            programs_list = fetch_programation_with_selenium(channel_info['url'], channel_info['name'])
        
        if programs_list:
            programs[tvg_id] = {
                'name': channel_info['name'],
                'programs': programs_list
            }
        else:
            print(f"  ⚠ Usando programação genérica")
            programs[tvg_id] = {
                'name': channel_info['name'],
                'programs': get_generic_programation(channel_info['name'])
            }
        
        time.sleep(1)
    
    print("\n[2] Gerando arquivo EPG XML...")
    generate_epg_xml(programs, OUTPUT_FILE)
    
    print("\n" + "=" * 60)
    print("Concluído!")
    print("=" * 60)
    print(f"\nExecute GLOBO.py para gerar a lista M3U com EPG configurado!")

if __name__ == "__main__":
    main()
