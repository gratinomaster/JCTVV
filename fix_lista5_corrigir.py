#!/usr/bin/env python3
import requests
import gzip
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from urllib.parse import urlparse
import sys
import os

M3U_FILE = "lista5.m3u"

EPG_SOURCES = {
    "global": {"url": "https://epg.pw/xmltv/epg.xml.gz", "label": "EPG Global"},
    "us": {"url": "https://iptv-epg.org/files/epg-us.xml.gz", "label": "EPG EUA"},
    "br": {"url": "https://epg.pw/xmltv/epg_BR.xml.gz", "label": "EPG Brasil"},
    "uk": {"url": "https://iptv-epg.org/files/epg-gb.xml.gz", "label": "EPG UK"},
    "es": {"url": "https://iptv-epg.org/files/epg-es.xml.gz", "label": "EPG Espanha"},
    "fr": {"url": "https://iptv-epg.org/files/epg-fr.xml.gz", "label": "EPG Franca"},
    "de": {"url": "https://iptv-epg.org/files/epg-de.xml.gz", "label": "EPG Alemanha"},
    "it": {"url": "https://iptv-epg.org/files/epg-it.xml.gz", "label": "EPG Italia"},
    "share_br": {"url": "https://epgshare01.online/epgshare01/epg_ripper_BR1.xml.gz", "label": "EPG Share BR"},
    "share_uk": {"url": "https://epgshare01.online/epgshare01/epg_ripper_UK1.xml.gz", "label": "EPG Share UK"},
}

