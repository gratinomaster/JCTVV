#!/usr/bin/env python3
"""Testa cada entrada da lista5.m3u em profundidade e remove as que nao funcionam.

Teste por URL:
  1) GET do playlist -> precisa ser HLS (#EXTM3U)
  2) se master playlist -> busca a primeira variante e testa
  3) busca o primeiro/ultimo segmento (.ts/.m4s/.aac) e confirma que retorna bytes
Cache por URL para nao repetir requisicoes (a lista tem URLs duplicadas).
"""
import re
import shutil
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from urllib.parse import urljoin

import requests

INPUT = "lista5.m3u"
REPORT = "relatorio_lista5_teste_20261008.txt"

UAS = [
    "VLC/3.0.20 LibVLC/3.0.20",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
]
TIMEOUT = 12

_tls = threading.local()


def session():
    s = getattr(_tls, "s", None)
    if s is None:
        s = requests.Session()
        _tls.s = s
    return s


def get(url, timeout=TIMEOUT, stream=False):
    last = None
    for ua in UAS:
        try:
            r = session().get(
                url,
                timeout=timeout,
                stream=stream,
                headers={"User-Agent": ua, "Accept": "*/*"},
            )
            if r.status_code == 403 and ua is not UAS[-1]:
                if not stream:
                    r.close()
                continue
            return r
        except requests.RequestException as e:
            last = e
    if last is not None:
        raise last
    raise requests.RequestException("sem resposta")


def looks_like_hls(text):
    head = text[:800].lstrip().upper()
    return head.startswith("#EXTM3U") or "#EXT-X-" in head


def playlist_uris(text):
    uris = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        uris.append(line)
    return uris


def test_url(url, depth=0):
    """Retorna (ok: bool, motivo: str)."""
    if depth > 3:
        return True, "ok (profundidade max)"
    try:
        r = get(url, stream=True)
    except requests.RequestException as e:
        return False, f"erro de rede: {type(e).__name__}"
    try:
        if r.status_code not in (200, 206):
            return False, f"HTTP {r.status_code}"
        ctype = (r.headers.get("Content-Type") or "").lower()
        raw = b""
        for chunk in r.iter_content(chunk_size=8192):
            raw += chunk
            if len(raw) >= 65536:
                break
    finally:
        r.close()

    if not raw:
        return False, "resposta vazia"

    text = raw.decode("utf-8", errors="replace")

    if not looks_like_hls(text):
        if "text/html" in ctype or text.lstrip().startswith("<"):
            return False, f"nao e HLS (HTML), status {r.status_code}"
        if ctype.startswith("application/json") or text.lstrip().startswith("{"):
            return False, "nao e HLS (JSON de erro)"
        return False, f"conteudo nao e playlist ({ctype or 'sem content-type'})"

    has_master = "#EXT-X-STREAM-INF" in text.upper()
    uris = playlist_uris(text)

    if has_master:
        if not uris:
            return False, "master playlist sem variantes"
        return test_url(urljoin(url, uris[0]), depth + 1)

    if not uris:
        return False, "playlist sem segmentos"

    # segmento: prefere o ultimo (mais recente em live), senao o primeiro
    seg_url = urljoin(url, uris[-1])
    try:
        sr = get(seg_url, stream=True, timeout=TIMEOUT)
    except requests.RequestException as e:
        return False, f"segmento inacessivel: {type(e).__name__}"
    try:
        if sr.status_code not in (200, 206):
            return False, f"segmento HTTP {sr.status_code}"
        sctype = (sr.headers.get("Content-Type") or "").lower()
        chunk = next(sr.iter_content(chunk_size=4096), b"")
    finally:
        sr.close()

    if not chunk:
        return False, "segmento vazio"
    head = chunk.lstrip()[:200].lower()
    if head.startswith(b"<!doctype") or head.startswith(b"<html"):
        return False, "segmento devolveu HTML"
    if head.startswith(b"{") and "json" in sctype:
        return False, "segmento devolveu JSON de erro"
    return True, f"ok (segmento {len(chunk)}B)"


def parse(path):
    entries = []
    header = "#EXTM3U"
    extinf = None
    with open(path, encoding="utf-8") as f:
        for line in f.read().splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("#EXTM3U"):
                header = line
                continue
            if line.startswith("#EXTINF"):
                extinf = line
            elif line.startswith(("http://", "https://")) and extinf is not None:
                entries.append((extinf, line))
                extinf = None
            elif line.startswith("#"):
                continue
    return header, entries


def name_of(extinf):
    return extinf.split(",")[-1].strip()


def main():
    header, entries = parse(INPUT)
    total = len(entries)
    print(f"Entradas na lista: {total}")

    unique = list({url for _, url in entries})
    print(f"URLs unicas: {len(unique)}\n" + "=" * 70)

    results = {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(test_url, u): u for u in unique}
        for fut, url in futures.items():
            results[url] = fut.result()

    # retry unico para casos instaveis (falso negativo por rede/rota)
    flaky = [u for u in unique if not results[u][0]]
    if flaky:
        print(f"\nResultados de falha: {len(flaky)}. Re-testando com retry...")
        time.sleep(2)
        with ThreadPoolExecutor(max_workers=4) as ex:
            futures = {ex.submit(test_url, u): u for u in flaky}
            for fut, url in futures.items():
                ok, why = fut.result()
                if ok:
                    print(f"retry OK: {url[:90]} | {why}")
                results[url] = (ok, why + " (apos retry)")

    kept, removed = [], []
    for i, (extinf, url) in enumerate(entries, 1):
        ok, why = results[url]
        status = "OK  " if ok else "FAIL"
        print(f"[{i:02d}/{total}] {status} {name_of(extinf)[:60]} :: {why}")
        (kept if ok else removed).append((extinf, url, why))

    print("=" * 70)
    print(f"Funcionando: {len(kept)}/{total}  |  Removidos: {len(removed)}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    shutil.copy2(INPUT, f"{INPUT}.bak.pre_teste_{ts}")

    with open(INPUT, "w", encoding="utf-8") as f:
        f.write(header + "\n")
        for extinf, url, _ in kept:
            f.write(extinf + "\n")
            f.write(url + "\n")

    lines = [
        f"Teste da lista5.m3u - {datetime.now().isoformat(timespec='seconds')}",
        f"Total de entradas: {total}",
        f"Mantidas: {len(kept)}",
        f"Removidas: {len(removed)}",
        "",
        "--- REMOVIDAS (nao funcionando) ---",
    ]
    for extinf, url, why in removed:
        lines.append(f"- {name_of(extinf)} | {why}")
        lines.append(f"  {url}")
    lines.append("")
    lines.append("--- MANTIDAS ---")
    for extinf, url, why in kept:
        lines.append(f"- {name_of(extinf)} | {why}")
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"Backup: {INPUT}.bak.pre_teste_{ts}")
    print(f"Relatorio: {REPORT}")
    print(f"Lista sobrescrita: {INPUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
