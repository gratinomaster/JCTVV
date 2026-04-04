#!/usr/bin/env python3
import requests
import gzip
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import sys

def testar_epg(epg_url):
    print(f"\n{'='*60}")
    print("TESTE DE EPG")
    print(f"{'='*60}")
    print(f"URL: {epg_url}")
    
    resultado = {
        "status": "falhou",
        "programas_hoje": 0,
        "programas_amanha": 0,
        "programas_depois_amanha": 0,
        "canais": [],
        "erro": None
    }
    
    try:
        response = requests.get(epg_url, timeout=60, headers={'Accept-Encoding': 'gzip'})
        response.raise_for_status()
        
        print(f"Status: {response.status_code}")
        print(f"Tamanho: {len(response.content)} bytes")
        
        try:
            xml_content = gzip.decompress(response.content).decode('utf-8')
        except:
            xml_content = response.text
        
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
            resultado["erro"] = "Programação insuficiente para os próximos dias"
            print("\n✗ EPG com problemas de programação")
        
        return resultado
        
    except Exception as e:
        resultado["erro"] = str(e)
        print(f"\n✗ ERRO: {e}")
        return resultado

if __name__ == "__main__":
    epg_urls = [
        "https://epg.pw/xmltv/epg.xml.gz",
        "https://epg.pw/xmltv/epg_BR.xml.gz",
    ]
    
    for epg in epg_urls:
        testar_epg(epg)
