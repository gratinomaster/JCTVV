#!/usr/bin/env python3
"""Validacao independente do lista5.m3u gerado (nao usa o script que gravou)."""
import datetime
import gzip
import re
import sys
from urllib.parse import urljoin, urlsplit

import requests

H = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
    "Accept": "*/*",
}
PL = "lista5.m3u"
linhas = [l.rstrip("\n").rstrip("\r") for l in open(PL, encoding="utf-8") if l.strip()]
fail = []


def a(line, k):
    m = re.search(r'%s="([^"]*)"' % k, line)
    return m.group(1) if m else ""


def pares_token(q):
    return [x for x in (q or "").split("~") if "=" in x]


def inherit(base, child):
    p = urlsplit(base)
    q = pares_token(p.query)
    frag = child.split("|")[0].split("#")[0]
    full = urljoin(base, frag)
    if q:
        full = full.split("?")[0] + "?" + "~".join(q)
    return full


# 1. estrutura ----------------------------------------------------------
hdr = linhas[0]
if not hdr.startswith("#EXTM3U"):
    fail.append("header nao comeca com #EXTM3U")
epg_urls = [u for u in (a(hdr, "x-tvg-url") + "," + a(hdr, "url-tvg")).split(",") if u]
if not epg_urls:
    fail.append("sem x-tvg-url/url-tvg no header")
pares, pending = [], None
for l in linhas[1:]:
    if l.startswith("#EXTINF"):
        if pending:
            fail.append("#EXTINF sem URL antes de outro #EXTINF")
        pending = l
    elif l.startswith("#"):
        fail.append("linha inesperada: " + l[:40])
    else:
        if pending is None:
            fail.append("URL sem #EXTINF na linha de cima: " + l[:60])
        else:
            pares.append((pending, l))
        pending = None
if pending:
    fail.append("#EXTINF sem URL no fim do arquivo")
urls = [u for _, u in pares]
if len(urls) != len(set(urls)):
    fail.append("URLs duplicadas")
print("Estrutura: %d entradas, %d EPG(s) no header, %d tvg-id distintos"
      % (len(pares), len(epg_urls), len(set(a(e, "tvg-id") for e, _ in pares))))

# 2. tvg-id, logo .jpg, sem imgur, respondendo ---------------------------
for extinf, url in pares:
    nome = a(extinf, "tvg-name") or extinf.split(",")[-1]
    if not a(extinf, "tvg-id"):
        fail.append("sem tvg-id: " + nome)
    lg = a(extinf, "tvg-logo")
    if not lg:
        fail.append("sem tvg-logo: " + nome)
        continue
    if "imgur" in lg.lower():
        fail.append("logo imgur: " + lg)
    if not lg.split("?")[0].lower().endswith(".jpg"):
        fail.append("logo nao .jpg: " + lg)
    try:
        r = requests.get(lg, headers=H, timeout=25, stream=True)
        b = next(r.iter_content(16), b"")
        ct = r.headers.get("content-type", "")
        r.close()
        if r.status_code != 200 or b[:3] != b"\xff\xd8\xff":
            fail.append("logo invalido (%s %s): %s" % (r.status_code, ct, lg))
        else:
            print("  LOGO OK  %-34s %s" % (lg.split("/")[-1][:34], ct))
    except Exception as e:
        fail.append("logo erro %s: %s" % (type(e).__name__, lg))

# 3. EPG: 200 + gzip + tvg-id com guia hoje/amanha/depois ----------------
guia = ""
for src in epg_urls:
    try:
        r = requests.get(src, headers=H, timeout=300)
        if r.status_code != 200:
            fail.append("EPG HTTP %d: %s" % (r.status_code, src))
            continue
        raw = r.content
        if src.endswith(".gz") or raw[:2] == b"\x1f\x8b":
            raw = gzip.decompress(raw)
        txt = raw.decode("utf-8", "replace")
        if "<tv" not in txt[:2000]:
            fail.append("EPG sem header XMLTV: " + src)
            continue
        print("  EPG OK   %s (%.1f MB, %d canais, %d programas)"
              % (src, len(raw) / 1048576.0, txt.count("<channel "), txt.count("<programme ")))
        guia = txt if len(txt) > len(guia) else guia
    except Exception as e:
        fail.append("EPG erro %s: %s" % (type(e).__name__, src))

