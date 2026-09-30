#!/usr/bin/env python3
"""
Verificacao completa dos canais candidatos do lista5.m3u.

Para cada canal faz:
  1. Teste de transmissao: manifesto -> variante -> init -> segmento mais recente,
     exigindo bytes de midia de verdade (TS 0x47 ou caixa ISO-BMFF).
  2. Teste anti-virus ClamAV 1.4.6 (assinaturas de hoje) nos bytes reais servidos
     (manifesto + init + segmentos) e no tvg-logo.
  3. Reputacao de URL/host contra listas vivas de malware/phishing
     (URLhaus, OpenPhish, Phishing.Database) e DNSBL (Spamhaus DBL).
  4. Teste do tvg-logo: precisa ser JPEG de verdade e nao pode ser imgur.com.
  5. Teste do EPG: confere se o tvg-id existe na fonte XMLTV e se ha programme
     para hoje, amanha e depois de amanha.
"""
import csv
import io
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
import zlib
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests

H = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
    "Accept": "*/*",
}
TIMEOUT = 30
SEG_TIMEOUT = 45
MAX_SEG = 3
WORK = Path("/tmp/opencode/avscan/work")
CLAMSCAN = "/tmp/opencode/avscan/usr/local/bin/clamscan"
CLAM_LIB = "/tmp/opencode/avscan/usr/local/lib"
CLAM_DB = "/tmp/opencode/avscan/db"
BL_DIR = "/tmp/opencode"
EPG_URL = "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz"
MAGIC = (b"ftyp", b"styp", b"moof", b"mdat", b"sidx", b"emsg", b"free", b"skip", b"wide")

# Canais candidatos: nome, tvg-id, logo, grupo, lista de URLs (1a = principal)
CANDIDATOS = [
    dict(nome="ABC News Live", tvg_id="ABC.News.Live.us2",
         logo="https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
         grupo="NEWS WORLD",
         urls=[
             "https://abcnews-livestreams.akamaized.net/out/v1/6a597119dbd5428a82dc11a2f514a1a2/abcn-live-10-cmaf-manifest/abcn-live-10-index.m3u8",
             "https://pb-0n3n2ej0w8pl9.akamaized.net/ABCNewsLive_Disney.m3u8",
         ]),
    dict(nome="Fox News Channel", tvg_id="Fox.News.Channel.HD.us2",
         logo="https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/15de0523-3be4-4a9a-8159-7020114e7036/b6ff623a-26d6-4fd9-8bb8-0856adbf38ce/1280x720/match/676/380/image.jpg",
         grupo="NEWS WORLD",
         urls=["https://247preview.foxnews.com/hls/live/2020027/fncv3preview/primary.m3u8"]),
    dict(nome="Fox Business", tvg_id="Fox.Business.HD.us2",
         logo="https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/c9b2e2eb-7b87-435c-9510-eab2650ff944/8b584585-acf2-4c37-aa07-aaf2d077bb20/1280x720/match/676/380/image.jpg",
         grupo="NEWS WORLD",
         urls=["https://247preview.foxbusiness.com/hls/live/2020026/fbnv3preview/primary.m3u8"]),
    dict(nome="CBS News 24/7", tvg_id="CBS.News.National.Stream.us2",
         logo="https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
         grupo="NEWS WORLD",
         urls=["https://cbsn-us.cbsnstream.cbsnews.com/out/v1/55a8648e8f134e82a470f83d562deeca/master.m3u8"]),
]

