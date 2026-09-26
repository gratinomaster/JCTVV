#!/usr/bin/env python3
"""Teste independente do EPGFULL.xml.gz gerado a partir do NEWSWORLDNOVOS.m3u."""
import gzip
import io
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timedelta, timezone

M3U = "NEWSWORLDNOVOS.m3u"
EPG = "EPGFULL.xml.gz"

falhas = []


def check(ok, msg, detalhe=""):
    print(("  [OK]   " if ok else "  [FALHA]") + " " + msg + ((" -> " + detalhe) if detalhe else ""))
    if not ok:
        falhas.append(msg)
    return ok


print("=" * 72)
print("1. INTEGRIDADE DO ARQUIVO")
print("=" * 72)

check(os.path.exists(EPG), f"{EPG} existe")
if not os.path.exists(EPG):
    sys.exit(1)

sz_gz = os.path.getsize(EPG)
try:
    with gzip.open(EPG, "rb") as f:
        raw = f.read()
except Exception as e:
    print(f"  [FALHA] gzip corrompido: {e}")
    sys.exit(1)

check(len(raw) > 0, "gzip integro e descompacta", f"{sz_gz:,} B gz -> {len(raw):,} B xml")
check(raw.lstrip().startswith(b"<?xml"), "declaracao XML presente")

try:
    root = ET.fromstring(raw)
    ok_xml = True
except Exception as e:
    ok_xml = False
    print(f"  [FALHA] XML malformado: {e}")

check(ok_xml, "XML bem formado (parseavel por ElementTree)")
if not ok_xml:
    sys.exit(1)

print()
print("=" * 72)
print("2. CANAIS DO EPG x CANAIS DO .m3u")
print("=" * 72)

m3u_ids, m3u_names = set(), {}
with open(M3U, encoding="utf-8", errors="replace") as f:
    for line in f:
        if not line.startswith("#EXTINF"):
            continue
        m = re.search(r'tvg-id="([^"]*)"', line)
        tid = m.group(1).strip() if m else ""
        if tid:
            m3u_ids.add(tid)
            m3u_names[tid] = line.split(",")[-1].strip()

epg_channels = root.findall("channel")
epg_ids = [c.get("id", "") for c in epg_channels]
epg_id_set = set(epg_ids)

print(f"  .m3u: {len(m3u_ids)} tvg-id distintos em {M3U}")
print(f"  .epg: {len(epg_id_set)} canais distintos em {EPG}")
print()

extras = sorted(epg_id_set - m3u_ids)
faltando = sorted(m3u_ids - epg_id_set)

check(not extras, "nenhum canal no EPG esta fora do .m3u",
      "OK - todos os canais do EPG existem no .m3u" if not extras else f"EXTRAS: {extras}")
check(len(epg_ids) == len(epg_id_set), "sem canais duplicados no EPG",
      f"{len(epg_ids)} elementos <channel>")
check(not faltando, "todos os tvg-id do .m3u tem <channel> no EPG",
      "OK - 100% de cobertura" if not faltando else f"FALTAM {len(faltando)}: {faltando}")

sem_nome = [c.get("id") for c in epg_channels
            if c.find("display-name") is None or not (c.find("display-name").text or "").strip()]
check(not sem_nome, "todo <channel> tem <display-name>",
      "OK" if not sem_nome else f"{len(sem_nome)} sem display-name")

print()
print("=" * 72)
print("3. PROGRAMAS: REFERENCIAS E COBERTURA")
print("=" * 72)

programmes = root.findall("programme")
print(f"  Total de <programme>: {len(programmes)}")

orfaos = sorted({p.get("channel", "") for p in programmes} - epg_id_set)
check(not orfaos, "todo <programme> aponta para um <channel> existente",
      "OK - sem referencias orfas" if not orfaos else f"ORFAS: {orfaos}")

sem_titulo = sum(1 for p in programmes
                 if p.find("title") is None or not (p.find("title").text or "").strip())
check(sem_titulo == 0, "todo <programme> tem <title> com texto",
      "OK" if sem_titulo == 0 else f"{sem_titulo} sem titulo")


def parse_dt(s):
    return datetime.strptime(s[:14], "%Y%m%d%H%M%S")


invalidos = 0
datas = Counter()
com_prog = set()
for p in programmes:
    try:
        st, sp = p.get("start", ""), p.get("stop", "")
        dt = parse_dt(st)
        if dt > parse_dt(sp):
            invalidos += 1
            continue
        datas[dt.date().isoformat()] += 1
        com_prog.add(p.get("channel"))
    except Exception:
        invalidos += 1

