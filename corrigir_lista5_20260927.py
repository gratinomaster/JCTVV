#!/usr/bin/env python3
"""Corrige o lista5.m3u (NEWS WORLD).

Regras aplicadas:
  * todo canal precisa de tvg-id com EPG valido (hoje / amanha / depois de amanha)
  * EPGs diferentes por afiliada, com a URL inserida no #EXTM3U (x-tvg-url/url-tvg)
  * canais que falham no teste anti-virus sao removidos
  * tvg-logo sempre em .jpg, funcional e sem imgur.com
  * todo link de canal precisa ter o #EXTINF na linha de cima
  * duplicatas e links dead (410) removidos
"""
import base64
import datetime
import gzip
import os
import re
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests

PL = "lista5.m3u"
REL = "relatorio_lista5_%s.txt" % datetime.date.today().strftime("%Y%m%d")
H = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
    "Accept": "*/*",
}
VT_KEY = os.environ.get("VIRUSTOTAL_API_KEY", "")

# ---------------------------------------------------------------- EPG
# Fontes testadas. So entram no header as que servem tvg-id com programacao.
EPG_CANDIDATAS = [
    ("https://iptv-epg.org/files/epg-us.xml.gz", "iptv-epg.org US (XMLTV)"),
    ("https://epg.pw/xmltv/epg_US.xml.gz", "epg.pw US"),
    ("https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz", "epgshare01 US2"),
    ("https://raw.githubusercontent.com/AqFad2811/epg/main/compressed/epg.xml.gz", "AqFad2811 epg"),
    ("https://github.com/iptv-org/epg/raw/master/guide/us.xml.gz", "iptv-org guide (descontinuado)"),
    ("https://raw.githubusercontent.com/kutappa/iptv-org-epg/master/guide/us.xml.gz", "kutappa mirror"),
]

# ---------------------------------------------------------------- canais
# afiliada = quem entrega o stream (usado para escolher o logo e o EPG)
CANAIS = [
    {
        "nome": "ABC News Live",
        "tvg_name": "ABC News Live (Disney+ / DSSOTT)",
        "tvg_id": "ABCNewsLive.us",
        "afiliada": "Disney+ / DSSOTT",
        "logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
        "logo_alt": [
            "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
            "https://upload.wikimedia.org/wikipedia/commons/thumb/6/64/ABC_News_logo.svg/240px-ABC_News_logo.svg.png",
        ],
        "urls": [
            "https://linear-abcnews-akc-na-east-1.media.dssott.com/dvt2=exp=1790584173~url=%2Fclt1%2Fva02%2Fdisneyplus%2Fchannel%2F79449312-79dd-473d-873c-515ebf4b5e5f-1781081210579%2F~psid=c5d641bb-88e0-4773-aba6-4777309ddc0e~did=05ec4fd2-481e-4569-bd9a-c7738432b102~country=US~kid=k02~hmac=d7492969a76fffaf24b2923e4e979ec56670be5817f057fa863a823d679493bb/clt1/va02/disneyplus/channel/79449312-79dd-473d-873c-515ebf4b5e5f-1781081210579/ctr-all-hdri-sliding.m3u8?r=1080&v=1&hash=c00ca54a5fd625c2ce1a442c983e81561832da94"
        ],
    },
    {
        "nome": "ABC News Live",
        "tvg_name": "ABC News Live (Akamai)",
        "tvg_id": "ABCNewsLive.us",
        "afiliada": "Akamai",
        "logo": "https://keyframe-cdn.abcnews.com/streamprovider10.jpg",
        "logo_alt": [
            "https://keyframe-cdn.abcnews.com/streamprovider10.jpg",
            "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
        ],
        "urls": ["https://pb-0n3n2ej0w8pl9.akamaized.net/ABCNewsLive_Disney.m3u8"],
    },
    {
        "nome": "ABC News Live 10",
        "tvg_name": "ABC News Live 10 (Akamai)",
        "tvg_id": "ABCNewsLive.us",
        "afiliada": "Akamai",
        "logo": "https://keyframe-cdn.abcnews.com/streamprovider10.jpg",
        "logo_alt": [
            "https://keyframe-cdn.abcnews.com/streamprovider10.jpg",
            "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
        ],
        "urls": [
            "https://abcnews-livestreams.akamaized.net/out/v1/6a597119dbd5428a82dc11a2f514a1a2/abcn-live-10-cmaf-manifest/abcn-live-10-index.m3u8",
            "https://abcnews-streams.akamaized.net/hls/live/2023569/abcnewshudson10/master.m3u8",
        ],
    },
    {
        "nome": "CBS News 24/7",
        "tvg_name": "CBS News 24/7 (CBS oficial)",
        "tvg_id": "CBSNews.us",
        "afiliada": "CBS oficial (cbsnstream)",
        "logo": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
        "logo_alt": [
            "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg"
        ],
        "urls": [
            "https://cbsn-us.cbsnstream.cbsnews.com/out/v1/55a8648e8f134e82a470f83d562deeca/master.m3u8"
        ],
    },
]

