#!/usr/bin/env python3
"""Monta a lista5.m3u final: streams aprovados + EPG + logos .jpg + estrutura."""
import json, re
from collections import OrderedDict

BASE = "/home/runner/work/JCTVV/JCTVV/"
EPG1 = "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz"
EPG2 = "https://epg.pw/xmltv/epg_US.xml.gz"
EPGS = f"{EPG1} {EPG2}"

LOGO = {
    "abc":  "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
    "cbs":  "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
    "foxn": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/15de0523-3be4-4a9a-8159-7020114e7036/b6ff623a-26d6-4fd9-8bb8-0856adbf38ce/1280x720/match/676/380/image.jpg",
    "foxb": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/c9b2e2eb-7b87-435c-9510-eab2650ff944/8b584585-acf2-4c37-aa07-aaf2d077bb20/1280x720/match/676/380/image.jpg",
}

CANAIS = [
    ("abc",  "ABC.News.Live.us2",        "ABC News Live",
     ["https://abcnews-livestreams.akamaized.net/out/v1/6a597119dbd5428a82dc11a2f514a1a2/abcn-live-10-cmaf-manifest/abcn-live-10-index.m3u8"]),
    ("cbs",  "CBS.News.National.Stream.us2", "CBS News National Stream",
     ["https://cbsn-us.cbsnstream.cbsnews.com/out/v1/55a8648e8f134e82a470f83d562deeca/master.m3u8",
      "https://cbsn-2.cbsnstream.cbsnews.com/out/v1/a6a897e8f4f74cfc896223dfd822482f/master.m3u8",
      "https://cbsn-us-vtt.cbsnstream.cbsnews.com/out/v1/ef868690d34144509eda696884bf1619/master.m3u8"]),
    ("foxn", "Fox.News.Channel.HD.us2",  "Fox News Channel HD",
     ["https://247preview.foxnews.com/hls/live/2020027/fncv3preview/primary.m3u8",
      "https://247preview.foxnews.com/hls/live/2020027/fncv3preview/index.m3u8"]),
    ("foxb", "Fox.Business.HD.us2",      "Fox Business HD",
     ["https://247preview.foxbusiness.com/hls/live/2020026/fbnv3preview/primary.m3u8",
      "https://247preview.foxbusiness.com/hls/live/2020026/fbnv3preview/index.m3u8"]),
]

# URLs aprovadas no teste de stream e no anti-virus
stream_ok = {u for u, v in json.load(open(BASE + "fase1_streams_20261008.json")).items() if v["ok"]}
cand_ok = {u for u, v in json.load(open(BASE + "fase2_candidatos_20261008.json")).items() if v["ok"]}
aprovadas = stream_ok | cand_ok

# links extras do ABC que passaram no teste (redundancia)
extra_abc = [u for u in stream_ok if "dssott.com" in u]
extra_abc.sort()

linhas = [f'#EXTM3U url-tvg="{EPGS}" x-tvg-url="{EPGS}"']
total = 0
for key, tid, tnome, urls in CANAIS:
    todas = list(urls) + (extra_abc if key == "abc" else [])
    perdidas = [u for u in todas if u not in aprovadas]
    assert not perdidas, f"URL nao aprovada: {perdidas}"
    for u in todas:
        linhas.append(
            f'#EXTINF:-1 tvg-id="{tid}" tvg-name="{tnome}" tvg-logo="{LOGO[key]}" '
            f'group-title="NEWS WORLD",{tnome}'
        )
        linhas.append(u)
        total += 1

saida = BASE + "lista5.m3u"
with open(saida, "w", encoding="utf-8") as f:
    f.write("\n".join(linhas) + "\n")
print(f"{saida}: {total} entradas, {len(linhas)} linhas")
for key, tid, tnome, urls in CANAIS:
    n = len(urls) + (len(extra_abc) if key == "abc" else 0)
    print(f"  {tnome:26} tvg-id={tid:30} links={n}")
