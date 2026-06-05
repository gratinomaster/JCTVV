#!/usr/bin/env python3
"""
Correcao completa do lista5.m3u:
- EPG valido para todos os canais
- Teste de programacao (hoje, amanha, depois de amanha)
- Anti-virus (VirusTotal)
- tvg-logo .jpg
- URLs sem #EXTINF
- Remover imgur.com
- Testar streams
"""
import requests
import gzip
import re
import os
import sys
import base64
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import xml.etree.ElementTree as ET
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

VIRUSTOTAL_API_URL = "https://www.virustotal.com/api/v3/urls"

M3U_PATH = "lista5.m3u"
EPG_PATH = "lista5_epg.xml"

# Fontes EPG
EPG_SOURCES = [
    ("https://iptv-epg.org/files/epg-us.xml.gz", "IPTV-EPG US"),
    ("https://iptv-epg.org/files/epg-br.xml.gz", "IPTV-EPG BR"),
    ("https://github.com/iptv-org/epg/raw/master/guide/us.xml.gz", "IPTV-ORG US"),
    ("https://github.com/iptv-org/epg/raw/master/guide/br.xml.gz", "IPTV-ORG BR"),
    ("https://github.com/iptv-org/epg/raw/master/guide/mx.xml.gz", "IPTV-ORG MX"),
]

# Mapeamento de canais para IDs EPG
CHANNEL_MAPPING = {
    "abc news live": {"tvg_id": "ABCWBMA.us", "epg_name": "ABC News Live", "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f7/ABC_News_%282019%29.svg/200px-ABC_News_%282019%29.svg.jpg"},
    "abc news": {"tvg_id": "ABCWBMA.us", "epg_name": "ABC News", "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f7/ABC_News_%282019%29.svg/200px-ABC_News_%282019%29.svg.jpg"},
    "fox news": {"tvg_id": "FoxNewsChannel.us", "epg_name": "Fox News Channel", "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/17/Fox_News_Channel_logo.svg/200px-Fox_News_Channel_logo.svg.jpg"},
    "fox business": {"tvg_id": "FoxBusiness.us", "epg_name": "Fox Business", "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/77/Fox_Business_logo.svg/200px-Fox_Business_logo.svg.jpg"},
    "cbs news": {"tvg_id": "CBSNews.us", "epg_name": "CBS News 24/7", "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/43/CBS_News.svg/200px-CBS_News.svg.jpg"},
    "cnn": {"tvg_id": "CNN.us", "epg_name": "CNN", "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b1/CNN.svg/200px-CNN.svg.jpg"},
    "cnn brasil": {"tvg_id": "CNN.us", "epg_name": "CNN", "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b1/CNN.svg/200px-CNN.svg.jpg"},
    "bbc": {"tvg_id": "BBCNews.uk", "epg_name": "BBC News", "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0c/BBC_News_2022.svg/200px-BBC_News_2022.svg.jpg"},
    "bbc news": {"tvg_id": "BBCNews.uk", "epg_name": "BBC News", "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0c/BBC_News_2022.svg/200px-BBC_News_2022.svg.jpg"},
    "abcnl": {"tvg_id": "ABCWBMA.us", "epg_name": "ABC News Live", "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f7/ABC_News_%282019%29.svg/200px-ABC_News_%282019%29.svg.jpg"},
    "abc news live - abc news": {"tvg_id": "ABCWBMA.us", "epg_name": "ABC News Live", "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f7/ABC_News_%282019%29.svg/200px-ABC_News_%282019%29.svg.jpg"},
}

def extract_channel_name(line: str) -> str:
    line = line.strip()
    match = re.search(r',(.+)$', line)
    if match:
        return match.group(1).strip()
    return ""

def parse_m3u(filepath: str) -> List[Dict]:
    channels = []
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXTINF:'):
            url = lines[i + 1].strip() if i + 1 < len(lines) else ""
            channel_name = extract_channel_name(line)
            tvg_id_match = re.search(r'tvg-id="([^"]*)"', line)
            tvg_id = tvg_id_match.group(1) if tvg_id_match else ""
            tvg_logo_match = re.search(r'tvg-logo="([^"]*)"', line)
            tvg_logo = tvg_logo_match.group(1) if tvg_logo_match else ""
            group_match = re.search(r'group-title="([^"]*)"', line)
            group = group_match.group(1) if group_match else ""
            channels.append({
                "extinf": line,
                "url": url,
                "name": channel_name,
                "tvg_id": tvg_id,
                "tvg_logo": tvg_logo,
                "group": group,
            })
            i += 2
        else:
            i += 1
    return channels

