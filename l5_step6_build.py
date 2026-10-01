#!/usr/bin/env python3
"""Passo 6 - gera lista5.m3u final + EPG local filtrado (3 dias).

Canais = 4 (ABC News Live, FOX News, FOX Business, CBS News 24/7).
Fontes/afiliadas mantidas separadamente, todas com tvg-id do EPG.
"""
import gzip
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from datetime import date, timedelta

SRC = "lista5.m3u"
EPG_PRIM = "https://iptv-epg.org/files/epg-us.xml.gz"
EPG_SEC = "https://epgshare01.online/epgshare01/epg_ripper_ALL_SOURCES1.xml.gz"
EPG_LOCAL_CACHE = "/tmp/opencode/8cffd98f.gz"

# tvg-ids confirmados com D0/D+1/D+2 em iptv-epg.org
CANAIS = [
    {
        "chno": "1",
        "tvg_id": "ABCNewsLive.us",
        "nome": "ABC News Live",
        "origem": "Disney+ (dssott)",
        "logo": "https://s.abcnews.com/images/Live/abc_news_live-abc-ml-250210_1739199021469_hpMain_16x9_608.jpg",
        "host": "linear-abcnews-ftc-na-west-1.media.dssott.com",
        "match": "ctr-all-hdri-sliding.m3u8",
    },
    {
        "chno": "2",
        "tvg_id": "ABCNewsLive.us",
        "nome": "ABC News Live",
        "origem": "ABC News (Akamai)",
        "logo": "https://keyframe-cdn.abcnews.com/streamprovider10.jpg",
        "host": "abcnews-livestreams.akamaized.net",
        "match": "abcn-live-10-index.m3u8",
    },
    {
        "chno": "3",
        "tvg_id": "FoxNewsChannel.us",
        "nome": "FOX News",
        "origem": "FOX News (oficial)",
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/15de0523-3be4-4a9a-8159-7020114e7036/b6ff623a-26d6-4fd9-8bb8-0856adbf38ce/1280x720/match/676/380/image.jpg?ve=1&tl=1",
        "host": "247.foxnews.com",
        "match": "2003586/FNCHLSv3/master.m3u8",
    },
    {
        "chno": "4",
        "tvg_id": "FoxBusiness.us",
        "nome": "FOX Business",
        "origem": "FOX Business (oficial)",
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/c9b2e2eb-7b87-435c-9510-eab2650ff944/8b584585-acf2-4c37-aa07-aaf2d077bb20/1280x720/match/676/380/image.jpg?ve=1&tl=1",
        "host": "247.foxbusiness.com",
        "match": "2003756/FBNHLSv3/master.m3u8",
    },
    {
        "chno": "5",
        "tvg_id": "CBSNews.us",
        "nome": "CBS News 24/7",
        "origem": "Pluto TV (DAI)",
        "logo": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
        "host": "dai.google.com",
        "match": ":DLS/master.m3u8",
    },
]

GRUPO = "NEWS WORLD"


def parse(src):
    """Devolve [(extinf, url)] preservando ordem."""
    out, cur = [], None
    for ln in open(src, encoding="utf-8", errors="replace"):
        s = ln.strip()
        if s.startswith("#EXTINF"):
            cur = s
        elif s and not s.startswith("#"):
            out.append((cur or "", s))
            cur = None
    return out


def escolhe(entradas, canal):
    """Pega a URL viva que casa com host+match preferindo master."""
    cands = [u for _, u in entradas if canal["host"] in u]
    exact = [u for u in cands if canal["match"] in u]
    return (exact or cands or [None])[0]


def gera_m3u(entradas):
    linhas = [
        f'#EXTM3U url-tvg="{EPG_PRIM} {EPG_SEC}" '
        f'x-tvg-url="{EPG_PRIM} {EPG_SEC}" catchup="append" '
        'catchup-source="" catchup-days="3"'
    ]
    usados = set()
    for c in CANAIS:
        url = escolhe(entradas, c)
        if not url:
            print(f"  !! sem URL para {c['nome']} ({c['origem']}) - PULADO")
            continue
        usados.add(url)
        nome = (f'{c["nome"]} [{c["origem"]}]' if c["origem"] != "oficial"
                else c["nome"])
        linhas.append(
            f'#EXTINF:-1 tvg-id="{c["tvg_id"]}" tvg-chno="{c["chno"]}" '
            f'tvg-name="{c["nome"]}" tvg-logo="{c["logo"]}" '
            f'group-title="{GRUPO}",{nome}')
        linhas.append(url)
    return "\n".join(linhas) + "\n", usados


def gera_epg_local(destino, dias=3):
    """Extrai do EPG primario so os tvg-id usados, com D0..D+2."""
    ids = {c["tvg_id"] for c in CANAIS}
    hoje = date.today()
    alvo = {hoje + timedelta(i) for i in range(dias)}
    ch_blk, pr_blk = [], []
    buf, cap = [], False
    with gzip.open(EPG_LOCAL_CACHE, "rt", encoding="utf-8",
                   errors="replace") as f:
        for line in f:
            ls = line.strip()
            if ls.startswith("<channel ") or ls.startswith("<programme "):
                buf, cap = [ls], True
                continue
            if cap:
                buf.append(ls)
                if (ls.startswith("</channel>") or ls.startswith("</programme>")):
                    bloco = "\n".join(buf)
                    if ls.startswith("</channel>"):
                        m = re.search(r'channel id="([^"]+)"', bloco)
                        if m and m.group(1) in ids:
                            ch_blk.append(re.sub(r"\s+", " ", bloco))
                    else:
                        m = re.search(r'channel="([^"]+)"', bloco)
                        s = re.search(r'start="(\d{8})', bloco)
                        if m and s and m.group(1) in ids:
                            try:
                                d = date(int(s.group(1)[:4]),
                                         int(s.group(1)[4:6]),
                                         int(s.group(1)[6:8]))
                            except ValueError:
                                d = None
                            if d in alvo:
                                pr_blk.append(re.sub(r"\s+", " ", bloco))
                    buf, cap = [], False

    with open(destino, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<!DOCTYPE tv SYSTEM "xmltv.dtd">\n<tv generator-info-info="'
                'lista5 epg filtrado">\n')
        f.write("\n".join(ch_blk) + "\n")
        f.write("\n".join(pr_blk) + "\n")
        f.write("</tv>\n")
    return len(ch_blk), len(pr_blk)


if __name__ == "__main__":
    stamp = subprocess.run(["date", "+%Y%m%d_%H%M%S"], capture_output=True,
                           text=True).stdout.strip()
    shutil.copy(SRC, f"{SRC}.bak.{stamp}")
    print(f"backup: {SRC}.bak.{stamp}")

    entradas = parse(SRC)
    m3u, usados = gera_m3u(entradas)
    open(SRC, "w", encoding="utf-8").write(m3u)
    print(f"{SRC}: {len(entradas)} entradas -> "
          f"{m3u.count('#EXTINF')} canais, "
          f"{len({u for _, u in entradas}) - len(usados)} URLs descartadas")

    nc, np_ = gera_epg_local("l5_epg.xml")
    print(f"l5_epg.xml: {nc} canais, {np_} programas (D0..D+2)")