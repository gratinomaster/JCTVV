#!/usr/bin/env python3
import time
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

# Estados do Brasil
ESTADOS_BRASIL = [
    "ac","al","ap","am","ba","ce","df","es","go","ma",
    "mt","ms","mg","pa","pb","pr","pe","pi","rj","rn",
    "rs","ro","rr","sc","sp","se","to"
]

# =========================
# DRIVER (GitHub Actions OK)
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

    # ATIVA LOG DE PERFORMANCE (CRÍTICO)
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

    driver = webdriver.Chrome(service=Service(), options=options)
    return driver

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

            # Filtra links ruins (#v/)
            if "/ao-vivo/" in href and href.endswith(".ghtml"):
                links.append(href)
        except:
            pass

    return list(set(links))

# =========================
# CLICA PLAY (se existir)
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
# CAPTURA M3U8 (CORRETO)
# =========================
def capturar_m3u8(driver, tempo=40):
    encontrados = set()
    inicio = time.time()

    while time.time() - inicio < tempo:
        logs = driver.get_log("performance")

        for entry in logs:
            try:
                msg = json.loads(entry["message"])["message"]
                if msg.get("method") == "Network.responseReceived":
                    url = msg["params"]["response"]["url"]
                    if ".m3u8" in url:
                        encontrados.add(url)
            except:
                pass

        if encontrados:
            break

        time.sleep(1)

    return list(encontrados)

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

                m3u8s = capturar_m3u8(driver)

                if m3u8s:
                    m3u8 = m3u8s[0]
                    titulo = driver.title.strip()
                    f.write(f"#EXTINF:-1,{titulo}\n")
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
