#!/usr/bin/env python3
"""Corrige o lista1.m3u:

- Garante o cabecalho #EXTM3U com url-tvg/x-tvg-url apontando para as 3
  fontes XMLTV do BrazilTVEPG (globo, claro, vivoplay).
- Corrige os tvg-id usando SOMENTE ids que existem de fato nas tres fontes
  XMLTV, verificados contra os XMLs baixados do repositorio.

A lista atual (urls, logos, grupos e nomes) e preservada; apenas o cabecalho
e o atributo tvg-id de cada #EXTINF sao reescritos.
"""

import os
import re
import shutil
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from collections import OrderedDict

BASE = os.path.dirname(os.path.abspath(__file__))
LISTA = os.path.join(BASE, "lista1.m3u")
CACHE = os.path.join(BASE, ".epg_cache")

EPG_SOURCES = OrderedDict(
    [
        ("globo", "https://github.com/limaalef/BrazilTVEPG/raw/refs/heads/main/globo.xml"),
        ("claro", "https://github.com/limaalef/BrazilTVEPG/raw/refs/heads/main/claro.xml"),
        ("vivoplay", "https://github.com/limaalef/BrazilTVEPG/raw/refs/heads/main/vivoplay.xml"),
    ]
)

URL_TVG = ",".join(EPG_SOURCES.values())
HEADER = '#EXTM3U url-tvg="%s" x-tvg-url="%s"' % (URL_TVG, URL_TVG)

# Ordem importa: a primeira regra que casar define o tvg-id.
RULES = [
    (r"sportv|spor ?tv", "sportv"),
    (r"\bge\b|\bge\.?globo\b|ge\s*tv", "ge-tv"),
    (r"\bg1\b|jornal nacional|bonfim", "globonews"),
    (r"cbn", None),  # CBN nao existe em nenhuma das 3 fontes -> sem id
    (r"abtv|afiliad|\bglobo\b|\bsp\b", "tv-globo"),
]

EXTINF_RE = re.compile(r'^#EXTINF:(?P<dur>-?[\d.]+)\s*(?P<attrs>.*?),(?P<name>.*)$')
ATTR_RE = re.compile(r'([\w-]+)="([^"]*)"')


def download_epg_ids():
    """Baixa as 3 fontes e devolve o conjunto de channel ids disponiveis."""
    ids = set()
    os.makedirs(CACHE, exist_ok=True)
    for name, url in EPG_SOURCES.items():
        path = os.path.join(CACHE, "%s.xml" % name)
        if not os.path.exists(path) or os.path.getsize(path) < 1000:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=180) as resp:
                data = resp.read()
            with open(path, "wb") as fh:
                fh.write(data)
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError as exc:
            print("  ! %s.xml invalido: %s" % (name, exc))
            continue
        found = [c.get("id") for c in root.iter("channel") if c.get("id")]
        print("  %-8s %4d canais" % (name, len(found)))
        ids.update(found)
    return ids


def resolve_tvg_id(name, available):
    """Descobre o tvg-id correto a partir do nome do canal, ou None."""
    low = name.lower()
    for pattern, forced in RULES:
        if not re.search(pattern, low):
            continue
        if forced is None:
            return None
        if forced in available:
            return forced
        print("  ! id '%s' (regra %s) ausente nas fontes XMLTV" % (forced, pattern))
    return None


def count_programmes(cache_dir, channel_id):
    """Conta quantos <programme> existem para um channel id nas 3 fontes."""
    total = 0
    for name in EPG_SOURCES:
        path = os.path.join(cache_dir, "%s.xml" % name)
        try:
            root = ET.parse(path).getroot()
        except (ET.ParseError, OSError):
            continue
        for prog in root.iter("programme"):
            if prog.get("channel") == channel_id:
                total += 1
    return total


def main():
    print("Fontes EPG:")
    available = download_epg_ids()
    print("Total de ids disponiveis: %d\n" % len(available))

    with open(LISTA, encoding="utf-8", errors="replace") as fh:
        lines = fh.read().splitlines()

    stamp = time.strftime("%Y%m%d_%H%M%S")
    shutil.copy2(LISTA, "%s.bak.pre_tvgids_%s" % (LISTA, stamp))
    print("Backup: lista1.m3u.bak.pre_tvgids_%s\n" % stamp)

    out = [HEADER]
    changed = []
    sem_id = []
    kept = 0
    checked = {}

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        m = EXTINF_RE.match(line)
        if not m:
            i += 1
            continue

        url = ""
        if i + 1 < len(lines) and lines[i + 1].strip() and not lines[i + 1].startswith("#"):
            url = lines[i + 1].strip()
            i += 1

        old = dict(ATTR_RE.findall(m.group("attrs")))
        name = m.group("name").strip()
        old_id = old.get("tvg-id", "").strip()
        new_id = resolve_tvg_id(name, available)

        if new_id is None:
            sem_id.append(name)
        if new_id != old_id:
            if new_id or old_id:
                changed.append("%s: %s -> %s" % (name, old_id or "(vazio)", new_id or "(vazio)"))
        else:
            kept += 1
        if new_id and new_id not in checked:
            checked[new_id] = count_programmes(CACHE, new_id)

        fields = ['tvg-id="%s"' % new_id] if new_id else []
        fields.append('tvg-name="%s"' % name)
        logo = old.get("tvg-logo", "").strip()
        if logo:
            fields.append('tvg-logo="%s"' % logo)
        fields.append('group-title="%s"' % old.get("group-title", "GLOBO AO VIVO"))

        out.append("#EXTINF:%s %s,%s" % (m.group("dur"), " ".join(fields), name))
        if url:
            out.append(url)
        i += 1

    with open(LISTA, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out) + "\n")

    print("Canais: %d (tvg-id mantido: %d, corrigido: %d)" % ((len(out) - 1) // 2, kept, len(changed)))
    for line in changed:
        print("  * %s" % line)
    if sem_id:
        print("\nSem tvg-id (nao existem nas 3 fontes): %s" % "; ".join(sem_id))
    print("\nProgramas no EPG por tvg-id usado:")
    for cid in sorted(checked):
        print("  %-12s %6d" % (cid, checked[cid]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
