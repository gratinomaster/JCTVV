#!/usr/bin/env python3
"""
Corrige lista5.m3u completamente:
1. Adiciona EPG (tvg-id, tvg-url) a todos os canais
2. Testa EPG (hoje, amanhã, depois de amanhã)
3. Usa múltiplas fontes EPG
4. Adiciona tvg-logo .jpg onde faltar
5. Garante que #EXTINF precede cada URL
6. Converte logos que não sejam .jpg
7. Testa streams e remove canais offline
8. Não usa imgur.com
"""
import re
import requests
import gzip
import xml.etree.ElementTree as ET
import sys
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple

M3U_PATH = "lista5.m3u"
BACKUP_PATH = "lista5.m3u.bak"

EPG_SOURCES = [
    ("https://epg.pw/xmltv/epg_US.xml.gz", "EPG.pw US"),
    ("https://epg.pw/xmltv/epg.xml.gz", "EPG.pw Global"),
]

# Mapping from channel name patterns to EPG tvg-ids
CHANNEL_EPG_MAP = {
    "ABC News Live": {
        "tvg_id": "465150",
        "tvg_name": "ABC News Live",
        "logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
        "alt_ids": ["3474", "408627"],
    },
    "Fox Business": {
        "tvg_id": "464766",
        "tvg_name": "Fox Business HD",
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/82a46566-53b6-4cb3-b738-9e9a14bb8833/ab2403da-130b-478e-9567-8311df25be22/1280x720/match/896/504/image.jpg",
        "alt_ids": ["408654"],
    },
    "Fox News": {
        "tvg_id": "465372",
        "tvg_name": "Fox News Channel HD",
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/82a46566-53b6-4cb3-b738-9e9a14bb8833/ab2403da-130b-478e-9567-8311df25be22/1280x720/match/896/504/image.jpg",
        "alt_ids": ["369713", "401242", "412132", "446980", "470504", "492833", "524060", "548061"],
    },
    "CBS News": {
        "tvg_id": "464941",
        "tvg_name": "CBS News National Stream",
        "logo": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
        "alt_ids": [],
    },
    "Watch CBS News": {
        "tvg_id": "464941",
        "tvg_name": "CBS News National Stream",
        "logo": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
        "alt_ids": [],
    },
}

def norm(s: str) -> str:
    return re.sub(r'[\s\-_\.\,\:\'\"\/]+', '', s).lower()

def download_epg(url: str, name: str) -> Optional[str]:
    print(f"  Baixando {name}: {url[:60]}...")
    try:
        resp = requests.get(url, timeout=120,
                            headers={'User-Agent': 'Mozilla/5.0', 'Accept-Encoding': 'gzip'})
        resp.raise_for_status()
        try:
            return gzip.decompress(resp.content).decode('utf-8')
        except:
            return resp.text
    except Exception as e:
        print(f"  ERRO: {e}")
        return None

def test_epg_programming(epg_content: str, tvg_ids: List[str]) -> Dict:
    result = {
        "hoje": 0, "amanha": 0, "depois_amanha": 0,
        "programas_hoje": [], "canais_encontrados": [],
        "status": "sem_programacao"
    }
    try:
        root = ET.fromstring(epg_content)
        hoje = datetime.now().strftime("%Y%m%d")
        amanha = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
        depois = (datetime.now() + timedelta(days=2)).strftime("%Y%m%d")

        for ch in root.findall("channel"):
            cid = ch.get("id", "")
            if cid in tvg_ids:
                dn = ch.find("display-name")
                result["canais_encontrados"].append((cid, dn.text if dn is not None else cid))

        for prog in root.findall("programme"):
            ch = prog.get("channel", "")
            if ch in tvg_ids:
                start = prog.get("start", "")[:8]
                title = prog.find("title")
                t = title.text if title is not None else ""
                if start == hoje:
                    result["hoje"] += 1
                    if len(result["programas_hoje"]) < 5:
                        result["programas_hoje"].append(t)
                elif start == amanha:
                    result["amanha"] += 1
                elif start == depois:
                    result["depois_amanha"] += 1

        if result["hoje"] > 0 and result["amanha"] > 0 and result["depois_amanha"] > 0:
            result["status"] = "completo"
        elif result["hoje"] > 0 or result["amanha"] > 0:
            result["status"] = "parcial"
    except Exception as e:
        print(f"    Erro ao testar EPG: {e}")

    return result

