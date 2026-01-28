#!/usr/bin/env python3
"""
Script para buscar links "AO VIVO" no G1 Globo para todos os estados brasileiros
"""

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import sys

# Lista de todos os estados brasileiros com suas abreviações
ESTADOS_BRASIL = [
    "ac", "al", "ap", "am", "ba", "ce", "df", "es", "go", "ma",
    "mt", "ms", "mg", "pa", "pb", "pr", "pe", "pi", "rj", "rn",
    "rs", "ro", "rr", "sc", "sp", "se", "to"
]

def configurar_driver():
    """Configura e retorna o driver do Selenium"""
    options = Options()
    options.add_argument("--headless")  # Executa sem interface gráfica
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1280,720")
    options.add_argument("--disable-infobars")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    
    driver = webdriver.Chrome(options=options)
    return driver

def buscar_links_ao_vivo(driver, url):
    """
    Busca por links contendo "AO VIVO" na página
    Retorna uma lista com os links encontrados
    """
    links_encontrados = []
    
    try:
        print(f"  Acessando: {url}")
        driver.get(url)
        
        # Aguarda um pouco para a página carregar
        time.sleep(3)
        
        # Procura por elementos que contenham "AO VIVO"
        # Busca em textos e atributos
        try:
            # Espera por elementos que possam conter "AO VIVO"
            WebDriverWait(driver, 5).until(
                EC.presence_of_all_elements_located((By.TAG_NAME, "a"))
            )
        except:
            pass
        
        # Busca todos os links da página
        todos_elementos = driver.find_elements(By.XPATH, "//*")
        
        for elemento in todos_elementos:
            try:
                texto = elemento.text.upper()
                
                # Se encontrar "AO VIVO" no texto do elemento
                if "AO VIVO" in texto:
                    # Tenta encontrar um link associado
                    try:
                        link_element = elemento.find_element(By.TAG_NAME, "a")
                        href = link_element.get_attribute("href")
                        if href and href not in links_encontrados:
                            links_encontrados.append(href)
                            print(f"    ✓ Encontrado: {href}")
                    except:
                        # Se o elemento em si é um link
                        if elemento.tag_name == "a":
                            href = elemento.get_attribute("href")
                            if href and href not in links_encontrados:
                                links_encontrados.append(href)
                                print(f"    ✓ Encontrado: {href}")
            except:
                pass
        
        # Busca também por atributos que contenham "AO VIVO"
        elementos_ao_vivo = driver.find_elements(By.XPATH, "//*[contains(., 'AO VIVO')]")
        
        for elemento in elementos_ao_vivo:
            try:
                # Procura por links dentro ou próximos
                links = elemento.find_elements(By.TAG_NAME, "a")
                for link in links:
                    href = link.get_attribute("href")
                    if href and href not in links_encontrados:
                        links_encontrados.append(href)
                        print(f"    ✓ Encontrado: {href}")
                
                # Se o elemento em si é um link
                if elemento.tag_name == "a":
                    href = elemento.get_attribute("href")
                    if href and href not in links_encontrados:
                        links_encontrados.append(href)
                        print(f"    ✓ Encontrado: {href}")
            except:
                pass
        
        if not links_encontrados:
            print(f"  ℹ Nenhum link 'AO VIVO' encontrado nesta página")
        
    except Exception as e:
        print(f"  ✗ Erro ao acessar {url}: {str(e)}")
    
    return links_encontrados

def main():
    """Função principal"""
    driver = configurar_driver()
    
    todos_os_links = {}
    
    try:
        print("=" * 60)
        print("BUSCADOR DE LINKS AO VIVO - G1 GLOBO")
        print("=" * 60)
        print(f"Total de estados a processar: {len(ESTADOS_BRASIL)}\n")
        
        for idx, estado in enumerate(ESTADOS_BRASIL, 1):
            url = f"https://g1.globo.com/{estado}"
            print(f"[{idx}/{len(ESTADOS_BRASIL)}] Estado: {estado.upper()}")
            
            links = buscar_links_ao_vivo(driver, url)
            
            if links:
                todos_os_links[estado.upper()] = links
            
            print()
        
        # Salva os resultados em arquivo
        salvar_resultados(todos_os_links)
        
        print("=" * 60)
        print("PROCESSO CONCLUÍDO COM SUCESSO!")
        print("=" * 60)
        
    finally:
        driver.quit()

def salvar_resultados(dados):
    """Salva os resultados em um arquivo de texto"""
    nome_arquivo = "linksaovivo.txt"
    
    try:
        with open(nome_arquivo, "w", encoding="utf-8") as arquivo:
            arquivo.write("=" * 70 + "\n")
            arquivo.write("LINKS AO VIVO - G1 GLOBO\n")
            arquivo.write("=" * 70 + "\n\n")
            
            if not dados:
                arquivo.write("Nenhum link 'AO VIVO' foi encontrado nas páginas dos estados.\n")
            else:
                total_links = sum(len(links) for links in dados.values())
                arquivo.write(f"Total de links encontrados: {total_links}\n")
                arquivo.write(f"Estados com conteúdo AO VIVO: {len(dados)}\n\n")
                
                for estado, links in sorted(dados.items()):
                    arquivo.write(f"\n{'─' * 70}\n")
                    arquivo.write(f"ESTADO: {estado}\n")
                    arquivo.write(f"{'─' * 70}\n")
                    
                    for idx, link in enumerate(links, 1):
                        arquivo.write(f"{idx}. {link}\n")
        
        print(f"✓ Arquivo '{nome_arquivo}' criado com sucesso!")
        
    except Exception as e:
        print(f"✗ Erro ao salvar arquivo: {str(e)}")

if __name__ == "__main__":
    main()
