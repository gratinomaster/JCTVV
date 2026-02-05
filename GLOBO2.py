#!/usr/bin/env python3
import time
import concurrent.futures
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# =========================
# ESTADOS DO BRASIL (para busca dinâmica)
# =========================
ESTADOS_BRASIL = [
    "ac", "al", "ap", "am", "ba", "ce", "df", "es", "go", "ma",
    "mt", "ms", "mg", "pa", "pb", "pr", "pe", "pi", "rj", "rn",
    "rs", "ro", "rr", "sc", "sp", "se", "to"
]

# =========================
# CONFIGURAÇÕES DO DRIVER
# =========================
def criar_driver():
    """Cria e retorna uma instância do WebDriver do Chrome com as opções configuradas."""
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    # Desativa o log excessivo do Selenium no console
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    
    # Adapte o Service se o chromedriver não estiver no PATH
    service = Service()
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(45)
    return driver

# =========================
# ETAPA 1: BUSCAR LINKS "AO VIVO" NOS PORTAIS G1
# =========================
def buscar_links_ao_vivo():
    """Navega pelos portais G1 de cada estado e coleta links de transmissões 'ao vivo'."""
    print("\n🔎 ETAPA 1: Coletando links 'AO VIVO' dos portais G1...")
    links_encontrados = set()
    driver = criar_driver()

    try:
        for estado in ESTADOS_BRASIL:
            url = f"https://g1.globo.com/{estado}"
            try:
                driver.get(url )
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                
                # Encontra todos os links que contêm um elemento com a classe 'bstn-aovivo-label'
                elementos_link = driver.find_elements(By.XPATH, "//a[.//span[contains(@class, 'bstn-aovivo-label')]]")
                
                novos_links = {elem.get_attribute("href") for elem in elementos_link if elem.get_attribute("href")}
                
                if novos_links:
                    print(f"  ✓ {estado.upper()}: {len(novos_links)} link(s) encontrado(s).")
                    links_encontrados.update(novos_links)
                else:
                    print(f"  - {estado.upper()}: Nenhum link 'AO VIVO' encontrado.")

            except Exception as e:
                print(f"  ⚠ Erro ao processar o estado {estado.upper()}: {e}")
    finally:
        driver.quit()
    
    print(f"\n✅ Coleta finalizada. Total de {len(links_encontrados)} links únicos encontrados.")
    return sorted(list(links_encontrados))

# =========================
# ETAPA 2: PROCESSAR CADA LINK PARA EXTRAIR O STREAM
# =========================
def processar_link(url):
    """
    Abre um link, tenta extrair o título, o stream .m3u8 e uma thumbnail.
    Usa a técnica de `window.performance` para encontrar os recursos de mídia.
    """
    print(f"  ▶ Processando: {url}")
    driver = None
    try:
        driver = criar_driver()
        driver.get(url)

        # Tenta clicar no botão de play, se existir (comum no Globoplay)
        try:
            play_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.poster__play-wrapper, .vjs-big-play-button"))
            )
            driver.execute_script("arguments[0].click();", play_button)
            print(f"    ✓ Botão de play clicado para: {url}")
            # Espera um pouco para o stream começar após o clique
            time.sleep(15)
        except Exception:
            # Se não houver botão de play (comum no G1), o vídeo deve começar sozinho
            print(f"    - Botão de play não encontrado ou não clicável (comportamento esperado para alguns players).")
            time.sleep(10)

        # Extrai o título da página
        titulo = driver.title.split(" | ")[0].split(" - ")[0].strip()

        # Usa JavaScript para obter os recursos de rede carregados pela página
        log_entries = driver.execute_script("return window.performance.getEntriesByType('resource');")
        
        m3u8_url = None
        thumbnail_url = None

        # Itera sobre os recursos para encontrar o .m3u8 e a thumbnail
        for entry in reversed(log_entries): # Inverte para pegar os mais recentes primeiro
            entry_url = entry.get('name', '')
            if ".m3u8" in entry_url and not m3u8_url:
                m3u8_url = entry_url
            if (".jpg" in entry_url or ".jpeg" in entry_url) and "video.glbimg.com" in entry_url and not thumbnail_url:
                thumbnail_url = entry_url
            
            # Se já encontrou ambos, pode parar
            if m3u8_url and thumbnail_url:
                break
        
        if m3u8_url:
            print(f"    ✅ SUCESSO: Stream encontrado para '{titulo}'")
            return {"titulo": titulo, "m3u8": m3u8_url, "thumbnail": thumbnail_url, "grupo": "GLOBO AO VIVO"}
        else:
            print(f"    ❌ FALHA: Stream .m3u8 não encontrado para {url}")
            return None

    except Exception as e:
        print(f"    🔥 ERRO GERAL ao processar {url}: {e}")
        return None
    finally:
        if driver:
            driver.quit()

# =========================
# FUNÇÃO PRINCIPAL (MAIN)
# =========================
def main():
    # ETAPA 1
    links_para_processar = buscar_links_ao_vivo()

    if not links_para_processar:
        print("\nNenhum link 'AO VIVO' foi encontrado para processar. Encerrando.")
        return

    # ETAPA 2
    print(f"\n🔎 ETAPA 2: Extraindo streams de {len(links_para_processar)} links usando até 4 workers...")
    resultados_finais = []
    
    # Usando ThreadPoolExecutor para processar os links em paralelo
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        # Mapeia cada futura execução ao seu respectivo link
        future_to_url = {executor.submit(processar_link, url): url for url in links_para_processar}
        
        for future in concurrent.futures.as_completed(future_to_url):
            try:
                resultado = future.result()
                if resultado:
                    resultados_finais.append(resultado)
            except Exception as e:
                url = future_to_url[future]
                print(f"🔥 Erro crítico no worker para a URL {url}: {e}")

    # ETAPA 3: Gerar o arquivo .m3u
    if not resultados_finais:
        print("\nNenhum stream foi extraído com sucesso. Nenhum arquivo gerado.")
        return

    nome_arquivo = "lista_canais_integrada.m3u"
    with open(nome_arquivo, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for item in sorted(resultados_finais, key=lambda x: x['titulo']): # Ordena por título
            thumbnail = item.get("thumbnail") or ""
            extinf = f'#EXTINF:-1 tvg-logo="{thumbnail}" group-title="{item["grupo"]}",{item["titulo"]}\n'
            f.write(extinf)
            f.write(f'{item["m3u8"]}\n')

    print(f"\n\n🎉 Arquivo gerado com sucesso: {nome_arquivo} ({len(resultados_finais)} canais)")


# =========================
# EXECUÇÃO
# =========================
if __name__ == "__main__":
    main()
