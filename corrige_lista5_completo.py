#!/usr/bin/env python3
import requests
import re
import gzip
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

EPG_URL = "https://epg.pw/xmltv/epg.xml.gz"
EPG_BR_URL = "https://epg.pw/xmltv/epg_BR.xml.gz"

CHANNEL_EPG_MAP = {
    "abc news live": {"tvg_id": "465150", "name": "ABC News Live"},
    "abc news": {"tvg_id": "465150", "name": "ABC News Live"},
    "fox business": {"tvg_id": "464766", "name": "Fox Business"},
    "fox news": {"tvg_id": "465372", "name": "Fox News Channel"},
    "cbs news": {"tvg_id": "464941", "name": "CBS News 24/7"},
}

LOGO_MAP = {
    "abc news": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
    "fox business": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/c9b2e2eb-7b87-435c-9510-eab2650ff944/8b584585-acf2-4c37-aa07-aaf2d077bb20/1280x720/match/676/380/image.jpg",
    "fox news": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/15de0523-3be4-4a9a-8159-7020114e7036/b6ff623a-26d6-4fd9-8bb8-0856adbf38ce/1280x720/match/676/380/image.jpg",
    "cbs news": "https://www.cbsnews.com/bundles/cbsnewsvideo/images/cbsn--main-bg.jpg",
}

def test_epg_source(url: str) -> Optional[Dict]:
    try:
        r = requests.get(url, timeout=120, headers={'Accept-Encoding': 'gzip'})
        try:
            xml = gzip.decompress(r.content).decode('utf-8')
        except:
            xml = r.text
        root = ET.fromstring(xml)
        progs = root.findall("programme")
        hoje = datetime.now().strftime("%Y%m%d")
        amanha = (datetime.now() + timedelta(1)).strftime("%Y%m%d")
        depois = (datetime.now() + timedelta(2)).strftime("%Y%m%d")
        h = sum(1 for p in progs if p.get('start','')[:8]==hoje)
        a = sum(1 for p in progs if p.get('start','')[:8]==amanha)
        d = sum(1 for p in progs if p.get('start','')[:8]==depois)
        ok = h > 0 and a > 0 and d > 0
        print(f"  EPG {url[:50]}...: {len(root.findall('channel'))} canais, {len(progs)} prog, hoje={h}, amanha={a}, depois={d} {'OK' if ok else 'PARCIAL'}")
        return {"url": url, "xml": xml, "root": root, "hoje": h, "amanha": a, "depois": d, "ok": ok}
    except Exception as e:
        print(f"  EPG {url[:50]}...: ERRO {e}")
        return None

def check_channel_epg(epg_data: Dict, tvg_id: str) -> Dict:
    result = {"hoje": 0, "amanha": 0, "depois": 0, "ok": False}
    if not epg_data:
        return result
    root = epg_data["root"]
    hoje = datetime.now().strftime("%Y%m%d")
    amanha = (datetime.now() + timedelta(1)).strftime("%Y%m%d")
    depois = (datetime.now() + timedelta(2)).strftime("%Y%m%d")
    for p in root.findall(f"programme[@channel='{tvg_id}']"):
        start = p.get("start", "")[:8]
        if start == hoje: result["hoje"] += 1
        elif start == amanha: result["amanha"] += 1
        elif start == depois: result["depois"] += 1
    result["ok"] = result["hoje"] > 0 and result["amanha"] > 0
    return result

def test_stream(url: str) -> Dict:
    result = {"status": "unknown", "http": None}
    try:
        r = requests.head(url, timeout=15, allow_redirects=True, headers={'User-Agent': 'Mozilla/5.0'})
        result["http"] = r.status_code
        if r.status_code == 200: result["status"] = "ok"
        elif r.status_code in [403, 405]: result["status"] = "ok"
        elif r.status_code == 404: result["status"] = "404"
        else: result["status"] = f"http_{r.status_code}"
    except requests.exceptions.Timeout: result["status"] = "timeout"
    except Exception as e: result["status"] = "erro"
    return result

def parse_m3u(content: str) -> List[Dict]:
    channels = []
    lines = content.strip().split('\n')
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXTINF:'):
            if i + 1 < len(lines) and not lines[i+1].startswith('#'):
                url = lines[i+1].strip()
                name_match = re.search(r',(.+)$', line)
                name = name_match.group(1).strip() if name_match else ""
                logo_match = re.search(r'tvg-logo="([^"]*)"', line)
                logo = logo_match.group(1) if logo_match else ""
                group_match = re.search(r'group-title="([^"]*)"', line)
                group = group_match.group(1) if group_match else ""
                tvg_id_match = re.search(r'tvg-id="([^"]*)"', line)
                tvg_id = tvg_id_match.group(1) if tvg_id_match else ""
                channels.append({"extinf": line, "url": url, "name": name, "logo": logo, "group": group, "tvg_id": tvg_id})
                i += 2
            else:
                i += 1
        else:
            i += 1
    return channels

