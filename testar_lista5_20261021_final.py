#!/usr/bin/env python3
"""Testa todos os canais da lista5.m3u, remove os que nao funcionam e sobrescreve a lista.

Metodo de validacao (por canal):
  manifest -> master? -> melhor variante -> segmento real (bytes de midia)
  O audio e confirmado de duas formas: CODECS do master (video+audio muxado) ou
  grupo EXT-X-MEDIA TYPE=AUDIO (rendition de audio validada na parte).
"""
import concurrent.futures
import json
import os
import re
import shutil
import sys
import time
from datetime import datetime
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests

INPUT = "lista5.m3u"
OUTPUT = "lista5.m3u"
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
REPORT = f"relatorio_lista5_teste_{STAMP}_final.txt"
JSON_OUT = f"l5_teste_results_{STAMP}_final.json"
EPG_URL = "https://raw.githubusercontent.com/gratinomaster/JCTVV/main/lista5_epg.xml.gz"

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
TIMEOUT = (10, 20)
WORKERS = 8
RETRIES = 2
MAX_WORKERS_SEG = 3

VIDEO_CODECS = ("avc1", "avc3", "hvc1", "hev1", "av01", "vp09", "vp9", "mp4v", "dvh1", "dvhe")
AUDIO_CODECS = ("mp4a", "ac-3", "ec-3", "ac3", "ec3", "opus", "vorbis")


def inherit_query(parent, child):
    """Filho sem query herda a query do pai (token hdnea/dvt2 etc)."""
    if not parent or not child:
        return child
    p, c = urlsplit(parent), urlsplit(child)
    if c.query or not p.query:
        return child
    return urlunsplit((c.scheme, c.netloc, c.path, p.query, c.fragment))


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


def fetch(url, headers=None):
    h = dict(HEADERS)
    if headers:
        h.update(headers)
    return requests.get(url, headers=h, timeout=TIMEOUT, allow_redirects=True)


def is_hls_playlist(text):
    return "#EXTM3U" in text[:4000]


def encrypted_keys(text):
    found = []
    for ln in text.splitlines():
        ln = ln.strip()
        if not (ln.startswith("#EXT-X-KEY:") or ln.startswith("#EXT-X-SESSION-KEY:")):
            continue
        for part in ln.split(","):
            if "METHOD=" in part:
                m = part.split("METHOD=")[1].strip().strip('"').upper()
                if m and m != "NONE" and m not in found:
                    found.append(m)
    return found


def codecs_of(text):
    found = []
    for ln in text.splitlines():
        ln = ln.strip()
        if not (ln.startswith("#EXT-X-STREAM-INF:") or ln.startswith("#EXT-X-MAP:")):
            continue
        m = re.search(r'CODECS="([^"]*)"', ln)
        values = m.group(1).split(",") if m else []
        for c in values:
            c = c.strip().strip('"').lower()
            if c:
                found.append(c)
    return found


def has_video(codecs):
    return any(c.startswith(VIDEO_CODECS) for c in codecs)


def has_audio(codecs):
    return any(c.startswith(AUDIO_CODECS) for c in codecs)


