#!/usr/bin/env python3
"""
Script completo para corrigir lista5.m3u:
1. Remove duplicatas exatas
2. Testa streams HTTP (remove mortos/token-expirado)
3. Testa EPGs (hoje, amanhã, depois de amanhã)
4. Adiciona url-tvg e tvg-id
5. Garante tvg-logo em .jpg
6. Remove links imgur.com
7. Garante # na linha acima de cada URL de canal
"""

import re
import os
import sys
import gzip
import hashlib
import urllib.request
import urllib.error
import ssl
import time
from datetime import datetime, timedelta
from io import BytesIO

# Desabilitar verificação SSL para testes
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

M3U_FILE = "lista5.m3u"
OUTPUT_FILE = "lista5.m3u"

# EPG sources to test (in order of preference)
EPG_SOURCES = [
    {
        "name": "EPGTalk Combined",
        "url": "https://raw.githubusercontent.com/acidjesuz/EPGTalk/master/guide.xml.gz",
        "compressed": True,
    },
    {
        "name": "EPGTalk US",
        "url": "https://raw.githubusercontent.com/acidjesuz/EPGTalk/master/US_guide.xml.gz",
        "compressed": True,
    },
    {
        "name": "iptv-epg.org US",
        "url": "https://iptv-epg.org/files/epg-us.xml.gz",
        "compressed": True,
    },
    {
        "name": "epg.pw US",
        "url": "https://epg.pw/xmltv/epg_US.xml",
        "compressed": False,
    },
    {
        "name": "USA Locals",
        "url": "https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.xml.gz",
        "compressed": True,
    },
]

# Channel name -> tvg-id mapping (common XMLTV IDs)
CHANNEL_EPG_MAP = {
    "ABC News Live": [
        "ABCNewsLive.us",
        "ABCNews.us",
        "ABCNewsLive",
        "ABC News Live",
    ],
    "Good Morning America": [
        "GoodMorningAmerica.us",
        "GMA.us",
        "ABCNewsLive.us",
        "ABCNews.us",
    ],
    "Fox News": [
        "FoxNews.us",
        "FoxNewsChannel.us",
        "Fox News US",
        "FoxNews",
    ],
    "Fox Business": [
        "FoxBusiness.us",
        "FoxBusinessNetwork.us",
        "Fox Business US",
        "FoxBusiness",
    ],
    "CBS News": [
        "CBSNews.us",
        "CBSNews247.us",
        "CBSNewsLive.us",
        "CBS News US",
        "CBSNews",
    ],
}


def log(msg, level="INFO"):
    colors = {
        "INFO": "\033[94m",
        "OK": "\033[92m",
        "WARN": "\033[93m",
        "ERROR": "\033[91m",
        "TITLE": "\033[95m",
    }
    reset = "\033[0m"
    color = colors.get(level, "")
    print(f"{color}[{level}]{reset} {msg}")


def parse_m3u(filepath):
    """Parse M3U file into list of (extinf_line, url_line) tuples."""
    channels = []
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    header = None
    i = 0
    if lines and lines[0].startswith("#EXTM3U"):
        header = lines[0].strip()
        i = 1

    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTINF:"):
            extinf = line
            url = ""
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line and not next_line.startswith("#"):
                    url = next_line
                    i += 2
                else:
                    i += 1
            else:
                i += 1
            if url:
                channels.append((extinf, url))
        else:
            i += 1

    return header, channels


def extract_channel_name(extinf):
    """Extract channel name from EXTINF line."""
    # Format: #EXTINF:-1 tvg-logo="..." group-title="...",Channel Name
    match = re.search(r',([^,]+)$', extinf)
    if match:
        return match.group(1).strip()
    return "Unknown"


def extract_group(extinf):
    """Extract group-title from EXTINF line."""
    match = re.search(r'group-title="([^"]*)"', extinf)
    if match:
        return match.group(1)
    return ""


def extract_logo(extinf):
    """Extract tvg-logo from EXTINF line."""
    match = re.search(r'tvg-logo="([^"]*)"', extinf)
    if match:
        return match.group(1)
    return ""


def get_best_stream_key(url):
    """Get a key for deduplication based on stream URL path (ignoring tokens)."""
    # Remove query parameters for dedup
    path = url.split("?")[0]
    return path


