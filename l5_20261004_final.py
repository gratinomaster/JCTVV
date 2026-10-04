#!/usr/bin/env python3
"""
Correcao final da lista5.m3u (2026-10-04).

Etapas:
  1. Teste profundo dos streams (master -> variante -> segmentos, com video+audio reais).
  2. Teste anti-virus: reputacao (URLhaus / OpenPhish / Phishing.Database), DNSBL
     (Spamhaus DBL + SURBL) e heuristica de payload (nada de HTML/JS/EXE servido).
  3. Validacao dos tvg-logo (tem de ser .jpg de verdade, sem imgur).
  4. Validacao do EPG: 2 fontes (iptv-org US e epg.pw US), checando se os tvg-id
     tem programacao para hoje, amanha e depois de amanha.
  5. Reescreve lista5.m3u (backup antes) com #EXTINF acima de cada URL,
     url-tvg/x-tvg-url no cabecalho, tvg-id, tvg-logo .jpg e group-title.
  6. Revalida o arquivo gravado e grava relatorio.
"""
import concurrent.futures
import gzip
import json
import os
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from urllib.parse import urljoin, urlparse

import requests

ARQUIVO = "lista5.m3u"
RELATORIO = "relatorio_lista5_20261004_final.txt"
JSON_SAIDA = "l5_resultado_final_20261004.json"
CACHE = "/tmp/opencode/epg"
os.makedirs(CACHE, exist_ok=True)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
H = {"User-Agent": UA, "Accept": "*/*"}
TIMEOUT = (10, 25)

HOJE = date.today()
DIAS = [f"{(HOJE + timedelta(days=i)).strftime('%Y%m%d')}" for i in range(3)]

FONTES_EPG = [
    {
        "nome": "iptv-org US (iptv-epg.org)",
        "url": "https://iptv-epg.org/files/epg-us.xml.gz",
        "arquivo": os.path.join(CACHE, "iptv_epg_org_us.xml.gz"),
        "ids": {
            "ABC News Live": "ABCNewsLive.us",
            "Fox News Channel": "FoxNewsChannel.us",
            "Fox Business": "FoxBusiness.us",
            "CBS News 24/7": "CBSNews.us",
        },
    },
    {
        "nome": "epg.pw US",
        "url": "https://epg.pw/xmltv/epg_US.xml.gz",
        "arquivo": os.path.join(CACHE, "epg_pw_US.xml.gz"),
        "ids": {
            "ABC News Live": "465150",
            "Fox News Channel": "465372",
            "Fox Business": "464766",
            "CBS News 24/7": "464941",
        },
    },
]

