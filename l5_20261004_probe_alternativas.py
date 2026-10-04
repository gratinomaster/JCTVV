#!/usr/bin/env python3
"""Procura URLs alternativas que funcionem para Fox News / Fox Business / ABC News."""
import concurrent.futures
import sys

import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
H = {"User-Agent": UA, "Accept": "*/*"}

CANDS = [
    ("FOX NEWS 247 no-token", "https://247.foxnews.com/hls/live/2020027/FNCV3/master.m3u8"),
    ("FOX NEWS 247 hls3 no-token", "https://247.foxnews.com/hls/live/2003586/FNCHLSv3/master.m3u8"),
    ("FOX NEWS preview", "https://247preview.foxnews.com/hls/live/2020027/fncv3preview/primary.m3u8"),
    ("FOX NEWS 247 cdn 2003586 v3", "https://247.foxnews.com/hls/live/2020027/fncv3/master.m3u8"),
    ("FBN 247 no-token", "https://247.foxbusiness.com/hls/live/2003756/FBNHLSv3/master.m3u8"),
    ("FBN preview", "https://247preview.foxbusiness.com/hls/live/2020026/fbnv3preview/primary.m3u8"),
    ("FBN 247 2020026", "https://247.foxbusiness.com/hls/live/2020026/FBNV3/master.m3u8"),
    ("ABC akam master", "https://abcnews-livestreams.akamaized.net/out/v1/6a597119dbd5428a82dc11a2f514a1a2/abcn-live-10-cmaf-manifest/abcn-live-10-index.m3u8"),
]


def probe(item):
    name, url = item
    out = [name]
    try:
        r = requests.get(url, headers=H, timeout=20)
        out.append(f"http={r.status_code} ct={(r.headers.get('Content-Type') or '')[:30]}")
        body = r.text
        if r.status_code != 200 or "#EXTM3U" not in body[:2000]:
            out.append("NAO-PLAYLIST: " + body[:120].replace("\n", " "))
            return " | ".join(out)
        has_audio_group = "EXT-X-MEDIA" in body and "TYPE=\"AUDIO\"" in body
        out.append(f"media_audio_group={has_audio_group}")
        variants = []
        lines = [l.strip() for l in body.splitlines() if l.strip()]
        from urllib.parse import urljoin
        for i, l in enumerate(lines):
            if l.startswith("#EXT-X-STREAM-INF") and i + 1 < len(lines):
                nxt = lines[i + 1]
                if not nxt.startswith("#"):
                    bw = 0
                    for p in l.split(","):
                        if "BANDWIDTH=" in p:
                            bw = int(p.split("BANDWIDTH=")[1].split("-")[0])
                    variants.append((bw, urljoin(r.url, nxt)))
        variants.sort(reverse=True)
        out.append(f"variantes={len(variants)}")
        for bw, v in variants[:2]:
            try:
                rv = requests.get(v, headers=H, timeout=20)
                txt = rv.text
                codecs = [x.split("=")[1].strip('"') for x in txt.splitlines()
                          if x.startswith("#EXT-X-STREAM-INF") or x.startswith("#EXT-X-MAP:")]
                out.append(f"  var {bw//1000}k http={rv.status_code} codecs={codecs[:1]}")
                if "#EXT-X-KEY" in txt:
                    for l in txt.splitlines():
                        if l.startswith("#EXT-X-KEY"):
                            out.append("    " + l[:90])
                            break
            except Exception as e:
                out.append(f"  var {bw//1000}k erro={type(e).__name__}")
    except Exception as e:
        out.append(f"ERRO {type(e).__name__}: {e}")
    return "\n".join(out)


with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
    for res in ex.map(probe, CANDS):
        print(res)
        print("-" * 90)
sys.exit(0)