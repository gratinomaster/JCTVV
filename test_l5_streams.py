#!/usr/bin/env python3
"""Test every stream in an M3U playlist and report which ones actually deliver media."""
import os
import re
import sys
import json
import time
import base64
import threading
import queue
from urllib.parse import urljoin, urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

LISTA = sys.argv[1] if len(sys.argv) > 1 else "lista5.m3u"
REPORT = sys.argv[2] if len(sys.argv) > 2 else "test_l5_streams.json"
WORKERS = 8

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
HDRS = {
    "User-Agent": UA,
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "identity",
    "Connection": "close",
    "Origin": "https://example.com",
    "Referer": "https://example.com/",
}

session = requests.Session()
retry = Retry(total=1, connect=1, read=1, backoff_factor=0.3,
              status_forcelist=[500, 502, 503, 504], allowed_methods=["GET"])
adapter = HTTPAdapter(max_retries=retry, pool_connections=32, pool_maxsize=32)
session.mount("https://", adapter)
session.mount("http://", adapter)


def parse_m3u(path):
    entries = []
    info = None
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            if line.startswith("#EXTINF"):
                info = line
            elif line.startswith("#"):
                continue
            else:
                entries.append({"info": info or "", "url": line})
                info = None
    return entries


def name_of(entry):
    m = re.search(r",(.+)$", entry["info"])
    return m.group(1).strip() if m else entry["url"][:60]


def get(url, timeout, extra=None, stream=False):
    h = dict(HDRS)
    if extra:
        h.update(extra)
    r = session.get(url, headers=h, timeout=timeout, stream=stream, allow_redirects=True)
    return r


def is_manifest(text):
    return "#EXTM3U" in text[:400]


def parse_segment_uris(text, base):
    """Return list of (uri, is_init) for media playlists, plus variant URIs."""
    variants, segs, inits = [], [], []
    lines = [l.strip() for l in text.splitlines()]
    for i, l in enumerate(lines):
        if l.startswith("#EXT-X-MAP:"):
            m = re.search(r'URI="([^"]+)"', l)
            if m:
                inits.append(urljoin(base, m.group(1)))
        elif l.startswith("#EXTINF"):
            for nxt in lines[i + 1:i + 4]:
                if nxt and not nxt.startswith("#"):
                    segs.append(urljoin(base, nxt))
                    break
    for i, l in enumerate(lines):
        if l.startswith("#EXT-X-STREAM-INF") or l.startswith("#EXT-X-MEDIA:"):
            if l.startswith("#EXT-X-MEDIA:") and 'TYPE="VIDEO"' not in l:
                continue
            for nxt in lines[i + 1:i + 4]:
                if nxt and not nxt.startswith("#"):
                    variants.append(urljoin(base, nxt))
                    break
    return variants, segs, inits


def probe_segment(url, timeout, bytes_needed=200000):
    """Download part of a segment; return bytes read or 0."""
    total = 0
    h = dict(HDRS)
    h["Range"] = f"bytes=0-{bytes_needed - 1}"
    try:
        r = session.get(url, headers=h, timeout=timeout, stream=True, allow_redirects=True)
        if r.status_code not in (200, 206):
            return 0, f"seg_http_{r.status_code}"
        for chunk in r.iter_content(65536):
            total += len(chunk)
            if total >= bytes_needed:
                break
        r.close()
        return total, "ok"
    except Exception as e:
        return 0, f"seg_err_{type(e).__name__}"


def looks_like_media(data):
    """Detect TS / fMP4 / other media payload instead of an error page."""
    if not data:
        return False
    if data[:188] == b"\x47" or (len(data) > 376 and data[188:189] == b"\x47"):
        return True
    if b"ftyp" in data[:64] or b"styp" in data[:64] or b"moof" in data[:256]:
        return True
    if b"ID3" in data[:16]:
        return True
    low = data[:200].lower()
    if b"<html" in low or b"<!doctype" in low or b"<?xml" in low:
        return False
    return True


