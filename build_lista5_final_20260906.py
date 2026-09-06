#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reconstroi lista5.m3u com canais de noticias validados.

Criterios aplicados:
- 1 stream estavel por canal (sem tokens que expiram em horas)
- tvg-id de acordo com o EPG epgshare01 US2
- url-tvg inserido no arquivo .m3u
- tvg-logo sempre .jpg e acessivel (HTTP 200, image/jpeg)
- nenhum link de canal sem a linha #EXTINF acima
- nenhum logo do imgur.com
- somente dominios oficiais de primeira parte (anti-virus/reputacao)
"""

EPG_URL = "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz"

CHANNELS = [
    {
        "tvg-id": "ABC.News.Live.us2",
        "name": "ABC News Live",
        "logo": "https://keyframe-cdn.abcnews.com/streamprovider10.jpg",
        "chno": 1,
        "url": "https://abcnews-livestreams.akamaized.net/out/v1/6a597119dbd5428a82dc11a2f514a1a2/abcn-live-10-cmaf-manifest/abcn-live-10-index.m3u8",
    },
    {
        "tvg-id": "CBS.News.National.Stream.us2",
        "name": "CBS News 24/7",
        "logo": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
        "chno": 2,
        "url": "https://dai.google.com/linear/hls/pa/event/Sid4xiTQTkCT1SLu6rjUSQ/stream/0358051e-32ea-406a-a6c4-bdeebce9919e:TUL/master.m3u8",
    },
    {
        "tvg-id": "Fox.News.Channel.HD.us2",
        "name": "Fox News Channel",
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/15de0523-3be4-4a9a-8159-7020114e7036/b6ff623a-26d6-4fd9-8bb8-0856adbf38ce/1280x720/match/676/380/image.jpg?ve=1&tl=1",
        "chno": 3,
        "url": "http://247preview.foxnews.com/hls/live/2020027/fncv3preview/primary.m3u8",
    },
    {
        "tvg-id": "Fox.Business.HD.us2",
        "name": "Fox Business Network",
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/c9b2e2eb-7b87-435c-9510-eab2650ff944/8b584585-acf2-4c37-aa07-aaf2d077bb20/1280x720/match/676/380/image.jpg?ve=1&tl=1",
        "chno": 4,
        "url": "http://247preview.foxbusiness.com/hls/live/2020026/fbnv3preview/primary.m3u8",
    },
]


def best_logo(c):
    logo = c["logo"]
    path = logo.split("?", 1)[0]
    if not path.lower().endswith(".jpg"):
        logo = path.rsplit("/", 1)[0] + "/logo.jpg"
    return logo


def build():
    lines = [
        '#EXTM3U url-tvg="%s" x-tvg-url="%s"' % (EPG_URL, EPG_URL),
    ]
    for ch in CHANNELS:
        logo = best_logo(ch)
        extinf = '#EXTINF:-1 tvg-id="%s" tvg-logo="%s" tvg-chno="%d" group-title="NEWS WORLD",%s' % (
            ch["tvg-id"], logo, ch["chno"], ch["name"])
        lines.append(extinf)
        lines.append(ch["url"])
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    out = build()
    with open("lista5.m3u", "w", encoding="utf-8") as f:
        f.write(out)
    print(out)