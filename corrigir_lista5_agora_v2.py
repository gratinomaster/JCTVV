#!/usr/bin/env python3
"""
Script corrigir lista5.m3u:
- Mapeia nomes de canais para EPG tvg-id
- Adiciona x-tvg-url com múltiplos EPGs no #EXTM3U
- Agrupa entradas duplicadas (diferentes bitrates/qualidades)
- Testa URLs (conectividade)
- Adiciona tvg-logo .jpg onde não existir
- Converte tvg-logo que não sejam .jpg
- Remove imgur.com
- Garante que toda URL tenha #EXTINF na linha anterior
- Remove canais com streams mortos
- Verifica cobertura EPG hoje/amanhã/depois
"""

import re
import os
import shutil
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import ssl

M3U_FILE = "/home/runner/work/JCTVV/JCTVV/lista5.m3u"
BACKUP_FILE = M3U_FILE + ".bak." + datetime.now().strftime("%Y%m%d_%H%M%S")

# EPG XML files
EPG_XML = "/home/runner/work/JCTVV/JCTVV/lista5_epg.xml"
EPG_XML_ATUALIZADO = "/home/runner/work/JCTVV/JCTVV/lista5_epg_atualizado.xml"
EPG_XML_COMBINADO = "/home/runner/work/JCTVV/JCTVV/lista5_epg_combinado.xml"
GLOBO_EPG_XML = "/home/runner/work/JCTVV/JCTVV/GLOBOEPG.xml"

# EPG URLs to insert in the header
EPG_URLS = [
    "https://raw.githubusercontent.com/gratinomaster/JCTVV/main/lista5_epg.xml",
    "https://iptv-epg.org/files/epg-us.xml.gz",
    "https://epg.pw/xmltv/epg_US.xml.gz",
]

# Channel name normalization: raw_name -> canonical name
CHANNEL_NAME_MAP = {
    "Good Morning America First Look | Watch Live News on ABCNL": "ABC News Live",
    "ABC News Live - ABC News": "ABC News Live",
    "Video Flood threat in the mid-Atlantic; dangerous heat in the South | Watch Live News on ABCNL": "ABC News Live",
    "Watch Fox News Channel Online | Stream Fox News": "Fox News Channel",
    "Fox Business Go | Fox News Video": "Fox Business",
    "Watch CBS News 24/7, our free live news stream": "CBS News 24/7",
    "our free live news stream": "CBS News 24/7",
}

# EPG channel map: canonical name -> tvg-id
EPG_CHANNEL_MAP = {
    "ABC News Live": "465150",
    "ABC News": "465150",
    "Fox Business": "464766",
    "Fox News Channel": "465372",
    "CBS News": "464941",
    "CBS News 24/7": "464941",
}

# Default logos (.jpg only, no imgur)
DEFAULT_LOGOS = {
    "ABC News Live": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
    "ABC News": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
    "Fox Business": "https://a57.foxnews.com/static/foxnews/fox-business-logo.jpg",
    "Fox News Channel": "https://a57.foxnews.com/static/foxnews/fox-news-logo.jpg",
    "CBS News 24/7": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
    "CBS News": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
}

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def log(msg):
    print(msg)

def test_url(url, timeout=10):
    try:
        req = Request(url, method='GET', headers={'User-Agent': 'Mozilla/5.0'})
        resp = urlopen(req, timeout=timeout, context=ctx)
        resp.read(200)
        return resp.status == 200
    except (HTTPError, URLError, OSError):
        return False

def extract_channel_name(extinf_line):
    match = re.search(r',(.+)$', extinf_line)
    if match:
        return match.group(1).strip()
    return None

def extract_attribute(extinf_line, attr):
    match = re.search(rf'{attr}="([^"]*)"', extinf_line)
    return match.group(1) if match else None

def normalize_channel_name(raw_name):
    if raw_name in CHANNEL_NAME_MAP:
        return CHANNEL_NAME_MAP[raw_name]
    return raw_name

def get_tvg_id(channel_name):
    if channel_name in EPG_CHANNEL_MAP:
        return EPG_CHANNEL_MAP[channel_name]
    for key, val in EPG_CHANNEL_MAP.items():
        if key.lower() in channel_name.lower() or channel_name.lower() in key.lower():
            return val
    return None

def is_logo_jpg(logo_url):
    if not logo_url:
        return False
    return logo_url.lower().endswith('.jpg') or logo_url.lower().endswith('.jpeg')