CANDIDATOS = [
    {
        "canal": "ABC News Live",
        "grupo": "NEWS WORLD",
        "logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
        "urls": [
            "https://abcnews-livestreams.akamaized.net/out/v1/6a597119dbd5428a82dc11a2f514a1a2/"
            "abcn-live-10-cmaf-manifest/abcn-live-10-index.m3u8",
            "https://linear-abcnews-ftc-na-west-1.media.dssott.com/dvt2=exp=1791224880~url=%2Flas1%2Fva01%2F"
            "disneyplus%2Fchannel%2F79449312-79dd-473d-873c-515ebf4b5e5f-1781164031838%2F~psid="
            "e3eb06da-b185-437c-9bb4-a2e05aa18c33~did=2a1a3662-1796-4d94-b688-ed8433d622ca~country=US"
            "~kid=k02~hmac=0bbb464ff259c3759f4325942635de58af41041668f2370f7e932248d8128c66/las1/"
            "va01/disneyplus/channel/79449312-79dd-473d-873c-515ebf4b5e5f-1781164031838/"
            "ctr-all-hdri-sliding.m3u8?r=1080&v=1&hash=81fb88da5aab33fe54dc3f8d7ae5f0b2eaa56a8c",
        ],
    },
    {
        "canal": "Fox News Channel",
        "grupo": "NEWS WORLD",
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/"
                "15de0523-3be4-4a9a-8159-7020114e7036/b6ff623a-26d6-4fd9-8bb8-0856adbf38ce/"
                "1280x720/match/676/380/image.jpg?ve=1&tl=1",
        "urls": [
            "https://247preview.foxnews.com/hls/live/2020027/fncv3preview/primary.m3u8",
            "https://247.foxnews.com/hls/live/2003586/FNCHLSv3/master.m3u8?hdnea=exp=1791142080"
            "~acl=/*~hmac=461aeb941b838aa5352985a44f62a1c56384676cf9e892c26370dfa90f537ae7",
        ],
    },
    {
        "canal": "Fox Business",
        "grupo": "NEWS WORLD",
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/"
                "c9b2e2eb-7b87-435c-9510-eab2650ff944/8b584585-acf2-4c37-aa07-aaf2d077bb20/"
                "1280x720/match/676/380/image.jpg?ve=1&tl=1",
        "urls": [
            "https://247preview.foxbusiness.com/hls/live/2020026/fbnv3preview/primary.m3u8",
            "https://247.foxbusiness.com/hls/live/2003756/FBNHLSv3/master.m3u8?hdnea=exp=1791142080"
            "~acl=/*~hmac=461aeb941b838aa5352985a44f62a1c56384676cf9e892c26370dfa90f537ae7",
        ],
    },
    {
        "canal": "CBS News 24/7",
        "grupo": "NEWS WORLD",
        "logo": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/"
                "0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/"
                "949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
        "urls": [
            "https://cbsn-us-vtt.cbsnstream.cbsnews.com/out/v1/ef868690d34144509eda696884bf1619/master.m3u8",
            "https://cbsn-us.cbsnstream.cbsnews.com/out/v1/55a8648e8f134e82a470f83d562deeca/master.m3u8",
            "https://dai.google.com/linear/hls/pa/event/Sid4xiTQTkCT1SLu6rjUSQ/stream/"
            "2ee78a98-bf67-49a1-84e9-d5e887d78f7c:ATL/master.m3u8",
        ],
    },
]

BLOCKLISTS = [
    ("URLhaus (URLs de malware online)", "https://urlhaus.abuse.ch/downloads/text_online/", "url"),
    ("URLhaus (hostfile)", "https://urlhaus.abuse.ch/downloads/hostfile/", "url"),
    ("OpenPhish", "https://openphish.com/feed.txt", "url"),
    ("Phishing.Database (ACTIVE)", "https://raw.githubusercontent.com/mitchellkrogza/Phishing.Database/"
     "master/phishing-domains-ACTIVE.txt", "host"),
]


def log(msg=""):
    print(msg, flush=True)


def get(url, headers=None, timeout=TIMEOUT):
    h = dict(H)
    if headers:
        h.update(headers)
    return requests.get(url, headers=h, timeout=timeout, allow_redirects=True)


# --------------------------------------------------------------------------- #
# 1. teste profundo de stream
# --------------------------------------------------------------------------- #
def drm(text):
    for ln in text.splitlines():
        ln = ln.strip()
        if ln.startswith(("#EXT-X-KEY:", "#EXT-X-SESSION-KEY:")):
            for p in ln.split(","):
                if "METHOD=" in p:
                    m = p.split("METHOD=")[1].strip().strip('"').upper()
                    if m and m != "NONE":
                        return m
    return None


def variantes(base, text):
    linhas = [l.strip() for l in text.splitlines() if l.strip()]
    out = []
    for i, l in enumerate(linhas):
        if l.startswith("#EXT-X-STREAM-INF:") and i + 1 < len(linhas):
            nxt = linhas[i + 1]
            if not nxt.startswith("#"):
                bw = 0
                res = ""
                for p in l.split(","):
                    if "BANDWIDTH=" in p:
                        try:
                            bw = int(p.split("BANDWIDTH=")[1].split("-")[0])
                        except ValueError:
                            bw = 0
                    if "RESOLUTION=" in p:
                        res = p.split("RESOLUTION=")[1]
                out.append((bw, res, urljoin(base, nxt)))
    out.sort(key=lambda x: x[0], reverse=True)
    return out


