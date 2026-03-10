from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time
import concurrent.futures
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
from xml.dom import minidom

import json

options = Options()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-gpu")
options.add_argument("--window-size=1280,720")
options.add_argument("--disable-infobars")

LOCAL_EPG_FILE = "globo_epg.xml"
LOCAL_PROGRAMS_FILE = "globo_programs.json"

CHANNEL_TVG_IDS = {
    "globoplay.globo.com/v/4613774": "TVGlobo",
    "globoplay.globo.com/ao-vivo/7689934": "TVGlobo",
    "globoplay.globo.com/ao-vivo/7690141": "TVGlobo",
    "globoplay.globo.com/ao-vivo/7813174": "TVGlobo",
    "globoplay.globo.com/ao-vivo/7813173": "TVGlobo",
    "globoplay.globo.com/v/12749215": "TVGlobo",
    "globoplay.globo.com/v/1328766": "TVGlobo",
    "globoplay.globo.com/v/1467373": "TVGlobo",
    "globoplay.globo.com/v/4064559": "TVGlobo",
    "globoplay.globo.com/v/5472979": "TVGlobo",
    "globoplay.globo.com/v/992055": "TVGlobo",
    "globoplay.globo.com/v/602497": "TVGlobo",
    "globoplay.globo.com/v/8713568": "TVGlobo",
    "g1.globo.com/sp/campinas-regiao/ao-vivo/eptv-1-campinas": "EPTV1Campinas",
    "globoplay.globo.com/ao-vivo/14164032": "TVAlagoas",
    "globoplay.globo.com/ao-vivo/2134039": "TVBahia",
    "g1.globo.com/rr/roraima": "TVRural",
    "g1.globo.com/sp/ribeirao-preto-franca/ao-vivo/bom-dia-cidade": "BomDiaCidadeRP",
    "g1.globo.com/sp/ribeirao-preto-franca/ao-vivo/eptv1": "EPTV1Ribeirao",
    "g1.globo.com/sp/ribeirao-preto-franca/ao-vivo/eptv-2": "EPTV2Ribeirao",
    "g1.globo.com/pe/petrolina-regiao/ao-vivo/gr2": "GR2Petrolina",
    "g1.globo.com/ap/ao-vivo/bdap": "BDAP",
    "globoplay.globo.com/v/2135579": "RBSPortoAlegre",
    "globoplay.globo.com/v/6120663": "G1RS",
    "globoplay.globo.com/v/2145544": "NSCTV",
    "globoplay.globo.com/ao-vivo/10865071": "TVVanguarda",
    "globoplay.globo.com/v/4039160": "TVVerdesMares",
    "globoplay.globo.com/v/6329086": "GloboEsporteBA",
    "globoplay.globo.com/v/11999480": "TVGazetaES",
    "g1.globo.com/al/alagoas/ao-vivo/assista-aos-telejornais-da-tv-gazeta": "TVGazetaAlagoas",
    "globoplay.globo.com/ao-vivo/3667427": "TVIntegração",
    "globoplay.globo.com/v/4218681": "TVIntegração",
    "globoplay.globo.com/v/12945385": "TVIntegração",
    "globoplay.globo.com/v/3065772": "TVPantanal",
    "g1.globo.com/am/amazonas/ao-vivo/assista-aos-telejornais-da-rede-amazonica": "RedeAmazonica",
    "globoplay.globo.com/v/2923579": "RedeAmazonica",
    "globoplay.globo.com/v/2923546": "RedeAmazonica",
    "globoplay.globo.com/v/2168377": "TVLiberal",
    "globoplay.globo.com/v/10747444": "CBNSaoPaulo",
    "globoplay.globo.com/v/10740500": "CBNRio",
}

DEFAULT_PROGRAM = {
    "name": "Programação Globo",
    "programs": [
        ["05:00", "Globo"],
        ["07:00", "Globo"],
        ["09:00", "Globo"],
        ["11:00", "Jornal Hoje"],
        ["12:00", "Globo"],
        ["13:00", "Novela"],
        ["15:00", "Vale a Pena Ver de Novo"],
        ["17:00", "Globo"],
        ["19:00", "Jornal Nacional"],
        ["20:00", "Novela das 8"],
        ["21:00", "Globo Rural"],
        ["22:00", "Globo"],
        ["00:00", "Jornal da Globo"],
    ]
}

