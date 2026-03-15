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

    with open("globoplay_lista.m3u", "w", encoding="utf-8") as file:

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

import requests
import time

arquivo_m3u = "globoplay_lista.m3u"
timeout = 10
espera = 6


def pegar_segmentos(m3u8_url):
    try:
        r = requests.get(m3u8_url, timeout=timeout)
        if r.status_code != 200:
            return None

        linhas = r.text.splitlines()

        if "#EXT-X-ENDLIST" in r.text:
            return None  # VOD

        segmentos = [l for l in linhas if l.endswith(".ts") or l.endswith(".m4s")]
        return segmentos[-5:]  # últimos segmentos

    except:
        return None


def stream_ao_vivo(url):
    seg1 = pegar_segmentos(url)
    if not seg1:
        return False

    time.sleep(espera)

    seg2 = pegar_segmentos(url)
    if not seg2:
        return False

    return seg1 != seg2  # mudou = live


def testar_lista():
    with open(arquivo_m3u, "r", encoding="utf-8", errors="ignore") as f:
        linhas = f.readlines()

    nova_lista = []
    i = 0

    while i < len(linhas):
        linha = linhas[i].strip()

        if linha.startswith("#EXTINF"):
            info = linha
            url = linhas[i + 1].strip()

            print("Testando:", url)

            if stream_ao_vivo(url):
                print("AO VIVO ✅")
                nova_lista.append(info + "\n")
                nova_lista.append(url + "\n")
            else:
                print("SEM TRANSMISSÃO ❌")

            i += 2
        else:
            if linha.startswith("#EXTM3U"):
                nova_lista.append(linha + "\n")
            i += 1

    with open(arquivo_m3u, "w", encoding="utf-8") as f:
        f.writelines(nova_lista)

    print("\nLista atualizada: apenas canais AO VIVO mantidos.")


if __name__ == "__main__":
    testar_lista()