def segmentos(base, text, limite=3):
    linhas = [l.strip() for l in text.splitlines() if l.strip()]
    uris = []
    for i, l in enumerate(linhas):
        if l.startswith("#EXT-X-MAP:"):
            uris.append(urljoin(base, l.split("URI=", 1)[1].split(",")[0].strip('"\'')))
        elif not l.startswith("#") and i and linhas[i - 1].startswith("#EXTINF"):
            uris.append(urljoin(base, l))
    return uris[:limite]


def ts_secao(pkt):
    """Devolve a secao PSI (PAT/PMT) do pacote, resolvendo pointer_field e AFC."""
    afc = (pkt[3] >> 4) & 0x03
    if afc not in (1, 3):
        return b""
    off = 4
    if afc == 3:
        if len(pkt) < 6:
            return b""
        off += 1 + pkt[4]
    if off >= len(pkt):
        return b""
    ptr = pkt[off]
    off += 1 + ptr
    return pkt[off:]


def ts_streams(dados):
    """Le PAT -> PMT do MPEG-TS e devolve [(stream_type, pid), ...]."""
    def ler_pmt(sec):
        pil = ((sec[10] & 0x0F) << 8) | sec[11]
        j = 12 + pil
        out = []
        while j + 4 < len(sec):
            st = sec[j]
            pid = ((sec[j + 1] & 0x1F) << 8) | sec[j + 2]
            esil = ((sec[j + 3] & 0x0F) << 8) | sec[j + 4]
            out.append((st, pid))
            j += 5 + esil
            if st == 0:
                break
        return out

    pmt_pids = set()
    for i in range(0, min(len(dados), 3000 * 188) - 187, 188):
        pkt = dados[i:i + 188]
        if len(pkt) < 188 or pkt[0] != 0x47:
            continue
        pid = ((pkt[1] & 0x1F) << 8) | pkt[2]
        sec = ts_secao(pkt) if (pkt[1] & 0x40) else b""
        if pid == 0x0000 and sec[:1] == b"\x00" and len(sec) >= 12:
            j = 8
            while j + 4 <= len(sec):
                prog = (sec[j] << 8) | sec[j + 1]
                if prog != 0:
                    pmt_pids.add(((sec[j + 2] & 0x1F) << 8) | sec[j + 3])
                j += 4
        elif sec[:1] == b"\x02" and len(sec) >= 13:
            st = ler_pmt(sec)
            if st:
                return st
    for i in range(0, min(len(dados), 3000 * 188) - 187, 188):
        pkt = dados[i:i + 188]
        if len(pkt) < 188 or pkt[0] != 0x47:
            continue
        pid = ((pkt[1] & 0x1F) << 8) | pkt[2]
        if pid in pmt_pids and (pkt[1] & 0x40):
            sec = ts_secao(pkt)
            if sec[:1] == b"\x02" and len(sec) >= 13:
                st = ler_pmt(sec)
                if st:
                    return st
    return []


def ts_payload(dados, pid_desejado, limite=40000):
    """Junta os bytes de payload dos pacotes de um PID (para conferir o codec)."""
    out = bytearray()
    for i in range(0, min(len(dados), 3000 * 188) - 187, 188):
        pkt = dados[i:i + 188]
        if len(pkt) < 188 or pkt[0] != 0x47:
            continue
        pid = ((pkt[1] & 0x1F) << 8) | pkt[2]
        if pid != pid_desejado:
            continue
        afc = (pkt[3] >> 4) & 0x03
        off = 4
        if afc == 2:
            continue
        if afc == 3:
            off += 1 + pkt[4]
        out += pkt[off:]
        if len(out) >= limite:
            break
    return bytes(out)


