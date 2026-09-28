#!/usr/bin/env python3
"""
Correcao completa do lista5.m3u (grupo NEWS WORLD).

O que o script faz, nesta ordem:
  1. Le o lista5.m3u e separa cada #EXTINF do link da linha de baixo.
  2. Testa cada link: baixa o .m3u8, classifica (master / media / audio-only /
     VOD), segue ate uma rendition com video e baixa 1 segmento para confirmar
     o container (TS ou fMP4). Link morto, so-audio ou so-VOD e descartado.
  3. Tela anti-virus: usa o VirusTotal quando existe chave (arg/env) e, sem
     chave, roda triagem local (host, redirect, content-type, magic bytes,
     marcadores de malware nos bytes baixados).
  4. Escolhe 1 link por canal/afiliada, preferindo o manifest master.
  5. Aplica tvg-id + nome de canal + tvg-logo .jpg (testa cada logo: HTTP 200,
     content-type image/jpeg, magic FFD8FF; rejeita imgur.com e host bloqueado).
  6. Testa as fontes de EPG: baixa e conta os programas de cada tvg-id para
     hoje, amanha e depois de amanha, e insere a URL da EPG validada em url-tvg.
  7. Grava o lista5.m3u com backup previo e relatorio_txt.

Uso:
  python3 corrigir_lista5_20260928.py            # corrige usando a tabela de canais
  python3 corrigir_lista5_20260928.py VT_API_KEY # inclui consulta ao VirusTotal
  python3 corrigir_lista5_20260928.py --so-auditoria
"""

import argparse
import base64
import os
import re
import shutil
import sys
import zlib
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, urljoin

import requests

ARQUIVO = "lista5.m3u"
DATA = "20260928"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
VT_URL = "https://www.virustotal.com/api/v3/urls"
S = requests.Session()
S.headers.update({"User-Agent": UA, "Accept": "*/*"})

# --------------------------------------------------------------------------
# Fontes de EPG candidatas. O script escolhe a que cobre todos os tvg-id com
# programa nos 3 dias exigidos e usa as demais como reserva.
# --------------------------------------------------------------------------
FONTES_EPG = [
    ("epgshare01 US2", "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz", True),
    ("epgshare01 ALL_SOURCES1", "https://epgshare01.online/epgshare01/epg_ripper_ALL_SOURCES1.xml.gz", True),
    ("epg.pw US", "https://epg.pw/xmltv/epg_US.xml.gz", False),
]

# --------------------------------------------------------------------------
# Canais: tvg-id usado no EPG, logos aceitos (em ordem) e fontes conhecidas.
# --------------------------------------------------------------------------
CANAIS = {
    "ABC News Live": {
        "tvg_id": "ABC.News.Live.us2",
        "grupo": "NEWS WORLD",
        "logos": [
            "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
            "https://keyframe-cdn.abcnews.com/streamprovider10.jpg",
        ],
        "hospedeiros": ("dssott.com", "akamaized.net", "abcnews.com"),
        "observacao": "ABC News 24h (2 afiliadas: Disney+ e Akamai/CDN)",
    },
    "CBS News 24/7": {
        "tvg_id": "CBS.News.National.Stream.us2",
        "grupo": "NEWS WORLD",
        "logos": [
            "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-"
            "86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/"
            "247-key-channelthumbnail-1920x1080.jpg",
        ],
        "hospedeiros": ("dai.google.com",),
        "observacao": "CBS News 24/7 (via Google DAI)",
    },
}

BLOQUEIA_HOST = ("imgur.com", "i.imgur.com", "imgur.io")
BLOQUEIA_EXT = (".exe", ".dll", ".scr", ".apk", ".bat", ".cmd", ".ps1", ".js", ".vbs", ".jar", ".msi")
SUFIXOS_SUSPEITOS = (".tk", ".ml", ".ga", ".cf", ".gq", ".zip", ".mov", ".top", ".xyz", ".click", ".work", ".country")
MARCADORES_MALWARE = (b"<script", b"eval(atob", b"powershell", b"cmd.exe", b"/bin/sh", b"<?php", b"wscript")

relatorio = []


def log(*args):
    linha = " ".join(str(a) for a in args)
    print(linha, flush=True)
    relatorio.append(linha)


def host_de(url):
    return (urlparse(url).hostname or "").lower()


