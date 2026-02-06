#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para extrair links de canais ao vivo do Globoplay
"""

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import json
import time
from datetime import datetime

def extrair_links_globoplay(url="https://globoplay.globo.com/agora-na-tv/"):
    """
    Extrai todos os links de canais ao vivo do Globoplay usando Selenium
    """
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Iniciando extração de links do Globoplay...")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Acessando: {url}")
    
    # Configurações do Chrome
    options = Options()
    options.add_argument("--headless")  # Executa sem interface gráfica
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1280,720")
    options.add_argument("--disable-infobars")
    
    # Inicializar o driver
    driver = webdriver.Chrome(options=options)
    
    try:
        driver.get(url)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Aguardando carregamento da página...")
        time.sleep(5)  # Aguardar JS carregar
        
        # Executar JavaScript para extrair links
        script = """
        const links = [];
        const elements = document.querySelectorAll('a[href*="/ao-vivo/"]');
        
        elements.forEach(el => {
          const href = el.getAttribute('href');
          const text = el.textContent.trim();
          if (href && text && href.includes('/ao-vivo/')) {
            links.push({ titulo: text, url: href });
          }
        });
        
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
    """
    links_processados = []
    
    for link in links:
        if "associacao" in link['url']:
            continue
        if link['url'].startswith('/'):
            link['url'] = 'https://globoplay.globo.com' + link['url']
        titulo = ' '.join(link['titulo'].replace('\n', ' ').split())
        links_processados.append({'titulo': titulo, 'url': link['url']})
    
    return links_processados


def salvar_arquivo(links, nome_arquivo="canais_ao_vivo.txt"):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Salvando links em {nome_arquivo}...")
    try:
        with open(nome_arquivo, 'w', encoding='utf-8') as f:
            f.write("="*80 + "\n")
            f.write("CANAIS AO VIVO - GLOBOPLAY\n")
            f.write("="*80 + "\n")
            f.write(f"Data de extração: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
            f.write(f"Total de canais: {len(links)}\n")
            f.write("="*80 + "\n\n")
            for idx, link in enumerate(links, 1):
                f.write(f"{idx}. {link['titulo']}\n")
                f.write(f"   URL: {link['url']}\n\n")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Arquivo salvo com sucesso!")
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Erro ao salvar arquivo: {str(e)}")


def salvar_json(links, nome_arquivo="canais_ao_vivo.json"):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Salvando links em {nome_arquivo}...")
    try:
        with open(nome_arquivo, 'w', encoding='utf-8') as f:
            json.dump(links, f, ensure_ascii=False, indent=2)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Arquivo JSON salvo com sucesso!")
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Erro ao salvar JSON: {str(e)}")


def main():
    print("\n" + "="*80)
    print("EXTRATOR DE CANAIS AO VIVO - GLOBOPLAY")
    print("="*80 + "\n")
    
    links_brutos = extrair_links_globoplay()
    if not links_brutos:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Nenhum link foi encontrado!")
        return
    
    links_processados = processar_links(links_brutos)
    salvar_arquivo(links_processados, "canais_ao_vivo.txt")
    salvar_json(links_processados, "canais_ao_vivo.json")
    
    print("\n" + "="*80)
    print(f"Extração concluída! Total de canais: {len(links_processados)}")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
