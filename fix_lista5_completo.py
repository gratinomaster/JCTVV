#!/usr/bin/env python3
"""
Corrige lista5.m3u completamente:
- Adiciona x-tvg-url com fontes EPG testadas no header #EXTM3U
- Atribui tvg-id a cada canal (mapeado para EPG)
- Testa programacao EPG para hoje, amanha e depois de amanha
- Remove URLs duplicadas (mantem apenas 1 URL por canal, a melhor)
- Remove canais com URLs inacessiveis
- tvg-logo sempre .jpg, nunca imgur.com
- Garante formato #EXTINF antes de cada URL
"""
import requests, gzip, re, io, sys, xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from collections import OrderedDict

M3U_PATH = "lista5.m3u"

EPG_SOURCES = [
    ("https://epg.pw/xmltv/epg.xml.gz", "EPG.PW"),
    ("https://iptv-epg.org/files/epg-us.xml.gz", "IPTV-EPG US"),
]

MELHOR_URL_PADROES = ['ctr-all-hdri-sliding', 'index.m3u8', '.m3u8']

def download_epg(url):
    try:
        r = requests.get(url, timeout=180, headers={'User-Agent': 'Mozilla/5.0'})
        r.raise_for_status()
        if url.endswith('.gz'):
            return gzip.decompress(r.content).decode('utf-8', errors='replace')
        return r.text
    except Exception as e:
        return None

def testar_programacao(epg, tvg_id):
    hoje = datetime.now().strftime("%Y%m%d")
    amanha = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
    depois = (datetime.now() + timedelta(days=2)).strftime("%Y%m%d")
    r = {"status": "sem_programacao", "hoje": 0, "amanha": 0, "depois_amanha": 0,
         "programas_hoje": [], "programas_amanha": [], "programas_depois_amanha": []}
    try:
        for p in ET.fromstring(epg).findall("programme"):
            if p.get("channel") == tvg_id:
                s = p.get("start", "")[:8]
                t = p.findtext("title", "N/A").strip()
                if s == hoje:
                    r["hoje"] += 1
                    if len(r["programas_hoje"]) < 5: r["programas_hoje"].append(t)
                elif s == amanha:
                    r["amanha"] += 1
                    if len(r["programas_amanha"]) < 5: r["programas_amanha"].append(t)
                elif s == depois:
                    r["depois_amanha"] += 1
                    if len(r["programas_depois_amanha"]) < 5: r["programas_depois_amanha"].append(t)
        if all([r["hoje"] > 0, r["amanha"] > 0, r["depois_amanha"] > 0]):
            r["status"] = "completo"
        elif r["hoje"] > 0 or r["amanha"] > 0:
            r["status"] = "parcial"
    except: pass
    return r

def url_acessivel(url):
    try:
        r = requests.head(url, timeout=15, allow_redirects=True, headers={'User-Agent': 'Mozilla/5.0'})
        if r.status_code in range(200, 400): return True
    except: pass
    try:
        r = requests.get(url, timeout=15, stream=True, headers={'User-Agent': 'Mozilla/5.0'})
        return r.status_code in range(200, 400)
    except: return False

def consertar_logo(url):
    if not url: return ""
    if 'imgur.com' in url.lower(): return ""
    if not url.lower().endswith('.jpg'):
        base = re.sub(r'\.\w+$', '', url)
        return base + '.jpg'
    return url

def melhor_url(urls):
    for padrao in MELHOR_URL_PADROES:
        for u in urls:
            if padrao in u:
                return u
    return urls[0] if urls else ""

def normalizar_nome(n):
    n = re.sub(r'\s*\|\s*Watch.*$', '', n)
    n = re.sub(r'\s*-\s*ABC News$', '', n)
    n = re.sub(r'\s*\|\s*.*$', '', n)
    n = n.strip()
    if "ABC News Live" in n: return "ABC News Live"
    if "ABC News" in n: return "ABC News Live"
    return n

def parsear_m3u(path):
    canais = OrderedDict()
    with open(path, 'r', encoding='utf-8') as f:
        linhas = f.readlines()
    i = 0
    while i < len(linhas):
        linha = linhas[i].strip()
        if linha.startswith('#EXTINF:'):
            m = re.search(r',(.+)$', linha)
            if m:
                nome_raw = m.group(1).strip()
                nome_norm = normalizar_nome(nome_raw)
                if nome_norm not in canais:
                    canais[nome_norm] = {"urls": [], "extinf_original": linha}
                i += 1
                if i < len(linhas):
                    url = linhas[i].strip()
                    if url and not url.startswith('#'):
                        canais[nome_norm]["urls"].append(url)
        i += 1
    return canais

