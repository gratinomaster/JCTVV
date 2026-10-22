#!/usr/bin/env python3
"""Testa todos os canais do lista5.m3u, remove os que nao funcionam e sobrescreve o arquivo.

Cadeia de validacao (do mais forte ao mais fraco):
  manifest -> master -> melhor variante -> segmento real (bytes de midia)
  Tipo de midia conferido nos proprios bytes: fMP4 (sniff avc1/mp4a) ou
  MPEG-TS (PAT/PMT -> stream_type de video e audio).
  Audio separado (EXT-X-MEDIA TYPE=AUDIO) tambem e validado quando a variante
  de video nao embute audio.
  DRM (EXT-X-KEY METHOD != NONE) e reprovado: nao toca em player comum.

Canais sao agrupados (tvg-id ou titulo normalizado) e mantem apenas a melhor
URL funcional de cada canal. Cabecalho x-tvg-url e tvg-id do EPG (lista5_epg.xml.gz)
sao preservados/restaurados.
"""
import concurrent.futures
import gzip
import json
import os
import re
import shutil
import sys
import time
from datetime import datetime
from urllib.parse import urljoin

import requests

from testar_lista5_20261022 import (
    HEADERS,
    TIMEOUT,
    encrypted_keys,
    fetch,
    inherit_query,
    is_hls_playlist,
    parse_m3u,
)

INPUT = "lista5.m3u"
OUTPUT = "lista5.m3u"
EPG_LOCAL = "lista5_epg.xml.gz"
EPG_URL = "https://raw.githubusercontent.com/gratinomaster/JCTVV/main/lista5_epg.xml.gz"
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
REPORT = f"relatorio_lista5_{STAMP}.txt"
JSON_OUT = f"l5_resultados_{STAMP}.json"

WORKERS = 8
RETRIES = 2
MAX_SEG = 3

VIDEO_TYPES_TS = {0x01, 0x02, 0x10, 0x1B, 0x24, 0x51, 0x33, 0x34, 0xD1}
AUDIO_TYPES_TS = {0x03, 0x04, 0x0F, 0x11, 0x81, 0x06, 0x87}
VIDEO_BOX = (b"avc1", b"avc3", b"hvc1", b"hev1", b"av01", b"vp09", b"vp9", b"mp4v", b"dvh1", b"dvhe")
AUDIO_BOX = (b"mp4a", b"ac-3", b"ec-3", b"Opus", b"opus", b"fLaC", b"mp3")

# id do EPG (lista5_epg.xml.gz) por palavra chave do titulo do canal
EPG_MAP = (
    ("abc news", "ABCNewsLive.us"),
    ("fox business", "FoxBusiness.us"),
    ("cbs news", "CBSNews.us"),
)


# ---------------------------------------------------------------- MPEG-TS ---
def _ts_payload(pkt):
    afc = (pkt[3] >> 4) & 0x03
    if afc == 0:
        return None
    idx = 4
    if afc in (2, 3):
        if idx >= len(pkt):
            return None
        idx += 1 + pkt[idx]
    if afc == 2 or idx >= len(pkt):
        return None
    return pkt[idx:]


def _pat_pmt_pid(payload):
    if len(payload) < 12 or payload[0] != 0x00:
        return None
    sl = ((payload[1] & 0x0F) << 8) | payload[2]
    end = min(3 + sl - 4, len(payload))
    i = 8
    while i + 4 <= end:
        prog = (payload[i] << 8) | payload[i + 1]
        pid = ((payload[i + 2] & 0x1F) << 8) | payload[i + 3]
        if prog != 0:
            return pid
        i += 4
    return None


def _pmt_stream_types(payload):
    if len(payload) < 16 or payload[0] != 0x02:
        return set()
    sl = ((payload[1] & 0x0F) << 8) | payload[2]
    end = min(3 + sl - 4, len(payload))
    pi_len = ((payload[10] & 0x0F) << 8) | payload[11]
    i = 12 + pi_len
    types = set()
    while i + 5 <= end:
        st = payload[i]
        es_len = ((payload[i + 3] & 0x0F) << 8) | payload[i + 4]
        types.add(st)
        i += 5 + es_len
    return types


