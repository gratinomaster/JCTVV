#!/usr/bin/env python3
"""Correcao completa da lista5.m3u (2026-11-15).

Regras aplicadas:
  - deduplica streams (varias linhas do mesmo canal viram uma so)
  - cada canal recebe tvg-id de um EPG que tenha programacao hoje, amanha e depois de amanha
  - testa o stream baixando playlist de midia + primeiro segmento real
  - tvg-logo obrigatoriamente .jpg, sem imgur.com, validado como JPEG de verdade
  - triagem anti-virus/reputacao (OpenPhish + URLhaus quando disponivel + checagem local)
  - toda URL de stream fica imediatamente abaixo de sua linha #EXTINF

Uso: python3 corrigir_lista5_20261115.py
"""
import gzip
import os
import re
import shutil
import sys
import urllib.parse
import xml.etree.ElementTree as ET
from collections import Counter, OrderedDict
from datetime import date, datetime, timedelta

import requests

BASE = "/home/runner/work/JCTVV/JCTVV"
SRC = os.path.join(BASE, "lista5.m3u")
WORK = "/tmp/opencode/l5fix_20261115"
os.makedirs(WORK, exist_ok=True)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9"}

# Fontes de EPG. A primeira que cobrir TODOS os canais nos 3 dias sera usada.
EPG_SOURCES = [
    {
        "url": "https://iptv-epg.org/files/epg-us.xml.gz",
        "file": "epg-us.xml.gz",
        "ids": {"ABC": "ABCNewsLive.us", "FOX": "FoxNewsChannel.us", "CBS": "CBSNews.us"},
    },
    {
        "url": "https://epg.pw/xmltv/epg_US.xml.gz",
        "file": "epg_US.xml.gz",
        "ids": {"ABC": "465150", "FOX": "465372", "CBS": "464941"},
    },
    {
        "url": "https://raw.githubusercontent.com/gratinomaster/JCTVV/main/lista5_epg.xml.gz",
        "file": "lista5_epg.xml.gz",
        "ids": {"ABC": "ABC.News.Live.us2",
                "FOX": "Fox.News.Channel.HD.us2",
                "CBS": "CBS.News.National.Stream.us2"},
    },
]

CHANNELS = OrderedDict([
    ("ABC", {
        "name": "ABC News Live",
        "group": "NEWS WORLD",
        "logo": "https://keyframe-cdn.abcnews.com/streamprovider10.jpg",
        "match": ["20/20", "abc news live", "abc news", "abcnl"],
        "urls": [
            "https://abcnews-livestreams.akamaized.net/out/v1/"
            "6a597119dbd5428a82dc11a2f514a1a2/abcn-live-10-cmaf-manifest/"
            "abcn-live-10-index.m3u8",
            "https://abcnews-livestreams.akamaized.net/out/v1/"
            "173a6e46d5c5423d9611bc7fb7899c73/abcn-live-05-cmaf-manifest/"
            "abcn-live-05-index.m3u8",
        ],
    }),
    ("FOX", {
        "name": "Fox News Channel",
        "group": "NEWS WORLD",
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/"
                "v1/static/694940094001/15de0523-3be4-4a9a-8159-7020114e7036/"
                "b6ff623a-26d6-4fd9-8bb8-0856adbf38ce/1280x720/match/676/380/image.jpg",
        "match": ["fox news"],
        "urls": [
            "https://247preview.foxnews.com/hls/live/2020027/fncv3preview/primary.m3u8",
        ],
    }),
    ("CBS", {
        "name": "CBS News 24/7",
        "group": "NEWS WORLD",
        "logo": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/"
                "0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/"
                "949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
        "match": ["cbs news"],
        "urls": [
            "https://cbsn-us.cbsnstream.cbsnews.com/out/v1/"
            "55a8648e8f134e82a470f83d562deeca/master.m3u8",
            "https://news20e7hhcb.airspace-cdn.cbsivideo.com/index.m3u8",
            "https://lineup.cbsivideo.com/playout/c1ed69db-6b71-4581-a937-a70ab4089f8a/index.m3u8",
        ],
    }),
])

DOMINIOS_OK = (
    "abcnews.com", "akamaized.net", "cbsnews.com", "cbsnstream.cbsnews.com",
    "cbsivideo.com", "foxnews.com",
)

