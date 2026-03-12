#!/usr/bin/env python3
"""
GLOBOEPG.py - Generate EPG for all Globo regions
Creates GLOBOEPG.xml.gz with 5 days of programming for all Globo regions
Also generates tvg-ids.txt for IPTV playlists
"""

import gzip
import json
import re
import sys
import html
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
import urllib.parse

try:
    import requests
except ImportError:
    print("Installing requests...")
    import subprocess

    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests

BASE_URL = "https://redeglobo.globo.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}

REGION_URLS = {
    "sp": "sao-paulo",
    "rj": "rio",
    "df": "globobrasilia",
    "bh": "globominas",
    "pr": "rpc",
    "pe": "tvglobo",
    "ba": "redebahia",
    "pb": "tvparaiba",
    "es": "tvgazetaes",
    "mg": "globominas",
    "ce": "tvverdesmares",
    "ms": "tvmorena",
    "mt": "tvcentroamerica",
}

REGION_NAMES = {
    "sp": "São Paulo",
    "rj": "Rio de Janeiro",
    "df": "Distrito Federal",
    "bh": "Belo Horizonte",
    "pr": "Paraná",
    "pe": "Pernambuco",
    "ba": "Bahia",
    "pb": "Paraíba",
    "es": "Espírito Santo",
    "mg": "Minas Gerais",
    "ce": "Ceará",
    "ms": "Mato Grosso do Sul",
    "mt": "Mato Grosso",
}


def fetch_page(url: str) -> Optional[str]:
    """Fetch a webpage and return its content"""
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        return response.text
    except Exception:
        return None


def extract_programming_from_html(
    html_content: str, target_date: str
) -> Optional[dict]:
    """Extract programming data for a specific date from HTML"""
    try:
        m = re.search(r'class="grade-area" data-props="([^"]+)"', html_content)
        if not m:
            return None

        raw = m.group(1)
        decoded = html.unescape(raw)
        data = json.loads(decoded)

        output = (
            data.get("context", {})
            .get("gridData", {})
            .get("data", {})
            .get("output", [])
        )

        for day_data in output:
            day_date = day_data.get("date", "")[:10]
            if day_date == target_date:
                return day_data

        return None
    except Exception:
        return None


def get_programming_for_region(
    region_code: str, region_url: str, days: int = 5
) -> dict:
    """Get programming data for a specific region for multiple days"""
    all_programs = {}
    today = datetime.now()

    base_url = f"{BASE_URL}/{region_url}/programacao/"

    html_content = fetch_page(base_url)
    if not html_content:
        return all_programs

    for day_offset in range(days):
        target_date = (today + timedelta(days=day_offset)).strftime("%Y-%m-%d")

        day_data = extract_programming_from_html(html_content, target_date)

        if day_data:
            all_programs[target_date] = day_data

    return all_programs


def parse_time(time_str: str, date_str: str) -> datetime:
    """Parse time string to datetime"""
    if not time_str:
        return datetime.now()

    try:
        if len(time_str.split(":")) == 2:
            time_str += ":00"

        dt_str = f"{date_str}T{time_str}"

        if "-03:00" not in dt_str and "+03:00" not in dt_str:
            dt_str += "-03:00"

        return datetime.fromisoformat(dt_str.replace("+03:00", "-03:00"))
    except (ValueError, AttributeError):
        return datetime.now()


def format_xml_datetime(dt: datetime) -> str:
    """Format datetime for XMLTV"""
    return dt.strftime("%Y%m%dT%H%M%S") + " -0300"


