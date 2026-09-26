#!/usr/bin/env python3
"""Corrigir o lista5.m3u: EPG valido e atualizado, logos .jpg, dedup e teste.

Fluxo:
  1. le o lista5.m3u, agrupa entradas duplicadas por canal;
  2. testa cada URL (manifest -> variante -> segmento real, validando bytes
     de TS/fMP4) e mantem a melhor URL viva de cada canal;
  3. baixa cada fonte de EPG em url-tvg, resolve o tvg-id de cada canal pelo
     display-name e confirma programacao para hoje, amanha e depois de amanha;
  4. valida tvg-logo (tem de ser .jpg, responder 200 como imagem e nao ser
     imgur.com), trocando por uma alternativa .jpg quando necessario;
  5. regrava o lista5.m3u com #EXTINF sempre na linha de cima de cada URL.
"""

import gzip
import io
import os
import re
import shutil
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests

PLAYLIST = "lista5.m3u"
BACKUP = "lista5.m3u.bak.pre_corrigir_{}"
REPORT = "relatorio_lista5_{}.txt"

# Fontes de EPG testadas: so entram no m3u as que responderam 200 e cobriram
# os canais. epg.pw usa channel id numerico; epgshare usa id textual.
EPG_SOURCES = [
    "https://epg.pw/xmltv/epg_US.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz",
]

GROUP = "NEWS WORLD"

# Identidade do canal -> palavras-chave de deteccao e nomes preferidos no EPG.
# O tvg-id e resolvido em tempo de execucao pelo display-name do EPG.
CHANNELS = [
    {
        "name": "ABC News Live",
        "match": ["abcnews", "abc news"],
        "epg_names": ["ABC News Live", "ABC News"],
        "logos": [
            "https://s.abcnews.com/images/Live/abc_news_live-abc-ml-250210_1739199021469_hpMain_16x9_608.jpg",
            "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
        ],
    },
    {
        "name": "Fox News",
        "match": ["247.foxnews.com", "fox news"],
        "epg_names": ["Fox News Channel HD", "FOX News", "Fox News Channel"],
        "logos": [
            "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/15de0523-3be4-4a9a-8159-7020114e7036/b6ff623a-26d6-4fd9-8bb8-0856adbf38ce/1280x720/match/676/380/image.jpg?ve=1&tl=1",
        ],
    },
    {
        "name": "Fox Business",
        "match": ["247.foxbusiness.com", "fox business"],
        "epg_names": ["Fox Business HD", "FOX Business", "Fox Business"],
        "logos": [
            "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/c9b2e2eb-7b87-435c-9510-eab2650ff944/8b584585-acf2-4c37-aa07-aaf2d077bb20/1280x720/match/676/380/image.jpg?ve=1&tl=1",
        ],
    },
    {
        "name": "CBS News 24/7",
        "match": ["dai.google.com", "cbsnews.com", "cbs news"],
        "epg_names": ["CBS News National Stream", "CBS News 24/7", "CBS News"],
        "logos": [
            "https://www.cbsnews.com/bundles/cbsnewsvideo/images/cbsn--main-bg.jpg",
        ],
    },
]

TIMEOUT = 20
CONNECT_TIMEOUT = 10
MAX_WORKERS = 6
RETRIES = 3
RETRY_WAIT = 4
MAX_DEPTH = 4
SEG_BYTES = 65536

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36")
HEADERS = {
    "User-Agent": UA,
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
}

SEG_EXT = re.compile(r"\.(ts|m4s|mp4|mp4a|aac|m4a|mp3|m4v|cmfv|cmfa|key)(\?|$)", re.I)
BAD_LOGO_HOSTS = ("imgur.com", "i.imgur.com", "imgur.io")
# Assinatura temporaria (Akamai hdnea, token Disney+, hash de CDN): a URL so
# funciona ate o exp. Qando existe alternativa estavel, ela tem prioridade.
EXPIRING = re.compile(r"hdnea=|[?&]hash=|exp=\d{9,}", re.I)

findings = []


def log(msg):
    print(msg, flush=True)


def note(msg):
    findings.append(msg)
    log("  ! %s" % msg)


