from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time
import concurrent.futures
import os

options = Options()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-gpu")
options.add_argument("--window-size=1280,720")
options.add_argument("--disable-infobars")

LOCAL_EPG_FILE = "globo_epg.xml"
NATIONAL_EPG_FILE = "globo_epg_regional.xml"

CHANNEL_TVG_IDS = {
    "globoplay.globo.com/v/4613774": "GloboSP.br",
    "globoplay.globo.com/ao-vivo/7689934": "GloboSP.br",
    "globoplay.globo.com/ao-vivo/7690141": "GloboSP.br",
    "globoplay.globo.com/ao-vivo/7813173": "GloboSP.br",
    "g1.globo.com/sp/campinas-regiao/ao-vivo/eptv-1-campinas": "eptv-campinas",
    "globoplay.globo.com/ao-vivo/14164032": "tv-globo-al",
    "globoplay.globo.com/ao-vivo/2134039": "GloboSP.br",
    "g1.globo.com/rr/roraima": "rede-amazonica",
    "g1.globo.com/sp/ribeirao-preto-franca/ao-vivo/bom-dia-cidade": "eptv-ribeirao",
    "g1.globo.com/sp/ribeirao-preto-franca/ao-vivo/eptv1": "eptv-ribeirao",
    "g1.globo.com/sp/ribeirao-preto-franca/ao-vivo/eptv-2": "eptv-ribeirao",
    "g1.globo.com/pe/petrolina-regiao/ao-vivo/gr2": "tv-globo-pe",
    "g1.globo.com/ap/ao-vivo/bdap": "tv-globo-ap",
    "globoplay.globo.com/v/2135579": "rbs-tv",
    "globoplay.globo.com/v/6120663": "eptv-ribeirao",
    "globoplay.globo.com/v/2145544": "nsc-tv",
    "globoplay.globo.com/v/4039160": "tv-verdes-mares",
    "globoplay.globo.com/v/6329086": "tv-globo-ba",
    "globoplay.globo.com/v/11999480": "tv-gazeta-es",
    "g1.globo.com/al/alagoas/ao-vivo/assista-aos-telejornais-da-tv-gazeta": "tv-globo-al",
    "globoplay.globo.com/v/4218681": "tv-integracao",
    "globoplay.globo.com/v/3065772": "tv-pantanal",
    "g1.globo.com/am/amazonas/ao-vivo/assista-aos-telejornais-da-rede-amazonica": "rede-amazonica",
    "globoplay.globo.com/v/2168377": "tv-liberal",
    "globoplay.globo.com/v/10747444": "cbn-sp",
    "globoplay.globo.com/v/10740500": "cbn-rj",
    "globoplay.globo.com/v/10747444": "globonews",
    "globoplay.globo.com/v/10740500": "globonews",
    "g1.globo.com/rj": "globo-rj",
    "g1.globo.com/rj/rio-de-janeiro": "globo-rj",
    "globoplay.globo.com/v/1328766": "globo-rj",
    "globoplay.globo.com/v/1467373": "globo-rj",
    "globoplay.globo.com/v/4064559": "nsc-tv",
    "globoplay.globo.com/v/5472979": "tv-globo-pe",
    "globoplay.globo.com/v/10865071": "tv-vanguarda",
    "globoplay.globo.com/v/3667427": "tv-integracao",
    "globoplay.globo.com/v/12945385": "tv-integracao",
    "globoplay.globo.com/v/2923579": "rede-amazonica",
    "globoplay.globo.com/v/2923546": "rede-amazonica",
    "globoplay.globo.com/v/992055": "globo-rj",
    "globoplay.globo.com/v/602497": "globo-rj",
}

def get_epg_url():
    epg_url = ""
    if os.path.exists(LOCAL_EPG_FILE):
        epg_url = LOCAL_EPG_FILE
    elif os.path.exists(NATIONAL_EPG_FILE):
        epg_url = NATIONAL_EPG_FILE
    return epg_url

def get_tvg_id(url):
    for key, tvg_id in CHANNEL_TVG_IDS.items():
        if key in url:
            return tvg_id
    return "GloboSP.br"


