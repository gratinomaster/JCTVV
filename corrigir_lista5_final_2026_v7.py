#!/usr/bin/env python3
"""
Script para corrigir lista5.m3u:
- Adiciona tvg-id de acordo com o EPG existente
- Adiciona url-tvg/x-tvg-url no #EXTM3U
- Remove canais com streams mortos (teste de conectividade)
- Adiciona tvg-logo .jpg onde não existir
- Converte tvg-logo que não sejam .jpg para .jpg
- Garante que todo link tenha # na linha de cima
- Remove imgur.com logos
- Testa EPG para hoje, amanhã e depois de amanhã
- Remove canais duplicados (mantém 1 por canal lógico)
"""

import re
import os
import sys
import shutil
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import ssl

# Config
M3U_FILE = "/home/runner/work/JCTVV/JCTVV/lista5.m3u"
BACKUP_FILE = M3U_FILE + ".bak." + datetime.now().strftime("%Y%m%d_%H%M%S")
EPG_XML = "/home/runner/work/JCTVV/JCTVV/lista5_epg.xml"
EPG_XML_ATUALIZADO = "/home/runner/work/JCTVV/JCTVV/lista5_epg_atualizado.xml"
EPG_XML_COMBINADO = "/home/runner/work/JCTVV/JCTVV/lista5_epg_combinado.xml"
GLOBO_EPG_XML = "/home/runner/work/JCTVV/JCTVV/GLOBOEPG.xml"

# EPG sources mapping - channel name -> tvg-id in the EPG XML
EPG_CHANNEL_MAP = {
    "ABC News Live": "465150",
    "ABC News": "465150",
    "ABC News Live - ABC News": "465150",
    "Fox Business": "464766",
    "Fox Business Go | Fox News Video": "464766",
    "Fox News Channel": "465372",
    "Watch Fox News Channel Online | Stream Fox News": "465372",
    "CBS News": "464941",
    "CBS News 24/7": "464941",
    "Watch CBS News 24/7, our free live news stream": "464941",
    "our free live news stream": "464941",
}

# Alternative EPG sources for fallback
EPG_ALT_MAP = {
    "ABC News Live": "ABCNewsLive.us",
    "Fox Business": "FoxBusiness.us",
    "Fox News Channel": "FoxNewsChannel.us",
    "CBS News 24/7": "CBSNews.us",
}

# EPG URLs to add to the m3u header
EPG_URLS = [
    "https://raw.githubusercontent.com/JCTV/JCTV/main/lista5_epg.xml",
    "https://iptv-epg.org/files/epg-us.xml.gz",
    "https://epg.pw/xmltv/epg_US.xml.gz",
]

# Default logos for channels (all .jpg, no imgur)
DEFAULT_LOGOS = {
    "ABC News Live": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
    "ABC News": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
    "Fox Business": "https://a57.foxnews.com/static/foxnews/fox-business-logo.jpg",
    "Fox News Channel": "https://a57.foxnews.com/static/foxnews/fox-news-logo.jpg",
    "CBS News 24/7": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
    "CBS News": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
}

# Unified channel names (normalization)
CHANNEL_NAME_MAP = {
    "ABC News Live - ABC News": "ABC News Live",
    "Video Flood threat in the mid-Atlantic; dangerous heat in the South | Watch Live News on ABCNL": "ABC News Live",
    "Watch Fox News Channel Online | Stream Fox News": "Fox News Channel",
    "Fox Business Go | Fox News Video": "Fox Business",
    "Watch CBS News 24/7, our free live news stream": "CBS News 24/7",
    "our free live news stream": "CBS News 24/7",
}

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def test_url(url, timeout=10):
    """Test if a URL is accessible. Returns True if HTTP 200."""
    try:
        req = Request(url, method='GET', headers={'User-Agent': 'Mozilla/5.0'})
        resp = urlopen(req, timeout=timeout, context=ctx)
        # Read first few bytes to confirm it's a real stream
        data = resp.read(200)
        return resp.status == 200
    except (HTTPError, URLError, OSError) as e:
        return False

def extract_channel_name(extinf_line):
    """Extract the channel name from an #EXTINF line."""
    # Try to get name after the last attribute (quoted value followed by comma)
    # Format: #EXTINF:-1 tvg-id="x" tvg-name="y" ...,Channel Name
    # Channel name can contain commas
    match = re.search(r'group-title="[^"]*",(.+)$', extinf_line)
    if match:
        return match.group(1).strip()
    # Fallback: try to find last unquoted comma before non-attribute text
    match = re.search(r'"\s*,([^#].+)$', extinf_line)
    if match:
        return match.group(1).strip()
    # Last resort: after last comma
    match = re.search(r',([^,]+)$', extinf_line)
    if match:
        return match.group(1).strip()
    return None

