#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import json
import urllib.request
import gzip
import os
import time

LOCAL_EPG_REGIONAL_FILE = "globo_epg_regional.xml"

REGIONAL_CHANNELS = {
    "eptv-campinas": {
        "name": "EPTV Campinas",
        "url": "https://redeglobo.globo.com/sp/eptv/",
        "programacao_url": "https://redeglobo.globo.com/sp/eptv/programacao/"
    },
    "eptv-ribeirao": {
        "name": "EPTV Ribeirão Preto",
        "url": "https://redeglobo.globo.com/sp/eptv/",
        "programacao_url": "https://redeglobo.globo.com/sp/eptv/programacao/"
    },
    "rbs-porto-alegre": {
        "name": "RBS TV Porto Alegre",
        "url": "https://redeglobo.globo.com/rs/rbstvrs/",
        "programacao_url": "https://redeglobo.globo.com/rs/rbstvrs/programacao/"
    },
    "nsc-tv": {
        "name": "NSC TV",
        "url": "https://redeglobo.globo.com/sc/nsctv/",
        "programacao_url": "https://redeglobo.globo.com/sc/nsctv/programacao/"
    },
    "tv-verdes-mares": {
        "name": "TV Verdes Mares",
        "url": "https://redeglobo.globo.com/ce/tvverdesmares/",
        "programacao_url": "https://redeglobo.globo.com/ce/tvverdesmares/programacao/"
    },
    "tv-globo-ba": {
        "name": "TV Bahia",
        "url": "https://redeglobo.globo.com/ba/tvbahia/",
        "programacao_url": "https://redeglobo.globo.com/ba/tvbahia/programacao/"
    },
    "tv-globo-al": {
        "name": "TV Globo Alagoas",
        "url": "https://redeglobo.globo.com/al/tvgazetaal/",
        "programacao_url": "https://redeglobo.globo.com/al/tvgazetaal/programacao/"
    },
    "rede-amazonica": {
        "name": "Rede Amazônica",
        "url": "https://redeglobo.globo.com/am/redeamazonica/",
        "programacao_url": "https://redeglobo.globo.com/am/redeamazonica/programacao/"
    },
    "tv-liberal": {
        "name": "TV Liberal",
        "url": "https://redeglobo.globo.com/pa/tvliberal/",
        "programacao_url": "https://redeglobo.globo.com/pa/tvliberal/programacao/"
    },
    "tv-gazeta-es": {
        "name": "TV Gazeta ES",
        "url": "https://redeglobo.globo.com/es/tvgazetaes/",
        "programacao_url": "https://redeglobo.globo.com/es/tvgazetaes/programacao/"
    },
    "tv-integracao": {
        "name": "TV Integração",
        "url": "https://redeglobo.globo.com/mg/tvintegracao/",
        "programacao_url": "https://redeglobo.globo.com/mg/tvintegracao/programacao/"
    },
    "tv-vanguarda": {
        "name": "TV Vanguarda",
        "url": "https://redeglobo.globo.com/sp/tvvanguarda/",
        "programacao_url": "https://redeglobo.globo.com/sp/tvvanguarda/programacao/"
    },
    "tv-pantanal": {
        "name": "TV Pantanal",
        "url": "https://redeglobo.globo.com/ms/tvpantanal/",
        "programacao_url": "https://redeglobo.globo.com/ms/tvpantanal/programacao/"
    },
}

NATIONAL_PROGRAMS = {
    "tv-globo": [
        ["04:00", "Hora 1"],
        ["05:00", "Globo"],
        ["07:00", "Bom Dia Brasil"],
        ["09:00", "Mais Você"],
        ["10:00", "Encontro com Patrícia Poeta"],
        ["11:00", "Jornal Hoje"],
        ["12:00", "SPTV 1ª Edição"],
        ["13:00", "Jornal da Globo"],
        ["14:00", "Novela das 14h"],
        ["15:00", "Vale a Pena Ver de Novo"],
        ["17:00", "SPTV 2ª Edição"],
        ["18:00", "Globo Rural"],
        ["19:00", "Jornal Nacional"],
        ["20:00", "Novela das 20h"],
        ["21:00", "Globo Especial"],
        ["22:00", "Fantástico"],
        ["00:00", "Globo Repórter"],
        ["01:00", "Combate"],
    ],
    "globonews": [
        ["05:00", "GloboNews Noite"],
        ["07:00", "GloboNews Manhã"],
        ["09:00", "GloboNews 1ª Edição"],
        ["12:00", "GloboNews 2ª Edição"],
        ["15:00", "GloboNews 3ª Edição"],
        ["18:00", "Jornal das Dez"],
        ["20:00", "GloboNews Entrevista"],
        ["22:00", "GloboNews Dokument"],
        ["00:00", "GloboNews Noite"],
    ],
}

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
}

