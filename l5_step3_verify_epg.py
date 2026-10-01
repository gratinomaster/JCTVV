#!/usr/bin/env python3
"""Passo 3 - verificacao detalhada: contagem de programas por dia + amostra de titulos."""
import gzip
import re
import sys
from collections import defaultdict
from datetime import date, timedelta

HOJE = date.today()
DIAS = {HOJE: "D0", HOJE + timedelta(1): "D+1", HOJE + timedelta(2): "D+2"}

ALVOS = {
    "https://iptv-epg.org/files/epg-us.xml.gz": {
        "path": "/tmp/opencode/8cffd98f.gz",
        "ids": ["ABCNewsLive.us", "CBSNews.us", "FoxBusiness.us",
                "FoxNewsChannel.us"],
    },
    "https://epgshare01.online/epgshare01/epg_ripper_ALL_SOURCES1.xml.gz": {
        "path": "/tmp/opencode/214ab2f6.gz",
        "ids": ["ABC.News.Live.us2", "Fox.Business.HD.us2",
                "Fox.News.Channel.HD.us2", "plex.tv.CBS.News.24/7.plex"],
    },
    "https://epg.pw/xmltv/epg_US.xml.gz": {
        "path": "/tmp/opencode/c0c2144c.gz",
        "ids": ["465150", "464941", "464766", "465372"],
    },
}

TITRE = re.compile(r"<title[^>]*>(.*?)</title>", re.S)
DESCR = re.compile(r"<desc[^>]*>(.*?)</desc>", re.S)
ICON = re.compile(r'<icon src="([^"]+)"')


def clean(s):
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\s+", " ", s).strip()


def run(url, spec):
    print(f"\n{'='*78}\n{url}\n{'='*78}")
    want = set(spec["ids"])
    cont = defaultdict(lambda: defaultdict(list))
    icons = {}
    nomes = {}
    in_ch, cid = False, None
    with gzip.open(spec["path"], "rt", encoding="utf-8", errors="replace") as f:
        for line in f:
            ls = line.strip()
            if ls.startswith("<channel "):
                in_ch = True
                m = re.search(r'channel id="([^"]+)"', ls)
                cid = m.group(1) if m else None
            elif in_ch:
                if ls.startswith("<display-name"):
                    if cid in want:
                        nomes.setdefault(cid, []).append(clean(ls))
                elif ls.startswith("<icon"):
                    m = ICON.search(ls)
                    if m and cid in want:
                        icons.setdefault(cid, m.group(1))
                elif ls.startswith("</channel"):
                    in_ch = False
                continue
            elif ls.startswith("<programme "):
                m = re.search(r'channel="([^"]+)"', ls)
                s = re.search(r'start="(\d{8})', ls)
                if not (m and s) or m.group(1) not in want:
                    continue
                try:
                    d = date(int(s.group(1)[:4]), int(s.group(1)[4:6]),
                             int(s.group(1)[6:8]))
                except ValueError:
                    continue
                if d not in DIAS:
                    continue
                t = TITRE.search(ls)
                cont[m.group(1)][DIAS[d]].append(
                    clean(t.group(1)) if t else "(sem titulo)")

    for cid in spec["ids"]:
        dias = cont.get(cid, {})
        tot = sum(len(v) for v in dias.values())
        dias_ok = [d for d in ("D0", "D+1", "D+2") if dias.get(d)]
        st = "OK" if len(dias_ok) == 3 else ("PARCIAL" if dias_ok else "VAZIO")
        print(f"\n  {cid}  [{' | '.join(nomes.get(cid, [])[:3])}]  => {st}")
        print(f"    icone: {icons.get(cid, '(sem)')[:100]}")
        for d in ("D0", "D+1", "D+2"):
            lst = dias.get(d, [])
            print(f"    {d:>4}: {len(lst):>3} programas", end="")
            if lst:
                uniq = list(dict.fromkeys(lst))[:3]
                print(f"   ex: {' / '.join(uniq)[:100]}")
            else:
                print()
        if tot == 0:
            print("    >>> NAO ENCONTRADO neste EPG")


if __name__ == "__main__":
    sel = sys.argv[1:]
    for url, spec in ALVOS.items():
        if sel and url not in sel:
            continue
        run(url, spec)