from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time
import concurrent.futures
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
import json
import urllib.request
import gzip
import shutil
import os

options = Options()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-gpu")
options.add_argument("--window-size=1280,720")
options.add_argument("--disable-infobars")

LOCAL_EPG_FILE = "globo_epg.xml"
LOCAL_EPG_REGIONAL_FILE = "globo_epg_regional.xml"
EPG_ONLINE_URL = "https://raw.githubusercontent.com/limaalef/BrazilTVEPG/main/globo.xml"
EPG_ONLINE_FILE = "globo_epg_online.xml"

NATIONAL_CHANNELS = [
    "tv-globo", "globonews", "gnt", "multishow", "gloob", "gloobinho", "ge-tv",
    "bis", "canal-brasil", "canal-off", "combate", "premiere", "sportv",
    "sportv-2", "sportv-3", "megapix", "telecine-action", "telecine-cult",
    "telecine-fun", "telecine-pipoca", "telecine-premium", "telecine-touch",
    "universal", "studio-universal", "futura", "usa", "dpa-fast", "malhacao-fast",
    "receitas-fast", "modo-viagem", "globoplay-novelas"
]

REGIONAL_EPG_URLS = {
    "eptv-campinas": "https://redeglobo.globo.com/sp/eptv/campinas/programacao/",
    "eptv-ribeirao": "https://redeglobo.globo.com/sp/eptv/ribeirao-preto/programacao/",
    "rbs-porto-alegre": "https://redeglobo.globo.com/rs/rbstvrs/programacao/",
    "nsc-tv": "https://redeglobo.globo.com/sc/nsctv/programacao/",
    "tv-verdes-mares": "https://redeglobo.globo.com/ce/tvverdesmares/programacao/",
    "tv-globo-ba": "https://redeglobo.globo.com/ba/tvbahia/programacao/",
    "tv-globo-al": "https://redeglobo.globo.com/al/tvgazetaal/programacao/",
    "rede-amazonica": "https://redeglobo.globo.com/am/redeamazonica/programacao/",
    "tv-liberal": "https://redeglobo.globo.com/pa/tvliberal/programacao/",
    "tv-gazeta-es": "https://redeglobo.globo.com/es/tvgazetaes/programacao/",
    "tv-integracao": "https://redeglobo.globo.com/mg/tvintegracao/programacao/",
    "tv-vanguarda": "https://redeglobo.globo.com/sp/tvvanguarda/programacao/",
    "tv-pantanal": "https://redeglobo.globo.com/ms/tvpantanal/programacao/",
}

CHANNEL_TVG_IDS = {
    "globoplay.globo.com/v/4613774": "tv-globo",
    "globoplay.globo.com/ao-vivo/7689934": "tv-globo",
    "globoplay.globo.com/ao-vivo/7690141": "tv-globo",
    "globoplay.globo.com/ao-vivo/7813174": "tv-globo",
    "globoplay.globo.com/ao-vivo/7813173": "tv-globo",
    "globoplay.globo.com/v/12749215": "tv-globo",
    "globoplay.globo.com/v/1328766": "globonews",
    "globoplay.globo.com/v/1467373": "globonews",
    "globoplay.globo.com/v/4064559": "gnt",
    "globoplay.globo.com/v/5472979": "multishow",
    "globoplay.globo.com/v/992055": "gloob",
    "globoplay.globo.com/v/602497": "gloobinho",
    "globoplay.globo.com/v/8713568": "ge-tv",
    "g1.globo.com/sp/campinas-regiao/ao-vivo/eptv-1-campinas": "eptv-campinas",
    "globoplay.globo.com/ao-vivo/14164032": "tv-globo-al",
    "globoplay.globo.com/ao-vivo/2134039": "tv-globo-ba",
    "g1.globo.com/rr/roraima": "tv-globo-rr",
    "g1.globo.com/sp/ribeirao-preto-franca/ao-vivo/bom-dia-cidade": "eptv-ribeirao",
    "g1.globo.com/sp/ribeirao-preto-franca/ao-vivo/eptv1": "eptv-ribeirao",
    "g1.globo.com/sp/ribeirao-preto-franca/ao-vivo/eptv-2": "eptv-ribeirao-2",
    "g1.globo.com/pe/petrolina-regiao/ao-vivo/gr2": "gr2",
    "g1.globo.com/ap/ao-vivo/bdap": "bdap",
    "globoplay.globo.com/v/2135579": "rbs-porto-alegre",
    "globoplay.globo.com/v/6120663": "g1-rs",
    "globoplay.globo.com/v/2145544": "nsc-tv",
    "globoplay.globo.com/ao-vivo/10865071": "tv-vanguarda",
    "globoplay.globo.com/v/4039160": "tv-verdes-mares",
    "globoplay.globo.com/v/6329086": "globo-esporte-ba",
    "globoplay.globo.com/v/11999480": "tv-gazeta-es",
    "g1.globo.com/al/alagoas/ao-vivo/assista-aos-telejornais-da-tv-gazeta": "tv-gazeta-al",
    "globoplay.globo.com/ao-vivo/3667427": "tv-integracao",
    "globoplay.globo.com/v/4218681": "tv-integracao",
    "globoplay.globo.com/v/12945385": "tv-integracao",
    "globoplay.globo.com/v/3065772": "tv-pantanal",
    "g1.globo.com/am/amazonas/ao-vivo/assista-aos-telejornais-da-rede-amazonica": "rede-amazonica",
    "globoplay.globo.com/v/2923579": "rede-amazonica",
    "globoplay.globo.com/v/2923546": "rede-amazonica",
    "globoplay.globo.com/v/2168377": "tv-liberal",
    "globoplay.globo.com/v/10747444": "cbn-sp",
    "globoplay.globo.com/v/10740500": "cbn-rio",
}