def fetch_page(url):
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"✗ Erro ao acessar {url}: {e}")
        return None

def parse_globo_programacao(html_content, channel_name):
    programs = []
    
    if not html_content:
        return None
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    program_items = soup.find_all('div', class_='programation-grid__item') or \
                    soup.find_all('li', class_='programation-list__item') or \
                    soup.find_all('div', class_='program-card') or \
                    soup.find_all('article', class_='program')
    
    if program_items:
        for item in program_items:
            title_elem = item.find('h3') or item.find('h2') or item.find('span', class_='programation-grid__title') or item.find('span', class_='program__title')
            time_elem = item.find('time') or item.find('span', class_='programation-grid__time') or item.find('span', class_='program__time')
            
            title = title_elem.get_text(strip=True) if title_elem else None
            time_str = time_elem.get('datetime') or time_elem.get_text(strip=True) if time_elem else None
            
            if title and time_str:
                try:
                    if 'T' in time_str:
                        dt = datetime.fromisoformat(time_str.replace('Z', '-03:00'))
                        time_str = dt.strftime("%H:%M")
                except:
                    pass
                
                if title and time_str:
                    programs.append([time_str, title])
        
        if programs:
            print(f"  ✓ {channel_name}: {len(programs)} programas encontrados")
            return programs
    
    script_tags = soup.find_all('script')
    for script in script_tags:
        if script.string and 'programation' in script.string.lower():
            try:
                if 'application/ld+json' in str(script):
                    data = json.loads(script.string)
                    if isinstance(data, list):
                        for item in data:
                            if item.get('@type') == 'TVEpisode':
                                start = item.get('partOfSeason', {}).get('startDate', '')
                                title = item.get('name', '')
                                if start and title:
                                    try:
                                        dt = datetime.fromisoformat(start.replace('Z', '-03:00'))
                                        time_str = dt.strftime("%H:%M")
                                        programs.append([time_str, title])
                                    except:
                                        pass
            except:
                pass
    
    return programs if programs else None

def parse_epg_br():
    url = "https://iptv-epg.org/files/epg-br.xml.gz"
    local_gz = "epg-br.xml.gz"
    local_xml = "epg-br.xml"
    
    try:
        print(f"Baixando EPG do iptv-epg.org...")
        urllib.request.urlretrieve(url, local_gz)
        
        with gzip.open(local_gz, 'rb') as f_in:
            with open(local_xml, 'wb') as f_out:
                f_out.write(f_in.read())
        
        print(f"✓ EPG iptv-epg.org baixado")
        return local_xml
    except Exception as e:
        print(f"✗ Erro ao baixar EPG iptv-epg.org: {e}")
        return None

def fetch_all_regional_programs():
    all_programs = {}
    
    print("\n=== Buscando programação regional da Globo ===")
    
    for tvg_id, channel_info in REGIONAL_CHANNELS.items():
        print(f"\nProcessando: {channel_info['name']} ({tvg_id})")
        
        html = fetch_page(channel_info['programacao_url'])
        
        if html:
            programs = parse_globo_programacao(html, channel_info['name'])
            if programs:
                all_programs[tvg_id] = {
                    'name': channel_info['name'],
                    'programs': programs
                }
                continue
        
        print(f"  ⚠ Usando programação genérica para {channel_info['name']}")
        all_programs[tvg_id] = {
            'name': channel_info['name'],
            'programs': get_generic_programation(channel_info['name'])
        }
        
        time.sleep(1)
    
    return all_programs