VIDEO_TS = {0x01, 0x02, 0x10, 0x1B, 0x24, 0x1C}
AUDIO_AC3 = {0x81, 0x87, 0x48}
AUDIO_ADTS = {0x0F, 0x11}
AUDIO_MP2 = {0x03, 0x04}
AUDIO_TS = AUDIO_AC3 | AUDIO_ADTS | AUDIO_MP2 | {0x06}


def ts_tem_audio(dados, streams):
    """Confirma que existe audio de verdade (sync word AC-3 / ADTS / MP2)."""
    for st, pid in streams:
        if st in AUDIO_AC3:
            if b"\x0b\x77" in ts_payload(dados, pid):
                return True, "AC-3"
        elif st in AUDIO_ADTS:
            if b"\xff\xf1" in ts_payload(dados, pid) or b"\xff\xf9" in ts_payload(dados, pid):
                return True, "AAC-ADTS"
        elif st in AUDIO_MP2:
            return True, "MP2"
    return False, ""


def ts_tem_video(streams):
    for st, _ in streams:
        if st in VIDEO_TS:
            return True
    return False


def testa_stream(url):
    """Retorna (status, motivo). status: 'video+audio' | 'video_sem_audio' | 'falha'."""
    try:
        r = get(url)
    except Exception as e:
        return "falha", f"erro={type(e).__name__}"
    if r.status_code >= 400:
        return "falha", f"http={r.status_code}"
    texto = r.text
    if "#EXTM3U" not in texto[:3000]:
        return "falha", "resposta nao e playlist HLS"
    if re.search(r"text/html", r.headers.get("Content-Type", ""), re.I):
        return "falha", "servidor devolveu HTML"
    metodo = drm(texto)
    if metodo:
        return "falha", f"protegido DRM={metodo}"

    grupo_audio = "TYPE=\"AUDIO\"" in texto

    if "#EXT-X-STREAM-INF" in texto:
        vs = variantes(r.url, texto)
        if not vs:
            return "falha", "master sem variantes"
        erros = []
        melhor_video = None
        for bw, res, v in vs[:4]:
            try:
                rv = get(v)
            except Exception as e:
                erros.append(f"{bw//1000}k erro={type(e).__name__}")
                continue
            if rv.status_code != 200 or "#EXTM3U" not in rv.text[:2000]:
                erros.append(f"{bw//1000}k http={rv.status_code}")
                continue
            vt = rv.text
            if drm(vt):
                erros.append(f"{bw//1000}k DRM")
                continue
            segs = segmentos(rv.url, vt)
            if not segs:
                erros.append(f"{bw//1000}k sem segmentos")
                continue
            ok_all, tv, ta, detalhe, codec = True, False, False, "", ""
            for s in segs:
                try:
                    rs = get(s, headers={"Range": "bytes=0-400000"})
                except Exception as e:
                    ok_all = False
                    detalhe = f"seg erro={type(e).__name__}"
                    break
                if rs.status_code not in (200, 206) or not rs.content:
                    ok_all = False
                    detalhe = f"seg http={rs.status_code}"
                    break
                cab = rs.content[:4]
                if cab[:3] == b"\x00\x00\x00" or rs.content[4:8] == b"ftyp":
                    tv, ta = True, True          # fMP4 traz video e audio no mesmo init
                elif cab[0] == 0x47:
                    streams = ts_streams(rs.content)
                    if not streams:
                        ok_all = False
                        detalhe = "TS sem PMT"
                        break
                    tv = tv or ts_tem_video(streams)
                    achou, codec = ts_tem_audio(rs.content, streams)
                    ta = ta or achou
            if not ok_all:
                erros.append(f"{bw//1000}kbps {detalhe}")
                continue
            marca = f"{bw//1000}kbps {res or '?'} ({len(segs)} segmentos)"
            if tv and ta:
                return "video+audio", f"{marca} video+audio OK, audio={codec or 'grupo'}"
            if tv and melhor_video is None:
                melhor_video = marca
            erros.append(f"{marca} video={tv} audio={ta}")
        if melhor_video:
            return "video_sem_audio", f"{melhor_video} so video (sem audio no CDN)"
        return "falha", "todas as variantes rejeitadas: " + "; ".join(erros[:3])

    segs = segmentos(r.url, texto)
    if not segs:
        return "falha", "sem segmentos"
    try:
        rs = get(segs[0], headers={"Range": "bytes=0-400000"})
    except Exception as e:
        return "falha", f"seg erro={type(e).__name__}"
    if rs.status_code not in (200, 206) or not rs.content:
        return "falha", f"seg http={rs.status_code}"
    if rs.content[4:8] == b"ftyp" or rs.content[:3] == b"\x00\x00\x00":
        return "video+audio", "media playlist fMP4 ok"
    if rs.content[0] == 0x47:
        streams = ts_streams(rs.content)
        tv = ts_tem_video(streams)
        achou, codec = ts_tem_audio(rs.content, streams)
        ta = achou or grupo_audio
        if tv and ta:
            return "video+audio", f"media playlist TS video+audio OK (audio={codec or 'grupo'})"
        if tv:
            return "video_sem_audio", "media playlist TS so video (sem audio)"
        return "falha", f"TS video={tv} audio={ta}"
    return "falha", "segmento nao parece midia"


