#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para extrair links de canais ao vivo do Globoplay
Acessa https://globoplay.globo.com/agora-na-tv/ e extrai todos os links dos canais
"""

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import json
import time
from datetime import datetime

def extrair_links_globoplay(url="https://globoplay.globo.com/agora-na-tv/"):
    """
    Extrai todos os links de canais ao vivo do Globoplay usando Selenium
    
    Args:
        url (str): URL da página do Globoplay
        
    Returns:
        list: Lista de dicionários com título e URL dos canais
    """
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Iniciando extração de links do Globoplay...")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Acessando: {url}")
    
    # Configurar opções do Chrome
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    # chrome_options.add_argument("--headless")  # Descomente para modo headless
    
    # Inicializar o driver
    driver = webdriver.Chrome(options=chrome_options)
    
    try:
        # Acessar a página
        driver.get(url)
        
        # Aguardar o carregamento da página
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Aguardando carregamento da página...")
        time.sleep(3)
        
        # Executar JavaScript para extrair os links
        script = """
        const links = [];
        const elements = document.querySelectorAll('a[href*="/ao-vivo/"]');
        
        elements.forEach(el => {
          const href = el.getAttribute('href');
          const text = el.textContent.trim();
          if (href && text && href.includes('/ao-vivo/')) {
            links.push({
              titulo: text,
              url: href
            });
          }
        });
        
        // Remover duplicatas
        const uniqueLinks = [];
        const seen = new Set();
        links.forEach(link => {
          if (!seen.has(link.url)) {
            seen.add(link.url);
            uniqueLinks.push(link);
          }
        });
        
        return uniqueLinks;
        """
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Executando extração de links via JavaScript...")
        links = driver.execute_script(script)
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Total de links encontrados: {len(links)}")
        
        return links
        
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Erro ao extrair links: {str(e)}")
        return []
        
    finally:
        driver.quit()
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Driver fechado")


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
    print("EXTRATOR DE CANAIS AO VIVO - GLOBOPLAY")
    print("=" * 80 + "\n")
    
    # Extrair links
    links_brutos = extrair_links_globoplay()
    
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