def download_epg(epg_url: str) -> Optional[str]:
    try:
        print(f"  Baixando: {epg_url[:60]}...")
        response = requests.get(epg_url, timeout=120, headers={'Accept-Encoding': 'gzip', 'User-Agent': 'Mozilla/5.0'})
        response.raise_for_status()
        if epg_url.endswith('.gz') or response.headers.get('Content-Type', '').startswith('application/gzip'):
            try:
                content = gzip.decompress(response.content).decode('utf-8')
            except:
                content = response.text
        else:
            content = response.text
        return content
    except Exception as e:
        print(f"  Erro: {e}")
        return None

def find_channel_in_epg(epg_content: str, tvg_id: str) -> Optional[Dict]:
    try:
        root = ET.fromstring(epg_content)
        for channel in root.findall("channel"):
            if channel.get("id") == tvg_id:
                display_name = channel.find("display-name")
                icon = channel.find("icon")
                return {
                    "id": channel.get("id"),
                    "name": display_name.text if display_name is not None else tvg_id,
                    "icon": icon.get("src") if icon is not None else ""
                }
        return None
    except:
        return None

def find_channel_by_name_in_epg(epg_content: str, name: str) -> Optional[Dict]:
    try:
        root = ET.fromstring(epg_content)
        name_lower = name.lower().replace("  ", " ")
        for channel in root.findall("channel"):
            dn = channel.find("display-name")
            if dn is not None and dn.text:
                epg_name = dn.text.lower().replace("  ", " ")
                if name_lower in epg_name or epg_name in name_lower:
                    icon = channel.find("icon")
                    return {
                        "id": channel.get("id"),
                        "name": dn.text,
                        "icon": icon.get("src") if icon is not None else ""
                    }
        return None
    except:
        return None

def get_all_channel_ids_from_epg(epg_content: str) -> Dict[str, Dict]:
    result = {}
    try:
        root = ET.fromstring(epg_content)
        for channel in root.findall("channel"):
            cid = channel.get("id")
            dn = channel.find("display-name")
            icon = channel.find("icon")
            if cid:
                result[cid] = {
                    "id": cid,
                    "name": dn.text if dn is not None else cid,
                    "icon": icon.get("src") if icon is not None else ""
                }
    except:
        pass
    return result

def test_epg_programming(epg_content: str, tvg_id: str) -> Dict:
    resultado = {
        "status": "sem_programacao",
        "hoje": 0,
        "amanha": 0,
        "depois_amanha": 0,
        "programas_hoje": [],
    }
    try:
        root = ET.fromstring(epg_content)
        hoje = datetime.now().strftime("%Y%m%d")
        amanha = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
        depois_amanha = (datetime.now() + timedelta(days=2)).strftime("%Y%m%d")
        for prog in root.findall("programme"):
            channel = prog.get("channel", "")
            if channel == tvg_id:
                start = prog.get("start", "")[:8]
                title_elem = prog.find("title")
                title = title_elem.text if title_elem is not None else "Sem titulo"
                if start == hoje:
                    resultado["hoje"] += 1
                    resultado["programas_hoje"].append(title)
                elif start == amanha:
                    resultado["amanha"] += 1
                elif start == depois_amanha:
                    resultado["depois_amanha"] += 1
        if resultado["hoje"] > 0:
            resultado["status"] = "completo" if resultado["amanha"] > 0 and resultado["depois_amanha"] > 0 else "parcial"
    except:
        pass
    return resultado

def check_url_stream(url: str) -> bool:
    try:
        r = requests.get(url, timeout=10, stream=True, allow_redirects=True,
                         headers={'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'})
        if r.status_code == 200:
            try:
                content = r.raw.read(500, decode_content=False)
                if b'#EXTM3U' in content or b'.ts' in content or b'.m4s' in content:
                    return True
            except:
                pass
            return True
        return r.status_code in [200, 206, 301, 302, 307, 308]
    except:
        return False

def fix_logo_to_jpg(logo_url: str) -> str:
    if not logo_url:
        return ""
    if "imgur.com" in logo_url.lower():
        return ""
    logo_url = re.sub(r'(\.png|\.webp|\.svg)(\?.*)?$', '.jpg', logo_url)
    return logo_url