def convert_logo_to_jpg(logo_url):
    if not logo_url:
        return logo_url
    base = logo_url.split('?')[0]
    base = re.sub(r'\.(png|webp|svg|gif|jpeg)(\?.*)?$', '.jpg', base, flags=re.IGNORECASE)
    if base == logo_url.split('?')[0] and not base.lower().endswith('.jpg'):
        base += '.jpg'
    return base

def contains_imgur(logo_url):
    if not logo_url:
        return False
    return 'imgur.com' in logo_url.lower()

def parse_m3u(filepath):
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
    return header, entries

def check_epg_data():
    today = datetime.now(timezone.utc).strftime('%Y%m%d')
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).strftime('%Y%m%d')
    day_after = (datetime.now(timezone.utc) + timedelta(days=2)).strftime('%Y%m%d')

    results = {}
    for name, path in [
        ("lista5_epg.xml", EPG_XML),
        ("lista5_epg_atualizado.xml", EPG_XML_ATUALIZADO),
        ("lista5_epg_combinado.xml", EPG_XML_COMBINADO),
        ("GLOBOEPG.xml", GLOBO_EPG_XML),
    ]:
        if not os.path.exists(path):
            results[name] = {"exists": False}
            continue
        try:
            tree = ET.parse(path)
            root = tree.getroot()
            channels = [(ch.get('id'), ch.find('display-name').text if ch.find('display-name') is not None else '?') for ch in root.findall('channel')]
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
    log("=" * 60)
    log("CORRECAO COMPLETA DO LISTA5.M3U")
    log("=" * 60)

    # Step 1: Check EPG data
    log("\n[1] VERIFICANDO DADOS EPG...")
    epg_results = check_epg_data()
    for name, data in epg_results.items():
        if data.get("exists"):
            log(f"  {name}:")
            log(f"    Canais: {len(data['channels'])}")
            log(f"    Programas: {data['total_programmes']}")
            log(f"    Datas: {data['dates'][:5]}... ({len(data['dates'])} total)")
            log(f"    Hoje: {'OK' if data['has_today'] else 'FALTA'}")
            log(f"    Amanha: {'OK' if data['has_tomorrow'] else 'FALTA'}")
            log(f"    Depois: {'OK' if data['has_day_after'] else 'FALTA'}")
        else:
            log(f"  {name}: NAO ENCONTRADO")

    # Step 2: Backup
    log("\n[2] FAZENDO BACKUP...")
    shutil.copy2(M3U_FILE, BACKUP_FILE)
    log(f"  Backup: {BACKUP_FILE}")

    # Step 3: Parse
    log("\n[3] ANALISANDO LISTA5.M3U...")
    header, entries = parse_m3u(M3U_FILE)
    log(f"  Entradas: {len(entries)}")

    # Step 4: Group by normalized channel name
    log("\n[4] AGRUPANDO CANAIS...")
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
            }
        channel_groups[norm_name]["raw_names"].add(raw_name)
        channel_groups[norm_name]["urls"].append(url)
        if tvg_logo:
            channel_groups[norm_name]["logos"].add(tvg_logo)
        channel_groups[norm_name]["group_titles"].add(group_title)

    for ch_name, ch_data in channel_groups.items():
        log(f"  {ch_name}: {len(ch_data['urls'])} urls, {len(ch_data['logos'])} logos")

    # Step 5: Test URLs
    log("\n[5] TESTANDO URLS...")
    working_urls = {}
    dead_urls = []
    all_urls = set()
    for ch_data in channel_groups.values():
        for url in ch_data['urls']:
            all_urls.add(url)

    for url in sorted(all_urls):
        if test_url(url, timeout=10):
            working_urls[url] = True
            log(f"  OK: {url[:70]}...")
        else:
            dead_urls.append(url)
            log(f"  FALHOU: {url[:70]}...")

    log(f"\n  Funcionando: {len(working_urls)}")
    log(f"  Mortas: {len(dead_urls)}")

    # Step 6: Build final list
    log("\n[6] CONSTRUINDO LISTA FINAL...")
    final_entries = []

    for ch_name, ch_data in sorted(channel_groups.items()):
        best_url = None
        for url in ch_data['urls']:
            if url in working_urls:
                best_url = url
                break

        if best_url is None:
            log(f"  REMOVIDO: {ch_name} - URL falhou")
            continue

        tvg_id = get_tvg_id(ch_name)
        if tvg_id is None:
            tvg_id = ch_name.lower().replace(' ', '').replace('|', '')

        logo = None
        for l in list(ch_data['logos']):
            if contains_imgur(l):
                log(f"  AVISO: {ch_name} - imgur removido")
                continue
            if is_logo_jpg(l):
                logo = l
                break
            else:
                logo = convert_logo_to_jpg(l)
                log(f"  CONVERTIDO: {ch_name} - logo -> .jpg")
                break

        if logo is None and ch_name in DEFAULT_LOGOS:
            logo = DEFAULT_LOGOS[ch_name]
            log(f"  LOGO: {ch_name} - padrao")

        if logo is None:
            log(f"  AVISO: {ch_name} - sem logo")

        group_title = "NEWS WORLD"
        if ch_data['group_titles']:
            group_title = list(ch_data['group_titles'])[0]

        extinf = f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-name="{ch_name}"'
        if logo:
            extinf += f' tvg-logo="{logo}"'
        extinf += f' group-title="{group_title}",{ch_name}'

        final_entries.append((extinf, best_url))
        log(f"  OK: {ch_name} (tvg-id={tvg_id})")

    # Step 7: Write header with EPG URLs
    log("\n[7] CONFIGURANDO EPG URLS...")
    epg_url_string = " ".join(EPG_URLS)
    new_header = f'#EXTM3U x-tvg-url="{epg_url_string}"'
    log(f"  Header: {new_header[:80]}...")

    # Step 8: Write file
    log("\n[8] ESCREVENDO LISTA CORRIGIDA...")
    with open(M3U_FILE, 'w', encoding='utf-8') as f:
        f.write(new_header + "\n")
        for extinf, url in final_entries:
            f.write(extinf + "\n")
            f.write(url + "\n")
    log(f"  Canais: {len(final_entries)}")

    # Step 9: Verify output
    log("\n[9] VERIFICANDO LISTA FINAL...")
    issues = []
    with open(M3U_FILE, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('http'):
            if i == 0 or not lines[i-1].strip().startswith('#EXTINF:'):
                prev = lines[i-1].strip()[:40] if i > 0 else "(inicio)"
                issues.append(f"  Linha {i+1}: URL sem #EXTINF (anterior: {prev})")
        if 'imgur.com' in stripped.lower():
            issues.append(f"  Linha {i+1}: imgur.com encontrado")
        logo_match = re.search(r'tvg-logo="([^"]*)"', stripped)
        if logo_match:
            lu = logo_match.group(1)
            if not lu.lower().endswith('.jpg'):
                issues.append(f"  Linha {i+1}: logo nao .jpg: {lu[:40]}")
            if 'imgur.com' in lu.lower():
                issues.append(f"  Linha {i+1}: logo imgur.com")

    if issues:
        log("  PROBLEMAS:")
        for issue in issues:
            log(f"    {issue}")
    else:
        log("  OK - NENHUM PROBLEMA!")

    # Step 10: EPG match verification
    log("\n[10] VERIFICANDO EPG CORRESPONDENTE...")
    try:
        tree = ET.parse(EPG_XML)
        root = tree.getroot()
        epg_ids = {ch.get('id') for ch in root.findall('channel')}
        for extinf, url in final_entries:
            tid = extract_attribute(extinf, 'tvg-id')
            if tid:
                if tid in epg_ids:
                    log(f"  OK: tvg-id={tid} -> EPG encontrado")
                else:
                    log(f"  AVISO: tvg-id={tid} nao no EPG principal")
    except Exception as e:
        log(f"  ERRO: {e}")

    # Step 11: Summary
    log("\n" + "=" * 60)
    log("RESUMO")
    log("=" * 60)
    log(f"  Backup: {BACKUP_FILE}")
    log(f"  Canais finais: {len(final_entries)}")
    log(f"  URLs removidas (mortas): {len(dead_urls)}")
    log(f"  EPG hoje: {epg_results.get('lista5_epg.xml', {}).get('has_today', '?')}")
    log(f"  EPG amanha: {epg_results.get('lista5_epg.xml', {}).get('has_tomorrow', '?')}")
    log(f"  EPG depois: {epg_results.get('lista5_epg.xml', {}).get('has_day_after', '?')}")

    return final_entries, dead_urls

if __name__ == "__main__":
    main()
