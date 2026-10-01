#!/usr/bin/env python3
import gzip
import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timedelta

EPG_FILE = "EPGFULL.xml.gz"
M3U_FILE = "NEWSWORLDNOVOS.m3u"
M3U_URL = "https://github.com/gratinomaster/JCTV/raw/refs/heads/main/NEWSWORLDNOVOS.m3u"

falhas = []


def check(ok, label, detalhe=""):
    print(f"  {'OK  ' if ok else 'FALHA'} {label}{(' -> ' + detalhe) if detalhe else ''}")
    if not ok:
        falhas.append(label)
    return ok


def norm(value):
    return re.sub(r"[\s\-_.]+", "", value or "").lower()


def minutes(stamp):
    digits = re.sub(r"[^0-9]", "", stamp or "")
    if len(digits) < 12:
        return None
    return (
        int(digits[0:4]) * 525600
        + int(digits[4:6]) * 43200
        + int(digits[6:8]) * 1440
        + int(digits[8:10]) * 60
        + int(digits[10:12])
    )


print("=" * 66)
print("1. PLAYLIST DE REFERENCIA (M3U)")
print("=" * 66)

try:
    req = urllib.request.Request(M3U_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        m3u_text = resp.read().decode("utf-8", errors="replace")
    print(f"   baixado do GitHub: {len(m3u_text):,} bytes")
except Exception as exc:
    print(f"   download falhou ({exc}), usando {M3U_FILE}")
    with open(M3U_FILE, encoding="utf-8", errors="replace") as handle:
        m3u_text = handle.read()

m3u_ids = []
m3u_info = {}
for line in m3u_text.splitlines():
    if not line.startswith("#EXTINF"):
        continue
    found = re.search(r'tvg-id="([^"]*)"', line)
    name = line.split(",", 1)[1].strip() if "," in line else ""
    if found and found.group(1).strip() not in ("", "0", "(no tvg-id)"):
        tid = found.group(1).strip()
        if tid not in m3u_info:
            m3u_ids.append(tid)
            m3u_info[tid] = name
    else:
        m3u_ids.append(None)
        m3u_info.setdefault(None, name)

m3u_norm = {}
for tid in m3u_ids:
    if tid:
        m3u_norm.setdefault(norm(tid), tid)

print(f"   entradas na M3U .. {len(m3u_ids)}")
print(f"   com tvg-id ....... {sum(1 for t in m3u_ids if t)} ({len(set(t for t in m3u_ids if t))} unicos)")

print()
print("=" * 66)
print("2. INTEGRIDADE DO ARQUIVO")
print("=" * 66)

if not os.path.exists(EPG_FILE):
    print(f"   ERRO: {EPG_FILE} nao existe")
    sys.exit(1)

comprimido = os.path.getsize(EPG_FILE)
try:
    with gzip.open(EPG_FILE, "rb") as handle:
        bruto = handle.read()
    check(True, "gzip integro", f"{comprimido:,} bytes comprimidos -> {len(bruto):,} bytes XML")
except Exception as exc:
    check(False, "gzip integro", str(exc))
    sys.exit(1)

try:
    root = ET.fromstring(bruto)
    check(True, "XML bem formado", f"<tv> com {len(list(root))} elementos")
except ET.ParseError as exc:
    check(False, "XML bem formado", str(exc))
    sys.exit(1)

canais = root.findall("channel")
programas = root.findall("programme")
ids_xml = {c.get("id") for c in canais}

print()
print("=" * 66)
print("3. FILTRAGEM: SÓ CANAIS DA M3U")
print("=" * 66)

extras = sorted(cid for cid in ids_xml if norm(cid) not in m3u_norm)
check(not extras, "nenhum canal fora da M3U", f"{len(extras)} encontrados" if extras else "0")
if extras:
    print(f"      {extras[:20]}")

com_programa = {p.get("channel") for p in programas}
fora = sorted(cid for cid in ids_xml if norm(cid) not in m3u_norm)
print(f"   canais declarados .. {len(ids_xml)} (M3U com tvg-id: {len(m3u_norm)})")
print(f"   canais com grade ... {len(com_programa)}")

faltando = sorted(set(t for t in m3u_ids if t) - ids_xml)
if faltando:
    print(f"   INFO: {len(faltando)} tvg-ids da M3U sem <channel> no EPG: {faltando[:10]}")

orfas = [p for p in programas if p.get("channel") not in ids_xml]
check(not orfas, "programas sem <channel> correspondente", f"{len(orfas)} orfaos" if orfas else "0")

print()
print("=" * 66)
print("4. QUALIDADE DA GRADE")
print("=" * 66)

invalidos = 0
conflitos = 0
ultimo_stop = {}
for prog in programas:
    start = minutes(prog.get("start", ""))
    stop = minutes(prog.get("stop", ""))
    if start is None or stop is None or stop <= start:
        invalidos += 1
        continue
    cid = prog.get("channel")
    anterior = ultimo_stop.get(cid)
    if anterior is not None and start < anterior:
        conflitos += 1
    ultimo_stop[cid] = stop

check(invalidos == 0, "horarios validos (stop > start)", f"{invalidos} invalidos" if invalidos else "todos ok")
check(conflitos == 0, "sem sobreposicao de horarios", f"{conflitos} conflitos" if conflitos else "0")

vazios = [p for p in programas if not (p.findtext("title") or "").strip()]
check(not vazios, "todos os programas tem titulo", f"{len(vazios)} sem titulo" if vazios else "0")

por_dia = defaultdict(int)
canais_por_dia = defaultdict(set)
for prog in programas:
    dia = prog.get("start", "")[:8]
    por_dia[dia] += 1
    canais_por_dia[dia].add(prog.get("channel"))

print(f"   datas presentes: {', '.join(f'{d}({c})' for d, c in sorted(por_dia.items()))}")

print()
print("=" * 66)
print("5. PROGRAMACAO DE HOJE E AMANHA")
print("=" * 66)

now = datetime.now()
hoje = now.strftime("%Y%m%d")
amanha = (now + timedelta(days=1)).strftime("%Y%m%d")

check(por_dia.get(hoje, 0) > 0, f"hoje {hoje} tem programacao", f"{por_dia.get(hoje, 0)} programas em {len(canais_por_dia.get(hoje, ()))} canais")
check(por_dia.get(amanha, 0) > 0, f"amanha {amanha} tem programacao", f"{por_dia.get(amanha, 0)} programas em {len(canais_por_dia.get(amanha, ()))} canais")

# cobertura por dia: um canal com hoje deve ter amanha
com_hoje = canais_por_dia.get(hoje, set())
cobertos = sorted(com_hoje & canais_por_dia.get(amanha, set()))
ratio = len(cobertos) / len(com_hoje) * 100 if com_hoje else 0
check(ratio >= 50, "canais de hoje que tambem tem amanha", f"{len(cobertos)}/{len(com_hoje)} ({ratio:.0f}%)")

print()
print("   Amostra de 5 canais com grade de hoje:")
print("   " + "-" * 64)
for cid in sorted(cobertos)[:5]:
    nome = next((m3u_info.get(c, c) for c in com_programa if norm(c) == norm(cid)), cid)
    print(f"   {cid} ({nome})")
    itens = [p for p in programas if p.get("channel") == cid and p.get("start", "")[:8] == hoje]
    for prog in sorted(itens, key=lambda p: p.get("start", ""))[:4]:
        print(f"      {prog.get('start')} -> {prog.get('stop')}  {prog.findtext('title')}")
    print()

print("=" * 66)
if falhas:
    print(f"RESULTADO: {len(falhas)} VERIFICACAO(OES) FALHARAM: {falhas}")
    sys.exit(1)
print(f"RESULTADO: EPGFULL.xml.gz OK - {len(ids_xml)} canais (todos da M3U),")
print(f"           {len(programas)} programas, {comprimido:,} bytes comprimidos")
print(f"           hoje={por_dia.get(hoje, 0)} programas / amanha={por_dia.get(amanha, 0)} programas")
print("=" * 66)