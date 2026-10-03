#!/usr/bin/env python3
"""Filtra o EPGFULL para conter apenas os canais presentes no NEWSWORLDNOVOS.m3u.

Uso:
    python3 filtrar_epgfull.py

Comportamento:
  - baixa o .m3u de referencia do GitHub (usa o arquivo local se o download falhar)
  - le o EPG de origem (EPGFULL.xml.gz, ou EPGFULL.xml como alternativa)
  - mantem apenas <channel> cujo id bate com um tvg-id da .m3u
  - mantem apenas <programme> cujo atributo channel aponte para um canal mantido
  - grava EPGFULL.xml.gz de forma atomica, guardando backup do anterior
"""
import gzip
import os
import re
import shutil
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET

M3U_URL = "https://github.com/gratinomaster/JCTVV/raw/refs/heads/main/NEWSWORLDNOVOS.m3u"
M3U_LOCAL = "NEWSWORLDNOVOS.m3u"
FONTES = ("EPGFULL.xml.gz", "EPGFULL.xml")
SAIDA = "EPGFULL.xml.gz"


def norm(valor):
    return re.sub(r"[\s\-_.]+", "", valor or "").lower()


def log(msg):
    print(msg, flush=True)


def baixar_m3u():
    if os.path.exists(M3U_LOCAL):
        return open(M3U_LOCAL, "rb").read().decode("utf-8", errors="replace"), "local"
    req = urllib.request.Request(M3U_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8", errors="replace"), "GitHub"


def ids_da_m3u(texto):
    """Retorna (ids_exatos, mapa_normalizado->id, nome_do_canal)."""
    exatos, nomes = set(), {}
    for linha in texto.splitlines():
        if not linha.startswith("#EXTINF"):
            continue
        achou = re.search(r'tvg-id="([^"]*)"', linha)
        nome = linha.split(",", 1)[1].strip() if "," in linha else ""
        if not achou:
            continue
        tid = achou.group(1).strip()
        if not tid or tid in ("0", "(no tvg-id)"):
            continue
        exatos.add(tid)
        nomes.setdefault(tid, nome)
    normalizados = {}
    for tid in exatos:
        normalizados.setdefault(norm(tid), tid)
    return exatos, normalizados, nomes


def ler_bruto(caminho):
    if caminho.endswith(".gz"):
        with gzip.open(caminho, "rb") as fh:
            return fh.read()
    with open(caminho, "rb") as fh:
        return fh.read()


def melhor_fonte(exatos, normalizados):
    """Escolhe o EPG de origem que cobre mais canais da .m3u, desempatando por programas."""
    alvo = "|".join(re.escape(t) for t in sorted(exatos | set(normalizados)))
    rx = re.compile(r'channel="(' + alvo + r')"')
    melhor, score = None, (-1, -1)
    for caminho in FONTES:
        if not os.path.exists(caminho):
            continue
        texto = ler_bruto(caminho).decode("utf-8", errors="replace")
        casados = rx.findall(texto)
        n = (len(set(casados)), len(casados))
        log(f"   candidato {caminho:<18} {os.path.getsize(caminho):>12,} B"
            f"  {n[0]:>4} canais com grade  {n[1]:>7,} programas uteis")
        if n > score:
            melhor, score = caminho, n
    return melhor, score


def main():
    log("=" * 70)
    log("1. PLAYLIST DE REFERENCIA")
    log("=" * 70)
    try:
        texto, origem = baixar_m3u()
    except Exception as exc:
        log(f"   ERRO ao obter a .m3u: {exc}")
        return 1
    exatos, normalizados, nomes = ids_da_m3u(texto)
    log(f"   fonte .............. {origem} ({len(texto):,} bytes)")
    log(f"   tvg-id unicos ....... {len(exatos)}")

    log("")
    log("=" * 70)
    log("2. EPG DE ORIGEM")
    log("=" * 70)
    fonte, score = melhor_fonte(exatos, normalizados)
    if not fonte:
        log("   ERRO: nenhum EPG de origem encontrado")
        return 1
    raiz = ET.fromstring(ler_bruto(fonte))
    canais_origem = raiz.findall("channel")
    programas_origem = raiz.findall("programme")
    log(f"   escolhida ........... {fonte} ({os.path.getsize(fonte):,} bytes)")
    log(f"   canais .............. {len(canais_origem)}")
    log(f"   programas ........... {len(programas_origem)}")

    log("")
    log("=" * 70)
    log("3. FILTRAGEM")
    log("=" * 70)
    # canais que só casaram pela versão normalizada são reescritos para o
    # tvg-id exato da .m3u, assim o app casa por igualdade literal
    raiz_novo = ET.Element("tv", raiz.attrib)
    mantidos, ocupados, remapeados, por_norm = set(), set(), {}, set()
    for canal in canais_origem:
        cid = canal.get("id", "")
        destino = cid if cid in exatos else normalizados.get(norm(cid))
        if destino not in exatos or destino in ocupados:
            continue
        if destino != cid:
            canal.set("id", destino)
            remapeados[cid] = destino
            por_norm.add(destino)
        ocupados.add(destino)
        mantidos.add(destino)
        raiz_novo.append(canal)

    log(f"   canais mantidos ..... {len(mantidos)} de {len(canais_origem)}")
    log(f"   canais removidos .... {len(canais_origem) - len(mantidos)}")
    log(f"   ids normalizados .... {len(por_norm)} (canal <- tvg-id da .m3u)")
    log(f"   cobertura .m3u ...... {len(mantidos)}/{len(exatos)} tvg-id presentes")
    faltando = sorted(exatos - mantidos)
    if faltando:
        log(f"   sem <channel> ....... {len(faltando)}: {faltando[:10]}")

    orfas = 0
    for prog in programas_origem:
        cid = prog.get("channel")
        if cid in remapeados:
            cid = remapeados[cid]
            prog.set("channel", cid)
        if cid in mantidos:
            raiz_novo.append(prog)
        else:
            orfas += 1
    programas = raiz_novo.findall("programme")
    log(f"   programas mantidos .. {len(programas)} de {len(programas_origem)}")
    log(f"   programas removidos . {orfas} (canal fora da .m3u)")

    log("")
    log("=" * 70)
    log("4. GRAVACAO")
    log("=" * 70)
    if os.path.exists(SAIDA):
        backup = f"{SAIDA}.bak.{time.strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(SAIDA, backup)
        log(f"   backup do anterior .. {backup}")

    ET.indent(raiz_novo, space="  ")
    corpo = ET.tostring(raiz_novo, encoding="utf-8", xml_declaration=True)
    tmp = SAIDA + ".tmp"
    with gzip.GzipFile(tmp, "wb", compresslevel=9, mtime=0) as fh:
        fh.write(corpo)
    with gzip.open(tmp, "rb") as fh:
        if fh.read() != corpo:
            os.remove(tmp)
            log("   ERRO: verificacao gzip falhou")
            return 1
    os.replace(tmp, SAIDA)
    log(f"   {SAIDA} gravado: {os.path.getsize(SAIDA):,} bytes comprimidos")
    log(f"   XML interno ........ {len(corpo):,} bytes")

    log("")
    log("=" * 70)
    log("RESUMO")
    log("=" * 70)
    log(f"   canais na .m3u ...... {len(exatos)}")
    log(f"   canais no EPG ....... {len(mantidos)} (zero canais extras)")
    log(f"   programas ........... {len(programas)}")
    log("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