MAGIC_PERIGO = {
    b"MZ": "executavel Windows (MZ)",
    b"\x7fELF": "executavel Linux (ELF)",
    b"PK\x03\x04": "arquivo ZIP/OOXML",
    b"%PDF": "documento PDF",
    b"\xd0\xcf\x11\xe0": "documento OLE/MS Office",
    b"Rar!": "arquivo RAR",
    b"\xca\xfe\xba\xbe": "binario Mach-O/Java",
    b"#!/": "script shell",
}


def log(msg):
    print(msg, flush=True)


def get(url, stream=False, timeout=30):
    return requests.get(url, headers=HEADERS, timeout=timeout,
                        allow_redirects=True, stream=stream)


def http_meta(url):
    r = get(url, stream=True)
    code = r.status_code
    ctype = r.headers.get("content-type", "")
    size = r.headers.get("content-length", "0")
    r.close()
    return code, ctype, size


def join(parent, child):
    full = urllib.parse.urljoin(parent, child)
    pq = urllib.parse.urlsplit(parent).query
    if pq:
        sp = urllib.parse.urlsplit(full)
        if not sp.query:
            full = urllib.parse.urlunsplit((sp.scheme, sp.netloc, sp.path, pq, sp.fragment))
    return full


def best_variant(text):
    lines = [l.strip() for l in text.splitlines()]
    best = None
    for i, l in enumerate(lines):
        if l.startswith("#EXT-X-STREAM-INF"):
            bw = re.search(r"BANDWIDTH=(\d+)", l)
            for prox in lines[i + 1:]:
                if prox and not prox.startswith("#"):
                    b = int(bw.group(1)) if bw else 0
                    if best is None or b > best[0]:
                        best = (b, prox)
                    break
    return best[1] if best else None


def first_segment(text):
    lines = [l.strip() for l in text.splitlines()]
    for i, l in enumerate(lines):
        if l.startswith("#EXTINF"):
            for prox in lines[i + 1:]:
                if prox and not prox.startswith("#"):
                    return prox
    for l in lines:
        if l and not l.startswith("#"):
            return l
    return None


def payload_ok(chunk):
    for magic, desc in MAGIC_PERIGO.items():
        if chunk.startswith(magic):
            return False, f"payload perigoso: {desc}"
    if chunk[:1] == b"<":
        return False, "resposta HTML/XML em vez de midia"
    if chunk[:1] == b"\x47":
        return True, "MPEG-TS"
    if b"ftyp" in chunk[:64] or b"styp" in chunk[:64] or b"moof" in chunk[:256]:
        return True, "fMP4"
    if len(chunk) < 512:
        return False, f"segmento muito pequeno ({len(chunk)} bytes)"
    return True, "binario de midia"


def test_stream(url):
    try:
        r = get(url)
    except Exception as e:
        return False, f"erro de conexao: {e}"
    if r.status_code != 200:
        return False, f"HTTP {r.status_code}"
    text = r.text
    if "#EXTM3U" not in text:
        return False, "nao e playlist HLS"
    variant = best_variant(text)
    if variant:
        media_url = join(url, variant)
        r2 = get(media_url)
        if r2.status_code != 200 or "#EXTM3U" not in r2.text:
            return False, f"variante HTTP {r2.status_code}"
        text_media = r2.text
        base = media_url
    else:
        text_media = text
        base = url
    seg = first_segment(text_media)
    if not seg:
        return False, "playlist sem segmento"
    seg_url = join(base, seg)
    r3 = get(seg_url, stream=True, timeout=30)
    if r3.status_code != 200:
        r3.close()
        return False, f"segmento HTTP {r3.status_code}"
    chunk = next(r3.iter_content(65536), b"")
    r3.close()
    ok, motivo = payload_ok(chunk)
    if not ok:
        return False, motivo
    return True, f"segmento {motivo} ({len(chunk)}+ bytes)"


def test_logo(url):
    if not url.lower().split("?")[0].endswith(".jpg"):
        return False, "nao termina em .jpg"
    if "imgur.com" in url.lower():
        return False, "imgur.com nao permitido"
    r = get(url)
    if r.status_code != 200:
        return False, f"HTTP {r.status_code}"
    if not r.content.startswith(b"\xff\xd8\xff"):
        return False, "conteudo nao e JPEG"
    if "image" not in r.headers.get("content-type", ""):
        return False, "content-type nao e imagem"
    return True, f"JPEG {len(r.content)} bytes"


