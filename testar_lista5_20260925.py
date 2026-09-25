#!/usr/bin/env python3
"""Testa todos os canais do lista5.m3u e reescreve o arquivo sem os que falham."""

import gzip
import os
import re
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from urllib.parse import urljoin, urlparse

import requests

PLAYLIST = "lista5.m3u"
BACKUP = "lista5.m3u.bak.teste_{}"
REPORT = "relatorio_lista5_{}.txt"
TIMEOUT = 15
MAX_WORKERS = 8
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9"}


def parse_m3u(path):
    entries = []
    extinf = None
    header = []
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            if line.startswith("#EXTINF"):
                extinf = line
            elif line.startswith("#"):
                if extinf is None:
                    header.append(line)
            else:
                entries.append({"extinf": extinf or "", "url": line})
                extinf = None
    return header, entries


def fetch(url, session, limit=2_000_000):
    resp = session.get(url, headers=HEADERS, timeout=TIMEOUT, stream=True,
                       allow_redirects=True)
    try:
        body = b"".join(resp.iter_content(65536))
    except Exception:
        body = b""
    finally:
        resp.close()
    if resp.headers.get("Content-Encoding") == "gzip" or body[:2] == b"\x1f\x8b":
        try:
            body = gzip.decompress(body)
        except Exception:
            pass
    return resp, body[:limit]


def looks_like_playlist(body):
    text = body[:4000].decode("utf-8", errors="ignore")
    return "#EXTM3U" in text or "#EXT-X-" in text


def check_segment(session, playlist_url, text):
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        seg = urljoin(playlist_url, line)
        resp, body = fetch(seg, session)
        if resp.status_code == 200 and len(body) > 1024:
            return True
        if resp.status_code == 200 and b"not found" not in body[:200].lower():
            if len(body) > 0:
                return True
    return False


def check_media_playlist(session, url, text):
    if not looks_like_playlist(text.encode()):
        return False, "conteudo nao e playlist HLS"
    if "#EXT-X-STREAM-INF" not in text:
        return check_segment(session, url, text), ""
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        variant = urljoin(url, line)
        vresp, vbody = fetch(variant, session)
        if vresp.status_code != 200:
            continue
        vtext = vbody.decode("utf-8", errors="ignore")
        if not looks_like_playlist(vbody):
            continue
        ok, why = check_media_playlist(session, variant, vtext)
        if ok:
            return True, ""
        if "#EXT-X-STREAM-INF" in vtext:
            continue
        return False, why
    return False, "nenhuma variante do master respondeu"


def test_entry(entry, session):
    url = entry["url"]
    try:
        resp, body = fetch(url, session)
    except requests.RequestException as exc:
        return url, False, "erro de conexao: %s" % type(exc).__name__
    if resp.status_code != 200:
        return url, False, "HTTP %d" % resp.status_code
    if not body:
        return url, False, "resposta vazia"
    text = body.decode("utf-8", errors="ignore")
    if "<?xml" in text[:200].lower() or "<html" in text[:400].lower():
        return url, False, "retornou XML/HTML em vez de stream"
    if not looks_like_playlist(body):
        return url, False, "conteudo nao e playlist HLS"
    ok, why = check_media_playlist(session, url, text)
    return url, ok, why or ""


def main():
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    header, entries = parse_m3u(PLAYLIST)
    total = len(entries)
    print("Canais encontrados em %s: %d" % (PLAYLIST, total))

    results = {}
    with requests.Session() as session:
        session.max_redirects = 5
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            futures = {pool.submit(test_entry, e, session): e for e in entries}
            done = 0
            for fut in as_completed(futures):
                entry = futures[fut]
                try:
                    url, ok, why = fut.result()
                except Exception as exc:
                    url, ok, why = entry["url"], False, "excecao: %s" % exc
                results[url] = (ok, why)
                done += 1
                print("[%2d/%2d] %s %s" % (done, total, "OK  " if ok else "FALHA", url))
                time.sleep(0)

    alive = [e for e in entries if results.get(e["url"], (False, ""))[0]]
    dead = [e for e in entries if not results.get(e["url"], (False, ""))[0]]

    if not alive:
        print("\nNenhum canal funcionando. lista5.m3u mantido intacto.")
        with open(REPORT.format(stamp), "w", encoding="utf-8") as fh:
            fh.write("Teste %s\nNenhum dos %d canais respondeu.\n" % (stamp, total))
        return 1

    shutil.copy2(PLAYLIST, BACKUP.format(stamp))
    with open(PLAYLIST, "w", encoding="utf-8") as fh:
        fh.write("\n".join(header) + "\n")
        for e in alive:
            fh.write(e["extinf"] + "\n" + e["url"] + "\n")

    with open(REPORT.format(stamp), "w", encoding="utf-8") as fh:
        fh.write("Teste de canais em lista5.m3u - %s\n" % stamp)
        fh.write("Total: %d | Funcionando: %d | Removidos: %d\n\n"
                 % (total, len(alive), len(dead)))
        fh.write("REMOVIDOS (%d)\n" % len(dead))
        for e in dead:
            fh.write("- %s [%s]\n  %s\n" % (results[e["url"]][1], e["url"],
                                             e["extinf"][:160]))
        fh.write("\nMANTIDOS (%d)\n" % len(alive))
        for e in alive:
            fh.write("- %s\n" % e["url"])

    print("\nTotal: %d | Funcionando: %d | Removidos: %d"
          % (total, len(alive), len(dead)))
    print("Backup: %s | Relatorio: %s" % (BACKUP.format(stamp), REPORT.format(stamp)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
