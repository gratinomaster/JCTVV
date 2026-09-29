#!/usr/bin/env python3
"""Testa todos os canais do lista5.m3u e reescreve o arquivo sem os mortos."""
import re
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from urllib.parse import urljoin, urlsplit

import requests

H = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
    "Accept": "*/*",
}
PL = "lista5.m3u"
TIMEOUT = 25


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


def testar(url):
    """Retorna (ok, motivo). Faz manifesto -> variante -> segmento."""
    try:
        r = requests.get(url, headers=H, timeout=TIMEOUT)
    except Exception as e:
        return False, "conexao %s" % type(e).__name__
    if r.status_code != 200:
        return False, "HTTP %d" % r.status_code
    txt = r.text
    if "#EXTM3U" not in txt:
        return False, "nao e M3U"
    if "#EXT-X-ENDLIST" in txt:
        return False, "VOD/fim de lista (nao e live)"

    base, texto = url, txt
    var = re.findall(r"#EXT-X-STREAM-INF:[^\n]*\n([^\n#]+)", txt)
    if var:
        achou = False
        for alvo in var[:4]:
            child = inherit(url, alvo.strip())
            try:
                rr = requests.get(child, headers=H, timeout=TIMEOUT)
            except Exception:
                continue
            if rr.status_code == 200 and "#EXTM3U" in rr.text:
                base, texto, achou = child, rr.text, True
                break
        if not achou:
            return False, "nenhuma variante responde"

    segs = [l.strip() for l in texto.splitlines() if l.strip() and not l.startswith("#")]
    if not segs:
        return False, "sem segmentos"

    mp = re.search(r'#EXT-X-MAP:URI="([^"]+)"', texto)
    if mp:
        try:
            ir = requests.get(inherit(base, mp.group(1)), headers=H, timeout=TIMEOUT)
        except Exception as e:
            return False, "init segment %s" % type(e).__name__
        if ir.status_code != 200 or b"ftyp" not in ir.content[:64]:
            return False, "init segment invalido (%d)" % ir.status_code

    try:
        rs = requests.get(inherit(base, segs[0]), headers=H, timeout=40, stream=True)
        b = next(rs.iter_content(262144), b"")
        st = rs.status_code
        rs.close()
    except Exception as e:
        return False, "segmento %s" % type(e).__name__
    magic = (b[:1] == b"\x47") or any(k in b[:64] for k in (b"ftyp", b"styp", b"moof", b"mdat", b"sidx"))
    if st != 200:
        return False, "segmento HTTP %d" % st
    if len(b) < 2048:
        return False, "segmento curto (%dB)" % len(b)
    if not magic:
        return False, "segmento nao e midia"
    return True, "%d variante(s), %d bytes" % (len(var), len(b))


def main():
    with open(PL, encoding="utf-8") as f:
        linhas = f.read().splitlines()
    header = linhas[0]
    pares, pending = [], None
    for l in linhas[1:]:
        if not l.strip():
            continue
        if l.startswith("#EXTINF"):
            pending = l
        elif l.startswith("#"):
            continue
        elif pending is not None:
            pares.append((pending, l))
            pending = None
    print("Canais encontrados: %d" % len(pares))
    print("Testando em paralelo...")
    print("-" * 72)

    def job(i_par):
        i, (extinf, url) = i_par
        nome = extinf.split(",")[-1].strip()[:34]
        ok, motivo = testar(url)
        return i, extinf, url, ok, motivo, nome

    with ThreadPoolExecutor(max_workers=8) as ex:
        resultados = list(ex.map(job, list(enumerate(pares))))

    vivos, mortos = [], []
    for i, extinf, url, ok, motivo, nome in resultados:
        if ok:
            print("  OK    %-36s %s" % (nome, motivo))
            vivos.append((extinf, url))
        else:
            print("  FALHA %-36s %s" % (nome, motivo))
            mortos.append((extinf, url))

    bak = "%s.bak.%s" % (PL, datetime.now().strftime("%Y%m%d_%H%M%S"))
    shutil.copy2(PL, bak)
    print("-" * 72)
    print("Backup: %s" % bak)

    with open(PL, "w", encoding="utf-8") as f:
        f.write(header + "\n")
        for extinf, url in vivos:
            f.write(extinf + "\n" + url + "\n")

    print("Total: %d | functioning: %d | removidos: %d" % (len(pares), len(vivos), len(mortos)))
    if mortos:
        print("Removidos:")
        for extinf, url in mortos:
            print("  - %s" % extinf.split(",")[-1].strip()[:60])
    sys.exit(0)


if __name__ == "__main__":
    main()
