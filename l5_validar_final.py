#!/usr/bin/env python3
"""End-to-end validation of lista5.m3u: structure, EPG coverage, streams, logos."""
import os, re, gzip, subprocess, sys, requests, collections
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

M3U = "lista5.m3u"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36")
H = {"User-Agent": UA, "Accept": "*/*"}
ok_all = True


def chk(cond, msg):
    global ok_all
    print(("  [OK]  " if cond else "  [FAIL] ") + msg)
    if not cond:
        ok_all = False
    return cond


def parse(path):
    entries, cur = [], None
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("#EXTINF"):
            cur = {"attrs": line, "url": None}
        elif line.startswith("#"):
            continue
        else:
            if cur is None:
                cur = {"attrs": "#EXTINF:ORPHAN", "url": None}
            cur["url"] = line
            entries.append(cur)
            cur = None
    return entries


lines = open(M3U, encoding="utf-8").read().splitlines()
entries = parse(M3U)
header = lines[0]

print("=" * 70)
print("1) ESTRUTURA / # NA LINHA DE CIMA")
print("=" * 70)
chk(header.startswith("#EXTM3U"), "primeira linha e #EXTM3U")
chk(not entries or entries[0]["attrs"] != "#EXTINF:ORPHAN",
    "nenhum link de canal sem #EXTINF na linha de cima")
chk(len(entries) == 4, f"total de canais = {len(entries)}")
chk(all(e["attrs"].startswith("#EXTINF") for e in entries),
    "todo par EXTINF/URL esta correctly emparelhado")

print()
print("=" * 70)
print("2) EPG (url-tvg / x-tvg-url no cabecalho)")
print("=" * 70)
epgs = re.findall(r'(?:url-tvg|x-tvg-url)="([^"]+)"', header)
chk(bool(epgs), "cabecalho possui url-tvg/x-tvg-url")
epg_urls = sorted(set(u for e in epgs for u in e.split()))
print(f"  EPG(s) na lista: {len(epg_urls)}")
epg_data, epg_src = {}, {}
for u in epg_urls:
    try:
        r = requests.get(u, timeout=120, headers={"User-Agent": UA})
        chk(r.status_code == 200, f"HTTP 200 em {u}")
        raw = gzip.decompress(r.content) if u.endswith(".gz") else r.content
        txt = raw.decode("utf-8", "ignore")
        ids = set(re.findall(r'<channel id="([^"]+)"', txt))
        epg_data[u] = ids
        print(f"     canais no EPG: {len(ids)}  bytes: {len(raw)}")
        epg_src[u] = txt
    except Exception as e:
        chk(False, f"falha ao baixar {u}: {e}")

ids_needed = [re.search(r'tvg-id="([^"]+)"', e["attrs"]).group(1) for e in entries]
print(f"  tvg-id usados: {ids_needed}")
for i in ids_needed:
    found = [u for u, ids in epg_data.items() if i in ids]
    chk(bool(found), f"tvg-id '{i}' existe em {len(found)} EPG(s)")

print()
print("=" * 70)
print("3) PROGRAMACAO: HOJE / AMANHA / DEPOIS DE AMANHA")
print("=" * 70)
today = datetime.now(timezone.utc).date()
days = {"HOJE": today, "AMANHA": today + timedelta(days=1),
        "DEPOIS DE AMANHA": today + timedelta(days=2)}
for label, d in days.items():
    ds = d.strftime("%Y%m%d")
    print(f"  -- {label} ({d.isoformat()} / {ds})")
for i in ids_needed:
    counts = collections.Counter()
    for u, txt in epg_src.items():
        for ch, st in re.findall(r'<programme channel="([^"]+)" start="(\d{14})', txt):
            if ch == i:
                counts[st[:8]] += 1
    for label, d in days.items():
        n = counts[d.strftime("%Y%m%d")]
        chk(n > 0, f"{i} -> {label}: {n} programas")

