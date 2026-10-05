#!/usr/bin/env python3
"""Testa todos os canais da lista5.m3u, remove os que nao funcionam e sobrescreve a lista."""
import concurrent.futures
import json
import os
import re
import shutil
import sys
import time
from datetime import datetime
from urllib.parse import urljoin

import requests

INPUT = "lista5.m3u"
OUTPUT = "lista5.m3u"
REPORT = "relatorio_lista5_teste_20261005_v2.txt"
JSON_OUT = "l5_teste_results_20261005_v2.json"

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


def encrypted_keys(text):
    """Retorna os metodos de DRM declarados no playlist (fora de NONE)."""
    found = []
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln.startswith("#EXT-X-KEY:") and not ln.startswith("#EXT-X-SESSION-KEY:"):
            continue
        for part in ln.split(","):
            if "METHOD=" in part:
                m = part.split("METHOD=")[1].strip().strip('"').upper()
                if m and m != "NONE" and m not in found:
                    found.append(m)
    return found


VIDEO_CODECS = ("avc1", "avc3", "hvc1", "hev1", "av01", "vp09", "vp9", "mp4v", "dvh1", "dvhe")
AUDIO_CODECS = ("mp4a", "ac-3", "ec-3", "ac3", "ec3", "opus", "vorbis")
AUDIO_EXT = (".aac", ".mp4a", ".m4a", ".mp3", ".ac3", ".eac3", ".ec3")
MUXED_EXT = (".ts", ".mpegts", ".tsa", ".m2ts", ".mpg", ".mpeg", ".flv", ".f4v")


def codecs_of(text):
    """Codecs declarados em EXT-X-STREAM-INF / EXT-X-MAP (fonte autoritativa)."""
    found = []
    for ln in text.splitlines():
        ln = ln.strip()
        if not (ln.startswith("#EXT-X-STREAM-INF:") or ln.startswith("#EXT-X-MAP:")):
            continue
        m = re.search(r'CODECS="([^"]*)"', ln)
        if m:
            values = m.group(1).split(",")
        else:
            m = re.search(r"(?:^|,)CODECS=([^,]+)", ln)
            values = m.group(1).split(",") if m else []
        for c in values:
            c = c.strip().strip('"').lower()
            if c:
                found.append(c)
    return found


def media_uris(text):
    """URIs de init map e de segmentos."""
    uris = []
    for ln in text.splitlines():
        ln = ln.strip()
        if ln.startswith("#EXT-X-MAP:"):
            uris.append(ln.split("URI=", 1)[1].split(",")[0].strip().strip('"').strip("'"))
        elif not ln.startswith("#") and ln:
            uris.append(ln)
    return [u for u in uris if u]


def classify(text):
    """Classifica a midia como 'video+audio', 'video' ou 'audio'."""
    codecs = codecs_of(text)
    has_v = any(c.startswith(VIDEO_CODECS) for c in codecs)
    has_a = any(c.startswith(AUDIO_CODECS) for c in codecs)
    if codecs and (has_v or has_a):
        if has_v and has_a:
            return "video+audio"
        return "video" if has_v else "audio"

    uris = media_uris(text)
    if not uris:
        return "desconhecido"
    tail = [u.split("?")[0].lower() for u in uris]
    if any(t.endswith(AUDIO_EXT) for t in tail):
        return "audio"
    if any(t.endswith(MUXED_EXT) for t in tail):
        return "video+audio"
    if any("_video" in t or "/video" in t for t in tail):
        return "video"
    if any("_audio" in t or "/audio" in t or "audio-aac" in t for t in tail):
        return "audio"
    return "desconhecido"


def pick_segments(ptext, base):
    segs, lines = [], [ln.strip() for ln in ptext.splitlines() if ln.strip()]
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
    return segs[:3]


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
    """Resolve as variantes de uma master playlist e devolve as acessiveis."""
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