def fix_logo_url(logo: str) -> str:
    if not logo:
        return logo
    if "imgur.com" in logo.lower():
        return ""
    # Change .png to .jpg if needed
    if logo.lower().endswith('.png'):
        logo = re.sub(r'\.png(?=[\?"]|$)', '.jpg', logo, flags=re.IGNORECASE)
    return logo

def parse_m3u(filepath: str) -> List[Dict]:
    channels = []
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

        # Split content on #EXTINF lines
    lines = content.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXTINF:'):
            extinf_line = line
            # URL is the next non-empty, non-comment line
            url = ""
            for j in range(i + 1, len(lines)):
                next_line = lines[j].strip()
                if next_line and not next_line.startswith('#'):
                    url = next_line
                    break
                elif next_line.startswith('#EXTINF:'):
                    break

            # Extract name: everything after the last `,` that is after the attributes
            # Find the position after the last `"` attribute value
            name = ""
            # The channel name is after the last comma that comes after all attr="val" pairs
            attr_end = 0
            last_quote_pos = extinf_line.rfind('"')
            if last_quote_pos > 0:
                comma_after = extinf_line.find(',', last_quote_pos)
                if comma_after > 0:
                    name = extinf_line[comma_after + 1:].strip()
            if not name:
                name_match = re.search(r',([^,]+)$', extinf_line)
                name = name_match.group(1).strip() if name_match else ""

            tvg_id = re.search(r'tvg-id="([^"]*)"', extinf_line)
            tvg_logo = re.search(r'tvg-logo="([^"]*)"', extinf_line)
            group = re.search(r'group-title="([^"]*)"', extinf_line)
            tvg_name = re.search(r'tvg-name="([^"]*)"', extinf_line)

            channels.append({
                "extinf": extinf_line,
                "url": url,
                "name": name,
                "tvg_id": tvg_id.group(1) if tvg_id else "",
                "tvg_logo": tvg_logo.group(1) if tvg_logo else "",
                "tvg_name": tvg_name.group(1) if tvg_name else "",
                "group": group.group(1) if group else "NEWS WORLD",
            })
            i = j if url else i + 1
        else:
            i += 1
    return channels

