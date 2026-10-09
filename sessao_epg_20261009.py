#!/usr/bin/env python3
"""Verifica fontes EPG: leitura, tvg-id, display-name e cobertura hoje/+1/+2."""
import gzip
import io
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

import requests

EPGS = [
    "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz",
    "https://epg.pw/xmltv/epg_US.xml.gz",
]
# tvg-id -> tvg-name esperado
ALVOS = {
    "ABC.News.Live.us2": "ABC News Live",
    "CBS.News.National.Stream.us2": "CBS News National Stream",
    "Fox.News.Channel.HD.us2": "Fox News Channel HD",
    "Fox.Business.HD.us2": "Fox Business HD",
}
# nomes alternativos aceitaveis de display-name
NOMES = {
    "ABC.News.Live.us2": ["abc news live"],
    "CBS.News.National.Stream.us2": ["cbs news national stream", "cbs news 24/7"],
    "Fox.News.Channel.HD.us2": ["fox news channel hd", "fox news channel"],
    "Fox.Business.HD.us2": ["fox business hd", "fox business"],
}
DIAS = [(datetime.now() + timedelta(days=k)).strftime("%Y%m%d") for k in range(3)]

roots = {}
for src in EPGS:
    try:
        r = requests.get(src, timeout=180)
        raw = r.content
        try:
            raw = gzip.decompress(raw)
        except Exception:
            pass
        root = ET.fromstring(raw)
        roots[src] = root
        print(f"EPG OK {src.split('/')[-1]}: {len(root.findall('channel'))} canais, "
              f"{len(root.findall('programme'))} programas")
    except Exception as e:
        print(f"EPG FALHA {src}: {e}")

# busca por nome em todas as fontes
print("\n--- busca por display-name (afiliadas/aliases) ---")
for src, root in roots.items():
    print(f"\n[{src.split('/')[-1]}]")
    for tid, nomes in NOMES.items():
        hit = None
        for ch in root.findall("channel"):
            dns = [d.text or "" for d in ch.findall("display-name")]
            for dn in dns:
                if any(n in dn.strip().lower() for n in nomes):
                    hit = (ch.get("id"), dn)
                    break
            if hit:
                break
        print(f"  {tid:32} -> {hit}")

print("\n--- cobertura 3 dias por tvg-id ---")
for tid in ALVOS:
    ok_any = False
    for src, root in roots.items():
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
            ok_any = True
            print(f"[OK ] {tid} ({dn}) via {src.split('/')[-1]}: "
                  f"hoje={cont[DIAS[0]]} amanha={cont[DIAS[1]]} depois={cont[DIAS[2]]}")
            for d in DIAS:
                print(f"      {d}: {' / '.join(amostra[d])}")
        else:
            faltam = [d for d in DIAS if cont[d] == 0]
            print(f"[--] {tid} via {src.split('/')[-1]}: faltam {faltam} (cont={cont})")
    if not ok_any:
        print(f"[FALHA] {tid} sem 3 dias em nenhuma fonte")

print(f"\nHoje/amanha/depois: {DIAS}")
