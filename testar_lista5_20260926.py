#!/usr/bin/env python3
"""Testa todos os canais do lista5.m3u e reescreve o arquivo sem os que falham.

O teste e profundo: baixa o manifest, segue variantes e baixa um segmento de
midia real, validando os bytes do segmento (TS 0x47 / fMP4 / AAC) para nao
aceitar paginas de erro HTML servidas com HTTP 200.
"""

import os
import re
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests

PLAYLIST = "lista5.m3u"
BACKUP = "lista5.m3u.bak.teste_{}"
REPORT = "relatorio_lista5_{}.txt"

TIMEOUT = 15
CONNECT_TIMEOUT = 10
MAX_WORKERS = 6
RETRIES = 3
RETRY_WAIT = 3
MAX_DEPTH = 4
SEG_BYTES = 65536

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
HEADERS = {
    "User-Agent": UA,
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
}

SEG_EXT = re.compile(r"\.(ts|m4s|mp4|mp4a|aac|m4a|mp3|m4v|cmfv|cmfa|key)(\?|$)", re.I)


def log(msg):
    print(msg, flush=True)


def parse_m3u(path):
    """Devolve (header, entradas) preservando o formato original."""
    header = []
    entries = []
    extinf = None
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            line = raw.rstrip("\n").rstrip("\r")
            if not line.strip():
                continue
            if line.startswith("#EXTINF"):
                extinf = line
            elif line.startswith("#"):
                if extinf is None:
                    header.append(line)
            else:
                entries.append({"extinf": extinf or "", "url": line.strip()})
                extinf = None
    return header, entries


def inherit_query(url, base):
    """Reproduz query string herdada de manifests HLS (ex.: dvt2=...&hash=...)."""
    if "?" in url:
        return url
    query = urlsplit(base).query
    if not query:
        return url
    scheme, netloc, path, _, frag = urlsplit(url)
    return urlunsplit((scheme, netloc, path, query, frag))


def is_media_segment(name):
    return bool(SEG_EXT.search(name))


def is_manifest(name):
    return ".m3u8" in name.lower()


def looks_like_playlist(text):
    return "#EXTM3U" in text or "#EXT-X-" in text


def is_error_page(text):
    low = text[:600].lower()
    return ("<!doctype html" in low or "<html" in low
            or "<?xml" in low and "<html" not in low and "urlset" not in low)


def looks_like_media(head):
    """Valida bytes magicos de TS (0x47), fMP4 (ftyp/styp) ou ID3/AAC."""
    if len(head) < 16:
        return False
    if head[0] == 0x47 and (len(head) <= 188 or head[188] == 0x47):
        return True
    if b"ftyp" in head[:64] or b"styp" in head[:64]:
        return True
    if head[:3] == b"ID3":
        return True
    if head[0] == 0xFF and (head[1] & 0xF0) == 0xF0:
        return True
    if b"\x1aE" in head[:64] or head[:4] == b"\x30\x26\xb2\x75":
        return True
    # fallback: precisa ter densidade alta de bytes nao-texto/imprimiveis
    printable = sum(1 for b in head if 9 <= b <= 13 or 32 <= b < 127)
    return printable / len(head) < 0.85


def probe(url, session, want_bytes=SEG_BYTES):
    """GET simples. Devolve (status, bytes) ou lanca requests.RequestException."""
    resp = session.get(url, headers=HEADERS, timeout=(CONNECT_TIMEOUT, TIMEOUT),
                       stream=True, allow_redirects=True)
    try:
        data = resp.raw.read(want_bytes, decode_content=True) or b""
    except Exception:
        data = b""
    finally:
        resp.close()
    return resp.status_code, data