def validate_playlist(url, text, enforce_media=True):
    """Valida um playlist HLS ja resolvido ate o nivel de segmentos."""
    drm = encrypted_keys(text)
    if drm:
        return False, f"protegido_drm={','.join(drm)} (nao toca em player comum)"

    kind = classify(text)
    if enforce_media:
        if kind == "audio":
            return False, "somente_audio (sem video)"
        if kind == "video":
            return False, "somente_video (sem audio)"

    segs = pick_segments(text, url)
    if not segs:
        return False, "sem segmentos"

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS_SEG) as ex:
        futs = [ex.submit(probe_segment, s) for s in segs]
        oks = [f.result() for f in futs]
    nok = sum(1 for ok, _ in oks if ok)
    if nok:
        return True, f"[{kind}] segmentos {nok}/{len(segs)} ok"
    return False, f"[{kind}] segmentos falharam: {oks[0][1]}"


def test_url(url):
    last = ""
    for attempt in range(1, RETRIES + 1):
        try:
            r = fetch(url)
            if r.status_code >= 400:
                last = f"http={r.status_code}" + (" (possivel bloqueio geografico)" if r.status_code in (401, 403) else "")
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
                    if classify(text) == "audio":
                        last = "master somente_audio"
                        time.sleep(1.5 * attempt)
                        continue
                    ok_vars, checked = probe_variants(r.url, text)
                    if not ok_vars:
                        bad = ", ".join(checked[:3]) if checked else "sem variantes"
                        last = f"master ok mas variantes inacessiveis [{bad}]"
                        time.sleep(1.5 * attempt)
                        continue
                    failures = []
                    for bw, target, pr in ok_vars:
                        ok, why = validate_playlist(pr.url, pr.text, enforce_media=False)
                        if ok:
                            return url, True, f"master->variante {bw // 1000}kbps | {why}"
                        failures.append(f"{bw // 1000}kbps:{why}")
                    last = "master->variantes rejeitadas [" + "; ".join(failures[:3]) + "]"
                    time.sleep(1.5 * attempt)
                    continue

                ok, why = validate_playlist(r.url, text)
                if ok:
                    return url, True, why
                last = why
                time.sleep(1.5 * attempt)
                continue

            if any(k in ctype for k in ("video", "audio", "mp2t", "octet-stream", "mpeg")):
                return url, True, f"direto ok http={r.status_code} {len(body)}B {ctype.split(';')[0]}"

            last = f"tipo_invalido={ctype.split(';')[0] or 'desconhecido'} http={r.status_code}"
        except requests.exceptions.SSLError:
            last = "ssl=SSLError"
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

    backup = f"{INPUT}.bak.pre_teste_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(INPUT, backup)

    entries = parse_m3u(INPUT)
    urls, seen = [], set()
    for e in entries:
        for u in e["urls"]:
            if u not in seen:
                seen.add(u)
                urls.append(u)

    print(f"Backup: {backup}")
    print(f"Entradas em {INPUT}: {len(entries)}")
    print(f"URLs unicas a testar: {len(urls)}")
    print(f"Iniciando teste com {WORKERS} workers, {RETRIES} tentativas por URL\n")

    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futures = {ex.submit(test_url, u): u for u in urls}
        for i, fut in enumerate(concurrent.futures.as_completed(futures), 1):
            url, ok, reason = fut.result()
            results[url] = {"ok": ok, "reason": reason}
            print(f"[{i}/{len(urls)}] {'OK  ' if ok else 'FALHA'} {reason} | {url[:70]}")

    kept, removed = [], []
    written = set()
    dup = 0
    for e in entries:
        good = [u for u in e["urls"] if results.get(u, {}).get("ok")]
        fresh = []
        for u in good:
            key = (e["extinf"], u)
            if key in written:
                dup += 1
                continue
            written.add(key)
            fresh.append(u)
        if fresh:
            kept.append((e, fresh))
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
    print(f"Duplicados      : {dup}")
    for e in removed:
        print(f"  - REMOVIDO: {name_of(e)}")
    print(f"Lista sobrescrita: {OUTPUT}")

    lines = [
        "RELATORIO DE TESTE DE STREAM - lista5.m3u",
        f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Backup: {backup}",
        f"Entradas testadas: {len(entries)} | URLs: {len(urls)} | Funcionais: {ok_urls}",
        f"Canais mantidos: {len(kept)} | Canais removidos: {len(removed)} | Duplicados: {dup}",
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