# URLs dos vídeos Globoplay e G1 ao vivo
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
    "https://g1.globo.com/sp/ribeirao-preto-franca/ao-vivo/bom-dia-cidade-ribeirao-preto.ghtml",  # Bom Dia Cidade Ribeirão Preto
    "https://g1.globo.com/sp/ribeirao-preto-franca/ao-vivo/eptv1.ghtml",  # EPTV 1ª Edição - Ribeirão Preto
    "https://g1.globo.com/sp/ribeirao-preto-franca/ao-vivo/eptv-2-ribeirao-e-franca-ao-vivo.ghtml",  # EPTV 2ª Edição - Ribeirão e Franca
    "https://g1.globo.com/pe/petrolina-regiao/ao-vivo/ao-vivo-assista-ao-gr2.ghtml",  # GR2 - Petrolina
    "https://g1.globo.com/ap/ao-vivo/assista-ao-bdap-desta-sexta-feira-7.ghtml",  # BDAP - Amapá
    "https://globoplay.globo.com/v/1328766/",
    "https://globoplay.globo.com/v/1467373/",  # Globoplay - Transmissão ao vivo
    "https://globoplay.globo.com/v/4064559/",  # G1 ao vivo - Transmissão ao vivo
    "https://globoplay.globo.com/v/5472979/",
    "https://globoplay.globo.com/v/2135579/",  # G1 RS - Telejornais da RBS TV
    "https://globoplay.globo.com/v/5472979/", #BONI
    "https://globoplay.globo.com/v/6120663/",  # G1 RS - Jornal da EPTV 1ª Edição - Ribeirão Preto
    "https://globoplay.globo.com/v/2145544/",  # G1 SC - Telejornais da NSC TV
    "https://globoplay.globo.com/ao-vivo/10865071/",
    "https://globoplay.globo.com/v/4039160/",  # G1 CE - TV Verdes Mares ao vivo
    "https://globoplay.globo.com/v/6329086/",  # Globo Esporte BA - Travessia Itaparica-Salvador ao vivo
    "https://globoplay.globo.com/v/11999480/",  # G1 ES - Jornal Regional ao vivo
    "https://g1.globo.com/al/alagoas/ao-vivo/assista-aos-telejornais-da-tv-gazeta-de-alagoas.ghtml",  # Telejornais da TV Gazeta de Alagoas
    "https://globoplay.globo.com/ao-vivo/3667427/",  # Globoplay - Transmissão ao vivo
    "https://globoplay.globo.com/v/4218681/",  # G1 Triângulo Mineiro - Transmissão ao vivo
    "https://globoplay.globo.com/v/12945385/",  # Globoplay - Transmissão ao vivo
    "https://globoplay.globo.com/v/3065772/",  # G1 MS - Transmissão ao vivo em MS
    "https://globoplay.globo.com/v/2923579/",  # G1 AP - Telejornais da Rede Amazônica
    "https://g1.globo.com/am/amazonas/ao-vivo/assista-aos-telejornais-da-rede-amazonica.ghtml",  # Telejornais da Rede Amazônica - Amazonas
    "https://globoplay.globo.com/v/2923546/",  # G1 AC - Jornais da Rede Amazônica
    "https://globoplay.globo.com/v/2168377/",  # Telejornais da TV Liberal
    "https://globoplay.globo.com/v/992055/",  # G1 ao vivo - Transmissão ao vivo
    "https://globoplay.globo.com/v/602497/",  # ge.globo - Transmissão ao vivo
    "https://globoplay.globo.com/v/8713568/",  # Globo Esporte RS - Gauchão ao vivo
    "https://globoplay.globo.com/v/10747444/",  # CBN SP - Transmissão ao vivo
    "https://globoplay.globo.com/v/10740500/",  # CBN RJ - Transmissão ao vivo
]

def extract_globoplay_data(url):
    """
    Extrai dados de vídeos do Globoplay e G1 ao vivo.
    
    Funciona com:
    - URLs do Globoplay (globoplay.globo.com)
    - URLs do G1 ao vivo (g1.globo.com/...ao-vivo/...)
    
    Args:
        url (str): URL do vídeo ou transmissão ao vivo
        
    Returns:
        tuple: (título, url_m3u8, url_thumbnail)
    """
    driver = webdriver.Chrome(options=options)
    driver.get(url)
    
    try:
        # Tentar clicar no botão de play (funciona para Globoplay)
        # Se não existir, o script continua normalmente (para G1 ao vivo)
        try:
            play_button = driver.find_element(By.CSS_SELECTOR, "button.poster__play-wrapper")
            if play_button:
                play_button.click()
                time.sleep(20)
                print(f"Botão de play clicado para: {url}")
        except Exception as e:
            # G1 ao vivo não tem botão de play, o vídeo começa automaticamente
            print(f"Botão de play não encontrado (esperado para G1 ao vivo): {e}")
    except Exception as e:
        print(f"Erro ao processar botão de reprodução: {e}")

    # Aguardar o carregamento da página e do stream
    time.sleep(60)
    
    title = driver.title
    
    # Extrair recursos carregados pela página
    log_entries = driver.execute_script("return window.performance.getEntriesByType('resource');")
    
    m3u8_url = None
    thumbnail_url = None
    
    # Procurar por URLs de playlist (m3u8)
    for entry in log_entries:
        # Buscar por playlist.m3u8 ou qualquer URL contendo m3u8
        if ".m3u8" in entry['name'] or (entry['name'].endswith('.m3u8') and 'egcdn-live' in entry['name']):
            m3u8_url = entry['name']
            print(f"M3U8 encontrado: {m3u8_url[:80]}...")
            break
        
        # Buscar por imagens de thumbnail
        if ".jpg" in entry['name'] and not thumbnail_url:
            thumbnail_url = entry['name']
    
    driver.quit()
    
    return title, m3u8_url, thumbnail_url

with open("lista1.m3u", "w") as output_file:
    epg_url = get_epg_url()
    if epg_url:
        output_file.write(f'#EXTM3U x-tvg-url="{epg_url}"\n')
    else:
        output_file.write('#EXTM3U\n')
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        future_to_url = {executor.submit(extract_globoplay_data, url): url for url in globoplay_urls}
        for future in concurrent.futures.as_completed(future_to_url):
            url = future_to_url[future]
            try:
                title, m3u8_url, thumbnail_url = future.result()
                if m3u8_url:
                    thumbnail_url = thumbnail_url if thumbnail_url else ""
                    tvg_id = get_tvg_id(url)
                    output_file.write(f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-name="{tvg_id}" tvg-logo="{thumbnail_url}" group-title="GLOBO AO VIVO", {title}\n')
                    output_file.write(f"{m3u8_url}\n")
                    print(f"✓ Processado com sucesso: {url}")
                else:
                    print(f"✗ M3U8 não encontrado para {url}")
            except Exception as e:
                print(f"✗ Erro ao processar {url}: {e}")

print("\n✓ Arquivo 'lista1.m3u' gerado com sucesso!")
