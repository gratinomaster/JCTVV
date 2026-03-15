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

# URLs
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

        m3u8 = None
        thumbnail = None

        logs = driver.get_log("performance")

        for entry in logs:

            log = json.loads(entry["message"])["message"]

            if log["method"] == "Network.responseReceived":

                response = log["params"]["response"]

                url_response = response["url"]

                if ".m3u8" in url_response:
                    m3u8 = url_response

                if ".jpg" in url_response and thumbnail is None:
                    thumbnail = url_response

        return title, m3u8, thumbnail

    except Exception as e:
        print("Erro:", e)
        return None, None, None

    finally:
        driver.quit()


def generate_playlist():

    with open("globoplay_lista.m3u", "w", encoding="utf-8") as file:

        file.write("#EXTM3U\n")

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:

            futures = {executor.submit(extract_stream, url): url for url in globoplay_urls}

            for future in concurrent.futures.as_completed(futures):

                url = futures[future]

                title, m3u8, thumb = future.result()

                if m3u8:

                    thumb = thumb if thumb else ""

                    file.write(
                        f'#EXTINF:-1 tvg-logo="{thumb}" group-title="GLOBO",{title}\n'
                    )

                    file.write(f"{m3u8}\n")

                    print("OK:", url)

                else:

                    print("Stream não encontrado:", url)


if __name__ == "__main__":
    generate_playlist()
