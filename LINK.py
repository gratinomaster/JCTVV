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

    with open("lista5.m3u", "w", encoding="utf-8") as file:

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
                            f'#EXTINF:-1 tvg-logo="{thumb}" group-title="NEWS WORLD",{title}\n'
                        )

                        file.write(f"{m3u8}\n")

                        print("M3U8 encontrado:", m3u8)

                    print("OK:", url)

                else:
                    print("Stream não encontrado:", url)


if __name__ == "__main__":
    generate_playlist()

import time

def check_url(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/58.0.3029.110 Safari/537.36 Firefox/89.0"
    }
    try:
        start_time = time.time()
        response = requests.get(url, headers=headers, timeout=30, stream=True)  # Stream permite ler parcialmente
        elapsed_time = time.time() - start_time

        # Se o status não for 200, ou se demorar menos de 25 segundos, considerar offline
        if response.status_code == 200 and elapsed_time >= 25:
            logger.info("URL OK: %s (tempo: %.2f s)", url, elapsed_time)
            return True
        else:
            logger.warning(
                "URL Offline ou muito rápido: %s (status: %d, tempo: %.2f s)",
                url, response.status_code, elapsed_time
            )
            return False
    except requests.exceptions.RequestException as e:
        logger.error("Request Error %s: %s", url, str(e))
        return False
