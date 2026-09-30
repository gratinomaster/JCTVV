#!/usr/bin/env python3
"""Corrige o lista1.m3u:

- Garante o cabecalho #EXTM3U com url-tvg/x-tvg-url apontando para as 3
  fontes XMLTV do BrazilTVEPG (globo, claro, vivoplay).
- Corrige os tvg-id usando SOMENTE ids que existem de fato nas tres fontes
  XMLTV, verificados contra o XML baixado do repositorio.
- Cada id so pode ficar em UM canal. As reacoes regionais que disputavam o
  mesmo id (11 canais em globonews, 2 em tv-globo, 2 em ge-tv) ficam sem
  tvg-id, porque o XMLTV so tem um canal por rede. Assim o EPG para de ser
  atribuido ao canal errado.
"""

import os
import re
import shutil
import sys
import time
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

# Redes -> id do XMLTV. Avaliadas em ordem sobre o nome/tvg-name do canal.
NETWORKS = [
    (re.compile(r"sportv", re.I), "sportv"),
    (re.compile(r"globo\s*news|\bg1\b|jornal nacional", re.I), "globonews"),
    (re.compile(r"^\s*ge\b|\bge\s*hd\b|ge\.globo|globo esporte", re.I), "ge-tv"),
    (re.compile(r"^\s*globo\b|globo\.com|abtv", re.I), "tv-globo"),
]

EXTINF_RE = re.compile(r'^#EXTINF:(?P<dur>-?[\d.]+)\s*(?P<attrs>.*?),(?P<name>.*)$')
ATTR_RE = re.compile(r'([\w-]+)="([^"]*)"')


def available_ids():
    ids = set()
    for name in EPG_SOURCES:
        path = os.path.join(CACHE, "%s.xml" % name)
        if not os.path.exists(path):
            print("  ! %s.xml ausente em .epg_cache" % name)
            continue
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError as exc:
            print("  ! %s.xml invalido: %s" % (name, exc))
            continue
        found = [c.get("id") for c in root.iter("channel") if c.get("id")]
        print("  %-8s %4d canais" % (name, len(found)))
        ids.update(found)
    return ids


def parse(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        lines = fh.read().splitlines()

    entries = []
    i = 0
    while i < len(lines):
        m = EXTINF_RE.match(lines[i].strip())
        if not m:
            i += 1
            continue
        url = ""
        if i + 1 < len(lines) and lines[i + 1].strip() and not lines[i + 1].startswith("#"):
            url = lines[i + 1].strip()
            i += 1
        entries.append((dict(ATTR_RE.findall(m.group("attrs"))), m.group("name").strip(), url))
        i += 1
    return entries


def resolve(name, ids):
    for pattern, tvg_id in NETWORKS:
        if pattern.search(name) and tvg_id in ids:
            return tvg_id
    return None


def main():
    print("Fontes EPG:")
    ids = available_ids()
    if not ids:
        print("ERRO: nenhum id disponivel em .epg_cache")
        return 1

    entries = parse(LISTA)
    print("\nCanais na lista: %d" % len(entries))

    stamp = time.strftime("%Y%m%d_%H%M%S")
    backup = "%s.bak.pre_tvgids_%s" % (LISTA, stamp)
    shutil.copy2(LISTA, backup)
    print("Backup: %s" % os.path.basename(backup))

    used = {}
    out = [HEADER]
    trocas = []
    sem_id = []
    for old, name, url in entries:
        if not url:
            continue
        clean = name.split("|")[0].strip()
        tvg_id = resolve(clean, ids)
        dono = used.get(tvg_id)
        if tvg_id and dono is not None:
            trocas.append((clean, tvg_id, dono))
            tvg_id = None
        elif tvg_id:
            used[tvg_id] = clean
        if tvg_id is None and clean not in sem_id:
            sem_id.append(clean)

        fields = ['tvg-id="%s"' % tvg_id] if tvg_id else []
        fields.append('tvg-name="%s"' % clean)
        logo = old.get("tvg-logo", "").strip()
        if logo:
            fields.append('tvg-logo="%s"' % logo)
        fields.append('group-title="%s"' % old.get("group-title", "GLOBO AO VIVO"))
        out.append("#EXTINF:-1 %s,%s" % (" ".join(fields), clean))
        out.append(url)

    with open(LISTA, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out) + "\n")

    print("Canais escritos: %d" % ((len(out) - 1) // 2))
    print("Ids usados: %s" % ", ".join("%s -> %s" % (v, k) for k, v in used.items()))
    if trocas:
        print("\ntvg-id removido (id ja usado por outro canal):")
        for clean, tvg_id, dono in trocas:
            print("  %-28s %-11s (mantido em %s)" % (clean, tvg_id, dono))
    print("\nSem tvg-id: %d" % len(sem_id))
    return 0


if __name__ == "__main__":
    sys.exit(main())
