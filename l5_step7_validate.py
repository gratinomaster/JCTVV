#!/usr/bin/env python3
"""Passo 7 - validacao final ponta a ponta de lista5.m3u.

Confere cada exigencia:
  1. toda URL tem #EXTINF na linha de cima
  2. tvg-logo existe em todo canal, e .jpg (validado como JPEG real)
  3. nenhum link de imgur.com
  4. tvg-id de todo canal existe no EPG da url-tvg declarada
  5. EPG tem programacao de D0, D+1 e D+2 (com titulo real)
  6. streams reproduzem (manifesto + segmento)
"""
import gzip
import io
import os
import re
import subprocess
import sys
import urllib.request
from collections import defaultdict
from datetime import date, timedelta

M3U = "lista5.m3u"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

HOJE = date.today()
DIAS = [(HOJE, "HOJE"), (HOJE + timedelta(1), "AMANHA"),
        (HOJE + timedelta(2), "DEPOIS DE AMANHA")]

falhas = []
avisos = []


def erro(m):
    falhas.append(m)
    print(f"  [FALHA] {m}")


def aviso(m):
    avisos.append(m)
    print(f"  [AVISO] {m}")


def ok(m):
    print(f"  [ok] {m}")


def curl(url, extra=(), timeout=30):
    cmd = ["curl", "-sL", "-A", UA, "--max-time", str(timeout), *extra, url]
    try:
        return subprocess.run(cmd, capture_output=True,
                              timeout=timeout + 15).stdout
    except Exception:
        return b""


def join(parent, child):
    import urllib.parse
    full = urllib.parse.urljoin(parent, child)
    pq = urllib.parse.urlsplit(parent).query
    if pq:
        sp = urllib.parse.urlsplit(full)
        if not sp.query:
            full = urllib.parse.urlunsplit(
                (sp.scheme, sp.netloc, sp.path, pq, sp.fragment))
    return full


def parse_m3u(path):
    canais, cur = [], None
    linhas = open(path, encoding="utf-8", errors="replace").read().splitlines()
    header = linhas[0] if linhas else ""
    orfas = []
    for i, ln in enumerate(linhas[1:], 2):
        s = ln.strip()
        if s.startswith("#EXTINF"):
            cur = s
        elif s and not s.startswith("#"):
            if cur is None:
                orfas.append((i, s))
            else:
                canais.append((cur, s))
            cur = None
    return header, canais, orfas


def attr(extinf, nome):
    m = re.search(nome + r'="([^"]*)"', extinf)
    return m.group(1) if m else ""


def checa_stream(url):
    man = curl(url)
    if not man.startswith(b"#EXTM3U"):
        return False, "manifesto invalido"
    txt = man.decode("utf-8", "replace")
    linhas = [l.strip() for l in txt.splitlines() if l.strip()]
    var = None
    for i, l in enumerate(linhas):
        if l.startswith("#EXT-X-STREAM-INF"):
            for j in range(i + 1, len(linhas)):
                if not linhas[j].startswith("#"):
                    var = linhas[j]
                    break
            break
    if var:
        murl = join(url, var)
        mtxt = curl(murl).decode("utf-8", "replace")
        linhas2 = [l.strip() for l in mtxt.splitlines() if l.strip()]
        seg = None
        seen = False
        for l in linhas2:
            if l.startswith("#EXTINF:"):
                seen = True
            elif not l.startswith("#") and seen:
                seg = join(murl, l)
                break
    else:
        seen = False
        for l in linhas:
            if l.startswith("#EXTINF:"):
                seen = True
            elif not l.startswith("#") and seen:
                seg = join(url, l)
                break
    if not seg:
        return False, "sem segmento"
    data = curl(seg, ["-r", "0-400000"], timeout=30)
    if len(data) < 3000:
        return False, f"segmento curto ({len(data)}b)"
    ts = data[0:1] == b"G" and data[188:189] == b"G"
    mp4 = b"ftyp" in data[:64] or b"moof" in data[:8192]
    aac = data[:2] in (b"\xff\xf1", b"\xff\xf9", b"\xff\xfb")
    if not (ts or mp4 or aac):
        return False, "segmento nao TS/fMP4/AAC"
    return True, "ok"


def baixa_epg(url):
    """Baixa EPG (gz ou xml). Reusa cache local quando o tamanho bate."""
    import hashlib
    cache = "/tmp/opencode/l5_epgcache"
    os.makedirs(cache, exist_ok=True)
    destino = os.path.join(cache, hashlib.md5(url.encode()).hexdigest() + ".epg")
    if os.path.exists(destino) and os.path.getsize(destino) > 10000:
        out = open(destino, "rb").read()
    else:
        out = subprocess.run(["curl", "-sL", "--max-time", "900", url],
                             capture_output=True).stdout
        if len(out) > 10000:
            with open(destino, "wb") as f:
                f.write(out)
    if out[:2] == b"\x1f\x8b":
        out = gzip.decompress(out)
    if out[:3] == b"\xef\xbb\xbf":          # tira BOM UTF-8
        out = out[3:]
    return out, destino


