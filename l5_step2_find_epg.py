#!/usr/bin/env python3
"""Passo 2 - caça aos EPGs: procura canais ABC/Fox/CBS e cobertura D0/D+1/D+2."""
import gzip
import re
import sys
from collections import defaultdict
from datetime import date, timedelta

ALVO = re.compile(
    r"ABC\s*News|Fox\s*News|Fox\s*Business|CBS\s*News|CBSN", re.I)

FILES = {
    "epg.pw/epg_US.xml.gz": "/tmp/opencode/c0c2144c.gz",
    "iptv-epg.org/epg-us.xml.gz": "/tmp/opencode/8cffd98f.gz",
    "epgshare01_ALL_SOURCES1": "/tmp/opencode/214ab2f6.gz",
}

HOJE = date.today()
DIAS = {HOJE: "D0", HOJE + timedelta(1): "D+1", HOJE + timedelta(2): "D+2"}


def esc(s):
    return re.escape(s)


def analyse(nome, path):
    print(f"\n{'='*78}\n{nome}\n{'='*78}")
    canais = {}          # id -> display-names
    prog = defaultdict(set)   # id -> set(dias)
    total_prog = 0
    try:
        with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
            in_ch = False
            cid = None
            for line in f:
                ls = line.strip()
                if ls.startswith("<channel "):
                    in_ch = True
                    cid = None
                    m = re.search(r'channel id="([^"]+)"', ls)
                    if m:
                        cid = m.group(1)
                    continue
                if in_ch:
                    if ls.startswith("<display-name"):
                        nm = re.sub(r"<[^>]+>", "", ls).strip()
                        if cid and ALVO.search(nm):
                            canais.setdefault(cid, set()).add(nm)
                    elif ls.startswith("</channel"):
                        in_ch = False
                    continue
                if ls.startswith("<programme "):
                    total_prog += 1
                    m = re.search(r'channel="([^"]+)"', ls)
                    s = re.search(r'start="(\d{8})', ls)
                    if m and s:
                        try:
                            d = date(int(s.group(1)[:4]),
                                     int(s.group(1)[4:6]),
                                     int(s.group(1)[6:8]))
                        except ValueError:
                            d = None
                        if d in DIAS:
                            prog[m.group(1)].add(DIAS[d])
    except Exception as e:
        print("ERRO:", e)
        return

    print(f"programmes totais: {total_prog}")
    print(f"canais candidatos: {len(canais)}")
    for cid, names in sorted(canais.items()):
        dias = prog.get(cid, set())
        flag = "".join(x for x in ("D0", "D+1", "D+2") if x in dias)
        print(f"  {cid:<45} [{','.join(sorted(names))[:60]}] -> {flag or 'SEM PROGRAMA'}")
    return canais


if __name__ == "__main__":
    alvos = sys.argv[1:] or list(FILES)
    for nome in alvos:
        analyse(nome, FILES[nome])