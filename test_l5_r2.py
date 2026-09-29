#!/usr/bin/env python3
"""Round 2: strict verification - check A/V presence and re-probe stability."""
import re
import sys
import json
import queue
import threading
from urllib.parse import urljoin

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

LISTA = sys.argv[1] if len(sys.argv) > 1 else "lista5.m3u"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
HDRS = {"User-Agent": UA, "Accept": "*/*", "Accept-Encoding": "identity",
        "Connection": "close"}

s = requests.Session()
s.mount("https://", HTTPAdapter(max_retries=Retry(total=2, backoff_factor=0.5),
                                pool_connections=32, pool_maxsize=32))
s.mount("http://", HTTPAdapter(max_retries=Retry(total=2, backoff_factor=0.5)))


def parse(path):
    out, info = [], None
    for line in open(path, encoding="utf-8", errors="replace"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("#EXTINF"):
            info = line
        elif not line.startswith("#"):
            out.append((info or "", line))
            info = None
    return out


def nm(info):
    m = re.search(r",(.+)$", info)
    return m.group(1).strip() if m else "?"


def fetch(url, t=12):
    return s.get(url, headers=HDRS, timeout=t, allow_redirects=True)


def descend(text, base, depth=0):
    """Return (segments, inits, types) for a playlist, following masters."""
    types = set()
    for m in re.finditer(r'#EXT-X-STREAM-INF', text):
        types.add("video")
    lines = [l.strip() for l in text.splitlines()]
    segs, inits, variants = [], [], []
    for i, l in enumerate(lines):
        if l.startswith("#EXT-X-MAP:"):
            m = re.search(r'URI="([^"]+)"', l)
            if m:
                inits.append(urljoin(base, m.group(1)))
                if "TYPE=" in l:
                    types.add(re.search(r'TYPE="([A-Z]+)"', l).group(1).lower())
        if l.startswith("#EXT-X-MEDIA:"):
            mt = re.search(r'TYPE="([A-Z]+)"', l)
            if mt:
                types.add(mt.group(1).lower())
            if 'URI="' in l:
                variants.append(urljoin(base, re.search(r'URI="([^"]+)"', l).group(1)))
        if l.startswith("#EXT-X-STREAM-INF"):
            for n in lines[i + 1:i + 4]:
                if n and not n.startswith("#"):
                    variants.append(urljoin(base, n))
                    break
        if l.startswith("#EXTINF"):
            if re.search(r",0\b", l) is None:
                types.add("video")
            for n in lines[i + 1:i + 4]:
                if n and not n.startswith("#"):
                    segs.append(urljoin(base, n))
                    break
    if not segs and variants and depth < 3:
        for v in variants:
            try:
                r = fetch(v)
            except Exception:
                continue
            if r.status_code == 200 and b"#EXTM3U" in r.content[:300]:
                return descend(r.content.decode("utf-8", "replace"),
                               str(r.url), depth + 1)
    return segs, inits, types


def probe(url, n=300000):
    h = dict(HDRS)
    h["Range"] = f"bytes=0-{n-1}"
    try:
        r = s.get(url, headers=h, timeout=20, stream=True)
        if r.status_code not in (200, 206):
            return 0, f"http_{r.status_code}"
        tot = 0
        for c in r.iter_content(65536):
            tot += len(c)
            if tot >= n:
                break
        r.close()
        return tot, "ok"
    except Exception as e:
        return 0, type(e).__name__


def run(info, url):
    r = {"name": nm(info), "url": url, "ok": False, "a": False, "v": False,
         "bytes": 0, "note": ""}
    try:
        resp = fetch(url)
    except Exception as e:
        r["note"] = f"conn {type(e).__name__}"
        return r
    if resp.status_code != 200 or b"#EXTM3U" not in resp.content[:300]:
        r["note"] = f"http_{resp.status_code}"
        return r
    segs, inits, types = descend(resp.content.decode("utf-8", "replace"), str(resp.url))
    r["a"] = "audio" in types
    r["v"] = "video" in types
    if not segs:
        r["note"] = "no_segments"
        return r
    for i in inits[:1]:
        try:
            ri = fetch(i, 15)
            if ri.status_code in (200, 206):
                r["bytes"] += len(ri.content)
        except Exception:
            pass
    for sg in segs[:2]:
        n, why = probe(sg)
        r["bytes"] += n
        if n > 1000:
            break
        r["note"] = why
    r["ok"] = r["bytes"] > 1000
    if r["ok"]:
        r["note"] = f"{r['bytes']}B a={r['a']} v={r['v']}"
    return r


entries = parse(LISTA)
print(f"verificando {len(entries)} entradas (rodada 2, estrita)\n", flush=True)
q = queue.Queue()
for i, (info, url) in enumerate(entries):
    q.put((i, info, url))
res, lock = [], threading.Lock()


def w():
    while True:
        try:
            i, info, url = q.get_nowait()
        except queue.Empty:
            return
        r = run(info, url)
        r["i"] = i
        with lock:
            res.append(r)
            print(f"[{i:>3}] {'OK  ' if r['ok'] else 'FAIL'} A={'S' if r['a'] else 'N'} "
                  f"V={'S' if r['v'] else 'N'} {r['note'][:34]:<34} {r['name'][:40]}",
                  flush=True)


ts = [threading.Thread(target=w, daemon=True) for _ in range(6)]
[t.start() for t in ts]
[t.join() for t in ts]
res.sort(key=lambda x: x["i"])
json.dump(res, open("test_l5_streams_r2.json", "w"), indent=2, ensure_ascii=False)

print("\n--- resumo rodada 2 ---")
print("ok:", sum(1 for r in res if r["ok"]), "/", len(res))
print("so audio (sem video):", sum(1 for r in res if r["ok"] and r["a"] and not r["v"]))
print("com video:", sum(1 for r in res if r["ok"] and r["v"]))
print("falhas:", sum(1 for r in res if not r["ok"]))
for r in res:
    if not r["ok"]:
        print("  FALHOU:", r["note"], r["name"][:50])
