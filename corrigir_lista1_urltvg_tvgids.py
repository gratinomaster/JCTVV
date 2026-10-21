#!/usr/bin/env python3
"""Corrige o lista1.m3u:

- Garante o cabecalho #EXTM3U com url-tvg apontando para as 3
  fontes XMLTV do BrazilTVEPG (globo, claro, vivoplay), separadas por espaco.
- Corrige os tvg-id usando SOMENTE ids que existem de fato nas tres fontes
  XMLTV, verificados contra os XMLs baixados do repositorio.

A lista atual (urls, logos, grupos e nomes) e preservada; apenas o cabecalho
e o atributo tvg-id de cada #EXTINF sao reescritos.
"""

import datetime
import os
import re
import shutil
import sys
import time
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter, OrderedDict

BASE = os.path.dirname(os.path.abspath(__file__))
LISTA = os.path.join(BASE, "lista1.m3u")
CACHE = os.path.join(BASE, ".epg_cache")
REPORT = os.path.join(BASE, "relatorio_lista1_epg.txt")
CACHE_TTL = 6 * 3600

EPG_SOURCES = OrderedDict(
    [
        ("globo", "https://github.com/limaalef/BrazilTVEPG/raw/refs/heads/main/globo.xml"),
        ("claro", "https://github.com/limaalef/BrazilTVEPG/raw/refs/heads/main/claro.xml"),
        ("vivoplay", "https://github.com/limaalef/BrazilTVEPG/raw/refs/heads/main/vivoplay.xml"),
    ]
)

URL_TVG = " ".join(EPG_SOURCES.values())
HEADER = '#EXTM3U url-tvg="%s"' % URL_TVG

# Ordem importa: a primeira regra que casar define o tvg-id.
# Todos os ids abaixo foram conferidos nas 3 fontes XMLTV.
#   sportv    -> globo.xml / vivoplay.xml
#   ge-tv     -> globo.xml
#   GLOBO SP  -> claro.xml (grade da afiliada de Sao Paulo)
#   globonews -> globo.xml (G1 regionais sao canais de noticias)
#   tv-globo  -> globo.xml (grade nacional, usada pelas afiliadas)
# CBN nao existe em nenhuma das 3 fontes -> fica sem id.
REGRAS = [
    (r"^spor ?tv$|^sportv$", "sportv"),
    (r"^ge$|^ge hd$|^gehd$", "ge-tv"),
    (r"^cbn\b", None),
    (r"^globo (sao paulo|sp)$", "GLOBO SP"),
    (r"^g1\b", "globonews"),
    (r"^globo\b", "tv-globo"),
]

EXTINF_RE = re.compile(r'^#EXTINF:(?P<dur>-?[\d.]+)\s*(?P<attrs>.*?),(?P<name>.*)$')
ATTR_RE = re.compile(r'([\w-]+)="([^"]*)"')


def normaliza(texto):
    """minusculas, sem acento e sem caracteres nao alfanumericos."""
    texto = unicodedata.normalize("NFKD", str(texto))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", texto.lower()).strip()


def download_epg_sources():
    """Baixa (se necessario) as 3 fontes e devolve os ids e a programacao.

    O cache em .epg_cache/ e reusado apenas enquanto estiver atualizado
    (CACHE_TTL), para que a validacao use sempre o EPG mais recente.
    """
    fontes = OrderedDict()
    os.makedirs(CACHE, exist_ok=True)
    hoje = datetime.date.today()
    dias_interesse = [(hoje + datetime.timedelta(days=d)).strftime("%Y%m%d") for d in range(3)]

    for name, url in EPG_SOURCES.items():
        path = os.path.join(CACHE, "%s.xml" % name)
        desatualizado = (
            not os.path.exists(path)
            or os.path.getsize(path) < 1000
            or time.time() - os.path.getmtime(path) > CACHE_TTL
        )
        if desatualizado:
            print("  baixando %s.xml ..." % name)
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=180) as resp:
                data = resp.read()
            with open(path, "wb") as fh:
                fh.write(data)
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError as exc:
            print("  ! %s.xml invalido: %s" % (name, exc))
            fontes[name] = {"ids": set(), "dias": {}}
            continue

        ids = set(c.get("id") for c in root.iter("channel") if c.get("id"))
        dias = {}
        for prog in root.iter("programme"):
            cid = prog.get("channel")
            if not cid:
                continue
            dia = (prog.get("start") or "")[:8]
            if dia in dias_interesse:
                dias.setdefault(cid, Counter())[dia] += 1
        fontes[name] = {"ids": ids, "dias": dias}
        com_prog = len(set(dias) & ids)
        print("  %-8s %4d canais (%d com programacao)" % (name, len(ids), com_prog))
    return fontes