# --------------------------------------------------------------------------
# 1) leitura do M3U
# --------------------------------------------------------------------------
def ler_m3u(caminho):
    entradas, atual = [], None
    for bruto in open(caminho, encoding="utf-8", errors="replace"):
        linha = bruto.strip()
        if not linha:
            continue
        if linha.startswith("#EXTINF"):
            nome = linha.split(",", 1)[1].strip() if "," in linha else "?"
            atual = {"extinf": linha, "nome": nome, "url": None}
            entradas.append(atual)
        elif linha.startswith("#"):
            if atual is not None and "url" not in atual:
                atual["attrs"] = atual.get("attrs", []) + [linha]
        else:
            if atual is None:
                log("  [ORFAO] link sem #EXTINF na linha de cima: " + linha[:90])
                continue
            atual["url"] = linha
            atual = None
    return entradas


def get(url, timeout=25, faixa=400000):
    r = S.get(url, timeout=timeout, stream=True, headers={"Range": f"bytes=0-{faixa}"})
    corpo = r.raw.read(faixa + 1, decode_content=True)
    return r, corpo


# --------------------------------------------------------------------------
# 2) teste de stream
# --------------------------------------------------------------------------
CAIXAS_BMFF = (b"ftyp", b"styp", b"moof", b"moov", b"sidx", b"emsg", b"free", b"skip", b"mdat")
AMOSTRAS_VIDEO = (b"avc1", b"avc3", b"hvc1", b"hev1", b"av01", b"vp09", b"vp9", b"dvh1", b"dvhe")
AMOSTRAS_AUDIO = (b"mp4a", b"ac-3", b"ec-3", b"ac-4", b"Opus", b"sowt", b"fLaC")


def caixas_iniciais(cab, limite=12):
    """Anda pela cadeia de caixas ISO-BMFF e devolve os tipos encontrados."""
    tipos, pos = [], 0
    while pos + 8 <= len(cab) and len(tipos) < limite:
        tamanho = int.from_bytes(cab[pos:pos + 4], "big")
        tipo = cab[pos + 4:pos + 8]
        if not tipo.isalpha() and not all(32 < b < 127 for b in tipo):
            break
        tipos.append(tipo)
        if tamanho == 1:
            pos += 8 + int.from_bytes(cab[pos + 8:pos + 16], "big")
        elif tamanho <= 0:
            break
        else:
            pos += tamanho
    return tipos


def identificar_container(cab):
    """Diz se os bytes iniciais sao midia (MPEG-TS ou ISO-BMFF) e de que tipo."""
    if len(cab) < 8:
        return None
    if cab[:1] == b"\x47":
        ts = sum(1 for i in range(0, min(len(cab), 1880), 188) if cab[i:i + 1] == b"\x47")
        return "MPEG-TS" if ts >= 2 else None
    tipos = caixas_iniciais(cab)
    if any(t in CAIXAS_BMFF for t in tipos):
        return "fMP4/" + "+".join(t.decode("ascii", "replace") for t in tipos[:3])
    return None


def variantes(txt, base):
    saida, linhas = [], txt.splitlines()
    for i, l in enumerate(linhas):
        if not l.startswith("#EXT-X-STREAM-INF"):
            continue
        prox = next((x.strip() for x in linhas[i + 1:] if x.strip() and not x.startswith("#")), None)
        if not prox:
            continue
        bw = re.search(r"BANDWIDTH=(\d+)", l)
        rs = re.search(r"RESOLUTION=(\d+)x(\d+)", l)
        codecs = re.search(r'CODECS="([^"]+)"', l)
        tem_video = bool(codecs) and any(c in codecs.group(1).lower() for c in ("avc", "hvc", "hev", "vp9", "av01"))
        saida.append({"bw": int(bw.group(1)) if bw else 0,
                      "res": f"{rs.group(1)}x{rs.group(2)}" if rs else "sem-resolucao",
                      "altura": int(rs.group(2)) if rs else 0,
                      "url": urljoin(base, prox),
                      "tem_video": tem_video})
    return sorted(saida, key=lambda v: v["bw"])


