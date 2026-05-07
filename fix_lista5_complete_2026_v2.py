#!/usr/bin/env python3
import requests
import gzip
import re
from datetime import datetime, timedelta
from xml.etree import ElementTree as ET

today = datetime.now().date()
tomorrow = today + timedelta(days=1)
day_after = today + timedelta(days=2)

EPG_SOURCES = {
    "us": "https://epg.pw/xmltv/epg_US.xml.gz",
    "br": "https://epg.pw/xmltv/epg_BR.xml.gz",
    "global": "https://epg.pw/xmltv/epg.xml.gz",
}

EPG_IDS = {
    "ABC News Live": "465150",
    "Fox News": "465372",
    "Fox Business": "464766",
    "CBS News": "464941",
}

LOGOS = {
    "ABC News Live": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
    "ABC News": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
    "CBS News": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
    "CBS News 24/7": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
}

def test_epg_source(url):
    print(f"  Testando EPG: {url}")
    try:
        headers = {'User-Agent': 'Mozilla/5.0', 'Accept-Encoding': 'gzip'}
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code != 200:
            print(f"    HTTP {resp.status_code}")
            return False, set()
        try:
            data = gzip.decompress(resp.content)
        except:
            data = resp.content
        root = ET.fromstring(data)

        dates = set()
        for prog in root.findall('.//programme'):
            start = prog.get('start', '')
            if start:
                try:
                    d = datetime.strptime(start[:8], '%Y%m%d').date()
                    dates.add(d)
                except:
                    pass

        print(f"    Canais: {len(root.findall('.//channel'))}, Programas: {len(root.findall('.//programme'))}")
        print(f"    Datas: {len(dates)}")
        print(f"    Hoje ({today}): {'✓' if today in dates else '✗'}")
        print(f"    Amanha ({tomorrow}): {'✓' if tomorrow in dates else '✗'}")
        print(f"    Depois ({day_after}): {'✓' if day_after in dates else '✗'}")

        has_coverage = today in dates or tomorrow in dates or day_after in dates
        return has_coverage, dates
    except Exception as e:
        print(f"    Erro: {e}")
        return False, set()