# --------------------------------------------------------------------------
# parsing
# --------------------------------------------------------------------------

def attr(line, key):
    m = re.search(r'%s="([^"]*)"' % re.escape(key), line)
    return m.group(1).strip() if m else ""


def display_name(extinf):
    m = re.search(r",([^,]*)$", extinf)
    return m.group(1).strip() if m else ""


def parse_m3u(path):
    """Devolve (header, entradas). Entrada = dict com extinf e url."""
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


# --------------------------------------------------------------------------
# teste de stream (manifest -> variante -> segmento)
# --------------------------------------------------------------------------

def inherit_query(url, base):
    """Reproduz a query herdada do manifest pai (ex.: hdnea=... do Fox)."""
    if "?" in url:
        return url
    query = urlsplit(base).query
    if not query:
        return url
    scheme, netloc, path, _, frag = urlsplit(url)
    return urlunsplit((scheme, netloc, path, query, frag))


def probe(url, session, want_bytes=SEG_BYTES):
    resp = session.get(url, headers=HEADERS, timeout=(CONNECT_TIMEOUT, TIMEOUT),
                       stream=True, allow_redirects=True)
    try:
        data = resp.raw.read(want_bytes, decode_content=True) or b""
    except Exception:
        data = b""
    finally:
        resp.close()
    return resp.status_code, data


def is_error_page(text):
    low = text[:600].lower()
    return "<!doctype html" in low or "<html" in low


def looks_like_media(head):
    """Valida bytes magicos de TS (0x47), fMP4 (ftyp/styp/moof/mdat), ID3 ou AAC."""
    if len(head) < 16:
        return False
    if head[0] == 0x47 and (len(head) <= 188 or head[188] == 0x47):
        return True
    if b"ftyp" in head[:64] or b"styp" in head[:64]:
        return True
    if b"moof" in head[:64] or b"mdat" in head[:64]:
        return True
    if head[:3] == b"ID3":
        return True
    if head[0] == 0xFF and (head[1] & 0xF0) == 0xF0:
        return True
    printable = sum(1 for b in head if 9 <= b <= 13 or 32 <= b < 127)
    return printable / len(head) < 0.85


def token_expiry(url):
    """Segundos ate a expiracao da assinatura da URL (hdnea/exp=), se houver."""
    m = re.search(r"exp=(\d{9,})", url)
    if not m:
        return None
    return int(m.group(1)) - int(time.time())


def check_segment(seg_url, session):
    try:
        status, data = probe(seg_url, session)
    except requests.RequestException:
        return False
    return status == 200 and len(data) >= 1024 and looks_like_media(data)


def fetch_manifest(url, session, depth=0):
    """Valida um manifest. Devolve (ok, motivo, variantes_boas)."""
    if depth > MAX_DEPTH:
        return False, "profundidade maxima de variantes", 0

    try:
        status, data = probe(url, session)
    except requests.RequestException as exc:
        return False, "conexao: %s" % type(exc).__name__, 0

    if status != 200:
        return False, "HTTP %d" % status, 0
    if not data:
        return False, "resposta vazia", 0

    text = data.decode("utf-8", errors="ignore")
    if is_error_page(text):
        return False, "retornou HTML em vez de stream", 0
    if "#EXTM3U" not in text and "#EXT-X-" not in text:
        return False, "conteudo nao e playlist HLS", 0

    refs = [l.strip() for l in text.splitlines() if l.strip() and not l.startswith("#")]
    variants = [l for l in refs if ".m3u8" in l.lower()]
    master = "#EXT-X-STREAM-INF" in text

    if master and variants:
        reasons = []
        for var in variants[:6]:
            var_url = inherit_query(urljoin(url, var), url)
            ok, why, _ = fetch_manifest(var_url, session, depth + 1)
            if ok:
                return True, "variante ok (%d)" % len(variants), len(variants)
            reasons.append(why)
        return False, "; ".join(dict.fromkeys(reasons)), 0

    for seg in (refs or [])[:4]:
        if check_segment(inherit_query(urljoin(url, seg), url), session):
            return True, "segmento ok", 0
    return False, "nenhum segmento respondeu", 0


