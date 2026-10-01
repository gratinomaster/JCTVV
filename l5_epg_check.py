#!/usr/bin/env python3
"""Confere cobertura D0/D+1/D+2 do EPG local filtrado l5_epg.xml."""
import re
from collections import defaultdict
from datetime import date, timedelta

hoje = date.today()
rot = {hoje: "HOJE", hoje + timedelta(1): "AMANHA",
       hoje + timedelta(2): "DEPOIS DE AMANHA"}
raw = open("l5_epg.xml", encoding="utf-8").read()

ch = re.findall(r'<channel id="([^"]+)">.*?<display-name[^>]*>([^<]*)'
                r'</display-name>', raw, re.S)
c = defaultdict(lambda: defaultdict(int))
for m in re.finditer(r'<programme start="(\d{8})[^"]*"[^>]*'
                     r'channel="([^"]+)"', raw):
    s, cid = m.group(1), m.group(2)
    try:
        d = date(int(s[:4]), int(s[4:6]), int(s[6:8]))
    except ValueError:
        continue
    if d in rot:
        c[cid][rot[d]] += 1

print(f"l5_epg.xml - {len(raw)} bytes, {len(raw.split('<programme'))-1} "
      f"programas\n")
falhas = 0
for cid, nome in ch:
    d = c[cid]
    linha = f"{d['HOJE']:>3} / {d['AMANHA']:>3} / {d['DEPOIS DE AMANHA']:>3}"
    bom = all(d[k] for k in rot.values())
    falhas += 0 if bom else 1
    print(f"  {'[ok]  ' if bom else '[FALHA]'} {cid:<20} {nome:<24} "
          f"HOJE/AMANHA/DEPOIS = {linha}")
print(f"\n{'todos os canais com 3 dias' if not falhas else falhas} "
      f"canal(ais) sem os 3 dias")