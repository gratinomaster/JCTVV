#!/usr/bin/env python3
"""Validacao final lista5.m3u - 2026-10-18.

Checa: estrutura M3U (todo URL precedido de #EXTINF, tvg-id/tvg-name/
tvg-logo .jpg/group-title, sem duplicatas, sem imgur), streams (manifest ->
variante -> segmento real), logos (HTTP 200 + JPEG), EPG nas DUAS fontes do
url-tvg cobrindo hoje/amanha/depois de amanha, e anti-virus (motor local +
reputacao de URL no Google Safe Browsing via Transparency Report).
"""
import gzip
import json
import re
import subprocess
import sys
from datetime import date, timedelta

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

HOJE = date.today()
DIAS = {HOJE: "D0", HOJE + timedelta(1): "D+1", HOJE + timedelta(2): "D+2"}

# (nome, url remota, cache local)
FONTES = [
    ("epgshare US2 (primario)", "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz",
     "/tmp/opencode/99c63b46.gz"),
    ("epg.pw US (backup)", "https://epg.pw/xmltv/epg_US.xml.gz",
     "/tmp/opencode/c0c2144c.gz"),
]


def curl(args, timeout=30):
    try:
        p = subprocess.run(["curl", "-sL", "-A", UA, "--max-time", str(timeout),
                            *args], capture_output=True, timeout=timeout + 10)
        return p.stdout
    except Exception:
        return b""


def parse_m3u(path):
    txt = open(path, encoding="utf-8", errors="replace").read()
    header = txt.splitlines()[0]
    chans, cur, orfas = [], None, 0
    for ln in txt.splitlines()[1:]:
        s = ln.strip()
        if not s:
            continue
        if s.startswith("#EXTINF"):
            cur = s
        elif s.startswith("#"):
            continue
        else:
            if cur is None:
                orfas += 1
            chans.append((cur or "", s))
            cur = None
    return header, chans, orfas


def attr(ext, nome):
    m = re.search(nome + r'="([^"]*)"', ext)
    return m.group(1) if m else ""


def check_estrutura(header, chans, orfas):
    print("ESTRUTURA")
    probs = []
    if "url-tvg" not in header:
        probs.append("cabecalho sem url-tvg")
    if "x-tvg-url" not in header:
        probs.append("cabecalho sem x-tvg-url")
    print(f"  url-tvg/x-tvg-url no #EXTM3U : {'url-tvg' in header} / {'x-tvg-url' in header}")
    print(f"  fontes EPG no cabecalho      : {header.count('https://')}")
    print(f"  canais                       : {len(chans)}")
    print(f"  URLs sem #EXTINF acima       : {orfas}")
    if orfas:
        probs.append(f"{orfas} URL orfa")
    vistos = {}
    for ext, url in chans:
        vistos[url] = vistos.get(url, 0) + 1
    dups = [u for u, c in vistos.items() if c > 1]
    print(f"  URLs duplicadas              : {len(dups)}")
    probs += [f"url duplicada {u[:60]}" for u in dups]
    for ext, url in chans:
        nome = attr(ext, "tvg-name") or url[:40]
        for campo in ("tvg-id", "tvg-name", "tvg-logo", "group-title"):
            if not attr(ext, campo):
                probs.append(f"{nome}: sem {campo}")
        logo = attr(ext, "tvg-logo")
        if logo and not logo.lower().split("?")[0].endswith(".jpg"):
            probs.append(f"{nome}: logo nao-.jpg ({logo})")
        if "imgur.com" in (ext + url).lower():
            probs.append(f"{nome}: imgur")
        if not url.lower().startswith("https://"):
            probs.append(f"{nome}: url nao-https")
    print(f"  problemas                    : {len(probs)}")
    for p in probs:
        print(f"      !! {p}")
    return not probs