def test_url(url, session, attempts=RETRIES):
    last = ""
    for i in range(1, attempts + 1):
        ok, why, nvar = fetch_manifest(url, session)
        if ok:
            return ok, why, nvar
        last = why
        if i < attempts:
            time.sleep(RETRY_WAIT)
    return False, last, 0


# --------------------------------------------------------------------------
# EPG
# --------------------------------------------------------------------------

def load_epg(url, session):
    """Baixa uma fonte de EPG. Devolve (dict, days) ou None."""
    try:
        resp = session.get(url, headers=HEADERS, timeout=(CONNECT_TIMEOUT, 180),
                           allow_redirects=True)
    except requests.RequestException as exc:
        note("EPG %s falhou na conexao (%s)" % (url, type(exc).__name__))
        return None
    if resp.status_code != 200 or len(resp.content) < 1024:
        note("EPG %s respondeu HTTP %d" % (url, resp.status_code))
        return None

    raw = resp.content
    if url.endswith(".gz") or raw[:2] == b"\x1f\x8b":
        try:
            raw = gzip.decompress(raw)
        except OSError as exc:
            note("EPG %s nao descompactou (%s)" % (url, exc))
            return None

    today = date.today()
    wanted = {today + timedelta(days=d): 0 for d in (0, 1, 2)}
    names = {}
    ids = set()
    text = raw.decode("utf-8", errors="ignore")

    for block in re.findall(r"<channel\b.*?</channel>", text, re.S):
        mid = re.search(r'<channel id="([^"]+)"', block)
        if not mid:
            continue
        cid = mid.group(1)
        ids.add(cid)
        for name in re.findall(r"<display-name[^>]*>(.*?)</display-name>", block, re.S):
            names.setdefault(cid, name.strip())

    prog = defaultdict(Counter)
    for block in re.findall(r"<programme\b[^>]*>", text):
        mid = re.search(r'channel="([^"]+)"', block)
        mstart = re.search(r'start="(\d{8})', block)
        if not (mid and mstart):
            continue
        day = datetime.strptime(mstart.group(1), "%Y%m%d").date()
        if day in wanted:
            prog[mid.group(1)][day] += 1

    if not prog:
        note("EPG %s nao tem nenhuma programme" % url)
        return None
    return {"url": url, "names": names, "ids": ids, "days": prog}


def resolve_tvg_id(epgs, wanted_names):
    """Procura, em ordem de preferencia, um channel id com bom EPG."""
    for name in wanted_names:
        key = re.sub(r"\s+", " ", name).strip().lower()
        for epg in epgs:
            for cid, disp in epg["names"].items():
                if re.sub(r"\s+", " ", disp).strip().lower() == key:
                    return cid, epg, disp
    # segundo passo: coincidencia parcial (ex.: "Fox News" em "Fox News NOW")
    for name in wanted_names:
        key = name.strip().lower()
        for epg in epgs:
            for cid, disp in epg["names"].items():
                d = disp.strip().lower()
                if key in d or d in key:
                    return cid, epg, disp
    return None, None, None


def epg_coverage(epg, cid):
    days = epg["days"].get(cid, Counter())
    today = date.today()
    return [days.get(today + timedelta(days=d), 0) for d in (0, 1, 2)]


# --------------------------------------------------------------------------
# logos
# --------------------------------------------------------------------------

def check_logo(url, session):
    """Valida logo: precisa ser .jpg, 200 e bytes JPEG de verdade."""
    if not url:
        return "vazio"
    low = url.lower().split("?")[0]
    if any(host in low for host in BAD_LOGO_HOSTS):
        return "host bloqueado (imgur)"
    if not low.endswith((".jpg", ".jpeg")):
        return "extensao nao e .jpg"
    try:
        status, data = probe(url, session, want_bytes=4096)
    except requests.RequestException as exc:
        return "conexao: %s" % type(exc).__name__
    if status != 200:
        return "HTTP %d" % status
    if data[:3] != b"\xff\xd8\xff":
        return "conteudo nao e JPEG"
    return ""


