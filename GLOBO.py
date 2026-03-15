from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import concurrent.futures
import json
import time

# Configuração do Chrome
options = Options()
options.add_argument("--headless=new")
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")
options.add_argument("--window-size=1280,720")

# ativar logs de rede
options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

globoplay_urls = [
    "https://www.foxnews.com/video/5614615980001",
]

def extract_stream(url):

    driver = webdriver.Chrome(options=options)

    try:
        driver.get(url)

        wait = WebDriverWait(driver, 20)

        # tentar clicar play
        try:
            play = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button"))
            )
            play.click()
        except:
            pass

        time.sleep(12)

        title = driver.title

        m3u8_list = []
        thumbnail = None

        logs = driver.get_log("performance")

        for entry in logs:
            log = json.loads(entry["message"])["message"]

            if log["method"] == "Network.responseReceived":

                response = log["params"]["response"]
                url_response = response["url"]

                if ".m3u8" in url_response:
                    m3u8_list.append(url_response)

                if ".jpg" in url_response and thumbnail is None:
                    thumbnail = url_response

        return title, m3u8_list, thumbnail

    except Exception as e:
        print("Erro:", e)
        return None, [], None

    finally:
        driver.quit()


def generate_playlist():

    with open("lista5.M3U", "w", encoding="utf-8") as file:

        file.write("#EXTM3U\n")

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:

            futures = {executor.submit(extract_stream, url): url for url in globoplay_urls}

            for future in concurrent.futures.as_completed(futures):

                url = futures[future]

                title, m3u8_list, thumb = future.result()

                if m3u8_list:

                    thumb = thumb if thumb else ""

                    for m3u8 in m3u8_list:

                        file.write(
                            f'#EXTINF:-1 tvg-logo="{thumb}" group-title="GLOBO",{title}\n'
                        )

                        file.write(f"{m3u8}\n")

                        print("M3U8 encontrado:", m3u8)

                    print("OK:", url)

                else:
                    print("Stream não encontrado:", url)


if __name__ == "__main__":
    generate_playlist()

import os
import requests
import logging
from logging.handlers import RotatingFileHandler
import json
from bs4 import BeautifulSoup

# Configuração do logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

log_file = "log.txt"
file_handler = RotatingFileHandler(log_file, maxBytes=1000000, backupCount=5)
file_handler.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Cabeçalho do arquivo M3U
banner = "#EXTM3U\n"

# Função para verificar URLs via requisição HTTP com o agente de usuário do Firefox
def check_url(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36 Firefox/89.0"
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)  # Usando GET para verificar a URL
        if response.status_code == 200:
            logger.info("URL OK: %s", url)
            return True
        else:
            logger.warning("URL Error %s: Status Code %d", url, response.status_code)
            return False
    except requests.exceptions.RequestException as e:
        logger.error("Request Error %s: %s", url, str(e))
        return False

# Função para processar uma linha #EXTINF
def parse_extinf_line(line):
    group_title = "Undefined"
    tvg_id = "Undefined"
    tvg_logo = "Undefined.png"
    ch_name = "Undefined"
    
    if 'group-title="' in line:
        group_title = line.split('group-title="')[1].split('"')[0]
    if 'tvg-id="' in line:
        tvg_id = line.split('tvg-id="')[1].split('"')[0]
    if 'tvg-logo="' in line:
        tvg_logo = line.split('tvg-logo="')[1].split('"')[0]
    if ',' in line:
        ch_name = line.split(',')[-1].strip()
    
    return ch_name, group_title, tvg_id, tvg_logo

# Função principal para processar o arquivo de entrada
def process_m3u_file(input_file, output_file):
    with open(input_file) as f:
        lines = f.readlines()

    channel_data = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        if line.startswith('#EXTINF'):
            ch_name, group_title, tvg_id, tvg_logo = parse_extinf_line(line)
            extra_lines = []
            link = None
            
            # Procura pela URL e ignora linhas intermediárias (#EXTVLCOPT, #KODIPROP, etc.)
            while i + 1 < len(lines):
                i += 1
                next_line = lines[i].strip()
                if next_line.startswith('#'):  # Verifica se a linha começa com '#'
                    extra_lines.append(next_line)  # Armazena a linha extra
                else:
                    link = next_line  # Caso contrário, é a URL do canal
                    break
            
            # Verifica a URL antes de adicionar
            if link and check_url(link):
                # Se o canal não tiver logotipo, buscar o logo automaticamente
                if tvg_logo in ["", "N/A", "Undefined.png"]:  # Condição para logo vazio ou "N/A"
                    logo_url = search_google_images(ch_name)
                    if logo_url:
                        tvg_logo = logo_url
                    else:
                        tvg_logo = "NoLogoFound.png"  # Caso não encontre logo
                
                channel_data.append({
                    'name': ch_name,
                    'group': group_title,
                    'tvg_id': tvg_id,
                    'logo': tvg_logo,
                    'url': link,
                    'extra': extra_lines
                })
        i += 1

    # Gera o arquivo de saída M3U
    with open(output_file, "w") as f:  # Certifique-se de usar "w" e não "a" para sobrescrever
        f.write(banner)
        for channel in channel_data:
            extinf_line = (
                f'#EXTINF:-1 group-title="{channel["group"]}" '
                f'tvg-id="{channel["tvg_id"]}" '
                f'tvg-logo="{channel["logo"]}",{channel["name"]}'
            )
            f.write(extinf_line + '\n')
            for extra in channel['extra']:
                f.write(extra + '\n')
            f.write(channel['url'] + '\n')

    # Salva os dados em JSON para análise posterior
    with open("playlist.json", "w") as f:
        json.dump(channel_data, f, indent=2)

# Função para buscar imagem no Google
def search_google_images(query):
    search_url = f"https://www.google.com/search?hl=pt-BR&q={query}&tbm=isch"  # URL de busca de imagens
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
    }
    
    try:
        response = requests.get(search_url, headers=headers)
        soup = BeautifulSoup(response.text, "html.parser")
        # Buscar a primeira imagem
        img_tags = soup.find_all("img")
        if img_tags:
            # A primeira imagem no Google geralmente é a mais relevante
            img_url = img_tags[1]['src']  # O primeiro item é o logo do Google
            return img_url
    except Exception as e:
        logger.error("Error searching Google images: %s", e)
    
    return None

# Configuração dos arquivos de entrada e saída
input_file = "lista5.M3U"
output_file = "lista5.M3U"

# Executa o processamento
process_m3u_file(input_file, output_file)