check(invalidos == 0, "todas as datas start/stop sao validas e stop > start",
      "OK" if invalidos == 0 else f"{invalidos} registros invalidos")

print()
print("  Distribuicao por dia:")
for d in sorted(datas):
    print(f"    {d}: {datas[d]:>5} programas")

print()
print("=" * 72)
print("4. TESTE DE HOJE E AMANHA (requisito principal)")
print("=" * 72)

agora = datetime.now(timezone.utc).replace(tzinfo=None)
hoje = agora.date()
amanha = hoje + timedelta(days=1)

hoje_canais, amanha_canais = set(), set()
hoje_progs, amanha_progs = [], []
for p in programmes:
    try:
        d = parse_dt(p.get("start", "")).date()
    except Exception:
        continue
    if d == hoje:
        hoje_canais.add(p.get("channel"))
        hoje_progs.append(p)
    elif d == amanha:
        amanha_canais.add(p.get("channel"))
        amanha_progs.append(p)

print(f"  Agora (UTC): {agora:%Y-%m-%d %H:%M}")
print(f"  Hoje  = {hoje}")
print(f"  Amanha = {amanha}")
print()
print(f"  HOJE   -> {len(hoje_progs):>5} programas em {len(hoje_canais):>3} canais")
print(f"  AMANHA -> {len(amanha_progs):>5} programas em {len(amanha_canais):>3} canais")

check(len(hoje_progs) > 0, "tem programas para HOJE", f"{len(hoje_progs)} programas")
check(len(amanha_progs) > 0, "tem programas para AMANHA", f"{len(amanha_progs)} programas")
check(len(hoje_canais) > 0, "tem canais com programacao hoje", f"{len(hoje_canais)} canais")
check(len(amanha_canais) > 0, "tem canais com programacao amanha", f"{len(amanha_canais)} canais")

# cobertura dos canais principais (noticias)
principais = ["Telemundo.mx", "TN.ar", "C5N.ar", "Telefe.ar", "Mega.cl", "Mega2.cl",
              "T13.cl", "Chilevision.cl", "Telemax.ar", "AmericaTV.ar", "כאן.11.il",
              "מכאן.il", "24/7CanaldeNoticias.ar", "CNN", "France24enEspanol.ar"]
print()
print("  Cobertura de canais-chave:")
for cid in principais:
    if cid in m3u_ids:
        h = "HOJE " if cid in hoje_canais else "  -  "
        a = "AMANHA" if cid in amanha_canais else "  -  "
        print(f"    [{h}][{a}] {m3u_names.get(cid, cid)} ({cid})")

# spot check: agenda de hoje de alguns canais
print()
print("  Amostra da programacao de HOJE (3 canais):")
for cid in sorted(hoje_canais)[:3]:
    progs = sorted((p for p in hoje_progs if p.get("channel") == cid),
                   key=lambda p: p.get("start"))
    print(f"    >> {m3u_names.get(cid, cid)} [{cid}] - {len(progs)} programas")
    for p in progs[:4]:
        t = (p.findtext("title") or "").strip()
        s = p.get("start")[8:12]
        e = p.get("stop")[8:12]
        cat = (p.findtext("category") or "").strip()
        print(f"       {s}-{e}  {t[:70]}{' [' + cat + ']' if cat else ''}")

print()
print("=" * 72)
print("RESUMO")
print("=" * 72)
print(f"  Arquivo .......: {EPG} ({sz_gz:,} bytes)")
print(f"  XML cru .......: {len(raw):,} bytes")
print(f"  Canais ........: {len(epg_id_set)} (todos do .m3u, zero extras)")
print(f"  Programas .....: {len(programmes)}")
print(f"  Cobertura hoje : {len(hoje_canais)}/{len(epg_id_set)} canais")
print(f"  Cobertura amanha: {len(amanha_canais)}/{len(epg_id_set)} canais")
print(f"  Canais sem EPG : {len(epg_id_set - com_prog)}")
print()

if falhas:
    print(f"  RESULTADO: {len(falhas)} VERIFICACAO(OES) FALHARAM")
    for x in falhas:
        print(f"    - {x}")
    sys.exit(1)

print("  RESULTADO: TODAS AS VERIFICACOES PASSARAM - EPG FUNCIONANDO")
sys.exit(0)