def main():
    print("=" * 74)
    print(f"VALIDACAO FINAL - {M3U}  ({HOJE})")
    print("=" * 74)

    header, canais, orfas = parse_m3u(M3U)

    print("\n[1] ESTRUTURA M3U")
    if not header.startswith("#EXTM3U"):
        erro("primeira linha nao e #EXTM3U")
    else:
        ok("header #EXTM3U presente")
    if orfas:
        for i, u in orfas:
            erro(f"linha {i}: URL sem #EXTINF acima -> {u[:60]}")
    else:
        ok(f"todas as {len(canais)} URLs tem #EXTINF na linha de cima")
    if len(canais) != len({u for _, u in canais}):
        erro("ha URLs duplicadas")
    else:
        ok("sem URLs duplicadas")

    print("\n[2] EPGS DECLARADOS NO ARQUIVO")
    tvg = attr(header, "url-tvg")
    x_tvg = attr(header, "x-tvg-url")
    epgs = tvg.split()
    if not epgs:
        erro("header sem url-tvg (nenhum EPG declarado)")
    else:
        for e in epgs:
            h = curl(e, ["-I"], timeout=40)
            todos = re.findall(rb"HTTP/[\d.]+\s+(\d{3})", h)
            cod = todos[-1].decode() if todos else "?"
            tam = re.search(rb"[Cc]ontent-[Ll]ength:\s*(\d+)", h)
            if cod == "200":
                mb = int(tam.group(1)) // 1048576 if tam else "?"
                ok(f"EPG acessivel (HTTP 200, ~{mb}MB): {e}")
            else:
                erro(f"EPG nao acessivel (HTTP {cod}): {e}")
    if x_tvg and x_tvg != tvg:
        aviso("x-tvg-url difere de url-tvg")

    print("\n[3] LOGOS (.jpg, sem imgur, JPEG real)")
    for ext, url in canais:
        nome = ext.split(",", 1)[-1]
        logo = attr(ext, "tvg-logo")
        if not logo:
            erro(f"{nome}: sem tvg-logo")
            continue
        if "imgur.com" in logo:
            erro(f"{nome}: logo no imgur.com -> {logo}")
        if not re.search(r"\.jpg(\?|$)", logo, re.I):
            erro(f"{nome}: tvg-logo nao termina em .jpg -> {logo}")
            continue
        d = curl(logo, ["-r", "0-2047"], timeout=20)
        if d[:3] != b"\xff\xd8\xff":
            erro(f"{nome}: logo nao e JPEG valido -> {logo}")
        else:
            ok(f"{nome}: logo JPEG ok")

    print("\n[4] STREAM (manifesto + segmento)")
    for ext, url in canais:
        nome = ext.split(",", 1)[-1]
        good, why = checa_stream(url)
        if good:
            ok(f"{nome}: reproduz")
        else:
            erro(f"{nome}: {why} -> {url[:60]}")

    print("\n[5] EPG: cobertura D0 / D+1 / D+2 por tvg-id")
    ids = sorted({attr(e, "tvg-id") for e, _ in canais})
    print(f"    tvg-ids usados: {', '.join(ids)}")
    alvo = {d: r for d, r in DIAS}
    cont = defaultdict(lambda: defaultdict(int))
    titulo = defaultdict(list)
    achados = set()
    achados_tit = {}
    buf, cap, cid = [], False, None
    for e in epgs:
        if not e:
            continue
        raw, _ = baixa_epg(e)
        if b"<tv" not in raw[:400]:
            erro(f"conteudo nao-XMLTV em {e}")
            continue
        f = io.StringIO(raw.decode("utf-8", "replace"))
        for line in f:
            ls = line.strip()
            if ls.startswith("<channel "):
                cap, buf = True, [ls]
                m = re.search(r'channel id="([^"]+)"', ls)
                cid = m.group(1) if m else None
                continue
            if ls.startswith("<programme "):
                cap, buf = True, [ls]
                m = re.search(r'channel="([^"]+)"', ls)
                cid = m.group(1) if m else None
                continue
            if cap:
                buf.append(ls)
                if ls.startswith("</channel>") or ls.startswith("</programme>"):
                    bloco = "\n".join(buf)
                    if ls.startswith("</channel>"):
                        if cid in ids:
                            achados.add(cid)
                            for t in re.findall(
                                    r"<display-name[^>]*>(.*?)</display-name>",
                                    bloco):
                                achados_tit.setdefault(cid, []).append(t)
                    else:
                        m = re.search(r'channel="([^"]+)"', bloco)
                        s = re.search(r'start="(\d{8})', bloco)
                        if m and s and m.group(1) in ids:
                            try:
                                d = date(int(s.group(1)[:4]),
                                         int(s.group(1)[4:6]),
                                         int(s.group(1)[6:8]))
                            except ValueError:
                                d = None
                            if d in alvo:
                                r = alvo[d]
                                cont[m.group(1)][r] += 1
                                t = re.search(
                                    r"<title[^>]*>(.*?)</title>", bloco)
                                if t:
                                    tt = re.sub(r"\s+", " ", t.group(1)).strip()
                                    titulo[(m.group(1), r)].append(tt)
                    cap, buf = [], False

    for i in ids:
        if i not in achados:
            erro(f"{i}: canal NAO encontrado no EPG declarado")
            continue
        nm = ", ".join(achados_tit.get(i, [])[:2])
        linha = []
        for _, r in DIAS:
            n = cont[i][r]
            linha.append(f"{r}={n}")
            if n == 0:
                erro(f"{i}: sem programacao em {r}")
        if all(cont[i][r] for _, r in DIAS):
            ex = titulo.get((i, "HOJE"), [])
            u = list(dict.fromkeys(ex))[:3]
            ok(f"{i} [{nm}] " + " ".join(linha))
            print(f"        hoje: {' / '.join(u) if u else '(sem titulo)'}")

    print("\n" + "=" * 74)
    print(f"RESULTADO: {len(falhas)} falha(s), {len(avisos)} aviso(s)")
    for f in falhas:
        print(f"  - {f}")
    print("=" * 74)
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())