print()
print("=" * 70)
print("4) LOGOS (.jpg, sem imgur, baixam de verdade)")
print("=" * 70)
for e in entries:
    name = e["attrs"].split(",")[-1]
    m = re.search(r'tvg-logo="([^"]*)"', e["attrs"])
    if not chk(bool(m) and m.group(1), f"{name}: possui tvg-logo"):
        continue
    u = m.group(1)
    chk("imgur.com" not in u.lower(), f"{name}: nao usa imgur")
    path = urlparse(u).path.lower()
    chk(path.endswith(".jpg") or ".jpg" in path, f"{name}: extensao .jpg ({path[-24:]})")
    try:
        r = requests.get(u, timeout=30, headers={"User-Agent": UA})
        chk(r.status_code == 200 and r.content[:3] == b"\xff\xd8\xff",
            f"{name}: JPEG valido http={r.status_code} bytes={len(r.content)}")
    except Exception as ex:
        chk(False, f"{name}: erro no logo {ex}")

print()
print("=" * 70)
print("5) SINAIS DE AFILIADAS / ENCURTADORES")
print("=" * 70)
pat = re.compile(r"aff(iliate)?=|partner=|/aff|\?ref=|referrer=|clickid|tracker|"
                 r"bit\.ly|tinyurl|t\.me/|shorte|adsterra|popads|onclicka", re.I)
for e in entries:
    n = e["attrs"].split(",")[-1]
    hits = pat.findall(e["url"] + " " + e["attrs"])
    chk(not hits, f"{n}: sem sinal de afiliada/encurtador {hits[:2] if hits else ''}")

print()
print("=" * 70)
print("6) STREAM: master -> variante -> segmento (HLS real)")
print("=" * 70)
import os as _os
_os.makedirs("/tmp/opencode/final", exist_ok=True)
for e in entries:
    name = e["attrs"].split(",")[-1]
    u = e["url"]
    try:
        r = requests.get(u, headers=H, timeout=30)
        if not chk(r.status_code == 200 and b"#EXTM3U" in r.content[:200],
                   f"{name}: master http={r.status_code}"):
            continue
        ls = [x.strip() for x in r.text.splitlines()]
        v = None
        res = "?"
        for i2, l in enumerate(ls):
            if l.startswith("#EXT-X-STREAM-INF"):
                nx = next((x for x in ls[i2 + 1:] if x and not x.startswith("#")), None)
                if nx:
                    from urllib.parse import urljoin
                    rm = re.search(r"RESOLUTION=(\d+x\d+)", l)
                    res = rm.group(1) if rm else "?"
                    v = urljoin(u, nx)
        if not v:
            chk(False, f"{name}: sem variantes")
            continue
        vr = requests.get(v, headers=H, timeout=30)
        segs = [x.strip() for x in vr.text.splitlines() if x.strip() and not x.startswith("#")]
        chk(bool(segs), f"{name}: variante lista {len(segs)} segmento(s)")
        if not segs:
            continue
        from urllib.parse import urljoin
        su = urljoin(v, segs[-1])
        sr = requests.get(su, headers=H, timeout=40)
        body = sr.content
        media = (body[:1] == b"G" or body[4:8] in (b"styp", b"moof", b"ftyp")
                 or body[:2] in (b"\xff\xf1", b"\xff\xf9"))
        safe = re.sub(r"[^A-Za-z0-9]+", "_", name)
        p = f"/tmp/opencode/final/{safe}.seg"
        open(p, "wb").write(body)
        chk(sr.status_code == 200 and media and len(body) > 10000,
            f"{name}: segmento ok http={sr.status_code} bytes={len(body)} res={res}")
    except Exception as ex:
        chk(False, f"{name}: excecao {ex}")

print()
print("=" * 70)
print("7) ANTIVIRUS (ClamAV) nos segmentos baixados do servidor")
print("=" * 70)
segs = [f"/tmp/opencode/final/{f}" for f in os.listdir("/tmp/opencode/final")]
if segs:
    cp = subprocess.run(["clamscan", "--no-summary", "--infected", *segs],
                        capture_output=True, text=True, timeout=300)
    out = (cp.stdout + cp.stderr).strip()
    chk("FOUND" not in out, f"ClamAV: {len(segs)} arquivo(s) verificado(s), 0 deteccao"
        + ("" if "FOUND" not in out else f" -> {out[:400]}"))
else:
    chk(False, "nenhum segmento para verificar")

print()
print("=" * 70)
print("RESULTADO:", "TUDO OK" if ok_all else "HAVE FALHAS")
print("=" * 70)
sys.exit(0 if ok_all else 1)