# URLs que existiam no lista5.m3u e devem ser julgadas (incluindo as de token expirado)
AVALIADOS_EXTRA = [
    ("[antigo] Fox News 247+hdnea", "https://247.foxnews.com/hls/live/2003586/FNCHLSv3/master.m3u8?hdnea=exp=1790736284~acl=/*~hmac=4bce2123c63430635adfa62c0ba014bb281cd802a0d65becb795fe13af48c5c2"),
    ("[antigo] Fox Business 247+hdnea", "https://247.foxbusiness.com/hls/live/2003756/FBNHLSv3/master.m3u8?hdnea=exp=1790736283~acl=/*~hmac=5b841224644fd9f486e578f7dc1e7ce059e881527c2f5b86b634f8308acb5506"),
    ("[antigo] ABC Disney dssott", "https://linear-abcnews-ftc-na-west-1.media.dssott.com/dvt2=exp=1790819081~url=%2Flas1%2Fva01%2Fdisneyplus%2Fchannel%2F79449312-79dd-473d-873c-515ebf4b5e5f-1781164031838%2F~psid=b2d8f180-4908-48c7-81f0-3b11af32720e~did=08637cdb-ed3c-4c6a-9990-557f8b64cadb~country=US~kid=k02~hmac=9cf7674030000ce0ac626d9b3d64f2d4b862fa05677cc92cec3f434635a83afb/las1/va01/disneyplus/channel/79449312-79dd-473d-873c-515ebf4b5e5f-1781164031838/ctr-all-hdri-sliding.m3u8?r=1080&v=1&hash=81fb88da5aab33fe54dc3f8d7ae5f0b2eaa56a8c"),
    ("[antigo] ABC Disney audio 64K", "https://linear-abcnews-ftc-na-west-1.media.dssott.com/dvt2=exp=1790819081~url=%2Flas1%2Fva01%2Fdisneyplus%2Fchannel%2F79449312-79dd-473d-873c-515ebf4b5e5f-1781164031838%2F~psid=b2d8f180-4908-48c7-81f0-3b11af32720e~did=08637cdb-ed3c-4c6a-9990-557f8b64cadb~country=US~kid=k02~hmac=9cf7674030000ce0ac626d9b3d64f2d4b862fa05677cc92cec3f434635a83afb/las1/va01/disneyplus/channel/79449312-79dd-473d-873c-515ebf4b5e5f-1781164031838/audio-aac-1-64K/64_slide.m3u8"),
    ("[antigo] ABC akamai index_4_0", "https://abcnews-livestreams.akamaized.net/out/v1/6a597119dbd5428a82dc11a2f514a1a2/abcn-live-10-cmaf-manifest/abcn-live-10-index_4_0.m3u8"),
    ("[antigo] ABC akamai index_3", "https://abcnews-livestreams.akamaized.net/out/v1/6a597119dbd5428a82dc11a2f514a1a2/abcn-live-10-cmaf-manifest/abcn-live-10-index_3.m3u8"),
    ("[antigo] CBS DAI google master", "https://dai.google.com/linear/hls/pa/event/Sid4xiTQTkCT1SLu6rjUSQ/stream/ab37821e-5807-47fc-954b-96aabb5d9853:TUL/master.m3u8"),
    ("[antigo] CBS DAI google variant 441k", "https://dai.google.com/linear/hls/pa/event/Sid4xiTQTkCT1SLu6rjUSQ/stream/ab37821e-5807-47fc-954b-96aabb5d9853:TUL/variant/2ed2c78fd57ae51fb6ba5d4bbd59e953/bandwidth/441000.m3u8"),
    ("[antigo] ABC logo s.abcnews", "https://s.abcnews.com/images/Live/abc_news_live-abc-ml-250210_1739199021469_hpMain_16x9_608.jpg"),
]


def pares_token(q):
    return [x for x in (q or "").split("~") if "=" in x]


def herdar(base, child):
    """Resolve URL relativa preservando tokens ~token= do query (ex.: dssott)."""
    p = urlsplit(base)
    q = pares_token(p.query)
    frag = child.split("|")[0].split("#")[0].strip()
    full = urljoin(base, frag)
    if q:
        full = full.split("?")[0] + "?" + "~".join(q)
    return full