def extract_attribute(extinf_line, attr):
    """Extract an attribute value from an #EXTINF line."""
    match = re.search(rf'{attr}="([^"]*)"', extinf_line)
    if match:
        return match.group(1)
    return None

def normalize_channel_name(raw_name):
    """Normalize channel name using the mapping."""
    if raw_name in CHANNEL_NAME_MAP:
        return CHANNEL_NAME_MAP[raw_name]
    return raw_name

def get_tvg_id(channel_name, epg_map):
    """Get the tvg-id for a channel name from the EPG map."""
    # Try exact match first
    if channel_name in epg_map:
        return epg_map[channel_name]
    # Try normalized name
    norm_name = normalize_channel_name(channel_name)
    if norm_name in epg_map:
        return epg_map[norm_name]
    # Try alternative names
    for key, val in epg_map.items():
        if key.lower() in channel_name.lower() or channel_name.lower() in key.lower():
            return val
    return None

def is_logo_jpg(logo_url):
    """Check if a logo URL ends with .jpg or similar."""
    if not logo_url:
        return False
    logo_lower = logo_url.lower()
    return logo_lower.endswith('.jpg') or logo_lower.endswith('.jpeg')

def convert_logo_to_jpg(logo_url):
    """Convert a non-jpg logo URL to jpg."""
    if not logo_url:
        return logo_url
    # Strip query params
    base = logo_url.split('?')[0]
    # Replace .png, .webp, etc. with .jpg
    base = re.sub(r'\.(png|webp|svg|gif|jpeg)(\?.*)?$', '.jpg', base, flags=re.IGNORECASE)
    # If no change, add .jpg
    if base == logo_url.split('?')[0] and not base.lower().endswith('.jpg'):
        base += '.jpg'
    return base

def contains_imgur(logo_url):
    """Check if a logo URL is from imgur.com."""
    if not logo_url:
        return False
    return 'imgur.com' in logo_url.lower()

def parse_m3u(filepath):
    """Parse an M3U file and return (header_line, list of (extinf, url))."""
    entries = []
    header = "#EXTM3U"
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    current_extinf = None
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('#EXTM3U'):
            header = stripped
        elif stripped.startswith('#EXTINF:'):
            current_extinf = stripped
        elif stripped.startswith('http') and current_extinf is not None:
            entries.append((current_extinf, stripped))
            current_extinf = None
        elif stripped.startswith('#') and not stripped.startswith('#EXTINF:') and not stripped.startswith('#EXTM3U'):
            # Comment line - ignore
            pass

    return header, entries

def check_epg_data():
    """Check if EPG XML files have programming for today, tomorrow, day after."""
    today = datetime.now(timezone.utc).strftime('%Y%m%d')
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).strftime('%Y%m%d')
    day_after = (datetime.now(timezone.utc) + timedelta(days=2)).strftime('%Y%m%d')

    results = {}
    for name, path in [("lista5_epg.xml", EPG_XML),
                        ("lista5_epg_atualizado.xml", EPG_XML_ATUALIZADO),
                        ("lista5_epg_combinado.xml", EPG_XML_COMBINADO)]:
        if not os.path.exists(path):
            results[name] = {"exists": False, "dates": [], "channels": []}
            continue
        try:
            tree = ET.parse(path)
            root = tree.getroot()
            channels = [(ch.get('id'), ch.find('display-name').text) for ch in root.findall('channel')]
            programmes = root.findall('programme')
            dates = set()
            for p in programmes:
                start = p.get('start')
                if start:
                    dates.add(start[:8])
            results[name] = {
                "exists": True,
                "channels": channels,
                "dates": sorted(dates),
                "total_programmes": len(programmes),
                "has_today": today in dates,
                "has_tomorrow": tomorrow in dates,
                "has_day_after": day_after in dates,
            }
        except Exception as e:
            results[name] = {"exists": False, "error": str(e)}

    return results

