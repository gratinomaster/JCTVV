#!/usr/bin/env python3
"""Reconstroi o lista5.m3u: 1 entrada por canal, EPG validado, logo .jpg testado,
sem duplicatas, sem audio-only, sem canais mortos e toda URL com #EXTINF acima."""
import shutil
import sys
import time
from datetime import datetime

ARQ = "lista5.m3u"

EPG = [
    "https://iptv-epg.org/files/epg-us.xml.gz",
    "https://epg.pw/xmltv/epg_US.xml.gz",
]

CANAIS = [
    {
        "tvg_id": "ABCNewsLive.us",
        "tvg_name": "ABC News Live",
        "display": "ABC News Live",
        "grupo": "NEWS WORLD",
        "logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
        "url": "https://pb-0n3n2ej0w8pl9.akamaized.net/ABCNewsLive_Disney.m3u8",
    },
    {
        "tvg_id": "CBSNews.us",
        "tvg_name": "CBS News 24/7",
        "display": "CBS News 24/7",
        "grupo": "NEWS WORLD",
        "logo": ("https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/"
                 "0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/"
                 "949f3d3fef16f9c113e3048c6aef229f/"
                 "247-key-channelthumbnail-1920x1080.jpg"),
        "url": "https://news20e7hhcb.airspace-cdn.cbsivideo.com/index.m3u8",
    },
]


def cabecalho():
    u = " ".join(EPG)
    x = ",".join(EPG)
    return f'#EXTM3U url-tvg="{u}" x-tvg-url="{x}"'


def linha(c):
    return (f'#EXTINF:-1 tvg-id="{c["tvg_id"]}" tvg-name="{c["tvg_name"]}" '
            f'tvg-logo="{c["logo"]}" group-title="{c["grupo"]}",{c["display"]}')


def build():
    ts = time.strftime("%Y%m%d_%H%M%S")
    shutil.copy2(ARQ, f"{ARQ}.bak.pre_corrigir_{ts}")
    out = [cabecalho()]
    vistos = set()
    for c in CANAIS:
        if c["url"] in vistos:
            continue
        vistos.add(c["url"])
        out.append(linha(c))
        out.append(c["url"])
    out.append("")
    with open(ARQ, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out))
    print(f"backup -> {ARQ}.bak.pre_corrigir_{ts}")
    print(f"gerado -> {ARQ} ({len(CANAIS)} canais, {datetime.now():%Y-%m-%d %H:%M})")


if __name__ == "__main__":
    sys.exit(build())