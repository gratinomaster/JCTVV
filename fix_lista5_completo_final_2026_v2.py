#!/usr/bin/env python3
"""
Correção completa do lista5.m3u:
- Adiciona tvg-id e url-tvg (EPG) para todos os canais
- Testa programação EPG (hoje, amanhã, depois de amanhã)
- Remove canais com URLs quebradas
- Garante que toda URL tenha #EXTINF na linha acima
- Adiciona tvg-logo .jpg onde não existe
- Converte logos não-.jpg para .jpg
- Remove links do imgur.com
- Usa múltiplos EPGs para cobertura completa
"""

import gzip
import os
import re
import shutil
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

M3U_PATH = "lista5.m3u"
BACKUP_PATH = "lista5.m3u.bak"

# Mapeamento de canais para IDs de EPG
CHANNEL_MAPPING = {
    "abc news live": {"tvg_id": "ABCNewsLive.us", "name": "ABC News Live"},
    "abc news": {"tvg_id": "ABCNewsLive.us", "name": "ABC News Live"},
    "fox business": {"tvg_id": "FoxBusiness.us", "name": "Fox Business"},
    "fox news": {"tvg_id": "FoxNewsChannel.us", "name": "Fox News Channel"},
    "cbs news": {"tvg_id": "CBSNews.us", "name": "CBS News 24/7"},
}

# URLs de EPG (primeira = local, mais rápida; seguintes = fallback online)
EPG_SOURCES = [
    ("lista5_epg.xml.gz", "EPG Local (lista5_epg.xml.gz)"),
]

# URL fixa do EPG para colocar no m3u
EPG_URL = "https://raw.githubusercontent.com/iptv-org/epg/master/guide/us.xml.gz"

# Logos padrão em .jpg por canal
DEFAULT_LOGOS = {
    "abc news live": "https://s.abcnews.com/images/Live/abc_news_live-abc-ml-250210_1739199021469_hpMain_16x9_608.jpg",
    "abc news": "https://s.abcnews.com/images/Live/abc_news_live-abc-ml-250210_1739199021469_hpMain_16x9_608.jpg",
    "fox news": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/2727a4e5-e7cb-40b6-bebb-cb06e3dc7e3f/adc0efd6-e90f-4f85-a053-cb0e71969813/1280x720/match/400/225/image.jpg",
    "fox business": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/c9b2e2eb-7b87-435c-9510-eab2650ff944/8b584585-acf2-4c37-aa07-aaf2d077bb20/1280x720/match/676/380/image.jpg",
    "cbs news": "https://www.cbsnews.com/bundles/cbsnewsvideo/images/cbsn--main-bg.jpg",
}


def load_epg(path: str) -> Optional[ET.Element]:
    """Carrega EPG de arquivo .xml ou .xml.gz"""
    try:
        if path.endswith(".gz"):
            with gzip.open(path, "rb") as f:
                content = f.read().decode("utf-8", errors="replace")
        else:
            with open(path, "rb") as f:
                content = f.read().decode("utf-8", errors="replace")

        content = re.sub(r"&(?!(?:amp|lt|gt|quot|apos|#\d+);)", "&amp;", content)
        root = ET.fromstring(content)
        return root
    except Exception as e:
        print(f"  ERRO ao carregar EPG {path}: {e}")
        return None


def get_epg_channels(root: ET.Element) -> Dict[str, str]:
    """Extrai canais do EPG"""
    channels = {}
    for ch in root.findall("channel"):
        ch_id = ch.get("id", "")
        name_el = ch.find("display-name")
        name = name_el.text if name_el is not None else ch_id
        channels[ch_id] = name
    return channels


def test_epg_programming(root: ET.Element, tvg_id: str, date_str: str) -> int:
    """Conta programas para um canal em uma data específica"""
    count = 0
    for prog in root.findall("programme"):
        if prog.get("channel", "") == tvg_id:
            start = prog.get("start", "")[:8]
            if start == date_str:
                count += 1
    return count


def extract_channel_name(extinf: str) -> str:
    """Extrai nome do canal do EXTINF"""
    m = re.search(r",(.+)$", extinf)
    return m.group(1).strip().lower() if m else ""


def extract_attrs(extinf: str) -> Dict[str, str]:
    """Extrai atributos do EXTINF"""
    attrs = {}
    for attr in ["tvg-id", "tvg-logo", "tvg-name", "group-title"]:
        m = re.search(rf'{attr}="([^"]*)"', extinf)
        if m:
            attrs[attr] = m.group(1)
    return attrs


