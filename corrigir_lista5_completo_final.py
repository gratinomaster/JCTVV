#!/usr/bin/env python3
import re
import xml.etree.ElementTree as ET
import shutil
from datetime import datetime, timedelta

M3U_PATH = "/home/runner/work/JCTVV/JCTVV/lista5.m3u"
EPG_PATH = "/home/runner/work/JCTVV/JCTVV/lista5_epg.xml"
BACKUP_PATH = "/home/runner/work/JCTVV/JCTVV/lista5.m3u.bak." + datetime.now().strftime("%Y%m%d_%H%M%S")

CHANNEL_EPG_MAP = {
    "abc news live": {
        "tvg_id": "ABCNewsLive.us",
        "tvg_url": "https://raw.githubusercontent.com/anomalyco/EPG/main/lista5_epg.xml",
        "tvg_logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg"
    },
    "watch cbs news 24/7": {
        "tvg_id": "CBSNews.us",
        "tvg_url": "https://raw.githubusercontent.com/anomalyco/EPG/main/lista5_epg.xml",
        "tvg_logo": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg"
    },
    "fox business go": {
        "tvg_id": "FoxBusiness.us",
        "tvg_url": "https://raw.githubusercontent.com/anomalyco/EPG/main/lista5_epg.xml",
        "tvg_logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/6e3fd75c-cc16-4c29-abf5-7fd2c8d69048/8c8fbd37-685b-4a1a-81d6-26353d7db283/1280x720/match/393/221/image.jpg"
    },
    "watch fox news channel online": {
        "tvg_id": "FoxNewsChannel.us",
        "tvg_url": "https://raw.githubusercontent.com/anomalyco/EPG/main/lista5_epg.xml",
        "tvg_logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/15de0523-3be4-4a9a-8159-7020114e7036/b6ff623a-26d6-4fd9-8bb8-0856adbf38ce/1280x720/match/676/380/image.jpg"
    },
    "video severe storms": {
        "tvg_id": "ABCNewsLive.us",
        "tvg_url": "https://raw.githubusercontent.com/anomalyco/EPG/main/lista5_epg.xml",
        "tvg_logo": "https://keyframe-cdn.abcnews.com/streamprovider10.jpg"
    }
}

DEFAULT_EPG_URL = "https://raw.githubusercontent.com/anomalyco/EPG/main/lista5_epg.xml"

def verify_epg():
    print("Verificando EPG...")
    tree = ET.parse(EPG_PATH)
    root = tree.getroot()

    channel_ids = set()
    for ch in root.findall("channel"):
        channel_ids.add(ch.get("id"))

    print(f"  Canais no EPG: {len(channel_ids)}")
    for cid in sorted(channel_ids):
        print(f"    - {cid}")

    today = datetime.now().strftime("%Y%m%d")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
    day_after = (datetime.now() + timedelta(days=2)).strftime("%Y%m%d")

    prog_counts = {today: 0, tomorrow: 0, day_after: 0}
    for prog in root.findall("programme"):
        start = prog.get("start", "")
        d = start[:8]
        if d in prog_counts:
            prog_counts[d] += 1

    missing = []
    for needed_id in set(v["tvg_id"] for v in CHANNEL_EPG_MAP.values()):
        if needed_id not in channel_ids:
            missing.append(needed_id)
        count = sum(1 for p in root.findall(f"programme[@channel='{needed_id}']")
                    if p.get("start", "")[:8] in prog_counts)
        print(f"  EPG para {needed_id}: {count} programas em {today[:6]}")

    print(f"\n  Programas para hoje ({today}): {prog_counts[today]}")
    print(f"  Programas para amanhã ({tomorrow}): {prog_counts[tomorrow]}")
    print(f"  Programas para depois ({day_after}): {prog_counts[day_after]}")

    if missing:
        print(f"  AVISO: Canais sem EPG: {missing}")
    else:
        print("  OK: Todos os canais tem EPG disponivel")

    return prog_counts[today] > 0 and prog_counts[tomorrow] > 0