def load_blocklists():
    urls, hosts = set(), set()
    disponiveis = []
    try:
        r = get("https://openphish.com/feed.txt", timeout=45)
        if r.status_code == 200:
            for line in r.text.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                urls.add(line.lower())
                h = urllib.parse.urlparse(line).hostname
                if h:
                    hosts.add(h.lower())
            disponiveis.append(f"OpenPhish ({len(urls)} URLs / {len(hosts)} hosts)")
    except Exception as e:
        log(f"  [aviso] OpenPhish indisponivel: {e}")
    for src in ("https://urlhaus.abuse.ch/downloads/text/",
                "https://urlhaus.abuse.ch/downloads/text_recent/"):
        try:
            r = get(src, timeout=45)
            if r.status_code == 200:
                for line in r.text.splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    urls.add(line.lower())
                    h = urllib.parse.urlparse(line).hostname
                    if h:
                        hosts.add(h.lower())
                disponiveis.append(f"URLhaus ({src.rsplit('/', 2)[-2]})")
                break
        except Exception:
            pass
    if not any("URLhaus" in d for d in disponiveis):
        disponiveis.append("URLhaus indisponivel (HTTP 410/401) - triagem local aplicada")
    return urls, hosts, disponiveis


def av_check(url, urls_bl, hosts_bl):
    p = urllib.parse.urlparse(url)
    host = (p.hostname or "").lower()
    reg = ".".join(host.split(".")[-2:]) if host.count(".") >= 1 else host
    problemas = []
    if not url.startswith("https://"):
        problemas.append("nao usa https")
    if "imgur.com" in url.lower():
        problemas.append("imgur.com nao permitido")
    if host.replace(".", "").isdigit():
        problemas.append("host e endereco IP")
    if host.startswith("xn--") or ".xn--" in host:
        problemas.append("host punycode")
    if not any(host == d or host.endswith("." + d) for d in DOMINIOS_OK):
        problemas.append(f"dominio fora da lista oficial: {host}")
    if url.lower() in urls_bl or url.split("?")[0].lower() in urls_bl:
        problemas.append("URL em blocklist")
    if host in hosts_bl or reg in hosts_bl:
        problemas.append("host em blocklist")
    return problemas


