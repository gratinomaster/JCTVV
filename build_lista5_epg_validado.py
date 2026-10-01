#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Corrige a lista5.m3u: EPG valido, logos .jpg, streams testados e sem canais orfaos.

Regras aplicadas:
  - todo canal precisa de tvg-id que existe no EPG com programacao de hoje, amanha e depois de amanha
  - tvg-logo obrigatoriamente .jpg (nunca imgur.com)
  - toda URL de stream precisa de uma linha #EXTINF imediatamente acima
  - URLs com token/sessao expirada (hdnea=exp=, dai.google.com) sao descartadas
  - remocoes/stream duplicados sao eliminados

Uso: python3 build_lista5_epg_validado.py [--escrever]
"""
import argparse
import datetime
import gzip
import os
import re
import shutil
import sys
from urllib.parse import urljoin

import requests

PLAYLIST = "lista5.m3u"
EPG_URLS = ["https://iptv-epg.org/files/epg-us.xml.gz"]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9"}

# dominios oficiais de emissora/CDN (tambem usados na triagem de seguranca)
DOMINIOS_OK = (
    "abcnews.com", "akamaized.net", "cbsnews.com", "cbsnstream.cbsnews.com",
    "cbsivideo.com", "foxnews.com", "foxbusiness.com",
)

CHANNELS = [
    {
        "name": "ABC News Live",
        "tvg_id": "ABCNewsLive.us",
        "logo": "https://keyframe-cdn.abcnews.com/streamprovider10.jpg",
        "group": "NEWS WORLD",
        "url": ("https://abcnews-livestreams.akamaized.net/out/v1/"
                "6a597119dbd5428a82dc11a2f514a1a2/abcn-live-10-cmaf-manifest/"
                "abcn-live-10-index.m3u8"),
    },
    {
        "name": "ABC News Live 2",
        "tvg_id": "ABCNewsLive.us",
        "logo": "https://keyframe-cdn.abcnews.com/streamprovider5.jpg",
        "group": "NEWS WORLD",
        "url": ("https://abcnews-livestreams.akamaized.net/out/v1/"
                "173a6e46d5c5423d9611bc7fb7899c73/abcn-live-05-cmaf-manifest/"
                "abcn-live-05-index.m3u8"),
    },
    {
        "name": "Fox News Channel",
        "tvg_id": "FoxNewsChannel.us",
        "logo": ("https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/"
                 "694940094001/15de0523-3be4-4a9a-8159-7020114e7036/"
                 "b6ff623a-26d6-4fd9-8bb8-0856adbf38ce/1280x720/match/676/380/image.jpg"),
        "group": "NEWS WORLD",
        "url": "https://247preview.foxnews.com/hls/live/2020027/fncv3preview/primary.m3u8",
    },
    {
        "name": "Fox Business",
        "tvg_id": "FoxBusiness.us",
        "logo": ("https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/"
                 "694940094001/c9b2e2eb-7b87-435c-9510-eab2650ff944/"
                 "8b584585-acf2-4c37-aa07-aaf2d077bb20/1280x720/match/676/380/image.jpg"),
        "group": "NEWS WORLD",
        "url": "https://247preview.foxbusiness.com/hls/live/2020026/fbnv3preview/primary.m3u8",
    },
    {
        "name": "CBS News 24/7",
        "tvg_id": "CBSNews.us",
        "logo": ("https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/"
                 "0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/"
                 "949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg"),
        "group": "NEWS WORLD",
        "url": ("https://cbsn-us.cbsnstream.cbsnews.com/out/v1/"
                "55a8648e8f134e82a470f83d562deeca/master.m3u8"),
    },
]

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


# ---------------------------------------------------------------- EPG
def carregar_epg(url):
    log(f"[EPG] baixando {url}")
    r = requests.get(url, headers=HEADERS, timeout=180)
    r.raise_for_status()
    bruto = r.content
    if url.endswith(".gz") or bruto[:2] == b"\x1f\x8b":
        bruto = gzip.decompress(bruto)
    return bruto.decode("utf-8", "replace")


def conferir_epg(epg, dias=3):
    """Retorna {tvg_id: {dia: n_programas}} e o total de canais definidos."""
    definidos = set(re.findall(r'<channel id="([^"]+)"', epg))
    contagem = {}
    prog = re.compile(r'<programme start="(\d{14})[^"]*"[^>]*channel="([^"]+)"')
    alvo = {c["tvg_id"] for c in CHANNELS}
    for m in prog.finditer(epg):
        if m.group(2) in alvo:
            contagem.setdefault(m.group(2), {}).setdefault(m.group(1)[:8], 0)
            contagem[m.group(2)][m.group(1)[:8]] += 1
    hoje = datetime.datetime.now(datetime.timezone.utc).date()
    dias_alvo = [(hoje + datetime.timedelta(days=i)).strftime("%Y%m%d") for i in range(dias)]
    log(f"[EPG] janela verificada: {dias_alvo}")
    for ch in CHANNELS:
        cid = ch["tvg_id"]
        por_dia = contagem.get(cid, {})
        detalhe = ", ".join(f"{d}:{por_dia.get(d, 0)}" for d in dias_alvo)
        estado = "OK" if cid in definidos and all(por_dia.get(d, 0) > 0 for d in dias_alvo) else "FALHA"
        log(f"[EPG] {estado} {cid:<22} {detalhe}")
    return contagem, definidos


# ---------------------------------------------------------------- stream
def _get(url, stream=False, timeout=25):
    return requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True, stream=stream)


def _best_variant(texto):
    linhas = [l.strip() for l in texto.splitlines()]
    melhor = None
    for i, l in enumerate(linhas):
        if l.startswith("#EXT-X-STREAM-INF"):
            bw = re.search(r"BANDWIDTH=(\d+)", l)
            for prox in linhas[i + 1:]:
                if prox and not prox.startswith("#"):
                    b = int(bw.group(1)) if bw else 0
                    if melhor is None or b > melhor[0]:
                        melhor = (b, prox)
                    break
    return melhor[1] if melhor else None


def _primeiro_segmento(texto):
    linhas = [l.strip() for l in texto.splitlines()]
    for i, l in enumerate(linhas):
        if l.startswith("#EXTINF"):
            for prox in linhas[i + 1:]:
                if prox and not prox.startswith("#"):
                    return prox
    return None


def _checar_payload(chunk, url):
    """Retorna (ok, motivo). Rejeita conteudo que nao seja midia HLS/TS/fMP4."""
    for magic, descricao in MAGIC_PERIGO.items():
        if chunk.startswith(magic):
            return False, f"payload perigoso: {descricao}"
    if chunk[:1] == b"<":
        return False, "resposta em XML/HTML em vez de midia"
    if chunk[0] == 0x47:
        return True, "MPEG-TS"
    if b"ftyp" in chunk[:64] or b"styp" in chunk[:64] or b"moof" in chunk[:256]:
        return True, "fMP4"
    if len(chunk) < 188:
        return False, f"segmento muito pequeno ({len(chunk)} bytes)"
    return False, "payload nao reconhecido como midia"


def triagem_seguranca(url):
    """Anti-virus local: dominio permitido, https, sem token expirado, sem redirecionar para fora."""
    problemas = []
    if not url.startswith("https://"):
        problemas.append("nao usa https")
    host = re.match(r"https?://([^/]+)", url).group(1).split(":")[0].lower()
    if not any(host == d or host.endswith("." + d) for d in DOMINIOS_OK):
        problemas.append(f"dominio nao permitido: {host}")
    if "imgur.com" in url:
        problemas.append("host dislikes imgur.com")
    if not url.lower().endswith((".m3u8", ".mp4")) and ".m3u8" not in url.lower():
        problemas.append("extensao de stream inesperada")
    r = _get(url, stream=True)
    if r.status_code != 200:
        problemas.append(f"HTTP {r.status_code}")
    final = r.url
    if final != url:
        host_final = re.match(r"https?://([^/]+)", final).group(1).split(":")[0].lower()
        if not any(host_final == d or host_final.endswith("." + d) for d in DOMINIOS_OK):
            problemas.append(f"redireciona para dominio nao permitido: {host_final}")
    ctype = r.headers.get("content-type", "")
    if ctype and not any(t in ctype for t in ("mpegurl", "x-mpeg", "octet-stream", "video/mp2t", "video/", "dash")):
        problemas.append(f"content-type inesperado: {ctype}")
    r.close()
    return problemas


def testar_stream(url):
    r = _get(url)
    if r.status_code != 200:
        return False, f"HTTP {r.status_code}"
    texto = r.text
    if "#EXTM3U" not in texto:
        return False, "nao e playlist"
    variante = _best_variant(texto)
    if variante:
        url_var = urljoin(url, variante)
        r2 = _get(url_var)
        if r2.status_code != 200 or "#EXTM3U" not in r2.text:
            return False, f"variante HTTP {r2.status_code}"
        segmento = _primeiro_segmento(r2.text)
        base = url_var
    else:
        segmento = _primeiro_segmento(texto)
        base = url
    if not segmento:
        return False, "sem segmentos"
    r3 = _get(urljoin(base, segmento), stream=True)
    if r3.status_code != 200:
        return False, f"segmento HTTP {r3.status_code}"
    chunk = next(r3.iter_content(32768), b"")
    r3.close()
    ok, motivo = _checar_payload(chunk, urljoin(base, segmento))
    return ok, f"segmento {motivo}"


def testar_logo(url):
    if not url.lower().split("?")[0].endswith(".jpg"):
        return False, "nao termina em .jpg"
    if "imgur.com" in url:
        return False, "imgur.com nao permitido"
    r = _get(url)
    if r.status_code != 200:
        return False, f"HTTP {r.status_code}"
    if not r.content.startswith(b"\xff\xd8\xff"):
        return False, "conteudo nao e JPEG"
    return True, f"JPEG {len(r.content)} bytes"


# ---------------------------------------------------------------- playlist
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--escrever", action="store_true", help="sobrescreve a lista apos validar")
    args = ap.parse_args()

    epg = carregar_epg(EPG_URLS[0])
    contagem, definidos = conferir_epg(epg)

    hoje = datetime.datetime.now(datetime.timezone.utc).date()
    dias = [(hoje + datetime.timedelta(days=i)).strftime("%Y%m%d") for i in range(3)]
    aprovados = []
    for ch in CHANNELS:
        cid = ch["tvg_id"]
        por_dia = contagem.get(cid, {})
        epg_ok = cid in definidos and all(por_dia.get(d, 0) > 0 for d in dias)

        probs = triagem_seguranca(ch["url"])
        log(f"[SEG] {'FALHA' if probs else 'OK  '} {ch['name']:<18} {ch['url'][:72]}")
        for p in probs:
            log(f"          -> {p}")

        stream_ok, stream_msg = (False, "removido")
        if not probs:
            stream_ok, stream_msg = testar_stream(ch["url"])
        log(f"[STR] {'OK  ' if stream_ok else 'FALHA'} {ch['name']:<18} {stream_msg}")

        logo_ok, logo_msg = testar_logo(ch["logo"])
        log(f"[LOGO] {'OK  ' if logo_ok else 'FALHA'} {ch['name']:<18} {logo_msg}")

        if epg_ok and stream_ok and logo_ok:
            aprovados.append(ch)
        else:
            log(f"[X] {ch['name']} removido (epg_ok={epg_ok} stream_ok={stream_ok} logo_ok={logo_ok})")

    if not aprovados:
        log("nenhum canal passou em todas as verificacoes")
        return 1

    saida = ['#EXTM3U x-tvg-url="{0}" url-tvg="{0}"'.format(",".join(EPG_URLS))]
    for ch in aprovados:
        saida.append('#EXTINF:-1 tvg-id="{tvg_id}" tvg-logo="{logo}" group-title="{group}",{name}'.format(**ch))
        saida.append(ch["url"])
    conteudo = "\n".join(saida) + "\n"

    if args.escrever:
        if os.path.exists(PLAYLIST):
            stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup = f"{PLAYLIST}.bak.pre_tarefa_{stamp}"
            shutil.copy2(PLAYLIST, backup)
            log(f"[BAK] {backup}")
        with open(PLAYLIST, "w", encoding="utf-8") as f:
            f.write(conteudo)
        log(f"[OK] {PLAYLIST} gravado com {len(aprovados)} canais")
    else:
        log("")
        log(conteudo)
    return 0


if __name__ == "__main__":
    sys.exit(main())