# --------------------------------------------------------------------------- #
# 2. anti-virus
# --------------------------------------------------------------------------- #
def carrega_blocklists():
    urls, hosts = set(), set()
    for nome, url, modo in BLOCKLISTS:
        try:
            r = get(url, timeout=(10, 120))
            linhas = r.text.splitlines()
            for l in linhas:
                l = l.strip()
                if not l or l.startswith("#"):
                    continue
                if modo == "url":
                    urls.add(l.lower())
                    h = urlparse(l).hostname
                    if h:
                        hosts.add(h.lower())
                else:
                    hosts.add(l.lower().lstrip("."))
            log(f"   {nome}: {len(linhas)} linhas")
        except Exception as e:
            log(f"   {nome}: FALHOU ({type(e).__name__})")
    return urls, hosts


def dnsbl(host):
    hits = []
    for zona in ("dbl.spamhaus.org", "multi.surbl.org"):
        try:
            r = subprocess.run(["dig", "+short", "+time=5", "+tries=1", f"{host}.{zona}", "A"],
                               capture_output=True, timeout=15)
            out = r.stdout.decode(errors="ignore").strip()
            if out:
                hits.append(f"{zona}={out}")
        except Exception:
            pass
    return hits


def antvirus(url, bl_urls, bl_hosts):
    host = (urlparse(url).hostname or "").lower()
    reg = ".".join(host.split(".")[-2:]) if len(host.split(".")) >= 2 else host
    base = url.split("?")[0].lower()
    achados = []
    if url.lower() in bl_urls or base in bl_urls:
        achados.append("URL em blocklist de malware/phishing")
    if host in bl_hosts or reg in bl_hosts:
        achados.append("dominio em blocklist de phishing")
    dns = dnsbl(reg)
    if dns:
        achados.append("DNSBL " + ",".join(dns))
    try:
        r = get(url)
        ct = (r.headers.get("Content-Type") or "").lower()
        if r.status_code >= 400:
            achados.append(f"http={r.status_code}")
        if re.search(r"text/html|javascript|x-msdownload|x-executable|application/octet-stream", ct):
            if "mpegurl" not in ct:
                achados.append(f"content-type suspeito={ct}")
        corpo = r.content[:4000]
        if b"<html" in corpo.lower() or b"access denied" in corpo.lower():
            achados.append("servidor devolveu HTML em vez de midia")
        if b"#EXTM3U" not in corpo:
            achados.append("nao devolve playlist HLS")
    except Exception as e:
        achados.append(f"erro={type(e).__name__}")
    return (not achados), achados


