#!/usr/bin/env python3
"""Testa todos os canais da lista5.m3u, remove os que nao funcionam e sobrescreve a lista."""
import concurrent.futures
import json
import os
import shutil
import sys
import time
from datetime import datetime
from urllib.parse import urljoin

import requests

INPUT = "lista5.m3u"
OUTPUT = "lista5.m3u"
REPORT = "relatorio_lista5_teste_20261003.txt"
JSON_OUT = "l5_teste_results_20261003.json"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": UA,
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "close",
}
TIMEOUT = (10, 15)
WORKERS = 8
RETRIES = 2
MAX_WORKERS_SEG = 3


def parse_m3u(path):
    entries = []
    cur = None
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n").rstrip("\r")
            if not line.strip():
                continue
            if line.startswith("#EXTM3U"):
                continue
            if line.startswith("#EXTINF:"):
                if cur:
                    entries.append(cur)
                cur = {"extinf": line, "urls": []}
            elif line.startswith("http://") or line.startswith("https://"):
                if cur is None:
                    cur = {"extinf": "#EXTINF:-1", "urls": []}
                cur["urls"].append(line)
    if cur:
        entries.append(cur)
    return entries


def fetch(url, headers=None, method="GET"):
    h = dict(HEADERS)
    if headers:
        h.update(headers)
    return requests.request(method, url, headers=h, timeout=TIMEOUT, allow_redirects=True)


def is_hls_playlist(text):
    return "#EXTM3U" in text[:4000]


def pick_segment(playlist_text, base_url):
    lines = [ln.strip() for ln in playlist_text.splitlines() if ln.strip()]
    for i, ln in enumerate(lines):
        if ln.startswith("#EXT-X-MAP:"):
            uri = ln.split("URI=", 1)[1].split(",")[0].strip().strip('"').strip("'")
            if uri:
                return urljoin(base_url, uri)
        if not ln.startswith("#") and not ln.startswith("http"):
            prev = lines[i - 1] if i else ""
            if prev.startswith("#EXTINF"):
                return urljoin(base_url, ln)
    for ln in lines:
        if not ln.startswith("#") and not ln.startswith("http"):
            return urljoin(base_url, ln)
    return None


def probe_segment(seg_url):
    try:
        r = fetch(seg_url, headers={"Range": "bytes=0-262143"})
        if r.status_code not in (200, 206):
            return False, f"seg_http={r.status_code}"
        body = r.content
        if not body:
            return False, "seg_vazio"
        head = body[:200].decode("utf-8", errors="ignore")
        if "<HTML>" in head or "Access Denied" in head:
            return False, "seg_bloqueado"
        return True, f"seg_ok={len(body)}B"
    except Exception as e:
        return False, f"seg_erro={type(e).__name__}"


