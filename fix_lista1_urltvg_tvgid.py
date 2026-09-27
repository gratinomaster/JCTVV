#!/usr/bin/env python3
"""Corrige o lista1.m3u:

- Garante o cabecalho #EXTM3U com url-tvg/x-tvg-url apontando para as 3
  fontes XMLTV do BrazilTVEPG (globo, claro, vivoplay).
- Recupera os canais de uma versao integra anterior da lista (as execucoes
  passadas reduziram o arquivo ate sobrarem apenas o cabecalho).
- Corrige os tvg-id usando SOMENTE ids que existem de fato nas tres fontes
  XMLTV, verificados contra o XML baixado do repositorio.
"""

import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from collections import OrderedDict

BASE = os.path.dirname(os.path.abspath(__file__))
LISTA = os.path.join(BASE, "lista1.m3u")

EPG_SOURCES = OrderedDict(
    [
        ("globo", "https://github.com/limaalef/BrazilTVEPG/raw/refs/heads/main/globo.xml"),
        ("claro", "https://github.com/limaalef/BrazilTVEPG/raw/refs/heads/main/claro.xml"),
        ("vivoplay", "https://github.com/limaalef/BrazilTVEPG/raw/refs/heads/main/vivoplay.xml"),
    ]
)

URL_TVG = ",".join(EPG_SOURCES.values())
HEADER = '#EXTM3U url-tvg="%s" x-tvg-url="%s"' % (URL_TVG, URL_TVG)

# Fontes integrais, da mais recente para a mais antiga.
CANDIDATES = [
    "lista1.m3u.bak.pre_corrigir_tvgid_20260924_135651",
    "lista1.m3u.bak.pre_corrigir_tvgid_20260923_080635",
    "lista1.m3u.bak.pre_corrigir_tvgid_20260922_182555",
    "lista1.m3u.bak.pre_corrigir_tvgid_20260922_134507",
    "lista1.m3u.bak.pre_corrigir_tvgid_20260921_152704",
    "lista1.m3u.bak.pre_corrigir_tvgid_20260921_123036",
    "lista1.m3u.bak.pre_tvg_20260926_021625",
    "lista1.m3u.bak",
]

# Regras de tvg-id, avaliadas em ordem sobre o nome do canal.
# Cada id precisa existir em alguma das tres fontes XMLTV.
RULES = [
    (r"sportv|sports?\b", "sportv"),
    (r"\bge\.?globo\b|globo esporte|globo\.com/ge", "ge-tv"),
    (r"\bg1\b|globo news|jornal nacional|bonfim", "globonews"),
    (r"cbn", None),  # CBN nao existe em nenhuma das 3 fontes -> sem id
    (r"gnt|multishow|universal|telecine|premiere|bis\b|combate|gnt", "gnt"),
    (r"globo|abtv|record", "tv-globo"),
]

EXTINF_RE = re.compile(r'^#EXTINF:(?P<dur>-?[\d.]+)\s*(?P<attrs>.*?),(?P<name>.*)$')
ATTR_RE = re.compile(r'([\w-]+)="([^"]*)"')


def download_epg_ids(cache_dir):
    """Baixa as 3 fontes e devolve o conjunto de channel ids disponiveis."""
    ids = set()
    os.makedirs(cache_dir, exist_ok=True)
    for name, url in EPG_SOURCES.items():
        path = os.path.join(cache_dir, "%s.xml" % name)
        if not os.path.exists(path) or os.path.getsize(path) < 1000:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=90) as resp:
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


def parse_entries(path):
    """Extrai (attrs, nome, url) de cada #EXTINF do arquivo."""
    entries = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        lines = fh.read().splitlines()
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
        entries.append((m.group("attrs"), m.group("name").strip(), url))
        i += 1
    return entries


def resolve_tvg_id(name, available):
    """Descobre o tvg-id correto a partir do nome do canal."""
    low = name.lower()
    for pattern, forced in RULES:
        if not re.search(pattern, low, re.I):
            continue
        if forced is None:
            return None
        if forced in available:
            return forced
    return None


def main():
    print("Fontes EPG:")
    available = download_epg_ids(os.path.join(BASE, ".epg_cache"))

    source = None
    entries = []
    for cand in CANDIDATES:
        path = os.path.join(BASE, cand)
        if not os.path.exists(path):
            continue
        found = parse_entries(path)
        if len(found) > len(entries):
            source, entries = cand, found
    if not entries:
        print("ERRO: nenhum canal encontrado nas versoes de backup.")
        return 1

    print("\nFonte dos canais: %s (%d canais)" % (source, len(entries)))

    stamp = time.strftime("%Y%m%d_%H%M%S")
    shutil.copy2(LISTA, "%s.bak.pre_urltvg_tvgid_%s" % (LISTA, stamp))
    print("Backup: lista1.m3u.bak.pre_urltvg_tvgid_%s" % stamp)

    out = [HEADER]
    sem_id = []
    for attrs, name, url in entries:
        if not url:
            continue
        old = dict(ATTR_RE.findall(attrs))
        tvg_id = resolve_tvg_id(name, available)
        if tvg_id is None:
            sem_id.append(name)

        clean = name.split("|")[0].strip()
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

    print("\nCanais escritos: %d" % ((len(out) - 1) // 2))
    if sem_id:
        print("Sem tvg-id (nao existem nas 3 fontes): %s" % "; ".join(sem_id))
    return 0


if __name__ == "__main__":
    sys.exit(main())