def testar_link(url, profundidade=0):
    """Retorna dicionario com o veredito do link."""
    r = {"url": url, "ok": False, "motivo": "", "tipo": "", "detalhe": ""}
    try:
        resp, corpo = get(url)
    except Exception as e:
        r["motivo"] = f"ERRO {type(e).__name__}: {str(e)[:70]}"
        return r
    r["http"] = resp.status_code
    r["final"] = resp.url
    r["ct"] = resp.headers.get("content-type", "")

    if resp.status_code >= 400:
        r["motivo"] = f"HTTP {resp.status_code}"
        return r
    if not corpo.lstrip().startswith(b"#EXTM3U"):
        r["motivo"] = "resposta nao-HLS"
        r["detalhe"] = corpo[:16].hex()
        return r

    txt = corpo.decode("utf-8", "replace")
    var = variantes(txt, resp.url)
    r["tipo"] = "master" if var else "media"
    r["n_variantes"] = len(var)
    r["vod"] = ("#EXT-X-ENDLIST" in txt) or ("PLAYLIST-TYPE:VOD" in txt)

    # master sem nenhuma rendition de video = audio-only
    if var and not any(v["tem_video"] for v in var):
        r["motivo"] = "somente audio"
        return r

    if var:
        cand = [v for v in var if v["tem_video"]] or var
        melhor = cand[-1]
        r["res"] = melhor["res"]
        r["altura"] = melhor["altura"]
        r["detalhe"] = f"{len(var)} variantes, melhor {melhor['res']}"
        if profundidade == 0:
            sub = testar_link(melhor["url"], 1)
            r["sub"] = sub
            if not sub["ok"]:
                r["motivo"] = "rendition de video falhou: " + sub["motivo"]
                return r
            if sub.get("vod"):
                r["motivo"] = "VOD gravado (todas as variantes tem ENDLIST)"
                return r
            r["segmento"] = sub.get("segmento")
            r["container"] = sub.get("container")
            r["so_audio"] = sub.get("so_audio")
    else:
        segs = [x.strip() for x in txt.splitlines() if x.strip() and not x.startswith("#")]
        r["n_segmentos"] = len(segs)
        r["detalhe"] = f"{len(segs)} segmentos, endlist={r['vod']}"
        if profundidade == 0 and r["vod"]:
            r["motivo"] = "VOD gravado (nao e canal ao vivo)"
            return r
        if not segs:
            r["motivo"] = "sem segmentos"
            return r
        mapa = re.search(r'#EXT-X-MAP:.*?URI="([^"]+)"', txt)
        r["init"] = urljoin(resp.url, mapa.group(1)) if mapa else None
        r["segmento"] = urljoin(resp.url, segs[0])

    if r.get("segmento"):
        sc = checar_segmento(r["segmento"])
        r["bytes"] = sc.get("bytes")
        r["container"] = sc.get("container")
        if not sc.get("ok"):
            r["motivo"] = "segmento invalido: " + sc.get("motivo", "")
            return r
    if r.get("init"):
        faixas = ler_tracks(r["init"])
        r["tracks"] = faixas
        if faixas == ["audio"]:
            r["so_audio"] = True
            if profundidade == 0:
                r["ok"] = False
                r["motivo"] = "somente audio (init segment so tem faixa de audio)"
                return r
    r["ok"] = True
    r["motivo"] = "OK"
    return r


def ler_tracks(url_init):
    """Le o init segment e diz quais faixas ele declara."""
    try:
        resp, corpo = get(url_init, timeout=25, faixa=120000)
    except Exception:
        return []
    if resp.status_code >= 400 or not identificar_container(corpo[:8192]):
        return []
    faixas = [("video", any(a in corpo for a in AMOSTRAS_VIDEO)),
              ("audio", any(a in corpo for a in AMOSTRAS_AUDIO))]
    return [n for n, achou in faixas if achou]


def checar_segmento(url):
    out = {"segmento": url, "ok": False}
    try:
        resp, corpo = get(url, timeout=30)
    except Exception as e:
        out["motivo"] = f"ERRO {type(e).__name__}"
        return out
    out["http"] = resp.status_code
    out["ct"] = resp.headers.get("content-type", "")
    out["bytes"] = len(corpo)
    if resp.status_code >= 400:
        out["motivo"] = f"HTTP {resp.status_code}"
        return out
    cab = corpo[:8192]
    container = identificar_container(cab)
    if not container:
        out["container"] = "?"
        out["motivo"] = "container desconhecido " + cab[:12].hex()
        return out
    out["container"] = container
    if container == "MPEG-TS":
        out["sync_ts"] = sum(1 for i in range(0, min(len(corpo), 3760), 188) if corpo[i:i + 1] == b"\x47")
    out["ok"] = len(corpo) > 20000
    out["motivo"] = "OK" if out["ok"] else "segmento pequeno demais"
    return out