def parece_midia(b):
    """MPEG-TS (0x47) ou ISO-BMFF (caixa size+4CC)."""
    if not b or len(b) < 8:
        return False
    if b[:1] == b"\x47":
        return True
    if any(k in b[:64] for k in MAGIC):
        return True
    tam = int.from_bytes(b[:4], "big")
    return 8 <= tam <= 64 * 1024 * 1024 and b[4:8].isascii() and b[4:8].isalnum()


def verificar_stream(url, destino):
    """Teste de ponta a ponta. Salva os bytes entregues em destino. Retorna dict."""
    res = dict(url=url, ok=False, motivo="", http=0, ctype="", bytes_mid=0, arquivos=[])
    r = requests.get(url, headers=H, timeout=TIMEOUT)
    res["http"] = r.status_code
    res["ctype"] = r.headers.get("Content-Type", "")
    if r.status_code != 200:
        res["motivo"] = "HTTP %d" % r.status_code
        return res
    if "#EXTM3U" not in r.text:
        res["motivo"] = "resposta nao e M3U"
        return res
    if "#EXT-X-ENDLIST" in r.text:
        res["motivo"] = "VOD (ENDLIST), nao e live"
        return res

    destino.mkdir(parents=True, exist_ok=True)
    p0 = destino / "00-playlist.m3u8"
    p0.write_bytes(r.content)
    res["arquivos"].append(p0)

    base, texto = url, r.text
    variantes = re.findall(r"#EXT-X-STREAM-INF:[^\n]*\n([^\n#]+)", texto)
    if variantes:
        for alvo in variantes[:5]:
            child = herdar(url, alvo.strip())
            try:
                rr = requests.get(child, headers=H, timeout=TIMEOUT)
            except Exception:
                continue
            if rr.status_code == 200 and "#EXTM3U" in rr.text:
                base, texto = child, rr.text
                p1 = destino / "01-variante.m3u8"
                p1.write_bytes(rr.content)
                res["arquivos"].append(p1)
                break
        else:
            res["motivo"] = "nenhuma variante responde"
            return res

    mp = re.search(r'#EXT-X-MAP:URI="([^"]+)"', texto)
    if mp:
        ir = herdar(base, mp.group(1))
        try:
            rr = requests.get(ir, headers=H, timeout=TIMEOUT)
        except Exception as e:
            res["motivo"] = "init segment conexao (%s)" % type(e).__name__
            return res
        if rr.status_code != 200 or b"ftyp" not in rr.content[:64]:
            res["motivo"] = "init segment invalido (HTTP %d)" % rr.status_code
            return res
        pi = destino / "02-init.m4s"
        pi.write_bytes(rr.content)
        res["arquivos"].append(pi)

    segs = [l.strip() for l in texto.splitlines() if l.strip() and not l.startswith("#")]
    if not segs:
        res["motivo"] = "manifesto sem segmentos"
        return res

    # segmentos mais recentes primeiro (em live os antigos expiram)
    for i, alvo in enumerate(reversed(segs[-MAX_SEG:])):
        su = herdar(base, alvo)
        try:
            rs = requests.get(su, headers=H, timeout=SEG_TIMEOUT, stream=True)
        except Exception as e:
            res["motivo"] = "segmento conexao (%s)" % type(e).__name__
            continue
        corpo = next(rs.iter_content(512 * 1024), b"")
        st = rs.status_code
        rs.close()
        if st != 200 or len(corpo) < 2048:
            res["motivo"] = "segmento HTTP %d / %dB" % (st, len(corpo))
            continue
        if not parece_midia(corpo):
            res["motivo"] = "segmento nao e midia"
            continue
        ext = ".ts" if corpo[:1] == b"\x47" else ".m4s"
        pf = destino / ("03-seg%d%s" % (i, ext))
        pf.write_bytes(corpo)
        res["arquivos"].append(pf)
        res["bytes_mid"] += len(corpo)

    if not res["bytes_mid"]:
        res["motivo"] = res["motivo"] or "nenhum segmento valido"
        return res
    res["ok"] = True
    res["motivo"] = "%d variante(s), %d bytes de midia" % (len(variantes), res["bytes_mid"])
    return res