def pick_logo(spec, current, session):
    """Mantem o logo atual se for .jpg valido; senao usa uma alternativa."""
    problema = check_logo(current, session)
    if not problema:
        return current, "mantido"
    for cand in spec["logos"]:
        problema = check_logo(cand, session)
        if not problema:
            return cand, "trocado (original: %s)" % problema
    return "", "sem logo .jpg valido (original: %s)" % problema


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def identify(url, extinf, spec_index):
    """Casa a entrada com um dos canais conhecidos."""
    hay = (url + " " + display_name(extinf) + " " + attr(extinf, "tvg-id")
           + " " + attr(extinf, "tvg-name")).lower()
    best, best_len = None, 0
    for i, spec in enumerate(CHANNELS):
        for key in spec["match"]:
            if key.lower() in hay and len(key) > best_len:
                best, best_len = i, len(key)
    if best is not None:
        return best
    return spec_index if spec_index is not None else 0


def main():
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if not os.path.exists(PLAYLIST):
        log("%s nao encontrado" % PLAYLIST)
        return 1

    header, entries = parse_m3u(PLAYLIST)
    total = len(entries)
    unique_urls = list(dict.fromkeys(e["url"] for e in entries))
    log("Playlist : %s" % PLAYLIST)
    log("Entradas : %d (%d URLs unicas)" % (total, len(unique_urls)))
    log("=" * 74)

    # 1. teste das URLs
    results = {}
    with requests.Session() as session:
        session.max_redirects = 5
        adapter = requests.adapters.HTTPAdapter(pool_connections=MAX_WORKERS * 2,
                                                pool_maxsize=MAX_WORKERS * 2)
        session.mount("https://", adapter)
        session.mount("http://", adapter)

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            futures = {pool.submit(test_url, u, session): u for u in unique_urls}
            done = 0
            for fut in as_completed(futures):
                url = futures[fut]
                try:
                    ok, why, nvar = fut.result()
                except Exception as exc:
                    ok, why, nvar = False, "excecao: %s" % exc, 0
                results[url] = (ok, why, nvar)
                done += 1
                log("[%2d/%2d] %-6s %-46s %s"
                    % (done, len(unique_urls), "OK" if ok else "FALHOU",
                       url.split("/")[2][:46], why))

        # 2. EPG
        log("-" * 74)
        epgs = []
        for src in EPG_SOURCES:
            epg = load_epg(src, session)
            if epg:
                epgs.append(epg)
                log("EPG OK  : %s (%d canais, %d com programme)"
                    % (src, len(epg["ids"]), len(epg["days"])))
        if not epgs:
            note("nenhuma fonte de EPG respondeu; lista sera gravada sem guia")

        # 3. monta a lista final: 1 entrada por canal, melhor URL viva
        kept = []
        seen = set()
        for idx, spec in enumerate(CHANNELS):
            alive = []
            for e in entries:
                if identify(e["url"], e["extinf"], idx) != idx:
                    continue
                if e["url"] in seen:
                    continue
                seen.add(e["url"])
                ok, why, nvar = results.get(e["url"], (False, "nao testado", 0))
                if ok:
                    alive.append((e, why, nvar))
            if not alive:
                log("%-16s SEM URL FUNCIONANDO - canal removido" % spec["name"])
                note("canal sem stream vivo: %s" % spec["name"])
                continue

            # master playlist (com variantes) tem prioridade sobre segmento solto;
            # URL sem token temporario ganha da URL que expira
            alive.sort(key=lambda t: (t[2] > 0, not EXPIRING.search(t[0]["url"]), t[2]),
                       reverse=True)
            chosen, why, nvar = alive[0]
            log("%-16s %-38s %s" % (spec["name"], chosen["url"].split("/")[2][:38], why))

            cid, epg, disp = (None, None, None)
            if epgs:
                cid, epg, disp = resolve_tvg_id(epgs, spec["epg_names"])
            cov = epg_coverage(epg, cid) if epg else [0, 0, 0]
            if epg is None:
                note("%s sem tvg-id (nenhum EPG casou)" % spec["name"])
            elif min(cov) == 0:
                note("%s com EPG incompleto: hoje=%d amanha=%d depois=%d"
                     % (spec["name"], cov[0], cov[1], cov[2]))

            logo, logo_status = pick_logo(spec, attr(chosen["extinf"], "tvg-logo"), session)

            expira = token_expiry(chosen["url"])
            if expira is not None:
                if expira <= 0:
                    note("%s: assinatura da URL ja expirou" % spec["name"])
                elif expira < 6 * 3600:
                    note("%s: URL assinada expira em %d min (hdnea do Akamai nao e "
                         "renovavel por script; a proxima execucao precisa de token novo)"
                         % (spec["name"], max(1, expira // 60)))

            extinf = '#EXTINF:-1 tvg-id="%s" tvg-name="%s" tvg-logo="%s" group-title="%s",%s' % (
                cid or "", spec["name"], logo, GROUP, spec["name"])
            kept.append({
                "spec": spec, "extinf": extinf, "url": chosen["url"],
                "why": why, "variants": nvar,
                "tvg_id": cid, "display": disp, "epg": epg["url"] if epg else "",
                "coverage": cov, "logo": logo, "logo_status": logo_status,
                "expires": expira,
            })

        # 4. grava o m3u
        if not kept:
            log("=" * 74)
            log("Nenhum canal funcionando - lista5.m3u mantido intacto.")
            return 1

        epg_urls = []
        for item in kept:
            for u in dict.fromkeys(i["epg"] for i in kept if i["epg"]):
                if u not in epg_urls:
                    epg_urls.append(u)
        epg_attr = ",".join(epg_urls)

        shutil.copy2(PLAYLIST, BACKUP.format(stamp))
        with open(PLAYLIST, "w", encoding="utf-8") as fh:
            if epg_attr:
                fh.write('#EXTM3U x-tvg-url="%s" url-tvg="%s"\n' % (epg_attr, epg_attr))
            else:
                fh.write("#EXTM3U\n")
            for item in kept:
                fh.write(item["extinf"] + "\n")
                fh.write(item["url"] + "\n")

    alive_entries = [e for e in entries if results.get(e["url"], (False, "", 0))[0]]
    dead_entries = [e for e in entries if not results.get(e["url"], (False, "", 0))[0]]
    log("=" * 74)
    log("Entradas: %d | mortas: %d | duplicadas removidas: %d | canais finais: %d"
        % (total, len(dead_entries), len(alive_entries) - len(kept), len(kept)))
    log("EPG no m3u: %s" % (epg_attr or "nenhuma"))

    with open(REPORT.format(stamp), "w", encoding="utf-8") as fh:
        fh.write("Correcao de %s - %s\n" % (PLAYLIST, stamp))
        fh.write("Entradas antes: %d | Mortas: %d | Duplicadas removidas: %d | "
                 "Canais depois: %d\n\n"
                 % (total, len(dead_entries), len(alive_entries) - len(kept), len(kept)))
        fh.write("FONTES DE EPG NO M3U\n")
        for u in epg_urls:
            fh.write("- %s\n" % u)
        for u in EPG_SOURCES:
            if u not in epg_urls:
                epg = next((e for e in epgs if e["url"] == u), None)
                fh.write("- %s (avaliada e descartada: nao cobre os canais da lista"
                         "%s)\n" % (u, ", %d canais" % len(epg["ids"]) if epg else ", falhou"))
        fh.write("\nCANAIS\n")
        for item in kept:
            fh.write("- %s\n" % item["spec"]["name"])
            fh.write("    url    : %s [%s]\n" % (item["url"], item["why"]))
            fh.write("    tvg-id : %s (%s em %s)\n"
                     % (item["tvg_id"], item["display"], item["epg"] or "sem EPG"))
            fh.write("    guia   : hoje=%d amanha=%d depois=%d\n" % tuple(item["coverage"]))
            fh.write("    logo   : %s (%s)\n" % (item["logo"], item["logo_status"]))
            if item["expires"] is not None:
                fh.write("    expira : em %d min (assinatura na URL)\n"
                         % max(0, item["expires"] // 60))
        fh.write("\nAVISOS (%d)\n" % len(findings))
        for f in findings:
            fh.write("- %s\n" % f)

    log("Backup   : %s" % BACKUP.format(stamp))
    log("Relatorio: %s" % REPORT.format(stamp))
    return 0


if __name__ == "__main__":
    sys.exit(main())