# --------------------------------------------------------------------------- #
# 3. logos
# --------------------------------------------------------------------------- #
def testa_logo(url):
    if "imgur" in url.lower():
        return False, "proibido (imgur.com)"
    caminho = urlparse(url).path.lower()
    if not caminho.endswith((".jpg", ".jpeg")):
        return False, "nao termina em .jpg"
    try:
        r = get(url, timeout=(10, 30))
    except Exception as e:
        return False, f"erro={type(e).__name__}"
    if r.status_code != 200:
        return False, f"http={r.status_code}"
    ct = (r.headers.get("Content-Type") or "").lower()
    if "image/jpeg" not in ct and not r.content[:3] == b"\xff\xd8\xff":
        return False, f"content-type={ct or 'desconhecido'} nao e JPEG"
    if r.content[:3] != b"\xff\xd8\xff":
        return False, "bytes nao comecam com marcador JPEG"
    return True, f"JPEG ok ({len(r.content)} bytes)"


# --------------------------------------------------------------------------- #
# 4. EPG
# --------------------------------------------------------------------------- #
def garante_epg(fonte):
    arq = fonte["arquivo"]
    if not os.path.exists(arq) or os.path.getsize(arq) < 10000:
        log(f"   baixando {fonte['nome']} ...")
        r = get(fonte["url"], timeout=(15, 900))
        r.raise_for_status()
        with open(arq, "wb") as f:
            f.write(r.content)
    return arq


def checa_epg(fonte):
    arq = garante_epg(fonte)
    opener = gzip.open if arq.endswith(".gz") else open
    dias = {cid: set() for cid in fonte["ids"].values()}
    nprog = {cid: 0 for cid in fonte["ids"].values()}
    exemplos = {cid: [] for cid in fonte["ids"].values()}
    with opener(arq, "rb") as f:
        for _, el in ET.iterparse(f, events=("end",)):
            if el.tag == "programme":
                ch = el.get("channel")
                if ch in dias:
                    dias[ch].add((el.get("start") or "")[:8])
                    nprog[ch] += 1
                    if len(exemplos[ch]) < 3:
                        t = el.find("title")
                        exemplos[ch].append((el.get("start"),
                                             (t.text or "")[:38] if t is not None else ""))
                el.clear()
            elif el.tag == "channel":
                el.clear()
    res = {}
    for canal, cid in fonte["ids"].items():
        cob = [d for d in DIAS if d in dias.get(cid, set())]
        res[canal] = {"id": cid, "programas": nprog[cid], "cobertura": cob,
                      "ok": len(cob) == 3, "exemplos": exemplos[cid]}
    return res


