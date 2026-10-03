#!/usr/bin/env python3
"""Testa todos os canais do lista5.m3u, remove os que nao funcionam e
sobrescreve o arquivo original (com backup previo)."""

import concurrent.futures as cf
import json
import os
import re
import shutil
import sys
import threading
import time
from datetime import datetime
from urllib.parse import urljoin, urlparse

import requests

PLAYLIST = "lista5.m3u"
RESULTS = "l5_test_results_now.json"
REPORT = "relatorio_lista5_teste_now.txt"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
TIMEOUT = 12
RETRIES = 2

_local = threading.local()


def session():
    s = getattr(_local, "s", None)
    if s is None:
        s = requests.Session()
        s.headers.update({
            "User-Agent": UA,
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
        })
        _local.s = s
    return s


# ---------------------------------------------------------------- playlist io
def parse_m3u(path):
    """Retorna lista de (info_line, url) preservando a ordem do arquivo."""
    entries = []
    info = None
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            line = raw.rstrip("\r\n")
            if not line.strip():
                continue
            if line.startswith("#EXTINF"):
                info = line
            elif line.startswith("#"):
                continue
            else:
                entries.append((info or "#EXTINF:-1,Canal", line.strip()))
                info = None
    return entries


def write_m3u(path, entries):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("#EXTM3U\n")
        for info, url in entries:
            fh.write(info + "\n")
            fh.write(url + "\n")


# ------------------------------------------------------------------ hls logic
def _resolve(base, ref):
    if ref.startswith(("http://", "https://")):
        return ref
    if ref.startswith("//"):
        return "https:" + ref
    return urljoin(base, ref)


def _attr(line, name):
    m = re.search(r'%s=(?:"([^"]*)"|([^,]*))' % re.escape(name), line)
    return (m.group(1) if m and m.group(1) is not None
            else (m.group(2).strip() if m else None))


