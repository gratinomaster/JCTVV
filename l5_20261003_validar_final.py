#!/usr/bin/env python3
"""Validacao final do lista5.m3u contra todos os requisitos do prompt.txt."""
import gzip
import re
import subprocess
import sys
import urllib.parse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

sys.path.insert(0, ".")
from l5_20261003_test_streams import probe          # noqa: E402
from l5_20261003_testar_logos import check as logo_check   # noqa: E402

ARQ = sys.argv[1] if len(sys.argv) > 1 else "lista5.m3u"
HOJE = date.today()
DIAS = {HOJE: "D0", HOJE + timedelta(1): "D+1", HOJE + timedelta(2): "D+2"}

fails = []


def ok(cond, msg):
    print(("  [OK ] " if cond else "  [FALHA] ") + msg)
    if not cond:
        fails.append(msg)
    return cond


def parse(path):
    header, canais, meta = None, [], None
    for ln in open(path, encoding="utf-8", errors="replace"):
        s = ln.strip()
        if not s:
            continue
        if s.startswith("#EXTM3U"):
            header = s
        elif s.startswith("#EXTINF"):
            meta = s
        elif s.startswith("#"):
            continue
        else:
            canais.append((meta, s))
            meta = None
    return header, canais


def attr(line, key):
    m = re.search(key + r'="([^"]*)"', line or "")
    return m.group(1) if m else ""


def name(line):
    return (line or "").rsplit(",", 1)[-1]


def epg_ids():
    d = defaultdict(lambda: defaultdict(int))
    urls = ["https://iptv-epg.org/files/epg-us.xml.gz",
            "https://epg.pw/xmltv/epg_US.xml.gz"]
    for url in urls:
        try:
            p = subprocess.run(["curl", "-sL", "--max-time", "300", url],
                               capture_output=True, timeout=330)
            import io
            with gzip.open(io.BytesIO(p.stdout), "rt", encoding="utf-8",
                           errors="replace") as f:
                for line in f:
                    ls = line.strip()
                    if ls.startswith("<programme "):
                        c = re.search(r'channel="([^"]+)"', ls)
                        s = re.search(r'start="(\d{8})', ls)
                        if c and s:
                            try:
                                dt = date(int(s.group(1)[:4]),
                                          int(s.group(1)[4:6]),
                                          int(s.group(1)[6:8]))
                            except ValueError:
                                continue
                            if dt in DIAS:
                                d[(url, c.group(1))][DIAS[dt]] += 1
        except Exception as e:
            print(f"  [ERRO] baixando {url}: {e}")
    return d


print("=" * 74)
print(f"VALIDACAO FINAL - {ARQ}")
print("=" * 74)

header, canais = parse(ARQ)

print("\n1) ESTRUTURA / SINTAXE")
ok(bool(header) and header.startswith("#EXTM3U"), "primeira linha e #EXTM3U")
ok(header is not None and "url-tvg=" in header, "cabecalho tem url-tvg")
ok(header is not None and "x-tvg-url=" in header, "cabecalho tem x-tvg-url (fallback)")
ok(len(canais) > 0, f"ha canais ({len(canais)})")
sem_hash = [u for m, u in canais if not (m or "").startswith("#EXTINF")]
ok(not sem_hash, f"toda URL tem #EXTINF na linha de cima (orfas={len(sem_hash)})")
dups = [u for u in {u for _, u in canais}
        if [x for _, x in canais].count(u) > 1]
ok(not dups, f"sem URLs duplicadas (dup={len(dups)})")
ok(all(m and "group-title=" in m for m, _ in canais), "todas com group-title")
ok(all(name(m) for m, _ in canais), "todas com nome de exibicao")

print("\n2) tvg-id / tvg-name")
ok(all(attr(m, "tvg-id") for m, _ in canais), "todas com tvg-id")
ok(all(attr(m, "tvg-name") for m, _ in canais), "todas com tvg-name")
ids = [attr(m, "tvg-id") for m, _ in canais]
ok(len(set(ids)) == len(ids), f"tvg-id unicos ({len(set(ids))}/{len(ids)})")

print("\n3) LOGOS (.jpg, sem imgur, HTTP 200 + JPEG real)")
logos = [attr(m, "tvg-logo") for m, _ in canais]
ok(all(l.endswith(".jpg") for l in logos), "todas as tvg-logo terminam em .jpg")
ok(not any("imgur.com" in l.lower() for l in logos), "nenhum logo em imgur.com")
with ThreadPoolExecutor(max_workers=6) as ex:
    lres = list(ex.map(logo_check, logos))
for (m, _u), r in zip(canais, lres):
    ok(r["ok"], f"logo {attr(m,'tvg-id')}: {r.get('http')} {r.get('bytes')}b "
                f"{r.get('ctype')} {r.get('erro','')}")

print("\n4) ANTI-VIRUS + STREAM (video+audio)")
with ThreadPoolExecutor(max_workers=3) as ex:
    sres = list(ex.map(probe, [u for _, u in canais]))
for (m, u), r in zip(canais, sres):
    ok(r.get("ok") and r.get("tipo") == "VIDEO+AUDIO",
       f"stream {attr(m,'tvg-id')}: tipo={r.get('tipo')} "
       f"formato={r.get('formato')} seg={r.get('seg_bytes')}b "
       f"{r.get('erro','')}")
try:
    av = subprocess.run(
        ["python3", "l5_step5_antivirus.py", ARQ], capture_output=True,
        text=True, timeout=900)
    print("\n   " + av.stdout.strip().replace("\n", "\n   "))
    ok("LIMPO" in av.stdout and "0 rejeitadas" in av.stdout,
       "todos os streams limpos no anti-virus")
except Exception as e:
    ok(False, f"anti-virus: {e}")

print("\n5) EPG: URL acessivel + programming D0/D+1/D+2 por tvg-id")
for u in re.findall(r'url-tvg="([^"]+)"', header or "")[0].split():
    r = subprocess.run(["curl", "-sIL", "-o", "/dev/null", "-w", "%{http_code}",
                        "--max-time", "60", u], capture_output=True, text=True)
    ok(r.stdout.strip() == "200",
       f"EPG acessivel {r.stdout.strip()} (seguindo redirects): {u}")

print("   (baixando EPGs para conferir a grade...)")
grade = epg_ids()
for i in ids:
    melhor = None
    for (url, cid), dias in grade.items():
        if cid == i and len(dias) == 3:
            melhor = (url, cid, dias)
            break
    if melhor:
        url, cid, dias = melhor
        ok(True, f"{i}: D0={dias['D0']} D+1={dias['D+1']} D+2={dias['D+2']} "
                 f"programas ({url.rsplit('/',1)[-1]})")
    else:
        achou = [(c, d) for (_, c), d in grade.items() if c == i]
        ok(False, f"{i}: sem grade completa D0/D+1/D+2 {achou}")

print("\n" + "=" * 74)
if fails:
    print(f"RESULTADO: {len(fails)} FALHA(S)")
    for f in fails:
        print("  - " + f)
    sys.exit(1)
print("RESULTADO: TODAS AS VERIFICACOES PASSARAM")