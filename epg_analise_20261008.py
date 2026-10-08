#!/usr/bin/env python3
"""Analisa EPGs: canais relevantes, janela de 3 dias e amostras."""
import gzip, re, sys, xml.etree.ElementTree as ET
from datetime import datetime, timedelta

HOJE = datetime.now()
DIAS = [(HOJE + timedelta(days=k)) for k in range(3)]
DS = [d.strftime("%Y%m%d") for d in DIAS]
print("Dias exigidos:", " | ".join(f"{d.strftime('%d/%m')}" for d in DIAS), f"(UTC now={HOJE:%Y-%m-%d %H:%M})")

PADROES = ["abc news live", "fox news", "fox business", "cbs news"]

def load(path):
    raw = open(path, "rb").read()
    try:
        raw = gzip.decompress(raw)
    except Exception:
        pass
    return ET.fromstring(raw)

for label, path in [("epgshare01 US2", "/tmp/opencode/epg/us2.xml.gz"),
                    ("epg.pw US", "/tmp/opencode/epg/us_pw.xml.gz")]:
    root = load(path)
    chans = root.findall("channel")
    progs = root.findall("programme")
    dates = sorted({p.get("start", "")[:8] for p in progs if p.get("start", "")[:8].isdigit()})
    print(f"\n=== {label}: {len(chans)} canais, {len(progs)} programas, janela {dates[0]}..{dates[-1]}")

    hits = []
    for ch in chans:
        dn = (ch.findtext("display-name") or "").strip()
        cid = ch.get("id", "")
        blob = (dn + " " + cid).lower()
        if any(p in blob for p in PADROES):
            hits.append((cid, dn))
    print(f"  matches: {len(hits)}")

    for cid, dn in sorted(hits, key=lambda x: x[1])[:400]:
        cont = {d: 0 for d in DS}
        amostra = {d: [] for d in DS}
        for p in root.findall(f"programme[@channel='{cid}']"):
            d = p.get("start", "")[:8]
            if d in cont:
                cont[d] += 1
                t = p.findtext("title")
                if t and len(amostra[d]) < 2:
                    amostra[d].append(t)
        flag = "OK  " if all(cont[d] > 0 for d in DS) else "FALHA"
        print(f"  [{flag}] {cid} | {dn} | hoje={cont[DS[0]]} amanha={cont[DS[1]]} depois={cont[DS[2]]}")
        if flag == "OK  ":
            print(f"        hoje: {' / '.join(amostra[DS[0]])}")
            print(f"        amanha: {' / '.join(amostra[DS[1]])}")
            print(f"        depois: {' / '.join(amostra[DS[2]])}")
