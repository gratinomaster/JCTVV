#!/usr/bin/env python3
"""
Script para buscar links "AO VIVO" no G1 Globo para todos os estados brasileiros
Usando requests + BeautifulSoup (sem Selenium)
"""

import requests
from bs4 import BeautifulSoup
import time

# Lista de todos os estados brasileiros com suas abreviações
ESTADOS_BRASIL = [
    "ac", "al", "ap", "am", "ba", "ce", "df", "es", "go", "ma",
    "mt", "ms", "mg", "pa", "pb", "pr", "pe", "pi", "rj", "rn",
    "rs", "ro", "rr", "sc", "sp", "se", "to"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

def buscar_links_ao_vivo(url):
    """
    Busca por links contendo 'AO VIVO' na página
    Retorna uma lista com os links encontrados
    """
    links_encontrados = []

    try:
        print(f"  Acessando: {url}")
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Busca todos os links da página
        for a in soup.find_all("a", href=True):
            texto = a.get_text(strip=True).upper()

            if "AO VIVO" in texto:
                href = a["href"]

                # Corrige links relativos
                if href.startswith("/"):
                    href = "https://g1.globo.com" + href

                if href not in links_encontrados:
                    links_encontrados.append(href)
                    print(f"    ✓ Encontrado: {href}")

        if not links_encontrados:
            print("  ℹ Nenhum link 'AO VIVO' encontrado nesta página")

    except requests.RequestException as e:
        print(f"  ✗ Erro ao acessar {url}: {e}")

    return links_encontrados

def salvar_resultados(dados):
    """Salva os resultados em um arquivo de texto"""
    nome_arquivo = "linksaovivo.txt"

    try:
        with open(nome_arquivo, "w", encoding="utf-8") as arquivo:
            arquivo.write("=" * 70 + "\n")
            arquivo.write("LINKS AO VIVO - G1 GLOBO\n")
            arquivo.write("=" * 70 + "\n\n")

            if not dados:
                arquivo.write("Nenhum link 'AO VIVO' foi encontrado.\n")
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
        print(f"✗ Erro ao salvar arquivo: {e}")

def main():
    print("=" * 60)
    print("BUSCADOR DE LINKS AO VIVO - G1 GLOBO")
    print("=" * 60)
    print(f"Total de estados a processar: {len(ESTADOS_BRASIL)}\n")

    todos_os_links = {}

    for idx, estado in enumerate(ESTADOS_BRASIL, 1):
        url = f"https://g1.globo.com/{estado}"
        print(f"[{idx}/{len(ESTADOS_BRASIL)}] Estado: {estado.upper()}")

        links = buscar_links_ao_vivo(url)

        if links:
            todos_os_links[estado.upper()] = links

        time.sleep(1)  # pausa para evitar muitas requisições seguidas
        print()

    salvar_resultados(todos_os_links)

    print("=" * 60)
    print("PROCESSO CONCLUÍDO COM SUCESSO!")
    print("=" * 60)

if __name__ == "__main__":
    main()