def carregar_blocklists():
    urls, hosts = set(), set()

    def add(txt, url_mode):
        for line in txt.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if url_mode:
                urls.add(line.lower())
                p = urlsplit(line)
                if p.hostname:
                    hosts.add(p.hostname.lower())
            else:
                hosts.add(line.lower().lstrip("."))

    p = os.path.join(BL_DIR, "urlhaus_full.csv")
    if os.path.exists(p):
        for line in open(p, encoding="utf-8", errors="replace"):
            line = line.strip()
            if not line or line.startswith("#") or line.startswith('"'):
                parts = next(csv.reader([line]), [])
                if len(parts) > 4 and parts[4]:
                    u = parts[4].lower()
                    urls.add(u)
                    urls.add(u.split("?")[0])
                    h = urlsplit(u).hostname
                    if h:
                        hosts.add(h)
    p = os.path.join(BL_DIR, "openphish.txt")
    if os.path.exists(p):
        add(open(p, encoding="utf-8", errors="replace").read(), True)
    p = os.path.join(BL_DIR, "phishdom.txt")
    if os.path.exists(p):
        add(open(p, encoding="utf-8", errors="replace").read(), False)
    return urls, hosts


def reputacao(url, bl_urls, bl_hosts):
    host = (urlsplit(url).hostname or "").lower()
    partes = host.split(".")
    reg = ".".join(partes[-3:]) if partes[-2:] in (("co", "uk"), ("com", "br"), ("co", "za")) else (
        ".".join(partes[-2:]) if len(partes) >= 2 else host)
    dnsbl = []
    for zona in ("dbl.spamhaus.org",):
        try:
            out = subprocess.run(["dig", "+short", "%s.%s" % (reg, zona), "A"],
                                 capture_output=True, timeout=20).stdout.decode().strip()
            if out:
                dnsbl.append("%s=%s" % (zona, out))
        except Exception:
            pass
    url_bl = url.lower() in bl_urls or url.split("?")[0].lower() in bl_urls
    host_bl = host in bl_hosts or reg in bl_hosts
    return dict(host=host, url_bl=url_bl, host_bl=host_bl, dnsbl=dnsbl,
                clean=not (url_bl or host_bl or dnsbl))


def clamscan(caminhos):
    if not caminhos:
        return []
    env = dict(os.environ, LD_LIBRARY_PATH=CLAM_LIB)
    cmd = [CLAMSCAN, "-d", CLAM_DB, "--no-summary", "--infected", "--max-filesize=64M",
           "--max-scansize=256M", "-r", *caminhos]
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=1800, env=env)
    except Exception as e:
        return ["ERRO clamscan: %s" % e]
    return [l for l in p.stdout.decode(errors="replace").splitlines() if l.endswith("FOUND")]


def e_jpeg(dados):
    return len(dados) > 256 and dados[:2] == b"\xff\xd8" and dados[-2:] == b"\xff\xd9"


def testar_logo(url):
    r = dict(url=url, ok=False, motivo="")
    if "imgur.com" in url:
        r["motivo"] = "REPROVADO: host imgur.com nao permitido"
        return r
    try:
        resp = requests.get(url, headers=H, timeout=30)
    except Exception as e:
        r["motivo"] = "conexao %s" % type(e).__name__
        return r
    if resp.status_code != 200:
        r["motivo"] = "HTTP %d" % resp.status_code
        return r
    if not url.lower().split("?")[0].endswith(".jpg"):
        r["motivo"] = "URL nao termina em .jpg"
        return r
    if not e_jpeg(resp.content):
        r["motivo"] = "conteudo nao e JPEG valido"
        return r
    if len(resp.content) < 1500:
        r["motivo"] = "imagem pequena demais (%dB)" % len(resp.content)
        return r
    d = WORK / ("logo_" + re.sub(r"[^A-Za-z0-9]+", "_", url)[-40:] + ".jpg")
    d.parent.mkdir(parents=True, exist_ok=True)
    d.write_bytes(resp.content)
    r["arquivo"] = str(d)
    r["bytes"] = len(resp.content)
    r["ok"] = True
    r["motivo"] = "JPEG %d bytes" % len(resp.content)
    return r