def get_generic_programation(channel_name):
    hour = datetime.now().hour
    
    if 'CBN' in channel_name:
        return [
            ["05:00", "CBN no Ar:00", ""],
            ["08CBN Entrevista"],
            ["09:00", "CBN Dinheiro"],
            ["10:00", "CBN Tecnologia"],
            ["11:00", "CBN No Caminho"],
            ["12:00", "CBN Esportes"],
            ["13:00", "CBN No Ar"],
            ["16:00", "CBN Dinheiro"],
            ["18:00", "CBN Brasil"],
            ["19:00", "CBN No Ar"],
            ["22:00", "CBN Late Night"],
        ]
    
    if 'EPTV' in channel_name or 'TV' in channel_name:
        return [
            ["04:00", "Hora 1"],
            ["05:00", "Globo"],
            ["07:00", "Bom Dia Cidade"],
            ["09:00", "Mais Você"],
            ["10:00", "Encontro"],
            ["11:00", "Jornal Hoje"],
            ["12:00", "Bom Dia Cidade"],
            ["13:00", "Jornal da Globo"],
            ["14:00", "Novela"],
            ["15:00", "Vale a Pena Ver de Novo"],
            ["17:00", "Jornal da Globo"],
            ["18:00", "Globo Rural"],
            ["19:00", "Jornal Nacional"],
            ["20:00", "Novela das 20h"],
            ["21:00", "Globo Rural"],
            ["22:00", "Jornal da Globo"],
            ["23:00", "Globo"],
        ]
    
    return [
        ["05:00", "Globo"],
        ["07:00", "Bom Dia Brasil"],
        ["09:00", "Mais Você"],
        ["11:00", "Jornal Hoje"],
        ["12:00", "Globo"],
        ["13:00", "Jornal da Globo"],
        ["14:00", "Novela"],
        ["15:00", "Vale a Pena Ver de Novo"],
        ["17:00", "Globo"],
        ["19:00", "Jornal Nacional"],
        ["20:00", "Novela das 20h"],
        ["21:00", "Globo Rural"],
        ["22:00", "Globo"],
    ]

def generate_epg_xml(programs_dict, output_file):
    root = ET.Element('tv')
    root.set('generator-info-name', 'Globo EPG Generator - Regional')
    root.set('generated-date', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    root.set('source-url', 'https://redeglobo.globo.com')
    
    base_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    for tvg_id, program_info in programs_dict.items():
        channel_elem = ET.SubElement(root, 'channel')
        channel_elem.set('id', tvg_id)
        
        display_name = ET.SubElement(channel_elem, 'display-name')
        display_name.set('lang', 'pt')
        display_name.text = program_info['name']
        
        icon_elem = ET.SubElement(channel_elem, 'icon')
        icon_elem.set('src', f"https://s3.glbimg.com/v1/gla3/c40a7726c0a14c084f1df0cb8e8d6e1c/{tvg_id}.png")
        
        programs_list = program_info.get('programs', [])
        
        for day_offset in range(3):
            current_date = base_date + timedelta(days=day_offset)
            date_str = current_date.strftime("%Y%m%d")
            
            for i, prog in enumerate(programs_list):
                time_str = prog[0]
                title = prog[1]
                
                try:
                    start_time = f"{date_str}{time_str.replace(':', '')}0000 -0300"
                except:
                    start_time = f"{date_str}050000 -0300"
                
                if i + 1 < len(programs_list):
                    end_time_str = programs_list[i + 1][0]
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
    print(f"  Programas: {sum(len(p.get('programs', [])) for p in programs_dict.values())}")

def main():
    print("=" * 60)
    print("GLOBO EPG - Gerador de Programação Regional")
    print("=" * 60)
    
    print("\n[1] Buscando programação das emissoras regionais...")
    programs = fetch_all_regional_programs()
    
    if not programs:
        print("\n⚠ Não foi possível buscar a programação online.")
        print("   Usando programação genérica...")
        for tvg_id, channel_info in REGIONAL_CHANNELS.items():
            programs[tvg_id] = {
                'name': channel_info['name'],
                'programs': get_generic_programation(channel_info['name'])
            }
    
    print("\n[2] Gerando arquivo EPG XML...")
    generate_epg_xml(programs, LOCAL_EPG_REGIONAL_FILE)
    
    print("\n[3] Verificando EPG nacional (iptv-epg.org)...")
    local_xml = parse_epg_br()
    if local_xml:
        print(f"   EPG nacional disponível em: {local_xml}")
    
    print("\n" + "=" * 60)
    print("Concluído!")
    print("=" * 60)
    print(f"\nArquivos gerados:")
    print(f"  - EPG Regional: {LOCAL_EPG_REGIONAL_FILE}")
    if local_xml:
        print(f"  - EPG Nacional:  {local_xml}")
    print(f"\nExecute GLOBO.py para gerar a lista M3U com EPG configurado!")

if __name__ == "__main__":
    main()
