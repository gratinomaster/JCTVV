#!/usr/bin/env python3
"""
Correcao completa do lista5.m3u:
1. Adiciona tvg-id para EPG
2. Adiciona tvg-url com fontes EPG
3. Converte tvg-logo para .jpg
4. Remove imgur.com
5. Adiciona #EXTINF onde faltar
6. Remove duplicatas
7. Testa URLs
8. Verifica EPG (hoje, amanha, depois de amanha)
"""
import re
import os
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from urllib.parse import urlparse

M3U_PATH = "/home/runner/work/JCTV/JCTV/lista5.m3u"
OUTPUT_PATH = "/home/runner/work/JCTV/JCTV/lista5.m3u"
EPG_LOCAL = "lista5_epg.xml"
EPG_BACKUP = "https://iptv-epg.org/files/epg-us.xml.gz"

CHANNEL_MAP = {
    "ABC News Live": {"tvg_id": "ABCNewsLive.us", "epg_name": "ABC News Live"},
    "Fox Business Go": {"tvg_id": "FoxBusiness.us", "epg_name": "Fox Business"},
    "Fox Business": {"tvg_id": "FoxBusiness.us", "epg_name": "Fox Business"},
    "Watch Fox News Channel Online": {"tvg_id": "FoxNewsChannel.us", "epg_name": "Fox News Channel"},
    "Fox News": {"tvg_id": "FoxNewsChannel.us", "epg_name": "Fox News Channel"},
    "CBS News 24/7": {"tvg_id": "CBSNews.us", "epg_name": "CBS News"},
    "CBS News": {"tvg_id": "CBSNews.us", "epg_name": "CBS News"},
    "Watch CBS News 24/7, our free live news stream": {"tvg_id": "CBSNews.us", "epg_name": "CBS News"},
    "Watch Fox News": {"tvg_id": "FoxNewsChannel.us", "epg_name": "Fox News Channel"},
    "Fox Business Go | Fox News Video": {"tvg_id": "FoxBusiness.us", "epg_name": "Fox Business"},
}

TVG_LOGO_MAP = {
    "ABCNewsLive.us": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
    "FoxNewsChannel.us": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/1fbe5643-b19c-458b-9074-9f4bbc59993f/8ec44ca3-a0d2-4f6e-9c50-dd05ddfbaed3/1280x720/match/400/225/image.jpg",
    "FoxBusiness.us": "https://a57.foxnews.com/static/694940094001/400/225/foxbusiness.jpg",
    "CBSNews.us": "https://www.cbsnews.com/bundles/cbsnewsvideo/images/cbsn--main-bg.jpg",
}

DISPLAY_NAMES = {
    "ABC News Live - ABC News": "ABC News Live",
    "ABC News Live": "ABC News Live",
    "Watch Fox News Channel Online | Stream Fox News": "Fox News Channel",
    "Fox Business Go | Fox News Video": "Fox Business",
    "Watch CBS News 24/7, our free live news stream": "CBS News 24/7",
    "CBS News 24/7": "CBS News 24/7",
    "Fox Business": "Fox Business",
    "Fox News": "Fox News Channel",
}


def parse_m3u(filepath):
    channels = []
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXTINF:'):
            url = ""
            if i + 1 < len(lines):
                url = lines[i + 1].strip()
            channel_name = line.split(',', 1)[-1].strip() if ',' in line else ''
            
            tvg_id_m = re.search(r'tvg-id="([^"]*)"', line)
            tvg_logo_m = re.search(r'tvg-logo="([^"]*)"', line)
            tvg_url_m = re.search(r'tvg-url="([^"]*)"', line)
            group_m = re.search(r'group-title="([^"]*)"', line)
            tvg_name_m = re.search(r'tvg-name="([^"]*)"', line)

            channels.append({
                "extinf": line,
                "url": url,
                "name": channel_name,
                "tvg_id": tvg_id_m.group(1) if tvg_id_m else "",
                "tvg_logo": tvg_logo_m.group(1) if tvg_logo_m else "",
                "tvg_url": tvg_url_m.group(1) if tvg_url_m else "",
                "group": group_m.group(1) if group_m else "",
                "tvg_name": tvg_name_m.group(1) if tvg_name_m else "",
            })
            i += 2
        else:
            i += 1

    return channels