def carregar_epg():
    """Baixa a fonte XMLTV e devolve {tvg_id: {datas com contagem}}."""
    print("  baixando EPG: %s" % EPG_URL)
    resp = requests.get(EPG_URL, headers=H, timeout=400, stream=True)
    resp.raise_for_status()
    d = zlib.decompressobj(16 + zlib.MAX_WBITS)
    xml = b""
    for pedaco in resp.iter_content(1 << 20):
        try:
            xml += d.decompress(pedaco)
        except Exception:
            pass
    resp.close()
    alvos = {c["tvg_id"] for c in CANDIDATOS}
    canais, dias = {}, {}
    for ev, el in ET.iterparse(io.BytesIO(xml), events=("end",)):
        if el.tag == "channel":
            cid = el.get("id") or ""
            if cid in alvos:
                nomes = [(n.text or "").strip() for n in el.iter("display-name")]
                canais[cid] = nomes
        elif el.tag == "programme":
            cid = el.get("channel")
            if cid in alvos:
                dias.setdefault(cid, {})
                dias[cid][el.get("start", "")[:8]] = dias[cid].get(el.get("start", "")[:8], 0) + 1
        el.clear()
    return canais, dias


def main():
    agora = datetime.now(timezone.utc)
    hoje = agora.strftime("%Y%m%d")
    amanha = (agora + timedelta(days=1)).strftime("%Y%m%d")
    depois = (agora + timedelta(days=2)).strftime("%Y%m%d")
    WORK.mkdir(parents=True, exist_ok=True)

    print("=" * 100)
    print("VERIFICACAO COMPLETA lista5.m3u - %s (UTC)" % agora.strftime("%Y-%m-%d %H:%M:%S"))
    print("Dias exigidos: hoje=%s  amanha=%s  depois=%s" % (hoje, amanha, depois))
    print("=" * 100)

    print("\n[1] Listas de malware/phishing + DNSBL")
    bl_urls, bl_hosts = carregar_blocklists()
    print("    %d URLs / %d hosts carregados" % (len(bl_urls), len(bl_hosts)))

    print("\n[2] Teste de transmissao (manifesto -> variante -> init -> segmento)")
    tarefas = []
    for c in CANDIDATOS:
        for i, u in enumerate(c["urls"]):
            tarefas.append((c["nome"], i, u, False))
    for nome, u in AVALIADOS_EXTRA:
        tarefas.append((nome, 0, u, True))

    def job(t):
        nome, i, u, extra = t
        destino = WORK / re.sub(r"[^A-Za-z0-9]+", "_", nome)[:48] / ("u%d" % i)
        r = verificar_stream(u, destino)
        r["nome"], r["idx"], r["extra"] = nome, i, extra
        return r

    with ThreadPoolExecutor(max_workers=6) as ex:
        stream_res = list(ex.map(job, tarefas))
    relatorio = []
    for r in stream_res:
        marca = "  %-30s u%d " % (r["nome"][:30], r["idx"])
        print("   %s %s | %s" % (("OK   " if r["ok"] else "FALHA"), marca, r["motivo"]))
        relatorio.append(r)

    print("\n[3] Anti-virus ClamAV 1.4.6 (assinaturas de hoje) nos bytes entregues")
    todos = sorted({str(p) for r in relatorio for p in r.get("arquivos", [])})
    print("    %d arquivos para escanear" % len(todos))
    inf = clamscan(todos)
    for i in inf:
        print("    INFECTADO: %s" % i)
    mapa_inf = set()
    for i in inf:
        mapa_inf.add(os.path.dirname(i.split(":")[0]))

    print("\n[4] Reputacao de URL/host")
    for r in relatorio:
        r["rep"] = reputacao(r["url"], bl_urls, bl_hosts)
        flag = "CLEAN" if r["rep"]["clean"] else "FLAGGED"
        det = ""
        if not r["rep"]["clean"]:
            det = " url_bl=%s host_bl=%s dnsbl=%s" % (r["rep"]["url_bl"], r["rep"]["host_bl"], r["rep"]["dnsbl"])
        print("   %-8s %-30s %s%s" % (flag, r["nome"][:30], r["rep"]["host"], det))

    print("\n[5] tvg-logo (tem de ser .jpg real, sem imgur)")
    logo_res = {}
    for c in CANDIDATOS:
        lr = testar_logo(c["logo"])
        logo_res[c["nome"]] = lr
        print("   %-6s %-22s %s" % ("OK" if lr["ok"] else "FALHA", c["nome"], lr["motivo"]))
    inf_logo = clamscan([v["arquivo"] for v in logo_res.values() if v.get("arquivo")])
    for i in inf_logo:
        print("    LOGO INFECTADO: %s" % i)

    print("\n[6] EPG: tvg-id presente + programme para hoje/amanha/depois de amanha")
    canais, dias = carregar_epg()
    epg_res = {}
    for c in CANDIDATOS:
        tid = c["tvg_id"]
        d = dias.get(tid, {})
        faltam = [x for x in (hoje, amanha, depois) if not d.get(x)]
        ok = tid in canais and not faltam
        epg_res[c["nome"]] = dict(tvg_id=tid, existe=tid in canais,
                                  nomes=canais.get(tid, []),
                                  hoje=d.get(hoje, 0), amanha=d.get(amanha, 0),
                                  depois=d.get(depois, 0),
                                  dias=sorted(d), ok=ok, faltam=faltam)
        print("   %-6s %-22s %-32s hoje=%-3s amanha=%-3s depois=%-3s %s"
              % ("OK" if ok else "FALHA", c["nome"], tid,
                 d.get(hoje, 0), d.get(amanha, 0), d.get(depois, 0),
                 "" if ok else "faltam " + ",".join(faltam)))

    print("\n[7] Veredito por canal")
    veredito = {}
    for c in CANDIDATOS:
        nome = c["nome"]
        meus = [r for r in relatorio if r["nome"] == nome and not r["extra"]]
        bons = [r for r in meus if r["ok"] and r["rep"]["clean"]
                and not any(r["url"] == i.split(":")[0] for i in inf)
                and not any(os.path.dirname(a) in mapa_inf for a in r.get("arquivos", []))]
        limpo = logo_res[nome]["ok"] and not any(nome in i for i in inf_logo)
        ok = bool(bons) and limpo and epg_res[nome]["ok"]
        veredito[nome] = dict(urls=[r["url"] for r in bons], epg=epg_res[nome],
                              logo=c["logo"], tvg_id=c["tvg_id"], grupo=c["grupo"],
                              nome=nome, ok=ok)
        print("   %-6s %-22s %d stream(s) ok | logo=%s | epg=%s"
              % ("OK" if ok else "FALHA", nome, len(bons), "ok" if limpo else "ruim",
                 "ok" if epg_res[nome]["ok"] else "ruim"))

    saida = dict(quando=agora.isoformat(), dias=dict(hoje=hoje, amanha=amanha, depois=depois),
                 streams=relatorio, logos=logo_res, epg=epg_res, veredito=veredito,
                 clamav_infected=inf, logo_infected=inf_logo)
    with open("/tmp/opencode/l5_verificacao.json", "w", encoding="utf-8") as f:
        json.dump(saida, f, indent=1, ensure_ascii=False, default=str)
    print("\nJSON: /tmp/opencode/l5_verificacao.json")
    return 0 if all(v["ok"] for v in veredito.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