def parse_master(text, base):
    """Retorna (variantes, audio_renditions) do master."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    variants = []
    audio = []
    for i, ln in enumerate(lines):
        if ln.startswith("#EXT-X-STREAM-INF:"):
            nxt = lines[i + 1] if i + 1 < len(lines) else ""
            if nxt and not nxt.startswith("#"):
                bw = 0
                for part in ln.split(","):
                    if "BANDWIDTH=" in part:
                        try:
                            bw = int(part.split("BANDWIDTH=")[1].split("-")[0])
                        except ValueError:
                            bw = 0
                m = re.search(r'CODECS="([^"]*)"', ln)
                variants.append(
                    {
                        "bw": bw,
                        "url": inherit_query(base, urljoin(base, nxt)),
                        "codecs": [c.lower() for c in (m.group(1).split(",") if m else [])],
                        "audio_group": (re.search(r'AUDIO="([^"]*)"', ln) or [None, ""])[1]
                        if re.search(r'AUDIO="([^"]*)"', ln)
                        else "",
                    }
                )
        elif ln.startswith("#EXT-X-MEDIA:") and "TYPE=AUDIO" in ln:
            m = re.search(r'URI="([^"]*)"', ln)
            gid = re.search(r'GROUP-ID="([^"]*)"', ln)
            if m:
                audio.append(
                    {
                        "url": inherit_query(base, urljoin(base, m.group(1))),
                        "group": gid.group(1) if gid else "",
                    }
                )
    variants.sort(key=lambda x: x["bw"], reverse=True)
    return variants, audio


def media_uris(text):
    uris = []
    for ln in text.splitlines():
        ln = ln.strip()
        if ln.startswith("#EXT-X-MAP:"):
            uris.append(ln.split("URI=", 1)[1].split(",")[0].strip().strip('"').strip("'"))
        elif not ln.startswith("#") and ln:
            uris.append(ln)
    return [u for u in uris if u]


def pick_segments(ptext, base):
    segs, lines = [], [ln.strip() for ln in ptext.splitlines() if ln.strip()]
    for ln in lines:
        if ln.startswith("#EXT-X-MAP:"):
            uri = ln.split("URI=", 1)[1].split(",")[0].strip().strip('"').strip("'")
            if uri:
                segs.append(inherit_query(base, urljoin(base, uri)))
    for i, ln in enumerate(lines):
        if not ln.startswith("#") and i and lines[i - 1].startswith("#EXTINF"):
            segs.append(inherit_query(base, urljoin(base, ln)))
        if len(segs) >= 3:
            break
    return segs[:3]


def is_media_bytes(body):
    """Confere se o corpo e midia real (fMP4 / MPEG-TS) e nao HTML/erro."""
    if not body or len(body) < 1024:
        return False, "corpo_pequeno"
    head = body[:300].decode("utf-8", errors="ignore")
    if "<HTML" in head.upper() or "ACCESS DENIED" in head.upper() or "<!DOCTYPE" in head:
        return False, "html_erro"
    if body[4:8] == b"ftyp" or b"ftyp" in body[:32]:
        return True, "fmp4"
    if body[0] == 0x47 and len(body) > 188 and body[188] == 0x47:
        return True, "mpegts"
    if body[:3] == b"\xff\xfb\x00" or body[:2] == b"ID":
        return False, "somente_audio"
    return True, f"binario_{len(body)}B"


def probe_segment(seg_url):
    try:
        r = fetch(seg_url, headers={"Range": "bytes=0-262143"})
        if r.status_code not in (200, 206):
            return False, f"seg_http={r.status_code}"
        ok, why = is_media_bytes(r.content)
        return ok, f"seg_{why}"
    except requests.exceptions.Timeout:
        return False, "seg_timeout"
    except requests.exceptions.RequestException as e:
        return False, f"seg_erro={type(e).__name__}"


def probe_segments(segs):
    if not segs:
        return 0, 0, "sem_segmentos"
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS_SEG) as ex:
        res = [f.result() for f in [ex.submit(probe_segment, s) for s in segs]]
    nok = sum(1 for ok, _ in res if ok)
    return nok, len(segs), res[0][1]


def media_kind(text):
    """Classifica o media playlist: video+audio / video / audio."""
    codecs = codecs_of(text)
    if codecs:
        if has_video(codecs) and has_audio(codecs):
            return "video+audio"
        if has_video(codecs):
            return "video"
        if has_audio(codecs):
            return "audio"
    uris = [u.split("?")[0].lower() for u in media_uris(text)]
    if any(t.endswith((".ts", ".mpegts", ".m2ts", ".tsa")) for t in uris):
        return "video+audio"
    v = any(k in t for t in uris for k in ("_video", "/video", "-video", "_av", "/av_"))
    a = any(k in t for t in uris for k in ("_audio", "/audio", "-audio", "audio_", "audio-"))
    if v and a:
        return "video+audio"
    if v:
        return "video"
    if a:
        return "audio"
    return "desconhecido"


def validate_media_playlist(url, text):
    """Valida um media playlist (variante). Retorna (ok, kind, motivo)."""
    if encrypted_keys(text):
        return False, "drm", "protegido_drm"
    segs = pick_segments(text, url)
    nok, total, why = probe_segments(segs)
    if not nok:
        return False, "erro", f"segmentos_falharam({why})"
    kind = media_kind(text)
    return True, kind, f"segmentos {nok}/{total} ok | {kind}"


def validate_audio_rendition(url):
    """Valida a rendition de audio referenciada no EXT-X-MEDIA. Retorna (ok, motivo)."""
    try:
        r = fetch(url)
        if r.status_code >= 400:
            return False, f"audio_http={r.status_code}"
        text = r.text
        if not is_hls_playlist(text):
            return False, "audio_nao_e_playlist"
        segs = pick_segments(text, r.url)
        nok, total, why = probe_segments(segs)
        if not nok:
            return False, f"audio_segmentos_falharam({why})"
        return True, f"audio_segmentos {nok}/{total} ok"
    except requests.exceptions.RequestException as e:
        return False, f"audio_erro={type(e).__name__}"


def test_url(url):
    """Retorna (url, ok, tem_audio, motivo, score). score maior = melhor."""
    last = ""
    for attempt in range(1, RETRIES + 1):
        try:
            r = fetch(url)
            if r.status_code >= 400:
                last = f"http={r.status_code}" + (
                    " (token expirado/bloqueio)" if r.status_code in (401, 403) else ""
                )
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
                    if encrypted_keys(text):
                        last = "protegido_drm (nao toca em player comum)"
                        time.sleep(1.5 * attempt)
                        continue
                    variants, audios = parse_master(text, r.url)
                    if not variants:
                        last = "master sem variantes"
                        time.sleep(1.5 * attempt)
                        continue
                    failures = []
                    for v in variants[:6]:
                        try:
                            pr = fetch(v["url"])
                        except requests.exceptions.RequestException as e:
                            failures.append(f"{v['bw'] // 1000}kbps:erro={type(e).__name__}")
                            continue
                        if pr.status_code != 200 or not is_hls_playlist(pr.text):
                            failures.append(f"{v['bw'] // 1000}kbps:http={pr.status_code}")
                            continue
                        ok, kind, why = validate_media_playlist(pr.url, pr.text)
                        if not ok:
                            failures.append(f"{v['bw'] // 1000}kbps:{why}")
                            continue
                        if kind == "video+audio":
                            return url, True, True, f"master->variante {v['bw'] // 1000}kbps | {why}", 1000 + v["bw"]
                        if kind != "video":
                            failures.append(f"{v['bw'] // 1000}kbps:{kind} (sem video)")
                            continue
                        # video em um segmento e audio em rendition separada
                        aud = [a for a in audios if v["audio_group"] and a["group"] == v["audio_group"]]
                        aok, awhy = (False, "sem_rendition_audio")
                        for a in aud[:2]:
                            aok, awhy = validate_audio_rendition(a["url"])
                            if aok:
                                break
                        if aok:
                            return (
                                url,
                                True,
                                True,
                                f"master->variante {v['bw'] // 1000}kbps | {why} | {awhy}",
                                1000 + v["bw"],
                            )
                        failures.append(f"{v['bw'] // 1000}kbps:audio separado quebrado ({awhy})")
                        continue
                    last = "master->variantes rejeitadas [" + "; ".join(failures[:3]) + "]"
                    time.sleep(1.5 * attempt)
                    continue

                ok, kind, why = validate_media_playlist(r.url, text)
                if ok and kind == "video+audio":
                    return url, True, True, f"playlist direta | {why}", 500
                if ok:
                    return url, False, False, f"playlist direta | {why} (sem audio)", 200
                last = why
                time.sleep(1.5 * attempt)
                continue

            if any(k in ctype for k in ("video", "audio", "mp2t", "octet-stream", "mpeg")):
                ok, why = is_media_bytes(body)
                if ok:
                    return url, True, True, f"direto ok http={r.status_code} {why}", 400
                last = f"direto invalido: {why}"
            else:
                last = f"tipo_invalido={ctype.split(';')[0] or 'desconhecido'} http={r.status_code}"
        except requests.exceptions.SSLError:
            last = "ssl=SSLError"
        except requests.exceptions.Timeout:
            last = "timeout"
        except requests.exceptions.ConnectionError:
            last = "conexao_recusada"
        except requests.exceptions.RequestException as e:
            last = f"erro={type(e).__name__}"
        if attempt < RETRIES:
            time.sleep(1.5 * attempt)
    return url, False, False, last or "desconhecido", -1


def name_of(entry):
    """Titulo do canal: tudo apos a primeira virgula do EXTINF."""
    if "," not in entry["extinf"]:
        return entry["extinf"].strip()
    return entry["extinf"].split(",", 1)[1].strip()


# nome do canal -> id no EPG local (lista5_epg.xml)
EPG_IDS = {
    "ABC News Live": "465150",
    "Fox Business HD": "464766",
    "Fox News Channel HD": "465372",
    "CBS News 24/7": "USBA370000104",
}
# titulos quebrados do scraper -> nome canonico do canal
TITLES = {
    "abc": "ABC News Live",
    "foxbusiness": "Fox Business HD",
    "foxnews": "Fox News Channel HD",
    "cbs": "CBS News 24/7",
}


def canonical_title(title, url):
    t = title.lower()
    u = url.lower()
    if "abcnews" in u or "abc news" in t or "abcnl" in t:
        return "ABC News Live"
    if "foxbusiness" in u or "fox business" in t:
        return "Fox Business HD"
    if "foxnews" in u or "fox news" in t:
        return "Fox News Channel HD"
    if "cbsnews" in u or "cbs news" in t:
        return "CBS News 24/7"
    return title


def build_extinf(logo, title):
    eid = EPG_IDS.get(title, "")
    attrs = []
    if eid:
        attrs.append(f'tvg-id="{eid}"')
    if logo:
        attrs.append(f'tvg-logo="{logo}"')
    attrs.append('group-title="NEWS WORLD"')
    return "#EXTINF:-1 " + " ".join(attrs) + "," + title


def main():
    if not os.path.exists(INPUT):
        print(f"ERRO: {INPUT} nao encontrado")
        return 1

    backup = f"{INPUT}.bak.pre_teste_{STAMP}"
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
    print(f"Iniciando teste com {WORKERS} workers, {RETRIES} tentativas por URL\n", flush=True)

    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futures = {ex.submit(test_url, u): u for u in urls}
        for i, fut in enumerate(concurrent.futures.as_completed(futures), 1):
            url, ok, aud, reason, score = fut.result()
            results[url] = {"ok": ok, "audio": aud, "reason": reason, "score": score}
            print(
                f"[{i}/{len(urls)}] {'OK  ' if ok else 'FALHA'} "
                f"{'A/V ' if aud else '    '}{reason} | {url[:70]}",
                flush=True,
            )

    # agrupa por canal canonico, ordena URLs por score (melhor primeiro) e dedup
    channels = {}
    for e in entries:
        title = canonical_title(name_of(e), e["urls"][0] if e["urls"] else "")
        logo = ""
        m = re.search(r'tvg-logo="([^"]*)"', e["extinf"])
        if m:
            logo = m.group(1)
        ch = channels.setdefault(title, {"logo": logo, "urls": {}})
        for u in e["urls"]:
            ch["urls"][u] = results.get(u, {"ok": False, "audio": False, "reason": "nao testado", "score": -1})

    kept, removed = [], []
    for title, ch in channels.items():
        good = [u for u, v in ch["urls"].items() if v["ok"] and v["audio"]]
        good.sort(key=lambda u: ch["urls"][u]["score"], reverse=True)
        if good:
            kept.append((title, ch["logo"], good, ch["urls"]))
        else:
            removed.append((title, ch["logo"], ch["urls"]))

    if kept:
        tmp = OUTPUT + ".new"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(f'#EXTM3U url-tvg="{EPG_URL}"\n')
            for title, logo, good, _ in kept:
                f.write(build_extinf(logo, title) + "\n")
                f.write(good[0] + "\n")
        shutil.move(tmp, OUTPUT)
    else:
        print("\nAVISO: nenhum canal funcional, lista5.m3u mantida intacta.")
        removed = []

    ok_urls = sum(1 for v in results.values() if v["ok"])
    print("")
    print(f"URLs funcionais : {ok_urls}/{len(urls)}")
    print(f"Canais mantidos  : {len(kept)}")
    print(f"Canais removidos : {len(removed)}")
    for title, _, _ in removed:
        print(f"  - REMOVIDO: {title}")
    print(f"Lista sobrescrita: {OUTPUT}")

    lines = [
        "RELATORIO DE TESTE DE STREAM - lista5.m3u",
        f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Backup: {backup}",
        f"Entradas testadas: {len(entries)} | URLs unicas: {len(urls)} | URLs funcionais: {ok_urls}",
        f"Canais mantidos: {len(kept)} | Canais removidos: {len(removed)}",
        "Metodo: manifest -> master -> melhor variante -> segmento real (bytes de midia)",
        "Audio: muxado no segmento ou em rendition EXT-X-MEDIA TYPE=AUDIO (validado)",
        "",
        "=== CANAIS MANTIDOS ===",
    ]
    for title, logo, good, allu in kept:
        lines.append(f"[OK] {title}  (tvg-id={EPG_IDS.get(title, '-')})")
        lines.append(f"     logo: {logo or '(sem)'}")
        lines.append(f"     usa: {good[0]}")
        lines.append(f"     {allu[good[0]]['reason']}")
        for u in good[1:]:
            lines.append(f"     (alternativa funcional) {u}")
    lines.append("")
    lines.append("=== CANAIS REMOVIDOS (sem nenhuma URL funcional) ===")
    if removed:
        for title, logo, allu in removed:
            lines.append(f"[FALHA] {title}")
            for u, v in allu.items():
                lines.append(f"     {v['reason']} | {u}")
    else:
        lines.append("(nenhum)")
    lines.append("")
    lines.append("=== URLS DESCARTADAS POR FALHAR ===")
    for title, logo, good, allu in kept:
        for u, v in allu.items():
            if u not in good:
                lines.append(f"[FALHA] {title}")
                lines.append(f"     {v['reason']} | {u}")
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    with open(JSON_OUT, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"Relatorio: {REPORT}")
    print(f"JSON: {JSON_OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
