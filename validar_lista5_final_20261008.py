#!/usr/bin/env python3
"""Validacao final da lista5.m3u: estrutura, logos, anti-virus, streams e EPG (3 dias)."""
import concurrent.futures, csv, gzip, io, json, re, sys, xml.etree.ElementTree as ET
from datetime import datetime, timedelta

import importlib.util
import requests

BASE = "/home/runner/work/JCTVV/JCTVV/"
LISTA = BASE + "lista5.m3u"
spec = importlib.util.spec_from_file_location("t", BASE + "testar_lista5_20261005_v2.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
spec2 = importlib.util.spec_from_file_location("av", BASE + "av_check_20261008.py")
av = importlib.util.module_from_spec(spec2); spec2.loader.exec_module(av)

erros, info = [], []
linhas = [l.rstrip("\n") for l in open(LISTA, encoding="utf-8")]

# ---------- 1. estrutura ----------
if not linhas[0].startswith("#EXTM3U"):
    erros.append("linha 1 nao e #EXTM3U")
header = linhas[0]
m_urls = re.findall(r'url-tvg="([^"]+)"', header)
if not m_urls:
    erros.append("cabecalho sem url-tvg")
    epg_srcs = []
else:
    epg_srcs = m_urls[0].split()
    info.append(f"url-tvg: {len(epg_srcs)} fontes -> {' | '.join(s.split('/')[-1] for s in epg_srcs)}")

entradas = []
for i, l in enumerate(linhas):
    if i == 0:
        continue
    if l.startswith("http"):
        prev = linhas[i - 1]
        if not prev.startswith("#EXTINF"):
            erros.append(f"linha {i+1}: URL sem #EXTINF na linha de cima")
        else:
            entradas.append((i + 1, prev, l))

logos, tvgids, nomes = {}, {}, {}
for i, ext, url in entradas:
    ml = re.search(r'tvg-logo="([^"]+)"', ext)
    if not ml:
        erros.append(f"linha {i}: sem tvg-logo")
    else:
        logos.setdefault(ml.group(1), []).append(i)
        if "imgur.com" in ml.group(1):
            erros.append(f"linha {i}: logo do imgur")
        if not re.search(r"\.jpg$", ml.group(1).split("?")[0], re.I):
            erros.append(f"linha {i}: logo nao termina em .jpg -> {ml.group(1)}")
    mi = re.search(r'tvg-id="([^"]+)"', ext)
    if not mi:
        erros.append(f"linha {i}: sem tvg-id")
    else:
        tvgids.setdefault(mi.group(1), []).append(i)
    mn = re.search(r'tvg-name="([^"]+)"', ext)
    if mn:
        nomes[mi.group(1) if mi else i] = mn.group(1)
    if "imgur.com" in url:
        erros.append(f"linha {i}: stream do imgur")

info.append(f"entradas={len(entradas)} | canais(tvg-id)={len(tvgids)} | logos distintos={len(logos)}")
info.append(f"links por canal: " + ", ".join(f"{k}={len(v)}" for k, v in tvgids.items()))

# ---------- 2. anti-virus ----------
hosts = av.load_hosts()
bad_urls = av.load_urls(av.ensure_downloaded())
todas = [u for _, _, u in entradas] + list(logos) + epg_srcs
reprovadas = 0
for u in todas:
    r = av.check(u, hosts, bad_urls)
    if r:
        reprovadas += 1
        erros.append(f"anti-virus REPROVOU {u} -> {', '.join(r)}")
info.append(f"anti-virus: {len(todas)} URLs testadas, {reprovadas} reprovadas "
            f"(URLhaus: {len(hosts)} hosts / {len(bad_urls)} URLs maliciosas)")

# controles negativos do detector
ctrl = [("https://imgur.com/a/xyz", "imgur_proibido"),
        ("http://110.136.5.74:44981/i", "urlhaus_url_maliciosa")]
for u, esperado in ctrl:
    r = av.check(u, hosts, bad_urls)
    if esperado not in r:
        erros.append(f"detector nao pegou o controle {u} ({esperado})")
info.append("controles negativos do detector: OK (imgur + URLhaus reprovados)")

# ---------- 3. logos HTTP ----------
UAH = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
for lg in sorted(logos):
    try:
        r = requests.get(lg, headers=UAH, timeout=25, stream=True, allow_redirects=True)
        ct = r.headers.get("Content-Type", "")
        ok = r.status_code == 200 and "image/jpeg" in ct
        info.append(f"logo {'OK  ' if ok else 'FALHA'} {r.status_code} {ct.split(';')[0]} {lg[:70]}")
        if not ok:
            erros.append(f"logo invalido: {lg}")
    except Exception as e:
        erros.append(f"logo erro {e}: {lg}")

# ---------- 4. streams ----------
def tst(u):
    _, ok, why = m.test_url(u)
    return u, ok, why
urls = [u for _, _, u in entradas]
stream_ok = 0
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
    for u, ok, why in ex.map(tst, urls):
        if ok:
            stream_ok += 1
        else:
            erros.append(f"stream caiu: {why} | {u[:90]}")
info.append(f"streams: {stream_ok}/{len(urls)} entregaram midia real")

# ---------- 5. EPG 3 dias ----------
DIAS = [(datetime.now() + timedelta(days=k)).strftime("%Y%m%d") for k in range(3)]
EPG_CACHE = {}
for src in epg_srcs:
    try:
        r = requests.get(src, timeout=180)
        raw = r.content
        try:
            raw = gzip.decompress(raw)
        except Exception:
            pass
        EPG_CACHE[src] = ET.fromstring(raw)
        info.append(f"EPG {src.split('/')[-1]}: OK ({len(EPG_CACHE[src].findall('channel'))} canais, "
                    f"{len(EPG_CACHE[src].findall('programme'))} programas)")
    except Exception as e:
        erros.append(f"EPG inacessivel {src}: {e}")

for tid in sorted(tvgids):
    cobertos = []
    for src, root in EPG_CACHE.items():
        ch = root.find(f"channel[@id='{tid}']")
        if ch is None:
            continue
        dn = ch.findtext("display-name") or ""
        cont = {d: 0 for d in DIAS}
        amostra = {d: [] for d in DIAS}
        for p in root.findall(f"programme[@channel='{tid}']"):
            d = p.get("start", "")[:8]
            if d in cont:
                cont[d] += 1
                t = p.findtext("title")
                if t and len(amostra[d]) < 2:
                    amostra[d].append(t)
        if all(cont[d] > 0 for d in DIAS):
            cobertos.append((src, dn, cont, amostra))
            nome = nomes.get(tid, "")
            if nome and nome.strip().lower() != dn.strip().lower():
                erros.append(f"tvg-name '{nome}' difere do display-name '{dn}' em {src.split('/')[-1]}")
    if not cobertos:
        erros.append(f"EPG: {tid} sem programacao de 3 dias em NENHUMA fonte")
        info.append(f"  [FALHA] {tid}")
        continue
    src, dn, cont, amostra = cobertos[0]
    info.append(f"  [OK ] {tid} ({dn}) via {src.split('/')[-1]}: "
                f"hoje={cont[DIAS[0]]} amanha={cont[DIAS[1]]} depois={cont[DIAS[2]]}")
    info.append(f"        hoje  {DIAS[0]}: {' / '.join(amostra[DIAS[0]])}")
    info.append(f"        amanha {DIAS[1]}: {' / '.join(amostra[DIAS[1]])}")
    info.append(f"        depois {DIAS[2]}: {' / '.join(amostra[DIAS[2]])}")
    if len(cobertos) == len(EPG_CACHE):
        info.append(f"        (presente e com 3 dias completos nas {len(cobertos)} fontes)")

# ---------- relatorio ----------
print("=" * 80)
print(f"VALIDACAO FINAL lista5.m3u  -  {datetime.now():%Y-%m-%d %H:%M:%S}")
print("=" * 80)
for l in info:
    print("  ", l)
print("-" * 80)
if erros:
    print(f"PROBLEMAS ({len(erros)}):")
    for e in erros:
        print("   X", e)
else:
    print("TUDO OK - sem problemas")
