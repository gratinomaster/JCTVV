#!/usr/bin/env python3
import requests
import gzip
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import re
import base64

EPG_URL = "https://github.com/iptv-org/epg/raw/master/guide/us.xml.gz"

def testar_epg():
    print("="*60)
    print("TESTE DO EPG")
    print("="*60)
    
    resultado = {
        "status": "falhou",
        "programas_hoje": 0,
        "programas_amanha": 0,
        "programas_depois_amanha": 0,
        "canais": [],
    }
    
    try:
        print(f"Baixando EPG: {EPG_URL}")
        response = requests.get(EPG_URL, timeout=120, headers={'Accept-Encoding': 'gzip'})
        response.raise_for_status()
        print(f"Tamanho: {len(response.content)} bytes")
        
        xml_content = gzip.decompress(response.content).decode('utf-8')
        root = ET.fromstring(xml_content)
        
        canais = root.findall("channel")
        programas = root.findall("programme")
        
        resultado["canais"] = [c.get("id") for c in canais]
        resultado["programas_total"] = len(programas)
        
        print(f"Canais encontrados: {len(canais)}")
        print(f"Programas encontrados: {len(programas)}")
        
        hoje = datetime.now().strftime("%Y%m%d")
        amanha = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
        depois_amanha = (datetime.now() + timedelta(days=2)).strftime("%Y%m%d")
        
        print(f"\nDatas de hoje: {hoje}, amanha: {amanha}, depois: {depois_amanha}")
        
        for prog in programas:
            start = prog.get("start", "")[:8]
            if start[:8] == hoje:
                resultado["programas_hoje"] += 1
            elif start[:8] == amanha:
                resultado["programas_amanha"] += 1
            elif start[:8] == depois_amanha:
                resultado["programas_depois_amanha"] += 1
        
        print(f"\nProgramação:")
        print(f"  Hoje: {resultado['programas_hoje']} programas")
        print(f"  Amanhã: {resultado['programas_amanha']} programas")
        print(f"  Depois de amanhã: {resultado['programas_depois_amanha']} programas")
        
        if resultado["programas_hoje"] > 0 and resultado["programas_amanha"] > 0:
            resultado["status"] = "ok"
            print("\n✓ EPG FUNCIONANDO!")
        else:
            print("\n✗ EPG com problemas de programação")
        
        print("\nCanais principais:")
        for canal_id in resultado["canais"][:20]:
            print(f"  - {canal_id}")
        
        return resultado
        
    except Exception as e:
        print(f"✗ ERRO: {e}")
        return resultado

def testar_stream(url):
    try:
        response = requests.head(url, timeout=15, allow_redirects=True, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        return response.status_code
    except:
        return None

def main():
    resultado = testar_epg()
    print("\n" + "="*60)
    print("RESULTADO FINAL")
    print("="*60)
    print(f"EPG Status: {resultado['status']}")
    print(f"Total de programas: {resultado.get('programas_total', 0)}")
    
    if resultado['status'] == 'ok':
        print("\nEPG pode ser usado: https://github.com/iptv-org/epg/raw/master/guide/us.xml.gz")

if __name__ == "__main__":
    main()
