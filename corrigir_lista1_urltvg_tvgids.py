#!/usr/bin/env python3
"""Corrige o lista1.m3u:

- Garante o cabecalho #EXTM3U com url-tvg/x-tvg-url apontando para as 3
  fontes XMLTV do BrazilTVEPG (globo, claro, vivoplay), separadas por espaco.
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
REPORT = os.path.join(BASE, "relatorio_lista1_epg.txt")

EPG_SOURCES = OrderedDict(
    [
        ("globo", "https://github.com/limaalef/BrazilTVEPG/raw/refs/heads/main/globo.xml"),
        ("claro", "https://github.com/limaalef/BrazilTVEPG/raw/refs/heads/main/claro.xml"),
        ("vivoplay", "https://github.com/limaalef/BrazilTVEPG/raw/refs/heads/main/vivoplay.xml"),
    ]
)

URL_TVG = " ".join(EPG_SOURCES.values())
HEADER = '#EXTM3U url-tvg="%s" x-tvg-url="%s"' % (URL_TVG, URL_TVG)

# Ordem importa: a primeira regra que casar define o tvg-id.
# CBN nao existe em nenhuma das 3 fontes -> fica sem id.
RULES = [
    (r"\bspor ?tv\b|\bsportv\b", "sportv"),
    (r"^ge\b|\bge\s?hd\b|\bge\s?tv\b|globo\s?esporte", "ge-tv"),
    (r"^g1\b|\bg1\b|jornal nacional|globo news", "globonews"),
    (r"\bcbn\b", None),
    (r"\bglobo\b|\babtv\b|afiliad", "tv-globo"),
]

EXTINF_RE = re.compile(r'^#EXTINF:(?P<dur>-?[\d.]+)\s*(?P<attrs>.*?),(?P<name>.*)$')
ATTR_RE = re.compile(r'([\w-]+)="([^"]*)"')


def download_epg_sources():
    """Baixa (se preciso) as 3 fontes e devolve {fonte: {channel ids}}."""
    available = OrderedDict()
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
            available[name] = set()
            continue
        ids = set(c.get("id") for c in root.iter("channel") if c.get("id"))
        progs = set(p.get("channel") for p in root.iter("programme") if p.get("channel"))
        available[name] = ids
        print("  %-8s %4d canais (%d com programacao)" % (name, len(ids), len(progs & ids)))
    return available


def resolve_tvg_id(name, per_source):
    """Descobre o tvg-id correto a partir do nome do canal, ou None."""
    available = set()
    for ids in per_source.values():
        available |= ids
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


def main():
    print("Fontes EPG:")
    per_source = download_epg_sources()
    available = set()
    for ids in per_source.values():
        available |= ids
    print("Total de ids disponiveis: %d\n" % len(available))

    with open(LISTA, encoding="utf-8", errors="replace") as fh:
        lines = fh.read().splitlines()

    stamp = time.strftime("%Y%m%d_%H%M%S")
    shutil.copy2(LISTA, "%s.bak.pre_urltvg_tvgids_%s" % (LISTA, stamp))
    print("Backup: lista1.m3u.bak.pre_urltvg_tvgids_%s\n" % stamp)

    out = [HEADER]
    rows = []
    changed = []
    kept = 0

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
        new_id = resolve_tvg_id(name, per_source)

        if new_id == (old_id or None):
            kept += 1
        else:
            changed.append("%s: %s -> %s" % (name, old_id or "(vazio)", new_id or "(vazio)"))

        # De onde vem o id, em qual fonte ele existe.
        found_in = [src for src, ids in per_source.items() if new_id and new_id in ids]
        rows.append((name, old_id, new_id, found_in))

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

    canais = (len(out) - 1) // 2
    print("Canais: %d (tvg-id mantido: %d, alterado: %d)" % (canais, kept, len(changed)))
    for line in changed:
        print("  * %s" % line)

    with open(REPORT, "w", encoding="utf-8") as fh:
        fh.write("lista1.m3u - correcao de url-tvg e tvg-ids (%s)\n" % stamp)
        fh.write("Fontes: %s\n\n" % ", ".join(EPG_SOURCES.values()))
        for name, old_id, new_id, found_in in rows:
            if new_id:
                status = "ok (%s)" % ",".join(found_in)
            else:
                status = "sem id (nao existe nas 3 fontes)"
            fh.write("%s | %s -> %s | %s\n" % (name, old_id or "(sem id)", new_id or "(sem id)", status))

    print("\nRelatorio: %s" % os.path.basename(REPORT))
    return 0


if __name__ == "__main__":
    sys.exit(main())