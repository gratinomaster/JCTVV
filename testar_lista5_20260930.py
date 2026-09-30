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
MAGIC = (b"ftyp", b"styp", b"moof", b"mdat", b"sidx", b"emsg", b"free", b"skip", b"wide")
TENTATIVAS = 3


def pares_token(q):
    return [x for x in (q or "").split("~") if "=" in x]


def inherit(base, child):
    """Resolve URL relativa preservando tokens ~token= do query (ex.: dssott)."""
    p = urlsplit(base)
    q = pares_token(p.query)
    frag = child.split("|")[0].split("#")[0].strip()
    full = urljoin(base, frag)
    if q:
        full = full.split("?")[0] + "?" + "~".join(q)
    return full


def parece_midia(b):
    """Diz se o corpo parece midia: MPEG-TS (0x47) ou ISO-BMFF (caixa size+4CC)."""
    if not b or len(b) < 8:
        return False
    if b[:1] == b"\x47":
        return True
    if any(k in b[:64] for k in MAGIC):
        return True
    # caixa ISO-BMFF generica: tamanho(4 bytes) + tipo(4 bytes ASCII)
    tam = int.from_bytes(b[:4], "big")
    return 8 <= tam <= 64 * 1024 * 1024 and b[4:8].isascii() and b[4:8].isalnum()


def pegar(url, timeout):
    """GET com retry exponencial curto. Retorna response ou None."""
    for i in range(TENTATIVAS):
        try:
            return requests.get(url, headers=H, timeout=timeout, stream=True)
        except Exception:
            if i == TENTATIVAS - 1:
                return None
            time.sleep(1.5 * (i + 1))
    return None


def testar(url):
    """Retorna (ok, motivo). Faz manifesto -> variante -> segmento (recursivo)."""
    motivo, corpo, prof = None, None, 0
    for _ in range(TENTATIVAS):
        try:
            r = requests.get(url, headers=H, timeout=TIMEOUT)
        except Exception as e:
            return False, "conexao %s" % type(e).__name__
        if r.status_code != 200:
            return False, "HTTP %d" % r.status_code

        if "#EXTM3U" not in r.text:
            if parece_midia(r.content):
                return True, "midia direta, %d bytes" % len(r.content)
            return False, "nao e M3U nem midia"
        if "#EXT-X-ENDLIST" in r.text:
            return False, "VOD/fim de lista (nao e live)"

        base, texto = url, r.text
        var = re.findall(r"#EXT-X-STREAM-INF:[^\n]*\n([^\n#]+)", texto)
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
            ir = pegar(inherit(base, mp.group(1)), TIMEOUT)
            if ir is None:
                return False, "init segment conexao"
            if ir.status_code != 200 or b"ftyp" not in ir.content[:64]:
                return False, "init segment invalido (%d)" % ir.status_code

        #usa o segmento MAIS RECENTE: em live o mais antigo ja pode ter expirado
        motivo, corpo, prof = None, None, 0
        rs = None
        for alvo in (segs[-1], segs[0]):
            rs = pegar(inherit(base, alvo), 40)
            if rs is None:
                motivo = "segmento conexao"
                continue
            corpo = next(rs.iter_content(262144), b"")
            st = rs.status_code
            rs.close()
            if st != 200:
                motivo = "segmento HTTP %d" % st
                continue
            if len(corpo) < 2048:
                motivo = "segmento curto (%dB)" % len(corpo)
                continue
            if not parece_midia(corpo):
                # CDN pode devolver outro manifesto em vez do segmento: desce um nivel
                if prof < 2 and b"#EXTM3U" in corpo[:64]:
                    url = inherit(base, alvo)
                    prof += 1
                    motivo = None
                    break
                motivo = "segmento nao e midia"
                continue
            return True, "%d variante(s), %d bytes" % (len(var), len(corpo))
        if prof and motivo is None and prof < 3:
            continue
        return False, motivo or "segmento invalido"
    return False, motivo or "falhou apos %d tentativas" % TENTATIVAS


def parse(linhas):
    """Extrai (extinf, url) preservando a ordem original."""
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
    return pares


def main():
    with open(PL, encoding="utf-8") as f:
        linhas = f.read().splitlines()
    header = linhas[0]
    pares = parse(linhas)
    print("Canais encontrados: %d" % len(pares))
    print("Testando em paralelo...")
    print("-" * 72)

    def job(i_par):
        i, (extinf, url) = i_par
        ok, motivo = testar(url)
        return i, extinf, url, ok, motivo

    with ThreadPoolExecutor(max_workers=8) as ex:
        resultados = sorted(ex.map(job, list(enumerate(pares))), key=lambda r: r[0])

    vivos, mortos = [], []
    for i, extinf, url, ok, motivo in resultados:
        nome = extinf.split(",")[-1].strip()[:34]
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

    rel = "relatorio_lista5_20260930.txt"
    with open(rel, "w", encoding="utf-8") as f:
        f.write("Teste lista5.m3u - %s\n" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        f.write("Total: %d | funcionando: %d | removidos: %d\n" % (len(pares), len(vivos), len(mortos)))
        f.write("\nREMOVIDOS:\n")
        for extinf, url in mortos:
            f.write("  - %s | %s\n" % (extinf.split(",")[-1].strip()[:60], url[:120]))
    print("Relatorio: %s" % rel)

    print("Total: %d | funcionando: %d | removidos: %d" % (len(pares), len(vivos), len(mortos)))
    if mortos:
        print("Removidos:")
        for extinf, url in mortos:
            print("  - %s" % extinf.split(",")[-1].strip()[:60])
    sys.exit(0)


if __name__ == "__main__":
    main()
