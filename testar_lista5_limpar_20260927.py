#!/usr/bin/env python3
"""Testa todos os canais do lista5.m3u e reescreve o arquivo sem os que nao funcionam.

Criterio de "funcionando":
  1. manifesto responde HTTP 200 e contem #EXTM3U
  2. se for master, pelo menos uma variante (#EXT-X-STREAM-INF) responde 200 e e M3U
  3. init segment (#EXT-X-MAP) baixado, quando houver
  4. pelo menos um segmento de midia baixado com magic TS/fMP4 e tamanho plausivel
"""
import os
import re
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin, urlsplit

import requests

PL = "lista5.m3u"
TS = int(time.time())
H = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
    "Accept": "*/*",
}
MAGIC = (b"\xff\xd8\xff", b"ftyp", b"styp", b"moof", b"mdat", b"sidx")


def pares():
    linhas = [l.rstrip("\n").rstrip("\r") for l in open(PL, encoding="utf-8") if l.strip()]
    cab, extinf, out = linhas[0], None, []
    for l in linhas[1:]:
        if l.startswith("#EXTINF"):
            extinf = l
        elif not l.startswith("#") and extinf is not None:
            out.append((extinf, l))
            extinf = None
    return cab, out


def herda(base, filho):
    """URLs dvt2= (Disney) carregam o token de auth no path: repassa para o filho."""
    p = urlsplit(base)
    q = [x for x in (p.query or "").split("~") if "=" in x]
    frag = filho.split("|")[0].split("#")[0]
    full = urljoin(base, frag)
    if q:
        full = full.split("?")[0] + "?" + "~".join(q)
    return full


def get(url, **kw):
    kw.setdefault("headers", H)
    kw.setdefault("timeout", 30)
    return requests.get(url, **kw)


def testa(url, tentativas=3):
    """Retorna (ok, motivo, detalhe)."""
    ultimo = ""
    for tent in range(tentativas):
        try:
            r = get(url)
            if r.status_code != 200:
                ultimo = "manifesto HTTP %d" % r.status_code
                time.sleep(1.5 * (tent + 1))
                continue
            txt = r.text
            if "#EXTM3U" not in txt:
                ultimo = "resposta nao e M3U"
                break

            base, texto = url, txt
            variantes = re.findall(r"#EXT-X-STREAM-INF:[^\n]*\n([^\n#]+)", txt)
            if variantes:
                ok_var = None
                for alvo in variantes:
                    child = herda(url, alvo.strip())
                    try:
                        rr = get(child)
                    except Exception as e:
                        ultimo = "variante erro %s" % type(e).__name__
                        continue
                    if rr.status_code == 200 and "#EXTM3U" in rr.text:
                        base, texto = child, rr.text
                        ok_var = alvo.strip().split("/")[-1]
                        break
                    ultimo = "variante HTTP %d" % rr.status_code
                if not ok_var:
                    return False, "nenhuma variante responde (%s)" % ultimo, variantes.__len__()

            segs = [l.strip() for l in texto.splitlines() if l.strip() and not l.startswith("#")]
            if not segs:
                ultimo = "stream sem segmentos"
                time.sleep(1.5 * (tent + 1))
                continue

            mp = re.search(r'#EXT-X-MAP:URI="([^"]+)"', texto)
            if mp:
                ir = get(herda(base, mp.group(1)))
                if ir.status_code != 200 or b"ftyp" not in ir.content[:64]:
                    ultimo = "init segment invalido (HTTP %d)" % ir.status_code
                    break

            rs = get(herda(base, segs[0]), stream=True)
            b = next(rs.iter_content(262144), b"")
            ct = rs.headers.get("content-type", "?")
            rs.close()
            magic = (b[:1] == b"\x47") or any(k in b[:64] for k in MAGIC)
            if rs.status_code != 200 or len(b) < 2048 or not magic:
                ultimo = "segmento invalido (HTTP %d, %d bytes, %s)" % (
                    rs.status_code, len(b), ct)
                time.sleep(1.5 * (tent + 1))
                continue

            det = "%d variante(s), init %s, seg %s %d bytes" % (
                len(variantes), "sim" if mp else "nao", ct.split(";")[0], len(b))
            return True, "OK", det
        except Exception as e:
            ultimo = "%s: %s" % (type(e).__name__, str(e)[:60])
            time.sleep(1.5 * (tent + 1))
    return False, ultimo, ""


def main():
    cab, entradas = pares()
    print("lista5.m3u: %d entradas\n" % len(entradas))

    # testa URLs unicas (varias entradas repetem a mesma URL)
    unicas = sorted({u for _, u in entradas})
    print("URLs distintas a testar: %d\n" % len(unicas))
    with ThreadPoolExecutor(max_workers=6) as ex:
        res = list(ex.map(lambda u: testa(u), unicas))
    mapa = dict(zip(unicas, res))

    print("%-3s %-9s %s" % ("#", "RESULTADO", "URL"))
    print("-" * 100)
    for i, (extinf, url) in enumerate(entradas, 1):
        ok, mot, det = mapa[url]
        print("%-3d %-9s %-47s %s" % (i, "FUNCIONA" if ok else "FORA",
                                      url.split("/")[-1][:47], det or mot))
    print("-" * 100)

    bons = [(e, u) for e, u in entradas if mapa[u][0]]
    ruins = [(e, u) for e, u in entradas if not mapa[u][0]]
    print("OK: %d entradas | fora: %d entradas (%d URLs distintas mortas)"
          % (len(bons), len(ruins), len({u for _, u in ruins})))

    if not bons:
        print("\nNENHUM canal funcionando: arquivo NAO foi alterado.")
        for u in sorted({u for _, u in ruins}):
            print("  -", mapa[u][1], u[:90])
        return 1

    bak = "%s.bak.limpar_%s" % (PL, time.strftime("%Y%m%d_%H%M%S", time.localtime(TS)))
    shutil.copy2(PL, bak)
    with open(PL, "w", encoding="utf-8", newline="\n") as f:
        f.write(cab + "\n")
        for extinf, url in bons:
            f.write(extinf + "\n" + url + "\n")
    print("\nBackup: %s" % bak)
    print("lista5.m3u reescrito: %d -> %d entradas" % (len(entradas), len(bons)))
    if ruins:
        print("\nRemovidos:")
        for u in sorted({u for _, u in ruins}):
            print("  -", mapa[u][1], u[:90])
    return 0


if __name__ == "__main__":
    sys.exit(main())