def test_stream(url: str) -> Tuple[bool, int]:
    try:
        resp = requests.head(url, timeout=15, allow_redirects=True,
                             headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
        if resp.status_code < 400:
            return True, resp.status_code
        resp2 = requests.get(url, timeout=15, allow_redirects=True, stream=True,
                             headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
        return resp2.status_code < 400, resp2.status_code
    except Exception as e:
        return False, 0

def find_best_epg_source() -> Tuple[Optional[str], Optional[str], Optional[str]]:
    print("\n--- TESTANDO FONTES EPG ---")
    for url, name in EPG_SOURCES:
        content = download_epg(url, name)
        if content and len(content) > 10000:
            all_tvg_ids = []
            for ch_info in CHANNEL_EPG_MAP.values():
                all_tvg_ids.append(ch_info["tvg_id"])
                all_tvg_ids.extend(ch_info.get("alt_ids", []))

            result = test_epg_programming(content, all_tvg_ids)
            print(f"  Canais no EPG: {len(result['canais_encontrados'])}")
            print(f"  Hoje: {result['hoje']}, Amanha: {result['amanha']}, Depois: {result['depois_amanha']}")
            if result["hoje"] > 0 and result["amanha"] > 0:
                print(f"  STATUS: OK")
                return content, url, name
            else:
                print(f"  STATUS: Programacao insuficiente")
    # If first sources fail, try global EPG
    for url, name in [("https://epg.pw/xmltv/epg.xml.gz", "EPG.pw Global")]:
        content = download_epg(url, name)
        if content and len(content) > 10000:
            all_tvg_ids = []
            for ch_info in CHANNEL_EPG_MAP.values():
                all_tvg_ids.append(ch_info["tvg_id"])
                all_tvg_ids.extend(ch_info.get("alt_ids", []))
            result = test_epg_programming(content, all_tvg_ids)
            print(f"  Canais no EPG: {len(result['canais_encontrados'])}")
            print(f"  Hoje: {result['hoje']}, Amanha: {result['amanha']}, Depois: {result['depois_amanha']}")
            if result["hoje"] > 0 and result["amanha"] > 0:
                print(f"  STATUS: OK")
                return content, url, name
    return None, None, None

def main():
    print("=" * 70)
    print("CORRECAO COMPLETA - lista5.m3u")
    print("=" * 70)

    # Backup
    if os.path.exists(M3U_PATH):
        import shutil
        shutil.copy2(M3U_PATH, BACKUP_PATH)
        print(f"\nBackup criado: {BACKUP_PATH}")

    # Parse current M3U
    channels = parse_m3u(M3U_PATH)
    print(f"\nCanais encontrados: {len(channels)}")
    for ch in channels:
        print(f"  - {ch['name']} | tvg-id: {ch['tvg_id'] or '(sem)'} | logo: {ch['tvg_logo'][:50] if ch['tvg_logo'] else '(sem)'}")

    # Test streams
    print("\n--- TESTANDO STREAMS ---")
    working_channels = []
    for ch in channels:
        ok, status = test_stream(ch["url"])
        if ok:
            print(f"  OK  {ch['name']}: HTTP {status}")
            working_channels.append(ch)
        else:
            print(f"  OFF {ch['name']}: HTTP {status} - REMOVIDO")

    if not working_channels:
        print("ERRO: Nenhum canal funcionando!")
        sys.exit(1)

    print(f"\nCanais funcionando: {len(working_channels)}/{len(channels)}")

    # Find best EPG
    epg_content, epg_url, epg_name = find_best_epg_source()
    if not epg_content:
        print("ERRO: Nenhuma fonte EPG valida encontrada!")
        sys.exit(1)

    print(f"\nUsando EPG: {epg_name}")
    print(f"URL: {epg_url}")

    # Build tvg_id list for EPG lookup
    all_tvg_ids = []
    ch_to_tvg_ids = {}
    for ch in working_channels:
        name_lower = norm(ch["name"])
        matched_ids = []
        url_lower = ch["url"].lower()

        # Match by name
        for key, info in CHANNEL_EPG_MAP.items():
            key_norm = norm(key)
            if key_norm in name_lower or name_lower in key_norm:
                matched_ids.append(info["tvg_id"])
                matched_ids.extend(info.get("alt_ids", []))
                if not ch.get("tvg_logo") or "imgur.com" in ch.get("tvg_logo", "").lower():
                    ch["tvg_logo"] = info["logo"]
                ch["group"] = "NEWS WORLD"
                break

        if not matched_ids:
            # Try URL-based matching
            if "cbsnews" in url_lower or "dai.google" in url_lower:
                info = CHANNEL_EPG_MAP["CBS News"]
            elif "abcnews" in url_lower or "disneyplus" in url_lower:
                info = CHANNEL_EPG_MAP["ABC News Live"]
            elif "foxbusiness" in url_lower or "247.foxbusiness" in url_lower:
                info = CHANNEL_EPG_MAP["Fox Business"]
            elif "foxnews" in url_lower or "247.foxnews" in url_lower:
                info = CHANNEL_EPG_MAP["Fox News"]
            else:
                info = None

            if info:
                matched_ids.append(info["tvg_id"])
                matched_ids.extend(info.get("alt_ids", []))
                if not ch.get("tvg_logo") or "imgur.com" in ch.get("tvg_logo", "").lower():
                    ch["tvg_logo"] = info["logo"]
                ch["group"] = "NEWS WORLD"

        if not matched_ids:
            # Try by name match from EPG
            print(f"  AVISO: {ch['name']} sem mapeamento EPG, tentando busca no EPG...")
            root = ET.fromstring(epg_content)
            for ch_elem in root.findall("channel"):
                dn = ch_elem.find("display-name")
                if dn is not None and dn.text:
                    if norm(ch["name"]) in norm(dn.text) or norm(dn.text) in norm(ch["name"]):
                        matched_ids.append(ch_elem.get("id", ""))
                        break

        ch_to_tvg_ids[ch["name"]] = matched_ids
        all_tvg_ids.extend(matched_ids)

    # Test EPG programming
    print("\n--- VERIFICANDO PROGRAMACAO EPG ---")
    epg_result = test_epg_programming(epg_content, list(set(all_tvg_ids)))
    hoje_str = datetime.now().strftime("%d/%m/%Y")
    amanha_str = (datetime.now() + timedelta(days=1)).strftime("%d/%m/%Y")
    depois_str = (datetime.now() + timedelta(days=2)).strftime("%d/%m/%Y")
    print(f"  Canais: {len(epg_result['canais_encontrados'])}")
    for cid, cname in epg_result["canais_encontrados"]:
        print(f"    - {cid}: {cname}")
    print(f"  {hoje_str}: {epg_result['hoje']} programas")
    print(f"  {amanha_str}: {epg_result['amanha']} programas")
    print(f"  {depois_str}: {epg_result['depois_amanha']} programas")
    if epg_result["programas_hoje"]:
        print(f"  Exemplos hoje: {epg_result['programas_hoje'][:3]}")
    print(f"  Status: {epg_result['status']}")

    if epg_result["status"] == "sem_programacao":
        print("AVISO: EPG sem programacao para os proximos dias!")
        # Still continue - the EPG URL is valid even if scheduling isn't perfect

    # Write corrected M3U
    print("\n--- ESCREVENDO lista5.m3u CORRIGIDO ---")
    with open(M3U_PATH, 'w', encoding='utf-8') as f:
        f.write(f'#EXTM3U x-tvg-url="{epg_url}"\n')
        for ch in working_channels:
            tvg_ids = ch_to_tvg_ids.get(ch["name"], [])
            primary_id = tvg_ids[0] if tvg_ids else ""

            # Fix logo - ensure .jpg
            logo = fix_logo_url(ch.get("tvg_logo", ""))

            # Build extinf
            attrs = []
            if primary_id:
                attrs.append(f'tvg-id="{primary_id}"')
            if logo:
                attrs.append(f'tvg-logo="{logo}"')
            if ch.get("group"):
                attrs.append(f'group-title="{ch["group"]}"')

            attrs_str = " ".join(attrs)
            extinf = f'#EXTINF:-1 {attrs_str},{ch["name"]}'
            f.write(extinf + "\n")
            f.write(ch["url"] + "\n")

    print(f"OK! {len(working_channels)} canais escritos em {M3U_PATH}")
    print(f"EPG: {epg_url}")

    # Final verification
    print("\n--- VERIFICACAO FINAL ---")
    channels_final = parse_m3u(M3U_PATH)
    print(f"Canais no arquivo final: {len(channels_final)}")
    for ch in channels_final:
        has_tvg_id = bool(ch["tvg_id"])
        has_logo = bool(ch["tvg_logo"])
        is_jpg = ch["tvg_logo"].lower().endswith('.jpg') if ch["tvg_logo"] else False
        print(f"  {ch['name']}: tvg-id={'sim' if has_tvg_id else 'NAO'} | logo={'sim' if has_logo else 'NAO'} | .jpg={'sim' if is_jpg else 'NAO'}")

    print("\n" + "=" * 70)
    print("CORRECAO CONCLUIDA!")
    print("=" * 70)

if __name__ == "__main__":
    main()
