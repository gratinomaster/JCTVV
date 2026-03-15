import json
import time
import logging
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait

# ==============================
# CONFIG
# ==============================

URLS = [
    "https://www.foxnews.com/video/5614615980001"
]

OUTPUT_FILE = "lista5.m3u"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# ==============================
# LOGGER
# ==============================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ==============================
# SELENIUM DRIVER
# ==============================

def create_driver():

    options = Options()

    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1280,720")

    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

    return webdriver.Chrome(options=options)


# ==============================
# EXTRACT STREAM
# ==============================

def extract_stream(url):

    driver = create_driver()

    try:

        driver.get(url)

        WebDriverWait(driver, 20)

        time.sleep(8)

        logs = driver.get_log("performance")

        m3u8_list = set()
        thumbnail = None

        for entry in logs:

            log = json.loads(entry["message"])["message"]

            if log["method"] != "Network.responseReceived":
                continue

            response = log["params"]["response"]
            response_url = response["url"]

            if ".m3u8" in response_url:
                m3u8_list.add(response_url)

            if ".jpg" in response_url and thumbnail is None:
                thumbnail = response_url

        return {
            "title": driver.title,
            "streams": list(m3u8_list),
            "thumbnail": thumbnail
        }

    except Exception as e:

        logging.error(f"Erro {url}: {e}")

        return None

    finally:

        driver.quit()


# ==============================
# CHECK STREAM
# ==============================

session = requests.Session()

def check_url(url):

    try:

        r = session.head(url, timeout=10)

        return r.status_code == 200

    except:

        return False


# ==============================
# GENERATE PLAYLIST
# ==============================

def generate_playlist():

    channels = []

    with ThreadPoolExecutor(max_workers=3) as executor:

        futures = [executor.submit(extract_stream, url) for url in URLS]

        for future in as_completed(futures):

            result = future.result()

            if not result:
                continue

            for stream in result["streams"]:

                if check_url(stream):

                    channels.append({
                        "name": result["title"],
                        "logo": result["thumbnail"],
                        "url": stream
                    })

                    logging.info(f"Stream OK: {stream}")

    write_m3u(channels)


# ==============================
# WRITE M3U
# ==============================

def write_m3u(channels):

    with open(OUTPUT_FILE, "w", encoding="utf8") as f:

        f.write("#EXTM3U\n")

        for ch in channels:

            logo = ch["logo"] if ch["logo"] else ""

            f.write(
                f'#EXTINF:-1 group-title="NEWS WORLD" tvg-logo="{logo}",{ch["name"]}\n'
            )

            f.write(f"{ch['url']}\n")

    logging.info("Playlist gerada com sucesso")


# ==============================
# MAIN
# ==============================

if __name__ == "__main__":

    generate_playlist()
    