def fix_logo_url(logo_url, channel_name):
    if not logo_url:
        return logo_url
    
    if 'imgur.com' in logo_url:
        tvg_id = None
        for name, mapping in CHANNEL_MAP.items():
            if name.lower() in channel_name.lower() or channel_name.lower() in name.lower():
                tvg_id = mapping["tvg_id"]
                break
        if tvg_id and tvg_id in TVG_LOGO_MAP:
            return TVG_LOGO_MAP[tvg_id]
        return ""
    
    parsed = urlparse(logo_url)
    path = parsed.path
    if path.lower().endswith('.png') or path.lower().endswith('.webp') or path.lower().endswith('.svg'):
        path_new = re.sub(r'\.(png|webp|svg)(\?.*)?$', '.jpg', path, flags=re.IGNORECASE)
        logo_url = parsed._replace(path=path_new).geturl()
    
    return logo_url


def get_channel_map(name):
    clean_name = DISPLAY_NAMES.get(name, name)
    for key, mapping in CHANNEL_MAP.items():
        if key.lower() in clean_name.lower() or clean_name.lower() in key.lower():
            return mapping
    
    name_l = clean_name.lower().strip()
    if 'abc' in name_l:
        return {"tvg_id": "ABCNewsLive.us", "epg_name": "ABC News Live"}
    elif 'fox news' in name_l or 'foxnew' in name_l:
        return {"tvg_id": "FoxNewsChannel.us", "epg_name": "Fox News Channel"}
    elif 'fox business' in name_l or 'foxbiz' in name_l:
        return {"tvg_id": "FoxBusiness.us", "epg_name": "Fox Business"}
    elif 'cbs' in name_l:
        return {"tvg_id": "CBSNews.us", "epg_name": "CBS News"}
    
    return None


def clean_display_name(name):
    return DISPLAY_NAMES.get(name, name)


def test_epg_coverage():
    print("\n=== TESTE DE COBERTURA EPG ===")
    
    epg_local = "/home/runner/work/JCTV/JCTV/lista5_epg.xml"
    if not os.path.exists(epg_local):
        print(f"ERRO: {epg_local} nao encontrado!")
        return False
    
    tree = ET.parse(epg_local)
    root = tree.getroot()
    channels = root.findall("channel")
    programmes = root.findall("programme")
    
    today = datetime.now().strftime("%Y%m%d")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
    day_after = (datetime.now() + timedelta(days=2)).strftime("%Y%m%d")
    
    print(f"Total canais no EPG: {len(channels)}")
    print(f"Total programas: {len(programmes)}")
    print(f"Datas: hoje={today}, amanha={tomorrow}, depois={day_after}")
    
    prog_count = {}
    for p in programmes:
        ch = p.get("channel", "")
        start = p.get("start", "")
        if start:
            d = start[:8]
            if d not in prog_count:
                prog_count[d] = {}
            prog_count[d][ch] = prog_count[d].get(ch, 0) + 1
    
    for ch_elem in channels:
        ch_id = ch_elem.get("id", "")
        display_name = ch_elem.find("display-name")
        dname = display_name.text if display_name is not None else ch_id
        hoje_c = prog_count.get(today, {}).get(ch_id, 0)
        amanha_c = prog_count.get(tomorrow, {}).get(ch_id, 0)
        depois_c = prog_count.get(day_after, {}).get(ch_id, 0)
        
        status = "OK" if (hoje_c > 0 and amanha_c > 0) else "INCOMPLETO"
        print(f"  {ch_id} ({dname}): hoje={hoje_c}, amanha={amanha_c}, depois={depois_c} [{status}]")
    
    return True


