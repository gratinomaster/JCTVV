#!/usr/bin/env python3
"""Validacao final da lista5.m3u: estrutura, logos, streams, EPG (3 dias)."""
import concurrent.futures, gzip, re, sys, xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import importlib.util, requests

LISTA = "/home/runner/work/JCTVV/JCTVV/lista5.m3u"
spec = importlib.util.spec_from_file_location("t", "/home/runner/work/JCTVV/JCTVV/testar_lista5_20261005_v2.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

linhas = [l.rstrip("\n") for l in open(LISTA, encoding="utf-8")]
erros, info = [], []

# --- 1. estrutura ---
if not linhas[0].startswith("#EXTM3U"):
    erros.append("primeira linha nao e #EXTM3U")
header = linhas[0]
m_urls = re.findall(r'url-tvg="([^"]+)"', header)
if not m_urls:
    erros.append("cabecalho sem url-tvg")
else:
    info.append(f"url-tvg: {m_urls[0]}")

entradas = []
for i, l in enumerate(linhas[1:], start=2):
    if l.startswith("http"):
        prev = linhas[i-2] if i-2 >= 0 else ""
        if not prev.startswith("#EXTINF"):
            erros.append(f"linha {i}: URL sem #EXTINF acima")
        else:
            entradas.append((i, prev, l))

logos = set(); tvgids = {}
for i, ext, url in entradas:
    ml = re.search(r'tvg-logo="([^"]+)"', ext)
    if not ml:
        erros.append(f"linha {i}: sem tvg-logo")
    else:
        logos.add(ml.group(1))
        if "imgur.com" in ml.group(1):
            erros.append(f"linha {i}: logo do imgur")
        if not re.search(r'\.jpg(\?|$)', ml.group(1), re.I):
            erros.append(f"linha {i}: logo nao termina em .jpg -> {ml.group(1)}")
    mi = re.search(r'tvg-id="([^"]+)"', ext)
    if not mi:
        erros.append(f"linha {i}: sem tvg-id")
    else:
        tvgids.setdefault(mi.group(1), []).append(i)
    if "imgur.com" in url:
        erros.append(f"linha {i}: URL de stream do imgur")

info.append(f"entradas: {len(entradas)} | tvg-ids distintos: {len(tvgids)} | logos distintos: {len(logos)}")

# --- 2. logos HTTP ---
for lg in sorted(logos):
    try:
        r = requests.head(lg, timeout=20, allow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
        ct = r.headers.get("Content-Type", "")
        ok = r.status_code == 200 and "image/jpeg" in ct
        info.append(f"logo {'OK ' if ok else 'FALHA'} {r.status_code} {ct.split(';')[0]} {lg[:80]}")
        if not ok: erros.append(f"logo invalido: {lg}")
    except Exception as e:
        erros.append(f"logo erro {e}: {lg}")

# --- 3. streams ---
def tst(u):
    _, ok, why = m.test_url(u); return u, ok, why
urls = [u for _,_,u in entradas]
stream_ok = {}
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
    for u, ok, why in ex.map(tst, urls):
        stream_ok[u] = (ok, why)
        info.append(f"stream {'OK  ' if ok else 'FALHA'} {why[:60]} | {u[:80]}")
        if not ok: erros.append(f"stream caiu: {u}")

# --- 4. EPG 3 dias ---
DIAS = [(datetime.now()+timedelta(days=k)).strftime("%Y%m%d") for k in range(3)]
epg_srcs = [u.strip() for u in m_urls[0].split()]
for src in epg_srcs:
    print(f"\n### EPG {src}", file=sys.stderr)
    try:
        r = requests.get(src, timeout=120)
        raw = r.content
        try: raw = gzip.decompress(raw)
        except Exception: pass
        root = ET.fromstring(raw)
    except Exception as e:
        erros.append(f"EPG inacessivel {src}: {e}"); continue
    info.append(f"EPG {src.split('/')[-1]}: canais={len(root.findall('channel'))} programas={len(root.findall('programme'))}")
    for tid in sorted(tvgids):
        ch = root.find(f"channel[@id='{tid}']")
        if ch is None:
            info.append(f"  {tid}: AUSENTE neste EPG")
            continue
        dn = ch.findtext("display-name")
        cont = {d: 0 for d in DIAS}
        amostra = {d: [] for d in DIAS}
        for p in root.findall(f"programme[@channel='{tid}']"):
            d = p.get("start","")[:8]
            if d in cont:
                cont[d] += 1
                t = p.findtext("title")
                if t and len(amostra[d]) < 3: amostra[d].append(t)
        flag = "OK " if all(cont[d] > 0 for d in DIAS) else "FALHA"
        info.append(f"  [{flag}] {tid} ({dn}) -> hoje {cont[DIAS[0]]} | amanha {cont[DIAS[1]]} | depois {cont[DIAS[2]]}")
        if flag == "FALHA":
            erros.append(f"EPG sem programacao em 3 dias para {tid} em {src}")
        else:
            info.append(f"        hoje: {' / '.join(amostra[DIAS[0]])}")
            info.append(f"        amanha: {' / '.join(amostra[DIAS[1]])}")
            info.append(f"        depois: {' / '.join(amostra[DIAS[2]])}")

print("="*78)
print("VALIDACAO FINAL lista5.m3u", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
print("="*78)
for l in info: print(" ", l)
print("-"*78)
if erros:
    print(f"PROBLEMAS ({len(erros)}):")
    for e in erros: print("  X", e)
else:
    print("TUDO OK - sem problemas")
print(f"streams: {sum(1 for v in stream_ok.values() if v[0])}/{len(urls)}")
