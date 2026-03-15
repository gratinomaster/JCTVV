from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import concurrent.futures
import time

# Configurações do Chrome
options = Options()
options.add_argument("--headless=new")
options.add_argument("--no-sandbox")
options.add_argument("--disable-gpu")
options.add_argument("--window-size=1280,720")
options.add_argument("--disable-infobars")

# URLs dos vídeos Globoplay
globoplay_urls = [
    "https://www.imvbox.com/en/watch-iranian-persian-farsi-live-tv/iribtv3",
    "https://www.aparatchi.com/iran-live-tv/farsi-irib-tv/irib1-live",
    "https://farsiland.com/tv1-irib-live/",
    "https://icanlive.tv/live/16259/irib1.html"
]


def extract_globoplay_data(url):
    driver = None
    try:
        driver = webdriver.Chrome(options=options)
        driver.get(url)

        wait = WebDriverWait(driver, 20)

        # tenta clicar no botão play se existir
        try:
            play_button = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.poster__play-wrapper"))
            )
            play_button.click()
        except:
            pass

        # aguarda o player carregar
        time.sleep(10)

        title = driver.title

        # captura requisições da página
        log_entries = driver.execute_script(
            "return window.performance.getEntriesByType('resource');"
        )

        m3u8_url = None
        thumbnail_url = None

        for entry in log_entries:
            name = entry.get("name", "")

            if ".m3u8" in name and not m3u8_url:
                m3u8_url = name

            if ".jpg" in name and not thumbnail_url:
                thumbnail_url = name

        return title, m3u8_url, thumbnail_url

    except Exception as e:
        print(f"Erro ao processar {url}: {e}")
        return None, None, None

    finally:
        if driver:
            driver.quit()


def generate_m3u():
    with open("lista1.m3u", "w", encoding="utf-8") as output_file:
        output_file.write("#EXTM3U\n")

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(extract_globoplay_data, url): url
                for url in globoplay_urls
            }

            for future in concurrent.futures.as_completed(futures):
                url = futures[future]

                try:
                    title, m3u8_url, thumbnail_url = future.result()

                    if m3u8_url:
                        thumbnail_url = thumbnail_url or ""

                        output_file.write(
                            f'#EXTINF:-1 tvg-logo="{thumbnail_url}" group-title="GLOBO AO VIVO",{title}\n'
                        )
                        output_file.write(f"{m3u8_url}\n")

                        print(f"Processado: {url}")

                    else:
                        print(f"M3U8 não encontrado: {url}")

                except Exception as e:
                    print(f"Erro ao finalizar {url}: {e}")


# Executa
if __name__ == "__main__":
    generate_m3u()