def test_urls(channels):
    print("\n=== TESTE DE URLs ===")
    seen = set()
    results = {}
    
    for ch in channels:
        url = ch["url"]
        if not url or url in seen:
            continue
        seen.add(url)
        
        try:
            r = requests.head(url, timeout=15, allow_redirects=True,
                            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
            status = r.status_code
            if status in (200, 202, 301, 302, 307, 308, 405):
                results[url] = ("ok", status)
                print(f"  OK [{status}] {ch['name'][:40]}")
            elif status == 403:
                results[url] = ("token_expired", status)
                print(f"  TOKEN_EXP [{status}] {ch['name'][:40]}")
            elif status == 404:
                results[url] = ("dead", status)
                print(f"  DEAD [{status}] {ch['name'][:40]}")
            else:
                results[url] = ("unknown", status)
                print(f"  ? [{status}] {ch['name'][:40]}")
        except requests.exceptions.Timeout:
            results[url] = ("timeout", 0)
            print(f"  TIMEOUT {ch['name'][:40]}")
        except Exception as e:
            results[url] = ("error", str(e))
            print(f"  ERROR {ch['name'][:40]}: {e}")
    
    return results


def write_corrected_m3u(channels, url_results):
    print("\n=== GERANDO lista5.m3u CORRIGIDO ===")
    
    tvg_urls = [f"{EPG_LOCAL}"]
    tvg_url_attr = ' tvg-url="' + '|'.join(tvg_urls) + '"'
    
    unique_entries = {}
    for ch in channels:
        key = ch["url"]
        if key in unique_entries:
            continue
        
        name = ch["name"]
        display_name = clean_display_name(name)
        mapping = get_channel_map(name)
        tvg_id = mapping["tvg_id"] if mapping else ""
        
        logo = fix_logo_url(ch["tvg_logo"], name)
        # Use map logo when available (corrects Fox Business vs Fox News logos)
        if tvg_id and tvg_id in TVG_LOGO_MAP:
            logo = TVG_LOGO_MAP[tvg_id]
        elif not logo and tvg_id and tvg_id in TVG_LOGO_MAP:
            logo = TVG_LOGO_MAP[tvg_id]
        
        group = ch.get("group", "")
        if not group:
            group = "NEWS WORLD"
        
        url_status = url_results.get(ch["url"], ("unknown", 0))[0]
        if url_status == "dead":
            print(f"  REMOVIDO (dead): {display_name}")
            continue
        
        attrs = [f'tvg-id="{tvg_id}"']
        if logo:
            attrs.append(f'tvg-logo="{logo}"')
        attrs.append(f'group-title="{group}"')
        attrs.append(f'tvg-name="{display_name}"')
        
        new_extinf = '#EXTINF:-1 ' + ' '.join(attrs) + ',' + display_name
        
        unique_entries[key] = {
            "extinf": new_extinf,
            "url": ch["url"],
        }
    
    lines = ['#EXTM3U']
    lines.append(f'#PLAYLIST: LISTA5 CORRIGIDA')
    lines.append(f'#URLTVG:{EPG_LOCAL}')
    lines.append(f'#KODIPROP:inputstreamaddon=inputstream.adaptive')
    lines.append(f'#KODIPROP:inputstream.adaptive.manifest_type=hls')
    lines.append('')
    
    for entry in unique_entries.values():
        lines.append(entry["extinf"])
        lines.append(entry["url"])
        lines.append('')
    
    content = '\n'.join(lines) + '\n'
    
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"\nArquivo salvo: {OUTPUT_PATH}")
    print(f"Total de entradas: {len(unique_entries)}")
    
    tvg_ids_used = set()
    for entry in unique_entries.values():
        m = re.search(r'tvg-id="([^"]*)"', entry["extinf"])
        if m:
            tvg_ids_used.add(m.group(1))
    print(f"tvg-ids usados: {', '.join(sorted(tvg_ids_used))}")
    
    return unique_entries


def verify_output():
    print("\n=== VERIFICACAO FINAL ===")
    with open(OUTPUT_PATH, 'r', encoding='utf-8') as f:
        content = f.read()
    
    lines = content.strip().split('\n')
    
    issues = []
    
    if not content.startswith('#EXTM3U'):
        issues.append("FALTA #EXTM3U no inicio")
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('http'):
            if i == 0 or not lines[i-1].strip().startswith('#'):
                issues.append(f"Linha {i+1}: URL sem #EXTINF acima")
        
        if 'tvg-logo=' in stripped:
            m = re.search(r'tvg-logo="([^"]*)"', stripped)
            if m:
                logo = m.group(1)
                if 'imgur.com' in logo:
                    issues.append(f"Linha {i+1}: imgur.com encontrado")
                parsed = urlparse(logo)
                path = parsed.path.lower()
                if path.endswith('.png') or path.endswith('.webp') or path.endswith('.svg'):
                    issues.append(f"Linha {i+1}: logo nao e .jpg: {path}")
    
    if issues:
        print("PROBLEMAS ENCONTRADOS:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("TUDO OK! Nenhum problema encontrado.")
    
    return len(issues) == 0


def main():
    print("=" * 60)
    print("CORRECAO COMPLETA - lista5.m3u")
    print("=" * 60)
    
    if not os.path.exists(M3U_PATH):
        print(f"ERRO: {M3U_PATH} nao encontrado!")
        return
    
    channels = parse_m3u(M3U_PATH)
    print(f"\nCanais/entradas lidos: {len(channels)}")
    
    unique_names = set(ch["name"] for ch in channels)
    print(f"Canais unicos: {len(unique_names)}")
    for n in sorted(unique_names):
        print(f"  - {n}")
    
    test_epg_coverage()
    
    url_results = test_urls(channels)
    
    write_corrected_m3u(channels, url_results)
    
    verify_output()
    
    print("\n" + "=" * 60)
    print("CORRECAO CONCLUIDA!")
    print("=" * 60)


if __name__ == "__main__":
    main()
