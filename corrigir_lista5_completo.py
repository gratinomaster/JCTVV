#!/usr/bin/env python3
import re
import requests
import gzip
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

M3U_PATH = "lista5.m3u"
TEMPLATE_PATH = "lista5_fixed.m3u"
EPG_SOURCE_URL = "https://raw.githubusercontent.com/gratinomaster/JCTV/main/lista5_epg.xml.gz"

CHANNEL_CONFIG = [
    {
        "names": ["ABC News Live", "abc news live", "ABC News", "abc news"],
        "tvg_id": "ABCNewsLive.us",
        "tvg_logo": "https://keyframe-cdn.abcnews.com/streamprovider5.jpg",
        "group": "NEWS WORLD",
    },
    {
        "names": ["Fox News", "fox news channel", "fox news", "Watch Fox News"],
        "tvg_id": "FoxNewsChannel.us",
        "tvg_logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/a6a5c792-7fc5-4cbd-a17f-5c17b855647d/d5bbc9d6-134a-4eb2-a923-931842d1e2dd/1280x720/match/400/225/image.jpg",
        "group": "NEWS WORLD",
    },
    {
        "names": ["Fox Business", "fox business", "Fox Business Go"],
        "tvg_id": "FoxBusiness.us",
        "tvg_logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/a6a5c792-7fc5-4cbd-a17f-5c17b855647d/d5bbc9d6-134a-4eb2-a923-931842d1e2dd/1280x720/match/400/225/image.jpg",
        "group": "NEWS WORLD",
    },
    {
        "names": ["CBS News", "cbs news", "Watch CBS News", "CBS News 24/7"],
        "tvg_id": "CBSNews.us",
        "tvg_logo": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
        "group": "NEWS WORLD",
    },
]


def norm_name(name: str) -> str:
    return re.sub(r'[^a-z0-9]', '', name.lower())


def match_channel(name: str) -> Optional[Dict]:
    nname = norm_name(name)
    if 'abcnl' in nname or 'memorial' in nname:
        return CHANNEL_CONFIG[0]
    # Check longer names first for specificity
    scored = []
    for cfg in CHANNEL_CONFIG:
        for cname in cfg["names"]:
            ncname = norm_name(cname)
            score = 0
            if ncname in nname:
                score = len(ncname)
            elif nname in ncname:
                score = len(nname)
            if score > 0:
                scored.append((score, cfg))
    if scored:
        scored.sort(key=lambda x: -x[0])
        return scored[0][1]
    return None


def parse_m3u(filepath: str) -> Tuple[str, List[Dict]]:
    header = "#EXTM3U"
    channels = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except:
        return header, channels

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXTM3U'):
            header = line
            i += 1
        elif line.startswith('#EXTINF:'):
            url = lines[i + 1].strip() if i + 1 < len(lines) else ""
            if not url:
                i += 1
                continue

            tvg_id_m = re.search(r'tvg-id="([^"]*)"', line)
            tvg_logo_m = re.search(r'tvg-logo="([^"]*)"', line)
            group_m = re.search(r'group-title="([^"]*)"', line)
            name_m = re.search(r',(.+)$', line)

            channels.append({
                "extinf": line,
                "url": url,
                "name": name_m.group(1).strip() if name_m else "",
                "tvg_id": tvg_id_m.group(1) if tvg_id_m else "",
                "tvg_logo": tvg_logo_m.group(1) if tvg_logo_m else "",
                "group": group_m.group(1) if group_m else "",
            })
            i += 2
        else:
            i += 1
    return header, channels


def check_url(url: str) -> bool:
    try:
        r = requests.get(url, timeout=10, allow_redirects=True, stream=True,
                          headers={'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'})
        ok_codes = [200, 301, 302, 303, 307, 308, 405, 416, 503, 502]
        return r.status_code in ok_codes
    except requests.exceptions.Timeout:
        return True
    except:
        return False


def test_epg_programming(tvg_id: str) -> Dict:
    result = {"status": "sem_programacao", "hoje": 0, "amanha": 0, "depois_amanha": 0}
    try:
        import os
        epg_file = 'lista5_epg.xml.gz'
        if not os.path.exists(epg_file):
            return {"status": "sem_programacao", "hoje": 0, "amanha": 0, "depois_amanha": 0, "erro": "arquivo_nao_encontrado"}
        with gzip.open(epg_file, 'rb') as f:
            content = f.read()
        root = ET.fromstring(content)

        hoje = datetime.now().strftime("%Y%m%d")
        amanha = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
        depois_amanha = (datetime.now() + timedelta(days=2)).strftime("%Y%m%d")

        for prog in root.findall("programme"):
            ch = prog.get("channel", "")
            if ch == tvg_id:
                start = prog.get("start", "")[:8]
                if start == hoje:
                    result["hoje"] += 1
                elif start == amanha:
                    result["amanha"] += 1
                elif start == depois_amanha:
                    result["depois_amanha"] += 1

        if result["hoje"] > 0 and result["amanha"] > 0 and result["depois_amanha"] > 0:
            result["status"] = "completo"
        elif result["hoje"] > 0:
            result["status"] = "parcial"
    except Exception as e:
        result["status"] = f"erro: {e}"
    return result