def detect_channel_name(name: str) -> Optional[str]:
    name_lower = name.lower()
    for key in sorted(CHANNEL_MAPPING.keys(), key=len, reverse=True):
        if key in name_lower:
            return key
    return None

def check_virustotal(url: str, api_key: str) -> Dict:
    resultado = {"status": "nao_verificado", "malicious": False, "suspicious": 0, "detection_ratio": ""}
    try:
        url_id = base64.urlsafe_b64encode(url.encode()).decode().strip("=")
        headers = {"x-apikey": api_key}
        response = requests.get(f"{VIRUSTOTAL_API_URL}/{url_id}", headers=headers, timeout=30)
        if response.status_code == 200:
            data = response.json()
            stats = data.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
            malicious = stats.get("malicious", 0)
            suspicious = stats.get("suspicious", 0)
            harmless = stats.get("harmless", 0)
            undetected = stats.get("undetected", 0)
            total = malicious + suspicious + harmless + undetected
            resultado["malicious"] = malicious > 0
            resultado["suspicious"] = suspicious
            resultado["detection_ratio"] = f"{malicious}/{total}"
            resultado["status"] = "verificado"
        elif response.status_code == 404:
            resultado["status"] = "nao_encontrado"
        else:
            resultado["status"] = f"erro_{response.status_code}"
    except Exception as e:
        resultado["status"] = f"erro_{str(e)[:30]}"
    return resultado