def test_entry(entry, manifest_timeout=12, seg_timeout=15):
    url = entry["url"]
    name = name_of(entry)
    res = {"name": name, "url": url, "ok": False, "reason": "", "level": None,
           "bytes": 0, "kind": None}
    try:
        r = get(url, manifest_timeout)
    except requests.exceptions.SSLError as e:
        res["reason"] = f"ssl:{type(e).__name__}"
        return res
    except requests.exceptions.Timeout:
        res["reason"] = "timeout_manifest"
        return res
    except Exception as e:
        res["reason"] = f"conn:{type(e).__name__}"
        return res

    with r:
        if r.status_code != 200:
            res["reason"] = f"manifest_http_{r.status_code}"
            return res
        ctype = r.headers.get("Content-Type", "").lower()
        try:
            text = r.content.decode("utf-8", "replace")
        except Exception:
            res["reason"] = "decode_fail"
            return res

    if not is_manifest(text):
        # Some endpoints return a redirect/HTML -> not playable
        res["reason"] = "not_m3u8"
        return res

    base = str(r.url)
    variants, segs, inits = parse_segment_uris(text, base)

    # MASTER -> follow down to a media playlist
    if variants and not segs:
        res["level"] = "master"
        picked = None
        for v in variants:
            try:
                rv = get(v, manifest_timeout)
            except Exception:
                continue
            with rv:
                if rv.status_code != 200:
                    continue
                tv = rv.content.decode("utf-8", "replace")
            if is_manifest(tv):
                vv, vs, vi = parse_segment_uris(tv, str(rv.url))
                if vs:
                    picked = (str(rv.url), vs, vi)
                    break
        if not picked:
            res["reason"] = "no_playable_variant"
            return res
        base, segs, inits = picked
        res["kind"] = "hls"
    else:
        res["kind"] = "hls"
        res["level"] = "media" if segs else "empty_manifest"

    if not segs:
        res["reason"] = "no_segments"
        return res

    # 1) init segment (fMP4) if present
    for init in inits[:1]:
        try:
            ri = get(init, seg_timeout)
            with ri:
                if ri.status_code in (200, 206) and len(ri.content) > 0:
                    res["bytes"] += len(ri.content)
        except Exception:
            pass

    # 2) try up to 3 media segments
    got = 0
    detail = ""
    for seg in segs[:3]:
        n, why = probe_segment(seg, seg_timeout)
        if n > 0:
            got += n
            detail = why
            break
        detail = why
    res["bytes"] += got

    if got > 0:
        res["ok"] = True
        res["reason"] = f"ok {got}B"
        return res

    res["reason"] = f"seg_fail:{detail}"
    return res


def worker(q, out, lock):
    while True:
        try:
            idx, entry = q.get_nowait()
        except queue.Empty:
            return
        try:
            r = test_entry(entry)
        except Exception as e:
            r = {"name": name_of(entry), "url": entry["url"], "ok": False,
                 "reason": f"fatal:{type(e).__name__}:{e}", "level": None,
                 "bytes": 0, "kind": None}
        r["index"] = idx
        with lock:
            out.append(r)
            print(f"[{r['index']:>3}] {'OK  ' if r['ok'] else 'FAIL'} "
                  f"{r['reason']:<28} {r['name'][:58]}", flush=True)
        q.task_done()


def main():
    entries = parse_m3u(LISTA)
    print(f"{len(entries)} entradas em {LISTA}\n", flush=True)

    q = queue.Queue()
    for i, e in enumerate(entries):
        q.put((i, e))
    out, lock = [], threading.Lock()
    threads = [threading.Thread(target=worker, args=(q, out, lock), daemon=True)
               for _ in range(WORKERS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    out.sort(key=lambda r: r["index"])
    with open(REPORT, "w", encoding="utf-8") as fh:
        json.dump({"total": len(out),
                   "ok": sum(1 for r in out if r["ok"]),
                   "results": out}, fh, indent=2, ensure_ascii=False)

    ok = [r for r in out if r["ok"]]
    bad = [r for r in out if not r["ok"]]
    print("\n=== RESUMO ===")
    print(f"total={len(out)}  funcionando={len(ok)}  falhas={len(bad)}")
    uniq_ok = {}
    for r in ok:
        uniq_ok.setdefault(r["name"], 0)
        uniq_ok[r["name"]] += 1
    print("\nCanais com pelo menos 1 URL valida:")
    for n, c in uniq_ok.items():
        print(f"  {c}x  {n[:70]}")
    print("\nURLs que falharam:")
    for r in bad:
        print(f"  {r['reason']:<28} {r['name'][:58]}")


if __name__ == "__main__":
    main()