# --------------------------------------------------------------------------
# 3) tela anti-virus
# --------------------------------------------------------------------------
def triar_url(url, chave_vt=None, resultado_stream=None):
    """Retorna (veredito, detalhe). 'limpo' | 'suspeito' | 'nao_avaliado'."""
    reasons = []
    h = host_de(url)
    p = urlparse(url)

    if h.endswith(BLOQUEIA_HOST):
        reasons.append("host bloqueado pelo usuario (imgur)")
    if h.endswith(SUFIXOS_SUSPEITOS):
        reasons.append("TLD/sufixo suspeito")
    if h.startswith("xn--") or ".xn--" in h:
        reasons.append("host punycode/IDN")
    if p.username or p.password:
        reasons.append("credencial na URL")
    if p.scheme not in ("http", "https"):
        reasons.append("esquema nao suportado")
    if p.scheme == "http":
        reasons.append("sem TLS")
    if p.port not in (None, 80, 443):
        reasons.append(f"porta nao padrao {p.port}")
    if urlparse(url).path.lower().endswith(BLOQUEIA_EXT):
        reasons.append("extensao de executavel/script")
    if resultado_stream and resultado_stream.get("final"):
        hf = host_de(resultado_stream["final"])
        if hf and hf != h and not (h.endswith(".dssott.com") and hf.endswith(".dssott.com")):
            reasons.append(f"redirect para outro dominio: {hf}")
    if resultado_stream and resultado_stream.get("ct"):
        ct = resultado_stream["ct"].lower()
        if not any(x in ct for x in ("mpegurl", "m3u", "octet-stream", "audio/", "video/")):
            reasons.append(f"content-type inesperado: {resultado_stream['ct'][:40]}")

    if reasons:
        return "suspeito", "; ".join(reasons)

    if chave_vt:
        try:
            ident = base64.urlsafe_b64encode(url.encode()).decode().strip("=")
            resp = S.get(f"{VT_URL}/{ident}", headers={"x-apikey": chave_vt}, timeout=40)
            if resp.status_code == 200:
                st = resp.json()["data"]["attributes"]["last_analysis_stats"]
                maus = st.get("malicious", 0) + st.get("suspicious", 0)
                if maus:
                    return "suspeito", f"VirusTotal: {maus} deteccoes ({st})"
                return "limpo", f"VirusTotal: {st.get('harmless', 0)} benignos, 0 deteccoes"
            if resp.status_code == 429:
                return "nao_avaliado", "VirusTotal: cota excedida"
            if resp.status_code == 404:
                return "limpo", "VirusTotal: URL nao submitted (nenhuma deteccao)"
            return "nao_avaliado", f"VirusTotal HTTP {resp.status_code}"
        except Exception as e:
            return "nao_avaliado", f"VirusTotal falhou: {type(e).__name__}"

    return "limpo", "triagem local ( VirusTotal sem chave )"


def inspecionar_bytes(url, esperado):
    """Confere que o que o servidor entrega e midia, nao codigo executavel."""
    problemas = []
    try:
        resp, corpo = get(url, timeout=25, faixa=200000)
    except Exception as e:
        return [f"erro ao baixar: {type(e).__name__}"]
    if resp.status_code >= 400:
        problemas.append(f"HTTP {resp.status_code}")
    if any(m in corpo[:60000].lower() for m in MARCADORES_MALWARE):
        problemas.append("marcador de codigo malicioso no conteudo")
    if corpo[:2] == b"MZ" or corpo[:4] == b"\x7fELF":
        problemas.append("payload executavel")
    if esperado == "midia" and not identificar_container(corpo[:8192]):
        problemas.append("conteudo nao e midia (nem TS nem ISO-BMFF)")
    return problemas


