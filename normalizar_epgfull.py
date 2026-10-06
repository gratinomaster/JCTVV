#!/usr/bin/env python3
"""Normaliza EPGFULL.xml.gz: um unico fuso horario e nenhuma grade sobreposta.

Fontes distintas gravam o mesmo canal em fusos diferentes (ex.: +0000 e -0500).
Depois da conversao para o mesmo instante absoluto os horarios batem, e o
resultado sao dois programas comecando no mesmo minuto, o que quebra a grade.
Aqui tudo vira UTC (+0000) e, por canal, fica apenas a cadeia sem sobreposicao.

Uso:
    python3 normalizar_epgfull.py
"""
import copy
import gzip
import os
import re
import shutil
import sys
import time
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime, timedelta

ARQUIVO = "EPGFULL.xml.gz"
STAMP = re.compile(r"^(\d{14})\s*([+-]\d{4})?$")


def log(msg):
    print(msg, flush=True)


def para_utc(valor):
    """'20261006013000 -0500' -> datetime UTC. None se o formato nao bate."""
    m = STAMP.match((valor or "").strip())
    if not m:
        return None
    dt = datetime.strptime(m.group(1), "%Y%m%d%H%M%S")
    if m.group(2):
        sinal = 1 if m.group(2)[0] == "+" else -1
        dt -= timedelta(hours=int(m.group(2)[1:3]), minutes=int(m.group(2)[3:5]))
    return dt


def para_stamp(dt):
    return dt.strftime("%Y%m%d%H%M%S +0000")


def main():
    if not os.path.exists(ARQUIVO):
        log(f"ERRO: {ARQUIVO} nao existe")
        return 1

    with gzip.open(ARQUIVO, "rb") as fh:
        bruto = fh.read()
    raiz = ET.fromstring(bruto)
    canais = raiz.findall("channel")
    programas = raiz.findall("programme")
    log("=" * 66)
    log("1. LEITURA")
    log("=" * 66)
    log(f"   {ARQUIVO} ......... {len(bruto):,} bytes XML / {os.path.getsize(ARQUIVO):,} gzip")
    log(f"   canais ............. {len(canais)}")
    log(f"   programas .......... {len(programas)}")

    fusos = Counter()
    for prog in programas:
        fusos[(prog.get("start") or "")[-5:].strip() or "sem fuso"] += 1
    log(f"   fusos na entrada ... {dict(sorted(fusos.items(), key=lambda kv: -kv[1]))}")

    log("")
    log("=" * 66)
    log("2. CONVERSAO PARA UTC")
    log("=" * 66)
    por_canal = defaultdict(list)
    invalidos = 0
    for prog in programas:
        inicio = para_utc(prog.get("start"))
        fim = para_utc(prog.get("stop"))
        if inicio is None or fim is None or fim <= inicio:
            invalidos += 1
            continue
        por_canal[prog.get("channel")].append((inicio, fim, prog))
    log(f"   horarios validos ... {sum(len(v) for v in por_canal.values())}")
    log(f"   descartados ........ {invalidos} (stop <= start ou formato invalido)")

    log("")
    log("=" * 66)
    log("3. REMOCAO DE SOBREPOSICOES")
    log("=" * 66)
    removidos = Counter()
    for canal in sorted(por_canal):
        itens = por_canal[canal]
        # desempate: mesmo inicio -> fica o programa do fuso mais frequente
        peso = Counter((prog.get("start") or "")[-5:].strip() for _, _, prog in itens)
        itens.sort(key=lambda it: (it[0], -peso[(it[2].get("start") or "")[-5:].strip()],
                                   it[1]))
        mantidos, ultimo_fim = [], None
        for inicio, fim, prog in itens:
            if ultimo_fim is not None and inicio < ultimo_fim:
                removidos[canal] += 1
                continue
            mantidos.append((inicio, fim, prog))
            ultimo_fim = fim
        por_canal[canal] = mantidos

    total_removidos = sum(removidos.values())
    if removidos:
        log(f"   canais afetados .... {len(removidos)}")
        for canal in sorted(removidos, key=lambda c: -removidos[c]):
            kept = len(por_canal[canal])
            log(f"     {canal:<58} -{removidos[canal]:>4}  (resta {kept})")
    log(f"   programas removidos {total_removidos}")

    log("")
    log("=" * 66)
    log("4. GRAVACAO")
    log("=" * 66)
    raiz_novo = ET.Element("tv", raiz.attrib)
    for canal in canais:
        raiz_novo.append(canal)
    gravados = 0
    for canal in sorted(por_canal):
        for inicio, fim, prog in por_canal[canal]:
            novo = copy.deepcopy(prog)
            novo.set("start", para_stamp(inicio))
            novo.set("stop", para_stamp(fim))
            raiz_novo.append(novo)
            gravados += 1

    ET.indent(raiz_novo, space="  ")
    corpo = ET.tostring(raiz_novo, encoding="utf-8", xml_declaration=True)

    backup = f"{ARQUIVO}.bak.{time.strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(ARQUIVO, backup)
    log(f"   backup ............. {backup}")

    tmp = ARQUIVO + ".tmp"
    with gzip.GzipFile(tmp, "wb", compresslevel=9, mtime=0) as fh:
        fh.write(corpo)
    with gzip.open(tmp, "rb") as fh:
        if fh.read() != corpo:
            os.remove(tmp)
            log("   ERRO: verificacao gzip falhou")
            return 1
    os.replace(tmp, ARQUIVO)
    log(f"   canais ............. {len(canais)}")
    log(f"   programas .......... {gravados}")
    log(f"   {ARQUIVO} .......... {os.path.getsize(ARQUIVO):,} bytes gzip / {len(corpo):,} XML")

    fusos_novo = Counter()
    for prog in raiz_novo.findall("programme"):
        fusos_novo[(prog.get("start") or "")[-5:]] += 1
    log(f"   fusos na saida ..... {dict(fusos_novo)}")

    log("")
    log("=" * 66)
    log("RESUMO")
    log("=" * 66)
    log(f"   programas antes .... {len(programas)}")
    log(f"   programas depois ... {gravados}")
    log(f"   sobreposicoes ....... {total_removidos} removidas, 0 restantes")
    log(f"   fusos .............. {len(fusos_novo)} (UTC)")

    # conferencia final independente
    ultimo = {}
    conflitos = 0
    for prog in raiz_novo.findall("programme"):
        canal = prog.get("channel")
        inicio = para_utc(prog.get("start"))
        if ultimo.get(canal) is not None and inicio < ultimo[canal]:
            conflitos += 1
        ultimo[canal] = para_utc(prog.get("stop"))
    log(f"   revisao final ...... {conflitos} sobreposicoes")
    return 1 if conflitos else 0


if __name__ == "__main__":
    sys.exit(main())
