import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

ESTADOS_BRASIL = [
    "ac","al","ap","am","ba","ce","df","es","go","ma",
    "mt","ms","mg","pa","pb","pr","pe","pi","rj","rn",
    "rs","ro","rr","sc","sp","se","to"
]

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

    driver = webdriver.Chrome(service=Service(), options=options)

    # Ativa Network (CDP)
    driver.execute_cdp_cmd("Network.enable", {})

    return driver


def buscar_links_ao_vivo(driver, url):
    links = []
    driver.get(url)
    time.sleep(3)

    spans = driver.find_elements(By.CLASS_NAME, "bstn-aovivo-label")
    for span in spans:
        try:
            a = span.find_element(By.XPATH, "./ancestor::a[@href]")
            href = a.get_attribute("href")
            if "/ao-vivo/" in href:
                links.append(href)
        except:
            pass

    return list(set(links))

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

def capturar_m3u8(driver, tempo=20):
    """
    Escuta o tráfego de rede e captura .m3u8
    """
    encontrados = set()
    inicio = time.time()

    while time.time() - inicio < tempo:
        logs = driver.execute_cdp_cmd("Network.getResponseBody", {})
        time.sleep(1)

        # Lê todas as requests registradas
        entries = driver.execute_script(
            "return performance.getEntriesByType('resource')"
        )

        for e in entries:
            url = e.get("name", "")
            if ".m3u8" in url:
                encontrados.add(url)

        if encontrados:
            break

    return list(encontrados)

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
            print("Nenhum link AO VIVO encontrado.")
            return

        print("\n🎥 EXTRAINDO STREAMS (.m3u8)\n")

        with open("lista2.m3u", "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")

            for link in links_ao_vivo:
                print(f"\n➡ Abrindo: {link}")
                driver.get(link)
                time.sleep(5)

                clicar_play(driver)
                time.sleep(5)

                m3u8s = capturar_m3u8(driver)

                if m3u8s:
                    m3u8 = m3u8s[0]
                    titulo = driver.title
                    f.write(f"#EXTINF:-1,{titulo}\n")
                    f.write(f"{m3u8}\n")
                    print(f"   ✅ M3U8 encontrado")
                else:
                    print("   ❌ Nenhum M3U8 capturado")

    finally:
        driver.quit()

    print("\n✅ Arquivo gerado: lista2.m3u")

if __name__ == "__main__":
    main()