hoje = datetime.date.today()
dias = [hoje, hoje + datetime.timedelta(days=1), hoje + datetime.timedelta(days=2)]
for cid in sorted(set(a(e, "tvg-id") for e, _ in pares)):
    if not guia:
        fail.append("sem EPG carregado para validar " + cid)
        continue
    if ('<channel id="%s"' % cid) not in guia:
        fail.append("tvg-id %s nao existe no EPG" % cid)
        continue
    tot = []
    for d in dias:
        n = len(re.findall(r'<programme start="%s\d{6} [+-]\d{4}"[^>]*channel="%s"'
                           % (d.strftime("%Y%m%d"), re.escape(cid)), guia))
        tot.append(n)
        if n == 0:
            fail.append("tvg-id %s sem programacao em %s" % (cid, d))
    print("  EPG %-16s hoje=%-3d amanha=%-3d depois=%-3d %s"
          % (cid, tot[0], tot[1], tot[2], "OK" if all(tot) else "FALHA"))

# 4. stream: manifesto -> variante -> segmento ---------------------------
for extinf, url in pares:
    nome = a(extinf, "tvg-name") or extinf.split(",")[-1]
    try:
        r = requests.get(url, headers=H, timeout=30)
        if r.status_code != 200:
            fail.append("stream HTTP %d: %s" % (r.status_code, nome))
            continue
        txt = r.text
        if "#EXTM3U" not in txt:
            fail.append("stream nao e M3U: " + nome)
            continue
        var = re.findall(r'#EXT-X-STREAM-INF:[^\n]*\n([^\n#]+)', txt)
        base, texto = url, txt
        if var:
            for alvo in var[:4]:
                child = urljoin(url, alvo.strip())
                if "dvt2=" in url:
                    child = inherit(url, child)
                rr = requests.get(child, headers=H, timeout=30)
                if rr.status_code == 200 and "#EXTM3U" in rr.text:
                    base, texto = child, rr.text
                    break
            else:
                fail.append("nenhuma variante responde: " + nome)
                continue
        segs = [l.strip() for l in texto.splitlines() if l.strip() and not l.startswith("#")]
        if not segs:
            fail.append("stream sem segmentos: " + nome)
            continue
        mp = re.search(r'#EXT-X-MAP:URI="([^"]+)"', texto)
        if mp:
            ir = requests.get(inherit(base, mp.group(1)), headers=H, timeout=25)
            if ir.status_code != 200 or b"ftyp" not in ir.content[:64]:
                fail.append("init segment invalido: " + nome)
                continue
        rs = requests.get(inherit(base, segs[0]), headers=H, timeout=40, stream=True)
        b = next(rs.iter_content(262144), b"")
        ct = rs.headers.get("content-type", "?")
        rs.close()
        magic = (b[:1] == b"\x47") or any(k in b[:64] for k in (b"ftyp", b"styp", b"moof", b"mdat", b"sidx"))
        if rs.status_code != 200 or len(b) < 2048 or not magic:
            fail.append("segmento invalido (%s %dB): %s" % (rs.status_code, len(b), nome))
        else:
            print("  STREAM %-32s %d variante(s), segmento %s %d bytes OK"
                  % (nome[:32], len(var), ct, len(b)))
    except Exception as e:
        fail.append("stream erro %s em %s" % (type(e).__name__, nome))

print("=" * 68)
if fail:
    print("FALHAS (%d):" % len(fail))
    for f in fail:
        print(" -", f)
    sys.exit(1)
print("TUDO OK: %d canais | EPG com hoje/amanha/depois | logo .jpg | stream testado" % len(pares))
