#!/usr/bin/env python3
"""Validacao independente da lista5.m3u gravada: estrutura, logos, EPG, streams e AV."""
import concurrent.futures
import gzip
import os
import re
import sys
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from urllib.parse import urlparse

import requests

import l5_20261004_final as F

ARQUIVO = "lista5.m3u"
HOJE = date.today()
DIAS = [f"{(HOJE + timedelta(days=i)).strftime('%Y%m%d')}" for i in range(3)]


def parse(path):
    """Parser proprio: devolve (cabecalho, entradas) exigindo #EXTINF antes de cada URL."""
    cabecalho = ""
    entradas = []
    extinf = None
    problemas = []
    with open(path, encoding="utf-8") as f:
        for n, raw in enumerate(f, 1):
            linha = raw.strip()
            if not linha:
                continue
            if linha.startswith("#EXTM3U"):
                cabecalho = linha
                continue
            if linha.startswith("#EXTINF:"):
                extinf = (n, linha)
                continue
            if linha.startswith("#"):
                continue
            if linha.startswith("http://") or linha.startswith("https://"):
                if extinf is None:
                    problemas.append(f"linha {n}: URL sem #EXTINF acima -> {linha[:60]}")
                    entradas.append({"linha": n, "extinf": "", "url": linha})
                else:
                    entradas.append({"linha": n, "extinf": extinf[1], "url": linha})
                extinf = None
                continue
            if extinf is None:
                problemas.append(f"linha {n}: texto solto sem #EXTINF -> {linha[:40]}")
            extinf = None
    return cabecalho, entradas, problemas


def attr(extinf, nome):
    m = re.search(nome + r'="([^"]*)"', extinf)
    return m.group(1) if m else ""


def confere_epg(caminho, ids):
    """Baixa/usa o EPG e devolve {id: dias_cobertos}."""
    cache = "/tmp/opencode/epg/val_" + re.sub(r"[^A-Za-z0-9]+", "_", caminho)[-60:] + ".gz"
    if not os.path.exists(cache):
        r = requests.get(caminho, headers=F.H, timeout=(15, 900))
        r.raise_for_status()
        open(cache, "wb").write(r.content)
    alvo = set(ids.values())
    dias = {i: set() for i in alvo}
    with gzip.open(cache, "rb") as f:
        for _, el in ET.iterparse(f, events=("end",)):
            if el.tag == "programme":
                ch = el.get("channel")
                if ch in dias:
                    dias[ch].add((el.get("start") or "")[:8])
                el.clear()
            elif el.tag == "channel":
                el.clear()
    return dias


def main():
    print("=" * 96)
    print("VALIDACAO FINAL DO ARQUIVO GRAVADO -", ARQUIVO, HOJE.isoformat())
    print("=" * 96)
    cabecalho, entradas, problemas = parse(ARQUIVO)
    erros = list(problemas)

    print(f"\n[1] ESTRUTURA")
    print(f"   entradas: {len(entradas)}")
    m = re.search(r'url-tvg="([^"]*)"', cabecalho) or re.search(r"x-tvg-url=\"([^\"]*)\"", cabecalho)
    fontes_epg = m.group(1).split() if m else []
    print(f"   #EXTM3U: {cabecalho[:150]}")
    print(f"   fontes EPG declaradas: {fontes_epg}")
    if not fontes_epg:
        erros.append("cabecalho sem url-tvg")
    if not cabecalho.startswith("#EXTM3U"):
        erros.append("primeira linha nao e #EXTM3U")

    print(f"\n[2] METADADOS / LOGOS")
    logos = {}
    ids_por_canal = {}
    for e in entradas:
        nome = e["extinf"].split(",")[-1].strip()
        tvgid = attr(e["extinf"], "tvg-id")
        logo = attr(e["extinf"], "tvg-logo")
        grupo = attr(e["extinf"], "group-title")
        if not tvgid:
            erros.append(f"{nome}: sem tvg-id")
        if not grupo:
            erros.append(f"{nome}: sem group-title")
        if not logo:
            erros.append(f"{nome}: sem tvg-logo")
            logos[nome] = (False, "ausente")
        else:
            logos[nome] = F.testa_logo(logo)
        if "imgur" in logo.lower():
            erros.append(f"{nome}: logo no imgur")
        if not urlparse(logo).path.lower().endswith((".jpg", ".jpeg")):
            erros.append(f"{nome}: logo nao termina em .jpg")
        ids_por_canal[nome] = tvgid
        print(f"   {nome:18} tvg-id={tvgid:20} grupo={grupo:12} logo={logos[nome][1]}")

    print(f"\n[3] FONTES DE EPG (cobertura hoje/amanha/+2)")
    cobertura = {}
    for fonte in fontes_epg:
        try:
            dias = confere_epg(fonte, ids_por_canal)
        except Exception as e:
            erros.append(f"EPG {fonte}: download falhou ({type(e).__name__})")
            print(f"   FALHA {fonte} ({type(e).__name__})")
            continue
        for nome, tvgid in ids_por_canal.items():
            cob = [d for d in DIAS if d in dias.get(tvgid, set())]
            cobertura[(fonte, nome)] = cob
            marca = "OK  " if len(cob) == 3 else "PARCIAL"
            print(f"   {marca} {fonte.split('/')[-1]:26} {nome:18} {tvgid:20} {len(cob)}/3 {cob}")
            if len(cob) < 3:
                erros.append(f"{nome}: EPG {fonte} sem guia para {cob}")

    print(f"\n[4] STREAMS (novo teste, ao vivo)")
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        res = dict(zip([e["url"] for e in entradas],
                       ex.map(F.testa_stream, [e["url"] for e in entradas])))
    for e in entradas:
        nome = e["extinf"].split(",")[-1].strip()
        status, why = res[e["url"]]
        marca = {"video+audio": "OK  ", "video_sem_audio": "SOM ", "falha": "FALHA"}[status]
        print(f"   {marca} {nome:18} {why}")
        if status == "falha":
            erros.append(f"{nome}: stream falhou ({why})")

    print(f"\n[5] ANTI-VIRUS")
    bl_urls, bl_hosts = F.carrega_blocklists()
    for e in entradas:
        nome = e["extinf"].split(",")[-1].strip()
        ok, achados = F.antvirus(e["url"], bl_urls, bl_hosts)
        print(f"   {'LIMPO' if ok else 'SUSPEITO':9} {nome:18} "
              f"{'nada encontrado' if ok else '; '.join(achados)}")
        if not ok:
            erros.append(f"{nome}: antivirus reprovou ({'; '.join(achados)})")

    print("\n" + "=" * 96)
    if erros:
        print(f"RESULTADO: {len(erros)} PROBLEMA(S):")
        for e in erros:
            print("  -", e)
    else:
        print("RESULTADO: TUDO OK - estrutura, logos .jpg, EPG de 3 dias, streams e AV aprovados")
    print("=" * 96)
    return 1 if erros else 0


if __name__ == "__main__":
    sys.exit(main())