def main():
    print("="*60)
    print("CORREÇÃO COMPLETA lista5.m3u")
    print("="*60)

    # Read file
    with open('/home/runner/work/JCTV/JCTV/lista5.m3u', 'r') as f:
        content = f.read()

    channels = parse_m3u(content)
    print(f"\nCanais brutos encontrados: {len(channels)}")

    # Test EPG sources
    print("\n--- Testando fontes EPG ---")
    epg_data = test_epg_source(EPG_URL)
    epg_br_data = test_epg_source(EPG_BR_URL)

    epg_sources_usadas = []
    if epg_data and epg_data["ok"]:
        epg_sources_usadas.append(EPG_URL)
    if epg_br_data and epg_br_data["ok"]:
        epg_sources_usadas.append(EPG_BR_URL)

    print(f"\nEPGs funcionando: {epg_sources_usadas}")

    # Check EPG for each channel
    print("\n--- Verificando EPG por canal ---")
    channel_epg_status = {}
    for ch in channels:
        name_lower = ch["name"].lower()
        for key, mapping in CHANNEL_EPG_MAP.items():
            if key in name_lower:
                tvg_id = mapping["tvg_id"]
                if tvg_id not in channel_epg_status:
                    status = check_channel_epg(epg_data, tvg_id)
                    channel_epg_status[tvg_id] = status
                    print(f"  {mapping['name']} (id={tvg_id}): hoje={status['hoje']}, amanha={status['amanha']}, depois={status['depois']} {'OK' if status['ok'] else 'SEM EPG'}")

    # Deduplicate - keep unique URLs only
    print("\n--- Deduplicando ---")
    seen_urls = set()
    seen_names = set()
    unique_channels = []
    for ch in channels:
        if ch["url"] not in seen_urls:
            # Also check for near-duplicate names (same channel different source)
            is_new = True
            name_key = ch["name"].lower().split("|")[0].strip()[:30]
            seen_urls.add(ch["url"])
            unique_channels.append(ch)
    print(f"Canais únicos: {len(unique_channels)}")

    # Process each channel
    print("\n--- Processando canais ---")
    output_channels = []
    for ch in unique_channels:
        name_lower = ch["name"].lower()
        tvg_id = ""
        new_logo = ch["logo"]
        epg_url_attr = ""

        # Find EPG mapping
        for key, mapping in CHANNEL_EPG_MAP.items():
            if key in name_lower:
                tvg_id = mapping["tvg_id"]
                break

        # Fix logo to .jpg
        if ch["logo"]:
            if not ch["logo"].lower().endswith('.jpg'):
                for key, logo_url in LOGO_MAP.items():
                    if key in name_lower:
                        new_logo = logo_url
                        break
                else:
                    new_logo = ch["logo"]
        else:
            for key, logo_url in LOGO_MAP.items():
                if key in name_lower:
                    new_logo = logo_url
                    break

        # Remove imgur.com
        if new_logo and 'imgur.com' in new_logo.lower():
            for key, logo_url in LOGO_MAP.items():
                if key in name_lower:
                    new_logo = logo_url
                    break

        # Build new EXTINF line
        parts = []
        if tvg_id:
            parts.append(f'tvg-id="{tvg_id}"')
        if new_logo:
            parts.append(f'tvg-logo="{new_logo}"')
        if ch["group"]:
            parts.append(f'group-title="{ch["group"]}"')

        attrs = " ".join(parts)
        new_extinf = f'#EXTINF:-1 {attrs},{ch["name"]}'

        output_channels.append({
            "extinf": new_extinf,
            "url": ch["url"],
            "name": ch["name"],
            "tvg_id": tvg_id
        })

    # Test streams
    print("\n--- Testando streams ---")
    working_channels = []
    for ch in output_channels:
        result = test_stream(ch["url"])
        status_str = f"{'OK' if result['status']=='ok' else result['status']} (HTTP {result.get('http','N/A')})"
        print(f"  {ch['name'][:40]:40s} {status_str}")
        if result["status"] == "ok":
            working_channels.append(ch)
        else:
            print(f"    -> REMOVIDO (stream falhou)")

    if not working_channels:
        print("\nNenhum canal funcionou! Mantendo originais.")
        working_channels = output_channels

    print(f"\nCanais que passaram no teste: {len(working_channels)}/{len(output_channels)}")

    # Write output
    print("\n--- Escrevendo lista5.m3u ---")
    with open('/home/runner/work/JCTV/JCTV/lista5.m3u', 'w') as f:
        f.write("#EXTM3U\n")
        for url in epg_sources_usadas:
            f.write(f'#EXTM3U x-tvg-url="{url}"\n')
        for ch in working_channels:
            f.write(f"{ch['extinf']}\n{ch['url']}\n")

    print(f"Arquivo atualizado: {len(working_channels)} canais")
    print(f"EPG sources: {epg_sources_usadas}")

    # Final verification
    print("\n--- VERIFICAÇÃO FINAL ---")
    with open('/home/runner/work/JCTV/JCTV/lista5.m3u', 'r') as f:
        final = f.read()
    final_lines = final.strip().split('\n')
    extinf_count = sum(1 for l in final_lines if l.startswith('#EXTINF:'))
    url_count = sum(1 for l in final_lines if l.startswith('http'))
    print(f"Linhas #EXTINF: {extinf_count}")
    print(f"URLs: {url_count}")
    print(f"EPG sources no header: {epg_sources_usadas}")

if __name__ == "__main__":
    main()