def ts_track_types(body):
    """Retorna (tem_video, tem_audio) lendo PAT/PMT de um segmento MPEG-TS."""
    pmt_pid = None
    for i in range(0, len(body) - 187, 188):
        pkt = body[i:i + 188]
        if pkt[0] != 0x47:
            continue
        pid = ((pkt[1] & 0x1F) << 8) | pkt[2]
        payload = _ts_payload(pkt)
        if payload is None:
            continue
        if pid == 0:
            if pmt_pid is None:
                pmt_pid = _pat_pmt_pid(payload)
        elif pmt_pid is not None and pid == pmt_pid:
            types = _pmt_stream_types(payload)
            v = any(t in VIDEO_TYPES_TS for t in types)
            a = any(t in AUDIO_TYPES_TS for t in types)
            return v, a
    return False, False


def sniff_tracks(body):
    """Retorna (tem_video, tem_audio) pelos boxes de sample entry (fMP4)."""
    head = body[:131072]
    v = any(t in head for t in VIDEO_BOX)
    a = any(t in head for t in AUDIO_BOX)
    return v, a


def tracks_of(body):
    """Detecta video/audio de um segmento fMP4 ou MPEG-TS."""
    if len(body) > 188 and body[0] == 0x47 and body[188] == 0x47:
        v, a = ts_track_types(body)
        if v or a:
            return v, a
    return sniff_tracks(body)


