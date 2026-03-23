#!/usr/bin/env python3
"""
Script para testar EPG e verificar URLs com VirusTotal.
Uso: python3 testar_epg_virustotal.py [VIRUSTOTAL_API_KEY]
"""

import sys
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import hashlib
import base64

try:
    import requests
except ImportError:
    print("Instalando requests...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests

EPG_URL = "https://tvit.leicaflorianrobert.dev/epg/list.xml"
VIRUSTOTAL_API_URL = "https://www.virustotal.com/api/v3/urls"

def testar_epg(epg_url: str) -> Dict:
    """Testa se o EPG está funcionando e retorna informações."""
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
        response = requests.get(epg_url, timeout=30)
        response.raise_for_status()
        
        print(f"Status: {response.status_code}")
        print(f"Tamanho: {len(response.content)} bytes")
        
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


def verificar_url_virustotal(url: str, api_key: Optional[str] = None) -> Dict:
    """Verifica URL no VirusTotal (requer API key)."""
    print(f"\n{'='*60}")
    print("VERIFICAÇÃO VIRUSTOTAL")
    print(f"{'='*60}")
    print(f"URL: {url}")
    
    resultado = {
        "status": "nao_verificado",
        "malicious": None,
        "engines": {},
        "erro": None
    }
    
    if not api_key:
        print("⚠️ API key não fornecida. Pulando verificação VirusTotal.")
        print("Para verificar, obtenha uma API key em: https://www.virustotal.com/gui/user/apikey")
        return resultado
    
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
            
            print(f"\nResultados:")
            print(f"  Malicious: {resultado['malicious']}")
            print(f"  Suspicious: {resultado['suspicious']}")
            print(f"  Harmless: {resultado['harmless']}")
            print(f"  Undetected: {resultado['undetected']}")
            
            if resultado["malicious"]:
                print("\n⚠️ ATENÇÃO: URL detectada como maliciosa!")
            elif resultado["suspicious"] > 0:
                print("\n⚠️ ATENÇÃO: URL detectada como suspeita!")
            else:
                print("\n✓ URL parece segura")
                
        elif response.status_code == 404:
            print("URL não encontrada no banco de dados. Enviando para scan...")
            
            scan_response = requests.post(
                VIRUSTOTAL_API_URL,
                headers=headers,
                data={"url": url},
                timeout=30
            )
            
            if scan_response.status_code == 200:
                print("✓ URL enviada para análise. Aguarde alguns minutos e consulte novamente.")
                resultado["status"] = "enviado_para_analise"
            else:
                resultado["erro"] = f"Erro ao enviar URL: {scan_response.status_code}"
        else:
            resultado["erro"] = f"Erro na API: {response.status_code}"
            
    except Exception as e:
        resultado["erro"] = str(e)
        print(f"✗ ERRO: {e}")
    
    return resultado


def verificar_stream(url: str) -> Dict:
    """Verifica se o stream está acessível."""
    print(f"\n{'='*60}")
    print("TESTE DE STREAM")
    print(f"{'='*60}")
    print(f"URL: {url}")
    
    resultado = {
        "status": "desconhecido",
        "http_code": None,
        "erro": None
    }
    
    try:
        response = requests.head(url, timeout=10, allow_redirects=True)
        resultado["http_code"] = response.status_code
        
        if response.status_code == 200:
            resultado["status"] = "ok"
            print(f"✓ Stream acessível (HTTP {response.status_code})")
        elif response.status_code == 404:
            resultado["status"] = "404_nao_encontrado"
            print(f"✗ Stream não encontrado (HTTP 404)")
        elif response.status_code == 403:
            resultado["status"] = "403_proibido"
            print(f"⚠️ Stream proibido (HTTP 403) - pode precisar de VPN")
        else:
            resultado["status"] = f"http_{response.status_code}"
            print(f"⚠️ Status HTTP: {response.status_code}")
            
    except requests.exceptions.Timeout:
        resultado["status"] = "timeout"
        resultado["erro"] = "Timeout ao conectar"
        print("✗ Timeout ao conectar")
    except Exception as e:
        resultado["status"] = "erro"
        resultado["erro"] = str(e)
        print(f"✗ ERRO: {e}")
    
    return resultado


def main():
    print("="*60)
    print("TESTE DE EPG E VERIFICAÇÃO DE URL")
    print("="*60)
    
    api_key = sys.argv[1] if len(sys.argv) > 1 else None
    
    epg_resultado = testar_epg(EPG_URL)
    
    stream_url = "https://tvit.leicaflorianrobert.dev/discovery/real-time/stream.m3u8"
    stream_resultado = verificar_stream(stream_url)
    
    if api_key:
        vt_resultado = verificar_url_virustotal(stream_url, api_key)
    
    print("\n" + "="*60)
    print("RESUMO")
    print("="*60)
    print(f"EPG: {'✓ OK' if epg_resultado['status'] == 'ok' else '✗ FALHOU'}")
    print(f"Stream: {stream_resultado['status']}")
    if api_key:
        print(f"VirusTotal: {vt_resultado['status']}")


if __name__ == "__main__":
    main()