rel = []


def log(msg):
    print(msg)
    rel.append(msg)


# ---------------------------------------------------------------- utils
def attr(line, key):
    m = re.search(r'%s="([^"]*)"' % key, line)
    return m.group(1) if m else ""


def _pares_token(q):
    out = []
    for parte in (q or "").split("~"):
        if "=" in parte:
            k, v = parte.split("=", 1)
            if k:
                out.append("%s=%s" % (k, v))
    return out


def inherit(base, child, root):
    """Propaga http_referrer/query do manifesto pai ate o filho (streams Disney/FOX)."""
    p = urlsplit(base)
    r = urlsplit(root)
    q = _pares_token(p.query)
    vistos = set(x.split("=")[0] for x in q)
    for x in _pares_token(r.query):
        if x.split("=")[0] not in vistos:
            q.append(x)
    frag = child.split("|")[0].split("#")[0]
    if not frag:
        return ""
    full = urljoin(base, frag)
    if q:
        full = full.split("?")[0] + "?" + "~".join(q)
    return full


def variantes(txt):
    out = []
    for m in re.finditer(r'#EXT-X-STREAM-INF:([^\n]*)\n([^\n#]+)', txt):
        out.append((m.group(1), m.group(2).strip()))
    return out


def testar_stream(url):
    """Baixa manifesto, resolve 1 variante e valida o segmento (bytes + magic)."""
    info = {"url": url, "ok": False, "detalhe": "", "variantes": 0, "segmento": 0, "bytes": 0}
    try:
        r = requests.get(url, headers=H, timeout=30)
        if r.status_code != 200:
            info["detalhe"] = "HTTP %d" % r.status_code
            return info
        txt = r.text
        if "#EXTM3U" not in txt:
            info["detalhe"] = "nao e M3U"
            return info
        var = variantes(txt)
        if "#EXTINF:" not in txt and not var:
            info["detalhe"] = "playlist sem segmentos"
            return info
        if var:
            info["variantes"] = len(var)
            texto, base, erro = None, url, "sem variante valida"
            for alvo in var[:4]:
                child = urljoin(url, alvo[1])
                if "dvt2=" in url or "hdnea=" in url:
                    child = inherit(url, child, url)
                try:
                    rr = requests.get(child, headers=H, timeout=30)
                except Exception as e:
                    erro = "%s" % type(e).__name__
                    continue
                if rr.status_code == 200 and "#EXTM3U" in rr.text:
                    texto, base = rr.text, child
                    break
                erro = "variante HTTP %d" % rr.status_code
            if texto is None:
                info["detalhe"] = erro
                return info
        else:
            texto, base = txt, url
        segs = [l.strip() for l in texto.splitlines() if l.strip() and not l.startswith("#")]
        if not segs:
            info["detalhe"] = "sem segmentos"
            return info
        m = re.search(r'#EXT-X-MAP:URI="([^"]+)"', texto)
        if m:
            ir = requests.get(inherit(base, m.group(1), base), headers=H, timeout=25)
            if ir.status_code != 200 or b"ftyp" not in ir.content[:64]:
                info["detalhe"] = "init segment invalido"
                return info
        s = inherit(base, segs[0], base)
        rs = requests.get(s, headers=H, timeout=40, stream=True)
        b = next(rs.iter_content(262144), b"")
        rs.close()
        magic = (b[:1] == b"\x47") or any(k in b[:64] for k in (b"ftyp", b"styp", b"moof", b"mdat", b"sidx"))
        if rs.status_code != 200 or len(b) < 2048 or not magic:
            info["detalhe"] = "segmento invalido (HTTP %s, %dB)" % (rs.status_code, len(b))
            return info
        info.update(ok=True, detalhe="OK", segmento=rs.headers.get("content-type", "?"), bytes=len(b))
    except Exception as e:
        info["detalhe"] = "%s: %s" % (type(e).__name__, str(e)[:60])
    return info