def fix_m3u():
    print(f"\nLendo {M3U_PATH}...")
    with open(M3U_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.split("\n")
    new_lines = []
    i = 0
    stats = {"fixed_epg": 0, "fixed_logo": 0, "fixed_missing_extinf": 0, "entries": 0}

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("#EXTINF:"):
            stats["entries"] += 1
            name_match = re.search(r',(.+)$', stripped)
            channel_name = name_match.group(1).strip().lower() if name_match else ""

            matched_key = None
            for key in sorted(CHANNEL_EPG_MAP.keys(), key=len, reverse=True):
                if channel_name.startswith(key):
                    matched_key = key
                    break
                if key in channel_name:
                    matched_key = key
                    break

            if matched_key:
                epg_info = CHANNEL_EPG_MAP[matched_key]

                tvg_id = epg_info["tvg_id"]
                tvg_url = epg_info["tvg_url"]
                tvg_logo = epg_info["tvg_logo"]

                if 'tvg-id="' not in stripped:
                    stripped = re.sub(
                        r'(#EXTINF:-1)',
                        f'\\1 tvg-id="{tvg_id}" tvg-url="{tvg_url}"',
                        stripped
                    )
                    stats["fixed_epg"] += 1

                logo_match = re.search(r'tvg-logo="([^"]*)"', stripped)
                if logo_match:
                    current_logo = logo_match.group(1)
                    if current_logo != tvg_logo:
                        stripped = stripped.replace(
                            f'tvg-logo="{current_logo}"',
                            f'tvg-logo="{tvg_logo}"'
                        )
                        stats["fixed_logo"] += 1
                else:
                    stripped = re.sub(
                        r'(group-title="[^"]*")',
                        f'\\1 tvg-logo="{tvg_logo}"',
                        stripped
                    )
                    stats["fixed_logo"] += 1

            new_lines.append(stripped)
            i += 1

            if i < len(lines):
                url_line = lines[i].strip()
                if url_line and not url_line.startswith("#"):
                    new_lines.append(url_line)
                else:
                    stats["fixed_missing_extinf"] += 1
                i += 1
        else:
            if stripped or (i == 0 and stripped == "#EXTM3U"):
                new_lines.append(stripped)
            else:
                new_lines.append(stripped)
            i += 1

    output = "\n".join(new_lines)
    if not output.endswith("\n"):
        output += "\n"

    print(f"\nEstatisticas:")
    print(f"  Total de entradas: {stats['entries']}")
    print(f"  EPG adicionado/corrigido: {stats['fixed_epg']}")
    print(f"  Logo corrigido: {stats['fixed_logo']}")
    print(f"  Linhas sem #EXTINF: {stats['fixed_missing_extinf']}")

    return output

def verify_output(m3u_content):
    print("\nVerificando saida...")
    issues = []

    lines = m3u_content.strip().split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTINF:"):
            i += 1
            if i < len(lines):
                url = lines[i].strip()
                if not url or url.startswith("#"):
                    issues.append(f"Linha {i+1}: URL ausente apos #EXTINF")
                elif not url.startswith("http"):
                    issues.append(f"Linha {i+1}: URL parece invalida: {url[:50]}")
            i += 1
        elif line.startswith("http"):
            issues.append(f"Linha {i+1}: URL sem #EXTINF acima")
            i += 1
        else:
            i += 1

    extinf_count = len(re.findall(r'#EXTINF:', m3u_content))
    url_count = len(re.findall(r'^https?://', m3u_content, re.MULTILINE))

    if extinf_count != url_count:
        issues.append(f"Discrepancia: {extinf_count} #EXTINF vs {url_count} URLs")

    tvg_ids = set(re.findall(r'tvg-id="([^"]*)"', m3u_content))
    print(f"  tvg-ids encontrados: {tvg_ids}")

    for tid in tvg_ids:
        if tid not in [v["tvg_id"] for v in CHANNEL_EPG_MAP.values()]:
            issues.append(f"tvg-id desconhecido: {tid}")

    logos = re.findall(r'tvg-logo="([^"]*)"', m3u_content)
    for logo in logos:
        if not logo.endswith(".jpg") and "?ve=" not in logo:
            issues.append(f"Logo nao termina em .jpg: {logo[:60]}")
        if "imgur.com" in logo:
            issues.append(f"Logo do imgur.com detectado: {logo[:60]}")

    print(f"  Total #EXTINF: {extinf_count}")
    print(f"  Total URLs: {url_count}")
    print(f"  Total logos: {len(logos)}")

    if issues:
        print(f"\n  Problemas encontrados ({len(issues)}):")
        for iss in issues[:10]:
            print(f"    - {iss}")
    else:
        print("  OK: Nenhum problema encontrado")

    return len(issues) == 0

def main():
    print("=" * 60)
    print("CORRECAO LISTA5.M3U - EPG, LOGOS, FORMATACAO")
    print("=" * 60)

    epg_ok = verify_epg()

    print(f"\nFazendo backup em {BACKUP_PATH}...")
    shutil.copy2(M3U_PATH, BACKUP_PATH)

    m3u_content = fix_m3u()

    print(f"\nSalvando {M3U_PATH}...")
    with open(M3U_PATH, "w", encoding="utf-8") as f:
        f.write(m3u_content)

    is_valid = verify_output(m3u_content)

    print(f"\n{'='*60}")
    print(f"EPG OK: {'SIM' if epg_ok else 'NAO - VERIFICAR'}")
    print(f"Arquivo valido: {'SIM' if is_valid else 'NAO - VERIFICAR'}")
    print(f"Backup: {BACKUP_PATH}")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