CHANNEL_NAMES = {
    "tv-globo": "TV Globo",
    "globonews": "GloboNews",
    "gnt": "GNT",
    "multishow": "Multishow",
    "gloob": "Gloob",
    "gloobinho": "Gloobinho",
    "ge-tv": "GE TV",
    "eptv-campinas": "EPTV Campinas",
    "eptv-ribeirao": "EPTV Ribeirão Preto",
    "eptv-ribeirao-2": "EPTV 2ª Edição",
    "rbs-porto-alegre": "RBS TV Porto Alegre",
    "g1-rs": "G1 RS",
    "nsc-tv": "NSC TV",
    "tv-vanguarda": "TV Vanguarda",
    "tv-verdes-mares": "TV Verdes Mares",
    "globo-esporte-ba": "Globo Esporte BA",
    "tv-gazeta-es": "TV Gazeta ES",
    "tv-gazeta-al": "TV Gazeta Alagoas",
    "tv-globo-al": "TV Globo Alagoas",
    "tv-globo-ba": "TV Bahia",
    "tv-globo-rr": "TV Rural",
    "tv-integracao": "TV Integração",
    "tv-pantanal": "TV Pantanal",
    "rede-amazonica": "Rede Amazônica",
    "tv-liberal": "TV Liberal",
    "cbn-sp": "CBN São Paulo",
    "cbn-rio": "CBN Rio",
    "gr2": "GR2 Petrolina",
    "bdap": "BDAP",
}

ONLINE_EPG_CHANNELS = [
    "tv-globo", "globonews", "gnt", "multishow", "gloob", "gloobinho", "ge-tv",
    "bis", "canal-brasil", "canal-off", "combate", "premiere", "sportv",
    "sportv-2", "sportv-3", "megapix", "telecine-action", "telecine-cult",
    "telecine-fun", "telecine-pipoca", "telecine-premium", "telecine-touch",
    "universal", "studio-universal", "futura", "usa", "dpa-fast", "malhacao-fast",
    "receitas-fast", "modo-viagem", "globoplay-novelas"
]

def download_online_epg():
    try:
        print(f"Baixando EPG online de: {EPG_ONLINE_URL}")
        urllib.request.urlretrieve(EPG_ONLINE_URL, EPG_ONLINE_FILE)
        print(f"✓ EPG online baixado: {EPG_ONLINE_FILE}")
        return True
    except Exception as e:
        print(f"✗ Erro ao baixar EPG online: {e}")
        return False

def get_tvg_id(url):
    for key, tvg_id in CHANNEL_TVG_IDS.items():
        if key in url:
            return tvg_id
    return "tv-globo"

def generate_regional_epg_file(regional_epg_file=None):
    import os
    root = ET.Element('tv')
    root.set('generator-info-name', 'Globo EPG Generator - Regional')
    root.set('generated-date', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    if regional_epg_file and os.path.exists(regional_epg_file):
        try:
            tree = ET.parse(regional_epg_file)
            regional_root = tree.getroot()
            for child in regional_root:
                root.append(child)
            print(f"✓ EPG regional de {regional_epg_file} mesclado")
        except Exception as e:
            print(f"✗ Erro ao processar EPG regional: {e}")
    
    for tvg_id, channel_name in CHANNEL_NAMES.items():
        if tvg_id in NATIONAL_CHANNELS:
            continue
        
        found = False
        for channel in root.findall('channel'):
            if channel.get('id') == tvg_id:
                found = True
                break
        
        if not found:
            channel_elem = ET.SubElement(root, 'channel')
            channel_elem.set('id', tvg_id)
            
            display_name = ET.SubElement(channel_elem, 'display-name')
            display_name.text = channel_name
    
    output_file = regional_epg_file if regional_epg_file else LOCAL_EPG_REGIONAL_FILE
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(output_file, encoding='UTF-8', xml_declaration=True)
    print(f"✓ Arquivo EPG regional gerado: {output_file}")
    
    return output_file

def merge_epg_files():
    root = ET.Element('tv')
    root.set('generator-info-name', 'Globo EPG - Merged')
    root.set('generated-date', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    if download_online_epg():
        try:
            tree = ET.parse(EPG_ONLINE_FILE)
            online_root = tree.getroot()
            for child in online_root:
                root.append(child)
            print("✓ EPG online (limaalef) mesclado")
        except Exception as e:
            print(f"✗ Erro ao mesclar EPG online: {e}")
    
    if os.path.exists(LOCAL_EPG_REGIONAL_FILE):
        try:
            tree = ET.parse(LOCAL_EPG_REGIONAL_FILE)
            regional_root = tree.getroot()
            for child in regional_root:
                root.append(child)
            print("✓ EPG regional mesclado")
        except Exception as e:
            print(f"✗ Erro ao mesclar EPG regional: {e}")
    
    for tvg_id, channel_name in CHANNEL_NAMES.items():
        if tvg_id in NATIONAL_CHANNELS:
            continue
        
        found = False
        for channel in root.findall('channel'):
            if channel.get('id') == tvg_id:
                found = True
                break
        
        if not found:
            channel_elem = ET.SubElement(root, 'channel')
            channel_elem.set('id', tvg_id)
            
            display_name = ET.SubElement(channel_elem, 'display-name')
            display_name.text = channel_name
    
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(LOCAL_EPG_FILE, encoding='UTF-8', xml_declaration=True)
    print(f"✓ Arquivo EPG final gerado: {LOCAL_EPG_FILE}")

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
    merge_epg_files()
    
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
