#!/usr/bin/env python3
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

OUTPUT_FILE = "globo_epg_regional.xml"

CHANNELS = {
    "GloboSP.br": {
        "name": "Globo São Paulo",
        "programs": [
            ["04:00", "Hora 1"],
            ["05:00", "Globo"],
            ["07:00", "Bom Dia Brasil"],
            ["09:00", "Mais Você"],
            ["10:00", "Encontro com Patrícia Poeta"],
            ["11:00", "Jornal Hoje"],
            ["12:00", "SPTV 1ª Edição"],
            ["13:00", "Jornal da Globo"],
            ["14:00", "Êta Mundo Melhor!"],
            ["15:00", "Dona de Mim"],
            ["17:00", "SPTV 2ª Edição"],
            ["18:00", "Globo Rural"],
            ["19:00", "Jornal Nacional"],
            ["20:00", "Três Graças"],
            ["21:00", "Globo Especial"],
            ["22:00", "Fantástico"],
            ["00:00", "Globo Repórter"],
            ["01:00", "Combate"],
        ]
    },
    "eptv-campinas": {
        "name": "EPTV Campinas",
        "programs": [
            ["04:00", "Hora 1"],
            ["05:00", "Globo"],
            ["07:00", "Bom Dia Cidade"],
            ["09:00", "Mais Você"],
            ["10:00", "Encontro"],
            ["11:00", "Jornal Hoje"],
            ["12:00", "EPTV 1ª Edição"],
            ["13:00", "Jornal da Globo"],
            ["14:00", "Êta Mundo Melhor!"],
            ["15:00", "Dona de Mim"],
            ["17:00", "EPTV 2ª Edição"],
            ["18:00", "Globo Rural"],
            ["19:00", "Jornal Nacional"],
            ["20:00", "Três Graças"],
            ["21:00", "Globo Rural"],
            ["22:00", "Jornal da Globo"],
            ["23:00", "Fantástico"],
        ]
    },
    "eptv-ribeirao": {
        "name": "EPTV Ribeirão Preto",
        "programs": [
            ["04:00", "Hora 1"],
            ["05:00", "Globo"],
            ["07:00", "Bom Dia Cidade"],
            ["09:00", "Mais Você"],
            ["10:00", "Encontro"],
            ["11:00", "Jornal Hoje"],
            ["12:00", "EPTV 1ª Edição"],
            ["13:00", "Jornal da Globo"],
            ["14:00", "Êta Mundo Melhor!"],
            ["15:00", "Dona de Mim"],
            ["17:00", "EPTV 2ª Edição"],
            ["18:00", "Globo Rural"],
            ["19:00", "Jornal Nacional"],
            ["20:00", "Três Graças"],
            ["21:00", "Globo Rural"],
            ["22:00", "Jornal da Globo"],
            ["23:00", "Fantástico"],
        ]
    },
    "rbs-tv": {
        "name": "RBS TV Porto Alegre",
        "programs": [
            ["04:00", "Hora 1"],
            ["05:00", "Globo"],
            ["07:00", "Bom Dia Rio Grande"],
            ["09:00", "Mais Você"],
            ["10:00", "Encontro"],
            ["11:00", "Jornal Hoje"],
            ["12:00", "RBS TV 1ª Edição"],
            ["13:00", "Jornal da Globo"],
            ["14:00", "Êta Mundo Melhor!"],
            ["15:00", "Dona de Mim"],
            ["17:00", "RBS TV 2ª Edição"],
            ["18:00", "Globo Rural"],
            ["19:00", "Jornal Nacional"],
            ["20:00", "Três Graças"],
            ["21:00", "Globo Rural"],
            ["22:00", "Jornal da Globo"],
            ["23:00", "Fantástico"],
        ]
    },
    "nsc-tv": {
        "name": "NSC TV",
        "programs": [
            ["04:00", "Hora 1"],
            ["05:00", "Globo"],
            ["07:00", "Bom Dia Santa Catarina"],
            ["09:00", "Mais Você"],
            ["10:00", "Encontro"],
            ["11:00", "Jornal Hoje"],
            ["12:00", "NSC TV 1ª Edição"],
            ["13:00", "Jornal da Globo"],
            ["14:00", "Êta Mundo Melhor!"],
            ["15:00", "Dona de Mim"],
            ["17:00", "NSC TV 2ª Edição"],
            ["18:00", "Globo Rural"],
            ["19:00", "Jornal Nacional"],
            ["20:00", "Três Graças"],
            ["21:00", "Globo Rural"],
            ["22:00", "Jornal da Globo"],
            ["23:00", "Fantástico"],
        ]
    },
    "tv-verdes-mares": {
        "name": "TV Verdes Mares",
        "programs": [
            ["04:00", "Hora 1"],
            ["05:00", "Globo"],
            ["07:00", "Bom Dia Ceará"],
            ["09:00", "Mais Você"],
            ["10:00", "Encontro"],
            ["11:00", "Jornal Hoje"],
            ["12:00", "TV Verdes Mares 1ª Edição"],
            ["13:00", "Jornal da Globo"],
            ["14:00", "Êta Mundo Melhor!"],
            ["15:00", "Dona de Mim"],
            ["17:00", "TV Verdes Mares 2ª Edição"],
            ["18:00", "Globo Rural"],
            ["19:00", "Jornal Nacional"],
            ["20:00", "Três Graças"],
            ["21:00", "Globo Rural"],
            ["22:00", "Jornal da Globo"],
            ["23:00", "Fantástico"],
        ]
    },
    "tv-globo-ba": {
        "name": "TV Bahia",
        "programs": [
            ["04:00", "Hora 1"],
            ["05:00", "Globo"],
            ["07:00", "Bom Dia Bahia"],
            ["09:00", "Mais Você"],
            ["10:00", "Encontro"],
            ["11:00", "Jornal Hoje"],
            ["12:00", "Bahia Rural"],
            ["13:00", "Jornal da Globo"],
            ["14:00", "Êta Mundo Melhor!"],
            ["15:00", "Dona de Mim"],
            ["17:00", "Jornal da Globo"],
            ["18:00", "Globo Rural"],
            ["19:00", "Jornal Nacional"],
            ["20:00", "Três Graças"],
            ["21:00", "Globo Rural"],
            ["22:00", "Jornal da Globo"],
            ["23:00", "Fantástico"],
        ]
    },
    "tv-globo-al": {
        "name": "TV Gazeta de Alagoas",
        "programs": [
            ["04:00", "Hora 1"],
            ["05:00", "Globo"],
            ["07:00", "Bom Dia Alagoas"],
            ["09:00", "Mais Você"],
            ["10:00", "Encontro"],
            ["11:00", "Jornal Hoje"],
            ["12:00", "TV Gazeta 1ª Edição"],
            ["13:00", "Jornal da Globo"],
            ["14:00", "Êta Mundo Melhor!"],
            ["15:00", "Dona de Mim"],
            ["17:00", "TV Gazeta 2ª Edição"],
            ["18:00", "Globo Rural"],
            ["19:00", "Jornal Nacional"],
            ["20:00", "Três Graças"],
            ["21:00", "Globo Rural"],
            ["22:00", "Jornal da Globo"],
            ["23:00", "Fantástico"],
        ]
    },
    "rede-amazonica": {
        "name": "Rede Amazônica",
        "programs": [
            ["04:00", "Hora 1"],
            ["05:00", "Globo"],
            ["07:00", "Bom Dia Amazônia"],
            ["09:00", "Mais Você"],
            ["10:00", "Encontro"],
            ["11:00", "Jornal Hoje"],
            ["12:00", "Rede Amazônica 1ª Edição"],
            ["13:00", "Jornal da Globo"],
            ["14:00", "Êta Mundo Melhor!"],
            ["15:00", "Dona de Mim"],
            ["17:00", "Rede Amazônica 2ª Edição"],
            ["18:00", "Globo Rural"],
            ["19:00", "Jornal Nacional"],
            ["20:00", "Três Graças"],
            ["21:00", "Globo Rural"],
            ["22:00", "Jornal da Globo"],
            ["23:00", "Fantástico"],
        ]
    },
    "tv-liberal": {
        "name": "TV Liberal",
        "programs": [
            ["04:00", "Hora 1"],
            ["05:00", "Globo"],
            ["07:00", "Bom Dia Pará"],
            ["09:00", "Mais Você"],
            ["10:00", "Encontro"],
            ["11:00", "Jornal Hoje"],
            ["12:00", "TV Liberal 1ª Edição"],
            ["13:00", "Jornal da Globo"],
            ["14:00", "Êta Mundo Melhor!"],
            ["15:00", "Dona de Mim"],
            ["17:00", "TV Liberal 2ª Edição"],
            ["18:00", "Globo Rural"],
            ["19:00", "Jornal Nacional"],
            ["20:00", "Três Graças"],
            ["21:00", "Globo Rural"],
            ["22:00", "Jornal da Globo"],
            ["23:00", "Fantástico"],
        ]
    },
    "tv-gazeta-es": {
        "name": "TV Gazeta ES",
        "programs": [
            ["04:00", "Hora 1"],
            ["05:00", "Globo"],
            ["07:00", "Bom Dia Espírito Santo"],
            ["09:00", "Mais Você"],
            ["10:00", "Encontro"],
            ["11:00", "Jornal Hoje"],
            ["12:00", "TV Gazeta 1ª Edição"],
            ["13:00", "Jornal da Globo"],
            ["14:00", "Êta Mundo Melhor!"],
            ["15:00", "Dona de Mim"],
            ["17:00", "TV Gazeta 2ª Edição"],
            ["18:00", "Globo Rural"],
            ["19:00", "Jornal Nacional"],
            ["20:00", "Três Graças"],
            ["21:00", "Globo Rural"],
            ["22:00", "Jornal da Globo"],
            ["23:00", "Fantástico"],
        ]
    },
    "tv-integracao": {
        "name": "TV Integração",
        "programs": [
            ["04:00", "Hora 1"],
            ["05:00", "Globo"],
            ["07:00", "Bom Dia Minas"],
            ["09:00", "Mais Você"],
            ["10:00", "Encontro"],
            ["11:00", "Jornal Hoje"],
            ["12:00", "MGTV 1ª Edição"],
            ["13:00", "Jornal da Globo"],
            ["14:00", "Êta Mundo Melhor!"],
            ["15:00", "Dona de Mim"],
            ["17:00", "MGTV 2ª Edição"],
            ["18:00", "Globo Rural"],
            ["19:00", "Jornal Nacional"],
            ["20:00", "Três Graças"],
            ["21:00", "Globo Rural"],
            ["22:00", "Jornal da Globo"],
            ["23:00", "Fantástico"],
        ]
    },
    "tv-pantanal": {
        "name": "TV Pantanal",
        "programs": [
            ["04:00", "Hora 1"],
            ["05:00", "Globo"],
            ["07:00", "Bom Dia MS"],
            ["09:00", "Mais Você"],
            ["10:00", "Encontro"],
            ["11:00", "Jornal Hoje"],
            ["12:00", "TV Pantanal 1ª Edição"],
            ["13:00", "Jornal da Globo"],
            ["14:00", "Êta Mundo Melhor!"],
            ["15:00", "Dona de Mim"],
            ["17:00", "TV Pantanal 2ª Edição"],
            ["18:00", "Globo Rural"],
            ["19:00", "Jornal Nacional"],
            ["20:00", "Três Graças"],
            ["21:00", "Globo Rural"],
            ["22:00", "Jornal da Globo"],
            ["23:00", "Fantástico"],
        ]
    },
    "globonews": {
        "name": "GloboNews",
        "programs": [
            ["05:00", "GloboNews Noite"],
            ["07:00", "GloboNews Manhã"],
            ["09:00", "GloboNews 1ª Edição"],
            ["12:00", "GloboNews 2ª Edição"],
            ["15:00", "GloboNews 3ª Edição"],
            ["18:00", "Jornal das Dez"],
            ["20:00", "GloboNews Entrevista"],
            ["22:00", "GloboNews Dokument"],
            ["00:00", "GloboNews Noite"],
        ]
    },
    "cbn-sp": {
        "name": "CBN São Paulo",
        "programs": [
            ["05:00", "CBN No Ar"],
            ["08:00", "CBN Entrevista"],
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
    },
    "cbn-rj": {
        "name": "CBN Rio de Janeiro",
        "programs": [
            ["05:00", "CBN No Ar"],
            ["08:00", "CBN Entrevista"],
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
    },
}

def generate_epg():
    root = ET.Element('tv')
    root.set('generator-info-name', 'Globo EPG Generator - Regional')
    root.set('generated-date', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    root.set('source-url', 'https://redeglobo.globo.com')
    
    base_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    for tvg_id, channel_info in CHANNELS.items():
        channel_elem = ET.SubElement(root, 'channel')
        channel_elem.set('id', tvg_id)
        
        display_name = ET.SubElement(channel_elem, 'display-name')
        display_name.set('lang', 'pt')
        display_name.text = channel_info['name']
        
        programs_list = channel_info['programs']
        
        for day_offset in range(7):
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
    tree.write(OUTPUT_FILE, encoding='UTF-8', xml_declaration=True)
    
    print(f"✓ Arquivo EPG gerado: {OUTPUT_FILE}")
    print(f"  Canais: {len(CHANNELS)}")
    print(f"  Programas por canal: ~18")
    print(f"  Dias de programação: 7")

if __name__ == "__main__":
    generate_epg()