def test_stream_url(url, timeout=10):
    """Test if a stream URL is accessible."""
    try:
        req = urllib.request.Request(url, method="HEAD")
        req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)
        code = resp.getcode()
        resp.close()
        return code in (200, 301, 302, 303, 307, 308)
    except urllib.error.HTTPError as e:
        return e.code in (200, 301, 302, 303, 307, 308)
    except Exception:
        # For HLS streams, HEAD may fail but GET works with Range header
        try:
            req = urllib.request.Request(url)
            req.add_header("User-Agent", "Mozilla/5.0")
            req.add_header("Range", "bytes=0-1")
            resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)
            code = resp.getcode()
            data = resp.read(200)
            resp.close()
            return code in (200, 206) and len(data) > 0
        except urllib.error.HTTPError as e:
            return e.code in (200, 206)
        except Exception:
            return False


def fetch_epg_data(url, compressed=False, max_size_mb=50):
    """Fetch EPG data (partial) to test channel coverage."""
    try:
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "Mozilla/5.0")
        resp = urllib.request.urlopen(req, timeout=30, context=ctx)

        if compressed:
            data = resp.read(max_size_mb * 1024 * 1024)
            resp.close()
            try:
                data = gzip.decompress(data)
            except Exception:
                pass
        else:
            data = resp.read(max_size_mb * 1024 * 1024)
            resp.close()

        return data.decode("utf-8", errors="replace")
    except Exception as e:
        log(f"Erro ao baixar EPG: {e}", "ERROR")
        return None


def find_channel_in_epg(epg_data, channel_names):
    """Search for channel in EPG data by name variations."""
    found_ids = []
    for name in channel_names:
        # Case-insensitive search
        pattern = re.compile(re.escape(name), re.IGNORECASE)
        matches = pattern.findall(epg_data)
        if matches:
            # Find the channel ID
            id_pattern = re.compile(
                r'<channel\s+id="([^"]*)"[^>]*>.*?' + re.escape(name) + r'.*?</channel>',
                re.IGNORECASE | re.DOTALL,
            )
            id_match = id_pattern.search(epg_data)
            if id_match:
                found_ids.append(id_match.group(1))
            else:
                # Try display-name pattern
                dn_pattern = re.compile(
                    r'<channel\s+id="([^"]*)"[^>]*>\s*<display-name>[^<]*' + re.escape(name) + r'[^<]*</display-name>',
                    re.IGNORECASE | re.DOTALL,
                )
                dn_match = dn_pattern.search(epg_data)
                if dn_match:
                    found_ids.append(dn_match.group(1))

    return list(set(found_ids))


def test_epg_programming(epg_data, channel_id, days=3):
    """Test if EPG has programming for today, tomorrow, and day after."""
    today = datetime.now()
    dates_to_check = []
    for d in range(days):
        date = today + timedelta(days=d)
        dates_to_check.append(date.strftime("%Y-%m-%d"))

    found_dates = set()
    # Search for programme entries with this channel id
    pattern = re.compile(
        r'<programme\s+[^>]*channel="' + re.escape(channel_id) + r'"[^>]*start="(\d{4})(\d{2})(\d{2})',
        re.IGNORECASE,
    )

    for match in pattern.finditer(epg_data):
        year, month, day = match.group(1), match.group(2), match.group(3)
        date_str = f"{year}-{month}-{day}"
        if date_str in dates_to_check:
            found_dates.add(date_str)

    return found_dates, dates_to_check


def has_auth_tokens(url):
    """Check if URL has authentication tokens that will expire."""
    token_patterns = [
        r'hdnea=',
        r'hmac=',
        r'exp=\d+',
        r'psid=',
        r'did=',
        r'kid=',
    ]
    for pattern in token_patterns:
        if re.search(pattern, url):
            return True
    return False


def ensure_jpg_logo(logo_url):
    """Ensure logo URL ends with .jpg."""
    if not logo_url:
        return logo_url

    # Remove any non-jpg extension and ensure .jpg
    base = logo_url.split("?")[0]  # Remove query params

    # Check if it already ends with .jpg
    if base.lower().endswith(".jpg"):
        return logo_url

    # If it ends with another image extension, replace with .jpg
    exts_to_replace = [".png", ".gif", ".jpeg", ".webp", ".svg", ".bmp"]
    for ext in exts_to_replace:
        if base.lower().endswith(ext):
            new_url = logo_url[: -len(ext)] + ".jpg"
            # Preserve query params
            if "?" in logo_url:
                new_url += logo_url[logo_url.index("?") :]
            return new_url

    # If no extension, add .jpg
    if "." not in base.split("/")[-1]:
        return logo_url + ".jpg"

    return logo_url


