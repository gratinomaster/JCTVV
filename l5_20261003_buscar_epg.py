#!/usr/bin/env python3
"""Caca EPGs para ABC News Live e CBS News 24/7, medindo cobertura D0/D+1/D+2."""
import gzip
import re
import sys
from collections import defaultdict
from datetime import date, timedelta

FILES = {
    "https://iptv-epg.org/files/epg-us.xml.gz": "8cffd98f.gz",
    "https://epg.pw/xmltv/epg_US.xml.gz": "c0c2144c.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_ALL_SOURCES1.xml.gz": "214ab2f6.gz",
}

ALVO = re.compile(r"\bABC\s*News\b|\bCBS\s*News\b|\bCBSN\b|ABC\.News|CBS\.News",
                  re.I)

HOJE = date.today()
DIAS = {HOJE: "D0", HOJE + timedelta(1): "D+1", HOJE + timedelta(2): "D+2"}


def clean(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s)).strip()


def analyse(url, path):
    print("=" * 78)
    print(url)
    print("=" * 78)
    canais = {}
    prog = defaultdict(lambda: defaultdict(list))
    in_ch = False
    cid = None
    try:
        with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
            for line in f:
                ls = line.strip()
                if ls.startswith("<channel "):
                    in_ch = True
                    m = re.search(r'channel id="([^"]+)"', ls)
                    cid = m.group(1) if m else None
                    continue
                if in_ch:
                    if ls.startswith("<display-name"):
                        nm = clean(ls)
                        if cid and ALVO.search(nm):
                            canais.setdefault(cid, []).append(nm)
                    elif ls.startswith("</channel"):
                        in_ch = False
                    continue
                if ls.startswith("<programme "):
                    m = re.search(r'channel="([^"]+)"', ls)
                    s = re.search(r'start="(\d{8})', ls)
                    if not (m and s) or m.group(1) not in canais:
                        continue
                    d = date(int(s.group(1)[:4]), int(s.group(1)[4:6]),
                             int(s.group(1)[6:8]))
                    if d in DIAS:
                        t = re.search(r"<title[^>]*>(.*?)</title>", ls)
                        prog[m.group(1)][DIAS[d]].append(
                            clean(t.group(1)) if t else "?")
                    continue
    except Exception as e:
        print("ERRO:", e)
        return
    print(f"canais candidatos: {len(canais)}")
    for cid, names in sorted(canais.items()):
        dias = prog.get(cid, {})
        flag = "".join(x for x in ("D0", "D+1", "D+2") if dias.get(x))
        n = sum(len(v) for v in dias.values())
        st = "OK" if len(flag) == 3 else ("PARCIAL" if flag else "VAZIO")
        print(f"\n  {cid}")
        print(f"    nomes   : {' | '.join(dict.fromkeys(names))[:150]}")
        print(f"    status  : {st}  [{flag}]  total prog D0-D+2 = {n}")
        for d in ("D0", "D+1", "D+2"):
            lst = dias.get(d, [])
            ex = " / ".join(list(dict.fromkeys(lst))[:4])[:120]
            print(f"    {d:>4}: {len(lst):>4} prog  {ex}")


if __name__ == "__main__":
    sel = sys.argv[1:]
    for url, path in FILES.items():
        if sel and url not in sel:
            continue
        analyse(url, path)