def fix_logo_url(logo: str) -> str:
    if not logo:
        return logo
    if 'imgur.com' in logo:
        return ""
    logo = logo.rstrip('/')
    if not logo.lower().endswith('.jpg') and not logo.lower().endswith('.jpeg'):
        logo = re.sub(r'\.[^./]+$', '.jpg', logo)
    return logo


import urllib.parse

def get_base_domain(url):
    try:
        parts = urllib.parse.urlparse(url).netloc.split('.')
        if len(parts) >= 2:
            return '.'.join(parts[-2:])
        return '.'.join(parts)
    except:
        return ""


def pick_best_url(urls_by_domain):
    """Escolhe a melhor URL, 1 por canal (prioriza melhor qualidade)"""
    # Flatten by base domain first
    by_base = {}
    for domain, chs in urls_by_domain.items():
        for ch in chs:
            base = get_base_domain(ch["url"])
            if base not in by_base:
                by_base[base] = []
            by_base[base].append(ch["url"])

    result = []
    for base, urls in by_base.items():
        if not urls:
            continue
        if 'dssott' in base or 'disney' in base:
            best = None
            for u in urls:
                if '2400K' in u or '2400_hdri' in u:
                    best = u
            result.append(best or urls[0])
        elif 'akamaized' in base:
            best = None
            for u in urls:
                if u.endswith('index.m3u8'):
                    best = u
            result.append(best or urls[0])
        elif 'google' in base:
            best = None
            for u in urls:
                if '/master.m3u8' in u:
                    best = u
            result.append(best or urls[0])
        elif 'fox' in base:
            best = None
            for u in urls:
                if '/master.m3u8' in u:
                    best = u
            result.append(best or urls[0])
        else:
            result.append(urls[0])
    return result


