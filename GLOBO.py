from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import concurrent.futures
import re
import json

options = Options()
options.add_argument("--headless=new")
options.add_argument("--no-sandbox")
options.add_argument("--disable-gpu")
options.add_argument("--window-size=1280,720")
options.add_argument("--disable-infobars")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-extensions")
options.add_argument("--disable-logging")
options.add_argument("--log-level=3")

EPG_FILES = "https://github.com/gratinomaster/JCTV/raw/refs/heads/main/GLOBOEPG.xml.gz,https://github.com/limaalef/BrazilTVEPG/raw/refs/heads/main/globo.xml"

CHANNEL_TVG_IDS = {
    "globoplay.globo.com/v/4613774": "globo_sp",
    "globoplay.globo.com/ao-vivo/7689934": "globo_sp",
    "globoplay.globo.com/ao-vivo/7690141": "globo_sp",
    "globoplay.globo.com/ao-vivo/7813173": "globo_sp",
    "g1.globo.com/sp/campinas-regiao/ao-vivo/eptv-1-campinas": "globo_sp",
    "globoplay.globo.com/ao-vivo/14164032": "globo_al",
    "globoplay.globo.com/ao-vivo/2134039": "globo_sp",
    "g1.globo.com/rr/roraima": "globo_am",
    "g1.globo.com/sp/ribeirao-preto-franca/ao-vivo/bom-dia-cidade": "globo_sp",
    "g1.globo.com/sp/ribeirao-preto-franca/ao-vivo/eptv1": "globo_sp",
    "g1.globo.com/sp/ribeirao-preto-franca/ao-vivo/eptv-2": "globo_sp",
    "g1.globo.com/pe/petrolina-regiao/ao-vivo/gr2": "globo_pe",
    "g1.globo.com/ap/ao-vivo/bdap": "globo_ap",
    "globoplay.globo.com/v/2135579": "globo_rs",
    "globoplay.globo.com/v/6120663": "globo_sp",
    "globoplay.globo.com/v/2145544": "globo_sc",
    "globoplay.globo.com/v/4039160": "globo_ce",
    "globoplay.globo.com/v/6329086": "globo_ba",
    "globoplay.globo.com/v/11999480": "globo_es",
    "g1.globo.com/al/alagoas/ao-vivo/assista-aos-telejornais-da-tv-gazeta": "globo_al",
    "globoplay.globo.com/v/4218681": "globo_mg",
    "globoplay.globo.com/v/3065772": "globo_ms",
    "g1.globo.com/am/amazonas/ao-vivo/assista-aos-telejornais-da-rede-amazonica": "globo_am",
    "globoplay.globo.com/v/2168377": "globo_pa",
    "globoplay.globo.com/v/10747444": "cbn_sp",
    "globoplay.globo.com/v/10740500": "cbn_rj",
    "g1.globo.com/rj": "globo_rj",
    "g1.globo.com/rj/rio-de-janeiro": "globo_rj",
    "globoplay.globo.com/v/1328766": "globo_rj",
    "globoplay.globo.com/v/1467373": "globo_rj",
    "globoplay.globo.com/v/4064559": "globo_sc",
    "globoplay.globo.com/v/5472979": "globo_pe",
    "globoplay.globo.com/v/10865071": "globo_sp",
    "globoplay.globo.com/v/3667427": "globo_mg",
    "globoplay.globo.com/v/12945385": "globo_mg",
    "globoplay.globo.com/v/2923579": "globo_am",
    "globoplay.globo.com/v/2923546": "globo_am",
    "globoplay.globo.com/v/992055": "globo_rj",
    "globoplay.globo.com/v/602497": "globo_rj",
    "globoplay.globo.com/v/8713568": "sportv",
}


def get_epg_url():
    return EPG_FILES


def get_tvg_id(url):
    for key, tvg_id in CHANNEL_TVG_IDS.items():
        if key in url:
            return tvg_id
    return "globo_sp"


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


