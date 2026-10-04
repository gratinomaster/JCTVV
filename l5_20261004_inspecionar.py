#!/usr/bin/env python3
"""Inspecao profunda das URLs candidatas: master completo + teste de segmentos com audio."""
import sys
from urllib.parse import urljoin

import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
H = {"User-Agent": UA, "Accept": "*/*"}

TARGETS = [
    ("FOX NEWS preview", "https://247preview.foxnews.com/hls/live/2020027/fncv3preview/primary.m3u8"),
    ("FBN preview", "https://247preview.foxbusiness.com/hls/live/2020026/fbnv3preview/primary.m3u8"),
    ("ABC akam", "https://abcnews-livestreams.akamaized.net/out/v1/6a597119dbd5428a82dc11a2f514a1a2/abcn-live-10-cmaf-manifest/abcn-live-10-index.m3u8"),
]


def deepest(u, label, depth=0, seen=None):
    seen = seen or set()
    if depth > 2 or u in seen:
        return
    seen.add(u)
    try:
        r = requests.get(u, headers=H, timeout=20)
    except Exception as e:
        print(f"    [{label}] erro {type(e).__name__}")
        return
    print(f"    [{label}] http={r.status_code} url_final={r.url[:100]}")
    txt = r.text
    lines = [l.strip() for l in txt.splitlines() if l.strip()]
    for l in lines[:40]:
        print(f"      | {l[:150]}")
    # segmentos
    segs = []
    for i, l in enumerate(lines):
        if l.startswith("#EXT-X-MAP:"):
            segs.append(urljoin(r.url, l.split("URI=", 1)[1].split(",")[0].strip('"')))
        elif not l.startswith("#") and i and lines[i - 1].startswith("#EXTINF"):
            segs.append(urljoin(r.url, l))
    if segs:
        for s in segs[:2]:
            try:
                rs = requests.get(s, headers={**H, "Range": "bytes=0-200000"}, timeout=20)
                head = rs.content[:4]
                print(f"      SEG http={rs.status_code} bytes={len(rs.content)} magic={head!r} {s.split('/')[-1][:60]}")
            except Exception as e:
                print(f"      SEG erro {type(e).__name__}")
    for i, l in enumerate(lines):
        if l.startswith("#EXT-X-STREAM-INF") and i + 1 < len(lines) and not lines[i + 1].startswith("#"):
            if depth < 1:
                deepest(urljoin(r.url, lines[i + 1]), f"{label}/variante", depth + 1, seen)


for name, u in TARGETS:
    print("=" * 100)
    print(name, u)
    deepest(u, "master")