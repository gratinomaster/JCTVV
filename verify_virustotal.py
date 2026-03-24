#!/usr/bin/env python3
"""
Script para verificar streams da lista5.m3u com VirusTotal.
Uso: python3 verify_virustotal.py [VIRUSTOTAL_API_KEY]
"""

import requests
import base64
import sys
import re
from typing import Dict, List, Optional

VIRUSTOTAL_API_URL = "https://www.virustotal.com/api/v3/urls"

def extract_streams_from_m3u(file_path: str) -> List[Dict]:
    streams = []
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    current_info = None
    for line in lines:
        line = line.strip()
        if line.startswith('#EXTINF:'):
            current_info = line
        elif line.startswith('http') and current_info:
            streams.append({
                'url': line,
                'info': current_info
            })
            current_info = None
    return streams

def extract_name_from_info(info: str) -> str:
    match = re.search(r',(.+)$', info)
    if match:
        return match.group(1)
    return "Unknown"

def verificar_url_virustotal(url: str, api_key: str) -> Dict:
    resultado = {
        "status": "nao_verificado",
        "malicious": False,
        "suspicious": 0,
        "harmless": 0,
        "undetected": 0,
        "erro": None
    }
    
    try:
        url_id = base64.urlsafe_b64encode(url.encode()).decode().strip("=")
        headers = {"x-apikey": api_key}
        
        response = requests.get(
            f"{VIRUSTOTAL_API_URL}/{url_id}",
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            stats = data.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
            
            resultado["malicious"] = stats.get("malicious", 0) > 0
            resultado["suspicious"] = stats.get("suspicious", 0)
            resultado["harmless"] = stats.get("harmless", 0)
            resultado["undetected"] = stats.get("undetected", 0)
            resultado["status"] = "verificado"
            
        elif response.status_code == 404:
            print("  URL não encontrada, enviando para scan...")
            scan_response = requests.post(
                VIRUSTOTAL_API_URL,
                headers=headers,
                data={"url": url},
                timeout=30
            )
            
            if scan_response.status_code == 200:
                resultado["status"] = "enviado_para_analise"
        else:
            resultado["erro"] = f"Erro na API: {response.status_code}"
            
    except Exception as e:
        resultado["erro"] = str(e)
    
    return resultado

def main():
    print("="*60)
    print("VERIFICAÇÃO DE STREAMS COM VIRUSTOTAL")
    print("="*60)
    
    api_key = sys.argv[1] if len(sys.argv) > 1 else None
    
    if not api_key:
        print("\n⚠️ API key do VirusTotal não fornecida!")
        print("Para verificar, obtenha uma API key em: https://www.virustotal.com/gui/user/apikey")
        print("\nUso: python3 verify_virustotal.py [VIRUSTOTAL_API_KEY]")
        return
    
    streams = extract_streams_from_m3u('lista5.m3u')
    
    print(f"\nTotal de streams: {len(streams)}")
    
    resultados = []
    for i, stream in enumerate(streams, 1):
        name = extract_name_from_info(stream['info'])
        url = stream['url']
        
        print(f"\n{i}/{len(streams)} Verificando: {name}")
        print(f"  URL: {url[:60]}...")
        
        resultado = verificar_url_virustotal(url, api_key)
        
        if resultado["status"] == "verificado":
            print(f"  Resultado: Malicious={resultado['malicious']}, Suspicious={resultado['suspicious']}, Harmless={resultado['harmless']}")
            if resultado["malicious"]:
                print("  ⚠️ ATENÇÃO: URL MALICIOSA!")
            elif resultado["suspicious"] > 0:
                print("  ⚠️ ATENÇÃO: URL SUSPEITA!")
            else:
                print("  ✓ URL OK")
        
        resultados.append({
            'name': name,
            'url': url,
            'resultado': resultado
        })
    
    print("\n" + "="*60)
    print("RESUMO")
    print("="*60)
    
    malicious = [r for r in resultados if r['resultado'].get('malicious')]
    suspicious = [r for r in resultados if r['resultado'].get('suspicious', 0) > 0]
    
    print(f"Total verificado: {len([r for r in resultados if r['resultado']['status'] == 'verificado'])}")
    print(f"Maliciosos: {len(malicious)}")
    print(f"Suspeitos: {len(suspicious)}")
    
    if malicious:
        print("\n⚠️ URLs MALICIOSAS (DEVEM SER REMOVIDAS):")
        for r in malicious:
            print(f"  - {r['name']}: {r['url'][:60]}...")
    
    if suspicious:
        print("\n⚠️ URLs SUSPEITAS (REVISAR):")
        for r in suspicious:
            print(f"  - {r['name']}: {r['url'][:60]}...")

if __name__ == "__main__":
    main()
