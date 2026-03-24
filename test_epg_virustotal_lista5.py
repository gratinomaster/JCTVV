#!/usr/bin/env python3
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import base64
import json
import sys

VIRUSTOTAL_API_URL = "https://www.virustotal.com/api/v3/urls"

EPG_SOURCES = {
    "ABCNews.us": "https://github.com/iptv-org/epg/raw/master/sites/abcnews.com.channels.xml",
    "CBSNews.us": "https://github.com/iptv-org/epg/raw/master/sites/cbsnews.com.channels.xml",
    "FoxNewsChannel.us": "https://github.com/iptv-org/epg/raw/master/sites/foxnews.com.channels.xml",
    "FoxBusiness.us": "https://github.com/iptv-org/epg/raw/master/sites/foxbusiness.com.channels.xml",
}

EPG_DIRECT = "https://github.com/iptv-org/epg/raw/master/guide/us.xml.gz"

def get_base_url():
    return "https://github.com/iptv-org/epg/raw/master/guide/us.xml.gz"

def testar_epg(epg_url: str) -> Dict:
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
            import gzip
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

def verificar_url_virustotal(url: str, api_key: Optional[str] = None) -> Dict:
    print(f"\n{'='*60}")
    print("VERIFICAÇÃO VIRUSTOTAL")
    print(f"{'='*60}")
    print(f"URL: {url[:80]}...")
    
    resultado = {
        "status": "nao_verificado",
        "malicious": None,
        "suspicious": 0,
        "harmless": 0,
        "undetected": 0,
        "erro": None
    }
    
    if not api_key:
        print("⚠️ API key não fornecida. Pulando verificação VirusTotal.")
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
    print(f"\n{'='*60}")
    print("TESTE DE STREAM")
    print(f"{'='*60}")
    print(f"URL: {url[:80]}...")
    
    resultado = {
        "status": "desconhecido",
        "http_code": None,
        "erro": None
    }
    
    try:
        response = requests.head(url, timeout=15, allow_redirects=True, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        resultado["http_code"] = response.status_code
        
        if response.status_code == 200:
            resultado["status"] = "ok"
            print(f"✓ Stream acessível (HTTP {response.status_code})")
        elif response.status_code == 404:
            resultado["status"] = "404_nao_encontrado"
            print(f"✗ Stream não encontrado (HTTP 404)")
        elif response.status_code == 403:
            resultado["status"] = "403_proibido"
            print(f"⚠️ Stream proibido (HTTP 403) - pode precisar de autenticação")
        elif response.status_code == 405:
            resultado["status"] = "ok_metodo_nao_permitido"
            print(f"✓ Stream pode estar OK (HTTP 405 - método não permitido é normal para streaming)")
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
    
    print("\nTestando fontes de EPG para canais americanos...")
    
    epg_urls = [
        ("https://github.com/iptv-org/epg/raw/master/guide/us.xml.gz", "IPTV-ORG US EPG (gzipped)"),
        ("https://iptv-epg.org/files/epg-us.xml.gz", "IPTV-EPG US"),
    ]
    
    melhor_epg = None
    for url, name in epg_urls:
        print(f"\n--- Testando {name} ---")
        resultado = testar_epg(url)
        if resultado["status"] == "ok":
            melhor_epg = url
            print(f"✓ EPG Funcionando: {name}")
            break
    
    if not melhor_epg:
        print("\n✗ Nenhum EPG funcionou completamente, usando fonte padrão")
        melhor_epg = epg_urls[0][0]
    
    print("\n" + "="*60)
    print("RESUMO")
    print("="*60)
    print(f"EPG selecionado: {melhor_epg}")
    
    return melhor_epg

if __name__ == "__main__":
    main()