def fetch_manifest(url, session, depth=0):
    """Valida um manifest e retorna (ok, motivo). Percorre variantes."""
    if depth > MAX_DEPTH:
        return False, "profundidade maxima de variantes"

    try:
        status, data = probe(url, session)
    except requests.RequestException as exc:
        return False, "conexao: %s" % type(exc).__name__

    if status != 200:
        return False, "HTTP %d" % status
    if not data:
        return False, "resposta vazia"

    text = data.decode("utf-8", errors="ignore")
    if is_error_page(text):
        return False, "retornou HTML/XML em vez de stream"
    if not looks_like_playlist(text):
        return False, "conteudo nao e playlist HLS"

    lines = [l.strip() for l in text.splitlines()]
    refs = [l for l in lines if l and not l.startswith("#")]
    variants = [l for l in refs if is_manifest(l)]
    segments = [l for l in refs if is_media_segment(l)]
    has_stream_inf = "#EXT-X-STREAM-INF" in text

    if not variants and not segments:
        return False, "manifest sem segmentos"

    if not has_stream_inf:
        # media playlist: toda linha sem # e segmento, mesmo sem extensao
        # conhecida (ex.: .mp4a do audio-only ABC)
        for seg in (refs or [])[:4]:
            seg_url = inherit_query(urljoin(url, seg), url)
            if check_segment(seg_url, session):
                return True, "segmento ok"
        return False, "nenhum segmento respondeu"

    # master playlist: tenta cada variante ate uma funcionar
    reasons = []
    for var in variants[:6]:
        var_url = inherit_query(urljoin(url, var), url)
        ok, why = fetch_manifest(var_url, session, depth + 1)
        if ok:
            return True, "variante ok"
        reasons.append(why)
    return False, "; ".join(dict.fromkeys(reasons)) or "nenhuma variante respondeu"


def check_segment(seg_url, session):
    try:
        status, data = probe(seg_url, session)
    except requests.RequestException:
        return False
    if status != 200 or len(data) < 1024:
        return False
    return looks_like_media(data)


def test_url(url, session, attempts=RETRIES):
    last = ""
    for i in range(1, attempts + 1):
        ok, why = fetch_manifest(url, session)
        if ok:
            return True, why
        last = why
        if i < attempts:
            time.sleep(RETRY_WAIT)
    return False, last


def channel_name(extinf):
    m = re.search(r",([^,]+)$", extinf)
    return m.group(1).strip() if m else ""


def main():
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    header, entries = parse_m3u(PLAYLIST)
    total = len(entries)
    unique = list(dict.fromkeys(e["url"] for e in entries))
    log("Playlist : %s" % PLAYLIST)
    log("Entradas : %d (%d URLs unicas)" % (total, len(unique)))
    log("=" * 70)

    names = {}
    for e in entries:
        names.setdefault(e["url"], channel_name(e["extinf"]))

    results = {}
    with requests.Session() as session:
        session.max_redirects = 5
        adapter = requests.adapters.HTTPAdapter(pool_connections=MAX_WORKERS * 2,
                                                pool_maxsize=MAX_WORKERS * 2)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            futures = {pool.submit(test_url, u, session): u for u in unique}
            done = 0
            for fut in as_completed(futures):
                url = futures[fut]
                try:
                    ok, why = fut.result()
                except Exception as exc:
                    ok, why = False, "excecao: %s" % exc
                results[url] = (ok, why)
                done += 1
                log("[%2d/%2d] %-6s %-52s %s"
                    % (done, len(unique), "OK" if ok else "FALHOU",
                       names.get(url, "")[:52], why))

    alive = [e for e in entries if results.get(e["url"], (False, ""))[0]]
    dead = [e for e in entries if not results.get(e["url"], (False, ""))[0]]

    log("=" * 70)
    log("Total: %d | Funcionando: %d | Removidos: %d" % (total, len(alive), len(dead)))

    if not alive:
        log("Nenhum canal funcionando - lista5.m3u mantido intacto.")
        return 1

    shutil.copy2(PLAYLIST, BACKUP.format(stamp))
    with open(PLAYLIST, "w", encoding="utf-8") as fh:
        for line in header or ["#EXTM3U"]:
            fh.write(line + "\n")
        for e in alive:
            fh.write(e["extinf"] + "\n" + e["url"] + "\n")

    seen = set()
    with open(REPORT.format(stamp), "w", encoding="utf-8") as fh:
        fh.write("Teste de canais em %s - %s\n" % (PLAYLIST, stamp))
        fh.write("Total: %d | Funcionando: %d | Removidos: %d\n\n"
                 % (total, len(alive), len(dead)))
        fh.write("REMOVIDOS (%d)\n" % len(dead))
        for e in dead:
            if e["url"] in seen:
                continue
            seen.add(e["url"])
            fh.write("- [%s] %s\n  %s\n"
                     % (results[e["url"]][1], channel_name(e["extinf"])[:90], e["url"]))
        fh.write("\nMANTIDOS (%d)\n" % len(alive))
        for e in alive:
            fh.write("- [%s] %s\n" % (results[e["url"]][1], e["url"]))

    log("Backup   : %s" % BACKUP.format(stamp))
    log("Relatorio: %s" % REPORT.format(stamp))
    return 0


if __name__ == "__main__":
    sys.exit(main())