# --------------------------------------------------------------------------
# 4) logos
# --------------------------------------------------------------------------
def testar_logo(url):
    r = {"url": url, "ok": False}
    h = host_de(url)
    if h.endswith(BLOQUEIA_HOST):
        r["motivo"] = "host bloqueado (imgur)"
        return r
    if not urlparse(url).path.lower().endswith((".jpg", ".jpeg")):
        r["motivo"] = "extensao diferente de .jpg"
        return r
    try:
        resp = S.get(url, timeout=25, stream=True)
        corpo = resp.raw.read(60000, decode_content=True)
    except Exception as e:
        r["motivo"] = f"ERRO {type(e).__name__}"
        return r
    r["http"] = resp.status_code
    r["ct"] = resp.headers.get("content-type", "")
    r["bytes"] = len(corpo)
    if resp.status_code != 200:
        r["motivo"] = f"HTTP {resp.status_code}"
        return r
    if "image/jpeg" not in r["ct"] and "image/jpg" not in r["ct"]:
        r["motivo"] = f"content-type {r['ct'][:30]}"
        return r
    if corpo[:3] != b"\xff\xd8\xff":
        r["motivo"] = "nao e JPEG valido"
        return r
    r["ok"] = True
    r["motivo"] = "JPEG ok"
    return r


# --------------------------------------------------------------------------
# 5) EPG
# --------------------------------------------------------------------------
def dias_alvo():
    hoje = datetime.now(timezone.utc).date()
    return [(hoje + timedelta(days=i)).strftime("%Y%m%d") for i in range(3)]


def verificar_epg(url, tvg_ids, dias, verbose=True, limite_bytes=260 * 1024 * 1024):
    """Baixa a EPG (stream) e conta os programas de cada tvg-id nos dias pedidos."""
    alvo = set(tvg_ids)
    padrao_chan = re.compile(r'<channel id="([^"]+)"')
    padrao_prog = re.compile(r'<programme\s+channel="([^"]+)"\s+start="(\d{8})')
    conta = defaultdict(lambda: defaultdict(int))
    achou_canal = set()
    try:
        resp = S.get(url, timeout=90, stream=True)
    except Exception as e:
        return {"url": url, "ok": False, "motivo": f"ERRO {type(e).__name__}: {str(e)[:60]}", "last_modified": None}
    lm = resp.headers.get("last-modified")
    tamanho = int(resp.headers.get("content-length") or limite_bytes)
    total = tamanho
    if total > limite_bytes:
        if verbose:
            log(f"    (arquivo de {total/1048576:.0f} MB: varredura limitada a {limite_bytes/1048576:.0f} MB)")
        total = limite_bytes
    lido, dec, pendente, texto, camadas = 0, None, b"", b"", 0
    try:
        resp.raw.decode_content = False
        while lido < total:
            bloco = resp.raw.read(1 << 20)
            if not bloco:
                break
            lido += len(bloco)
            if dec is None:
                pendente += bloco
                if len(pendente) < 2:
                    continue
                dec = zlib.decompressobj(16 + zlib.MAX_WBITS if pendente[:2] == b"\x1f\x8b" else zlib.MAX_WBITS)
                camadas += 1
                bloco, pendente = pendente, b""
            elif dec.eof:
                # camada extra de gzip (Content-Encoding do servidor por cima do arquivo .gz)
                dec = zlib.decompressobj(16 + zlib.MAX_WBITS) if bloco[:2] == b"\x1f\x8b" else None
                camadas += 1
                if dec is None:
                    break
            saida = dec.decompress(bloco)
            if not saida:
                continue
            texto += saida
            linhas = texto.split(b"\n")
            texto = linhas.pop()
            for ln in linhas:
                linha = ln.decode("utf-8", "replace")
                m = padrao_chan.search(linha)
                if m and m.group(1) in alvo:
                    achou_canal.add(m.group(1))
                p = padrao_prog.search(linha)
                if p and p.group(1) in alvo and p.group(2) in dias:
                    conta[p.group(1)][p.group(2)] += 1
    except Exception as e:
        if verbose:
            log(f"    (varredura interrompida: {type(e).__name__})")
    if verbose and camadas:
        log(f"    (gzip em {camadas} camada(s), {lido/1048576:.1f} MB lidos de {total/1048576:.1f} MB)")
    ok = all(c in achou_canal and all(conta[c].get(d, 0) > 0 for d in dias) for c in alvo)
    return {"url": url, "ok": ok, "last_modified": lm, "bytes": tamanho, "canais": sorted(achou_canal),
            "programas": {c: {d: conta[c].get(d, 0) for d in dias} for c in sorted(achou_canal)},
            "motivo": "" if ok else "faltou canal ou dia sem programa"}


