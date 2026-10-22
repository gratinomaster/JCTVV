#!/usr/bin/env python3
"""Verificacao final independente do lista5.m3u (nao modifica a lista).

Para cada canal: manifest -> master -> melhor variante -> segmentos reais
(bytes de midia) + confere que o tvg-id existe no EPG publicado e tem
programacao de hoje.
"""
import gzip
import re
import sys
from datetime import datetime, timezone

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
            ok, kind, why = validate_media_playlist(pr.url, pr.text)
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


def main():
    lines = open(LISTA, encoding="utf-8").read().splitlines()
    entries = []
    cur = None
    for l in lines:
        if l.startswith("#EXTINF"):
            cur = {"extinf": l, "url": None}
            entries.append(cur)
        elif cur is not None and l.startswith("http"):
            cur["url"] = l

    epg = gzip.decompress(requests.get(EPG_URL, timeout=60).content).decode("utf-8", "ignore")
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    print(f"EPG: {EPG_URL}")
    print(f"Canais na lista: {len(entries)}\n")

    allok = True
    for e in entries:
        title = e["extinf"].split(",", 1)[1].strip() if "," in e["extinf"] else e["extinf"]
        tvg = re.search(r'tvg-id="([^"]*)"', e["extinf"])
        tvg = tvg.group(1) if tvg else ""
        logo = re.search(r'tvg-logo="([^"]*)"', e["extinf"])
        logo = logo.group(1) if logo else ""

        ok, detail = check_channel(e["url"])
        allok = allok and ok

        if tvg:
            ids = re.findall(r'<channel id="%s">' % re.escape(tvg), epg)
            progs = re.findall(
                r'<programme start="%s[^"]*"[^>]*channel="%s"' % (today, re.escape(tvg)), epg
            )
            st = f"epg canal={'sim' if ids else 'NAO'} | programas hoje={len(progs)}"
        else:
            st = "sem tvg-id"

        lstat = "sem logo"
        if logo:
            try:
                lr = requests.get(logo, headers=H, timeout=20, stream=True)
                lstat = f"logo {lr.status_code} {lr.headers.get('Content-Type', '')[:20]}"
                lr.close()
            except Exception as ex:
                lstat = f"logo erro {type(ex).__name__}"

        print(f"[{'OK  ' if ok else 'FALHA'}] {title}")
        print(f"        stream: {detail}")
        print(f"        {st} | {lstat}")
        print(f"        {e['url'][:110]}")

    print("\nRESULTADO:", "todos os canais funcionam" if allok else "ha canais com falha")
    return 0 if allok else 1


if __name__ == "__main__":
    sys.exit(main())