CHANNEL_MAP = {
    "ABC News Live": {"tvg_id": "ABCNewsLive.us", "epg_key": "us", "group": "NEWS WORLD",
                      "logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg"},
    "ABC News": {"tvg_id": "ABCNewsLive.us", "epg_key": "us", "group": "NEWS WORLD",
                 "logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg"},
    "ABC": {"tvg_id": "ABCNewsLive.us", "epg_key": "us", "group": "NEWS WORLD",
            "logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg"},
    "Fox News": {"tvg_id": "FoxNewsChannel.us", "epg_key": "us", "group": "NEWS WORLD",
                 "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/60/Fox_News_Channel_logo.svg/512px-Fox_News_Channel_logo.svg.jpg"},
    "Fox Business": {"tvg_id": "FoxBusiness.us", "epg_key": "us", "group": "NEWS WORLD",
                     "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0c/Fox_Business.svg/512px-Fox_Business.svg.jpg"},
    "CBS News": {"tvg_id": "CBSNews.us", "epg_key": "us", "group": "NEWS WORLD",
                 "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5d/CBS_News_Logo.svg/512px-CBS_News_Logo.svg.jpg"},
    "CBS News 24/7": {"tvg_id": "CBSNews.us", "epg_key": "us", "group": "NEWS WORLD",
                      "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5d/CBS_News_Logo.svg/512px-CBS_News_Logo.svg.jpg"},
    "Watch Fox News Channel Online": {"tvg_id": "FoxNewsChannel.us", "epg_key": "us", "group": "NEWS WORLD",
                                      "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/60/Fox_News_Channel_logo.svg/512px-Fox_News_Channel_logo.svg.jpg"},
    "Watch CBS News 24/7, our free live news stream": {"tvg_id": "CBSNews.us", "epg_key": "us", "group": "NEWS WORLD",
                                                       "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5d/CBS_News_Logo.svg/512px-CBS_News_Logo.svg.jpg"},
    "Fox Business Go": {"tvg_id": "FoxBusiness.us", "epg_key": "us", "group": "NEWS WORLD",
                        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0c/Fox_Business.svg/512px-Fox_Business.svg.jpg"},
    "Watch Fox News Channel Online | Stream Fox News": {"tvg_id": "FoxNewsChannel.us", "epg_key": "us", "group": "NEWS WORLD",
                                                        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/60/Fox_News_Channel_logo.svg/512px-Fox_News_Channel_logo.svg.jpg"},
    "Fox Business Go | Fox News Video": {"tvg_id": "FoxBusiness.us", "epg_key": "us", "group": "NEWS WORLD",
                                         "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0c/Fox_Business.svg/512px-Fox_Business.svg.jpg"},
}

def identify_channel(name):
    CHANNEL_ALIASES = {
        "ABC News Live": ["abc news live", "abc news"],
        "Fox Business": ["fox business", "fox business go"],
        "Fox News": ["fox news", "watch fox news channel online"],
        "CBS News 24/7": ["cbs news", "watch cbs news"],
    }
    name_lower = name.lower()
    for canonical, aliases in CHANNEL_ALIASES.items():
        for a in aliases:
            if a in name_lower:
                return canonical
    return name

def fix_logo(logo_url):
    if not logo_url:
        return None
    if "imgur.com" in logo_url.lower():
        return None
    parsed = urlparse(logo_url)
    path = parsed.path.lower()
    if path.endswith('.svg') or path.endswith('.png') or path.endswith('.webp') or path.endswith('.gif'):
        base = logo_url.rsplit('.', 1)[0]
        return base + '.jpg'
    if not path.endswith('.jpg') and not path.endswith('.jpeg'):
        if '.' in path.split('/')[-1]:
            base = logo_url.rsplit('.', 1)[0]
            return base + '.jpg'
    return logo_url

def download_epg(url):
    try:
        r = requests.get(url, timeout=180, headers={'Accept-Encoding': 'gzip', 'User-Agent': 'Mozilla/5.0'})
        r.raise_for_status()
        try:
            return gzip.decompress(r.content).decode('utf-8')
        except:
            return r.text
    except Exception as e:
        return None

def test_epg_programming(xml_content, tvg_id):
    result = {"status": "sem_programacao", "hoje": 0, "amanha": 0, "depois_amanha": 0, "programas_amostra": []}
    try:
        root = ET.fromstring(xml_content)
        hoje = datetime.now().strftime("%Y%m%d")
        amanha = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
        depois = (datetime.now() + timedelta(days=2)).strftime("%Y%m%d")
        for prog in root.findall("programme"):
            ch = prog.get("channel", "")
            if ch == tvg_id or tvg_id.lower() in ch.lower() or ch.lower() in tvg_id.lower():
                start = prog.get("start", "")[:8]
                title = prog.findtext("title", "sem titulo")
                if start == hoje:
                    result["hoje"] += 1
                    if len(result["programas_amostra"]) < 2:
                        result["programas_amostra"].append(f"Hoje: {title}")
                elif start == amanha:
                    result["amanha"] += 1
                elif start == depois:
                    result["depois_amanha"] += 1
        if result["hoje"] > 0 and result["amanha"] > 0 and result["depois_amanha"] > 0:
            result["status"] = "completo"
        elif result["hoje"] > 0 and result["amanha"] > 0:
            result["status"] = "parcial_2dias"
        elif result["hoje"] > 0:
            result["status"] = "parcial_hoje"
    except:
        pass
    return result

def test_url(url):
    try:
        r = requests.head(url, timeout=15, allow_redirects=True, headers={'User-Agent': 'Mozilla/5.0'})
        return r.status_code < 400
    except:
        try:
            r = requests.get(url, timeout=15, stream=True, headers={'User-Agent': 'Mozilla/5.0'})
            return r.status_code < 400
        except:
            return False

def main():
    print("=" * 70)
    print("CORRECAO COMPLETA lista5.m3u")
    print("=" * 70)

    with open(M3U_FILE, 'r', encoding='utf-8') as f:
        raw_lines = f.readlines()

    channels_raw = []
    i = 0
    while i < len(raw_lines):
        line = raw_lines[i].strip()
        if line.startswith('#EXTINF:'):
            url = raw_lines[i + 1].strip() if i + 1 < len(raw_lines) else ""
            extinf = line
            tvg_id = re.search(r'tvg-id="([^"]*)"', line)
            tvg_logo = re.search(r'tvg-logo="([^"]*)"', line)
            group = re.search(r'group-title="([^"]*)"', line)
            name_match = re.search(r',(.+)$', line)
            name = name_match.group(1).strip() if name_match else ""
            channels_raw.append({
                "extinf": extinf, "url": url, "name": name,
                "tvg_id": tvg_id.group(1) if tvg_id else "",
                "tvg_logo": tvg_logo.group(1) if tvg_logo else "",
                "group": group.group(1) if group else "",
            })
            i += 2
        else:
            i += 1

    print(f"\nCanais brutos encontrados: {len(channels_raw)}")

    # Normalize names and find unique channels
    unique_channels = {}
    for ch in channels_raw:
        canonical = identify_channel(ch["name"])
        if canonical not in unique_channels:
            unique_channels[canonical] = {"urls": [], "group": ch["group"], "tvg_logo": ch["tvg_logo"]}
        unique_channels[canonical]["urls"].append(ch["url"])

    print(f"Canais unicos identificados: {len(unique_channels)}")
    for name, data in unique_channels.items():
        print(f"  - {name}: {len(data['urls'])} URLs")

    # Download EPGs
    print("\n" + "-" * 70)
    print("BAIXANDO EPGs...")
    epg_data = {}
    for key, src in EPG_SOURCES.items():
        print(f"  {src['label']}...", end=" ", flush=True)
        content = download_epg(src["url"])
        if content and len(content) > 1000:
            epg_data[key] = {"content": content, "url": src["url"]}
            print(f"OK ({len(content):,} bytes)")
        else:
            print("FALHOU")

    print(f"\nEPGs carregados: {len(epg_data)}")

    # Test EPG for each channel
    print("\n" + "-" * 70)
    print("TESTANDO EPG PARA CADA CANAL...")
    channel_results = []
    for name, data in unique_channels.items():
        cfg = CHANNEL_MAP.get(name, {})
        tvg_id = cfg.get("tvg_id", "")
        epg_key = cfg.get("epg_key", "global")
        group = cfg.get("group", data["group"])
        logo = data["tvg_logo"] or ""
        if logo and not "imgur.com" in logo.lower():
            logo = fix_logo(logo)
        if not logo or "imgur.com" in logo.lower():
            logo = cfg.get("logo", "")
            if logo:
                logo = fix_logo(logo)

        epg_result = {"status": "sem_epg", "hoje": 0, "amanha": 0, "depois_amanha": 0, "programas_amostra": []}
        epg_url_used = ""

        if tvg_id:
            if epg_key in epg_data:
                epg_result = test_epg_programming(epg_data[epg_key]["content"], tvg_id)
                if epg_result["status"] != "sem_programacao":
                    epg_url_used = epg_data[epg_key]["url"]
            if epg_result["status"] == "sem_programacao":
                for k, v in epg_data.items():
                    if k != epg_key:
                        epg_result = test_epg_programming(v["content"], tvg_id)
                        if epg_result["status"] != "sem_programacao":
                            epg_url_used = v["url"]
                            break
                if epg_result["status"] == "sem_programacao":
                    # Try with just name matching
                    for k, v in epg_data.items():
                        epg_result = test_epg_programming(v["content"], name)
                        if epg_result["status"] != "sem_programacao":
                            epg_url_used = v["url"]
                            break

        status_str = epg_result["status"]
        if status_str == "completo":
            status_icon = "OK"
        elif "parcial" in status_str:
            status_icon = "PARCIAL"
        else:
            status_icon = "SEM EPG"

        print(f"  {name:<25} tvg-id={tvg_id:<20} EPG={status_icon:<12} H:{epg_result['hoje']} A:{epg_result['amanha']} D:{epg_result['depois_amanha']}")

        channel_results.append({
            "name": name,
            "tvg_id": tvg_id,
            "group": group or "NEWS WORLD",
            "logo": logo,
            "urls": data["urls"],
            "epg_result": epg_result,
            "epg_url": epg_url_used or EPG_SOURCES.get("global", {}).get("url", ""),
        })

    # Test URLs for accessibility
    print("\n" + "-" * 70)
    print("TESTANDO URLs...")
    all_urls = []
    for ch in channel_results:
        for u in ch["urls"]:
            if u not in all_urls:
                all_urls.append(u)

    url_status = {}
    for idx, url in enumerate(all_urls):
        ok = test_url(url)
        url_status[url] = ok
        status_txt = "OK" if ok else "FALHOU"
        if idx < 10 or not ok:
            print(f"  [{status_txt}] {url[:80]}...")
        elif idx == 10:
            print(f"  ... testando mais {len(all_urls) - 10} URLs...")

    working_count = sum(1 for v in url_status.values() if v)
    print(f"\n  URLs funcionando: {working_count}/{len(url_status)}")

    # Generate output
    print("\n" + "-" * 70)
    print("GERANDO lista5.m3u CORRIGIDO...")

    # Collect all EPG URLs used
    epg_urls_used = sorted(set(ch["epg_url"] for ch in channel_results if ch["epg_url"]))

    # Create back up
    os.rename(M3U_FILE, M3U_FILE + ".bak") if os.path.exists(M3U_FILE) else None

    with open(M3U_FILE, 'w', encoding='utf-8') as f:
        if epg_urls_used:
            f.write(f'#EXTM3U x-tvg-url="{",".join(epg_urls_used[:5])}"\n')
        else:
            f.write("#EXTM3U\n")

        for ch in channel_results:
            if not ch["urls"]:
                continue
            working_urls = [u for u in ch["urls"] if url_status.get(u, False)]
            final_urls = list(dict.fromkeys(working_urls)) if working_urls else list(dict.fromkeys(ch["urls"]))
            final_urls = final_urls[:3]

            for url in final_urls:
                attrs = []
                if ch["tvg_id"]:
                    attrs.append(f'tvg-id="{ch["tvg_id"]}"')
                if ch["logo"]:
                    attrs.append(f'tvg-logo="{ch["logo"]}"')
                attrs.append(f'group-title="{ch["group"]}"')
                attrs_str = " ".join(attrs)
                f.write(f'#EXTINF:-1 {attrs_str},{ch["name"]}\n')
                f.write(url + "\n")

    final_count = sum(len([u for u in ch["urls"] if url_status.get(u, True)]) for ch in channel_results)
    print(f"\nOK! {M3U_FILE} atualizado!")
    print(f"  - Canais unicos: {len(channel_results)}")
    print(f"  - URLs finais: {sum(len(ch['urls']) for ch in channel_results)}")
    print(f"  - URLs funcionando: {working_count}")
    print(f"  - EPGs incluidos: {len(epg_urls_used)}")

    # Summary
    print("\n" + "=" * 70)
    print("RELATORIO FINAL")
    print("=" * 70)
    for ch in channel_results:
        epg = ch["epg_result"]
        status = {
            "completo": "EPG COMPLETO (3 dias)",
            "parcial_2dias": "EPG PARCIAL (2 dias)",
            "parcial_hoje": "EPG APENAS HOJE",
            "sem_programacao": "SEM PROGRAMACAO",
            "sem_epg": "SEM EPG"
        }.get(epg["status"], epg["status"])
        print(f"  {ch['name']:<25} | {status:<25} | H:{epg['hoje']:>3} A:{epg['amanha']:>3} D:{epg['depois_amanha']:>3}")
        for s in epg.get("programas_amostra", []):
            print(f"    -> {s}")

    with open("relatorio_lista5.txt", "w", encoding="utf-8") as f:
        f.write(f"RELATORIO CORRECAO lista5.m3u\n")
        f.write(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"{'='*60}\n\n")
        for ch in channel_results:
            epg = ch["epg_result"]
            f.write(f"Canal: {ch['name']}\n")
            f.write(f"  tvg-id: {ch['tvg_id']}\n")
            f.write(f"  EPG: {epg['status']} (Hoje:{epg['hoje']} Amanha:{epg['amanha']} Depois:{epg['depois_amanha']})\n")
            f.write(f"  Logo: {ch['logo']}\n")
            f.write(f"  URLs: {len(ch['urls'])}\n\n")

    print(f"\nRelatorio salvo em: relatorio_lista5.txt")
    print(f"Backup: {M3U_FILE}.bak")

if __name__ == "__main__":
    main()
