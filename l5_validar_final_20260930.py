#!/usr/bin/env python3
"""
Validacao final, independente, do lista5.m3u ja gravado.

Reabre o arquivo do zero e confere cada exigencia do prompt:
  1. estrutura M3U: toda URL tem #EXTINF imediatamente na linha de cima;
  2. tvg-logo: existe, termina em .jpg, nao e imgur.com e devolve JPEG valido;
  3. EPG: url-tvg/x-tvg-url presente, tvg-id existe na fonte e tem programme
     para hoje, amanha e depois de amanha;
  4. stream: manifesto -> variante -> init -> segmento com midia de verdade;
  5. anti-virus ClamAV 1.4.6 nos bytes servidos;
  6. sem URLs duplicadas.
"""
import os
import re
import subprocess
import sys
import zlib
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests

PL = "lista5.m3u"
WORK = Path("/tmp/opencode/avscan/final")
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36", "Accept": "*/*"}
CLAMSCAN = "/tmp/opencode/avscan/usr/local/bin/clamscan"
CLAM_LIB = "/tmp/opencode/avscan/usr/local/lib"
CLAM_DB = "/tmp/opencode/avscan/db"
MAGIC = (b"ftyp", b"styp", b"moof", b"mdat", b"sidx", b"emsg", b"free", b"skip", b"wide")
falhas = []


def err(msg):
    falhas.append(msg)
    print("   FALHA  %s" % msg)


def attr(linha, chave):
    m = re.search(r'%s="([^"]*)"' % re.escape(chave), linha)
    return m.group(1) if m else ""


def parse():
    with open(PL, encoding="utf-8") as f:
        linhas = [l.rstrip("\n") for l in f]
    if not linhas or linhas[0].strip() != "#EXTM3U" and not linhas[0].startswith("#EXTM3U"):
        err("primeira linha nao e #EXTM3U")
    cabecalho = linhas[0]
    entradas, i = [], 1
    while i < len(linhas):
        l = linhas[i]
        if l.startswith("#EXTINF:"):
            if i + 1 >= len(linhas) or not re.match(r"^\w+://", linhas[i + 1]):
                err("#EXTINF na linha %d sem URL valida na linha de baixo" % (i + 1))
                i += 1
                continue
            entradas.append((l, linhas[i + 1]))
            i += 2
            continue
        if l.strip() and not l.startswith("#"):
            err("URL na linha %d sem #EXTINF na linha de cima: %s" % (i + 1, l[:70]))
        i += 1
    return cabecalho, entradas


def herdar(base, child):
    """Resolve URL relativa do manifesto preservando tokens ~token= do query."""
    tokens = [x for x in (urlsplit(base).query or "").split("~") if "=" in x]
    full = urljoin(base, child.split("|")[0].split("#")[0].strip())
    if tokens:
        full = full.split("?")[0] + "?" + "~".join(tokens)
    return full


def testar_stream(url, dest):
    arqs = []
    r = requests.get(url, headers=H, timeout=30)
    if r.status_code != 200 or "#EXTM3U" not in r.text:
        return False, "manifesto HTTP %d" % r.status_code, arqs
    if "#EXT-X-ENDLIST" in r.text:
        return False, "VOD, nao e live", arqs
    dest.mkdir(parents=True, exist_ok=True)
    p = dest / "playlist.m3u8"
    p.write_bytes(r.content)
    arqs.append(p)
    base, txt = url, r.text
    vars_ = re.findall(r"#EXT-X-STREAM-INF:[^\n]*\n([^\n#]+)", txt)
    for v in vars_[:5]:
        child = herdar(url, v)
        try:
            rr = requests.get(child, headers=H, timeout=30)
        except Exception:
            continue
        if rr.status_code == 200 and "#EXTM3U" in rr.text:
            base, txt = child, rr.text
            p2 = dest / "variante.m3u8"
            p2.write_bytes(rr.content)
            arqs.append(p2)
            break
    mp = re.search(r'#EXT-X-MAP:URI="([^"]+)"', txt)
    if mp:
        ri = requests.get(herdar(base, mp.group(1)), headers=H, timeout=30)
        if ri.status_code == 200 and b"ftyp" in ri.content[:64]:
            p3 = dest / "init.m4s"
            p3.write_bytes(ri.content)
            arqs.append(p3)
        else:
            return False, "init segment invalido", arqs
    segs = [l.strip() for l in txt.splitlines() if l.strip() and not l.startswith("#")]
    mid = 0
    for i, s in enumerate(reversed(segs[-2:])):
        try:
            rs = requests.get(herdar(base, s), headers=H, timeout=45, stream=True)
        except Exception:
            continue
        corpo = next(rs.iter_content(512 * 1024), b"")
        rs.close()
        bom = (corpo[:1] == b"\x47") or any(k in corpo[:64] for k in MAGIC) or (
            8 <= int.from_bytes(corpo[:4], "big") <= 64 << 20 and corpo[4:8].isascii()
            and corpo[4:8].isalnum())
        if bom and len(corpo) > 2048:
            p4 = dest / ("seg%d%s" % (i, ".ts" if corpo[:1] == b"\x47" else ".m4s"))
            p4.write_bytes(corpo)
            arqs.append(p4)
            mid += len(corpo)
    if not mid:
        return False, "nenhum segmento de midia", arqs
    return True, "%d bytes de midia" % mid, arqs


def main():
    agora = datetime.now(timezone.utc)
    dias = [agora.strftime("%Y%m%d"),
            (agora + timedelta(days=1)).strftime("%Y%m%d"),
            (agora + timedelta(days=2)).strftime("%Y%m%d")]
    WORK.mkdir(parents=True, exist_ok=True)
    print("=" * 96)
    print("VALIDACAO FINAL %s - %s (UTC)" % (PL, agora.strftime("%Y-%m-%d %H:%M:%S")))
    print("Dias exigidos: %s" % " / ".join(dias))
    print("=" * 96)

    print("\n[1] Estrutura")
    cabecalho, entradas = parse()
    epgs_cab = attr(cabecalho, "x-tvg-url")
    print("   #EXTM3U ok | x-tvg-url=%s" % epgs_cab)
    if not epgs_cab:
        err("x-tvg-url ausente no cabecalho")
    print("   %d entradas, todas com #EXTINF na linha de cima" % len(entradas))

    print("\n[2] Duplicatas")
    urls = [u for _, u in entradas]
    if len(urls) != len(set(urls)):
        err("existem URLs duplicadas")
    else:
        print("   nenhuma URL repetida")

    print("\n[3] tvg-logo")
    logos = set()
    for extinf, _ in entradas:
        lg = attr(extinf, "tvg-logo")
        nome = extinf.split(",")[-1]
        if not lg:
            err("%s sem tvg-logo" % nome)
            continue
        if "imgur.com" in lg:
            err("%s usa imgur.com" % nome)
        if not lg.split("?")[0].lower().endswith(".jpg"):
            err("%s tvg-logo nao termina em .jpg: %s" % (nome, lg[-40:]))
        logos.add(lg)
    for lg in sorted(logos):
        try:
            r = requests.get(lg, headers=H, timeout=30)
            jpg = r.status_code == 200 and r.content[:2] == b"\xff\xd8" and r.content[-2:] == b"\xff\xd9"
            print("   %-6s %-70s %dB" % ("OK" if jpg else "FALHA", lg[:70], len(r.content)))
            if not jpg:
                err("logo nao entrega JPEG: %s" % lg)
        except Exception as e:
            err("logo %s falhou: %s" % (lg[:60], type(e).__name__))

    print("\n[4] EPG (tvg-id x hoje / amanha / depois de amanha)")
    ids = {attr(e, "tvg-id") for e, _ in entradas}
    for i in ids:
        if not i:
            err("entrada sem tvg-id")
    epgs = {attr(e, "url-tvg") for e, _ in entradas} | {epgs_cab}
    for u in epgs:
        r = requests.get(u, headers=H, timeout=200, stream=True)
        d = zlib.decompressobj(16 + zlib.MAX_WBITS)
        xml = b""
        for c in r.iter_content(1 << 20):
            try:
                xml += d.decompress(c)
            except Exception:
                pass
        print("   fonte %s -> HTTP %d, %d bytes XML" % (u[:64], r.status_code, len(xml)))
        for tid in sorted(ids):
            existe = ('id="%s"' % tid).encode() in xml
            cont = {dia: len(re.findall(rb'<programme channel="%s" start="%s' % (
                re.escape(tid).encode(), dia.encode()), xml)) for dia in dias}
            ok = existe and all(cont[d] > 0 for d in dias)
            print("      %-6s %-30s hoje=%-3d amanha=%-3d depois=%-3d"
                  % ("OK" if ok else "FALHA", tid, cont[dias[0]], cont[dias[1]], cont[dias[2]]))
            if not ok:
                err("EPG de %s incompleto (existe=%s)" % (tid, existe))

    print("\n[5] Stream + [6] anti-virus ClamAV")
    def job(t):
        i, (extinf, url) = t
        return i, extinf, url, testar_stream(url, WORK / ("c%d" % i))
    with ThreadPoolExecutor(max_workers=5) as ex:
        res = list(ex.map(job, list(enumerate(entradas))))
    todos = []
    for i, extinf, url, (ok, motivo, arqs) in res:
        nome = extinf.split(",")[-1]
        print("   %-6s %-26s %s" % ("OK" if ok else "FALHA", nome, motivo))
        if not ok:
            err("stream de %s: %s" % (nome, motivo))
        todos += [str(a) for a in arqs]
    env = dict(os.environ, LD_LIBRARY_PATH=CLAM_LIB)
    p = subprocess.run([CLAMSCAN, "-d", CLAM_DB, "--no-summary", "--infected",
                        "--max-filesize=64M", "--max-scansize=512M", "-r", *todos],
                       capture_output=True, timeout=1800, env=env)
    inf = [l for l in p.stdout.decode(errors="replace").splitlines() if l.endswith("FOUND")]
    print("   ClamAV: %d arquivo(s) varrido(s) -> %d-infecao(oes)" % (len(todos), len(inf)))
    for i in inf:
        err("infectado: %s" % i)

    print("\n" + "=" * 96)
    if falhas:
        print("RESULTADO: %d FALHA(S)" % len(falhas))
        for f in falhas:
            print("  - %s" % f)
    else:
        print("RESULTADO: TUDO OK - %d canais/entradas, todos com EPG valido, "
              "logo .jpg, stream no ar e limpos no ClamAV" % len(entradas))
    print("=" * 96)
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
