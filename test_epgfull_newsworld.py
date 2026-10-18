#!/usr/bin/env python3
"""Testa EPGFULL.xml.gz: integridade, filtragem pelo .m3u e programacao de hoje/amanha.

Saida zero somente se o guia:
  - abre como gzip e e XML valido;
  - contem SOMENTE canais do NEWSWORLDNOVOS.m3u (nada extra);
  - traz todos os tvg-id do .m3u;
  - tem programas para HOJE e para AMANHA.
"""
import gzip
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timedelta, timezone

M3U_URL = "https://github.com/gratinomaster/JCTV/raw/refs/heads/main/NEWSWORLDNOVOS.m3u"
EPG = "EPGFULL.xml.gz"

erros = []


def falha(msg):
    erros.append(msg)
    print(f"  [FALHA] {msg}")


def ok(msg):
    print(f"  [OK] {msg}")


print("=" * 70)
print("1. LISTA .m3u (fonte da verdade)")
print("=" * 70)
req = urllib.request.Request(M3U_URL, headers={"User-Agent": "Mozilla/5.0"})
m3u = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")
ids_m3u = []
for linha in m3u.splitlines():
    if not linha.startswith("#EXTINF"):
        continue
    mt = re.search(r'tvg-id="([^"]*)"', linha)
    if mt and mt.group(1).strip() and mt.group(1).strip() not in ("0", "(no tvg-id)"):
        ids_m3u.append(mt.group(1).strip())
ids_m3u = list(dict.fromkeys(ids_m3u))
print(f"  tvg-id unicos no .m3u: {len(ids_m3u)}")

print()
print("=" * 70)
print("2. INTEGRIDADE DO EPGFULL.xml.gz")
print("=" * 70)
try:
    with gzip.open(EPG, "rb") as f:
        dados = f.read()
    ok(f"gzip valido ({len(dados):,} bytes XML)")
except Exception as e:
    falha(f"gzip invalido: {e}")
    sys.exit(1)

try:
    raiz = ET.fromstring(dados)
    ok("XML bem formado")
except Exception as e:
    falha(f"XML invalido: {e}")
    sys.exit(1)

canais = raiz.findall("channel")
programas = raiz.findall("programme")
ids_epg = [c.get("id", "") for c in canais]
print(f"  canais: {len(ids_epg)} | programas: {len(programas)}")

if raiz.tag != "tv":
    falha(f"raiz deveria ser <tv>, e e <{raiz.tag}>")

print()
print("=" * 70)
print("3. FILTRAGEM: somente canais do .m3u")
print("=" * 70)
extras = sorted(set(ids_epg) - set(ids_m3u))
faltando = sorted(set(ids_m3u) - set(ids_epg))
if extras:
    falha(f"{len(extras)} canais no EPG que nao estao no .m3u: {extras}")
else:
    ok("nenhum canal fora do .m3u")
if faltando:
    falha(f"{len(faltando)} tvg-id do .m3u ausentes no EPG: {faltando}")
else:
    ok(f"todos os {len(ids_m3u)} tvg-id do .m3u estao no EPG")

canais_invalidos = sorted({p.get("channel", "") for p in programas} - set(ids_epg))
if canais_invalidos:
    falha(f"programas apontando para canal inexistente: {canais_invalidos}")
else:
    ok("todo <programme> referencia um <channel> existente")

print()
print("=" * 70)
print("4. PROGRAMACAO DE HOJE E AMANHA")
print("=" * 70)
agora = datetime.now(timezone.utc)
hoje = agora.strftime("%Y%m%d")
amanha = (agora + timedelta(days=1)).strftime("%Y%m%d")
ontem = (agora - timedelta(days=1)).strftime("%Y%m%d")

por_dia = defaultdict(int)
por_dia_canais = defaultdict(set)
amostras = defaultdict(list)
for p in programas:
    dia = p.get("start", "")[:8]
    por_dia[dia] += 1
    por_dia_canais[dia].add(p.get("channel", ""))
    titulo = p.findtext("title") or ""
    if dia in (hoje, amanha) and len(amostras[dia]) < 6:
        amostras[dia].append((p.get("channel", ""), p.get("start", ""),
                              p.get("stop", ""), titulo.strip()))

print(f"  agora (UTC): {agora:%Y-%m-%d %H:%M}")
print(f"  datas no guia: {min(por_dia) if por_dia else '-'} -> "
      f"{max(por_dia) if por_dia else '-'}")
for dia in sorted(por_dia):
    marca = " <- HOJE" if dia == hoje else (" <- AMANHA" if dia == amanha else "")
    print(f"    {dia}: {por_dia[dia]:>5} programas em "
          f"{len(por_dia_canais[dia]):>2} canais{marca}")

if por_dia.get(ontem):
    ok(f"programas de ontem ({ontem}): {por_dia[ontem]} (grade em andamento)")
else:
    print(f"  [INFO] sem programas de ontem ({ontem})")

if por_dia.get(hoje, 0) > 0 and por_dia_canais.get(hoje):
    ok(f"HOJE {hoje}: {por_dia[hoje]} programas em {len(por_dia_canais[hoje])} canais")
else:
    falha(f"sem programas para HOJE ({hoje})")

if por_dia.get(amanha, 0) > 0 and por_dia_canais.get(amanha):
    ok(f"AMANHA {amanha}: {por_dia[amanha]} programas em {len(por_dia_canais[amanha])} canais")
else:
    falha(f"sem programas para AMANHA ({amanha})")

completos = sorted(set(ids_m3u))
grade = {t: (t in por_dia_canais.get(hoje, set()),
             t in por_dia_canais.get(amanha, set())) for t in completos}
ambos = sum(1 for h, a in grade.values() if h and a)
print(f"  canais com grade hoje+amanha: {ambos}/{len(ids_m3u)}")

print()
print("=" * 70)
print("5. AMOSTRA DA GRAVA (como o player le)")
print("=" * 70)
for dia, rotulo in ((hoje, "HOJE"), (amanha, "AMANHA")):
    print(f"  {rotulo} ({dia}):")
    for cid, st, sp, titulo in amostras.get(dia, []):
        print(f"    {cid:<34} {st[8:12]}-{sp[8:12]}  {titulo[:52]}")
    if not amostras.get(dia):
        falha(f"sem amostra de programas para {rotulo}")

print()
print("=" * 70)
print("RESULTADO")
print("=" * 70)
if erros:
    print(f"  {len(erros)} falha(s):")
    for e in erros:
        print(f"   - {e}")
    sys.exit(1)
print("  EPG FUNCIONANDO: somente canais do .m3u, com programacao de hoje e amanha.")
sys.exit(0)