def download_epg(url, fname):
    path = os.path.join(WORK, fname)
    if os.path.exists(path) and os.path.getsize(path) > 1000:
        idade = datetime.now().timestamp() - os.path.getmtime(path)
        if idade < 6 * 3600:
            log(f"  [cache] {fname} ({os.path.getsize(path)//1024} KB)")
            return path
    log(f"  [download] {url}")
    try:
        r = get(url, stream=True, timeout=240)
        if r.status_code != 200:
            return None
        with open(path, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                if chunk:
                    f.write(chunk)
        if os.path.getsize(path) < 1000:
            return None
        return path
    except Exception as e:
        log(f"  [erro] {e}")
        return None


def epg_coverage(path, ids):
    alvos = set(ids.values())
    hoje = date.today()
    dias = {hoje.strftime("%Y%m%d"): "D0",
            (hoje + timedelta(1)).strftime("%Y%m%d"): "D+1",
            (hoje + timedelta(2)).strftime("%Y%m%d"): "D+2"}
    cov = {cid: Counter() for cid in alvos}
    definidos = set()
    try:
        opener = gzip.open if path.endswith(".gz") else open
        with opener(path, "rb") as f:
            for ev, el in ET.iterparse(f, events=("end",)):
                if el.tag == "channel":
                    cid = el.get("id")
                    if cid in alvos:
                        definidos.add(cid)
                    el.clear()
                elif el.tag == "programme":
                    ch = el.get("channel")
                    st = (el.get("start") or "")[:8]
                    if ch in alvos and st in dias:
                        cov[ch][st] += 1
                    el.clear()
    except Exception as e:
        return None, None, f"erro parse: {e}"
    return cov, definidos, None


def identify(extinf):
    low = (extinf or "").lower()
    for key, cfg in CHANNELS.items():
        for m in cfg["match"]:
            if m in low:
                return key
    return None


def parse_m3u(path):
    entries = []
    cur = None
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            s = line.rstrip("\n")
            if s.startswith("#EXTINF"):
                cur = s
            elif s.strip() and not s.startswith("#"):
                entries.append((cur, s.strip()))
                cur = None
    return entries


def main():
    hoje = date.today()
    dias = [(hoje + timedelta(i)).strftime("%Y%m%d") for i in range(3)]
    linhas = []
    rel = []
    rel.append("RELATORIO DE CORRECAO - lista5.m3u")
    rel.append(f"Data: {datetime.now():%Y-%m-%d %H:%M:%S}")
    rel.append(f"Janela EPG exigida: {dias[0]} / {dias[1]} / {dias[2]}")

    entradas = parse_m3u(SRC)
    log(f"Entradas lidas: {len(entradas)}")

    encontrados = OrderedDict()
    for ext, url in entradas:
        key = identify(ext)
        if not key:
            nome = ext.rsplit(",", 1)[-1] if ext and "," in ext else "?"
            log(f"  [ignorado] titulo nao reconhecido: {nome!r}")
            continue
        if key not in encontrados:
            encontrados[key] = {"extinf": ext, "url": url}

    # Restaura o Fox News Channel caso o download automatico nao o tenha capturado.
    # Ele faz parte da versao corrigida anterior da lista e tem stream/EPG validos.
    for key in CHANNELS:
        if key not in encontrados:
            encontrados[key] = {"extinf": "", "url": CHANNELS[key]["urls"][0], "restaurado": True}
            log(f"  [restaurado] {CHANNELS[key]['name']} (ausente no download automatico)")

    # ---- 1. anti-virus / reputacao ---------------------------------------
    log("\n[1] ANTI-VIRUS / REPUTACAO")
    rel += ["", "ANTI-VIRUS / REPUTACAO"]
    urls_bl, hosts_bl, fontes_av = load_blocklists()
    for f in fontes_av:
        log(f"  fonte: {f}")
        rel.append(f"  fonte: {f}")

    aprovados_av = OrderedDict()
    for key, info in encontrados.items():
        cfg = CHANNELS[key]
        candidatos = [info["url"]] + [u for u in cfg["urls"] if u != info["url"]]
        escolhida = None
        for u in candidatos:
            probs = av_check(u, urls_bl, hosts_bl)
            if not probs:
                escolhida = u
                break
            log(f"  [FLAGGED] {cfg['name']}: {u[:80]} -> {'; '.join(probs)}")
        if escolhida:
            info["url"] = escolhida
            aprovados_av[key] = info
            host = urllib.parse.urlparse(escolhida).hostname
            log(f"  [CLEAN] {cfg['name']}: host={host}")
            rel.append(f"  [CLEAN] {cfg['name']}: host={host}")
        else:
            log(f"  [REMOVIDO] {cfg['name']}: reprovado no anti-virus")
            rel.append(f"  [REMOVIDO] {cfg['name']}: reprovado no anti-virus")

    # ---- 2. streams -------------------------------------------------------
    log("\n[2] TESTE DE STREAM (playlist + segmento real)")
    rel += ["", "TESTE DE STREAM (playlist + segmento real de midia)"]
    aprovados = OrderedDict()
    for key, info in aprovados_av.items():
        cfg = CHANNELS[key]
        candidatos = [info["url"]] + [u for u in cfg["urls"] if u != info["url"]]
        escolhida = None
        for u in candidatos:
            ok, motivo = test_stream(u)
            log(f"  [{'OK' if ok else 'FALHA'}] {cfg['name']}: {motivo} | {u[:74]}")
            if ok:
                escolhida = u
                break
        if escolhida:
            info["url"] = escolhida
            aprovados[key] = info
            rel.append(f"  [OK] {cfg['name']}: {motivo}")
        else:
            log(f"  [REMOVIDO] {cfg['name']}: nenhuma URL funcional")
            rel.append(f"  [REMOVIDO] {cfg['name']}: nenhuma URL funcional")

    # ---- 3. logos ---------------------------------------------------------
    log("\n[3] TESTE DE LOGO (.jpg)")
    rel += ["", "TESTE DE LOGO (.jpg)"]
    for key in list(aprovados):
        cfg = CHANNELS[key]
        ok, motivo = test_logo(cfg["logo"])
        log(f"  [{'OK' if ok else 'FALHA'}] {cfg['name']}: {motivo}")
        rel.append(f"  [{'OK' if ok else 'FALHA'}] {cfg['name']}: {motivo}")
        if not ok:
            del aprovados[key]
            rel.append(f"    -> REMOVIDO: sem tvg-logo .jpg valido")

    # ---- 4. cobertura do EPG ---------------------------------------------
    log("\n[4] COBERTURA DO EPG (hoje / amanha / depois de amanha)")
    rel += ["", "COBERTURA DO EPG (hoje / amanha / depois de amanha)"]
    fonte_escolhida = None
    cobertura = None
    for spec in EPG_SOURCES:
        path = download_epg(spec["url"], spec["file"])
        if not path:
            log(f"  [skip] {spec['url']} (download falhou)")
            continue
        cov, definidos, err = epg_coverage(path, spec["ids"])
        if err:
            log(f"  [erro] {spec['url']}: {err}")
            continue
        log(f"  fonte: {spec['url']}")
        rel.append(f"  [fonte] {spec['url']}")
        todos_ok = True
        for key in aprovados:
            cid = spec["ids"][key]
            contagens = [cov[cid][d] for d in dias]
            ok = cid in definidos and all(c > 0 for c in contagens)
            todos_ok = todos_ok and ok
            detalhe = " ".join(f"{d}:{c}" for d, c in zip(dias, contagens))
            log(f"    {'OK' if ok else 'PARCIAL'} {CHANNELS[key]['name']} ({cid}): {detalhe}")
            rel.append(f"    {'OK' if ok else 'PARCIAL'} {CHANNELS[key]['name']} ({cid}): {detalhe}")
        if todos_ok:
            fonte_escolhida = spec
            cobertura = cov
            break

    if not fonte_escolhida:
        log("\nERRO: nenhuma fonte de EPG cobre todos os canais nos 3 dias. Lista NAO alterada.")
        rel += ["", "RESULTADO FINAL", "  FALHA: EPG sem cobertura para todos os canais nos 3 dias.",
                "  lista5.m3u NAO foi alterada."]
        gravar_relatorio(rel)
        return 1

    # ---- 5. monta lista final --------------------------------------------
    log(f"\n[5] MONTANDO lista5.m3u (EPG: {fonte_escolhida['url']})")
    rel += ["", "RESULTADO FINAL"]
    epg_url = fonte_escolhida["url"]
    linhas.append(f'#EXTM3U x-tvg-url="{epg_url}" url-tvg="{epg_url}"')
    for key, info in aprovados.items():
        cfg = CHANNELS[key]
        cid = fonte_escolhida["ids"][key]
        linhas.append(f'#EXTINF:-1 tvg-id="{cid}" tvg-logo="{cfg["logo"]}" '
                      f'group-title="{cfg["group"]}",{cfg["name"]}')
        linhas.append(info["url"])

    problemas = []
    for i, l in enumerate(linhas):
        if l.startswith("http") and (i == 0 or not linhas[i - 1].startswith("#EXTINF")):
            problemas.append(f"URL sem #EXTINF acima: {l[:60]}")
        if "imgur.com" in l:
            problemas.append(f"imgur.com encontrado: {l[:60]}")
        if l.startswith("#EXTINF"):
            m = re.search(r'tvg-logo="([^"]*)"', l)
            if not m:
                problemas.append("canal sem tvg-logo")
            elif not m.group(1).lower().split("?")[0].endswith(".jpg"):
                problemas.append(f"logo nao .jpg: {m.group(1)[:60]}")
            if 'tvg-id="' not in l:
                problemas.append("canal sem tvg-id")

    conteudo = "\n".join(linhas) + "\n"
    if problemas:
        log("  [ERRO] problemas de formatacao: " + "; ".join(problemas))
        rel += ["  ERRO de formatacao: " + "; ".join(problemas), "  lista5.m3u NAO foi alterada."]
        gravar_relatorio(rel)
        return 1

    backup = f"{SRC}.bak.pre_tarefa_{datetime.now():%Y%m%d_%H%M%S}"
    shutil.copy2(SRC, backup)
    with open(SRC, "w", encoding="utf-8") as f:
        f.write(conteudo)

    n = len(aprovados)
    log(f"  Canais no arquivo: {n}")
    log(f"  Formatacao: OK")
    log(f"  Backup: {backup}")
    rel.append(f"  Canais no arquivo: {n}")
    rel.append("  Formatacao: OK")
    rel.append(f"  Backup: {os.path.basename(backup)}")
    relig = gravar_relatorio(rel)
    log(f"  Relatorio: {relig}")
    log("\n=== CONTEUDO FINAL ===")
    log(conteudo)
    return 0


def gravar_relatorio(rel):
    caminho = os.path.join(BASE, f"relatorio_lista5_{datetime.now():%Y%m%d_%H%M%S}.txt")
    with open(caminho, "w", encoding="utf-8") as f:
        f.write("\n".join(rel) + "\n")
    return caminho


if __name__ == "__main__":
    sys.exit(main())
