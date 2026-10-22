#!/usr/bin/env python3
"""Corrige o lista1.m3u:

- Garante o cabecalho #EXTM3U com url-tvg e x-tvg-url apontando para as 3
  fontes XMLTV do BrazilTVEPG (globo, claro, vivoplay).
- Corrige os tvg-id usando SOMENTE ids que existem de fato nas 3 fontes
  XMLTV, verificados contra o XML baixado do repositorio.
- Cada canal recebe o id da sua propria rede:
    * GE (SD)  -> ge-tv       (globo.xml)
    * GE HD    -> GE TV HD   (claro.xml)
    * G1 *     -> globonews  (globo.xml) - regional e nacional sao a mesma
                  rede (GloboNews), entao todas as reacoes ficam com a
                  programacao nacional.
    * CBN *    -> sem tvg-id (CBN nao existe nas 3 fontes)
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

URL_TVG = " ".join(EPG_SOURCES.values())
X_TVG_URL = ",".join(EPG_SOURCES.values())
HEADER = '#EXTM3U url-tvg="%s" x-tvg-url="%s"' % (URL_TVG, X_TVG_URL)

# tvg-id por nome de canal (comparacao case-insensitive).
EXPLICIT = {
    "ge": "ge-tv",
    "ge hd": "GE TV HD",
    "g1 ao vivo": "globonews",
    "g1 rio de janeiro": "globonews",
    "g1 rio grande do sul": "globonews",
    "g1 espirito santo": "globonews",
    "g1 triangulo mineiro": "globonews",
    "g1 triangulo mineiro - uberaba": "globonews",
    "g1 amapa": "globonews",
    "g1 acre": "globonews",
    "g1 para": "globonews",
    "cbn sao paulo": None,
    "cbn rio de janeiro": None,
}

# Regras genericas (aplicadas quando o nome nao esta em EXPLICIT).
FALLBACK = [
    (re.compile(r"cbn", re.I), None),
    (re.compile(r"\bg1\b|globo\s*news|globonews", re.I), "globonews"),
    (re.compile(r"\bge\b", re.I), "ge-tv"),
    (re.compile(r"sportv", re.I), "sportv"),
    (re.compile(r"\bglobo\b", re.I), "tv-globo"),
]

EXTINF_RE = re.compile(r'^#EXTINF:(?P<dur>-?[\d.]+)\s*(?P<attrs>.*?),(?P<name>.*)$')
ATTR_RE = re.compile(r'([\w-]+)="([^"]*)"')


def norm(name):
    """Normaliza o nome para comparacao (sem acento, minusculo, espacos)."""
    import unicodedata

    txt = unicodedata.normalize("NFKD", name)
    txt = "".join(c for c in txt if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", txt.lower()).strip()


def load_ids(download=True):
    """Baixa (ou reaproveita o cache) as 3 fontes e devolve os ids validos."""
    os.makedirs(CACHE, exist_ok=True)
    ids = set()
    for name, url in EPG_SOURCES.items():
        path = os.path.join(CACHE, "%s.xml" % name)
        if download and (not os.path.exists(path) or os.path.getsize(path) < 1000):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=120) as resp:
                    data = resp.read()
                with open(path, "wb") as fh:
                    fh.write(data)
                print("  %-8s baixado (%d bytes)" % (name, len(data)))
            except Exception as exc:  # noqa: BLE001
                print("  ! %s.xml nao baixado: %s" % (name, exc))
        if not os.path.exists(path):
            print("  ! %s.xml ausente" % name)
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
    """Extrai (attrs, nome, url) de cada #EXTINF do arquivo."""
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
    """Descobre o tvg-id correto (validado contra as 3 fontes XMLTV)."""
    key = norm(name)
    if key in EXPLICIT:
        candidate = EXPLICIT[key]
        if candidate is None or candidate in ids:
            return candidate
        return None
    for pattern, tvg_id in FALLBACK:
        if pattern.search(name):
            if tvg_id is None or tvg_id in ids:
                return tvg_id
            return None
    return None


def main():
    print("Fontes EPG:")
    ids = load_ids()
    if not ids:
        print("ERRO: nenhum id disponivel")
        return 1

    entries = parse(LISTA)
    print("\nCanais na lista: %d" % len(entries))

    stamp = time.strftime("%Y%m%d_%H%M%S")
    backup = "%s.bak.pre_epg_ids_%s" % (LISTA, stamp)
    shutil.copy2(LISTA, backup)
    print("Backup: %s" % os.path.basename(backup))

    out = [HEADER]
    changes = []
    sem_id = []
    for old, name, url in entries:
        if not url:
            continue
        clean = name.split("|")[0].strip()
        tvg_id = resolve(clean, ids)
        antigo = old.get("tvg-id", "").strip()
        if tvg_id != antigo:
            changes.append((clean, antigo, tvg_id))
        if not tvg_id and clean not in sem_id:
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
    if changes:
        print("\ntvg-id alterado:")
        for clean, antigo, novo in changes:
            print("  %-34s %-12s -> %s" % (clean, antigo or "(vazio)", novo or "(vazio)"))
    if sem_id:
        print("\nSem tvg-id: %s" % "; ".join(sem_id))
    return 0


if __name__ == "__main__":
    sys.exit(main())
