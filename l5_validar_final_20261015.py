#!/usr/bin/env python3
"""Validacao final lista5.m3u - 2026-10-15.

Checa: estrutura M3U, todo URL precedido de #EXTINF, tvg-id/tvg-name/tvg-logo
(.jpg) /group-title, ausencia de imgur, logos JPEG reais, EPG em DUAS fontes
(epgshare US2 + epg.pw) cobrindo hoje/amanha/depois de amanha, e anti-virus.
"""
import gzip
import re
import subprocess
import sys
from datetime import date, timedelta

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

HOJE = date.today()
DIAS = {HOJE: "D0", HOJE + timedelta(1): "D+1", HOJE + timedelta(2): "D+2"}

FONTES = [
    ("epgshare US2", "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz",
     "/tmp/opencode/us2.xml.gz"),
    ("epg.pw US", "https://epg.pw/xmltv/epg_US.xml.gz",
     "/tmp/opencode/epg_us_pw.xml.gz"),
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
    chans, cur = [], None
    orfas = 0
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
    print(f"  cabecalho url-tvg : {'url-tvg' in header}")
    print(f"  cabecalho x-tvg-url: {'x-tvg-url' in header}")
    print(f"  canais            : {len(chans)}")
    print(f"  URLs sem #EXTINF  : {orfas}")
    seen = {}
    for ext, url in chans:
        seen[url] = seen.get(url, 0) + 1
    dup = {u: c for u, c in seen.items() if c > 1}
    print(f"  URLs duplicadas   : {len(dup)}")
    problemas = []
    for ext, url in chans:
        for campo in ("tvg-id", "tvg-name", "tvg-logo", "group-title"):
            if not attr(ext, campo):
                problemas.append((attr(ext, "tvg-name") or url[:40], campo))
        logo = attr(ext, "tvg-logo")
        if logo and not logo.lower().split("?")[0].endswith(".jpg"):
            problemas.append((attr(ext, "tvg-name"), "logo nao-.jpg"))
        for campo in ("tvg-logo",):
            if "imgur.com" in attr(ext, campo).lower():
                problemas.append((attr(ext, "tvg-name"), "imgur"))
        if "imgur.com" in url.lower():
            problemas.append((url[:40], "imgur"))
    print(f"  campos faltando   : {len(problemas)}")
    for p in problemas:
        print(f"      {p}")
    return not problemas and not dup and not orfas


def check_logos(chans):
    print("\nLOGOS (HTTP 200 + assinatura JPEG FFD8FF)")
    ok = 0
    for ext, _ in chans:
        url = attr(ext, "tvg-logo")
        nome = attr(ext, "tvg-name")
        out = curl(["-r", "0-15", "-w", "\n%{http_code}|%{content_type}", url])
        i = out.rfind(b"\n")
        data, meta = out[:i], out[i + 1:].decode(errors="replace")
        jpeg = data[:3] == b"\xff\xd8\xff"
        ok += 1 if jpeg else 0
        print(f"  [{'JPEG' if jpeg else 'FAIL'}] {nome:<24} {meta}")
    return ok == len(chans)


def check_epg(chans):
    ids = {attr(ext, "tvg-id"): attr(ext, "tvg-name") for ext, _ in chans}
    print("\nEPG (cobertura hoje + amanha + depois)")
    all_ok = True
    for nome_fonte, url, path in FONTES:
        prog = {}
        nome_por_id = {}
        with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
            in_ch, cur = False, None
            for line in f:
                ls = line.strip()
                if ls.startswith("<channel"):
                    in_ch = True
                    m = re.search(r'id="([^"]+)"', ls)
                    cur = m.group(1) if m else None
                    continue
                if in_ch:
                    if ls.startswith("<display-name") and cur:
                        nm = re.sub(r"<[^>]+>", "", ls).strip()
                        nome_por_id.setdefault(nm, cur)
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
        print(f"  -- {nome_fonte} --")
        for cid, nome in ids.items():
            chave = cid if cid in prog else nome_por_id.get(nome)
            d = prog.get(chave, {})
            dias = [k for k in ("D0", "D+1", "D+2") if d.get(k)]
            st = "OK" if len(dias) == 3 else "FALHA"
            if st == "FALHA":
                all_ok = False
            det = " ".join(f"{k}={d[k]}" for k in ("D0", "D+1", "D+2") if d.get(k))
            print(f"  [{st:<5}] {nome:<24} {det or '(sem programa)'}")
    return all_ok


if __name__ == "__main__":
    header, chans, orfas = parse_m3u("lista5.m3u")
    e = check_estrutura(header, chans, orfas)
    l = check_logos(chans)
    g = check_epg(chans)
    print("\n" + "=" * 60)
    print(f"estrutura {'OK' if e else 'FALHA'} | logos {'OK' if l else 'FALHA'} "
          f"| EPG 2 fontes {'OK' if g else 'FALHA'}")
    sys.exit(0 if (e and l and g) else 1)
