import json
import time
import concurrent.futures
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# ------------------------
# CONFIGURAÇÃO
# ------------------------

MAX_THREADS = 4
OUTPUT_FILE = "globoplay_playlist.m3u"

seed_urls = [
    "https://globoplay.globo.com/ao-vivo/",
    "https://g1.globo.com/ao-vivo/",
    "https://globoplay.globo.com/"
]

# ------------------------
# CHROME CONFIG
# ------------------------

def create_driver():

    chrome_options = Options()

    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")

    chrome_options.set_capability(
        "goog:loggingPrefs",
        {"performance": "ALL"}
    )

    driver = webdriver.Chrome(options=chrome_options)

    return driver


# ------------------------
# CAPTURA STREAM
# ------------------------

def capture_stream(url):

    driver = create_driver()

    try:

        driver.get(url)

        time.sleep(10)

        logs = driver.get_log("performance")

        stream_url = None
        thumbnail = None

        for entry in logs:

            message = json.loads(entry["message"])["message"]

            if message["method"] == "Network.responseReceived":

                response = message["params"]["response"]
                res_url = response["url"]

                if ".m3u8" in res_url:
                    stream_url = res_url

                if ".jpg" in res_url and thumbnail is None:
                    thumbnail = res_url

        title = driver.title

        return {
            "title": title,
            "stream": stream_url,
            "thumb": thumbnail
        }

    except Exception as e:

        print("Erro:", url, e)

        return None

    finally:

        driver.quit()


# ------------------------
# GERADOR M3U
# ------------------------

def generate_m3u(results):

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:

        f.write("#EXTM3U\n")

        for item in results:

            if not item:
                continue

            if not item["stream"]:
                continue

            thumb = item["thumb"] if item["thumb"] else ""

            f.write(
                f'#EXTINF:-1 tvg-logo="{thumb}" group-title="Globo",{item["title"]}\n'
            )

            f.write(item["stream"] + "\n")


# ------------------------
# EXECUÇÃO
# ------------------------

def run():

    results = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:

        futures = [executor.submit(capture_stream, url) for url in seed_urls]

        for future in concurrent.futures.as_completed(futures):

            data = future.result()

            if data:
                print("Encontrado:", data["title"])
                results.append(data)

    generate_m3u(results)

    print("Playlist criada:", OUTPUT_FILE)


if __name__ == "__main__":
    run()