# ------------------------------------------------------------------ HLS -----
def parse_master(text, base):
    """Retorna (variantes, audio_renditions) do master playlist."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    variants, audios = [], []
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
                am = re.search(r'AUDIO="([^"]*)"', ln)
                variants.append(
                    {
                        "bw": bw,
                        "url": inherit_query(base, urljoin(base, nxt)),
                        "codecs": [c.lower() for c in (m.group(1).split(",") if m else [])],
                        "audio_group": am.group(1) if am else "",
                    }
                )
        elif ln.startswith("#EXT-X-MEDIA:") and "TYPE=AUDIO" in ln:
            m = re.search(r'URI="([^"]*)"', ln)
            gid = re.search(r'GROUP-ID="([^"]*)"', ln)
            if m:
                audios.append(
                    {
                        "url": inherit_query(base, urljoin(base, m.group(1))),
                        "group": gid.group(1) if gid else "",
                    }
                )
    variants.sort(key=lambda x: x["bw"], reverse=True)
    return variants, audios


def media_uris(text):
    out = []
    for ln in text.splitlines():
        ln = ln.strip()
        if ln.startswith("#EXT-X-MAP:"):
            uri = ln.split("URI=", 1)[1].split(",")[0].strip().strip('"').strip("'")
            if uri:
                out.append(uri)
        elif ln and not ln.startswith("#"):
            out.append(ln)
    return out


def pick_segments(text, base, limit=MAX_SEG):
    """URLs absolutas de segmentos reais (init + midia) do media playlist."""
    segs, lines = [], [ln.strip() for ln in text.splitlines() if ln.strip()]
    for ln in lines:
        if ln.startswith("#EXT-X-MAP:"):
            uri = ln.split("URI=", 1)[1].split(",")[0].strip().strip('"').strip("'")
            if uri:
                segs.append(inherit_query(base, urljoin(base, uri)))
    for i, ln in enumerate(lines):
        if not ln.startswith("#") and i and lines[i - 1].startswith("#EXTINF"):
            segs.append(inherit_query(base, urljoin(base, ln)))
        if len(segs) >= limit:
            break
    return segs[:limit]


def fetch_segment(url):
    """Baixa um segmento e devolve (ok, corpo, motivo)."""
    try:
        r = requests.get(
            url, headers={**HEADERS, "Range": "bytes=0-262143"}, timeout=TIMEOUT
        )
    except requests.exceptions.RequestException as e:
        return False, b"", f"erro={type(e).__name__}"
    if r.status_code not in (200, 206):
        return False, b"", f"http={r.status_code}"
    body = r.content
    if not body:
        return False, b"", "vazio"
    head = body[:300].decode("utf-8", "ignore").upper()
    if "<HTML" in head or "ACCESS DENIED" in head or "<!DOCTYPE" in head:
        return False, b"", "html_erro"
    if len(body) < 512:
        return False, b"", "pequeno"
    if b"ftyp" not in body[:32] and not (body[0] == 0x47 and len(body) > 188):
        return False, b"", "nao_e_midia"
    return True, body, "ok"


def probe_segments(segs):
    """Baixa segmentos em paralelo. Retorna (n_ok, total, corpo, motivos)."""
    if not segs:
        return 0, 0, b"", ["sem_segmentos"]
    bodies, reasons = [], []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_SEG) as ex:
        for ok, body, why in ex.map(fetch_segment, segs):
            reasons.append(why)
            if ok:
                bodies.append(body)
    return len(bodies), len(segs), (bodies[0] if bodies else b""), reasons


def classify(variant_codecs, body, name_hint=""):
    """Define (tem_video, tem_audio) combinando CODECS do master e bytes."""
    cov = any(c.startswith(("avc1", "avc3", "hvc1", "hev1", "av01", "vp09", "vp9")) for c in variant_codecs)
    cau = any(c.startswith(("mp4a", "ac-3", "ec-3", "ac3", "ec3", "opus")) for c in variant_codecs)
    bv, ba = tracks_of(body) if body else (False, False)
    hint = name_hint.lower()
    if not bv and not ba:
        # sem deteccao nos bytes: confia no CODECS do master
        if "audio" in hint or ".mp4a" in hint or "aac" in hint:
            ba = True
        if "video" in hint or "_av" in hint:
            bv = True
    video = bv or (cov and not ba and not bv)
    audio = ba or cau
    return video, audio


def validate_audio_rendition(url):
    try:
        r = fetch(url)
        if r.status_code >= 400:
            return False, f"audio_http={r.status_code}"
        if not is_hls_playlist(r.text):
            return False, "audio_nao_e_playlist"
        nok, total, _b, _r = probe_segments(pick_segments(r.text, r.url, limit=2))
        if not nok:
            return False, "audio_segmentos_falharam"
        return True, f"audio_segmentos {nok}/{total} ok"
    except requests.exceptions.RequestException as e:
        return False, f"audio_erro={type(e).__name__}"


def test_url(url):
    """Testa uma URL. Retorna dict {ok, kind, reason, score}."""
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
            text = r.text
            if not is_hls_playlist(text):
                last = f"nao_e_playlist http={r.status_code}"
                time.sleep(1.5 * attempt)
                continue

            if "#EXT-X-STREAM-INF" in text:
                if encrypted_keys(text):
                    last = "protegido_drm"
                    time.sleep(1.5 * attempt)
                    continue
                variants, audios = parse_master(text, r.url)
                if not variants:
                    last = "master sem variantes"
                    time.sleep(1.5 * attempt)
                    continue
                fails = []
                for v in variants[:6]:
                    try:
                        pr = fetch(v["url"])
                    except requests.exceptions.RequestException as e:
                        fails.append(f"{v['bw'] // 1000}kbps:erro={type(e).__name__}")
                        continue
                    if pr.status_code != 200 or not is_hls_playlist(pr.text):
                        fails.append(f"{v['bw'] // 1000}kbps:http={pr.status_code}")
                        continue
                    if encrypted_keys(pr.text):
                        fails.append(f"{v['bw'] // 1000}kbps:DRM")
                        continue
                    segs = pick_segments(pr.text, pr.url)
                    nok, total, body, why = probe_segments(segs)
                    if not nok:
                        fails.append(f"{v['bw'] // 1000}kbps:segmentos({why[0]})")
                        continue
                    video, audio = classify(v["codecs"], body, segs[0].rsplit("/", 1)[-1])
                    if video and audio:
                        return {
                            "ok": True,
                            "kind": "video+audio",
                            "reason": f"master->variante {v['bw'] // 1000}kbps | segmentos {nok}/{total} ok | video+audio",
                            "score": 1000 + v["bw"],
                        }
                    if not video and audio:
                        fails.append(f"{v['bw'] // 1000}kbps:sem video")
                        continue
                    aud = [a for a in audios if v["audio_group"] and a["group"] == v["audio_group"]]
                    aok, awhy = (False, "sem_rendition_audio")
                    for a in aud[:2]:
                        aok, awhy = validate_audio_rendition(a["url"])
                        if aok:
                            break
                    if aok:
                        return {
                            "ok": True,
                            "kind": "video+audio",
                            "reason": f"master->variante {v['bw'] // 1000}kbps | segmentos {nok}/{total} ok | video | {awhy}",
                            "score": 900 + v["bw"],
                        }
                    fails.append(f"{v['bw'] // 1000}kbps:audio separado quebrado ({awhy})")
                last = "master->variantes rejeitadas [" + "; ".join(fails[:3]) + "]"
                time.sleep(1.5 * attempt)
                continue

            if encrypted_keys(text):
                last = "protegido_drm"
                time.sleep(1.5 * attempt)
                continue
            segs = pick_segments(text, r.url)
            nok, total, body, why = probe_segments(segs)
            if not nok:
                last = f"segmentos_falharam({why[0]})"
                time.sleep(1.5 * attempt)
                continue
            video, audio = classify([], body, segs[0].rsplit("/", 1)[-1] if segs else "")
            if video and audio:
                return {
                    "ok": True,
                    "kind": "video+audio",
                    "reason": f"playlist direta | segmentos {nok}/{total} ok | video+audio",
                    "score": 500,
                }
            if video and not audio:
                last = f"playlist direta | segmentos {nok}/{total} ok | sem audio"
            elif audio and not video:
                last = f"playlist direta | segmentos {nok}/{total} ok | so audio"
            else:
                last = f"playlist direta | segmentos {nok}/{total} ok | midia nao identificada"
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
    return {"ok": False, "kind": "-", "reason": last or "desconhecido", "score": -1}


# ------------------------------------------------------------- metadados ---
def name_of(extinf):
    return extinf.split(",", 1)[1].strip() if "," in extinf else extinf.strip()


def group_key(extinf):
    """Agrupa entradas do mesmo canal."""
    m = re.search(r'tvg-id="([^"]+)"', extinf)
    if m and m.group(1):
        return "id:" + m.group(1)
    t = name_of(extinf).split("|")[0].lower()
    t = re.sub(r"[^a-z0-9]+", " ", t).strip()
    return "t:" + t


def epg_ids():
    """Ids existentes no EPG local/publicado."""
    ids = set()
    try:
        if os.path.exists(EPG_LOCAL):
            data = gzip.decompress(open(EPG_LOCAL, "rb").read()).decode("utf-8", "ignore")
        else:
            r = requests.get(EPG_URL, timeout=60)
            data = gzip.decompress(r.content).decode("utf-8", "ignore")
        ids = set(re.findall(r'<channel id="([^"]+)"', data))
    except Exception as e:  # noqa: BLE001
        print(f"Aviso: EPG indisponivel ({type(e).__name__}); tvg-id sera mantido do original.")
    return ids


def pick_epg_id(extinf, valid_ids):
    if re.search(r'tvg-id="[^"]+"', extinf):
        m = re.search(r'tvg-id="([^"]+)"', extinf)
        if m.group(1) in valid_ids:
            return m.group(1)
        return None
    t = name_of(extinf).lower()
    for key, eid in EPG_MAP:
        if key in t and eid in valid_ids:
            return eid
    return None


def set_epg_id(extinf, eid):
    if eid is None:
        return re.sub(r'\s*tvg-id="[^"]*"', "", extinf)
    if re.search(r'tvg-id="[^"]*"', extinf):
        return re.sub(r'tvg-id="[^"]*"', f'tvg-id="{eid}"', extinf)
    # insere logo apos #EXTINF:-1
    return re.sub(r"^(#EXTINF:-1)(\s)", rf'\1 tvg-id="{eid}"\2', extinf)


# ------------------------------------------------------------------ main ---
def main():
    if not os.path.exists(INPUT):
        print(f"ERRO: {INPUT} nao encontrado")
        return 1

    backup = f"{INPUT}.bak.pre_teste_{STAMP}"
    shutil.copy2(INPUT, backup)
    print(f"Backup: {backup}")

    entries = parse_m3u(INPUT)
    urls, seen = [], set()
    for e in entries:
        for u in e["urls"]:
            if u not in seen:
                seen.add(u)
                urls.append(u)
    print(f"Entradas: {len(entries)} | URLs unicas: {len(urls)}")
    print(f"Testando com {WORKERS} workers, {RETRIES} tentativas por URL\n", flush=True)

    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(test_url, u): u for u in urls}
        for i, fut in enumerate(concurrent.futures.as_completed(futs), 1):
            res = fut.result()
            results[futs[fut]] = res
            flag = "OK  " if res["ok"] else "FALHA"
            print(f"[{i}/{len(urls)}] {flag} {res['reason'][:110]}", flush=True)

    valid_ids = epg_ids()
    groups = {}
    for e in entries:
        groups.setdefault(group_key(e["extinf"]), []).append(e)

    kept, removed, redundant = [], [], []
    for key, items in groups.items():
        cands = []
        for e in items:
            for u in e["urls"]:
                r = results.get(u)
                if r and r["ok"]:
                    cands.append((r["score"], e, u, r))
        if not cands:
            removed.append((items[0], "sem URL funcional"))
            continue
        cands.sort(key=lambda x: -x[0])
        best_score, best_e, best_u, best_r = cands[0]
        kept.append((best_e, best_u, best_r))
        for sc, e, u, r in cands[1:]:
            redundant.append((e, u, r))
        for e in items:
            if e is best_e:
                continue
            bad = [u for u in e["urls"] if not (results.get(u) or {}).get("ok")]
            if bad:
                removed.append((e, bad[0]))

    if kept:
        tmp = OUTPUT + ".new"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(f'#EXTM3U x-tvg-url="{EPG_URL}"\n')
            for e, u, r in kept:
                extinf = set_epg_id(e["extinf"], pick_epg_id(e["extinf"], valid_ids))
                f.write(extinf + "\n")
                f.write(u + "\n")
        shutil.move(tmp, OUTPUT)
    else:
        print("\nAVISO: nenhum canal funcional; lista mantida intacta.")
        removed = []
        redundant = []

    ok_urls = sum(1 for v in results.values() if v["ok"])
    print("")
    print(f"URLs funcionais  : {ok_urls}/{len(urls)}")
    print(f"Canais mantidos   : {len(kept)}")
    print(f"Canais removidos  : {len(removed)}")
    print(f"URLs redundantes  : {len(redundant)}")
    for e, u, r in kept:
        print(f"  + MANTIDO: {name_of(e['extinf'])}")
        print(f"      {r['reason']}")
    for e, why in removed:
        print(f"  - REMOVIDO: {name_of(e['extinf'])}")
        print(f"      {why}")
    print(f"Lista sobrescrita: {OUTPUT}")

    lines = [
        "RELATORIO DE TESTE DE STREAM - lista5.m3u",
        f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Backup: {backup}",
        f"Entradas testadas: {len(entries)} | URLs unicas: {len(urls)} | URLs funcionais: {ok_urls}",
        f"Canais mantidos: {len(kept)} | Canais removidos: {len(removed)} | URLs redundantes: {len(redundant)}",
        "Metodo: manifest -> master -> melhor variante -> segmento real (bytes de midia)",
        "Midia: fMP4 (sniff avc1/mp4a) e MPEG-TS (PAT/PMT -> stream_type)",
        "Audio: muxado, ou rendition EXT-X-MEDIA TYPE=AUDIO validado",
        "DRM (EXT-X-KEY) reprovado: nao toca em player comum",
        "",
        "=== CANAIS MANTIDOS ===",
    ]
    for e, u, r in kept:
        lines.append(f"[OK] {name_of(e['extinf'])}")
        lines.append(f"     {r['reason']}")
        lines.append(f"     {u}")
    lines.append("")
    lines.append("=== CANAIS REMOVIDOS (nenhuma URL funcional) ===")
    if removed:
        for e, why in removed:
            lines.append(f"[FALHA] {name_of(e['extinf'])}")
            for u in e["urls"]:
                lines.append(f"     {results.get(u, {}).get('reason', 'nao testado')} | {u}")
    else:
        lines.append("(nenhum)")
    lines.append("")
    lines.append("=== URLs REDUNDANTES (funcionais, mas nao escolhidas) ===")
    if redundant:
        for e, u, r in redundant:
            lines.append(f"[DESCARTADA] {name_of(e['extinf'])}")
            lines.append(f"     {r['reason']}")
            lines.append(f"     {u}")
    else:
        lines.append("(nenhuma)")
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    with open(JSON_OUT, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"Relatorio: {REPORT}")
    print(f"JSON: {JSON_OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
