#!/usr/bin/env python3
"""Passo 1 - inventario + teste real dos streams HLS de lista5.m3u.

Testa cada URL: HTTP status, content-type, presenca de #EXTM3U, e
efetivamente baixa 1 segmento de midia para provar que o stream reproduz.
"""
import json
import os
import re
import subprocess
import sys
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

SRC = "lista5.m3u"
OUT = "l5_stream_results.json"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def curl(args, timeout=25):
    try:
        p = subprocess.run(["curl", "-sL", "-A", UA,
                            "--max-time", str(timeout), *args],
                           capture_output=True, timeout=timeout + 10)
        return p.stdout, p.returncode
    except Exception:
        return b"", -1


def code_of(url, extra=()):
    out, rc = curl(["-o", "/dev/null", "-w", "%{http_code} %{content_type} "
                    "%{size_download}", *extra, url])
    parts = out.decode(errors="replace").split(" ", 2)
    return (parts[0] if parts else "000"), (parts[1] if len(parts) > 1 else ""), rc


def parse_master(text):
    """Retorna lista de linhas de URL de midia (nao variantes)."""
    base = ""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines or not lines[0].startswith("#EXTM3U"):
        return None, "sem #EXTM3U"
    for i, l in enumerate(lines):
        if l.startswith("#EXT-X-STREAM-INF"):
            for j in range(i + 1, len(lines)):
                if not lines[j].startswith("#"):
                    base = lines[j]
                    break
            break
    return base or "", None


def join(parent, child):
    """urljoin + herda query do pai (tokens hdnea= etc)."""
    full = urllib.parse.urljoin(parent, child)
    pq = urllib.parse.urlsplit(parent).query
    if pq:
        sp = urllib.parse.urlsplit(full)
        if not sp.query:
            full = urllib.parse.urlunsplit(
                (sp.scheme, sp.netloc, sp.path, pq, sp.fragment))
    return full


def resolve(url):
    """Resolve master -> media. Devolve (media_url, tipo)."""
    body, rc = curl([url])
    txt = body.decode("utf-8", "replace")
    if not txt.startswith("#EXTM3U"):
        return url, "direto"
    media, err = parse_master(txt)
    if err or not media:
        return url, "media-playlist"
    return join(url, media), "master"


def test_one(idx_url):
    idx, url = idx_url
    rec = {"idx": idx, "url": url}
    code, ctype, rc = code_of(url)
    rec["http"] = code
    rec["ctype"] = ctype
    if code not in ("200", "206"):
        rec["ok"] = False
        rec["motivo"] = f"http {code}"
        return rec

    media, kind = resolve(url)
    rec["kind"] = kind
    rec["media"] = media

    body, _ = curl(["-r", "0-400000", media], timeout=25)
    txt = body.decode("utf-8", "replace")
    if txt.startswith("#EXTM3U"):
        lines = [l.strip() for l in txt.splitlines() if l.strip()]
        seg = ""
        for l in lines:
            if not l.startswith("#"):
                seg = join(media, l)
                break
        if not seg:
            rec["ok"] = False
            rec["motivo"] = "media sem segmento"
            return rec
        sbody, src = curl(["-r", "0-900000", seg], timeout=25)
        rec["seg_bytes"] = len(sbody)
        rec["seg_ok"] = src == 0 and len(sbody) > 2000
        if not rec["seg_ok"]:
            rec["ok"] = False
            rec["motivo"] = f"segmento vazio/erro ({len(sbody)}b)"
            return rec
    else:
        rec["seg_bytes"] = len(body)
        if len(body) < 2000:
            rec["ok"] = False
            rec["motivo"] = "body muito pequeno"
            return rec
        rec["seg_ok"] = True

    rec["ok"] = True
    rec["motivo"] = "ok"
    return rec


def main():
    entries = []
    with open(SRC, encoding="utf-8", errors="replace") as f:
        lines = f.read().splitlines()
    cur = None
    for ln in lines:
        s = ln.strip()
        if s.startswith("#EXTINF"):
            cur = s
        elif s and not s.startswith("#"):
            entries.append((cur or "(sem EXTINF)", s))
            cur = None

    # deduplicar mantendo ordem
    seen, uniq = set(), []
    for i, (ext, url) in enumerate(entries, 1):
        if url in seen:
            continue
        seen.add(url)
        uniq.append((i, ext, url))

    print(f"Entradas: {len(entries)} | URLs unicas: {len(uniq)}")
    with ThreadPoolExecutor(max_workers=8) as ex:
        res = list(ex.map(lambda t: test_one((t[0], t[2])), uniq))

    for r in res:
        flag = "OK  " if r.get("ok") else "FAIL"
        print(f"[{flag}] #{r['idx']:>2} http={r['http']:<4} seg={r.get('seg_bytes',0):>7} "
              f"{r.get('motivo','')} | {r['url'][:95]}")

    with open(OUT, "w") as f:
        json.dump(res, f, indent=1)

    ok = sum(1 for r in res if r.get("ok"))
    print(f"\nRESULTADO: {ok}/{len(res)} URLs funcionais")
    hosts = {}
    for r in res:
        h = re.match(r"https?://([^/]+)", r["url"]).group(1)
        hosts.setdefault(h, [0, 0])
        hosts[h][0] += 1
        hosts[h][1] += 1 if r.get("ok") else 0
    print("\nPor host:")
    for h, (t, o) in sorted(hosts.items()):
        print(f"  {h}: {o}/{t}")


if __name__ == "__main__":
    main()