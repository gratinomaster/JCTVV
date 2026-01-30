#!/usr/bin/env python3
import time
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

# =========================
# ESTADOS DO BRASIL
# =========================
ESTADOS_BRASIL = [
    "ac","al","ap","am","ba","ce","df","es","go","ma",
    "mt","ms","mg","pa","pb","pr","pe","pi","rj","rn",
    "rs","ro","rr","sc","sp","se","to"
]

# =========================
# DRIVER (GITHUB ACTIONS OK)
# =========================
def criar_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--autoplay-policy=no-user-gesture-required")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    # LOG DE PERFORMANCE (CRÍTICO)
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

    return webdriver.Chrome(service=Service(), options=options)

# =========================
# BUSCA LINKS AO VIVO
# =========================
def buscar_links_ao_vivo(driver, url):
    links = []
    driver.get(url)
    time.sleep(3)

    spans = driver.find_elements(By.CLASS_NAME, "bstn-aovivo-label")

    for span in spans:
        try:
            a = span.find_element(By.XPATH, "./ancestor::a[@href]")
            href = a.get_attribute("href")

            if "/ao-vivo/" in href and href.endswith(".ghtml"):
                links.append(href)
        except:
            pass

    return list(set(links))

# =========================
# CLICA PLAY (SE EXISTIR)
# =========================
def clicar_play(driver):
    seletores = [
        "button.poster__play-wrapper",
        ".play-button",
        "[aria-label='Play']",
        ".video-player__play-button"
    ]

    for s in seletores:
        try:
            btn = driver.find_element(By.CSS_SELECTOR, s)
            if btn.is_displayed():
                btn.click()
                return True
        except:
            pass

    return False

# =========================
# CAPTURA M3U8 + THUMBNAIL
# =========================
def capturar_streams(driver, tempo=40):
    m3u8_url = None
    thumbnail_url = None
    inicio = time.time()

    while time.time() - inicio < tempo:
        logs = driver.get_log("performance")

        for entry in logs:
            try:
                msg = json.loads(entry["message"])["message"]

                if msg.get("method") != "Network.responseReceived":
                    continue

                url = msg["params"]["response"]["url"].lower()

                # ===== M3U8 =====
                if ".m3u8" in url and not m3u8_url:
                    m3u8_url = msg["params"]["response"]["url"]

                # ===== THUMBNAIL (SOMENTE GLOBO) =====
                if (
                    not thumbnail_url
                    and (url.endswith(".jpg") or url.endswith(".jpeg"))
                    and "video.glbimg.com" in url
                ):
                    thumbnail_url = msg["params"]["response"]["url"]

            except:
                pass

        if m3u8_url:
            break

        time.sleep(1)

    return m3u8_url, thumbnail_url


# =========================
# MAIN
# =========================
def main():
    driver = criar_driver()
    links_ao_vivo = []

    try:
        print("\n🔎 COLETANDO LINKS AO VIVO\n")

        for estado in ESTADOS_BRASIL:
            url = f"https://g1.globo.com/{estado}"
            links = buscar_links_ao_vivo(driver, url)

            if links:
                print(f"{estado.upper()}:")
                for l in links:
                    print(f"  ✓ {l}")
                links_ao_vivo.extend(links)

        if not links_ao_vivo:
            print("\n⚠ Nenhum link AO VIVO encontrado.")
            return

        print("\n🎥 EXTRAINDO STREAMS (.m3u8)\n")

        with open("lista2.m3u", "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")

            for link in links_ao_vivo:
                print(f"\n➡ Abrindo: {link}")
                driver.get(link)
                time.sleep(6)

                clicar_play(driver)
                time.sleep(6)

                m3u8, thumbnail_url = capturar_streams(driver)

                if m3u8:
                    titulo = driver.title.strip()

                    extinf = '#EXTINF:-1 group-title="GLOBO AO VIVO"'

                    if thumbnail_url:
                        extinf += f' tvg-logo="{thumbnail_url}"'

                    extinf += f',{titulo}\n'

                    f.write(extinf)
                    f.write(f"{m3u8}\n")

                    print("   ✅ M3U8 encontrado")
                else:
                    print("   ❌ Nenhum M3U8 capturado")

    finally:
        driver.quit()

    print("\n✅ Arquivo gerado: lista2.m3u")

# =========================
# EXECUÇÃO
# =========================
if __name__ == "__main__":
    main()
