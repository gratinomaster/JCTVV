#!/usr/bin/env python3
"""Corrige o lista1.m3u: header url-tvg e tvg-ids validos contra as 3 fontes EPG."""
import datetime
import os
import re
import shutil
import ssl
import time
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET

M3U = "lista1.m3u"
BASE = "https://github.com/limaalef/BrazilTVEPG/raw/refs/heads/main/"
EPG_URLS = [BASE + "globo.xml", BASE + "claro.xml", BASE + "vivoplay.xml"]
CACHE = "/tmp/opencode/epg_cache"
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

RAIZ = os.path.dirname(os.path.abspath(__file__))
ARQUIVO_M3U = os.path.join(RAIZ, M3U)
RELATORIO = os.path.join(RAIZ, "relatorio_lista1_epg.txt")

# canais do lista1 sem id proprio nas 3 fontes -> id oficial da emissora
# (G1 regionais e afiliadas usam a grade nacional) ou sem tvg-id (radio)
ALIAS = {
    "ge": "ge-tv",
    "gehd": "ge-tv",
    "globoalagoas": "tv-globo",
    "globosaopaulo": "tv-globo",
    "cbnriodejaneiro": None,
    "cbnsaopaulo": None,
}

RE_ID = re.compile(r'\s*tvg-id="[^"]*"')
RE_NOME = re.compile(r'^(#EXTINF[^\n]*),(.+)$')


def normaliza(texto):
    """minusculas, sem acento e sem caracteres nao alfanumericos"""
    texto = unicodedata.normalize("NFKD", str(texto))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", texto.lower())


def baixa_epg(url):
    """baixa (com cache) uma fonte XMLTV e devolve os ids de canal"""
    os.makedirs(CACHE, exist_ok=True)
    cache = os.path.join(CACHE, url.rsplit("/", 1)[-1])
    if not os.path.exists(cache) or time.time() - os.path.getmtime(cache) > 3600:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=180, context=SSL_CTX) as resp:
            with open(cache, "wb") as fh:
                shutil.copyfileobj(resp, fh)
    ids = {}
    for _ev, el in ET.iterparse(cache, events=("end",)):
        if el.tag == "channel":
            ids[el.get("id")] = el.findtext("display-name") or ""
        el.clear()
    return ids


def carrega_fontes():
    """ids de canal das 3 fontes, na ordem de preferencia do header"""
    fontes = []
    for url in EPG_URLS:
        nome = url.rsplit("/", 1)[-1].replace(".xml", "")
        ids = baixa_epg(url)
        print(f"  {nome}: {len(ids)} canais")
        fontes.append((nome, ids))
    return fontes


def id_por_nome(nome, fontes):
    """id correto para o canal, ou None se nao existir nas 3 fontes"""
    alvo = normaliza(nome)
    if alvo in ALIAS:
        return ALIAS[alvo]
    # G1 regionais e afiliadas da Rede Globo usam a grade nacional
    if alvo.startswith("g1") or alvo.startswith("globo"):
        return "tv-globo"
    for _fonte, ids in fontes:
        for cid, display in ids.items():
            if normaliza(display) == alvo or normaliza(cid) == alvo:
                return cid
    return None


def corrige():
    print("baixando fontes EPG:")
    fontes = carrega_fontes()
    todos = {cid for _f, ids in fontes for cid in ids}

    with open(ARQUIVO_M3U, encoding="utf-8") as fh:
        linhas = fh.read().splitlines()

    header = "#EXTM3U url-tvg=\"" + " ".join(EPG_URLS) + '"'
    stamp = time.strftime("%Y%m%d_%H%M%S")
    backup = os.path.join(RAIZ, f"lista1.m3u.bak.pre_urltvg_tvgids_{stamp}")
    shutil.copy2(ARQUIVO_M3U, backup)

    alterados = 0
    linhas_novas = []
    log = []

    for linha in linhas:
        if linha.startswith("#EXTM3U"):
            if linha != header:
                alterados += 1
                log.append(f"header: {linha} -> {header}")
            linhas_novas.append(header)
            continue

        m = RE_NOME.match(linha)
        if not m:
            linhas_novas.append(linha)
            continue

        prefixo, nome = m.group(1), m.group(2).strip()
        atual = RE_ID.search(prefixo)
        atual = atual.group(0).strip() if atual else None
        atual_id = atual.split("=", 1)[1].strip('"') if atual else None

        correto = id_por_nome(nome, fontes)
        if correto is None and atual_id in todos:
            correto = atual_id

        if correto != atual_id:
            alterados += 1
            log.append(f"{nome}: {atual_id or '(sem id)'} -> {correto or '(sem id)'}")

        prefixo = prefixo.rstrip()
        if correto:
            # substitui o id no lugar, preservando a ordem dos atributos
            if atual:
                prefixo = RE_ID.sub(f' tvg-id="{correto}"', prefixo)
            else:
                prefixo = prefixo.replace("#EXTINF:-1 ", f'#EXTINF:-1 tvg-id="{correto}" ', 1)
        else:
            prefixo = RE_ID.sub("", prefixo).rstrip()

        fontes_id = [f for f, ids in fontes if correto in ids]
        log.append(
            f"  {nome} | {correto or '(sem id)'} | "
            + ("ok (" + ",".join(fontes_id) + ")" if correto and fontes_id
               else "sem id (nao existe nas 3 fontes)")
        )
        linhas_novas.append(f"{prefixo},{nome}")

    with open(ARQUIVO_M3U, "w", encoding="utf-8") as fh:
        fh.write("\n".join(linhas_novas) + "\n")

    relatorio = [
        f"lista1.m3u - correcao de url-tvg e tvg-ids ({stamp})",
        "Fontes: " + ", ".join(EPG_URLS),
        "",
        f"Backup: {os.path.basename(backup)}",
        f"Header: {header}",
        "",
        "Validacao de tvg-id (ids existentes nas 3 fontes EPG):",
    ] + log + [f"Alteracoes aplicadas: {alterados}"]

    with open(RELATORIO, "w", encoding="utf-8") as fh:
        fh.write("\n".join(relatorio) + "\n")

    print()
    print("\n".join(relatorio))
    print(f"\nM3U: {ARQUIVO_M3U}")
    print(f"Relatorio: {RELATORIO}")
    return 0


if __name__ == "__main__":
    raise SystemExit(corrige())
