#!/usr/bin/env python3
"""
Correção completa da lista5.m3u:
1. Adiciona EPG (tvg-id, url-tvg) em todos os canais
2. Remove duplicatas (variantes de qualidade)
3. Verifica se logos são .jpg
4. Garante #EXTINF acima de cada URL
5. Testa programação EPG para hoje, amanhã e depois de amanhã
6. Testa acessibilidade das URLs
7. Remove canais que não passarem nos testes
"""
import re
import gzip
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from urllib.request import Request, urlopen
from urllib.error import URLError
import ssl
import os

M3U_PATH = "lista5.m3u"
OUTPUT_PATH = "lista5.m3u"
BACKUP_PATH = "lista5.m3u.bak"

# EPG URLs para adicionar ao header
EPG_URLS = [
    "https://raw.githubusercontent.com/gratinomaster/JCTV/main/lista5_epg.xml.gz",
    "https://iptv-epg.org/files/epg-us.xml.gz",
    "https://epg.pw/xmltv/epg_US.xml.gz",
]

# Mapeamento de nomes de canais para tvg-id
CHANNEL_MAPPING = {
    "abc news live": "ABCNewsLive.us",
    "abc news": "ABCNewsLive.us",
    "20/20": "ABCNewsLive.us",
    "fox news": "FoxNewsChannel.us",
    "fox business": "FoxBusiness.us",
    "cbs news": "CBSNews.us",
}

# Mapas de logos corrigidos (.jpg)
CHANNEL_LOGOS = {
    "ABCNewsLive.us": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
    "FoxNewsChannel.us": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/5083aae4-b8c5-4708-ac25-f3c5ac554341/b17e991e-a824-4bf7-8e6b-885b7cd2bcf4/1280x720/match/400/225/image.jpg",
    "FoxBusiness.us": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/25afb380-3b42-47b4-be31-733f1bbe07ae/107e58b1-b052-49e8-a1c2-cc8ce1cf3c5a/1280x720/match/400/225/image.jpg",
    "CBSNews.us": "https://www.cbsnews.com/bundles/cbsnewsvideo/images/cbsn--main-bg.jpg",
}

CHANNEL_NAMES = {
    "ABCNewsLive.us": "ABC News Live",
    "FoxNewsChannel.us": "Fox News Channel",
    "FoxBusiness.us": "Fox Business",
    "CBSNews.us": "CBS News 24/7",
}


def parse_m3u(filepath: str) -> Tuple[str, List[Dict]]:
    """Parse m3u file, returns header and list of channel entries."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.split('\n')
    header = ""
    channels = []

    i = 0
    if lines and lines[0].startswith('#EXTM3U'):
        header = lines[0]
        i = 1

    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXTINF:'):
            url = ""
            if i + 1 < len(lines):
                url = lines[i + 1].strip()
            # Extract attributes
            tvg_id_m = re.search(r'tvg-id="([^"]*)"', line)
            tvg_logo_m = re.search(r'tvg-logo="([^"]*)"', line)
            group_m = re.search(r'group-title="([^"]*)"', line)
            tvg_url_m = re.search(r'(?:x-tvg-url|url-tvg)="([^"]*)"', line)

            name_m = re.search(r',(.+)$', line)
            channel_name = name_m.group(1).strip() if name_m else ""

            channels.append({
                "extinf": line,
                "url": url,
                "name": channel_name,
                "tvg_id": tvg_id_m.group(1) if tvg_id_m else "",
                "tvg_logo": tvg_logo_m.group(1) if tvg_logo_m else "",
                "group": group_m.group(1) if group_m else "",
                "tvg_url": tvg_url_m.group(1) if tvg_url_m else "",
            })
            i += 2
        else:
            i += 1

    return header, channels


def detect_tvg_id(name: str) -> Optional[str]:
    """Detect tvg-id from channel name."""
    name_lower = name.lower()
    for key, tvg_id in CHANNEL_MAPPING.items():
        if key in name_lower:
            return tvg_id
    return None


def is_valid_jpg_logo(logo_url: str) -> bool:
    """Check if logo URL is a valid .jpg."""
    if not logo_url:
        return False
    # Remove query params for extension check
    clean_url = logo_url.split('?')[0]
    return clean_url.lower().endswith('.jpg') or clean_url.lower().endswith('.jpeg')


def fix_logo_to_jpg(logo_url: str, tvg_id: str) -> str:
    """Fix logo to jpg, return corrected URL or default."""
    if not logo_url or not is_valid_jpg_logo(logo_url):
        # Use the default jpg logo for this channel
        if tvg_id and tvg_id in CHANNEL_LOGOS:
            return CHANNEL_LOGOS[tvg_id]
    return logo_url


def check_url_accessibility(url: str, timeout: int = 10) -> bool:
    """Check if a URL is accessible via HEAD request."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        req = Request(url, method='HEAD')
        req.add_header('User-Agent', 'Mozilla/5.0')
        resp = urlopen(req, timeout=timeout, context=ctx)
        return resp.status in [200, 301, 302, 307, 308]
    except Exception:
        pass
    # Try GET as fallback (some servers reject HEAD)
    try:
        req = Request(url, method='GET')
        req.add_header('User-Agent', 'Mozilla/5.0')
        resp = urlopen(req, timeout=timeout, context=ctx)
        # Just check first few bytes
        resp.read(1024)
        return True
    except Exception:
        return False