def parse_manifest(text):
    """Retorna (media_urls, is_media) a partir de um manifesto HLS."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines or not lines[0].startswith("#EXTM3U"):
        raise ValueError("manifesto invalido (sem #EXTM3U)")

    variants, media = [], []
    extinf = None
    is_media_playlist = False
    for line in lines[1:]:
        if line.startswith("#EXT-X-STREAM-INF"):
            extinf = line
            is_media_playlist = False
        elif line.startswith("#EXTINF"):
            extinf = line
        elif line.startswith("#EXT-X-MEDIA"):
            if 'URI="' in line:
                m = re.search(r'URI="([^"]+)"', line)
                if m:
                    variants.append(m.group(1))
        elif line.startswith("#"):
            if line.startswith("#EXT-X-TARGETDURATION") or \
               line.startswith("#EXT-X-MEDIA-SEQUENCE"):
                is_media_playlist = True
        else:
            if extinf is not None:
                variants.append(line)
                extinf = None
            media.append(line)

    if is_media_playlist and not variants:
        variants = media
    return variants, media, is_media_playlist


def _looks_media(data):
    if not data or len(data) < 8:
        return False
    # MPEG-TS: sync byte 0x47
    if data[0] == 0x47:
        return True
    # fMP4: ....ftyp / ....moof / ....styp
    if data[4:8] in (b"ftyp", b"styp", b"moof"):
        return True
    # AAC/MP3 ID3
    if data[0:3] == b"ID3" or data[0:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        return True
    return False


def check_media(url, hdrs=None):
    r = session().get(url, timeout=TIMEOUT, stream=True,
                      headers=hdrs or {}, allow_redirects=True)
    code = r.status_code
    ctype = (r.headers.get("Content-Type") or "").lower()
    r.close()
    if code != 200:
        return False, "HTTP %d no manifest" % code
    if "mpegurl" not in ctype and "audio" not in ctype and \
       "video" not in ctype and "octet-stream" not in ctype and \
       "vnd.apple" not in ctype:
        # alguns CDNs devolvem text/plain para m3u8
        if "text/plain" not in ctype:
            return False, "content-type inesperado: %s" % ctype
    return True, "ok"


def test_url(url):
    """Retorna (ok, motivo, detalhe)."""
    last_err = "desconhecido"
    for attempt in range(RETRIES):
        try:
            r = session().get(url, timeout=TIMEOUT, allow_redirects=True)
            if r.status_code != 200:
                last_err = "HTTP %d" % r.status_code
                time.sleep(0.5)
                continue
            text = r.text
            variants, media, is_media = parse_manifest(text)
            if not variants and not media:
                last_err = "manifesto sem variantes/segmentos"
                time.sleep(0.5)
                continue

            # 1) ja e media playlist -> testa um segmento
            if is_media and media:
                seg = _resolve(url, media[-1])
                seg_ok, seg_err = _probe_segment(seg)
                if not seg_ok:
                    last_err = "segmento invalido: %s" % seg_err
                    time.sleep(0.5)
                    continue
                return True, "OK (media playlist)", {
                    "tipo": "media",
                    "segmento": seg,
                    "bytes": r.content.__len__(),
                }

            # 2) master playlist -> testa variantes ate uma responder
            tested, errors = 0, []
            # ordena por bandwidth descendente (melhor qualidade primeiro)
            def bw(u):
                seg = [l for l in text.splitlines() if u in l]
                for l in seg:
                    if l.startswith("#EXT-X-STREAM-INF"):
                        v = _attr(l, "BANDWIDTH")
                        if v and v.isdigit():
                            return int(v)
                return 0
            cands = sorted(dict.fromkeys(variants), key=bw, reverse=True)
            for v in cands:
                vu = _resolve(url, v)
                try:
                    vr = session().get(vu, timeout=TIMEOUT)
                    if vr.status_code != 200:
                        errors.append("HTTP %d" % vr.status_code)
                        continue
                    vv, vm, vmedia = parse_manifest(vr.text)
                    if vmedia and vm:
                        seg_ok, seg_err = _probe_segment(_resolve(vu, vm[-1]))
                        if seg_ok:
                            return True, "OK (master, %d variante(s) ok)" % (tested + 1), {
                                "tipo": "master",
                                "variante": vu,
                                "segmento": _resolve(vu, vm[-1]),
                                "variantes_total": len(cands),
                            }
                        errors.append("segmento: %s" % seg_err)
                    elif vv:
                        errors.append("sub-manifesto sem segmentos")
                    else:
                        errors.append("vazio")
                except Exception as exc:  # noqa: BLE001
                    errors.append(type(exc).__name__)
                tested += 1
            last_err = "variantes falharam: %s" % ", ".join(errors[:4])
            time.sleep(0.5)
        except requests.exceptions.SSLError as exc:
            last_err = "SSL: %s" % str(exc)[:80]
            break
        except requests.exceptions.Timeout:
            last_err = "timeout"
            time.sleep(0.5)
        except Exception as exc:  # noqa: BLE001
            last_err = "%s: %s" % (type(exc).__name__, str(exc)[:80])
            time.sleep(0.5)
    return False, last_err, {}


def _probe_segment(seg_url, bytes_needed=120000):
    try:
        r = session().get(seg_url, timeout=TIMEOUT, stream=True,
                          allow_redirects=True)
        if r.status_code != 200:
            return False, "HTTP %d" % r.status_code
        buf = b""
        for chunk in r.iter_content(65536):
            buf += chunk
            if len(buf) >= bytes_needed:
                break
        r.close()
        if len(buf) < 100:
            return False, "segmento curto (%d bytes)" % len(buf)
        if not _looks_media(buf):
            return False, "conteudo nao e midia (nao TS/fMP4)"
        return True, "ok"
    except Exception as exc:  # noqa: BLE001
        return False, "%s" % type(exc).__name__


# --------------------------------------------------------------------- driver
def main():
    if not os.path.exists(PLAYLIST):
        sys.exit("arquivo %s nao encontrado" % PLAYLIST)

    entries = parse_m3u(PLAYLIST)
    total_raw = len(entries)

    # remove URLs duplicadas (mantem a primeira ocorrencia / melhor master)
    seen, uniq = set(), []
    dups = 0
    for info, url in entries:
        key = url.strip()
        if key in seen:
            dups += 1
            continue
        seen.add(key)
        uniq.append((info, url))
    entries = uniq

    print("=" * 68)
    print("TESTE DE CANAIS - %s" % PLAYLIST)
    print("entradas: %d | duplicadas removidas do teste: %d | a testar: %d"
          % (total_raw, dups, len(entries)))
    print("=" * 68)

    results = []
    with cf.ThreadPoolExecutor(max_workers=8) as pool:
        futs = {pool.submit(test_url, u): (i, u) for i, (_, u) in enumerate(entries)}
        for n, fut in enumerate(cf.as_completed(futs), 1):
            idx, url = futs[fut]
            ok, reason, detail = fut.result()
            info = entries[idx][0]
            name = info.split(",", 1)[1] if "," in info else url
            results.append({
                "url": url, "name": name, "info": info,
                "ok": ok, "reason": reason, "detail": detail,
            })
            print("[%2d/%2d] %-4s %-38s %s"
                  % (n, len(entries), "OK" if ok else "FAIL",
                     name[:38], reason[:70]))

    results.sort(key=lambda r: entries.index(
        next(x for x in entries if x[1] == r["url"])))

    with open(RESULTS, "w", encoding="utf-8") as fh:
        json.dump({
            "arquivo": PLAYLIST,
            "data": datetime.now().isoformat(timespec="seconds"),
            "total_original": total_raw,
            "duplicadas": dups,
            "total_testado": len(results),
            "funcionando": sum(1 for r in results if r["ok"]),
            "resultados": results,
        }, fh, indent=2, ensure_ascii=False)

    ok_entries = [(r["info"], r["url"]) for r in results if r["ok"]]

    with open(REPORT, "w", encoding="utf-8") as fh:
        fh.write("RELATORIO DE TESTE - %s\n" % PLAYLIST)
        fh.write("data: %s\n" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        fh.write("=" * 70 + "\n")
        fh.write("canais no arquivo original : %d\n" % total_raw)
        fh.write("urls duplicadas             : %d\n" % dups)
        fh.write("urls testadas               : %d\n" % len(results))
        fh.write("funcionando                 : %d\n" % len(ok_entries))
        fh.write("removidos                   : %d\n"
                 % (len(results) - len(ok_entries)))
        fh.write("=" * 70 + "\n\nFUNCIONANDO\n" + "-" * 70 + "\n")
        for r in results:
            if r["ok"]:
                fh.write("  OK   %-40s %s\n" % (r["name"][:40], r["reason"]))
        fh.write("\nREMOVIDOS\n" + "-" * 70 + "\n")
        for r in results:
            if not r["ok"]:
                fh.write("  FAIL %-40s %s\n" % (r["name"][:40], r["reason"]))
                fh.write("       %s\n" % r["url"][:150])

    if ok_entries:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = "%s.bak.pre_teste_%s" % (PLAYLIST, stamp)
        shutil.copy2(PLAYLIST, backup)
        write_m3u(PLAYLIST, ok_entries)
        print("\nbackup: %s" % backup)
        print("lista5.m3u sobrescrito: %d canais mantidos" % len(ok_entries))
    else:
        print("\nNENHUM canal funcionando - arquivo NAO foi alterado.")

    print("relatorio: %s | json: %s" % (REPORT, RESULTS))
    print("funcionando %d / %d testados" % (len(ok_entries), len(results)))


if __name__ == "__main__":
    main()