def main():
    print("=" * 70)
    print("CORRECAO COMPLETA lista5.m3u")
    print("=" * 70)
    agora = datetime.now()
    print(f"Data: {agora.strftime('%Y-%m-%d %H:%M')}")
    print(f"Hoje: {agora.strftime('%d/%m')} | Amanha: {(agora+timedelta(1)).strftime('%d/%m')} | Depois: {(agora+timedelta(2)).strftime('%d/%m')}")

    print("\n--- Passo 1: Parseando lista5.m3u ---")
    canais = parsear_m3u(M3U_PATH)
    print(f"Canais unicos: {len(canais)}")
    for nome, dados in canais.items():
        print(f"  - {nome} ({len(dados['urls'])} URLs)")

    print("\n--- Passo 2: Baixando EPGs ---")
    epgs = {}
    for url, nome in EPG_SOURCES:
        print(f"  {nome}...")
        conteudo = download_epg(url)
        if conteudo and len(conteudo) > 10000:
            epgs[nome] = {"conteudo": conteudo, "url": url}
            print(f"    OK: {len(conteudo):,} bytes")
        else:
            print(f"    FALHOU")

    if not epgs:
        print("ERRO: Nenhum EPG disponivel!")
        return

    # Mapeamento dos tvg-ids para ABC News Live (validado com EPG.PW)
    TVG_ID_MAP = {
        "ABC News Live": {
            "epg.pw": {"id": "465150", "programas": None},
            "iptv-epg us": {"id": "ABCNewsLive.pluto", "programas": None},
        }
    }

    print("\n--- Passo 3: Testando EPG para cada tvg-id ---")
    novos_canais = []
    epgs_usadas = set()

    for nome_norm, dados in canais.items():
        melhor_id = None
        melhor_epg_nome = None
        melhor_epg_url = None
        melhor_resultado = None

        if nome_norm in TVG_ID_MAP:
            for epg_nome in list(epgs.keys()):
                epg_key = epg_nome.lower()
                if epg_key in TVG_ID_MAP[nome_norm]:
                    info = TVG_ID_MAP[nome_norm][epg_key]
                    tvg_id = info["id"]
                    resultado = testar_programacao(epgs[epg_nome]["conteudo"], tvg_id)
                    total = resultado["hoje"] + resultado["amanha"] + resultado["depois_amanha"]
                    if total > 0 and (melhor_resultado is None or total > melhor_resultado["hoje"]+melhor_resultado["amanha"]+melhor_resultado["depois_amanha"]):
                        melhor_id = tvg_id
                        melhor_epg_nome = epg_nome
                        melhor_epg_url = epgs[epg_nome]["url"]
                        melhor_resultado = resultado

        if melhor_id is None:
            melhor_id = "465150"
            melhor_epg_nome = list(epgs.keys())[0]
            melhor_epg_url = epgs[melhor_epg_nome]["url"]
            melhor_resultado = {"status": "sem_programacao", "hoje": 0, "amanha": 0, "depois_amanha": 0,
                               "programas_hoje":[], "programas_amanha":[], "programas_depois_amanha":[]}

        if melhor_epg_url:
            epgs_usadas.add(melhor_epg_url)

        logo = "https://s.abcnews.com/images/Live/abc_news_live-abc-ml-250210_1739199021469_hpMain_16x9_608.jpg"
        logo = consertar_logo(logo)
        url = melhor_url(dados["urls"])

        attrs = []
        if melhor_id: attrs.append(f'tvg-id="{melhor_id}"')
        if logo: attrs.append(f'tvg-logo="{logo}"')
        attrs.append('group-title="NEWS WORLD"')
        if melhor_epg_url: attrs.append(f'x-tvg-url="{melhor_epg_url}"')
        extinf = f'#EXTINF:-1 {" ".join(attrs)},{nome_norm}'

        icone = "OK" if melhor_resultado["status"] == "completo" else ("PAR" if melhor_resultado["status"] == "parcial" else "---")
        print(f"  {icone} {nome_norm[:40]:<40} tvg-id={melhor_id or 'N/A':<25} H:{melhor_resultado['hoje']:>3} A:{melhor_resultado['amanha']:>3} D:{melhor_resultado['depois_amanha']:>3} [{melhor_epg_nome or 'N/A'}]")

        novos_canais.append({
            "extinf": extinf, "url": url, "nome": nome_norm,
            "tvg_id": melhor_id or "",
            "resultado": melhor_resultado
        })

    print("\n--- Passo 4: Verificando acessibilidade das URLs ---")
    canais_finais = []
    for ch in novos_canais:
        if ch["url"] and url_acessivel(ch["url"]):
            canais_finais.append(ch)
            print(f"  OK {ch['nome'][:40]:<40}")
        else:
            print(f"  X {ch['nome'][:40]:<40} INACESSIVEL - removido")

    print("\n--- Passo 5: Gerando EPGs extras (complementares) ---")
    for epg_nome in epgs:
        epgs_usadas.add(epgs[epg_nome]["url"])

    print("\n--- Passo 6: Montando #EXTM3U com x-tvg-url ---")
    urls_epg = []
    for epg_nome, epg_dados in epgs.items():
        url = epg_dados["url"]
        if url not in urls_epg:
            urls_epg.append(url)
    header = f'#EXTM3U x-tvg-url="{",".join(urls_epg)}"'
    print(f"  Header: {header}")

    print("\n--- Passo 7: Escrevendo lista5.m3u ---")
    with open(M3U_PATH, 'w', encoding='utf-8') as f:
        f.write(header + "\n")
        for ch in canais_finais:
            f.write(ch["extinf"] + "\n")
            f.write(ch["url"] + "\n")
    print(f"  Salvo: {M3U_PATH}")
    print(f"  Canais: {len(canais_finais)} | EPGs: {len(urls_epg)}")

    print("\n" + "=" * 70)
    print("RELATORIO EPG")
    print("=" * 70)
    for ch in canais_finais:
        r = ch["resultado"]
        print(f"\n{ch['nome']} (tvg-id={ch['tvg_id']}):")
        print(f"  Status: {r['status'].upper()}")
        print(f"  Hoje ({agora.strftime('%d/%m')}): {r['hoje']} programas")
        for p in r["programas_hoje"][:3]: print(f"    - {p}")
        print(f"  Amanha ({(agora+timedelta(1)).strftime('%d/%m')}): {r['amanha']} programas")
        for p in r["programas_amanha"][:3]: print(f"    - {p}")
        print(f"  Depois ({(agora+timedelta(2)).strftime('%d/%m')}): {r['depois_amanha']} programas")
        for p in r["programas_depois_amanha"][:3]: print(f"    - {p}")
    print("\n" + "=" * 70)
    print("FIM - lista5.m3u corrigida com sucesso!")

if __name__ == "__main__":
    main()