def test_url(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        resp = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        ok = resp.status_code == 200
        print(f"    {resp.status_code} {'✓' if ok else '✗'} {url[:70]}...")
        return ok, resp.status_code
    except Exception as e:
        print(f"    ERRO {str(e)[:40]} {url[:70]}...")
        return False, str(e)

CHANNELS = [
    {
        "name": "ABC News Live",
        "display": "ABC News Live - ABC News",
        "tvg_id": "465150",
        "logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
        "url": "https://abcnews-livestreams.akamaized.net/out/v1/6a597119dbd5428a82dc11a2f514a1a2/abcn-live-10-cmaf-manifest/abcn-live-10-index.m3u8",
        "group": "NEWS WORLD",
        "epg_key": "us",
    },
    {
        "name": "CBS News 24/7",
        "display": "CBS News 24/7",
        "tvg_id": "464941",
        "logo": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
        "url": "https://dai.google.com/linear/hls/pa/event/Sid4xiTQTkCT1SLu6rjUSQ/stream/9f486a29-6c4b-4f51-b456-0ff409e32c47:DLS/master.m3u8",
        "group": "NEWS WORLD",
        "epg_key": "us",
    },
]

def main():
    print("=" * 70)
    print("CORRECAO COMPLETA DO lista5.m3u")
    print(f"Data: {today}")
    print("=" * 70)

    print("\n1. TESTANDO EPG SOURCES...")
    valid_epgs = {}
    for key, url in EPG_SOURCES.items():
        ok, dates = test_epg_source(url)
        if ok:
            valid_epgs[key] = url
            print(f"    -> {key}: VALIDO ({len(dates)} dias de programacao)")
        else:
            print(f"    -> {key}: SEM PROGRAMACAO ADEQUADA")
        print()

    if not valid_epgs:
        print("ERRO: Nenhum EPG valido encontrado!")
        return

    print("\n2. TESTANDO URLS DOS CANAIS...")
    working_channels = []
    for ch in CHANNELS:
        print(f"\n  {ch['display']}:")
        ok, status = test_url(ch['url'])
        if ok:
            print(f"    -> OK!")
            working_channels.append(ch)
        else:
            print(f"    -> FALHOU ({status}) - REMOVIDO")

    print(f"\n3. CANAIS FUNCIONAIS: {len(working_channels)}/{len(CHANNELS)}")

    epg_urls_str = ",".join(valid_epgs.values())

    print(f"\n4. GERANDO lista5.m3u...")
    lines = []
    lines.append(f'#EXTM3U x-tvg-url="{epg_urls_str}"')
    lines.append("")

    for ch in working_channels:
        extinf = (
            f'#EXTINF:-1 tvg-id="{ch["tvg_id"]}" '
            f'tvg-logo="{ch["logo"]}" '
            f'group-title="{ch["group"]}"'
            f',{ch["display"]}'
        )
        lines.append(extinf)
        lines.append(ch["url"])
        lines.append("")

    output = "\n".join(lines)
    with open("lista5.m3u", "w", encoding="utf-8") as f:
        f.write(output)

    print(f"    Arquivo gerado: {len(output)} bytes")
    print(f"    Total canais: {len(working_channels)}")

    print("\n5. VERIFICANDO FORMATO...")
    with open("lista5.m3u", "r") as f:
        content = f.read()

    issues = []
    url_lines = [l for l in content.split("\n") if l.startswith("http")]
    for i, line in enumerate(content.split("\n")):
        if line.startswith("http") or line.startswith("://"):
            prev_lines = content.split("\n")[:content.split("\n").index(line)]
            if prev_lines and not prev_lines[-1].startswith("#EXTINF:"):
                issues.append(f"  URL sem #EXTINF antes: {line[:50]}...")

    extinf_lines = [l for l in content.split("\n") if l.startswith("#EXTINF:")]
    for el in extinf_lines:
        if "tvg-logo=" not in el:
            issues.append(f"  Sem tvg-logo: {el[:50]}...")
        logo_match = re.search(r'tvg-logo="([^"]*)"', el)
        if logo_match:
            logo = logo_match.group(1)
            if "imgur.com" in logo.lower():
                issues.append(f"  Logo imgur.com: {logo}")
            if not logo.lower().endswith(".jpg") and not logo.lower().endswith(".jpeg"):
                issues.append(f"  Logo nao .jpg: {logo}")

    for ch in working_channels:
        if ch["tvg_id"]:
            found = False
            for prog_el in ["prog"]:
                if re.search(r'tvg-id="' + re.escape(ch["tvg_id"]) + r'"', content):
                    found = True
                    break
            if not found:
                issues.append(f"  tvg-id ausente para {ch['display']}")

    if issues:
        print("  Problemas encontrados:")
        for iss in issues:
            print(f"    {iss}")
    else:
        print("  Nenhum problema encontrado!")

    print("\n6. VERIFICANDO EPG NA LISTA...")
    if "x-tvg-url=" in content.split("\n")[0]:
        print(f"  EPG URL no header: ✓")
        print(f"  Fontes: {epg_urls_str[:100]}...")
    else:
        print("  EPG URL no header: ✗")

    print("\n" + "=" * 70)
    print("RESULTADO FINAL")
    print("=" * 70)
    print(f"  Arquivo: lista5.m3u")
    print(f"  Canais: {len(working_channels)}")
    print(f"  EPG sources: {len(valid_epgs)}")
    print(f"  Removidos (quebrados): {len(CHANNELS) - len(working_channels)}")
    print()
    for ch in working_channels:
        print(f"  ✓ {ch['display']}")
        print(f"    tvg-id: {ch['tvg_id']}")
        print(f"    logo: {ch['logo'][:60]}...")
        print(f"    url: {ch['url'][:60]}...")
    print(f"\n  EPG sources ativas:")
    for key, url in valid_epgs.items():
        print(f"    - {key}: {url}")

if __name__ == "__main__":
    main()