# --------------------------------------------------------------------------
# fluxo principal
# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("vt_key", nargs="?", default=os.environ.get("VT_API_KEY") or os.environ.get("VIRUSTOTAL_API_KEY"))
    ap.add_argument("--so-auditoria", action="store_true", help="nao grava o m3u")
    ap.add_argument("--sem-epg", action="store_true", help="pula a verificação das EPGs")
    args = ap.parse_args()

    log(f"Correcao do {ARQUIVO} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (UTC)")
    log(f"chave VirusTotal: {'informada' if args.vt_key else 'ausente -> triagem local'}")
    log("")

    # ---- auditoria do original
    log("=" * 72)
    log("1) AUDITORIA DO ARQUIVO ORIGINAL")
    log("=" * 72)
    with open(ARQUIVO, encoding="utf-8", errors="replace") as f:
        linhas_brutas = f.read().splitlines()
    entradas = ler_m3u(ARQUIVO)
    urls = [e["url"] for e in entradas if e["url"]]
    sem_extinf = 0
    anterior = ""
    for l in linhas_brutas:
        if l.strip() and not l.strip().startswith("#") and not anterior.upper().startswith("#EXTINF"):
            sem_extinf += 1
        if l.strip():
            anterior = l.strip()
    log(f"  linhas: {len(linhas_brutas)} | #EXTINF: {len(entradas)} | links: {len(urls)} | links unicos: {len(set(urls))}")
    log(f"  duplicados exatos: {len(urls) - len(set(urls))}")
    log(f"  link sem #EXTINF na linha de cima: {sem_extinf}")
    log(f"  entradas sem tvg-id: {sum(1 for e in entradas if 'tvg-id' not in e['extinf'])}")
    log(f"  entradas sem tvg-logo: {sum(1 for e in entradas if 'tvg-logo' not in e['extinf'])}")
    log(f"  logos nao .jpg: {sum(1 for e in entradas if re.search(r'tvg-logo=\"([^\"]+)\"', e['extinf']) and not re.search(r'tvg-logo=\"([^\"]+)\"', e['extinf']).group(1).lower().endswith('.jpg'))}")
    log(f"  logos em imgur: {sum(1 for e in entradas if re.search(r'tvg-logo=\"([^\"]+)\"', e['extinf']) and 'imgur' in re.search(r'tvg-logo=\"([^\"]+)\"', e['extinf']).group(1).lower())}")
    log(f"  header #EXTM3U: {linhas_brutas[0].strip() if linhas_brutas else '(vazio)'}")
    log("")

    # ---- teste de todos os links
    log("=" * 72)
    log("2) TESTE DOS LINKS (playlist + rendition + segmento + anti-virus)")
    log("=" * 72)
    vistos = {}
    for e in entradas:
        u = e["url"]
        if u in vistos:
            continue
        vistos[u] = testar_link(u)
    for e in entradas:
        u = e["url"]
        res = vistos[u]
        if res["ok"] and res.get("segmento"):
            problemas = inspecionar_bytes(res["segmento"], "midia")
            res["inspecao"] = problemas
            if problemas:
                res["ok"] = False
                res["motivo"] = "inspecao de bytes: " + "; ".join(problemas)
    for u, res in vistos.items():
        vd, det = triar_url(u, args.vt_key, res)
        res["vt"] = vd
        res["vt_detalhe"] = det
        if vd == "suspeito":
            res["ok"] = False
            res["reprovado_antivirus"] = det
    for u, res in vistos.items():
        alvo = "ABC News Live" if any(d in u for d in ("dssott", "abcnews-livestreams")) else "CBS News 24/7"
        cur = "OK     " if res["ok"] else "REMOVER"
        log(f"  {cur} {str(res.get('http', '-')):>4} {res.get('tipo', '-'):>6} "
            f"{res.get('container') or res.get('detalhe', '')[:40]:<12} [{alvo}] {u[:96]}")
        log(f"          stream: {res['motivo']} | anti-virus: {res['vt_detalhe']}")
    log("")

    # ---- escolha do melhor link por canal/afiliada
    log("=" * 72)
    log("3) ESCOLHA DO LINK POR CANAL E POR AFILIADA")
    log("=" * 72)
    escolhidos = []
    for nome, cfg in CANAIS.items():
        cands = [(u, r) for u, r in vistos.items()
                 if r["ok"] and any(host_de(u) == h or host_de(u).endswith("." + h) for h in cfg["hospedeiros"])]
        if not cands:
            log(f"  {nome}: NENHUM link aprovado no teste -> canal removido da lista")
            continue
        # uma entrada por afiliada: melhor master de cada host aprovado
        por_host = {}
        for u, r in cands:
            por_host.setdefault(host_de(u), []).append((u, r))
        escolhidos_host = []
        for h, grupo in sorted(por_host.items(), key=lambda kv: kv[0]):
            grupo.sort(key=lambda x: (x[1].get("tipo") != "master", -x[1].get("altura", 0), -x[1].get("n_variantes", 0)))
            u, r = grupo[0]
            if h.endswith("dssott.com"):
                rot = "Disney+/ABC (dssott.com)"
            elif h.endswith("akamaized.net"):
                rot = "Akamai/CDN ABC (akamaized.net)"
            elif h == "dai.google.com":
                rot = "Google DAI (dai.google.com)"
            else:
                rot = h
            escolhidos_host.append({"canal": nome, "url": u, "r": r, "afiliada": rot, "host": h})
            log(f"  {nome} / {rot}")
            log(f"    master {'sim' if r.get('tipo') == 'master' else 'nao'} | {r.get('detalhe', '')} | "
                f"container {r.get('container', '-')} | faixas {r.get('tracks', '-')} | "
                f"segmento {r.get('bytes', 0)} bytes")
            for u2, r2 in grupo[1:]:
                log(f"    dispensado (rendition da mesma afiliada, coberta pelo master): {u2[-70:]}")
        # ordena: maior resolucao primeiro dentro do mesmo canal
        escolhidos_host.sort(key=lambda e: (-e["r"].get("altura", 0), e["host"]))
        for i, e in enumerate(escolhidos_host):
            e["nome"] = nome if i == 0 else f"{nome} ({e['afiliada'].split(' (')[0]})"
        escolhidos.extend(escolhidos_host)
    log("")

    if not escolhidos:
        log("  nenhum canal sobreviveu; nada a gravar.")
        return 2

    # ---- logos
    log("=" * 72)
    log("4) LOGOS (tem que ser .jpg, funcional e fora do imgur)")
    log("=" * 72)
    cache_logo = {}
    for esc in escolhidos:
        nome = esc["canal"]
        if nome in cache_logo:
            esc["logo"] = cache_logo[nome]
            continue
        escolhido = None
        for lg in CANAIS[nome]["logos"]:
            r = testar_logo(lg)
            log(f"  [{nome}] {'OK   ' if r['ok'] else 'FALHA'} {lg}")
            log(f"           http={r.get('http', '-')} ct={r.get('ct', '-')} bytes={r.get('bytes', '-')} -> {r['motivo']}")
            if r["ok"]:
                escolhido = lg
                break
        if not escolhido:
            log(f"  [{nome}] nenhum logo valido encontrado")
        cache_logo[nome] = escolhido
        esc["logo"] = escolhido
    log("")

    # ---- EPG
    log("=" * 72)
    log("5) FONTES DE EPG (hoje / amanha / depois de amanha)")
    log("=" * 72)
    dias = dias_alvo()
    log(f"  dias verificados (UTC): {', '.join(dias)}")
    usados, resultados_epg = [], {}
    if not args.sem_epg:
        necessarios = {e["canal"]: CANAIS[e["canal"]]["tvg_id"] for e in escolhidos}
        for rot, url, pesado in FONTES_EPG:
            log(f"  testando {rot}: {url}")
            r = verificar_epg(url, sorted(set(necessarios.values())), dias, limite_bytes=(260 << 20) if pesado else (200 << 20))
            resultados_epg[rot] = r
            log(f"    HTTP ok={r['ok']} | last-modified={r['last_modified']}")
            log(f"    canais encontrados: {r.get('canais', [])}")
            for cid, dias_c in (r.get("programas") or {}).items():
                log(f"      {cid}: " + " | ".join(f"{d}={n}" for d, n in dias_c.items()))
            if not r["ok"]:
                log(f"    -> descartada: {r.get('motivo', 'sem dados')}")
            elif usados and r.get("bytes", 0) > 25 * 1024 * 1024:
                log(f"    -> validada, mas NAO inserida: os mesmos canais ja vem de uma EPG aprovada "
                    f"e esta pesa {r['bytes']/1048576:.0f} MB (pesada demais para o player)")
                r["descartada_por"] = "redundante e pesada"
            else:
                usados.append(url)
            log("")
    if not usados:
        log("  NENHUMA EPG validada: as entradas serao gravadas sem url-tvg")
    else:
        log(f"  EPGs aprovadas: {len(usados)}")
        for u in usados:
            log(f"    - {u}")
    log("")

    # ---- escrita
    log("=" * 72)
    log("6) GRAVACAO")
    log("=" * 72)
    bak = "(nenhum: modo auditoria)" if args.so_auditoria else f"{ARQUIVO}.bak.pre_corrigir_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    if args.so_auditoria:
        log("  --so-auditoria: nenhum backup criado")
    else:
        shutil.copy2(ARQUIVO, bak)
        log(f"  backup: {bak}")

    saida = ["#EXTM3U"]
    for esc in escolhidos:
        cfg = CANAIS[esc["canal"]]
        attrs = f' tvg-id="{cfg["tvg_id"]}" tvg-name="{esc["afiliada"].split(" (")[0]}"'
        if esc.get("logo"):
            attrs += f' tvg-logo="{esc["logo"]}"'
        for u in usados:
            attrs += f' url-tvg="{u}"'
        attrs += f' group-title="{cfg["grupo"]}"'
        saida.append(f"#EXTINF:-1{attrs},{esc['nome']}")
        saida.append(esc["url"])
    conteudo = "\n".join(saida) + "\n"

    # conference final: nenhum link sem #EXTINF em cima
    checagem = conteudo.splitlines()
    problemas = []
    anterior = ""
    for i, l in enumerate(checagem, 1):
        if l.strip() and not l.startswith("#") and not anterior.startswith("#EXTINF"):
            problemas.append(f"linha {i}: link sem #EXTINF acima")
        if l.strip():
            anterior = l.strip()
    log(f"  entradas gravadas: {len(escolhidos)} | links: {sum(1 for l in checagem if l.strip() and not l.startswith('#'))}")
    log(f"  link sem #EXTINF na linha de cima: {len(problemas)}")
    for p in problemas:
        log("   " + p)
    log(f"  entradas sem tvg-id: {sum(1 for l in checagem if l.startswith('#EXTINF') and 'tvg-id' not in l)}")
    log(f"  entradas sem tvg-logo: {sum(1 for l in checagem if l.startswith('#EXTINF') and 'tvg-logo' not in l)}")
    log(f"  logos nao .jpg: {sum(1 for l in checagem if l.startswith('#EXTINF') and re.search(r'tvg-logo=\"([^\"]+)\"', l) and not re.search(r'tvg-logo=\"([^\"]+)\"', l).group(1).lower().endswith('.jpg'))}")
    log(f"  logos imgur: {sum(1 for l in checagem if l.startswith('#EXTINF') and 'imgur' in l)}")
    log(f"  entradas sem url-tvg: {sum(1 for l in checagem if l.startswith('#EXTINF') and 'url-tvg' not in l)}")

    if args.so_auditoria:
        log("")
        log("  --so-auditoria: arquivo nao foi alterado")
    else:
        with open(ARQUIVO, "w", encoding="utf-8") as f:
            f.write(conteudo)
        log("")
        log(f"  {ARQUIVO} gravado ({len(conteudo)} bytes)")
    log("")

    # ---- resumo
    log("=" * 72)
    log("RESUMO")
    log("=" * 72)
    log(f"  antes: {len(entradas)} entradas ({len(set(urls))} links unicos)")
    log(f"  depois: {len(escolhidos)} entradas")
    for esc in escolhidos:
        cfg = CANAIS[esc["canal"]]
        log(f"    {esc['nome']} | {esc['afiliada']} | tvg-id={cfg['tvg_id']} | logo={esc.get('logo')}")
    removidos = [r for r in vistos.values() if not r["ok"]]
    log(f"  links reprovados: {len(removidos)} de {len(vistos)} testados")
    for r in removidos:
        log(f"    - {r['motivo']} | {r['url'][-78:]}")
    rel = f"relatorio_lista5_{DATA}.txt"
    with open(rel, "w", encoding="utf-8") as f:
        f.write(f"Backup: {bak}\n\n")
        f.write("\n".join(relatorio) + "\n")
    log(f"  relatorio: {rel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