# --------------------------------------------------------------------------- #
def main():
    log("=" * 96)
    log("CORRECAO FINAL DA lista5.m3u - " + HOJE.isoformat())
    log("=" * 96)
    log(f"dias exigidos: hoje={DIAS[0]} amanha={DIAS[1]} depois={DIAS[2]}\n")

    log("[1] TESTE PROFUNDO DOS STREAMS")
    escolhidos = {}
    testes_stream = {}
    for c in CANDIDATOS:
        for u in c["urls"]:
            status, why = testa_stream(u)
            testes_stream[u] = (status, why)
            marca = {"video+audio": "OK  ", "video_sem_audio": "SOM ", "falha": "FALHA"}[status]
            log(f"   {marca} {c['canal']:18} {why}")
            log(f"          {u[:120]}")
            if status == "video+audio":
                escolhidos[c["canal"]] = (u, why)
                break
            if status == "video_sem_audio" and c["canal"] not in escolhidos:
                escolhidos[c["canal"]] = (u, why)

    log("\n[2] TESTE ANTI-VIRUS (reputacao + DNSBL + payload)")
    bl_urls, bl_hosts = carrega_blocklists()
    log(f"   blocklists: {len(bl_urls)} urls / {len(bl_hosts)} hosts")
    av = {}
    for c in CANDIDATOS:
        if c["canal"] not in escolhidos:
            continue
        u = escolhidos[c["canal"]][0]
        ok, achados = antvirus(u, bl_urls, bl_hosts)
        av[c["canal"]] = {"url": u, "ok": ok, "achados": achados}
        log(f"   {'LIMPO' if ok else 'SUSPEITO':9} {c['canal']:18} "
            f"{'nada encontrado' if ok else '; '.join(achados)}")

    log("\n[3] VALIDACAO DOS tvg-logo (.jpg, sem imgur)")
    logos = {}
    for c in CANDIDATOS:
        if c["canal"] not in escolhidos:
            continue
        ok, why = testa_logo(c["logo"])
        logos[c["canal"]] = {"url": c["logo"], "ok": ok, "motivo": why}
        log(f"   {'OK   ' if ok else 'FALHA'} {c['canal']:18} {why}")

    log("\n[4] VALIDACAO DAS FONTES DE EPG")
    epgs = []
    aprovadas = []
    resultado_epg = {}
    for fonte in FONTES_EPG:
        try:
            res = checa_epg(fonte)
        except Exception as e:
            log(f"   FALHA {fonte['nome']}: {type(e).__name__} {e}")
            continue
        resultado_epg[fonte["nome"]] = res
        todos = all(v["ok"] for v in res.values())
        log(f"   {fonte['nome']} -> {fonte['url']}")
        for canal, v in res.items():
            log(f"      {canal:18} id={v['id']:22} programas={v['programas']:4} "
                f"hoje/amanha/+2={len(v['cobertura'])}/3 {v['cobertura']}")
            if v["ok"]:
                for ini, tit in v["exemplos"][:1]:
                    log(f"         exemplo: {ini} {tit}")
        if todos:
            aprovadas.append(fonte)
        else:
            log("      fonte descartada (cobertura incompleta)")

    # So entram no cabecalho fontes que cobrem todos os canais aprovados E usam o
    # mesmo namespace de tvg-id da fonte principal, senao o player nao casa o guia.
    canais_aprovados = [c["canal"] for c in CANDIDATOS if c["canal"] in escolhidos]
    epgs = []
    if aprovadas:
        base = None
        for f in aprovadas:
            if all(f["ids"].get(c) for c in canais_aprovados):
                base = f
                break
        if base is None:
            log("\n   ERRO: nenhuma fonte cobre todos os canais aprovados; arquivo nao alterado.")
            return 1
        epgs = [base]
        for f in aprovadas:
            if f is base:
                continue
            if all(f["ids"].get(c) == base["ids"].get(c) for c in canais_aprovados):
                epgs.append(f)
            else:
                log(f"   fonte nao declarada no cabecalho (tvg-id diferente: "
                    f"{f['nome']} usa {sorted(set(f['ids'].values()))}): nao casa com a lista")

    canais = [c for c in CANDIDATOS
              if c["canal"] in escolhidos
              and av.get(c["canal"], {}).get("ok")
              and logos.get(c["canal"], {}).get("ok")]

    log(f"\n[5] Canais aprovados: {len(canais)} de {len(CANDIDATOS)}")
    for c in CANDIDATOS:
        if c["canal"] not in [x["canal"] for x in canais]:
            log(f"   REMOVIDO: {c['canal']}")

    if not canais:
        log("\nERRO: nenhum canal passou em todas as etapas; arquivo nao alterado.")
        return 1

    uris_epg = " ".join(f["url"] for f in epgs)
    id_principal = epgs[0]["ids"] if epgs else {}
    if len(epgs) < len(aprovadas):
        log("\n   AVISO: alguma fonte com guia valido NAO foi declarada no cabecalho")
        log("           porque usa outros tvg-id (veja secao 4 e relatorio).")

    backup = f"{ARQUIVO}.bak.pre_tarefa_{HOJE.strftime('%Y%m%d')}"
    shutil.copy2(ARQUIVO, backup)
    log(f"\n   backup: {backup}")

    cabecalho = '#EXTM3U url-tvg="{0}" x-tvg-url="{0}"'.format(uris_epg)
    linhas = [cabecalho]
    for c in canais:
        url = escolhidos[c["canal"]][0]
        tvgid = ""
        for f in epgs:
            if c["canal"] in f["ids"]:
                tvgid = f["ids"][c["canal"]]
                break
        nome = c["canal"] if c["canal"] in id_principal else c["canal"]
        linhas.append(
            f'#EXTINF:-1 tvg-id="{tvgid}" tvg-name="{nome}" '
            f'tvg-logo="{c["logo"]}" group-title="{c["grupo"]}",{nome}')
        linhas.append(url)

    tmp = ARQUIVO + ".new"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(linhas) + "\n")
    shutil.move(tmp, ARQUIVO)

    log(f"\n[6] Arquivo gravado: {ARQUIVO}")
    log("=" * 96)
    with open(ARQUIVO, encoding="utf-8") as f:
        for l in f.read().splitlines():
            log(l[:200])

    rel = [
        "RELATORIO FINAL - lista5.m3u",
        f"Data: {HOJE.isoformat()} (hoje/amanha/+2 = {DIAS[0]}, {DIAS[1]}, {DIAS[2]})",
        f"Backup: {backup}",
        f"Fontes de EPG no cabecalho: {len(epgs)}/{len(FONTES_EPG)}",
        "",
        "FONTES DE EPG NO ARQUIVO:",
    ]
    for f_ in epgs:
        rel.append(f"  - {f_['nome']}: {f_['url']}")
    for f_ in FONTES_EPG:
        if f_ not in epgs:
            rel.append(f"  - (nao declarada) {f_['nome']}: {f_['url']} "
                       f"usa tvg-id proprios {sorted(set(f_['ids'].values()))} - "
                       f"jogadores casam o EPG pelo tvg-id, entao nao serviria a lista")
    rel.append("")
    for c in CANDIDATOS:
        rel.append(f"CANAL: {c['canal']}")
        for u in c["urls"]:
            status, why = testes_stream.get(u, ("falha", "nao testado"))
            if u == escolhidos.get(c["canal"], (None,))[0]:
                rel.append(f"  [MANTIDO] {why}")
                rel.append(f"            {u}")
            else:
                rel.append(f"  [DESCARTADO] {status}: {why}")
                rel.append(f"              {u[:120]}")
        if c["canal"] in av:
            rel.append(f"  ANTIVIRUS: {'LIMPO' if av[c['canal']]['ok'] else 'SUSPEITO'} "
                       f"{av[c['canal']]['achados']}")
        if c["canal"] in logos:
            rel.append(f"  LOGO: {logos[c['canal']]['motivo']} {logos[c['canal']]['url'][:100]}")
        for f_ in FONTES_EPG:
            if c["canal"] in f_["ids"] and f_["nome"] in resultado_epg:
                v = resultado_epg[f_["nome"]][c["canal"]]
                rel.append(f"  EPG {f_['nome']}: id={v['id']} "
                           f"programas={v['programas']} cobertura={v['cobertura']}")
        rel.append("")
    with open(RELATORIO, "w", encoding="utf-8") as f:
        f.write("\n".join(rel) + "\n")

    with open(JSON_SAIDA, "w", encoding="utf-8") as f:
        json.dump({
            "streams": {k: {"url": v[0], "motivo": v[1]} for k, v in escolhidos.items()},
            "antivirus": av,
            "logos": logos,
            "epg": [{"fonte": f_["nome"], "url": f_["url"]} for f_ in epgs],
            "canais_aprovados": [c["canal"] for c in canais],
        }, f, indent=2, ensure_ascii=False)

    log(f"\nRelatorio: {RELATORIO}\nJSON: {JSON_SAIDA}")
    return 0


if __name__ == "__main__":
    sys.exit(main())