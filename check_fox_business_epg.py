#!/usr/bin/env python3
import requests
import gzip
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

print("=" * 70)
print("VERIFICACAO DE EPG PARA CANAIS")
print("=" * 70)

EPG_URL = "https://iptv-epg.org/files/epg-us.xml.gz"

CHANNELS_TO_CHECK = [
    "FoxBusiness.us",
    "FoxBusinessNetwork.us", 
    "FOXBusiness.us",
    "FoxBiz.us",
    "FBN.us",
]

try:
    print(f"\nBaixando EPG de {EPG_URL[:60]}...")
    response = requests.get(EPG_URL, timeout=120, headers={'Accept-Encoding': 'gzip'})
    response.raise_for_status()
    
    content = gzip.decompress(response.content).decode('utf-8')
    print(f"EPG baixado: {len(content):,} bytes")
    
    root = ET.fromstring(content)
    
    canais = root.findall("channel")
    print(f"Canais no EPG: {len(canais)}")
    
    print("\n" + "-" * 70)
    print("BUSCANDO CANAIS FOX BUSINESS:")
    print("-" * 70)
    
    encontrados = []
    for canal in canais:
        canal_id = canal.get("id", "")
        display_name = canal.find("display-name")
        nome = display_name.text if display_name is not None else ""
        
        if "fox" in canal_id.lower() or "business" in canal_id.lower() or "fbn" in canal_id.lower():
            if "fox" in nome.lower() and "business" in nome.lower():
                print(f"  ENCONTRADO: {canal_id} -> {nome}")
                encontrados.append(canal_id)
            elif "fox" in nome.lower() and "biz" in nome.lower():
                print(f"  ENCONTRADO: {canal_id} -> {nome}")
                encontrados.append(canal_id)
    
    if not encontrados:
        print("\nBuscando todos os canais com 'fox' ou 'business' no nome:")
        for canal in canais:
            canal_id = canal.get("id", "")
            display_name = canal.find("display-name")
            nome = display_name.text if display_name is not None else ""
            if "fox" in nome.lower() or "business" in nome.lower():
                print(f"  - {canal_id}: {nome}")
                encontrados.append(canal_id)
    
    if not encontrados:
        print("\nListando todos os canais que contem 'business':")
        for canal in canais:
            display_name = canal.find("display-name")
            nome = display_name.text if display_name is not None else ""
            if "business" in nome.lower():
                print(f"  - {canal.get('id')}: {nome}")
    
    print("\n" + "-" * 70)
    print("TESTANDO PROGRAMACAO DOS CANAIS ENCONTRADOS:")
    print("-" * 70)
    
    hoje = datetime.now().strftime("%Y%m%d")
    amanha = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
    depois_amanha = (datetime.now() + timedelta(days=2)).strftime("%Y%m%d")
    
    hoje_str = datetime.now().strftime("%d/%m")
    amanha_str = (datetime.now() + timedelta(days=1)).strftime("%d/%m")
    depois_amanha_str = (datetime.now() + timedelta(days=2)).strftime("%d/%m")
    
    for canal_id in list(set(encontrados)):
        programas_hoje = 0
        programas_amanha = 0
        programas_depois = 0
        
        for prog in root.findall("programme"):
            channel = prog.get("channel", "")
            if channel == canal_id:
                start = prog.get("start", "")[:8]
                if start[:8] == hoje:
                    programas_hoje += 1
                elif start[:8] == amanha:
                    programas_amanha += 1
                elif start[:8] == depois_amanha:
                    programas_depois += 1
        
        print(f"\n{canal_id}:")
        print(f"  {hoje_str}: {programas_hoje} programas")
        print(f"  {amanha_str}: {programas_amanha} programas")
        print(f"  {depois_amanha_str}: {programas_depois} programas")
        
        if programas_hoje > 0 and programas_amanha > 0 and programas_depois > 0:
            print(f"  STATUS: COMPLETO")
        elif programas_hoje > 0 or programas_amanha > 0:
            print(f"  STATUS: PARCIAL")
        else:
            print(f"  STATUS: SEM PROGRAMAÇÃO")
            
except Exception as e:
    print(f"ERRO: {e}")