def check_streams(chans):
    print("\nSTREAMS (manifest -> variante -> segmento real)")
    ok_all = True
    for ext, url in chans:
        nome = attr(ext, "tvg-name")
        body = curl([url]).decode("utf-8", "replace")
        if not body.startswith("#EXTM3U"):
            print(f"  [FAIL] {nome}: manifesto invalido")
            ok_all = False
            continue
        alvo = url
        if "#EXT-X-STREAM-INF" in body:
            linhas = [l.strip() for l in body.splitlines() if l.strip()]
            for i, l in enumerate(linhas):
                if l.startswith("#EXT-X-STREAM-INF"):
                    for j in range(i + 1, len(linhas)):
                        if not linhas[j].startswith("#"):
                            alvo = _join(url, linhas[j])
                            break
                    break
            vb = curl([alvo]).decode("utf-8", "replace")
        else:
            vb = body
        seg = None
        for l in [x.strip() for x in vb.splitlines() if x.strip()]:
            if not l.startswith("#"):
                seg = _join(alvo, l)
                break
        if not seg:
            print(f"  [FAIL] {nome}: sem segmento")
            ok_all = False
            continue
        data = curl(["-r", "0-900000", seg])
        ts_ok = len(data) >= 376 and data[0:1] == b"G" and data[188:189] == b"G"
        mp4 = b"ftyp" in data[:64] or b"moof" in data[:64] or b"styp" in data[:64]
        st = "OK  " if len(data) > 2000 and (ts_ok or mp4) else "FAIL"
        if st == "FAIL":
            ok_all = False
        tipo = "MPEG-TS" if ts_ok else ("fMP4" if mp4 else "desconhecido")
        print(f"  [{st}] {nome:<24} segmento {len(data):>7}B {tipo}")
    return ok_all


def _join(parent, child):
    import urllib.parse
    full = urllib.parse.urljoin(parent, child)
    pq = urllib.parse.urlsplit(parent).query
    if pq:
        sp = urllib.parse.urlsplit(full)
        if not sp.query:
            full = urllib.parse.urlunsplit((sp.scheme, sp.netloc, sp.path,
                                             pq, sp.fragment))
    return full


def check_logos(chans):
    print("\nLOGOS (HTTP 200 + content-type image/jpeg + magic FFD8FF)")
    ok = True
    for ext, _ in chans:
        url = attr(ext, "tvg-logo")
        nome = attr(ext, "tvg-name")
        out = curl(["-r", "0-15", "-w", "\n%{http_code}|%{content_type}", url])
        i = out.rfind(b"\n")
        data, meta = out[:i], out[i + 1:].decode(errors="replace")
        code, ctype = (meta.split("|") + [""])[:2]
        jpeg = data[:3] == b"\xff\xd8\xff"
        good = code in ("200", "206") and "jpeg" in ctype and jpeg
        ok &= good
        print(f"  [{'OK  ' if good else 'FAIL'}] {nome:<24} http={code} {ctype} jpeg={jpeg}")
    return ok