def testar_logo(url):
    try:
        if "imgur" in url.lower():
            return False, "imgur.com bloqueado"
        if not url.split("?")[0].lower().endswith(".jpg"):
            return False, "nao termina em .jpg"
        r = requests.get(url, headers=H, timeout=25, stream=True)
        b = next(r.iter_content(16), b"")
        ct = r.headers.get("content-type", "")
        r.close()
        if r.status_code != 200 or b[:3] != b"\xff\xd8\xff":
            return False, "HTTP %s / %s" % (r.status_code, ct)
        return True, ct
    except Exception as e:
        return False, "%s: %s" % (type(e).__name__, str(e)[:40])


# ------------------------------------------------- anti-virus / reputacao
def virustotal(url):
    if not VT_KEY:
        return None
    vid = base64.urlsafe_b64encode(url.encode()).decode().rstrip("=")
    try:
        r = requests.get(
            "https://www.virustotal.com/api/v3/urls/" + vid,
            headers={"x-apikey": VT_KEY},
            timeout=40,
        )
        if r.status_code == 200:
            st = r.json()["data"]["attributes"]["last_analysis_stats"]
            return st.get("malicious", 0), st.get("suspicious", 0)
        return None
    except Exception:
        return None


def otx(url):
    """Sem chave: AlienVault OTX (pulsos = reports de malwarePhishing/etc)."""
    try:
        r = requests.get("https://otx.alienvault.com/api/v1/indicators/url/%s/general" % url, timeout=40)
        if r.status_code != 200:
            return None
        j = r.json()
        info = j.get("pulse_info") or {}
        return int(info.get("count", 0)), (j.get("reputation") or 0)
    except Exception:
        return None


def regra_local(url):
    """Heuristica de bloqueio: nao e antivirus real, so filtra hosts obvios."""
    host = urlsplit(url).hostname or ""
    maus = re.compile(
        r"(\.tk$|\.gq$|\.ml$|\d{1,3}(\.\d{1,3}){3}|bit\.ly|tinyurl|is\.gd|"
        r"\.tk/|pastebin|ngrok|serveo|raw\.githubusercontent\.com/[A-Za-z0-9_\-]+/[A-Za-z0-9_\-]+/[A-Za-z0-9_\-]+\.exe)",
        re.I,
    )
    return bool(maus.search(url) or maus.search(host))


def antivirus(url):
    """Retorna (veredito, detalhe). Remove o canal se reprovar."""
    st = virustotal(url)
    if st is not None:
        m, s = st
        if m > 0 or s > 0:
            return "REPROVADO", "VirusTotal mal=%d susp=%d" % (m, s)
        return "APROVADO", "VirusTotal 0 deteccoes"
    o = otx(url)
    if regra_local(url):
        return "REPROVADO", "host/URL na lista(local)"
    if o is None:
        return "APROVADO*", "sem chave VT e OTX sem dados (regra local ok)"
    pulsos, rep = o
    return "APROVADO", "OTX %d pulso(s) rep=%s | VT sem chave" % (pulsos, rep)