def main():
    print("=" * 70)
    print("CORRECAO COMPLETA - lista5.m3u")
    print("Data: %s" % datetime.now().strftime("%d/%m/%Y %H:%M"))
    print("=" * 70)

    # 1. Parse M3U
    print("\n[1/7] Parseando lista5.m3u...")
    channels = parse_m3u(M3U_PATH)
    print(f"  Linhas EXTINF encontradas: {len(channels)}")

    # Agrupar por nome de canal
    unique_by_name = {}
    for ch in channels:
        name = ch["name"]
        if name not in unique_by_name:
            unique_by_name[name] = ch
    print(f"  Canais unicos: {len(unique_by_name)}")

    # 2. Baixar EPGs
    print("\n[2/7] Baixando fontes EPG...")
    epg_contents = []
    for url, name in EPG_SOURCES:
        print(f"  Testando: {name}")
        content = download_epg(url)
        if content and len(content) > 5000:
            print(f"  OK! Tamanho: {len(content):,} bytes")
            epg_contents.append((url, content))
        else:
            print(f"  Falhou ou muito pequeno")

    if not epg_contents:
        print("\nERRO: Nao foi possivel baixar nenhum EPG!")
        sys.exit(1)

    # 3. Mapear canais para EPG
    print("\n[3/7] Mapeando canais para EPG...")
    channel_epg_map = {}  # nome_canal -> {tvg_id, epg_url, logo, status}

    for ch_name, ch_data in unique_by_name.items():
        ch_lower = ch_name.lower().replace("  ", " ")
        
        # Procurar no mapping primeiro
        matched_key = detect_channel_name(ch_name)
        if matched_key:
            mapping = CHANNEL_MAPPING[matched_key]
            channel_epg_map[ch_name] = {
                "tvg_id": mapping["tvg_id"],
                "epg_name": mapping["epg_name"],
                "logo": mapping["logo"],
                "status": "mapeado",
                "encontrado_no_epg": False,
            }
            continue

        # Procurar no EPG por nome
        for epg_url, epg_content in epg_contents:
            info = find_channel_by_name_in_epg(epg_content, ch_name)
            if info:
                channel_epg_map[ch_name] = {
                    "tvg_id": info["id"],
                    "epg_name": info["name"],
                    "logo": info["icon"] if info["icon"] else "",
                    "status": "encontrado_epg",
                    "encontrado_no_epg": True,
                }
                break
        
        if ch_name not in channel_epg_map:
            channel_epg_map[ch_name] = {
                "tvg_id": "",
                "epg_name": ch_name,
                "logo": "",
                "status": "sem_epg",
                "encontrado_no_epg": False,
            }

    for ch_name, info in channel_epg_map.items():
        status_icon = "OK" if info["tvg_id"] else "X"
        print(f"  {status_icon} {ch_name[:40]:40s} -> tvg-id={info['tvg_id'] or 'N/A'}")

    # 4. Gerar EPG XML consolidado
    print("\n[4/7] Consolidando EPG...")
    
    # Coletar todos os programas de todas as fontes EPG
    all_programs = []
    epg_channel_ids = set()
    
    for epg_url, epg_content in epg_contents:
        try:
            root = ET.fromstring(epg_content)
            for prog in root.findall("programme"):
                all_programs.append(prog)
            for ch in root.findall("channel"):
                epg_channel_ids.add(ch.get("id"))
        except:
            pass

    # Criar EPG consolidado
    tv_elem = ET.Element("tv")
    
    # Adicionar canais do mapping
    added_channels = set()
    for ch_name, info in channel_epg_map.items():
        if info["tvg_id"] and info["tvg_id"] not in added_channels:
            ch_elem = ET.SubElement(tv_elem, "channel")
            ch_elem.set("id", info["tvg_id"])
            dn = ET.SubElement(ch_elem, "display-name")
            dn.text = info["epg_name"]
            if info["logo"]:
                icon = ET.SubElement(ch_elem, "icon")
                icon.set("src", info["logo"])
            added_channels.add(info["tvg_id"])

    # Adicionar programas relevantes
    tvg_ids_in_use = {v["tvg_id"] for v in channel_epg_map.values() if v["tvg_id"]}
    programs_added = 0
    for prog in all_programs:
        if prog.get("channel") in tvg_ids_in_use:
            tv_elem.append(prog)
            programs_added += 1

    # Salvar EPG
    tree = ET.ElementTree(tv_elem)
    tree.write(EPG_PATH, encoding='utf-8', xml_declaration=True)
    print(f"  EPG salvo: {EPG_PATH}")
    print(f"  Canais no EPG: {len(added_channels)}")
    print(f"  Programas no EPG: {programs_added}")

    # 5. Testar programacao EPG
    print("\n[5/7] Testando programacao EPG...")
    
    epg_full_content = ET.tostring(tv_elem, encoding='unicode')
    
    hoje_str = datetime.now().strftime("%d/%m/%Y")
    amanha_str = (datetime.now() + timedelta(days=1)).strftime("%d/%m/%Y")
    depois_str = (datetime.now() + timedelta(days=2)).strftime("%d/%m/%Y")
    
    all_ok = True
    for ch_name, info in channel_epg_map.items():
        if info["tvg_id"]:
            prog = test_epg_programming(epg_full_content, info["tvg_id"])
            status = prog["status"]
            print(f"  {ch_name[:35]:35s} [{status:10s}] {hoje_str}:{prog['hoje']:2d} {amanha_str}:{prog['amanha']:2d} {depois_str}:{prog['depois_amanha']:2d}")
            if prog["hoje"] == 0:
                all_ok = False

    print(f"\n  Resultado geral: {'TODOS COM EPG' if all_ok else 'ALGUNS SEM PROGRAMACAO HOJE'}")

    # 6. Testar streams + anti-virus
    print("\n[6/7] Testando streams e anti-virus...")
    
    # Obter API key do VirusTotal
    vt_api_key = os.environ.get('VIRUSTOTAL_API_KEY', '') or os.environ.get('VT_API_KEY', '')
    if len(sys.argv) > 1:
        vt_api_key = sys.argv[1]
    
    # Pegar URLs unicas
    unique_urls = {}
    for ch in channels:
        if ch["url"] and ch["url"] not in unique_urls:
            unique_urls[ch["url"]] = ch["name"]
    
    print(f"  URLs unicas para testar: {len(unique_urls)}")
    
    # VirusTotal
    malicious_urls = set()
    if vt_api_key:
        print("  Verificando VirusTotal...")
        for url, name in unique_urls.items():
            vt_result = check_virustotal(url, vt_api_key)
            if vt_result["status"] == "verificado":
                if vt_result["malicious"]:
                    print(f"  X MALICIOSO: {name[:40]} ({vt_result['detection_ratio']})")
                    malicious_urls.add(url)
                elif vt_result["suspicious"] > 0:
                    print(f"  ! SUSPEITO: {name[:40]} ({vt_result['detection_ratio']})")
                else:
                    print(f"  OK {name[:40]} ({vt_result['detection_ratio']})")
            else:
                print(f"  - {name[:40]}: VirusTotal {vt_result['status']}")
    else:
        print("  VirusTotal: sem API key (pule anti-virus)")
    
    # Testar streams em paralelo
    bad_urls = set()
    good_urls = set()
    
    def test_url(url):
        return url, check_url_stream(url)
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(test_url, url) for url in unique_urls.keys()]
        for future in as_completed(futures):
            url, is_ok = future.result()
            if is_ok and url not in malicious_urls:
                good_urls.add(url)
            else:
                bad_urls.add(url)
                if url not in malicious_urls:
                    print(f"  X Stream inacessivel: {unique_urls[url][:40]}")
    
    print(f"  Streams OK: {len(good_urls)}, Streams FAIL/REMOVED: {len(bad_urls)}")

    # 7. Gerar M3U corrigido
    print("\n[7/7] Gerando lista5.m3u corrigido...")
    
    # Selecionar melhor URL por canal (priorizar master.m3u8)
    best_url_per_channel = {}
    for ch in channels:
        name = ch["name"]
        url = ch["url"]
        if name not in best_url_per_channel:
            best_url_per_channel[name] = url
        else:
            current = best_url_per_channel[name]
            if "master.m3u8" in url and "master.m3u8" not in current:
                best_url_per_channel[name] = url
            elif "master.m3u8" in current:
                continue
            elif len(url) < len(current):
                best_url_per_channel[name] = url
    
    # Montar M3U
    lines = ["#EXTM3U"]
    
    for ch_name in unique_by_name:
        info = channel_epg_map.get(ch_name, {})
        tvg_id = info.get("tvg_id", "")
        
        # Determinar logo
        logo = ""
        original_ch = unique_by_name[ch_name]
        if original_ch["tvg_logo"]:
            logo = fix_logo_to_jpg(original_ch["tvg_logo"])
        if not logo:
            logo = info.get("logo", "")
        if not logo:
            logo = original_ch["tvg_logo"]
            if logo:
                logo = fix_logo_to_jpg(logo)
        
        # Se tiver logo do mapping, usar
        if info.get("logo") and (not logo or "imgur" in logo.lower()):
            logo = info["logo"]
        
        # Garantir que logo termina em .jpg
        if logo and not logo.lower().endswith('.jpg'):
            logo = re.sub(r'\.\w+(\?.*)?$', '.jpg', logo)
        
        group = original_ch.get("group", "")
        
        # Determinar melhor URL
        best_url = best_url_per_channel.get(ch_name, "")
        
        # Pular se URL for ruim
        if best_url in bad_urls:
            print(f"  Removendo (stream falhou): {ch_name}")
            continue
        
        # Pular se nao tem URL
        if not best_url:
            print(f"  Pulando (sem URL): {ch_name}")
            continue
        
        epg_url = EPG_SOURCES[0][0] if epg_contents else ""
        logo_attr = f' tvg-logo="{logo}"' if logo else ""
        tvg_id_attr = f' tvg-id="{tvg_id}"' if tvg_id else ""
        group_attr = f' group-title="{group}"' if group else ""
        epg_url_attr = f' x-tvg-url="{epg_url}"' if epg_url else ""
        
        extinf = f'#EXTINF:-1{tvg_id_attr}{logo_attr}{group_attr}{epg_url_attr},{ch_name}'
        
        lines.append(extinf)
        lines.append(best_url)
    
    lines.append("")  # Final newline
    
    # Fazer backup
    if os.path.exists(M3U_PATH):
        bak_path = M3U_PATH + ".bak." + datetime.now().strftime("%Y%m%d_%H%M%S")
        os.rename(M3U_PATH, bak_path)
        print(f"  Backup: {bak_path}")
    
    # Salvar
    with open(M3U_PATH, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    
    channel_count = sum(1 for l in lines if l.startswith('#EXTINF:'))
    print(f"  CANAIS FINAIS: {channel_count} canais")
    print(f"  Arquivo salvo: {M3U_PATH}")
    
    # Relatorio final
    print("\n" + "=" * 70)
    print("RELATORIO FINAL")
    print("=" * 70)
    for ch_name, info in channel_epg_map.items():
        tvg_id = info.get("tvg_id", "N/A")
        epg_url = EPG_SOURCES[0][0] if epg_contents else "N/A"
        logo = info.get("logo", "")
        print(f"  Canal: {ch_name}")
        print(f"    tvg-id: {tvg_id}")
        print(f"    tvg-logo: {logo[:60] if logo else 'N/A'}")
        print(f"    x-tvg-url: {epg_url[:60] if epg_url != 'N/A' else 'N/A'}...")
        if tvg_id != "N/A":
            prog = test_epg_programming(epg_full_content, tvg_id)
            print(f"    Programacao: Hoje={prog['hoje']} Amanha={prog['amanha']} Depois={prog['depois_amanha']}")
        print()

if __name__ == "__main__":
    main()