def check_epg(chans, header):
    print("\nEPG (fontes do url-tvg - cobertura D0/D+1/D+2)")
    urls_hdr = re.search(r'url-tvg="([^"]+)"', header)
    urls_hdr = urls_hdr.group(1).split(",") if urls_hdr else []
    alvos = [(attr(e, "tvg-id"), attr(e, "tvg-name")) for e, _ in chans]
    ok_all = True
    for nome_fonte, url_remota, path in FONTES:
        print(f"  -- {nome_fonte} --")
        print(f"     {url_remota}")
        if url_remota not in urls_hdr:
            print("     !! fonte nao listada no cabecalho")
            ok_all = False
        rem = curl(["-r", "0-3", "-w", "|%{http_code}", url_remota], timeout=40)
        p = rem.rfind(b"|")
        http = rem[p + 1:].decode() if p >= 0 else "?"
        gzip_ok = rem[:2] == b"\x1f\x8b"
        if http in ("200", "206") and gzip_ok:
            print(f"     remota: HTTP {http} + gzip valido")
        else:
            print(f"     !! remota http={http} gzip={gzip_ok}")
            ok_all = False
        try:
            with open(path, "rb") as f:
                gzip_MAGIC = f.read(2) == b"\x1f\x8b"
            if not gzip_MAGIC:
                print("     !! cache local nao e gzip")
                continue
        except FileNotFoundError:
            print("     !! cache local ausente")
            ok_all = False
            continue
        nome_por_id, prog = {}, {}
        with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
            in_ch, cid = False, None
            for line in f:
                ls = line.strip()
                if ls.startswith("<channel"):
                    in_ch = True
                    cid = None
                    m = re.search(r'id="([^"]+)"', ls)
                    if m:
                        cid = m.group(1)
                    continue
                if in_ch:
                    if ls.startswith("<display-name") and cid:
                        nm = re.sub(r"<[^>]+>", "", ls).strip()
                        nome_por_id.setdefault(nm, cid)
                    elif ls.startswith("</channel"):
                        in_ch = False
                    continue
                if not ls.startswith("<programme"):
                    continue
                m = re.search(r'channel="([^"]+)"', ls)
                s = re.search(r'start="(\d{8})', ls)
                if not (m and s):
                    continue
                try:
                    d = date(int(s.group(1)[:4]), int(s.group(1)[4:6]),
                             int(s.group(1)[6:8]))
                except ValueError:
                    continue
                if d in DIAS:
                    prog.setdefault(m.group(1), {}).setdefault(DIAS[d], 0)
                    prog[m.group(1)][DIAS[d]] += 1
        for tvg_id, tvg_name in alvos:
            chave = tvg_id if tvg_id in prog else nome_por_id.get(tvg_name)
            p = prog.get(chave, {})
            dias = [k for k in ("D0", "D+1", "D+2") if p.get(k)]
            st = "OK  " if len(dias) == 3 else "FAIL"
            if st == "FAIL":
                ok_all = False
            det = " ".join(f"{k}={p[k]}" for k in ("D0", "D+1", "D+2") if p.get(k))
            print(f"     [{st}] {tvg_name:<26} id={chave} {det or '(sem programa)'}")
    return ok_all


def sb_status(site):
    out = curl(["--max-time", "15",
                f"https://transparencyreport.google.com/transparencyreport/api/v3/safebrowsing/status?site={site}"],
               timeout=20).decode("utf-8", "replace")
    m = re.search(r"\)\]\}'\s*\n\s*(\[.*\])", out, re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(1))
        return {"status": d[0][1], "ameacas": d[0][2:7]}
    except Exception:
        return None


def check_av(chans):
    print("\nANTI-VIRUS (Google Safe Browsing/Transparency Report - sem API key)")
    alvos = set()
    for ext, url in chans:
        alvos.add(url)
        alvos.add(attr(ext, "tvg-logo"))
    ok_all = True
    for u in sorted(alvos):
        alvo = re.match(r"https?://([^/]+)", u).group(1)
        r = sb_status(alvo)
        if r is None:
            print(f"  [AVISO] {alvo}: sem resposta")
            continue
        malo = any(r["ameacas"]) or r["status"] == 3
        st = "REPROVADO" if malo else "APROVADO"
        if malo:
            ok_all = False
        print(f"  [{st}] {alvo:<48} status={r['status']} ameacas={r['ameacas']}")
    return ok_all


if __name__ == "__main__":
    header, chans, orfas = parse_m3u("lista5.m3u")
    e = check_estrutura(header, chans, orfas)
    s = check_streams(chans)
    l = check_logos(chans)
    g = check_epg(chans, header)
    a = check_av(chans)
    print("\n" + "=" * 64)
    print(f"estrutura {'OK' if e else 'FALHA'} | streams {'OK' if s else 'FALHA'} | "
          f"logos {'OK' if l else 'FALHA'} | EPG {'OK' if g else 'FALHA'} | "
          f"anti-virus {'OK' if a else 'FALHA'}")
    sys.exit(0 if all((e, s, l, g, a)) else 1)