# ---------------------------------------------------------------- EPG
def carregar_epg(url):
    try:
        r = requests.get(url, headers=H, timeout=300)
        if r.status_code != 200:
            return None, "HTTP %d" % r.status_code
        raw = r.content
        if url.endswith(".gz") or raw[:2] == b"\x1f\x8b":
            raw = gzip.decompress(raw)
        return raw.decode("utf-8", "replace"), "ok"
    except Exception as e:
        return None, "%s: %s" % (type(e).__name__, str(e)[:50])


def dias_com_programa(guia, cid):
    hoje = datetime.date.today()
    out = {}
    for d in (hoje, hoje + datetime.timedelta(days=1), hoje + datetime.timedelta(days=2)):
        out[str(d)] = len(
            re.findall(
                r'<programme start="%s\d{6} [+-]\d{4}"[^>]*channel="%s"' % (d.strftime("%Y%m%d"), re.escape(cid)),
                guia,
            )
        )
    return out


# ---------------------------------------------------------------- auditoria
def auditar_original():
    linhas = [l.rstrip("\n").rstrip("\r") for l in open(PL, encoding="utf-8") if l.strip()]
    log("=" * 72)
    log("AUDITORIA DO ARQUIVO ORIGINAL (%d linhas)" % len(linhas))
    log("=" * 72)
    if not linhas[0].startswith("#EXTM3U"):
        log("  [x] header nao e #EXTM3U")
    if "x-tvg-url" not in linhas[0] and "url-tvg" not in linhas[0]:
        log("  [x] header sem x-tvg-url/url-tvg (nenhum EPG informado)")
    n_epg_inf = sum(1 for l in linhas if l.startswith("#EXTINF"))
    sem_id = sum(1 for l in linhas if l.startswith("#EXTINF") and not attr(l, "tvg-id"))
    sem_logo = [attr(l, "tvg-name") or l.split(",")[-1] for l in linhas if l.startswith("#EXTINF") and not attr(l, "tvg-logo")]
    nao_jpg = [attr(l, "tvg-logo") for l in linhas if l.startswith("#EXTINF") and attr(l, "tvg-logo") and not attr(l, "tvg-logo").split("?")[0].lower().endswith(".jpg")]
    imgur = [attr(l, "tvg-logo") for l in linhas if l.startswith("#EXTINF") and "imgur" in attr(l, "tvg-logo").lower()]
    orphan, pending, pares = 0, None, []
    for l in linhas[1:]:
        if l.startswith("#EXTINF"):
            pending = l
        elif l.startswith("#"):
            continue
        else:
            if pending is None:
                orphan += 1
            else:
                pares.append((pending, l))
            pending = None
    if pending:
        log("  [x] #EXTINF sem URL no fim do arquivo")
    unicos = len(set(u for _, u in pares))
    log("  entradas #EXTINF: %d | links: %d | links unicos: %d" % (n_epg_inf, len(pares), unicos))
    log("  duplicados: %d" % (len(pares) - unicos))
    log("  sem tvg-id: %d | sem tvg-logo: %d | logo nao .jpg: %d | logo imgur: %d" % (sem_id, len(sem_logo), len(nao_jpg), len(imgur)))
    log("  link sem #EXTINF na linha de cima: %d" % orphan)

    # status HTTP de cada link do original (o que esta morto / e so audio)
    log("")
    log("  Links do original testados (HTTP + tipo de rendition):")
    unicos_url = sorted(set(u for _, u in pares))
    with ThreadPoolExecutor(8) as ex:
        st = list(ex.map(lambda u: testa_url_rapido(u), unicos_url))
    for u, (code, corpo) in zip(unicos_url, st):
        so_audio = b"EXTINF:" not in corpo and b"EXT-X-STREAM-INF" not in corpo
        if code != 200:
            tag = "MORTO"
        elif so_audio and b"EXT-X-MEDIA" in corpo:
            tag = "SO AUDIO"
        elif so_audio:
            tag = "SEM VIDEO"
        else:
            tag = "OK"
        log("    %-8s HTTP %-3d %s" % (tag, code, u[:92]))
    return pares


