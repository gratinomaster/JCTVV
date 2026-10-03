#!/usr/bin/env python3
"""Validador de tvg-logo: exige .jpg, HTTP 200, JPEG real, sem imgur."""
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

JPEG_SOI = (b"\xff\xd8\xff",)
PNG_SOI = (b"\x89PNG\r\n\x1a\n",)
BAD_EXT = (".png", ".svg", ".webp", ".gif", ".bmp", ".tif", ".tiff", ".ico")


def check(url):
    r = {"url": url}
    if "imgur.com" in url.lower():
        r.update(ok=False, erro="host imgur.com (proibido)")
        return r
    if not url.lower().endswith(".jpg"):
        r.update(ok=False, erro="extensao nao .jpg")
        return r
    try:
        p = subprocess.run(
            ["curl", "-sL", "-A", UA, "--max-time", "30", "-w",
             "\n%{http_code} %{content_type} %{size_download}", url],
            capture_output=True, timeout=45)
        out = p.stdout
    except Exception as e:
        r.update(ok=False, erro=f"curl falhou: {e}")
        return r
    body, _, info = out.rpartition(b"\n")
    parts = info.decode().split()
    code = parts[0] if parts else "?"
    ctype = parts[1] if len(parts) > 1 else "?"
    size = int(parts[2]) if len(parts) > 2 else 0
    r.update(http=code, ctype=ctype, bytes=size)
    if code != "200":
        r.update(ok=False, erro=f"HTTP {code}")
        return r
    if any(body.startswith(s) for s in PNG_SOI):
        r.update(ok=False, erro="conteudo PNG apesar do .jpg")
        return r
    if not any(body.startswith(s) for s in JPEG_SOI):
        r.update(ok=False, erro="nao comeca com SOI JPEG (FF D8 FF)")
        return r
    if size < 2000:
        r.update(ok=False, erro=f"imagem pequena demais ({size}b)")
        return r
    if "image" not in ctype:
        r.update(ok=False, erro=f"content-type {ctype}")
        return r
    r.update(ok=True)
    return r


if __name__ == "__main__":
    urls = [l.strip() for l in sys.stdin if l.strip()] or sys.argv[1:]
    with ThreadPoolExecutor(max_workers=6) as ex:
        res = list(ex.map(check, urls))
    ruins = 0
    for r in res:
        tag = "OK " if r["ok"] else "ERR"
        ruins += 0 if r["ok"] else 1
        print(f"[{tag}] http={r.get('http','-'):<4} {r.get('bytes',0):>7}b "
              f"{r.get('ctype','-'):<12} {r['url']}")
        if not r["ok"]:
            print(f"        -> {r['erro']}")
    print(f"\nLOGOS: {len(res) - ruins}/{len(res)} validos .jpg")
    sys.exit(1 if ruins else 0)