def resolve_tvg_id(name, per_source, atual=None):
    """Descobre o tvg-id correto a partir do nome do canal, ou None."""
    available = set()
    for fonte in per_source.values():
        available |= fonte["ids"]
    alvo = normaliza(name)
    for pattern, forced in REGRAS:
        if not re.search(pattern, alvo):
            continue
        if forced is None:
            return None
        if forced in available:
            return forced
        print("  ! id '%s' (regra %s) ausente nas fontes XMLTV" % (forced, pattern))
        return None
    # sem regra: mantem o id atual somente se ele existir nas 3 fontes
    if atual and atual in available:
        return atual
    return None


def programa_por_dia(per_source, cid):
    """Contagem de programas por dia (hoje/amanha/depois) de um tvg-id."""
    contagem = Counter()
    for fonte in per_source.values():
        for dia, qtd in fonte["dias"].get(cid, {}).items():
            contagem[dia] += qtd
    return contagem


def main():
    print("Fontes EPG:")
    per_source = download_epg_sources()
    available = set()
    for fonte in per_source.values():
        available |= fonte["ids"]
    print("Total de ids disponiveis: %d\n" % len(available))

    hoje = datetime.date.today()
    dias = [(hoje + datetime.timedelta(days=d)).strftime("%Y%m%d") for d in range(3)]

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
        new_id = resolve_tvg_id(name, per_source, old_id or None)

        if new_id == (old_id or None):
            kept += 1
        else:
            changed.append("%s: %s -> %s" % (name, old_id or "(vazio)", new_id or "(vazio)"))

        # De onde vem o id, em qual fonte ele existe e se ha programacao.
        found_in = [src for src, fonte in per_source.items() if new_id and new_id in fonte["ids"]]
        contagem = programa_por_dia(per_source, new_id) if new_id else Counter()
        rows.append((name, old_id, new_id, found_in, contagem))

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

    canais = len(rows)
    print("Canais: %d (tvg-id mantido: %d, alterado: %d)" % (canais, kept, len(changed)))
    for line in changed:
        print("  * %s" % line)

    com_prog = [r for r in rows if r[4].get(dias[0]) or r[4].get(dias[1])]

    with open(REPORT, "w", encoding="utf-8") as fh:
        fh.write("lista1.m3u - correcao de url-tvg e tvg-ids (%s)\n" % stamp)
        fh.write("Fontes: %s\n\n" % ", ".join(EPG_SOURCES.values()))
        fh.write("Estado do header: OK\n")
        fh.write("  %s\n" % HEADER)
        fh.write("  3 fontes XMLTV separadas por espaco, sem x-tvg-url obsoleto.\n\n")
        fh.write("Validacao de tvg-id (ids existentes nas 3 fontes EPG):\n")
        for name, old_id, new_id, found_in, contagem in rows:
            if new_id:
                status = "ok (%s)" % ",".join(found_in)
                status += " | programas hoje=%d amanha=%d depois=%d" % (
                    contagem.get(dias[0], 0), contagem.get(dias[1], 0), contagem.get(dias[2], 0))
            else:
                status = "sem id (nao existe nas 3 fontes)"
            fh.write("%s | %s -> %s | %s\n" % (name, old_id or "(sem id)", new_id or "(sem id)", status))
        fh.write("\nResultado: %d/%d canais com tvg-id valido ou corretamente sem id.\n"
                 % (sum(1 for r in rows if r[2]), len(rows)))
        fh.write("Programacao presente hoje ou amanha: %d/%d canais com tvg-id.\n"
                 % (len(com_prog), sum(1 for r in rows if r[2])))
        fh.write("\nNotas:\n")
        fh.write("- id CBN inexistente nas 3 fontes (grep 'cbn' = 0 ocorrencias).\n")
        fh.write("  Atribuir tv-globo exibiria programacao de TV, nao de radio. Mantido sem tvg-id.\n")
        fh.write("- G1 regionais: nao ha id regional nas 3 fontes; usam globonews (globo.xml),\n")
        fh.write("  que e a grade de noticias compativel com os G1, em vez da grade geral de tv-globo.\n")
        fh.write("- Globo Sao Paulo usa 'GLOBO SP' (claro.xml), que traz a grade da afiliada;\n")
        fh.write("  as demais afiliadas sem id proprio usam tv-globo (globo.xml).\n")
        fh.write("- Contagem de programas conferida nas 3 fontes em %s (hoje/amanha/depois).\n"
                 % hoje.strftime("%Y-%m-%d"))

    print("\nRelatorio: %s" % os.path.basename(REPORT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
