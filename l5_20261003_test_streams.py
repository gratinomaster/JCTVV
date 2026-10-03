#!/usr/bin/env python3
"""Testa cada URL unica do lista5.m3u: resolve master->variant, baixa segmento,
classifica (video+audio / so video / so audio) e grava JSON."""
import json
import re
import subprocess
import sys
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def curl(url, extra=(), timeout=25):
    try:
        p = subprocess.run(
            ["curl", "-sL", "-A", UA, "--max-time", str(timeout), *extra, url],
            capture_output=True, timeout=timeout + 10)
        return p.stdout
    except Exception:
        return b""


def join(parent, child):
    full = urllib.parse.urljoin(parent, child)
    pq = urllib.parse.urlsplit(parent).query
    if pq:
        sp = urllib.parse.urlsplit(full)
        if not sp.query:
            full = urllib.parse.urlunsplit(
                (sp.scheme, sp.netloc, sp.path, pq, sp.fragment))
    return full


def parse_attrs(line):
    out = {}
    for m in re.finditer(r'([A-Z0-9-]+)=("[^"]*"|[^,]*)', line):
        out[m.group(1)] = m.group(2).strip('"')
    return out


def first_variant(txt):
    lines = [l.strip() for l in txt.splitlines() if l.strip()]
    for i, l in enumerate(lines):
        if l.startswith("#EXT-X-STREAM-INF"):
            at = parse_attrs(l)
            for j in range(i + 1, len(lines)):
                if not lines[j].startswith("#"):
                    return lines[j], at
    return None, None


def first_seg(txt):
    seen = False
    for l in (x.strip() for x in txt.splitlines()):
        if l.startswith("#EXTINF:"):
            seen = True
            continue
        if l and not l.startswith("#") and seen:
            return l
    return None


def probe(url):
    r = {"url": url}
    man = curl(url)
    if not man or not man.startswith(b"#EXTM3U"):
        r.update(ok=False, erro="manifesto invalido/vazio",
                 bytes=len(man))
        return r
    txt = man.decode("utf-8", "replace")
    r["manifest_bytes"] = len(man)
    if "#EXTINF:" in txt:
        r["nivel"] = "media"
        r["segmentos"] = len(re.findall(r"^\S+", txt, re.M))
        seg = first_seg(txt)
        r["tipo_hint"] = re.search(r"#EXT-X-STREAM-INF.*CODECS=\"([^\"]+)\"",
                                   txt)
        codecs = ""
        if "#EXT-X-MEDIA" in txt:
            codecs = "muxed"
    else:
        var, at = first_variant(txt)
        r["nivel"] = "master"
        r["variants"] = len(re.findall(r"#EXT-X-STREAM-INF", txt))
        if not var:
            r.update(ok=False, erro="master sem variant")
            return r
        cod = (at or {}).get("CODECS", "")
        r["codecs"] = cod
        r["bandwidth"] = (at or {}).get("BANDWIDTH")
        r["resolucao"] = (at or {}).get("RESOLUTION")
        vurl = join(url, var)
        vtxt = curl(vurl).decode("utf-8", "replace")
        seg = first_seg(vtxt)
        if not seg:
            r.update(ok=False, erro="variant sem segmento")
            return r
        url = vurl
    segurl = join(url, seg)
    r["segmento"] = segurl
    data = curl(segurl, ("-r", "0-900000"), timeout=30)
    r["seg_bytes"] = len(data)
    ts = len(data) >= 376 and data[0:1] == b"G" and data[188:189] == b"G"
    mp4 = b"ftyp" in data[:64] or b"moof" in data[:8192]
    aac = data[:1] in (b"\xff",) and data[1:2] in (b"\xf1", b"\xf9", b"\xfb")
    r["formato"] = "TS" if ts else ("fMP4" if mp4 else ("AAC" if aac else "?"))
    if aac and not (ts or mp4):
        r["tipo"] = "AUDIO-ONLY"
    elif r["nivel"] == "media":
        r["tipo"] = "AUDIO-ONLY" if r.get("tipo_hint") == "" and aac else "MIXED"
    else:
        cod = (r.get("codecs") or "").lower()
        has_v = "avc" in cod or "hvc" in cod or "hev" in cod or "av01" in cod
        has_a = "mp4a" in cod or "ac-3" in cod or "ec-3" in cod
        if has_v and not has_a:
            r["tipo"] = "VIDEO-ONLY"
        elif has_a and not has_v:
            r["tipo"] = "AUDIO-ONLY"
        elif has_v and has_a:
            r["tipo"] = "VIDEO+AUDIO"
        else:
            r["tipo"] = "MIXED/UNKNOWN"
    r["ok"] = len(data) > 10000
    if not r["ok"]:
        r["erro"] = f"segmento curto ({len(data)}b)"
    return r


def urls_from(path):
    out, seen = [], set()
    for ln in open(path, encoding="utf-8", errors="replace"):
        s = ln.strip()
        if s and not s.startswith("#") and s not in seen:
            seen.add(s)
            out.append(s)
    return out


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "lista5.m3u"
    urls = urls_from(src)
    print(f"URLs unicas: {len(urls)}")
    with ThreadPoolExecutor(max_workers=4) as ex:
        res = list(ex.map(probe, urls))
    for r in res:
        tag = "OK " if r.get("ok") else "ERR"
        print(f"[{tag}] {r.get('tipo','?'):<12} {r.get('formato','?'):<5} "
              f"seg={r.get('seg_bytes',0):>7}b  {r['url'][:110]}")
        if not r.get("ok"):
            print(f"        erro: {r.get('erro')}")
    json.dump(res, open("l5_20261003_stream_probe.json", "w"), indent=1)
    print("\nJSON -> l5_20261003_stream_probe.json")