def load_channel_programs():
    try:
        with open(LOCAL_PROGRAMS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Arquivo {LOCAL_PROGRAMS_FILE} não encontrado. Usando programa padrão.")
        return {}

def get_tvg_id(url):
    for key, tvg_id in CHANNEL_TVG_IDS.items():
        if key in url:
            return tvg_id
    return "TVGlobo"

def generate_epg_xml():
    root = ET.Element('tv')
    root.set('generator-info-name', 'Globo EPG Generator')
    
    base_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    channel_data = {}
    for url in globoplay_urls:
        tvg_id = get_tvg_id(url)
        if tvg_id not in channel_data:
            channel_data[tvg_id] = True
    
    CHANNEL_PROGRAMS = load_channel_programs()
    
    for tvg_id in channel_data.keys():
        channel_elem = ET.SubElement(root, 'channel')
        channel_elem.set('id', tvg_id)
        
        display_name = ET.SubElement(channel_elem, 'display-name')
        program_info = CHANNEL_PROGRAMS.get(tvg_id, DEFAULT_PROGRAM)
        display_name.text = program_info['name']
    
    for tvg_id in channel_data.keys():
        program_info = CHANNEL_PROGRAMS.get(tvg_id, DEFAULT_PROGRAM)
        programs_list = program_info['programs']
        
        for day_offset in range(3):
            current_date = base_date + timedelta(days=day_offset)
            date_str = current_date.strftime("%Y%m%d")
            
            for i, prog in enumerate(programs_list):
                time_str = prog[0]
                title = prog[1]
                start_time = f"{date_str}{time_str.replace(':', '')}0000 -0300"
                
                if i + 1 < len(programs_list):
                    end_time_str = programs_list[i + 1][0]
                else:
                    end_time_str = "04:00"
                
                end_date = current_date
                if int(time_str.replace(':', '')) > int(end_time_str.replace(':', '')):
                    end_date = current_date + timedelta(days=1)
                
                end_time = f"{end_date.strftime('%Y%m%d')}{end_time_str.replace(':', '')}0000 -0300"
                
                prog_elem = ET.SubElement(root, 'programme')
                prog_elem.set('start', start_time)
                prog_elem.set('stop', end_time)
                prog_elem.set('channel', tvg_id)
                
                title_elem = ET.SubElement(prog_elem, 'title')
                title_elem.text = title
    
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(LOCAL_EPG_FILE, encoding='UTF-8', xml_declaration=True)
    print(f"✓ Arquivo EPG local gerado: {LOCAL_EPG_FILE}")

# URLs dos vídeos Globoplay e G1 ao vivo
globoplay_urls = [
    "https://globoplay.globo.com/v/4613774/",
    "https://globoplay.globo.com/ao-vivo/7689934/",
    "https://globoplay.globo.com/ao-vivo/7690141/",
    "https://globoplay.globo.com/ao-vivo/7813173/",
    "https://g1.globo.com/sp/campinas-regiao/ao-vivo/eptv-1-campinas-ao-vivo.ghtml",
    "https://globoplay.globo.com/ao-vivo/14164032",
    "https://globoplay.globo.com/ao-vivo/2134039/",
    "https://globoplay.globo.com/v/12749215/",
    "https://g1.globo.com/rr/roraima/video/ao-vivo-assista-o-jornal-de-roraima-1a-edicao-2923545-1739458038240.ghtml",
    "https://g1.globo.com/sp/ribeirao-preto-franca/ao-vivo/bom-dia-cidade-ribeirao-preto.ghtml",
    "https://g1.globo.com/sp/ribeirao-preto-franca/ao-vivo/eptv1.ghtml",
    "https://g1.globo.com/sp/ribeirao-preto-franca/ao-vivo/eptv-2-ribeirao-e-franca-ao-vivo.ghtml",
    "https://g1.globo.com/pe/petrolina-regiao/ao-vivo/ao-vivo-assista-ao-gr2.ghtml",
    "https://g1.globo.com/ap/ao-vivo/assista-ao-bdap-desta-sexta-feira-7.ghtml",
    "https://globoplay.globo.com/v/1328766/",
    "https://globoplay.globo.com/v/1467373/",
    "https://globoplay.globo.com/v/4064559/",
    "https://globoplay.globo.com/v/5472979/",
    "https://globoplay.globo.com/v/2135579/",
    "https://globoplay.globo.com/v/5472979/",
    "https://globoplay.globo.com/v/6120663/",
    "https://globoplay.globo.com/v/2145544/",
    "https://globoplay.globo.com/ao-vivo/10865071/",
    "https://globoplay.globo.com/v/4039160/",
    "https://globoplay.globo.com/v/6329086/",
    "https://globoplay.globo.com/v/11999480/",
    "https://g1.globo.com/al/alagoas/ao-vivo/assista-aos-telejornais-da-tv-gazeta-de-alagoas.ghtml",
    "https://globoplay.globo.com/ao-vivo/3667427/",
    "https://globoplay.globo.com/v/4218681/",
    "https://globoplay.globo.com/v/12945385/",
    "https://globoplay.globo.com/v/3065772/",
    "https://globoplay.globo.com/v/2923579/",
    "https://g1.globo.com/am/amazonas/ao-vivo/assista-aos-telejornais-da-rede-amazonica.ghtml",
    "https://globoplay.globo.com/v/2923546/",
    "https://globoplay.globo.com/v/2168377/",
    "https://globoplay.globo.com/v/992055/",
    "https://globoplay.globo.com/v/602497/",
    "https://globoplay.globo.com/v/8713568/",
    "https://globoplay.globo.com/v/10747444/",
    "https://globoplay.globo.com/v/10740500/",
]

def extract_globoplay_data(url):
    driver = webdriver.Chrome(options=options)
    driver.get(url)
    
    try:
        try:
            play_button = driver.find_element(By.CSS_SELECTOR, "button.poster__play-wrapper")
            if play_button:
                play_button.click()
                time.sleep(20)
                print(f"Botão de play clicado para: {url}")
        except Exception as e:
            print(f"Botão de play não encontrado (esperado para G1 ao vivo): {e}")
    except Exception as e:
        print(f"Erro ao processar botão de reprodução: {e}")

    time.sleep(60)
    
    title = driver.title
    
    log_entries = driver.execute_script("return window.performance.getEntriesByType('resource');")
    
    m3u8_url = None
    thumbnail_url = None
    
    for entry in log_entries:
        if ".m3u8" in entry['name'] or (entry['name'].endswith('.m3u8') and 'egcdn-live' in entry['name']):
            m3u8_url = entry['name']
            print(f"M3U8 encontrado: {m3u8_url[:80]}...")
            break
        
        if ".jpg" in entry['name'] and not thumbnail_url:
            thumbnail_url = entry['name']
    
    driver.quit()
    
    return title, m3u8_url, thumbnail_url

if __name__ == "__main__":
    generate_epg_xml()
    
    with open("lista1.m3u", "w") as output_file:
        output_file.write(f'#EXTM3U x-tvg-url="{LOCAL_EPG_FILE}"\n')
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            future_to_url = {executor.submit(extract_globoplay_data, url): url for url in globoplay_urls}
            for future in concurrent.futures.as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    title, m3u8_url, thumbnail_url = future.result()
                    if m3u8_url:
                        thumbnail_url = thumbnail_url if thumbnail_url else ""
                        tvg_id = get_tvg_id(url)
                        output_file.write(f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-name="{tvg_id}" tvg-logo="{thumbnail_url}" group-title="GLOBO AO VIVO", {title}\n')
                        output_file.write(f"{m3u8_url}\n")
                        print(f"✓ Processado com sucesso: {url}")
                    else:
                        print(f"✗ M3U8 não encontrado para {url}")
                except Exception as e:
                    print(f"✗ Erro ao processar {url}: {e}")

    print("\n✓ Arquivo 'lista1.m3u' gerado com sucesso!")
    print(f"✓ EPG local disponível em: {LOCAL_EPG_FILE}")