def escape_xml(text: str) -> str:
    """Escape special XML characters"""
    if not text:
        return ""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def generate_epg(regions_data: dict) -> tuple[str, list]:
    """Generate XMLTV EPG content"""
    channels = []
    programs = []
    tvg_ids = []

    for region_key, region_info in regions_data.items():
        region_name = region_info["name"]
        tvg_id = f"globo_{region_key}"
        tvg_ids.append(tvg_id)

        channel_display = f"Globo {region_name}"

        channels.append(f'''  <channel id="{tvg_id}">
    <display-name>{escape_xml(channel_display)}</display-name>
    <icon>https://s.glbimg.com/og/rg/static/img/redeglobo/logo-60x60.png</icon>
  </channel>''')

        for date_str, day_data in region_info["programs"].items():
            slots = day_data.get("slots", [])

            day_date = day_data.get("date", "")[:10]
            day_start = datetime.fromisoformat(day_date + "T00:00:00-03:00")
            current_time = day_start

            for slot in slots:
                program = slot.get("program", {})
                name = slot.get("name", "")

                if not name:
                    continue

                duration_str = slot.get("duration", "00:00:00")
                parts = duration_str.split(":")
                if len(parts) == 3:
                    delta = timedelta(
                        hours=int(parts[0]),
                        minutes=int(parts[1]),
                        seconds=int(parts[2]),
                    )
                else:
                    delta = timedelta(0)

                start_dt = current_time
                end_dt = current_time + delta
                current_time = end_dt

                description = program.get("synopsis", "") if program else ""
                category = slot.get("contentType", "")

                program_xml = f'''  <programme channel="{tvg_id}" start="{format_xml_datetime(start_dt)}" end="{format_xml_datetime(end_dt)}">
    <title lang="pt-BR">{escape_xml(name)}</title>'''

                if description:
                    program_xml += f"""
    <desc lang="pt-BR">{escape_xml(description)}</desc>"""

                if category:
                    program_xml += f"""
    <category lang="pt-BR">{escape_xml(category)}</category>"""

                program_xml += """
  </programme>"""

                programs.append(program_xml)

    xml_content = (
        f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE tv SYSTEM "xmltv.dtd">
<tv source-info-url="https://redeglobo.globo.com" source-info-name="Rede Globo">
"""
        + "\n".join(channels)
        + "\n"
        + "\n".join(programs)
        + "\n</tv>"
    )

    return xml_content, tvg_ids


def get_regions() -> list:
    """Get list of available regions from the predefined mapping"""
    return list(REGION_URLS.items())


def main():
    print("=" * 60)
    print("GLOBOEPG - Gerador de EPG da Rede Globo")
    print("=" * 60)

    print("\n1. Obtendo lista de regiões disponíveis...")
    regions = get_regions()
    print(f"   Encontradas {len(regions)} regiões")

    regions_data = {}

    print("\n2. Buscando programação para cada região...")
    for i, (region_code, region_url) in enumerate(regions, 1):
        region_name = REGION_NAMES.get(region_code, region_code.title())
        print(f"   [{i}/{len(regions)}] {region_name} ({region_code})...", end=" ")

        programs = get_programming_for_region(region_code, region_url, days=5)

        if programs:
            regions_data[region_code] = {
                "name": region_name,
                "url": region_url,
                "programs": programs,
            }
            print(f"✓ {len(programs)} dias")
        else:
            print("✗ Sem dados")

    if not regions_data:
        print("\nErro: Não foi possível obter dados de programação!")
        sys.exit(1)

    print("\n3. Gerando arquivo EPG (XML)...")
    epg_content, tvg_ids = generate_epg(regions_data)

    output_xml = "GLOBOEPG.xml"
    with open(output_xml, "w", encoding="utf-8") as f:
        f.write(epg_content)
    print(f"   ✓ {output_xml} criado")

    print("\n4. Compactando para GLOBOEPG.xml.gz...")
    output_gz = "GLOBOEPG.xml.gz"
    with gzip.open(output_gz, "wt", encoding="utf-8") as f:
        f.write(epg_content)
    print(f"   ✓ {output_gz} criado")

    print("\n5. Gerando arquivo de tvg-ids...")
    tvg_output = "tvg-ids.txt"
    with open(tvg_output, "w", encoding="utf-8") as f:
        f.write("# TVG IDs para playlists IPTV - Rede Globo\n")
        f.write(f"# Gerado em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("#\n")
        f.write("# Formato: tvg-id,tvg-name,tvg-logo,group-title\n\n")

        for region_key, region_info in regions_data.items():
            region_name = region_info["name"]
            tvg_id = f"globo_{region_key}"
            logo = "https://s.glbimg.com/og/rg/static/img/redeglobo/logo-60x60.png"
            group = "Globo"
            f.write(f'{tvg_id},"Globo {region_name}",{logo},{group}\n')

    print(f"   ✓ {tvg_output} criado")

    print("\n" + "=" * 60)
    print("Resumo:")
    print(f"  - Regiões processadas: {len(regions_data)}")
    print(f"  - Arquivos gerados:")
    print(f"    • {output_xml}")
    print(f"    • {output_gz}")
    print(f"    • {tvg_output}")
    print("=" * 60)
    print("\nEPG gerado com sucesso!")


if __name__ == "__main__":
    main()
