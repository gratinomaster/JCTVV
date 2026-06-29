#!/usr/bin/env python3
"""Corrige lista5.m3u: adiciona EPG, tvg-id, logos .jpg, testa EPG."""
import re
import os
import gzip
import json
from datetime import datetime, timezone, timedelta
from xml.etree import ElementTree as ET

M3U_PATH = "lista5.m3u"
BAK_PATH = "lista5.m3u.bak.20260628_165847"
EPG_XML = "lista5_epg.xml"
EPG_GZ = "lista5_epg_combinado.xml.gz"

EPG_SOURCES = [
    "https://raw.githubusercontent.com/JCTV/JCTV/main/lista5_epg_combinado.xml",
    "https://github.com/iptv-org/epg/raw/master/guide/us.xml.gz",
    "https://epg.pw/xmltv/epg_US.xml.gz",
]

CHANNEL_MAP = {
    "ABC News Live": {
        "tvg-id": "ABCNewsLive.us",
        "tvg-name": "ABC News Live",
        "group": "NEWS WORLD",
        "logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
        "name": "ABC News Live",
    },
    "ABC News Live - ABC News": {
        "tvg-id": "ABCNewsLive.us",
        "tvg-name": "ABC News Live",
        "group": "NEWS WORLD",
        "logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
        "name": "ABC News Live",
    },
    "Fox Business": {
        "tvg-id": "FoxBusiness.us",
        "tvg-name": "Fox Business",
        "group": "NEWS WORLD",
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/4fdfb4e5-62fc-4225-ba49-de956771ead5/1431e2ca-03f8-4f71-badb-55618b0e2e09/1280x720/match/400/225/image.jpg",
        "name": "Fox Business",
    },
    "Fox News Channel": {
        "tvg-id": "FoxNewsChannel.us",
        "tvg-name": "Fox News Channel",
        "group": "NEWS WORLD",
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/4fdfb4e5-62fc-4225-ba49-de956771ead5/1431e2ca-03f8-4f71-badb-55618b0e2e09/1280x720/match/400/225/image.jpg",
        "name": "Fox News Channel",
    },
    "CBS News 24/7 -CBS News": {
        "tvg-id": "CBSNews.us",
        "tvg-name": "CBS News",
        "group": "NEWS WORLD",
        "logo": "https://www.cbsnews.com/bundles/cbsnewsvideo/images/cbsn--main-bg.jpg",
        "name": "CBS News 24/7",
    },
    "our free live news stream": {
        "tvg-id": "CBSNews.us",
        "tvg-name": "CBS News",
        "group": "NEWS WORLD",
        "logo": "https://www.cbsnews.com/bundles/cbsnewsvideo/images/cbsn--main-bg.jpg",
        "name": "CBS News 24/7",
    },
}

STREAM_URLS = {
    "ABCNewsLive.us": [
        "https://abcnews-livestreams.akamaized.net/out/v1/6a597119dbd5428a82dc11a2f514a1a2/abcn-live-10-cmaf-manifest/abcn-live-10-index.m3u8",
    ],
    "FoxBusiness.us": [
        "https://247.foxbusiness.com/hls/live/2003756/FBNHLSv3/master.m3u8",
    ],
    "FoxNewsChannel.us": [
        "https://247.foxnews.com/hls/live/2003586/FNCHLSv3/master.m3u8",
    ],
    "CBSNews.us": [
        "https://dai.google.com/linear/hls/pa/event/Sid4xiTQTkCT1SLu6rjUSQ/stream/d4a37fb0-f1a8-4f6f-bb91-d15a41e148a6:MRN2/master.m3u8",
    ],
}


def load_epg_data():
    """Load EPG XML and parse channel programmes."""
    epg_channels = {}
    if os.path.exists(EPG_XML):
        tree = ET.parse(EPG_XML)
        root = tree.getroot()
        for ch in root.findall("channel"):
            ch_id = ch.get("id")
            epg_channels[ch_id] = {"programmes": []}
        for prog in root.findall("programme"):
            ch_id = prog.get("channel")
            if ch_id not in epg_channels:
                epg_channels[ch_id] = {"programmes": []}
            start = prog.get("start", "")
            stop = prog.get("stop", "")
            title_el = prog.find("title")
            title = title_el.text if title_el is not None else ""
            epg_channels[ch_id]["programmes"].append({
                "start": start,
                "stop": stop,
                "title": title,
            })
    return epg_channels


def test_epg_for_dates(epg_channels, tvg_id, dates):
    """Check EPG has programmes for specific dates."""
    results = {}
    for label, date_str in dates.items():
        found = False
        if tvg_id in epg_channels:
            for prog in epg_channels[tvg_id]["programmes"]:
                prog_date = prog["start"][:8] if prog["start"] else ""
                if prog_date == date_str:
                    found = True
                    break
        results[label] = found
    return results


