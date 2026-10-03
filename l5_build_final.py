#!/usr/bin/env python3
"""Rebuild lista5.m3u: valid updated EPG, verified streams, .jpg logos."""
import os, shutil, time

SRC = "lista5.m3u"
STAMP = time.strftime("%Y%m%d_%H%M%S")
BAK = f"lista5.m3u.bak.pre_corrigir_{STAMP}"

EPG = "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz"
GROUP = "NEWS WORLD"

CHANNELS = [
    {
        "name": "FOX News Channel",
        "tvg_id": "Fox.News.Channel.HD.us2",
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/15de0523-3be4-4a9a-8159-7020114e7036/b6ff623a-26d6-4fd9-8bb8-0856adbf38ce/1280x720/match/676/380/image.jpg?ve=1&tl=1",
        "url": "https://247preview.foxnews.com/hls/live/2020027/fncv3preview/index.m3u8",
    },
    {
        "name": "FOX Business",
        "tvg_id": "Fox.Business.HD.us2",
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/c9b2e2eb-7b87-435c-9510-eab2650ff944/8b584585-acf2-4c37-aa07-aaf2d077bb20/1280x720/match/676/380/image.jpg?ve=1&tl=1",
        "url": "https://247preview.foxbusiness.com/hls/live/2020026/fbnv3preview/index.m3u8",
    },
    {
        "name": "ABC News Live",
        "tvg_id": "ABC.News.Live.us2",
        "logo": "https://keyframe-cdn.abcnews.com/streamprovider10.jpg",
        "url": "https://abcnews-livestreams.akamaized.net/out/v1/6a597119dbd5428a82dc11a2f514a1a2/abcn-live-10-cmaf-manifest/abcn-live-10-index.m3u8",
    },
    {
        "name": "CBS News 24/7",
        "tvg_id": "CBS.News.National.Stream.us2",
        "logo": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
        "url": "https://cbsn-us-vtt.cbsnstream.cbsnews.com/out/v1/ef868690d34144509eda696884bf1619/master.m3u8",
    },
]


def main():
    if os.path.exists(SRC):
        shutil.copy2(SRC, BAK)
        print(f"backup -> {BAK}")

    out = [f'#EXTM3U url-tvg="{EPG}" x-tvg-url="{EPG}"']
    for c in CHANNELS:
        logo = c["logo"]
        if "imgur.com" in logo:
            raise SystemExit(f"imgur not allowed: {logo}")
        if ".jpg" not in logo.lower():
            raise SystemExit(f"logo not .jpg: {logo}")
        out.append(
            f'#EXTINF:-1 tvg-id="{c["tvg_id"]}" tvg-name="{c["name"]}" '
            f'tvg-logo="{logo}" group-title="{GROUP}",{c["name"]}'
        )
        out.append(c["url"])

    with open(SRC, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    print(f"wrote {SRC} with {len(CHANNELS)} channels")


if __name__ == "__main__":
    main()