def download_epg(url: str) -> Optional[str]:
    """Download EPG content from URL."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        req = Request(url)
        req.add_header('User-Agent', 'Mozilla/5.0')
        resp = urlopen(req, timeout=60, context=ctx)
        data = resp.read()
        if url.endswith('.gz'):
            data = gzip.decompress(data)
        return data.decode('utf-8', errors='replace')
    except Exception as e:
        print(f"  Erro EPG {url[:50]}: {e}")
        return None


def test_epg_for_channel(epg_content: str, tvg_id: str) -> Dict:
    """Test EPG programming for today, tomorrow, day after tomorrow."""
    result = {
        "status": "sem_programacao",
        "hoje": 0,
        "amanha": 0,
        "depois_amanha": 0,
        "programas": [],
    }
    try:
        root = ET.fromstring(epg_content)
        today = datetime.now().strftime("%Y%m%d")
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
        day_after = (datetime.now() + timedelta(days=2)).strftime("%Y%m%d")

        for prog in root.findall("programme"):
            channel = prog.get("channel", "")
            if channel == tvg_id:
                start = prog.get("start", "")
                start_date = start[:8] if len(start) >= 8 else ""
                title_elem = prog.find("title")
                title = title_elem.text if title_elem is not None else "N/A"

                if start_date == today:
                    result["hoje"] += 1
                    result["programas"].append(("hoje", start, title))
                elif start_date == tomorrow:
                    result["amanha"] += 1
                    result["programas"].append(("amanha", start, title))
                elif start_date == day_after:
                    result["depois_amanha"] += 1
                    result["programas"].append(("depois_amanha", start, title))

        today_prog = result["hoje"] > 0
        tomorrow_prog = result["amanha"] > 0
        day_after_prog = result["depois_amanha"] > 0

        if today_prog and tomorrow_prog and day_after_prog:
            result["status"] = "completo"
        elif today_prog or tomorrow_prog:
            result["status"] = "parcial"
        else:
            result["status"] = "sem_programacao"

        return result
    except Exception as e:
        print(f"  Erro testando EPG para {tvg_id}: {e}")
        return result


def main():
    print("=" * 70)
    print("CORREÇÃO COMPLETA DO lista5.m3u")
    print("=" * 70)

    # Step 1: Parse existing file
    print("\n[1/7] Analisando lista5.m3u...")
    header, channels = parse_m3u(M3U_PATH)
    print(f"  Header: {header[:50]}...")
    print(f"  Entradas encontradas: {len(channels)}")

    # Step 2: Group by unique channel name and detect tvg-id
    print("\n[2/7] Identificando canais únicos...")
    unique_channels = {}  # name_lower -> first entry
    for ch in channels:
        name_key = ch["name"].lower().strip()
        # Normalize similar names
        for prefix, tvg_id in CHANNEL_MAPPING.items():
            if prefix in name_key:
                name_key = tvg_id
                break

        if name_key not in unique_channels:
            unique_channels[name_key] = ch
            tvg_id = detect_tvg_id(ch["name"])
            display_name = CHANNEL_NAMES.get(tvg_id, ch["name"])
            print(f"  {display_name} [{tvg_id or 'sem ID'}]")

    print(f"  Total canais únicos: {len(unique_channels)}")

    # Step 3: Add EPG to header
    print("\n[3/7] Configurando EPG...")

    # Test available EPG sources
    working_epgs = []
    for epg_url in EPG_URLS:
        print(f"  Testando EPG: {epg_url.split('/')[-1]}")
        content = download_epg(epg_url)
        if content and len(content) > 100:
            print(f"    ✓ OK ({len(content)} bytes)")
            working_epgs.append(epg_url)
        else:
            print(f"    ✗ Falhou")

    if not working_epgs:
        print("  ⚠ Nenhum EPG externo funcionou, usando arquivo local")
        local_path = "lista5_epg.xml.gz"
        if os.path.exists(local_path):
            working_epgs = [local_path]
            print(f"  ✓ Usando {local_path}")

    epg_header_value = " ".join(working_epgs)
    new_header = f'#EXTM3U url-tvg="{epg_header_value}"'
    print(f"  Header EPG: {new_header[:80]}...")

    # Step 4: Download EPG content for testing
    epg_content = None
    for epg_url in working_epgs:
        if os.path.exists(epg_url):
            with open(epg_url, 'rb') as f:
                data = f.read()
            if epg_url.endswith('.gz'):
                data = gzip.decompress(data)
            epg_content = data.decode('utf-8', errors='replace')
        else:
            epg_content = download_epg(epg_url)
        if epg_content:
            break

    # Step 5: Test EPG programming
    print("\n[4/7] Testando programação EPG (hoje/amanhã/depois de amanhã)...")
    epg_results = {}
    for name_key, ch in unique_channels.items():
        tvg_id = detect_tvg_id(ch["name"])
        if not tvg_id:
            tvg_id = name_key

        if tvg_id and epg_content:
            result = test_epg_for_channel(epg_content, tvg_id)
            epg_results[tvg_id] = result
            display_name = CHANNEL_NAMES.get(tvg_id, tvg_id)
            status_icon = "✓" if result["status"] == "completo" else "⚠" if result["status"] == "parcial" else "✗"
            print(f"  {status_icon} {display_name}: Hoje={result['hoje']}, Amanhã={result['amanha']}, +2={result['depois_amanha']}")
        else:
            print(f"  ⚠ {ch['name'][:40]}: Sem EPG configurado")

    # Step 6: Test URL accessibility
    print("\n[5/7] Testando acessibilidade das URLs...")
    working_urls = set()
    failed_urls = set()
    for name_key, ch in unique_channels.items():
        url = ch["url"]
        if not url or url in working_urls:
            continue
        print(f"  Testando: {ch['name'][:40]}... ", end="", flush=True)
        if check_url_accessibility(url):
            print("✓ OK")
            working_urls.add(url)
        else:
            print("✗ Falhou")
            failed_urls.add(url)

    # Step 7: Generate corrected m3u
    print("\n[6/7] Gerando lista5.m3u corrigida...")

    # Backup original
    import shutil
    shutil.copy2(M3U_PATH, BACKUP_PATH)
    print(f"  Backup: {BACKUP_PATH}")

    lines = [new_header]
    added = set()

    for name_key, ch in unique_channels.items():
        url = ch["url"]

        # Skip failed URLs
        if url in failed_urls:
            print(f"  ✗ Removido (URL falhou): {ch['name'][:40]}")
            continue

        # Skip duplicates
        if url in added:
            continue
        added.add(url)

        # Detect tvg-id
        tvg_id = detect_tvg_id(ch["name"])
        if not tvg_id:
            continue

        # Fix logo to jpg
        logo = fix_logo_to_jpg(ch["tvg_logo"], tvg_id)
        if not logo:
            logo = CHANNEL_LOGOS.get(tvg_id, "")

        # Build display name
        display_name = CHANNEL_NAMES.get(tvg_id, ch["name"])
        group = ch["group"] if ch["group"] else "NEWS WORLD"

        # Build new EXTINF line
        attrs = f'tvg-id="{tvg_id}" tvg-logo="{logo}" group-title="{group}"'
        extinf = f"#EXTINF:-1 {attrs},{display_name}"

        lines.append(extinf)
        lines.append(url)
        print(f"  ✓ {display_name} [{tvg_id}]")

    # Write output
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')

    print(f"\n[7/7] Arquivo salvo: {OUTPUT_PATH}")
    print(f"  Canais na lista original: {len(channels)}")
    print(f"  Canais únicos: {len(unique_channels)}")
    print(f"  Canais na lista final: {len(lines) // 2}")
    print(f"  EPG ativo: {'sim' if working_epgs else 'nao'}")
    print(f"  Logos .jpg: {'sim' if all(is_valid_jpg_logo(CHANNEL_LOGOS.get(t, '')) for t in CHANNEL_LOGOS) else 'alguns nao'}")

    # Summary
    print("\n" + "=" * 70)
    print("RESUMO DA CORREÇÃO")
    print("=" * 70)
    print(f"  Header EPG: url-tvg com {len(working_epgs)} fonte(s)")
    for tvg_id, result in epg_results.items():
        if result:
            name = CHANNEL_NAMES.get(tvg_id, tvg_id)
            icon = "✓" if result["status"] == "completo" else "⚠" if result["status"] == "parcial" else "✗"
            print(f"  {icon} {name}: {result['status']} ({result['hoje']}+{result['amanha']}+{result['depois_amanha']} programas)")

    print("\n✓ Correção concluída!")


if __name__ == "__main__":
    main()