def main():
    today = datetime.now(timezone.utc)
    check_dates = {
        "Hoje": today.strftime("%Y%m%d"),
        "Amanha": (today + timedelta(days=1)).strftime("%Y%m%d"),
        "Depois de amanha": (today + timedelta(days=2)).strftime("%Y%m%d"),
    }

    print("=" * 60)
    print(f"Corrigindo lista5.m3u - {today.strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 60)

    epg_channels = load_epg_data()
    print(f"\nEPG carregado: {len(epg_channels)} canais")
    for ch_id, data in epg_channels.items():
        print(f"  {ch_id}: {len(data['programmes'])} programas")

    print("\n--- Teste EPG para cada canal ---")
    all_epg_ok = True
    for ch_name, cfg in CHANNEL_MAP.items():
        if ch_name in ["ABC News Live", "Fox Business", "Fox News Channel", "CBS News 24/7 -CBS News", "ABC News Live - ABC News", "our free live news stream"]:
            tvg_id = cfg["tvg-id"]
            results = test_epg_for_dates(epg_channels, tvg_id, check_dates)
            status = "OK" if all(results.values()) else "FALHA"
            print(f"  {cfg['name']:25s} | tvg-id={tvg_id:20s} | {status}")
            for label, found in results.items():
                print(f"    {label}: {'✓' if found else '✗'}")
            if not all(results.values()):
                all_epg_ok = False

    if not all_epg_ok:
        print("\n⚠  Alguns canais sem EPG completo. Verifique o XML.")

    # Build deduplicated channel entries
    seen_channels = set()
    unique_entries = []

    for ch_name, cfg in CHANNEL_MAP.items():
        if ch_name in ["ABC News Live - ABC News", "our free live news stream"]:
            continue
        tvg_id = cfg["tvg-id"]
        if tvg_id in seen_channels:
            continue
        seen_channels.add(tvg_id)

        if tvg_id not in STREAM_URLS:
            print(f"⚠  Sem stream URL para {ch_name} (tvg-id={tvg_id})")
            continue

        url = STREAM_URLS[tvg_id][0]

        extinf = (
            f'#EXTINF:-1 tvg-id="{cfg["tvg-id"]}" '
            f'tvg-logo="{cfg["logo"]}" '
            f'tvg-name="{cfg["tvg-name"]}" '
            f'group-title="{cfg["group"]}"'
            f',{cfg["name"]}'
        )
        unique_entries.append((extinf, url))

    # Write corrected M3U
    epg_urls_str = " ".join(EPG_SOURCES)
    lines = [f'#EXTM3U url-tvg="{epg_urls_str}"']
    for extinf, url in unique_entries:
        lines.append(extinf)
        lines.append(url)

    # Backup current file
    if os.path.exists(M3U_PATH):
        bak_name = f"{M3U_PATH}.bak.{today.strftime('%Y%m%d_%H%M%S')}"
        os.rename(M3U_PATH, bak_name)
        print(f"\nBackup criado: {bak_name}")

    with open(M3U_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"\nArquivo {M3U_PATH} escrito com {len(unique_entries)} canais únicos")
    print(f"EPG Sources: {epg_urls_str}")

    # Verification
    print("\n--- Verificação Final ---")
    with open(M3U_PATH, "r") as f:
        content = f.read()

    issues = []
    if "url-tvg=" not in content:
        issues.append("Falta url-tvg no header!")
    if "#EXTM3U" not in content:
        issues.append("Falta #EXTM3U!")
    if not issues:
        print("✓ Header OK (url-tvg presente)")
    else:
        for iss in issues:
            print(f"✗ {iss}")

    lines_list = content.strip().split("\n")
    for i, line in enumerate(lines_list):
        if line.startswith("http") and not lines_list[i - 1].startswith("#EXTINF"):
            issues.append(f"Linha {i+1}: URL sem #EXTINF acima")

    tvg_ids = set()
    for line in lines_list:
        m = re.search(r'tvg-id="([^"]+)"', line)
        if m:
            tvg_ids.add(m.group(1))

    print(f"✓ {len(tvg_ids)} canais com tvg-id: {', '.join(sorted(tvg_ids))}")

    # Validate EPG again from written file
    for tvg_id in sorted(tvg_ids):
        if tvg_id in epg_channels:
            count = len(epg_channels[tvg_id]["programmes"])
            print(f"  {tvg_id}: {count} programas EPG")
        else:
            print(f"  {tvg_id}: SEM EPG!")

    # Check logos are .jpg
    logo_issues = 0
    for line in lines_list:
        m = re.search(r'tvg-logo="([^"]+)"', line)
        if m:
            url_logo = m.group(1)
            if not url_logo.lower().endswith(".jpg") and not url_logo.lower().endswith(".jpeg"):
                if "imgur.com" in url_logo:
                    print(f"✗ Logo imgur.com encontrado: {url_logo}")
                    logo_issues += 1
                else:
                    print(f"⚠ Logo não .jpg: {url_logo}")
                    logo_issues += 1

    if logo_issues == 0:
        print("✓ Todos os logos são .jpg")
    else:
        print(f"✗ {logo_issues} logos com formato incorreto")

    print(f"\n✓ Correção concluída. {len(unique_entries)} canais no {M3U_PATH}")


if __name__ == "__main__":
    main()