def extract_globoplay_data(url):
    driver = None
    try:
        driver = webdriver.Chrome(options=options)
        driver.get(url)

        wait = WebDriverWait(driver, 15)

        try:
            play_button = wait.until(
                EC.presence_of_element_located(
                    (
                        By.CSS_SELECTOR,
                        "button.poster__play-wrapper, .play-button, [data-testid='play-button']",
                    )
                )
            )
            if play_button:
                driver.execute_script("arguments[0].click();", play_button)
                print(f"Botão de play clicado para: {url}")
                time.sleep(5)
        except Exception as e:
            print(
                f"Botão de play não encontrado (pode ser ao vivo ou vídeo sob demanda): {e}"
            )

        time.sleep(10)

        title = driver.title

        m3u8_url = None
        thumbnail_url = None

        network_logs = driver.get_log("performance")
        for log_entry in network_logs:
            try:
                log_data = json.loads(log_entry["message"])
                if (
                    log_data.get("message", {}).get("method")
                    == "Network.requestWillBeSent"
                ):
                    request_url = (
                        log_data.get("message", {})
                        .get("params", {})
                        .get("request", {})
                        .get("url", "")
                    )
                    if ".m3u8" in request_url and "globo" in request_url.lower():
                        m3u8_url = request_url
                        print(f"M3U8 encontrado: {m3u8_url[:80]}...")
                        break
            except:
                continue

        if not m3u8_url:
            log_entries = driver.execute_script("""
                return window.performance.getEntriesByType('resource')
                    .map(e => e.name);
            """)
            for entry in log_entries:
                if ".m3u8" in entry:
                    m3u8_url = entry
                    print(f"M3U8 encontrado (fallback): {m3u8_url[:80]}...")
                    break

        if not m3u8_url:
            page_source = driver.page_source
            m3u8_match = re.search(
                r'https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*', page_source
            )
            if m3u8_match:
                m3u8_url = m3u8_match.group(0)
                print(f"M3U8 encontrado (regex): {m3u8_url[:80]}...")

        thumbnails = driver.execute_script("""
            return window.performance.getEntriesByType('resource')
                .filter(e => e.name.match(/\\.(jpg|jpeg|png|webp)/))
                .map(e => e.name);
        """)
        if thumbnails:
            thumbnail_url = thumbnails[0]

        if not thumbnail_url:
            logo_elem = driver.find_elements(
                By.CSS_SELECTOR, "img.player-logo, .logo img, [class*='logo'] img"
            )
            if logo_elem:
                thumbnail_url = logo_elem[0].get_attribute("src")

    except Exception as e:
        print(f"Erro ao processar {url}: {e}")
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass

    return (
        title if "title" in locals() else url,
        m3u8_url if "m3u8_url" in locals() else None,
        thumbnail_url if "thumbnail_url" in locals() else None,
    )


with open("lista1.m3u", "w", encoding="utf-8") as output_file:
    epg_url = get_epg_url()
    if epg_url:
        output_file.write(f'#EXTM3U x-tvg-url="{epg_url}"\n')
    else:
        output_file.write("#EXTM3U\n")

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        future_to_url = {
            executor.submit(extract_globoplay_data, url): url for url in globoplay_urls
        }
        for future in concurrent.futures.as_completed(future_to_url):
            url = future_to_url[future]
            try:
                title, m3u8_url, thumbnail_url = future.result()
                if m3u8_url:
                    thumbnail_str = thumbnail_url if thumbnail_url else ""
                    tvg_id = get_tvg_id(url)
                    output_file.write(
                        f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-name="{tvg_id}" tvg-logo="{thumbnail_str}" group-title="GLOBO AO VIVO", {title}\n'
                    )
                    output_file.write(f"{m3u8_url}\n")
                    print(f"✓ Processado com sucesso: {url}")
                else:
                    print(f"✗ M3U8 não encontrado para {url}")
            except Exception as e:
                print(f"✗ Erro ao processar {url}: {e}")

print("\n✓ Arquivo 'lista1.m3u' gerado com sucesso!")
