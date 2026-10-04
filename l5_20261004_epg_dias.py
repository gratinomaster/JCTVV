#!/usr/bin/env python3
"""Confere se um EPG XMLTV tem programming para hoje/amanha/depois de amanha dos tvg-ids."""
import gzip
import sys
import xml.etree.ElementTree as ET
from datetime import date, timedelta

PATH = sys.argv[1]
WANT = sys.argv[2].split(",")
opener = gzip.open if PATH.endswith(".gz") else open

today = date.today()
dias = [f"{(today + timedelta(days=i)).strftime('%Y%m%d')}" for i in range(4)]
print(f"arquivo={PATH}")
print(f"dias verificados: {dias}")

days_found = {w: set() for w in WANT}
counts = {w: 0 for w in WANT}
titles = {w: [] for w in WANT}
with opener(PATH, "rb") as f:
    for ev, el in ET.iterparse(f, events=("end",)):
        if el.tag == "programme":
            ch = el.get("channel")
            if ch in days_found:
                start = el.get("start") or ""
                counts[ch] += 1
                if len(start) >= 8:
                    days_found[ch].add(start[:8])
                if len(titles[ch]) < 3:
                    t = el.find("title")
                    titles[ch].append((start, (t.text or "")[:40] if t is not None else ""))
            el.clear()
        elif el.tag == "channel":
            el.clear()

for w in WANT:
    ds = sorted(days_found[w])
    tem = [d for d in dias if d in days_found[w]]
    print(f"\n[{w}] programas={counts[w]} dias={ds}")
    print(f"   cobertura hoje/amanha/+2 = {tem} ({len(tem)}/3)")
    for s, t in titles[w]:
        print(f"      {s}  {t}")