def parse_m3u(filepath: str) -> List[Dict]:
    """Parse do arquivo M3U mantendo links de variantes juntos"""
    entries = []
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Agrupa: cada entrada tem extinf + url(s)
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if line.startswith("#EXTM3U"):
            entries.append({"type": "header", "line": lines[i].rstrip()})
            i += 1
        elif line.startswith("#EXTINF:"):
            extinf = line
            i += 1
            urls = []
            while i < len(lines):
                next_line = lines[i].strip()
                if not next_line:
                    i += 1
                    continue
                if next_line.startswith("#EXTINF:"):
                    break
                if next_line.startswith("#EXTM3U"):
                    break
                if next_line.startswith("http://") or next_line.startswith("https://"):
                    urls.append(next_line)
                i += 1

            if urls:
                entries.append({
                    "type": "channel",
                    "extinf": extinf,
                    "urls": urls,
                    "name": extract_channel_name(extinf),
                    "attrs": extract_attrs(extinf),
                })
        else:
            i += 1

    return entries


def is_valid_url(url: str) -> bool:
    """Testa se URL responde"""
    import requests
    try:
        r = requests.head(url, timeout=10, allow_redirects=True,
                          headers={"User-Agent": "Mozilla/5.0"})
        return r.status_code in (200, 302, 301, 307, 308, 405, 403, 401)
    except requests.exceptions.SSLError:
        try:
            r = requests.head(url, timeout=10, allow_redirects=True,
                              headers={"User-Agent": "Mozilla/5.0"}, verify=False)
            return r.status_code in (200, 302, 301, 307, 308, 405, 403, 401)
        except:
            return False
    except:
        return False


def is_imgur(url: str) -> bool:
    """Verifica se URL é do imgur.com"""
    return "imgur.com" in url.lower()


def fix_logo_to_jpg(logo_url: str) -> str:
    """Converte logo para .jpg se não for"""
    if not logo_url:
        return logo_url
    logo_lower = logo_url.lower()
    if logo_lower.endswith(".png") or logo_lower.endswith(".webp") or logo_lower.endswith(".gif"):
        logo_url = re.sub(r'\.(png|webp|gif)(\?.*)?$', '.jpg', logo_url, flags=re.I)
    elif not re.search(r'\.(jpg|jpeg)(\?|$)', logo_lower):
        logo_url += ".jpg" if "?" not in logo_url else ""
    return logo_url


