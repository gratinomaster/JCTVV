#!/usr/bin/env python3
"""Corrige o lista1.m3u: header url-tvg e tvg-ids validos contra as 3 fontes EPG."""
import datetime
import os
import re
import shutil
import ssl
import time
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET

M3U = "lista1.m3u"
BASE = "https://github.com/limaalef/BrazilTVEPG/raw/refs/heads/main/"
EPG_URLS = [BASE + "globo.xml", BASE + "claro.xml", BASE + "vivoplay.xml"]
CACHE = "/tmp/opencode/epg_cache"
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE


def norm(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", s.lower())


def fetch(url):
    path = os.path.join(CACHE, url.rsplit("/", 1)[-1])
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return open(path, encoding="utf-8", errors="ignore").read()
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60, context=SSL_CTX) as r:
                data = r.read().decode("utf-8", errors="ignore")
            os.makedirs(CACHE, exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(data)
            return data
        except Exception as exc:
            if attempt == 2:
                print("  ERRO ao baixar %s: %s" % (url, exc))
                return None
            time.sleep(3)
    return None


def load_epg_ids():
    """Retorna {id: [display-names]} unindo as 3 fontes."""
    canais = {}
    for url in EPG_URLS:
        xml = fetch(url)
        if not xml:
            continue
        try:
            root = ET.fromstring(xml)
        except Exception as exc:
            print("  XML invalido em %s: %s" % (url, exc))
            continue
        n = 0
        for ch in root.findall(".//channel"):
            cid = ch.get("id")
            if not cid:
                continue
            nomes = [e.text or "" for e in ch.findall("display-name")]
            canais.setdefault(cid, [])
            for nome in nomes:
                if nome not in canais[cid]:
                    canais[cid].append(nome)
            n += 1
        print("  %-12s %4d canais" % (url.rsplit("/", 1)[-1], n))
    return canais


def melhor_id(titulo, nome_attr, canais):
    """Procura um id do EPG que case com o canal. Retorna (id|None, motivo)."""
    for candidato, origem in ((titulo, "titulo"), (nome_attr, "tvg-name")):
        if not candidato:
            continue
        alvo = norm(candidato)
        if not alvo:
            continue
        for cid in canais:
            if norm(cid) == alvo:
                return cid, "exato via %s" % origem
        for cid, nomes in canais.items():
            if any(norm(x) == alvo for x in nomes):
                return cid, "display-name via %s" % origem
        for cid in canais:
            if alvo in norm(cid):
                return cid, "parcial via %s" % origem
        for cid, nomes in canais.items():
            if any(alvo in norm(x) or norm(x) in alvo for x in nomes if norm(x)):
                return cid, "contido via %s" % origem
    return None, "sem correspondencia nas 3 fontes EPG"


def main():
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = "%s.bak.pre_epg_ids_%s" % (M3U, ts)
    shutil.copy2(M3U, bak)
    print("Backup: %s" % bak)

    print("\nFontes EPG:")
    canais = load_epg_ids()
    print("  Total de ids unicos: %d\n" % len(canais))

    linhas = open(M3U, encoding="utf-8", errors="ignore").read().split("\n")

    header = '#EXTM3U url-tvg="%s" x-tvg-url="%s"' % (
        " ".join(EPG_URLS),
        ",".join(EPG_URLS),
    )

    saida = [header]
    relatorio = []
    i = 1 if linhas and linhas[0].startswith("#EXTM3U") else 0
    while i < len(linhas):
        linha = linhas[i]
        if linha.startswith("#EXTINF"):
            attrs, _, titulo = linha.partition(",")
            m = re.search(r'tvg-name="([^"]*)"', attrs)
            nome_attr = m.group(1) if m else ""
            m = re.search(r'tvg-id="([^"]*)"', attrs)
            id_atual = m.group(1) if m else ""
            if id_atual in canais:
                novo, motivo = id_atual, "atual valido nas 3 fontes EPG"
            else:
                novo, motivo = melhor_id(titulo, nome_attr, canais)

            novo_attrs = re.sub(r'\s*tvg-id="[^"]*"', "", attrs).rstrip()
            if novo:
                novo_attrs += ' tvg-id="%s"' % novo
            relatorio.append({
                "canal": titulo.strip(),
                "tvg_id_anterior": id_atual,
                "tvg_id_novo": novo or "",
                "motivo": motivo,
            })
            saida.append(novo_attrs + "," + titulo)
            i += 1
            if i < len(linhas) and linhas[i].strip() and not linhas[i].startswith("#"):
                saida.append(linhas[i].strip())
                i += 1
            continue
        if linha.strip():
            saida.append(linha.rstrip())
        i += 1

    with open(M3U, "w", encoding="utf-8") as fh:
        fh.write("\n".join(saida).rstrip("\n") + "\n")

    ok = sum(1 for r in relatorio if r["tvg_id_novo"])
    print("Canais: %d | com tvg-id valido: %d | sem match: %d"
          % (len(relatorio), ok, len(relatorio) - ok))
    for r in relatorio:
        print("  %-32s %-12s -> %-12s %s"
              % (r["canal"][:32], r["tvg_id_anterior"] or "-",
                 r["tvg_id_novo"] or "(removido)", r["motivo"]))

    with open("relatorio_lista1_epg.txt", "w", encoding="utf-8") as fh:
        fh.write("lista1.m3u - correcao de url-tvg e tvg-ids (%s)\n" % ts)
        fh.write("Fontes: %s\n\n" % ", ".join(EPG_URLS))
        for r in relatorio:
            fh.write("%s | %s -> %s | %s\n"
                     % (r["canal"], r["tvg_id_anterior"] or "-",
                        r["tvg_id_novo"] or "(removido)", r["motivo"]))
    print("\nRelatorio: relatorio_lista1_epg.txt")


if __name__ == "__main__":
    main()
