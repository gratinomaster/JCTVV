#!/usr/bin/env python3
"""
Regera o EPG normalizado da lista5 (lista5_epg.xml / lista5_epg.xml.gz).

Fontes:
  - https://iptv-epg.org/files/epg-us.xml.gz   (principal: 3+ dias, ids no padrao iptv-org)
  - https://epg.pw/xmltv/epg.xml.gz             (aliases numericos para compatibilidade)

O EPG gerado contem, para cada canal da lista5:
  - o id canonico do guia principal (ex.: ABCNewsLive.us) com a janela completa de dias
  - os ids numericos do epg.pw como alias (mesmos canais, outra numeracao)

Uso:  python3 build_lista5_epg.py
"""
import gzip
import os
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import requests

BASE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.environ.get("EPG_CACHE", "/tmp/lista5_epg_cache")
os.makedirs(CACHE, exist_ok=True)

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}

SRC_PRIMARY = ("https://iptv-epg.org/files/epg-us.xml.gz", "iptvepg_us.xml.gz")
SRC_GLOBAL = ("https://epg.pw/xmltv/epg.xml.gz", "epg_pw_global.xml.gz")

# canal da lista5 -> ids canonicos + aliases numericos (epg.pw)
CHANNEL_IDS = {
    "ABCNewsLive.us": ["465150", "408627", "3474"],
    "CBSNews.us": ["464941"],
    "FoxBusiness.us": ["464766", "408654"],
}
DAYS = 5  # dias de programa mantidos no EPG gerado


def fetch(url, cache_name):
    path = os.path.join(CACHE, cache_name)
    if os.path.exists(path):
        with open(path, "rb") as f:
            return gzip.decompress(f.read())
    print(f"baixando {url} ...", flush=True)
    r = requests.get(url, timeout=900, headers=UA)
    r.raise_for_status()
    data = r.content
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    with open(path, "wb") as f:
        f.write(gzip.compress(data))
    return data


def index(root):
    chans, progs = {}, defaultdict(list)
    for ch in root.findall("channel"):
        dn = ch.find("display-name")
        chans[ch.get("id")] = (dn.text if dn is not None and dn.text else "",
                               ch.get("lang", "en"))
    for p in root.findall("programme"):
        progs[p.get("channel")].append(p)
    return chans, progs


def keep_window(prog, today):
    s = (prog.get("start") or "")[:8]
    if len(s) != 8:
        return False
    try:
        d = datetime.strptime(s, "%Y%m%d").date()
    except ValueError:
        return False
    return today <= d < today + timedelta(days=DAYS)


def main():
    today = datetime.now(timezone.utc).date()
    alias_ids = {a for v in CHANNEL_IDS.values() for a in v}

    root_p = ET.fromstring(fetch(*SRC_PRIMARY))
    chans_p, progs_p = index(root_p)
    print(f"principal: {len(chans_p)} canais, {len(root_p.findall('programme'))} programas")

    root_g = ET.fromstring(fetch(*SRC_GLOBAL))
    chans_g, progs_g = index(root_g)
    print(f"global   : {len(chans_g)} canais, {len(root_g.findall('programme'))} programas")

    tv = ET.Element("tv", {"generator-info-name": "lista5 EPG normalizado",
                            "source-info-name": "iptv-epg.org + epg.pw"})
    for cid, aliases in CHANNEL_IDS.items():
        for name, lang in (chans_p.get(cid),):
            c = ET.SubElement(tv, "channel", {"id": cid})
            ET.SubElement(c, "display-name").text = name
            ET.SubElement(c, "lang").text = lang or "en"
        for alias in aliases:
            if alias in chans_g:
                name, lang = chans_g[alias]
                c = ET.SubElement(tv, "channel", {"id": alias})
                ET.SubElement(c, "display-name").text = name
                ET.SubElement(c, "lang").text = lang or "en"

    total = 0
    for cid in CHANNEL_IDS:
        for p in progs_p.get(cid, []):
            if keep_window(p, today):
                tv.append(p)
                total += 1
    for alias in alias_ids:
        for p in progs_g.get(alias, []):
            if keep_window(p, today):
                tv.append(p)
                total += 1

    out_xml = os.path.join(BASE, "lista5_epg.xml")
    ET.ElementTree(tv).write(out_xml, encoding="utf-8", xml_declaration=True)
    with open(out_xml, "rb") as f, gzip.open(out_xml + ".gz", "wb") as g:
        g.write(f.read())
    print(f"lista5_epg.xml: {len(tv.findall('channel'))} canais, {total} programas, "
          f"{os.path.getsize(out_xml)//1024} KB")
    print(f"lista5_epg.xml.gz: {os.path.getsize(out_xml + '.gz')//1024} KB")
    print(f"janela: {today} .. {today + timedelta(days=DAYS - 1)}")


if __name__ == "__main__":
    main()