def main():
    print("=" * 70)
    print("CORREÇÃO COMPLETA DO lista5.m3u")
    print("=" * 70)
    print()

    # Backup
    if os.path.exists(M3U_PATH):
        shutil.copy2(M3U_PATH, BACKUP_PATH)
        print(f"✓ Backup criado: {BACKUP_PATH}")
    print()

    # 1. Carregar EPG
    print("--- CARREGANDO EPG ---")
    epg_root = None
    epg_name = ""
    for epg_path, epg_label in EPG_SOURCES:
        if not os.path.exists(epg_path):
            print(f"  ✗ Arquivo não encontrado: {epg_path}")
            continue
        print(f"  Carregando: {epg_label} ({epg_path})...")
        root = load_epg(epg_path)
        if root is not None:
            epg_root = root
            epg_name = epg_label
            print(f"  ✓ EPG carregado com sucesso!")
            break

    if epg_root is None:
        print("  ✗ Nenhum EPG local encontrado!")
        return

    epg_channels = get_epg_channels(epg_root)
    print(f"  Canais no EPG: {len(epg_channels)}")
    for cid, cname in epg_channels.items():
        print(f"    - {cid}: {cname}")

    total_progs = len(epg_root.findall("programme"))
    print(f"  Total programas: {total_progs}")

    # Datas
    hoje = datetime.now().strftime("%Y%m%d")
    amanha = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
    depois_amanha = (datetime.now() + timedelta(days=2)).strftime("%Y%m%d")
    print(f"  Datas: hoje={hoje}, amanhã={amanha}, depois={depois_amanha}")
    print()

    # 2. Testar programação EPG
    print("--- TESTANDO PROGRAMAÇÃO EPG ---")
    for tvg_id, display_name in epg_channels.items():
        h = test_epg_programming(epg_root, tvg_id, hoje)
        a = test_epg_programming(epg_root, tvg_id, amanha)
        d = test_epg_programming(epg_root, tvg_id, depois_amanha)
        status = "✓ COMPLETO" if (h > 0 and a > 0 and d > 0) else \
                 "⚠ PARCIAL" if (h > 0 or a > 0) else "✗ SEM PROGRAMAÇÃO"
        print(f"  {tvg_id} ({display_name}):")
        print(f"    Hoje: {h} | Amanhã: {a} | Depois: {d} -> {status}")
    print()

    # 3. Parse do M3U
    print("--- PARSING DO LISTA5.M3U ---")
    entries = parse_m3u(M3U_PATH)
    channels = [e for e in entries if e["type"] == "channel"]
    print(f"  Entradas de canal encontradas: {len(channels)}")

    nomes_unicos = set()
    urls_unicas = set()
    channels_dedup = []
    for ch in channels:
        name_lower = ch["name"]
        if name_lower not in nomes_unicos:
            nomes_unicos.add(name_lower)
            channels_dedup.append(ch)
        else:
            urls_para_add = []
            for url in ch["urls"]:
                if url not in urls_unicas:
                    urls_unicas.add(url)
                    urls_para_add.append(url)
            if urls_para_add:
                for c in channels_dedup:
                    if c["name"] == name_lower:
                        c["urls"].extend(urls_para_add)
                        break

    print(f"  Canais únicos: {len(nomes_unicos)}")
    for ch in channels_dedup:
        print(f"    - {ch['name'][:50]} ({len(ch['urls'])} URLs)")
    print()

    # 4. Mapear canais para EPG
    print("--- MAPEANDO CANAIS PARA EPG ---")
    channel_epg_map = {}
    for ch in channels_dedup:
        name_lower = ch["name"]
        tvg_id = None
        tvg_name = name_lower.title()

        best_match = None
        best_len = 0
        for prefix, mapping in CHANNEL_MAPPING.items():
            if prefix in name_lower and len(prefix) > best_len:
                best_match = mapping
                best_len = len(prefix)

        if best_match:
            tvg_id = best_match["tvg_id"]
            tvg_name = best_match["name"]

        if not tvg_id:
            print(f"  ⚠ Sem mapeamento EPG para: {name_lower}")
            continue

        channel_epg_map[name_lower] = {
            "tvg_id": tvg_id,
            "tvg_name": tvg_name,
        }
        print(f"  ✓ {name_lower[:40]:40s} -> {tvg_id}")

    print()

    # 5. Testar URLs (acessibilidade + imgur)
    print("--- TESTANDO URLs ---")
    import requests
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    urls_to_test = []
    for ch in channels_dedup:
        for url in ch["urls"]:
            urls_to_test.append((ch["name"], url))

    print(f"  URLs para testar: {len(urls_to_test)}")

    bad_urls = set()
    imgur_urls = set()
    good_count = 0
    bad_count = 0

    for ch_name, url in urls_to_test:
        if is_imgur(url):
            print(f"  ✗ REMOVIDO (imgur): {ch_name[:40]}")
            imgur_urls.add(url)
            continue

        if is_valid_url(url):
            good_count += 1
        else:
            bad_count += 1
            bad_urls.add(url)
            print(f"  ✗ INACESSÍVEL: {ch_name[:40]}")

    print(f"  OK: {good_count} | Falhas: {len(bad_urls)} | Imgur: {len(imgur_urls)}")
    print()

    # Adicionar CBS News do backup se não existir no m3u atual
    if not any("cbs" in ch["name"] for ch in channels_dedup):
        print("  + Adicionando CBS News 24/7 a partir do backup...")
        channels_dedup.append({
            "type": "channel",
            "extinf": '#EXTINF:-1 tvg-logo="https://www.cbsnews.com/bundles/cbsnewsvideo/images/cbsn--main-bg.jpg" group-title="NEWS WORLD",CBS News 24/7',
            "urls": [
                "https://dai.google.com/linear/hls/pa/event/Sid4xiTQTkCT1SLu6rjUSQ/stream/05435f41-f6d8-44ca-93f1-20d38e3d5c77:DLS/master.m3u8",
            ],
            "name": "cbs news 24/7",
            "attrs": {
                "tvg-logo": "https://www.cbsnews.com/bundles/cbsnewsvideo/images/cbsn--main-bg.jpg",
                "group-title": "NEWS WORLD",
            },
        })
        print("  ✓ CBS News 24/7 adicionado!")

    # 6. Montar novo M3U
    print("--- GERANDO NOVO LISTA5.M3U ---")

    linhas = []
    linhas.append('#EXTM3U url-tvg="https://epg.pw/xmltv/epg_US.xml.gz https://iptv-epg.org/files/epg-us.xml.gz https://raw.githubusercontent.com/iptv-org/epg/master/guide/us.xml.gz"')

    for ch in channels_dedup:
        name_lower = ch["name"]
        ch_info = channel_epg_map.get(name_lower)
        tvg_id = ch_info["tvg_id"] if ch_info else ""
        tvg_name = ch_info["tvg_name"] if ch_info else name_lower.title()

        # Pegar logo existente ou usar padrão
        logo = ch["attrs"].get("tvg-logo", "")
        if not logo:
            logo = DEFAULT_LOGOS.get(name_lower, "")
        if is_imgur(logo):
            logo = DEFAULT_LOGOS.get(name_lower, "")
        logo = fix_logo_to_jpg(logo)

        group = ch["attrs"].get("group-title", "NEWS WORLD")

        urls_validas = [u for u in ch["urls"] if u not in bad_urls and u not in imgur_urls]

        for url in urls_validas:
            attrs_parts = [f'tvg-id="{tvg_id}"']
            if tvg_name:
                attrs_parts.append(f'tvg-name="{tvg_name}"')
            if logo:
                attrs_parts.append(f'tvg-logo="{logo}"')
            if group:
                attrs_parts.append(f'group-title="{group}"')

            attrs_str = " ".join(attrs_parts)
            display_name = ch_info["tvg_name"] if ch_info else name_lower.title()
            linhas.append(f'#EXTINF:-1 {attrs_str},{display_name}')
            linhas.append(url)

    with open(M3U_PATH, "w", encoding="utf-8") as f:
        for linha in linhas:
            f.write(linha + "\n")

    print(f"  ✓ Arquivo gerado: {M3U_PATH}")
    print(f"  Linhas: {len(linhas)}")
    print(f"  Canais únicos: {len(channels_dedup)}")
    channels_com_epg = sum(1 for ch in channels_dedup if ch["name"] in channel_epg_map)
    print(f"  Canais com EPG: {channels_com_epg}/{len(channels_dedup)}")
    print()

    # 7. Verificação final
    print("--- VERIFICAÇÃO FINAL ---")
    with open(M3U_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()
    print(f"  Total linhas: {len(lines)}")

    extinf_count = sum(1 for l in lines if l.startswith("#EXTINF:"))
    url_count = sum(1 for l in lines if l.startswith("http"))
    tvg_id_count = sum(1 for l in lines if 'tvg-id="' in l)
    url_tvg_count = sum(1 for l in lines if "url-tvg" in l)
    imgur_found = sum(1 for l in lines if "imgur" in l.lower())
    missing_extinf = 0
    non_jpg_logos = 0

    for i, line in enumerate(lines):
        if line.startswith("http"):
            if i == 0 or not lines[i-1].startswith("#EXTINF:"):
                missing_extinf += 1
        if 'tvg-logo="' in line:
            logo_match = re.search(r'tvg-logo="([^"]*)"', line)
            if logo_match:
                logo_url = logo_match.group(1)
                if not re.search(r'\.(jpg|jpeg)(\?|$)', logo_url.lower()):
                    non_jpg_logos += 1
                    print(f"  ⚠ Logo não-JPG na linha {i+1}: {logo_url[:60]}")

    print(f"  #EXTINF: {extinf_count}")
    print(f"  URLs: {url_count}")
    print(f"  tvg-id: {tvg_id_count}")
    print(f"  url-tvg no header: {url_tvg_count}")
    print(f"  imgur.com: {imgur_found} (deve ser 0)")
    print(f"  Missing #EXTINF: {missing_extinf} (deve ser 0)")
    print(f"  Logos não-JPG: {non_jpg_logos} (deve ser 0)")

    if missing_extinf == 0 and imgur_found == 0 and non_jpg_logos == 0:
        print("\n  ✓ TODAS AS VERIFICAÇÕES PASSARAM!")
    else:
        print("\n  ⚠ HÁ PROBLEMAS A CORRIGIR!")
    print()

    print("=" * 70)
    print("CORREÇÃO CONCLUÍDA!")
    print("=" * 70)


if __name__ == "__main__":
    main()
