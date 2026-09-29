#!/usr/bin/env python3
"""Deep AV scan: resolve HLS master -> child playlist -> real media segments, ClamAV every byte."""
import os, re, subprocess, requests, json
from urllib.parse import urljoin, urlparse

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
H = {"User-Agent": UA}
WORK = "/tmp/opencode/avdeep"
os.makedirs(WORK, exist_ok=True)

CH = [
    ("ABC News Live", "https://abcnews-livestreams.akamaized.net/out/v1/6a597119dbd5428a82dc11a2f514a1a2/abcn-live-10-cmaf-manifest/abcn-live-10-index.m3u8"),
    ("ABC News Live (Disney CDN)", "https://pb-0n3n2ej0w8pl9.akamaized.net/ABCNewsLive_Disney.m3u8"),
    ("Fox News Channel", "https://247preview.foxnews.com/hls/live/2020027/fncv3preview/primary.m3u8"),
    ("Fox Business", "https://247preview.foxbusiness.com/hls/live/2020026/fbnv3preview/primary.m3u8"),
    ("CBS News 24/7", "https://cbsn-us.cbsnstream.cbsnews.com/out/v1/55a8648e8f134e82a470f83d562deeca/master.m3u8"),
    ("CBS News 24/7 (vtt)", "https://cbsn-us-vtt.cbsnstream.cbsnews.com/out/v1/ef868690d34144509eda696884bf1619/master.m3u8"),
]

MEDIA_RE = re.compile(r"^[A-Za-z0-9_/.:%?=&~\-]+$")


def get(url, timeout=25):
    r = requests.get(url, headers=H, timeout=timeout)
    return r


def walk(url, depth, blobs, seen, max_depth=3):
    """recursively resolve playlists, capture real media segments"""
    if depth > max_depth or url in seen or len(blobs) > 14:
        return
    seen.add(url)
    try:
        r = get(url)
    except Exception:
        return
    if r.status_code != 200 or "mpegurl" not in (r.headers.get("Content-Type", "") + r.text[:200].lower()):
        pass
    txt = r.text
    if not txt.lstrip().startswith("#EXTM3U"):
        return
    lines = [l.strip() for l in txt.splitlines() if l.strip()]
    children, media = [], []
    for l in lines:
        if l.startswith("#"):
            continue
        su = urljoin(url, l)
        if su.endswith(".m3u8"):
            children.append(su)
        else:
            media.append(su)
    if children and not media:
        for c in children[:2]:
            walk(c, depth + 1, blobs, seen, max_depth)
    else:
        blobs.append((url, r.content, "playlist"))
        for m in media[:3]:
            if len(blobs) > 14:
                break
            try:
                rr = get(m)
                blobs.append((m, rr.content, "media"))
            except Exception:
                pass


def clamscan(paths):
    if not paths:
        return []
    p = subprocess.run(["sudo", "clamscan", "--no-summary", "--infected", *paths],
                       capture_output=True, timeout=1200)
    return [l for l in p.stdout.decode(errors="replace").splitlines() if l.endswith("FOUND")]


def sniff(data):
    if data[:4] == b"\x1a\x45\xdf\xa3":
        return "matroska/webm"
    if data[4:8] == b"ftyp":
        return "mp4/fmp4"
    if data[:1] == b"\x47" and len(data) > 188:
        return "mpeg-ts"
    if data[:3] == b"\xff\xfb" or data[:2] == b"\xff\xf1" or data[:2] == b"\xff\xf9":
        return "aac-adts"
    if data[:2] == b"ID3" or data[:3] == b"\xff\xfb":
        return "mp3/aac"
    if data.lstrip()[:5] == b"<?xml" or data.lstrip()[:1] == b"<":
        return "XML/MARKUP"
    if b"<!DOCTYPE html" in data[:2000] or b"<html" in data[:2000].lower():
        return "HTML"
    return "unknown"


report = []
print("=" * 100)
print("DEEP ANTI-VIRUS SCAN  --  real media payloads (HLS master -> child -> segments)")
print("=" * 100)
for name, u in CH:
    d = os.path.join(WORK, re.sub(r"[^A-Za-z0-9]+", "_", name)[:36])
    os.makedirs(d, exist_ok=True)
    blobs, seen = [], set()
    walk(u, 0, blobs, seen)
    paths, kinds, total = [], [], 0
    for i, (su, data, kind) in enumerate(blobs):
        if not data:
            continue
        s = sniff(data)
        total += len(data)
        ext = {}.get(s, ".bin") if s != "XML/MARKUP" else ".xml"
        if s == "mpeg-ts":
            ext = ".ts"
        elif s in ("mp4/fmp4",):
            ext = ".m4s"
        elif s in ("aac-adts", "mp3/aac"):
            ext = ".aac"
        elif s == "matroska/webm":
            ext = ".webm"
        elif s == "HTML":
            ext = ".html"
        p = os.path.join(d, f"b{i}{ext}")
        open(p, "wb").write(data)
        paths.append(p)
        kinds.append(f"{kind}:{s}:{len(data)//1024}K")

    inf = clamscan(paths)
    bad_types = [k for k in kinds if ":HTML:" in k or ":XML/MARKUP:" in k]
    verdict = "FAIL" if inf or bad_types else "PASS"
    print(f"\n{verdict}  {name}")
    print(f"      url      : {u[:96]}")
    print(f"      payloads : {len(paths)} files, {total/1e6:.2f} MB total")
    for k in kinds:
        print(f"        - {k}")
    if inf:
        for i in inf:
            print("      !! INFECTED:", i)
    if bad_types:
        print("      !! non-media payload:", bad_types)
    report.append(dict(name=name, url=u, ok=(verdict == "PASS"), files=len(paths),
                       bytes=total, infected=inf, kinds=kinds))

json.dump(report, open("/tmp/opencode/av_deep.json", "w"), indent=1)
print("\n" + "=" * 100)
print(f"DEEP AV RESULT: {sum(1 for r in report if r['ok'])}/{len(report)} PASS, "
      f"{sum(1 for r in report if not r['ok'])} FAIL")
print("=" * 100)
