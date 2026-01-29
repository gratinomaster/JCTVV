#!/usr/bin/env python3
"""
Script para buscar links "AO VIVO" no G1 Globo para todos os estados brasileiros
e gerar um arquivo M3U (.m3u) diretamente com os streams .m3u8.
Usa Selenium para lidar com conteúdo carregado via JavaScript.
"""

import time
import concurrent.futures
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# Lista de todos os estados brasileiros com suas abreviações
ESTADOS_BRASIL = [
    "ac", "al", "ap", "am", "ba", "ce", "df", "es", "go", "ma",
    "mt", "ms", "mg", "pa", "pb", "pr", "pe", "pi", "rj", "rn",
    "rs", "ro", "rr", "sc", "sp", "se", "to"
]

def criar_driver(headless=True):
    """Cria o driver do Chrome"""
    chrome_options = Options()
    if headless:
        chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    service = Service()
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

def buscar_links_ao_vivo(driver, url):
    """Busca links 'AO VIVO' em uma página do G1"""
    links_encontrados = []
    try:
        driver.get(url)
        try:
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CLASS_NAME, "bstn-aovivo-label"))
            )
        except TimeoutException:
            return links_encontrados

        spans = driver.find_elements(By.CLASS_NAME, "bstn-aovivo-label")
        for span in spans:
            try:
                parent_a = span.find_element(By.XPATH, "./ancestor::a[@href]")
                href = parent_a.get_attribute("href")
                if href not in links_encontrados:
                    links_encontrados.append(href)
            except:
                continue

    except Exception as e:
        print(f"Erro ao acessar {url}: {e}")

    return links_encontrados

def extract_stream_data(url):
    """Processa a URL para encontrar o stream m3u8"""
    driver = criar_driver()
    m3u8_url = None
    thumbnail_url = None
    title = "Sem Título"

    try:
        driver.get(url)
        time.sleep(10)  # espera a página carregar

        title = driver.title

        # Tenta disparar o player
        play_selectors = ["button.poster__play-wrapper", ".play-button", "[aria-label='Play']", ".video-player__play-button"]
        for selector in play_selectors:
            try:
                btn = driver.find_element(By.CSS_SELECTOR, selector)
                if btn.is_displayed():
                    btn.click()
                    time.sleep(5)
                    break
            except:
                continue

        # Captura m3u8 dos logs de rede
        resources = driver.execute_script("return window.performance.getEntriesByType('resource');")
        for entry in resources:
            name = entry['name']
            if ".m3u8" in name and not m3u8_url:
                if any(x in name for x in ["playlist.m3u8", "master.m3u8", "index.m3u8"]):
                    m3u8_url = name
            if (".jpg" in name or ".png" in name) and not thumbnail_url:
                if any(x in name for x in ["thumb", "poster", "logo"]):
                    thumbnail_url = name

    except Exception as e:
        print(f"Erro em {url}: {e}")
    finally:
        driver.quit()
    return title, m3u8_url, thumbnail_url, url

def main():
    driver = criar_driver()
    todos_os_links = []

    try:
        # Coleta links "AO VIVO" de todos os estados
        for estado in ESTADOS_BRASIL:
            url = f"https://g1.globo.com/{estado}"
            links = buscar_links_ao_vivo(driver, url)
            todos_os_links.extend(links)
    finally:
        driver.quit()

    if not todos_os_links:
        print("Nenhum link 'AO VIVO' encontrado.")
        return

    # Cria arquivo M3U final
    output_file = "lista2.m3u"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = {executor.submit(extract_stream_data, url): url for url in todos_os_links}
            for future in concurrent.futures.as_completed(futures):
                try:
                    title, m3u8, thumb, url = future.result()
                    if m3u8:
                        f.write(f'#EXTINF:-1 tvg-logo="{thumb or ""}" group-title="G1 AO VIVO",{title}\n')
                        f.write(f"{m3u8}\n")
                        print(f"OK: {title}")
                    else:
                        print(f"Stream não encontrado: {url}")
                except Exception as e:
                    print(f"Erro: {e}")

    print(f"\nLista gerada: {output_file}")

if __name__ == "__main__":
    main()