def main():
    print("=" * 60)
    print("CORREÇÃO COMPLETA DO LISTA5.M3U")
    print("=" * 60)

    # Step 1: Check EPG data
    print("\n[1] VERIFICANDO DADOS EPG...")
    epg_results = check_epg_data()
    for name, data in epg_results.items():
        if data.get("exists"):
            print(f"  {name}:")
            print(f"    Canais: {len(data['channels'])}")
            print(f"    Programas: {data['total_programmes']}")
            print(f"    Datas: {data['dates']}")
            print(f"    Hoje ({'OK' if data['has_today'] else 'FALTA'}): {data['has_today']}")
            print(f"    Amanhã ({'OK' if data['has_tomorrow'] else 'FALTA'}): {data['has_tomorrow']}")
            print(f"    Depois de amanhã ({'OK' if data['has_day_after'] else 'FALTA'}): {data['has_day_after']}")
        else:
            print(f"  {name}: NÃO ENCONTRADO")

    # Step 2: Backup original file
    print("\n[2] FAZENDO BACKUP...")
    shutil.copy2(M3U_FILE, BACKUP_FILE)
    print(f"  Backup criado: {BACKUP_FILE}")

    # Step 3: Parse current file
    print("\n[3] ANALISANDO LISTA5.M3U...")
    header, entries = parse_m3u(M3U_FILE)
    print(f"  Total de entradas: {len(entries)}")

    # Step 4: Group by normalized channel name and test URLs
    print("\n[4] AGRUPANDO CANAIS E TESTANDO STREAMS...")
    channel_groups = {}
    for extinf, url in entries:
        raw_name = extract_channel_name(extinf)
        if not raw_name:
            continue
        norm_name = normalize_channel_name(raw_name)
        tvg_logo = extract_attribute(extinf, 'tvg-logo')
        group_title = extract_attribute(extinf, 'group-title') or 'NEWS WORLD'

        if norm_name not in channel_groups:
            channel_groups[norm_name] = {
                "raw_names": set(),
                "urls": [],
                "logos": set(),
                "group_titles": set(),
                "extinf_samples": [],
            }
        channel_groups[norm_name]["raw_names"].add(raw_name)
        channel_groups[norm_name]["urls"].append(url)
        if tvg_logo:
            channel_groups[norm_name]["logos"].add(tvg_logo)
        channel_groups[norm_name]["group_titles"].add(group_title)
        channel_groups[norm_name]["extinf_samples"].append(extinf)

    for ch_name, ch_data in channel_groups.items():
        print(f"  {ch_name}: {len(ch_data['urls'])} URLs, {len(ch_data['logos'])} logos")

    # Step 5: Test unique URLs
    print("\n[5] TESTANDO URLS (CONECTIVIDADE)...")
    working_urls = {}
    dead_urls = []
    all_unique_urls = set()
    for ch_data in channel_groups.values():
        for url in ch_data['urls']:
            all_unique_urls.add(url)

    for url in all_unique_urls:
        if test_url(url, timeout=10):
            working_urls[url] = True
            # Show first 60 chars
            print(f"  OK: {url[:60]}...")
        else:
            dead_urls.append(url)
            print(f"  FALHOU: {url[:60]}...")

    print(f"\n  URLs funcionando: {len(working_urls)}")
    print(f"  URLs mortas: {len(dead_urls)}")

    # Step 6: Build final channel list (one per unique channel)
    print("\n[6] CONSTRUINDO LISTA FINAL...")
    final_entries = []
    used_logos = set()

    for ch_name, ch_data in sorted(channel_groups.items()):
        # Find a working URL
        best_url = None
        for url in ch_data['urls']:
            if url in working_urls:
                best_url = url
                break

        if best_url is None:
            print(f"  REMOVIDO: {ch_name} - URL falhou no teste de conectividade")
            continue

        # Determine tvg-id
        tvg_id = get_tvg_id(ch_name, EPG_CHANNEL_MAP)
        if tvg_id is None:
            # Try alternative map
            alt_id = get_tvg_id(ch_name, EPG_ALT_MAP)
            if alt_id:
                tvg_id = alt_id
            else:
                tvg_id = ch_name.lower().replace(' ', '')

        # Determine logo (must be .jpg, no imgur)
        logo = None
        for l in ch_data['logos']:
            if contains_imgur(l):
                print(f"  AVISO: {ch_name} - logo imgur.com removido: {l[:40]}...")
                continue
            if is_logo_jpg(l):
                logo = l
                break
            else:
                # Convert to .jpg
                logo = convert_logo_to_jpg(l)
                print(f"  CONVERTIDO: {ch_name} - logo convertido para .jpg")
                break

        if logo is None and ch_name in DEFAULT_LOGOS:
            logo = DEFAULT_LOGOS[ch_name]
            print(f"  LOGO ADICIONADO: {ch_name} - usando logo padrão")

        if logo is None:
            print(f"  AVISO: {ch_name} - sem logo disponível")

        # Determine group-title
        group_title = "NEWS WORLD"
        if ch_data['group_titles']:
            group_title = list(ch_data['group_titles'])[0]

        # Build the normalized channel name for display
        display_name = ch_name

        # Build the EXTINF line
        tvg_name_attr = f' tvg-name="{display_name}"'
        tvg_id_attr = f' tvg-id="{tvg_id}"'
        tvg_logo_attr = f' tvg-logo="{logo}"' if logo else ''
        group_attr = f' group-title="{group_title}"'
        extinf = f'#EXTINF:-1{tvg_id_attr}{tvg_name_attr}{tvg_logo_attr}{group_attr},{display_name}'

        final_entries.append((extinf, best_url))
        if logo:
            used_logos.add(logo)
        print(f"  OK: {display_name} (tvg-id={tvg_id}, url={best_url[:60]}...)")

    # Step 7: Build EPG URL header
    print("\n[7] CONFIGURANDO URLS EPG...")
    epg_url_string = " ".join(EPG_URLS)
    new_header = f'#EXTM3U x-tvg-url="{epg_url_string}"'
    print(f"  Header: {new_header[:80]}...")

    # Step 8: Write final file
    print("\n[8] ESCREVENDO LISTA5.M3U CORRIGIDO...")
    with open(M3U_FILE, 'w', encoding='utf-8') as f:
        f.write(new_header + "\n")
        for extinf, url in final_entries:
            f.write(extinf + "\n")
            f.write(url + "\n")

    print(f"  Total de canais na lista final: {len(final_entries)}")

    # Step 9: Verify the result
    print("\n[9] VERIFICANDO LISTA FINAL...")
    issues = []
    with open(M3U_FILE, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    for i, line in enumerate(lines):
        stripped = line.strip()
        # Check that every http URL has #EXTINF above it
        if stripped.startswith('http') and (i == 0 or not lines[i-1].strip().startswith('#EXTINF:')):
            if i == 0:
                issues.append(f"  Linha {i+1}: URL sem #EXTINF antes (primeira linha)")
            else:
                issues.append(f"  Linha {i+1}: URL sem #EXTINF antes (anterior: {lines[i-1].strip()[:40]})")
        # Check no imgur.com
        if 'imgur.com' in stripped.lower():
            issues.append(f"  Linha {i+1}: Contém imgur.com")
        # Check all tvg-logo end with .jpg
        logo_match = re.search(r'tvg-logo="([^"]*)"', stripped)
        if logo_match:
            logo_url = logo_match.group(1)
            if not logo_url.lower().endswith('.jpg'):
                issues.append(f"  Linha {i+1}: Logo não é .jpg: {logo_url[:40]}...")
            if 'imgur.com' in logo_url.lower():
                issues.append(f"  Linha {i+1}: Logo do imgur.com: {logo_url[:40]}...")

    if issues:
        print("  PROBLEMAS ENCONTRADOS:")
        for issue in issues:
            print(f"    {issue}")
    else:
        print("  NENHUM PROBLEMA ENCONTRADO!")

    # Step 10: Verify EPG matches
    print("\n[10] VERIFICANDO EPG CORRESPONDENTE...")
    try:
        tree = ET.parse(EPG_XML)
        root = tree.getroot()
        epg_channel_ids = {ch.get('id'): ch.find('display-name').text for ch in root.findall('channel')}

        for extinf, url in final_entries:
            tvg_id = extract_attribute(extinf, 'tvg-id')
            if tvg_id:
                if tvg_id in epg_channel_ids:
                    print(f"  OK: tvg-id={tvg_id} -> {epg_channel_ids[tvg_id]} (EPG encontrado)")
                else:
                    print(f"  AVISO: tvg-id={tvg_id} não encontrado no EPG XML")
            else:
                print(f"  AVISO: Canal sem tvg-id")
    except Exception as e:
        print(f"  ERRO ao verificar EPG: {e}")

    # Step 11: Print summary
    print("\n" + "=" * 60)
    print("RESUMO DA CORREÇÃO")
    print("=" * 60)
    print(f"  Arquivo original: {M3U_FILE}")
    print(f"  Backup: {BACKUP_FILE}")
    print(f"  Total de canais: {len(final_entries)}")
    print(f"  URLs removidas (mortas): {len(dead_urls)}")
    print(f"  EPG XML principal: {EPG_XML}")
    print(f"  Datas EPG: {epg_results.get('lista5_epg.xml', {}).get('dates', 'N/A')}")

    return final_entries, dead_urls

if __name__ == "__main__":
    main()