def main():
    log("=" * 60, "TITLE")
    log("CORREÇÃO COMPLETA DA LISTA5.M3U", "TITLE")
    log("=" * 60, "TITLE")

    # 1. Parse M3U file
    log(f"Lendo {M3U_FILE}...", "INFO")
    header, channels = parse_m3u(M3U_FILE)
    log(f"Total de entradas: {len(channels)}", "INFO")

    if not channels:
        log("Nenhum canal encontrado!", "ERROR")
        return

    # 2. Analyze channels
    log("\n--- ANÁLISE DOS CANAIS ---", "TITLE")
    unique_names = {}
    for extinf, url in channels:
        name = extract_channel_name(extinf)
        if name not in unique_names:
            unique_names[name] = []
        unique_names[name].append((extinf, url))

    for name, entries in unique_names.items():
        log(f"  {name}: {len(entries)} entradas", "INFO")

    # 3. Remove exact duplicates
    log("\n--- REMOVENDO DUPLICATAS ---", "TITLE")
    seen_urls = set()
    unique_channels = []
    duplicates_removed = 0

    for extinf, url in channels:
        url_key = url.strip()
        if url_key not in seen_urls:
            seen_urls.add(url_key)
            unique_channels.append((extinf, url))
        else:
            duplicates_removed += 1

    log(f"Duplicatas removidas: {duplicates_removed}", "OK")
    log(f"Entradas únicas: {len(unique_channels)}", "INFO")

    # 4. Remove imgur.com links
    log("\n--- REMOVENDO LINKS IMGUR ---", "TITLE")
    imgur_removed = 0
    filtered_channels = []
    for extinf, url in unique_channels:
        if "imgur.com" in url.lower() or "imgur" in extinf.lower():
            imgur_removed += 1
            log(f"  Removido (imgur): {extract_channel_name(extinf)}", "WARN")
        else:
            filtered_channels.append((extinf, url))
    log(f"Links imgur removidos: {imgur_removed}", "OK")

    # 5. Fix logos to .jpg
    log("\n--- CORRIGINDO LOGOS PARA .JPG ---", "TITLE")
    fixed_channels = []
    logos_fixed = 0
    for extinf, url in filtered_channels:
        logo = extract_logo(extinf)
        if logo:
            new_logo = ensure_jpg_logo(logo)
            if new_logo != logo:
                extinf = extinf.replace(f'tvg-logo="{logo}"', f'tvg-logo="{new_logo}"')
                logos_fixed += 1
                log(f"  Logo corrigido: {extract_channel_name(extinf)}", "OK")
        fixed_channels.append((extinf, url))
    log(f"Logos corrigidos: {logos_fixed}", "OK")

    # 6. Test streams (HTTP HEAD/GET)
    log("\n--- TESTANDO STREAMS ---", "TITLE")
    alive_channels = []
    dead_channels = []
    expired_channels = []

    for extinf, url in fixed_channels:
        name = extract_channel_name(extinf)
        has_tokens = has_auth_tokens(url)

        if has_tokens:
            log(f"  {name}: tokens de auth detectados (expira)", "WARN")
            expired_channels.append((extinf, url, name))
            continue

        log(f"  Testando: {name}...", "INFO")
        if test_stream_url(url, timeout=8):
            log(f"  {name}: VIVO", "OK")
            alive_channels.append((extinf, url))
        else:
            log(f"  {name}: MORTO", "ERROR")
            dead_channels.append((extinf, url, name))

    log(f"\nResultados:", "INFO")
    log(f"  Vivos: {len(alive_channels)}", "OK")
    log(f"  Mortos: {len(dead_channels)}", "ERROR")
    log(f"  Com tokens expirados: {len(expired_channels)}", "WARN")

    # 7. Test EPG sources
    log("\n--- TESTANDO FONTES EPG ---", "TITLE")
    working_epg = None
    epg_programming = {}

    for epg_source in EPG_SOURCES:
        log(f"\nTestando: {epg_source['name']}...", "INFO")
        log(f"  URL: {epg_source['url']}", "INFO")

        epg_data = fetch_epg_data(
            epg_source["url"],
            compressed=epg_source["compressed"],
            max_size_mb=30,
        )

        if not epg_data:
            log(f"  Falhou ao baixar", "ERROR")
            continue

        log(f"  Tamanho: {len(epg_data)} bytes", "INFO")

        # Check for our channels
        channel_ids_found = {}
        for ch_name, name_variations in CHANNEL_EPG_MAP.items():
            ids = find_channel_in_epg(epg_data, name_variations)
            if ids:
                channel_ids_found[ch_name] = ids
                log(f"  {ch_name}: IDs encontrados = {ids}", "OK")

                # Test programming for each ID
                for ch_id in ids:
                    found_dates, expected_dates = test_epg_programming(epg_data, ch_id)
                    coverage = len(found_dates) / len(expected_dates) * 100
                    log(f"    ID '{ch_id}': {len(found_dates)}/{len(expected_dates)} dias cobertos ({coverage:.0f}%)", "INFO")
                    if found_dates:
                        log(f"    Datas: {sorted(found_dates)}", "INFO")
                    epg_programming[ch_name] = {
                        "id": ch_id,
                        "found_dates": found_dates,
                        "expected_dates": expected_dates,
                    }
            else:
                log(f"  {ch_name}: NÃO ENCONTRADO", "WARN")

        if len(channel_ids_found) >= 3:  # At least 3 of 5 channels
            working_epg = epg_source
            log(f"\n  EPG SELECIONADO: {epg_source['name']}", "OK")
            break
        else:
            log(f"  Poucos canais encontrados ({len(channel_ids_found)}/{len(CHANNEL_EPG_MAP)}), tentando próxima...", "WARN")

    # 8. Build final M3U
    log("\n--- GERANDO ARQUIVO FINAL ---", "TITLE")

    # Build header with url-tvg
    epg_url = working_epg["url"] if working_epg else ""
    new_header = "#EXTM3U"
    if epg_url:
        new_header += f' url-tvg="{epg_url}"'
    log(f"Header: {new_header}", "INFO")

    # Build final channel list
    output_lines = [new_header + "\n"]

    for extinf, url in alive_channels:
        name = extract_channel_name(extinf)

        # Add tvg-id if we found one in EPG
        if name in epg_programming:
            ch_id = epg_programming[name]["id"]
            if "tvg-id" not in extinf:
                # Insert tvg-id after #EXTINF:-1
                extinf = extinf.replace("#EXTINF:-1", f'#EXTINF:-1 tvg-id="{ch_id}"', 1)

        # Ensure # is on line above URL (already should be, but verify)
        output_lines.append(extinf + "\n")
        output_lines.append(url + "\n")

    # 9. Write output
    log(f"\nEscrevendo {OUTPUT_FILE}...", "INFO")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.writelines(output_lines)

    # 10. Summary
    log("\n" + "=" * 60, "TITLE")
    log("RESUMO DA CORREÇÃO", "TITLE")
    log("=" * 60, "TITLE")
    log(f"Entradas originais: {len(channels)}", "INFO")
    log(f"Duplicatas removidas: {duplicates_removed}", "OK")
    log(f"Links imgur removidos: {imgur_removed}", "OK")
    log(f"Logos corrigidos para .jpg: {logos_fixed}", "OK")
    log(f"Streams com tokens expirados removidos: {len(expired_channels)}", "WARN")
    log(f"Streams mortos removidos: {len(dead_channels)}", "ERROR")
    log(f"Canais finais (vivos): {len(alive_channels)}", "OK")

    if working_epg:
        log(f"EPG selecionado: {working_epg['name']}", "OK")
        log(f"EPG URL: {epg_url}", "INFO")
        for ch_name, info in epg_programming.items():
            coverage = len(info["found_dates"]) / len(info["expected_dates"]) * 100
            log(f"  {ch_name}: ID={info['id']}, cobertura={coverage:.0f}%", "INFO")
    else:
        log("NENHUM EPG VÁLIDO ENCONTRADO!", "ERROR")

    # List removed channels
    if dead_channels or expired_channels:
        log("\nCanais removidos:", "WARN")
        for _, _, name in dead_channels:
            log(f"  - {name} (morto)", "ERROR")
        for _, _, name in expired_channels:
            log(f"  - {name} (token expirado)", "WARN")

    # List final channels
    log("\nCanais no arquivo final:", "OK")
    seen_final = set()
    for extinf, url in alive_channels:
        name = extract_channel_name(extinf)
        if name not in seen_final:
            seen_final.add(name)
            log(f"  - {name}", "OK")

    log(f"\nArquivo final: {OUTPUT_FILE}", "OK")
    log("Concluído!", "OK")


if __name__ == "__main__":
    main()
