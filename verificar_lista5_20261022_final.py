#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verificacao final independente da lista5 (nao modifica a lista).

Confere, para cada canal da lista:
  - URL de stream reproduzivel (manifest -> master -> variante -> bytes de midia)
  - tvg-id presente no EPG publicado com programacao de hoje, amanha e depois de amanha
  - tvg-logo .jpg (sem imgur.com) e servida com conteudo JPEG
  - cada URL de stream imediatamente abaixo de uma linha #EXTINF
  - cabecalho com x-tvg-url apontando para o EPG publicado
"""
import datetime
import gzip
import re
import sys
from urllib.parse import urlparse

import requests

from testar_lista5_20261022 import (
    fetch,
    parse_master,
    validate_audio_rendition,
    validate_media_playlist,
)

LISTA = "lista5.m3u"
EPG_URL = "https://raw.githubusercontent.com/gratinomaster/JCTVV/main/lista5_epg.xml.gz"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
H = {"User-Agent": UA, "Accept": "*/*", "Connection": "close"}


def check_channel(url):
    """Retorna (ok, detalhe)."""
    r = fetch(url)
    if r.status_code != 200:
        return False, f"HTTP {r.status_code}"
    text = r.text
    if "#EXTM3U" not in text[:2000]:
        return False, "nao e playlist HLS"
    if "#EXT-X-KEY:" in text or "#EXT-X-SESSION-KEY:" in text:
        return False, "protegido (DRM)"

    if "#EXT-X-STREAM-INF" in text:
        variants, audios = parse_master(text, r.url)
        if not variants:
            return False, "master sem variantes"
        for v in variants[:5]:
            pr = fetch(v["url"])
            if pr.status_code != 200 or "#EXTM3U" not in pr.text[:2000]:
                continue
            ok, kind, why = validate_media_playlist(pr.url, pr.text, v.get("codecs"))
            if not ok:
                continue
            if kind == "video+audio":
                return True, f"master->variante {v['bw'] // 1000}kbps | {why}"
            if kind != "video":
                continue
            aud = [a for a in audios if v["audio_group"] and a["group"] == v["audio_group"]]
            for a in aud[:2]:
                aok, awhy = validate_audio_rendition(a["url"])
                if aok:
                    return True, f"master->variante {v['bw'] // 1000}kbps | {why} | {awhy}"
        return False, "nenhuma variante reproduzivel"

    ok, kind, why = validate_media_playlist(r.url, text)
    if not ok:
        return False, why
    if kind == "video+audio":
        return True, f"playlist direta | {why}"
    return False, f"playlist direta | {why} (sem audio+video)"


def parse_lista(path):
    """Retorna (canais, problemas_de_estrutura)."""
    linhas = open(path, encoding="utf-8").read().splitlines()
    canais, problemas = [], []
    header = linhas[0] if linhas else ""
    if not header.startswith("#EXTM3U"):
        problemas.append("primeira linha nao e #EXTM3U")
    if "x-tvg-url" not in header:
        problemas.append("cabecalho sem x-tvg-url")
    for i, l in enumerate(linhas):
        if l.startswith("http"):
            anterior = linhas[i - 1] if i else ""
            if not anterior.startswith("#EXTINF"):
                problemas.append(f"linha {i + 1}: URL sem #EXTINF acima")
            if len(linhas) > i + 1 and linhas[i + 1].startswith("http"):
                problemas.append(f"linha {i + 1}: URL seguida de outra URL")
    cur = None
    for l in linhas:
        if l.startswith("#EXTINF"):
            cur = {"extinf": l, "url": None}
            canais.append(cur)
        elif cur is not None and l.startswith("http") and cur["url"] is None:
            cur["url"] = l
    return canais, problemas, header


def main():
    canais, problemas, header = parse_lista(LISTA)
    print(f"Lista: {LISTA}")
    print(f"EPG:   {EPG_URL}")
    print(f"Header: {header[:120]}\n")

    resp = requests.get(EPG_URL, timeout=90)
    if resp.status_code != 200:
        print(f"FALHA ao baixar o EPG publicado: HTTP {resp.status_code}")
        return 1
    epg = gzip.decompress(resp.content).decode("utf-8", "ignore")
    hoje = datetime.datetime.now(datetime.timezone.utc).date()
    dias = [(hoje + datetime.timedelta(days=i)).strftime("%Y%m%d") for i in range(3)]

    allok = True
    for e in canais:
        title = e["extinf"].split(",", 1)[1].strip() if "," in e["extinf"] else e["extinf"]
        tvg = re.search(r'tvg-id="([^"]*)"', e["extinf"])
        tvg = tvg.group(1) if tvg else ""
        logo = re.search(r'tvg-logo="([^"]*)"', e["extinf"])
        logo = logo.group(1) if logo else ""

        if not e["url"]:
            print(f"[FALHA] {title}\n        sem URL de stream")
            allok = False
            continue

        ok, detail = check_channel(e["url"])
        allok = allok and ok

        if tvg:
            ids = re.findall(r'<channel id="%s">' % re.escape(tvg), epg)
            cont = []
            for d in dias:
                n = len(re.findall(
                    r'<programme start="%s[^"]*"[^>]*channel="%s"' % (d, re.escape(tvg)), epg))
                cont.append(f"{d}={n}")
            epg_ok = bool(ids) and all(int(c.split("=")[1]) > 0 for c in cont)
            allok = allok and epg_ok
            st = f"epg canal={'sim' if ids else 'NAO'} | " + " ".join(cont)
        else:
            st = "sem tvg-id"
            allok = False

        lstat = "sem logo"
        if logo:
            if "imgur.com" in logo.lower():
                lstat = "logo no imgur (proibido)"
                allok = False
            elif not logo.lower().split("?")[0].endswith(".jpg"):
                lstat = "logo nao e .jpg"
                allok = False
            else:
                try:
                    lr = requests.get(logo, headers=H, timeout=25)
                    jpeg = lr.content.startswith(b"\xff\xd8\xff")
                    lstat = f"logo HTTP {lr.status_code} JPEG={jpeg}"
                    if lr.status_code != 200 or not jpeg:
                        allok = False
                except Exception as ex:
                    lstat = f"logo erro {type(ex).__name__}"
                    allok = False

        print(f"[{'OK  ' if ok else 'FALHA'}] {title}")
        print(f"        stream: {detail}")
        print(f"        {st} | {lstat}")
        print(f"        {e['url'][:110]}\n")

    if problemas:
        allok = False
        print("PROBLEMAS DE ESTRUTURA:")
        for p in problemas:
            print(f"  - {p}")
        print()

    print("RESULTADO:", "todos os canais funcionam" if allok else "ha falhas")
    return 0 if allok else 1


if __name__ == "__main__":
    sys.exit(main())
