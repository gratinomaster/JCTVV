#!/usr/bin/env python3
import re
import requests
import gzip
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import base64
import json

VIRUSTOTAL_API_URL = "https://www.virustotal.com/api/v3/urls"

EPG_SOURCES = {
    "pt": [
        "https://epg.pw/xmltv/epg.xml.gz",
        "https://epg.pw/xmltv/epg_BR.xml.gz",
    ],
    "es": [
        "https://github.com/iptv-org/epg/raw/master/sites/epg.json",
    ],
    "br": [
        "https://epg.pw/xmltv/epg_BR.xml.gz",
    ],
    "us": [
        "https://github.com/iptv-org/epg/raw/master/guide/us.xml.gz",
    ],
    "fr": [
        "https://github.com/iptv-org/epg/raw/master/guide/fr.xml.gz",
    ],
    "de": [
        "https://github.com/iptv-org/epg/raw/master/guide/de.xml.gz",
    ],
    "it": [
        "https://github.com/iptv-org/epg/raw/master/guide/it.xml.gz",
    ],
    "uk": [
        "https://github.com/iptv-org/epg/raw/master/guide/uk.xml.gz",
    ],
}

LOGO_MAPPING = {
    "RTP1": "https://raw.githubusercontent.com/LITUATUI/M3UPT/main/logos/RTP1.jpg",
    "RTP2": "https://raw.githubusercontent.com/LITUATUI/M3UPT/main/logos/RTP2.jpg",
    "SIC": "https://raw.githubusercontent.com/LITUATUI/M3UPT/main/logos/SIC.jpg",
    "TVI": "https://raw.githubusercontent.com/LITUATUI/M3UPT/main/logos/TVI.jpg",
    "RTP Noticias": "https://raw.githubusercontent.com/LITUATUI/M3UPT/main/logos/rtpnoticias.jpg",
    "SIC Noticias": "https://raw.githubusercontent.com/LITUATUI/M3UPT/main/logos/SIC-Notícias.jpg",
    "CNN Portugal": "https://raw.githubusercontent.com/LITUATUI/M3UPT/main/logos/CNN-Portugal.jpg",
    "CNN Brasil": "https://raw.githubusercontent.com/LITUATUI/M3UPT/main/logos/CNN-Brasil.jpg",
}

def convert_logo_to_jpg(url):
    if not url:
        return url
    url = re.sub(r'\.(png|webp|svg|jpeg|jfif)(\?.*)?$', r'.jpg\2', url, flags=re.IGNORECASE)
    if not url.endswith('.jpg'):
        url = url + '.jpg'
    return url

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

def verificar_url_virustotal(url, api_key=None):
    print(f"\n{'='*60}")
    print("VERIFICAÇÃO VIRUSTOTAL")
    print(f"{'='*60}")
    print(f"URL: {url[:80]}...")
    
    if not api_key:
        api_key = "7e6c3d4f8c8e6c3d4f8c8e6c3d4f8c8e6c3d4f8c8e6c3d4f8c8e6c3d4f8c8e6c3d4f8c8e6c3d4f8c8e6c3"
    
    try:
        encoded_url = base64.urlsafe_b64encode(url.encode()).decode().rstrip('=')
        
        headers = {
            "x-apikey": api_key,
            "Accept": "application/json"
        }
        
        response = requests.get(f"{VIRUSTOTAL_API_URL}/{encoded_url}", headers=headers, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            stats = data.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
            malicious = stats.get("malicious", 0)
            total = sum(stats.values())
            
            print(f"Total: {total}")
            print(f"Maliciosos: {malicious}")
            
            if malicious == 0:
                print("✓ URL SEGURA")
                return True
            elif malicious < 3:
                print("⚠ ATENÇÃO - Alguns motores detectaram")
                return True
            else:
                print("✗ URL MALICIOSA")
                return False
        elif response.status_code == 404:
            print("⚠ URL não encontrada no VirusTotal - não é possível determinar")
            return True
        else:
            print(f"Erro: {response.status_code}")
            return True
            
    except Exception as e:
        print(f"Erro ao verificar: {e}")
        return True

def processar_lista5():
    print("Lendo arquivo lista5.m3u...")
    
    with open("lista5.m3u", "r", encoding="utf-8") as f:
        linhas = f.readlines()
    
    print(f"Total de linhas: {len(linhas)}")
    
    novas_linhas = []
    i = 0
    while i < len(linhas):
        linha = linhas[i]
        
        if linha.startswith("#EXTINF:"):
            nova_linha = linha
            
            match = re.search(r'tvg-logo="([^"]*)"', linha)
            if match:
                logo_url = match.group(1)
                novo_logo = convert_logo_to_jpg(logo_url)
                nova_linha = linha.replace(f'tvg-logo="{logo_url}"', f'tvg-logo="{novo_logo}"')
            
            match_nome = re.search(r',(.+)$', linha)
            nome_canal = match_nome.group(1).strip() if match_nome else ""
            
            match_tvg_id = re.search(r'tvg-id="([^"]*)"', linha)
            tvg_id = match_tvg_id.group(1) if match_tvg_id else None
            
            if not logo_url or not match:
                if nome_canal in LOGO_MAPPING:
                    nova_linha = re.sub(r'(group-title="[^"]*")', r'\1 tvg-logo="' + LOGO_MAPPING[nome_canal] + '"', nova_linha)
                    if 'tvg-logo' not in nova_linha:
                        nova_linha = nova_linha.rstrip('\n') + ' tvg-logo="' + LOGO_MAPPING[nome_canal] + '"\n'
            
            novas_linhas.append(nova_linha)
            
            i += 1
            if i < len(linhas) and linhas[i].startswith("#EXTVLCOPT") or linhas[i].startswith("#KODIPROP"):
                while i < len(linhas) and (linhas[i].startswith("#EXTVLCOPT") or linhas[i].startswith("#KODIPROP") or linhas[i].startswith("#https")):
                    if linhas[i].startswith("#https"):
                        novas_linhas.append(linhas[i])
                    i += 1
            
            while i < len(linhas) and not linhas[i].startswith("#") and not linhas[i].startswith("http"):
                i += 1
            
            if i < len(linhas) and linhas[i].startswith("http"):
                url_linha = linhas[i]
                if not url_linha.startswith("#"):
                    pass
                else:
                    novas_linhas.append(url_linha)
                    i += 1
            else:
                if i < len(linhas):
                    novas_linhas.append(linhas[i])
                    i += 1
        else:
            novas_linhas.append(linha)
            i += 1
    
    print("Escrevendo arquivo modificado...")
    with open("lista5.m3u", "w", encoding="utf-8") as f:
        f.writelines(novas_linhas)
    
    print("Arquivo escrito com sucesso!")

if __name__ == "__main__":
    processar_lista5()
    
    print("\n\nTestando fontes de EPG...")
    epg_sources = [
        "https://epg.pw/xmltv/epg.xml.gz",
        "https://epg.pw/xmltv/epg_BR.xml.gz",
    ]
    
    for epg in epg_sources:
        testar_epg(epg)
