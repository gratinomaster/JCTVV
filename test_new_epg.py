#!/usr/bin/env python3
import gzip
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

EPG_FILE = "EPGFULL.xml.gz"

print("="*60)
print("TESTE DO EPGFULL.xml.gz GERADO")
print("="*60)

try:
    with gzip.open(EPG_FILE, 'rb') as f:
        raw = f.read()
    print(f"Tamanho do arquivo: {len(raw)} bytes")
    print(f"Válido como gzip: sim")

    root = ET.fromstring(raw)

    canais = root.findall("channel")
    programas = root.findall("programme")

    print(f"Canais encontrados: {len(canais)}")
    print(f"Programas encontrados: {len(programas)}")

    print("\n--- CANAIS ---")
    for ch in sorted(canais, key=lambda x: x.get("id")):
        dn = ch.find("display-name")
        name = dn.text if dn is not None else "N/A"
        print(f"  {ch.get('id')}: {name}")

    hoje = datetime.now().strftime("%Y%m%d")
    amanha = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
    depois_amanha = (datetime.now() + timedelta(days=2)).strftime("%Y%m%d")

    print(f"\n--- PROGRAMAÇÃO POR DATA ---")
    prog_hoje = 0
    prog_amanha = 0
    prog_depois = 0
    sem_data = 0
    prog_por_canal = {}

    for prog in programas:
        ch = prog.get("channel", "?")
        start = prog.get("start", "")
        if ch not in prog_por_canal:
            prog_por_canal[ch] = 0
        prog_por_canal[ch] += 1
        data = start[:8]
        if data == hoje:
            prog_hoje += 1
        elif data == amanha:
            prog_amanha += 1
        elif data == depois_amanha:
            prog_depois += 1
        else:
            sem_data += 1

    print(f"  Hoje ({hoje}): {prog_hoje} programas")
    print(f"  Amanhã ({amanha}): {prog_amanha} programas")
    print(f"  Depois de amanhã ({depois_amanha}): {prog_depois} programas")
    print(f"  Outras datas: {sem_data} programas")

    print(f"\n--- PROGRAMAS POR CANAL ---")
    for ch_id, count in sorted(prog_por_canal.items()):
        print(f"  {ch_id}: {count} programas")

    print(f"\n--- AMOSTRA DE PROGRAMAÇÃO (PRIMEIROS 10) ---")
    for prog in programas[:10]:
        ch = prog.get("channel", "?")
        start = prog.get("start", "")
        stop = prog.get("stop", "")
        title = prog.find("title")
        titulo = title.text if title is not None else "N/A"
        print(f"  [{ch}] {start} -> {stop}: {titulo}")

    print("\n" + "="*60)
    print("RESULTADO FINAL")
    print("="*60)

    if len(canais) > 0 and prog_hoje > 0 and prog_amanha > 0:
        print("✓ EPG FUNCIONANDO: contém programação de hoje e amanhã!")
    elif len(canais) == 0:
        print("✗ EPG COM PROBLEMAS: sem canais")
    else:
        print("✗ EPG COM PROBLEMAS: programação insuficiente")
        print(f"  Programas hoje: {prog_hoje}")
        print(f"  Programas amanhã: {prog_amanha}")

except Exception as e:
    print(f"\n✗ ERRO: {e}")
    import traceback
    traceback.print_exc()
