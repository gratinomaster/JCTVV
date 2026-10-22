import json
import re
import tempfile
import unicodedata
import urllib.request
from urllib.parse import unquote

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import concurrent.futures
import time


def criar_opcoes():
    """Cria as opções do Chrome.

    Cada instância usa um perfil próprio para poder rodar em paralelo sem
    disputar o mesmo diretório de dados, e o log de performance do Chrome
    DevTools fica habilitado para capturar a requisição do .m3u8.
    """
    opcoes = Options()
    opcoes.add_argument("--headless=new")
    opcoes.add_argument("--no-sandbox")
    opcoes.add_argument("--disable-gpu")
    opcoes.add_argument("--window-size=1920,1080")
    opcoes.add_argument("--disable-dev-shm-usage")
    opcoes.add_argument("--autoplay-policy=no-user-gesture-required")
    opcoes.add_argument("--disable-blink-features=AutomationControlled")
    opcoes.add_argument("--lang=pt-BR")
    opcoes.add_argument("--user-data-dir=" + tempfile.mkdtemp(prefix="chrome-globo-"))
    opcoes.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    return opcoes

# URLs dos vídeos Globoplay
globoplay_urls = [
    "https://rdcanais.com/casadopatrao1",
    "https://ge.globo.com/motor/formula-1/video/formula-1-no-sportv-2026-12749215.ghtml",
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


def m3u8_valido(endereco):
    """Aceita apenas manifests do Globo.

    O player também carrega manifests de anúncio hospedados em
    redirector.gvt1.com/googlevideo.com, que não transmitem o canal.
    """
    if any(
        bloqueado in endereco
        for bloqueado in (
            "redirector.gvt1.com",
            "googlevideo.com",
            "dclk_video_ads",
            "/api/manifest/",
        )
    ):
        return False

    return ".m3u8" in endereco


def capturar_requisicoes(driver):
    """Lê o log de performance do Chrome e devolve (m3u8, thumbnail).

    O player atual não registra o .m3u8 em performance.getEntriesByType(),
    por isso a captura é feita pelas mensagens de rede do CDP.
    """
    m3u8_url = None
    thumbnail_url = None

    for entry in driver.get_log("performance"):
        try:
            mensagem = json.loads(entry["message"])["message"]
        except Exception:
            continue

        if mensagem.get("method") not in (
            "Network.requestWillBeSent",
            "Network.responseReceived",
        ):
            continue

        parametros = mensagem["params"]
        pedido = parametros.get("request") or parametros.get("response") or {}
        endereco = pedido.get("url", "")

        if ".m3u8" in endereco and not m3u8_url and m3u8_valido(endereco):
            m3u8_url = endereco

        if ".jpg" in endereco and not thumbnail_url:
            thumbnail_url = endereco

    return m3u8_url, thumbnail_url


def extract_globoplay_data(url, tentativas=3):
    for tentativa in range(tentativas):
        driver = None
        try:
            driver = webdriver.Chrome(options=criar_opcoes())
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

            # aguarda o player carregar e fazer a requisição do .m3u8
            time.sleep(15)

            title = driver.title
            m3u8_url, thumbnail_url = capturar_requisicoes(driver)

            if m3u8_url:
                return title, m3u8_url, thumbnail_url

            print(f"M3U8 não capturado ({tentativa + 1}/{tentativas}): {url}")

        except Exception as e:
            print(f"Erro ao processar {url}: {e}")

        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass

    return None, None, None


EPG_SPORTV = "sportv"
EPG_GE = "ge-tv"
EPG_GLOBO = "tv-globo"
# G1 (GloboNews) tem grade propria: nao usar a grade geral de TV
EPG_G1 = "globonews"
# grade da afiliada de Sao Paulo (claro.xml)
EPG_GLOBO_SP = "GLOBO SP"

CANAIS_SPORTV = ("spo", "sportv", "sptv")
CANAIS_GE = ("ge", "gehd", "ge-hd", "ber1")
CANAIS_GLOBO = ("glb", "globo", "globo-rj", "globorj", "tv-globo", "abtv")
# slugs da afiliada de Sao Paulo (tem id proprio em claro.xml)
CANAIS_GLOBO_SP = ("glb", "globo-sp", "globosp", "tv-globo-sp")
CANAIS_G1_PREFIXO = ("g1", "rede", "tvl", "nsc", "tvvm", "vanguarda")
# slugs G1 regionais que comecam por "globo" e cairiam em CANAIS_GLOBO
CANAIS_G1_EXATOS = ("globo-rs1",)


def obter_tvg_id(m3u8_url, title):
    """Retorna o tvg-id existente no EPG do BrazilTVEPG ou "" quando o canal
    não existe nas fontes (CBN e canais sem equivalente), evitando associá-lo
    ao canal errado."""
    texto = unquote(m3u8_url)
    match = re.search(r"/live/f[^/]*/([^/]+)/", texto)
    canal = match.group(1).lower() if match else ""
    titulo = (title or "").lower()
    # titulo sem acentos para comparar nomes ("Globo Sao Paulo")
    titulo_simples = "".join(
        c for c in unicodedata.normalize("NFKD", titulo) if not unicodedata.combining(c)
    )

    if any(canal.startswith(p) for p in CANAIS_SPORTV) or "sportv" in titulo:
        return EPG_SPORTV
    if any(canal == p or canal.startswith(p + "-") for p in CANAIS_GE) or "ge.globo" in titulo:
        return EPG_GE
    if canal in CANAIS_G1_EXATOS or canal.startswith(CANAIS_G1_PREFIXO):
        return EPG_G1
    if re.search(r"\bg1\b", titulo):
        return EPG_G1
    if canal in CANAIS_GLOBO_SP or "globo sao paulo" in titulo_simples:
        return EPG_GLOBO_SP
    if any(canal.startswith(p) for p in CANAIS_GLOBO) or "abtv" in titulo:
        return EPG_GLOBO

    return ""


# Nome amigável de cada canal (o título da página do Globoplay é longo e
# muda com frequência, por isso o nome é fixado pelo slug do stream).
NOMES_CANAIS = {
    "spo": "SporTV",
    "glb": "Globo São Paulo",
    "abtv": "Globo Alagoas",
    "ber1": "ge",
    "gehd": "ge HD",
    "g1rj1": "G1 Rio de Janeiro",
    "jb1": "G1 ao vivo",
    "g1caruaru": "G1 Caruaru",
    "globo-rs1": "G1 Rio Grande do Sul",
    "rbsrsesporte": "G1 Rio Grande do Sul",
    "nscscatarina": "G1 Santa Catarina",
    "vanguarda1": "G1 Vanguarda",
    "tvvmcefor2": "G1 Ceará",
    "g1tvgazetaes": "G1 Espírito Santo",
    "g1integramgube": "G1 Triângulo Mineiro",
    "g1integramguba": "G1 Triângulo Mineiro - Uberaba",
    "redeap": "G1 Amapá",
    "redeac": "G1 Acre",
    "tvliberal": "G1 Pará",
    "cbnsp24ha": "CBN São Paulo",
    "cbnrj24ha": "CBN Rio de Janeiro",
}


def obter_nome(m3u8_url, title):
    """Nome amigável do canal a partir do slug; usa o título como fallback."""
    texto = unquote(m3u8_url)
    match = re.search(r"/live/f[^/]*/([^/]+)/", texto)
    canal = match.group(1).lower() if match else ""

    # o ge.globo e o "Agora no g1" usam o mesmo slug (gehd); mantém os dois nomes
    if canal == "gehd" and "ge.globo" in (title or "").lower():
        return "ge"

    return NOMES_CANAIS.get(canal, title)


def stream_ativo(m3u8_url):
    """Confere se o manifest responde 200 antes de publicar o canal."""
    try:
        requisicao = urllib.request.Request(m3u8_url, method="GET")
        with urllib.request.urlopen(requisicao, timeout=15) as resposta:
            return resposta.status == 200
    except Exception:
        return False


EPG_URLS = (
    "https://github.com/limaalef/BrazilTVEPG/raw/refs/heads/main/globo.xml",
    "https://github.com/limaalef/BrazilTVEPG/raw/refs/heads/main/claro.xml",
    "https://github.com/limaalef/BrazilTVEPG/raw/refs/heads/main/vivoplay.xml",
)

# M3U canonico: url-tvg com as 3 fontes XMLTV separadas por espaco (sem x-tvg-url)
HEADER = "#EXTM3U url-tvg=\"%s\"" % " ".join(EPG_URLS)


def generate_m3u():
    linhas = [HEADER]
    canais = 0

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
                    if not stream_ativo(m3u8_url):
                        print(f"Stream indisponível, ignorado: {url}")
                        continue

                    thumbnail_url = thumbnail_url or ""

                    tvg_id = obter_tvg_id(m3u8_url, title)
                    nome = obter_nome(m3u8_url, title)
                    atributo_tvg_id = f' tvg-id="{tvg_id}"' if tvg_id else ""

                    linhas.append(
                        f'#EXTINF:-1{atributo_tvg_id} tvg-name="{nome}" '
                        f'tvg-logo="{thumbnail_url}" group-title="GLOBO AO VIVO",{nome}'
                    )
                    linhas.append(m3u8_url)
                    canais += 1

                    print(f"Processado: {url}")

                else:
                    print(f"M3U8 não encontrado: {url}")

            except Exception as e:
                print(f"Erro ao finalizar {url}: {e}")

    if not canais:
        print("Nenhum canal encontrado: lista1.m3u mantida sem alterações.")
        return

    with open("lista1.m3u", "w", encoding="utf-8") as output_file:
        output_file.write("\n".join(linhas) + "\n")

    print(f"lista1.m3u gerado com {canais} canais.")


# Executa
if __name__ == "__main__":
    generate_m3u()
