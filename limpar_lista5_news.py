#!/usr/bin/env python3
import re
import requests
import hashlib
import time
import os

VT_API_KEY = os.environ.get("VT_API_KEY", "")

def remove_empty_entries():
    """Remove entradas que não têm URL"""
    
    with open("/home/runner/work/JCTV/JCTV/lista5.m3u", "r") as f:
        lines = f.readlines()
    
    new_lines = []
    i = 0
    
    while i < len(lines):
        line = lines[i].strip()
        
        if line.startswith("#EXTINF:"):
            # Verificar se a próxima linha é uma URL
            if i + 1 < len(lines) and lines[i + 1].strip().startswith("http"):
                new_lines.append(lines[i])
                new_lines.append(lines[i + 1])
                i += 2
            else:
                # Pular esta EXTINF se não tiver URL
                i += 1
        elif line.startswith("http"):
            # URL sem EXTINF - verificar se já temos EXTINF antes
            if new_lines and not new_lines[-1].startswith("#EXTINF:"):
                # Remover a última EXTINF se não tiver URL
                if new_lines and new_lines[-1].startswith("#EXTM3U"):
                    new_lines.pop()
                elif new_lines:
                    new_lines.pop()
            new_lines.append(line)
            i += 1
        elif line.startswith("#EXTM3U") or line.startswith("#EXTURL"):
            new_lines.append(lines[i])
            i += 1
        else:
            i += 1
    
    with open("/home/runner/work/JCTV/JCTV/lista5.m3u", "w") as f:
        f.write("\n".join(new_lines))
    
    print(f"Entradas vazias removidas. Total de linhas: {len(new_lines)}")

def extract_urls():
    """Extrai URLs únicas do arquivo m3u"""
    urls = set()
    
    with open("/home/runner/work/JCTV/JCTV/lista5.m3u", "r") as f:
        for line in f:
            line = line.strip()
            if line.startswith("http"):
                urls.add(line)
    
    return list(urls)

def check_virustotal(url, api_key):
    """Verifica URL no VirusTotal"""
    try:
        url_id = hashlib.sha256(url.encode()).hexdigest()
        
        headers = {
            "x-apikey": api_key,
            "accept": "application/json"
        }
        
        response = requests.get(
            f"https://www.virustotal.com/api/v3/urls/{url_id}",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            stats = data.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
            
            malicious = stats.get("malicious", 0)
            suspicious = stats.get("suspicious", 0)
            total = sum(stats.values())
            
            if malicious > 0 or suspicious > 0:
                return False, f"Malicious: {malicious}, Suspicious: {suspicious}"
            return True, "OK"
        elif response.status_code == 404:
            # URL não encontrada no VT, verificar diretamente
            return None, "Not found in VT"
        else:
            return None, f"Error: {response.status_code}"
            
    except Exception as e:
        return None, str(e)

def check_virustotal_batch(urls, api_key):
    """Verifica múltiplas URLs no VirusTotal"""
    results = {}
    
    for url in urls:
        result, message = check_virustotal(url, api_key)
        results[url] = {"safe": result, "message": message}
        
        # Rate limiting
        time.sleep(1)
    
    return results

def remove_unsafe_channels():
    """Remove canais inseguros com base no VirusTotal"""
    
    if not VT_API_KEY:
        print("VirusTotal API key não disponível. Pulando verificação de segurança.")
        return
    
    urls = extract_urls()
    print(f"Verificando {len(urls)} URLs no VirusTotal...")
    
    results = check_virustotal_batch(urls, VT_API_KEY)
    
    unsafe_urls = [url for url, result in results.items() 
                   if result["safe"] == False]
    
    if unsafe_urls:
        print(f"Encontradas {len(unsafe_urls)} URLs inseguras. Removendo...")
        
        with open("/home/runner/work/JCTV/JCTV/lista5.m3u", "r") as f:
            lines = f.readlines()
        
        new_lines = []
        i = 0
        
        while i < len(lines):
            line = lines[i].strip()
            
            if line.startswith("#EXTINF:"):
                # Verificar as próximas linhas para URLs
                extinf_lines = [lines[i]]
                j = i + 1
                
                while j < len(lines) and not lines[j].strip().startswith("#EXTINF:") and not lines[j].strip().startswith("#EXTM3U"):
                    if lines[j].strip().startswith("http"):
                        url = lines[j].strip()
                        if url not in unsafe_urls:
                            extinf_lines.append(lines[j])
                    j += 1
                
                # Se tiver pelo menos uma URL segura, adicionar
                if len(extinf_lines) > 1:
                    new_lines.extend(extinf_lines)
                
                i = j
            elif line.startswith("#EXTM3U") or line.startswith("#EXTURL"):
                new_lines.append(lines[i])
                i += 1
            elif line.startswith("http"):
                # Pular URLs inseguras
                i += 1
            else:
                new_lines.append(lines[i])
                i += 1
        
        with open("/home/runner/work/JCTV/JCTV/lista5.m3u", "w") as f:
            f.write("\n".join(new_lines))
        
        print(f"Canais inseguros removidos. Total de linhas: {len(new_lines)}")
    else:
        print("Nenhuma URL insegura encontrada.")

def test_stream(url, timeout=5):
    """Testa se um stream funciona"""
    try:
        response = requests.get(url, timeout=timeout, stream=True)
        
        if response.status_code == 200:
            # Verificar se é um m3u8 válido
            content = response.text
            if "#EXTM3U" in content or "#EXTINF" in content or ".m3u8" in url:
                return True, "OK"
            return False, "Not a valid stream"
        
        return False, f"HTTP {response.status_code}"
    except requests.exceptions.Timeout:
        return False, "Timeout"
    except requests.exceptions.ConnectionError:
        return False, "Connection error"
    except Exception as e:
        return False, str(e)

def verify_channels():
    """Verifica se os canais funcionam"""
    
    urls = extract_urls()
    print(f"Verificando {len(urls)} streams...")
    
    working = 0
    not_working = 0
    
    for url in urls:
        result, message = test_stream(url)
        if result:
            working += 1
        else:
            not_working += 1
            print(f"  FALHOU: {url[:80]}... - {message}")
    
    print(f"\nResultados: {working} funcionando, {not_working} não funcionando")

if __name__ == "__main__":
    print("1. Removendo entradas vazias...")
    remove_empty_entries()
    
    print("\n2. Verificando VirusTotal...")
    remove_unsafe_channels()
    
    print("\n3. Verificando streams...")
    verify_channels()
