#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para extrair links de canais ao vivo do Globoplay
Acessa https://globoplay.globo.com/agora-na-tv/ e extrai todos os links dos canais
Versão 2: Usando requests com JavaScript rendering
"""

import requests
from bs4 import BeautifulSoup
import json
import time
from datetime import datetime
import re

def extrair_links_globoplay_requests(url="https://globoplay.globo.com/agora-na-tv/"):
    """
    Extrai todos os links de canais ao vivo do Globoplay usando requests
    
    Args:
        url (str): URL da página do Globoplay
        
    Returns:
        list: Lista de dicionários com título e URL dos canais
    """
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Iniciando extração de links do Globoplay...")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Acessando: {url}")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        # Fazer requisição
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Fazendo requisição HTTP...")
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Parse HTML
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Analisando HTML...")
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Encontrar todos os links que contêm "/ao-vivo/"
        links = []
        
        # Procurar por links em tags <a>
        for a_tag in soup.find_all('a', href=True):
            href = a_tag.get('href', '')
            text = a_tag.get_text(strip=True)
            
            # Verificar se é um link de canal ao vivo
            if '/ao-vivo/' in href and text and 'associacao' not in href:
                links.append({
                    'titulo': text,
                    'url': href
                })
        
        # Remover duplicatas mantendo ordem
        seen = set()
        unique_links = []
        for link in links:
            if link['url'] not in seen:
                seen.add(link['url'])
                unique_links.append(link)
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Total de links encontrados: {len(unique_links)}")
        
        return unique_links
        
    except requests.exceptions.RequestException as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Erro na requisição: {str(e)}")
        return []
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Erro ao extrair links: {str(e)}")
        return []


def processar_links(links):
    """
    Processa e filtra os links extraídos
    
    Args:
        links (list): Lista de links brutos
        
    Returns:
        list: Lista de links processados e filtrados
    """
    
    links_processados = []
    
    for link in links:
        # Ignorar links de associação
        if "associacao" in link['url']:
            continue
            
        # Converter URLs relativas em absolutas
        if link['url'].startswith('/'):
            link['url'] = 'https://globoplay.globo.com' + link['url']
        
        # Limpar o título
        titulo = link['titulo'].replace('\n', ' ').strip()
        
        # Remover espaços múltiplos
        titulo = ' '.join(titulo.split())
        
        # Remover caracteres especiais desnecessários
        titulo = re.sub(r'\s+', ' ', titulo)
        
        links_processados.append({
            'titulo': titulo,
            'url': link['url']
        })
    
    return links_processados


def salvar_arquivo(links, nome_arquivo="canais_ao_vivo.txt"):
    """
    Salva os links em um arquivo .txt
    
    Args:
        links (list): Lista de links processados
        nome_arquivo (str): Nome do arquivo de saída
    """
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Salvando links em {nome_arquivo}...")
    
    try:
        with open(nome_arquivo, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("CANAIS AO VIVO - GLOBOPLAY\n")
            f.write("=" * 80 + "\n")
            f.write(f"Data de extração: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
            f.write(f"Total de canais: {len(links)}\n")
            f.write("=" * 80 + "\n\n")
            
            for idx, link in enumerate(links, 1):
                f.write(f"{idx}. {link['titulo']}\n")
                f.write(f"   URL: {link['url']}\n")
                f.write("\n")
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Arquivo salvo com sucesso!")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Caminho: {nome_arquivo}")
        
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Erro ao salvar arquivo: {str(e)}")


def salvar_json(links, nome_arquivo="canais_ao_vivo.json"):
    """
    Salva os links em um arquivo JSON (opcional)
    
    Args:
        links (list): Lista de links processados
        nome_arquivo (str): Nome do arquivo de saída
    """
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Salvando links em {nome_arquivo}...")
    
    try:
        with open(nome_arquivo, 'w', encoding='utf-8') as f:
            json.dump(links, f, ensure_ascii=False, indent=2)
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Arquivo JSON salvo com sucesso!")
        
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Erro ao salvar JSON: {str(e)}")


def main():
    """Função principal"""
    
    print("\n" + "=" * 80)
    print("EXTRATOR DE CANAIS AO VIVO - GLOBOPLAY (v2)")
    print("=" * 80 + "\n")
    
    # Extrair links
    links_brutos = extrair_links_globoplay_requests()
    
    if not links_brutos:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Nenhum link foi encontrado!")
        return
    
    # Processar links
    links_processados = processar_links(links_brutos)
    
    # Salvar em arquivo .txt
    salvar_arquivo(links_processados, "canais_ao_vivo.txt")
    
    # Salvar em arquivo JSON (opcional)
    salvar_json(links_processados, "canais_ao_vivo.json")
    
    print("\n" + "=" * 80)
    print(f"Extração concluída! Total de canais: {len(links_processados)}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