def probe_variants(base_url, text):
    """Resolve as variantes de uma master playlist e devolve a de maior banda."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    cands = []
    for i, ln in enumerate(lines):
        if ln.startswith("#EXT-X-STREAM-INF:") and i + 1 < len(lines):
            nxt = lines[i + 1]
            if not nxt.startswith("#"):
                bw = 0
                for part in ln.split(","):
                    if "BANDWIDTH=" in part:
                        try:
                            bw = int(part.split("BANDWIDTH=")[1].split("-")[0])
                        except ValueError:
                            bw = 0
                cands.append((bw, urljoin(base_url, nxt)))
    if not cands:
        return [], []
    cands.sort(key=lambda x: x[0], reverse=True)
    checked, ok = [], []
    for bw, v in cands[:6]:
        try:
            r = fetch(v)
        except Exception as e:
            checked.append(f"{v}: erro={type(e).__name__}")
            continue
        checked.append(f"http={r.status_code}")
        if r.status_code == 200 and b"#EXTM3U" in r.content[:4000]:
            ok.append((bw, v, r))
    return ok, checked


def test_url(url):
    last = ""
    for attempt in range(1, RETRIES + 1):
        try:
            r = fetch(url)
            if r.status_code >= 400:
                last = f"http={r.status_code}"
                time.sleep(1.5 * attempt)
                continue
            ctype = (r.headers.get("Content-Type") or "").lower()
            body = r.content
            if not body:
                last = f"corpo_vazio http={r.status_code}"
                time.sleep(1.5 * attempt)
                continue

            if "mpegurl" in ctype or is_hls_playlist(body[:4000].decode("utf-8", "ignore")):
                text = body.decode("utf-8", "ignore")

                if "#EXT-X-STREAM-INF" in text:
                    ok_vars, checked = probe_variants(r.url, text)
                    if not ok_vars:
                        bad = ", ".join(checked[:3]) if checked else "sem variantes"
                        last = f"master ok mas variantes inacessiveis [{bad}]"
                        time.sleep(1.5 * attempt)
                        continue
                    bw, target, pr = ok_vars[0]
                    base, ptext = pr.url, pr.text
                    note = f"master->variante {bw // 1000}kbps"
                else:
                    base, ptext, note = r.url, text, "media playlist"

                segs = []
                lines = [ln.strip() for ln in ptext.splitlines() if ln.strip()]
                for ln in lines:
                    if ln.startswith("#EXT-X-MAP:"):
                        uri = ln.split("URI=", 1)[1].split(",")[0].strip().strip('"').strip("'")
                        if uri:
                            segs.append(urljoin(base, uri))
                for i, ln in enumerate(lines):
                    if not ln.startswith("#") and i and lines[i - 1].startswith("#EXTINF"):
                        segs.append(urljoin(base, ln))
                    if len(segs) >= 3:
                        break

                if not segs:
                    last = f"{note} sem segmentos"
                    time.sleep(1.5 * attempt)
                    continue

                with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
                    futs = [ex.submit(probe_segment, s) for s in segs[:3]]
                    oks = [f.result() for f in futs]
                nok = sum(1 for ok, _ in oks if ok)
                if nok:
                    return url, True, f"{note} | segmentos {nok}/{len(segs[:3])} ok"
                last = f"{note} | segmentos falharam: {oks[0][1]}"
                time.sleep(1.5 * attempt)
                continue

            if any(k in ctype for k in ("video", "audio", "mp2t", "octet-stream", "mpeg")):
                return url, True, f"direto ok http={r.status_code} {len(body)}B {ctype.split(';')[0]}"

            last = f"tipo_invalido={ctype.split(';')[0] or 'desconhecido'} http={r.status_code}"
        except requests.exceptions.SSLError as e:
            last = f"ssl={type(e).__name__}"
        except requests.exceptions.Timeout:
            last = "timeout"
        except requests.exceptions.ConnectionError:
            last = "conexao_recusada"
        except requests.exceptions.TooManyRedirects:
            last = "muitos_redirects"
        except requests.exceptions.RequestException as e:
            last = f"erro={type(e).__name__}"
        if attempt < RETRIES:
            time.sleep(1.5 * attempt)
    return url, False, last or "desconhecido"


def name_of(entry):
    return entry["extinf"].split(",")[-1].strip() if "," in entry["extinf"] else entry["extinf"]


def main():
    if not os.path.exists(INPUT):
        print(f"ERRO: {INPUT} nao encontrado")
        return 1

    entries = parse_m3u(INPUT)
    urls = []
    seen = set()
    for e in entries:
        for u in e["urls"]:
            if u not in seen:
                seen.add(u)
                urls.append(u)

    print(f"Entradas em {INPUT}: {len(entries)}")
    print(f"URLs unicas a testar: {len(urls)}")
    print(f"Iniciando teste com {WORKERS} workers, {RETRIES} tentativas por URL\n")

    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futures = {ex.submit(test_url, u): u for u in urls}
        for i, fut in enumerate(concurrent.futures.as_completed(futures), 1):
            url, ok, reason = fut.result()
            results[url] = {"ok": ok, "reason": reason}
            print(f"[{i}/{len(urls)}] {'OK  ' if ok else 'FALHA'} {reason} | {url[:90]}")

    kept, removed = [], []
    for e in entries:
        good = [u for u in e["urls"] if results.get(u, {}).get("ok")]
        if good:
            kept.append((e, good))
        else:
            removed.append(e)

    if kept:
        tmp = OUTPUT + ".new"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            for e, good in kept:
                f.write(e["extinf"] + "\n")
                for u in good:
                    f.write(u + "\n")
        shutil.move(tmp, OUTPUT)
    else:
        print("\nAVISO: nenhum canal funcional, lista5.m3u mantida intacta.")

    ok_urls = sum(1 for v in results.values() if v["ok"])
    print("")
    print(f"URLs funcionais : {ok_urls}/{len(urls)}")
    print(f"Canais mantidos  : {len(kept)}")
    print(f"Canais removidos : {len(removed)}")
    for e in removed:
        print(f"  - REMOVIDO: {name_of(e)}")
    print(f"Lista sobrescrita: {OUTPUT}")

    lines = [
        "RELATORIO DE TESTE DE STREAM - lista5.m3u",
        f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Entradas testadas: {len(entries)} | URLs: {len(urls)} | Funcionais: {ok_urls}",
        "",
        "=== CANAIS MANTIDOS ===",
    ]
    for e, good in kept:
        lines.append(f"[OK] {name_of(e)}")
        for u in good:
            lines.append(f"     {results[u]['reason']} | {u}")
    lines.append("")
    lines.append("=== CANAIS REMOVIDOS ===")
    for e in removed:
        lines.append(f"[FALHA] {name_of(e)}")
        for u in e["urls"]:
            lines.append(f"     {results.get(u, {}).get('reason', 'nao testado')} | {u}")
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    with open(JSON_OUT, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"Relatorio: {REPORT}")
    print(f"JSON: {JSON_OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())