def main():
    print("=" * 70)
    print("CORREÇÃO COMPLETA DO lista5.m3u")
    print("=" * 70)

    print("\n[1/6] Lendo lista5_fixed.m3u (template de canais)...")
    _, template_channels = parse_m3u(TEMPLATE_PATH)
    print(f"  Canais no template: {len(template_channels)}")

    print("\n[2/6] Lendo lista5.m3u atual...")
    header, current_channels = parse_m3u(M3U_PATH)
    print(f"  Canais atuais: {len(current_channels)}")

    print("\n[3/6] Consolidando canais únicos com metadados EPG...")
    # Group by tvg_id
    from collections import defaultdict
    by_tvg_id = defaultdict(lambda: defaultdict(list))

    for ch in template_channels + current_channels:
        cfg = match_channel(ch["name"])
        tvg_id = cfg["tvg_id"] if cfg else ""
        # Extract domain for quality grouping
        from urllib.parse import urlparse
        try:
            domain = urlparse(ch["url"]).netloc
        except:
            domain = "unknown"
        by_tvg_id[tvg_id][domain].append(ch)

    fixed_channels = []
    for tvg_id, domain_groups in by_tvg_id.items():
        if tvg_id == "":
            # Try to match unnamed channels
            for domain, chs in domain_groups.items():
                for ch in chs:
                    cfg2 = match_channel(ch["name"])
                    if cfg2:
                        tvg_id = cfg2["tvg_id"]
                    if not tvg_id:
                        continue
                    logo = fix_logo_url(ch["tvg_logo"]) or (cfg2["tvg_logo"] if cfg2 else "")
                    attrs = f'tvg-id="{tvg_id}"'
                    if logo:
                        attrs += f' tvg-logo="{logo}"'
                    attrs += f' group-title="{ch.get("group") or "NEWS WORLD"}"'
                    new_extinf = f'#EXTINF:-1 {attrs},{ch["name"]}'
                    fixed_channels.append({
                        "extinf": new_extinf,
                        "url": ch["url"],
                        "name": ch["name"],
                        "tvg_id": tvg_id,
                    })
            continue

        cfg = None
        for c in CHANNEL_CONFIG:
            if c["tvg_id"] == tvg_id:
                cfg = c
                break

        best_urls = pick_best_url(domain_groups)
        for url in best_urls:
            # Find the original channel entry for this URL
            found_ch = None
            for ch in template_channels + current_channels:
                if ch["url"] == url:
                    found_ch = ch
                    break
            if not found_ch:
                continue

            logo = fix_logo_url(found_ch["tvg_logo"]) or (cfg["tvg_logo"] if cfg else "")
            attrs = f'tvg-id="{tvg_id}"'
            if logo:
                attrs += f' tvg-logo="{logo}"'
            attrs += f' group-title="{found_ch.get("group") or (cfg["group"] if cfg else "NEWS WORLD")}"'
            new_extinf = f'#EXTINF:-1 {attrs},{found_ch["name"]}'
            fixed_channels.append({
                "extinf": new_extinf,
                "url": url,
                "name": found_ch["name"],
                "tvg_id": tvg_id,
            })

    print(f"  Canais consolidados: {len(fixed_channels)}")

    print("\n[4/6] Verificando URLs...")
    working_urls = set()
    broken_urls = []

    def check_and_report(ch_info):
        name = ch_info["name"]
        url = ch_info["url"]
        ok = check_url(url)
        return (name, url, ok)

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(check_and_report, ch) for ch in fixed_channels]
        for future in as_completed(futures):
            name, url, ok = future.result()
            if ok:
                working_urls.add(url)
                print(f"  OK {name[:45]}")
            else:
                broken_urls.append(url)
                print(f"  X {name[:45]} - inacessível")

    channels_finais = [ch for ch in fixed_channels if ch["url"] in working_urls]
    removidos = [ch for ch in fixed_channels if ch["url"] not in working_urls]
    if removidos:
        print(f"\n  Canais removidos (URL inacessível): {len(removidos)}")
        for ch in removidos:
            print(f"    - {ch['name']}")

    print(f"\n[5/6] Testando EPG...")
    epg_results = {}
    for ch in channels_finais:
        tvg_id = ch["tvg_id"]
        if tvg_id not in epg_results:
            prog = test_epg_programming(tvg_id)
            epg_results[tvg_id] = prog
            dt = datetime.now()
            h = dt.strftime("%d/%m")
            a = (dt + timedelta(days=1)).strftime("%d/%m")
            da = (dt + timedelta(days=2)).strftime("%d/%m")
            print(f"  {tvg_id}: {prog['status']} ({h}:{prog['hoje']}, {a}:{prog['amanha']}, {da}:{prog['depois_amanha']})")

    print(f"\n[6/6] Escrevendo lista5.m3u corrigido...")
    with open(M3U_PATH, 'w', encoding='utf-8') as f:
        f.write(f'#EXTM3U x-tvg-url="{EPG_SOURCE_URL}"\n')
        for ch in channels_finais:
            f.write(ch["extinf"] + "\n")
            f.write(ch["url"] + "\n")

    print(f"\n" + "=" * 70)
    print(f"RESUMO DA CORREÇÃO:")
    print(f"=" * 70)
    print(f"  Canais finais: {len(channels_finais)}")
    print(f"  Canais removidos (URLs inacessíveis): {len(removidos)}")
    print(f"  EPG: {EPG_SOURCE_URL}")
    for tvg_id, prog in epg_results.items():
        print(f"  EPG {tvg_id}: {prog['status']} (hoje:{prog['hoje']} amanhã:{prog['amanha']} depois:{prog['depois_amanha']})")
    todos_completos = all(p['status'] == 'completo' for p in epg_results.values())
    if todos_completos:
        print(f"\n  EPG COMPLETO para todos os canais!")
    else:
        print(f"\n  EPG PARCIAL - alguns canais sem programação completa")

    # Verificações finais
    print(f"\n" + "-" * 70)
    print(f"VERIFICAÇÕES:")
    print(f"-" * 70)

    with open(M3U_PATH, 'r') as f:
        written = f.read()

    # Verificar se todos URLs tem #EXTINF acima
    lines = written.strip().split('\n')
    problems = 0
    for i, line in enumerate(lines):
        if line.startswith('http'):
            if i == 0 or not lines[i-1].startswith('#EXTINF:'):
                print(f"  X Linha {i+1}: URL sem #EXTINF acima")
                problems += 1

    # Verificar logos
    for match in re.finditer(r'tvg-logo="([^"]*)"', written):
        logo = match.group(1)
        if 'imgur.com' in logo:
            print(f"  X Logo imgur.com encontrado: {logo}")
            problems += 1
        if not logo.lower().endswith('.jpg') and not logo.lower().endswith('.jpeg'):
            print(f"  X Logo não é .jpg: {logo}")
            problems += 1

    # Verificar tvg-ids
    tvg_ids_encontrados = set(re.findall(r'tvg-id="([^"]*)"', written))
    print(f"  tvg-ids: {tvg_ids_encontrados}")
    print(f"  EPG URL: {EPG_SOURCE_URL}")
    print(f"  Total de linhas: {len(lines)}")
    print(f"  Total de canais: {len(channels_finais)}")

    if problems == 0:
        print(f"\n  OK - Nenhum problema encontrado!")
    else:
        print(f"\n  ATENÇÃO: {problems} problema(s) encontrado(s)")


if __name__ == "__main__":
    main()
