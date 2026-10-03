#!/usr/bin/env python3
"""Verificacao profunda: resolve variantes de master playlists e baixa segmentos reais."""
import concurrent.futures
import sys
from urllib.parse import urljoin

import requests

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
HEADERS = {"User-Agent": UA, "Accept": "*/*", "Connection": "close"}
TIMEOUT = (10, 15)

URLS = [
    "https://247.foxnews.com/hls/live/2003586/FNCHLSv3/master.m3u8?hdnea=exp=1791019732~acl=/*~hmac=027bbb37cd37d295372031db0ffb11e240a2e263596b04dc41fa8a6c8a9ae3d7",
    "https://247.foxbusiness.com/hls/live/2003756/FBNHLSv3/master.m3u8?hdnea=exp=1791019732~acl=/*~hmac=027bbb37cd37d295372031db0ffb11e240a2e263596b04dc41fa8a6c8a9ae3d7",
    "https://dai.google.com/linear/hls/pa/event/Sid4xiTQTkCT1SLu6rjUSQ/stream/6e8ebb92-5eca-44b5-ad6e-e9b70869ef71:TUL/master.m3u8",
]


def get(url, headers=None):
    h = dict(HEADERS)
    if headers:
        h.update(headers)
    return requests.get(url, headers=h, timeout=TIMEOUT, allow_redirects=True)


def variants(base, text):
    out = []
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    for i, l in enumerate(lines):
        if l.startswith("#EXT-X-STREAM-INF:") and i + 1 < len(lines):
            nxt = lines[i + 1]
            if not nxt.startswith("#"):
                out.append(urljoin(base, nxt))
    if not out:
        for l in lines:
            if l.startswith("#EXT-X-I-FRAME-STREAM-INF:"):
                uri = l.split("URI=", 1)[1].split(",")[0].strip().strip('"').strip("'")
                if uri:
                    out.append(urljoin(base, uri))
    if not out:
        for l in lines:
            if not l.startswith("#"):
                out.append(urljoin(base, l))
    return out


def segments(base, text, limit=2):
    out = []
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    for l in lines:
        if l.startswith("#EXT-X-MAP:"):
            uri = l.split("URI=", 1)[1].split(",")[0].strip().strip('"').strip("'")
            if uri:
                out.append(urljoin(base, uri))
    for i, l in enumerate(lines):
        if not l.startswith("#") and i and lines[i - 1].startswith("#EXTINF"):
            out.append(urljoin(base, l))
        if len(out) >= limit + 1:
            break
    return out[: limit + 1]


def deep(url):
    try:
        r = get(url)
    except Exception as e:
        return url, False, f"master erro={type(e).__name__}"
    if r.status_code >= 400:
        return url, False, f"master http={r.status_code}"

    text = r.content.decode("utf-8", "ignore")
    if "#EXTM3U" not in text[:4000]:
        return url, False, "master nao e HLS"

    if "#EXT-X-STREAM-INF" in text:
        vs = variants(r.url, text)
        if not vs:
            return url, False, "master sem variantes"
        best, best_bw = None, -1
        for v in vs:
            try:
                head = get(v)
                if head.status_code != 200:
                    continue
                bw = 0
                for ln in head.text.splitlines():
                    if ln.startswith("#EXT-X-STREAM-INF"):
                        for part in ln.split(","):
                            if "BANDWIDTH=" in part:
                                bw = max(bw, int(part.split("=")[1].split("-")[0]))
                if bw > best_bw:
                    best, best_bw = v, bw
            except Exception:
                continue
        if not best:
            return url, False, f"variante falha ({len(vs)} variantes)"
        target = best
        note = f"variante {best_bw//1000}kbps"
    else:
        target = r.url
        note = "media playlist"

    try:
        pr = get(target)
    except Exception as e:
        return url, False, f"playlist erro={type(e).__name__}"
    if pr.status_code != 200:
        return url, False, f"playlist http={pr.status_code}"

    segs = segments(pr.url, pr.text)
    if not segs:
        return url, False, "playlist sem segmentos"
    got = 0
    total = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
        futs = []
        for s in segs:
            futs.append(ex.submit(get, s, {"Range": "bytes=0-524287"}))
        for f in futs:
            try:
                resp = f.result()
                if resp.status_code in (200, 206) and resp.content:
                    got += 1
                    total += len(resp.content)
            except Exception:
                pass
    if not got:
        return url, False, f"segmentos falharam ({len(segs)} testados)"
    return url, True, f"{note} | segmentos {got}/{len(segs)} ok, {total}B baixados"


def main():
    ok_all = True
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
        futs = {ex.submit(deep, u): u for u in URLS}
        for fut in concurrent.futures.as_completed(futs):
            url, ok, reason = fut.result()
            ok_all = ok_all and ok
            print(f"{'OK  ' if ok else 'FALHA'} {reason}\n     {url[:100]}")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())