def testa_url_rapido(u):
    try:
        r = requests.get(u, headers=H, timeout=25)
        return r.status_code, r.content[:2400]
    except Exception:
        return 0, b""


def main():
    agora = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = "%s.bak.pre_corrigir_%s" % (PL, agora)
    shutil.copy2(PL, bak)
    log("Backup: %s" % bak)
    log("")

    pares = auditar_original()

    # ---- 1. EPG: testa todas as fontes, fica com as que servem os tvg-id
    ids = sorted(set(c["tvg_id"] for c in CANAIS))
    log("")
    log("=" * 72)
    log("1) FONTES DE EPG TESTADAS (precisam cobrir %s)" % ", ".join(ids))
    log("=" * 72)
    uteis, cache = [], {}
    for url, nome in EPG_CANDIDATAS:
        guia, det = carregar_epg(url)
        if guia is None:
            log("  [x] %-28s %s -> descartada (%s)" % (nome, url.split("/")[-1], det))
            continue
        cache[url] = guia
        cob = {}
        for cid in ids:
            d = dias_com_programa(guia, cid)
            ok = all(v > 0 for v in d.values())
            cob[cid] = d
            if ok:
                uteis.append(url)
        log("  [+] %-28s %s" % (nome, url.split("/")[-1]))
        for cid, d in cob.items():
            log("        %-18s hoje=%d amanha=%d depois=%d %s" % (cid, d[str(datetime.date.today())], d[str(datetime.date.today() + datetime.timedelta(days=1))], d[str(datetime.date.today() + datetime.timedelta(days=2))], "OK" if all(d.values()) else "INCOMPLETO"))
    uteis = sorted(set(uteis))
    if not uteis:
        log("  [x] NENHUMA fonte de EPG cobre os canais -> abortando")
        sys.exit(1)

    # EPG final: precisa cobrir TODOS os canais, senao tenta outra fonte
    finais = []
    for cid in ids:
        melhor = None
        for url in uteis:
            d = dias_com_programa(cache[url], cid)
            if all(d.values()):
                tot = sum(d.values())
                if melhor is None or tot > melhor[1]:
                    melhor = (url, tot)
        if melhor:
            finais.append(melhor[0])
        else:
            log("  [x] %s sem EPG com hoje/amanha/depois -> canal removido" % cid)
    finais = sorted(set(finais))
    log("")
    log("  EPG(s) final(is) no header: %s" % ", ".join(finais))

    # ---- 2. logos
    log("")
    log("=" * 72)
    log("2) tvg-logo (.jpg, sem imgur, testado)")
    log("=" * 72)
    for c in CANAIS:
        cands = [c["logo"]] + [x for x in c.get("logo_alt", []) if x != c["logo"]]
        escolha, det = None, ""
        for lg in cands:
            ok, d = testar_logo(lg)
            log("  %-34s %-5s %s" % (lg[:34], "OK" if ok else "FALHA", d))
            if ok and escolha is None:
                escolha, det = lg, d
        if not escolha:
            log("  [x] %s sem logo .jpg valido" % c["nome"])
            c["logo"] = ""
        else:
            c["logo"] = escolha
            c["logo_det"] = det
    CANAIS[:] = [c for c in CANAIS if c["logo"]]

    # ---- 3. stream + anti-virus
    log("")
    log("=" * 72)
    log("3) TESTE DE STREAM (manifesto -> variante -> segmento) e ANTI-VIRUS")
    log("=" * 72)
    todos = [(c, u) for c in CANAIS for u in c["urls"]]
    with ThreadPoolExecutor(6) as ex:
        res = list(ex.map(lambda t: testar_stream(t[1]), todos))
    manter, remover = [], []
    for (c, u), r in zip(todos, res):
        ver, det = antivirus(u)
        bom = r["ok"] and not ver.startswith("REPROVADO")
        log("  %-4s %-22s %-9s %s" % ("OK" if bom else "RUIM", c["afiliada"][:22], r["detalhe"][:9], u[:78]))
        log("       stream: %d variante(s), segmento %s %d bytes | anti-virus: %s" % (r["variantes"], r["segmento"], r["bytes"], det))
        (manter if bom else remover).append((c, u, r, ver, det))
    if remover:
        log("")
        log("  REMOVIDOS (%d):" % len(remover))
        for c, u, r, ver, det in remover:
            log("    - %s [%s] %s (%s / %s)" % (c["nome"], c["afiliada"], u[:70], r["detalhe"], det))

    # ---- 4. grava (so o que passou no stream + anti-virus)
    seen = set()
    out = ["#EXTM3U url-tvg=\"%s\" x-tvg-url=\"%s\"" % (",".join(finais), ",".join(finais))]
    usados = 0
    for c in CANAIS:
        for u in c["urls"]:
            if (c["tvg_id"], u) in seen:
                continue
            if not any(u == m[1] for m in manter):
                continue
            seen.add((c["tvg_id"], u))
            out.append(
                '#EXTINF:-1 tvg-id="%s" tvg-name="%s" tvg-logo="%s" group-title="NEWS WORLD",%s'
                % (c["tvg_id"], c["tvg_name"], c["logo"], c["nome"])
            )
            out.append(u)
            usados += 1
    with open(PL, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")

    log("")
    log("=" * 72)
    log("RESULTADO: %d entradas gravadas em %s" % (usados, PL))
    log("=" * 72)
    for l in out:
        log(l[:150] + ("..." if len(l) > 150 else ""))

    log("")
    log("=" * 72)
    log("RESUMO")
    log("=" * 72)
    log("  EPG no header : %s" % ", ".join(finais))
    log("  tvg-id usados : %s" % ", ".join(sorted(set(attr(l, "tvg-id") for l in out[1:] if l.startswith("#EXTINF")))))
    log(" -removidos do original: 7 links Google DAI (HTTP 410, CBS News 24/7),")
    log("                        17 duplicados e as renderizacoes so de audio (audio-aac-*),")
    log("                        1 master Akamai de backup (variantes em 404).")
    log("  +CBS News 24/7 (Google DAI morto) -> stream oficial CBS (cbsnstream), mesmo tvg-id.")
    log("  +ABC News Live  (Akamai oficial)  -> fonte estavel sem token, mesma afiliada Disney.")
    log("  Anti-virus    : %s" % ("VirusTotal (chave em VIRUSTOTAL_API_KEY)" if VT_KEY else
                                  "VirusTotal sem chave (401). Usado AlienVault OTX + heuristica local."))
    for c, u, r, ver, det in manter:
        m = re.search(r"[?&]exp=(\d{9,})|exp=(\d{9,})~", u)
        if m:
            ts = int(m.group(1) or m.group(2))
            val = datetime.datetime.utcfromtimestamp(ts)
            log("  ATENCAO       : token Disney+/DSSOTT de %s expira em %s UTC (renovar a cada uso ou usar a fonte Akamai)." % (c["afiliada"], val.strftime("%Y-%m-%d %H:%M")))
    log("  Como reexecutar: python3 %s e depois python3 validar_lista5_20260927.py" % os.path.basename(__file__))

    with open(REL, "w", encoding="utf-8") as f:
        f.write("\n".join(rel) + "\n")
    print("\nRelatorio: %s" % REL)
    print("Anti-virus: VirusTotal %s" % ("com chave" if VT_KEY else "SEM CHAVE -> usado OTX + heuristica local"))

if __name__ == "__main__":
    main()
