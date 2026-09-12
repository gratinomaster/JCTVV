#!/usr/bin/env python3
"""Testa todos os canais de lista5.m3u, remove os inoperantes e sobrescreve."""

import re
import ssl
import concurrent.futures
import urllib.request
from urllib.parse import urljoin

INPUT = "lista5.m3u"

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept": "*/*",
}


def fetch(url, timeout=15):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        return resp.read(65536)


def test_channel(url):
    try:
        body = fetch(url).decode("utf-8", errors="ignore")
        if "#EXTM3U" not in body:
            return False, "manifiesto invalido"
        lines = [l.strip() for l in body.splitlines() if l.strip() and not l.startswith("#")]
        if not lines:
            return False, "sin segmentos en manifiesto"
        if "#EXT-X-TARGETDURATION" in body or "#EXTINF" in body:
            seg = urljoin(url, lines[0])
        else:
            vfull = urljoin(url, lines[0])
            try:
                vbody = fetch(vfull).decode("utf-8", errors="ignore")
            except Exception as e:
                return False, f"variante falhou: {str(e)[:50]}"
            vlines = [l.strip() for l in vbody.splitlines() if l.strip() and not l.startswith("#")]
            if not vlines:
                return False, "variante sem segmentos"
            seg = urljoin(vfull, vlines[0])
        data = fetch(seg)
        if len(data) > 1000 and (data[0:1] == b"\x47" or b"ftyp" in data[:64] or b"moof" in data[:2048]):
            return True, f"OK ({len(data)}B)"
        return False, f"segmento inválido ({len(data)}B)"
    except Exception as e:
        msg = str(e)
        if isinstance(e, urllib.error.HTTPError):
            msg = f"HTTP {e.code}"
        elif isinstance(e, urllib.error.URLError):
            msg = str(e.reason)[:60]
        return False, msg[:70]


def parse_entries(filepath):
    entries = []
    with open(filepath, "r") as f:
        lines = f.read().splitlines()
    i = 0
    while i < len(lines):
        if lines[i].startswith("#EXTINF:"):
            extinf = lines[i]
            url = lines[i + 1].strip() if i + 1 < len(lines) else ""
            entries.append((extinf, url))
            i += 2
        else:
            i += 1
    return entries


def main():
    entries = parse_entries(INPUT)
    print(f"Entradas: {len(entries)}")

    unique_urls = list(dict.fromkeys(u for _, u in entries))
    print(f"URLs únicas a testar: {len(unique_urls)}")

    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
        futs = {ex.submit(test_channel, u): u for u in unique_urls}
        for fut in concurrent.futures.as_completed(futs):
            u = futs[fut]
            ok, msg = fut.result()
            results[u] = (ok, msg)
            name = next((re.search(r",(.+)$", e).group(1).strip()[:50] for e, u2 in entries if u2 == u and re.search(r",(.+)$", e)), "")
            print(f"[{'OK ' if ok else 'FALHOU'}] {name or u[:50]} -> {msg}")

    ok_urls = {u for u, (ok, _) in results.items() if ok}
    kept = [(e, u) for e, u in entries if u in ok_urls]
    removed = len(entries) - len(kept)

    print(f"\nRemovidas: {removed} | Mantidas: {len(kept)}")

    print("\nCanais removidos:")
    seen = set()
    for e, u in entries:
        if u not in ok_urls and u not in seen:
            m = re.search(r",(.+)$", e)
            print(f"  - {m.group(1).strip() if m else u[:60]} ({results[u][1]})")
            seen.add(u)

    with open(INPUT, "w") as f:
        f.write("#EXTM3U\n")
        for e, u in kept:
            f.write(e + "\n")
            f.write(u + "\n")

    print(f"\n{INPUT} sobrescrito com sucesso!")


if __name__ == "__main__":
    main()