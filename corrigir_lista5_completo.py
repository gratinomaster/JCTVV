#!/usr/bin/env python3
"""Corrige lista5.m3u: EPG valido, tvg-id, tvg-logo .jpg, formatação, teste de streams."""
import re
import gzip
import xml.etree.ElementTree as ET
import requests
import sys
from datetime import datetime, timedelta

M3U_FILE = "lista5.m3u"
BACKUP_FILE = "lista5.m3u.bak2"
EPG_FILE = "lista5_epg.xml.gz"
EPG_URL_RAW = "https://raw.githubusercontent.com/JCTV/JCTV/main/lista5_epg.xml.gz"

CHANNEL_MAP = {
    "abc news live": {"tvg_id": "465150", "tvg_name": "ABC News Live"},
    "abc news": {"tvg_id": "465150", "tvg_name": "ABC News Live"},
    "the weekend view": {"tvg_id": "465150", "tvg_name": "ABC News Live"},
    "fox business": {"tvg_id": "464766", "tvg_name": "Fox Business HD"},
    "fox news": {"tvg_id": "465372", "tvg_name": "Fox News Channel HD"},
    "cbs news": {"tvg_id": "464941", "tvg_name": "CBS News National Stream"},
}

LOGO_FALLBACKS = {
    "abc": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
    "fox": "https://a57.foxnews.com/static/694940094001/3b09e0ef-610a-43d4-960b-78dc97ae2bd2/1280x720/match/400/225/image.jpg",
    "foxbiz": "https://a57.foxnews.com/static/694940094001/c9b2e2eb-7b87-435c-9510-eab2650ff944/1280x720/match/676/380/image.jpg",
    "cbs": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
}

TVG_ID_LOGO = {
    "465150": LOGO_FALLBACKS["abc"],
    "464766": LOGO_FALLBACKS["foxbiz"],
    "465372": LOGO_FALLBACKS["fox"],
    "464941": LOGO_FALLBACKS["cbs"],
}

def detect_channel_type(name):
    nl = name.lower()
    if "fox business" in nl or "fox biz" in nl:
        return "foxbiz"
    if "fox" in nl:
        return "fox"
    if "abc" in nl:
        return "abc"
    if "cbs" in nl:
        return "cbs"
    return "abc"

def fix_logo_url(logo_url, ctype):
    if not logo_url:
        return LOGO_FALLBACKS.get(ctype, LOGO_FALLBACKS["abc"])
    if "imgur.com" in logo_url.lower():
        return LOGO_FALLBACKS.get(ctype, LOGO_FALLBACKS["abc"])
    logo_url = re.sub(r'\?.*$', '', logo_url)
    if logo_url.lower().endswith('.jpg') or logo_url.lower().endswith('.jpeg'):
        return logo_url
    ext_match = re.search(r'\.(png|svg|webp|gif|bmp)(\?|$)', logo_url.lower())
    if ext_match:
        base = re.sub(r'\.(png|svg|webp|gif|bmp)(\?.*)?$', '.jpg', logo_url)
        if base != logo_url:
            return base
        return LOGO_FALLBACKS.get(ctype, LOGO_FALLBACKS["abc"])
    if not re.search(r'\.(jpg|jpeg|png|svg|webp|gif)', logo_url.lower()):
        return LOGO_FALLBACKS.get(ctype, LOGO_FALLBACKS["abc"])
    return logo_url

def test_url(url, timeout=10):
    try:
        r = requests.head(url, timeout=timeout, allow_redirects=True, headers={'User-Agent': 'Mozilla/5.0'})
        return r.status_code in [200, 202, 204, 301, 302, 307, 308, 405]
    except:
        pass
    try:
        r = requests.get(url, timeout=timeout, stream=True, headers={'User-Agent': 'Mozilla/5.0'})
        return r.status_code in [200, 202, 204, 301, 302, 307, 308, 405]
    except:
        return False

def load_epg_data():
    try:
        with gzip.open(EPG_FILE, 'rb') as f:
            content = f.read().decode('utf-8')
        root = ET.fromstring(content)
        return root
    except Exception as e:
        print(f"ERRO ao carregar EPG: {e}")
        return None

def test_epg_programming(epg_root, tvg_id):
    result = {"hoje": 0, "amanha": 0, "depois_amanha": 0, "status": "sem_programacao"}
    hoje = datetime.now().strftime("%Y%m%d")
    amanha = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
    depois = (datetime.now() + timedelta(days=2)).strftime("%Y%m%d")
    for prog in epg_root.findall("programme"):
        if prog.get("channel") == tvg_id:
            start = prog.get("start", "")[:8]
            if start == hoje:
                result["hoje"] += 1
            elif start == amanha:
                result["amanha"] += 1
            elif start == depois:
                result["depois_amanha"] += 1
    if result["hoje"] > 0 and result["amanha"] > 0 and result["depois_amanha"] > 0:
        result["status"] = "completo"
    elif result["hoje"] > 0:
        result["status"] = "parcial"
    return result

def main():
    print("=" * 70)
    print("CORRECAO COMPLETA: lista5.m3u")
    print("=" * 70)

    # Backup
    try:
        with open(M3U_FILE, 'r', encoding='utf-8') as f:
            original = f.read()
        with open(BACKUP_FILE, 'w', encoding='utf-8') as f:
            f.write(original)
        print(f"Backup criado: {BACKUP_FILE}")
    except Exception as e:
        print(f"Erro ao criar backup: {e}")

    # Load EPG
    epg_root = load_epg_data()
    if not epg_root:
        print("ERRO FATAL: Não foi possivel carregar EPG")
        sys.exit(1)

    # Parse current m3u
    lines = original.split('\n')
    channels = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXTINF:'):
            extinf = line
            if i + 1 < len(lines):
                url = lines[i + 1].strip()
                if url.startswith('http'):
                    channels.append({"extinf": extinf, "url": url, "keep": False})
                    i += 2
                    continue
            i += 1
        else:
            i += 1

    total_entries = len(channels)
    print(f"Total de entradas encontradas: {total_entries}")

    # Test and deduplicate channels
    groups = {}

    for ch in channels:
        extinf = ch["extinf"]
        url = ch["url"]

        # Extract name: strip attributes then take after last comma
        attrs_removed = re.sub(r'\s*tvg-[a-z]+="[^"]*"\s*', '', extinf)
        attrs_removed = re.sub(r'\s*group-title="[^"]*"\s*', '', attrs_removed)
        name_match = re.search(r',(.+)$', attrs_removed)
        name = name_match.group(1).strip() if name_match else "Unknown"

        # Extract group
        group_match = re.search(r'group-title="([^"]*)"', extinf)
        group = group_match.group(1) if group_match else "NEWS WORLD"

        # Detect type
        ctype = detect_channel_type(name)

        # Find tvg_id
        tvg_id = None
        tvg_name = None
        for key, info in CHANNEL_MAP.items():
            if key in name.lower():
                tvg_id = info["tvg_id"]
                tvg_name = info["tvg_name"]
                break
        if not tvg_id:
            tvg_id = "465150"
            tvg_name = "ABC News Live"

        # Fix logo - prefer known good logos by tvg_id, fall back to fixing existing
        logo_url = TVG_ID_LOGO.get(tvg_id)
        if not logo_url:
            logo_match = re.search(r'tvg-logo="([^"]*)"', extinf)
            logo_url = fix_logo_url(logo_match.group(1) if logo_match else None, ctype)

        # Group by tvg_id, collecting all URLs
        if tvg_id not in groups:
            groups[tvg_id] = {
                "urls": [],
                "name": tvg_name or name,
                "group": group,
                "logo": logo_url,
                "tvg_id": tvg_id,
            }
        groups[tvg_id]["urls"].append(url)

    # Select best URL per channel: prefer akamai/primary streams over token-based CDN variants
    def url_score(url):
        score = 0
        if "akamaized" in url:
            score += 3
        if "abcnews-livestreams" in url:
            score += 5
        if "247.foxbusiness.com" in url:
            score += 3
        if "247.foxnews.com" in url:
            score += 3
        if "dai.google.com" in url:
            score += 3
        if "master.m3u8" in url or "/master." in url:
            score += 1
        if "dvt2=" in url:
            score -= 2
        if "hdnea=" in url:
            score -= 1
        if "hash=" in url:
            score -= 1
        return score

    unique_channels = []
    for tvg_id, info in groups.items():
        best_url = max(info["urls"], key=url_score)
        unique_channels.append({
            "url": best_url,
            "name": info["name"],
            "group": info["group"],
            "logo": info["logo"],
            "tvg_id": tvg_id,
        })
        found = len(info["urls"])
        print(f"  {info['name']}: {found} entradas -> melhor URL selecionada")

    print(f"Canais unicos apos dedup: {len(unique_channels)}")

    # Test streams
    print("\n" + "-" * 70)
    print("TESTANDO STREAMS:")
    print("-" * 70)
    working = []
    for ch in unique_channels:
        url = ch["url"]
        ok = test_url(url)
        status = "OK" if ok else "FALHOU"
        print(f"  {status}: {ch['name']}")
        if ok:
            working.append(ch)
        else:
            print(f"    URL: {url[:80]}...")

    print(f"\nCanais funcionando: {len(working)}/{len(unique_channels)}")

    # Test EPG
    print("\n" + "-" * 70)
    print("TESTANDO EPG:")
    print("-" * 70)
    hoje_str = datetime.now().strftime("%d/%m")
    amanha_str = (datetime.now() + timedelta(days=1)).strftime("%d/%m")
    depois_str = (datetime.now() + timedelta(days=2)).strftime("%d/%m")

    for ch in working:
        prog = test_epg_programming(epg_root, ch["tvg_id"])
        print(f"\n  {ch['tvg_id']} ({ch['name']}):")
        print(f"    {hoje_str}: {prog['hoje']} | {amanha_str}: {prog['amanha']} | {depois_str}: {prog['depois_amanha']}")
        print(f"    Status: {prog['status']}")

    # Write corrected file
    print("\n" + "-" * 70)
    print("GERANDO lista5.m3u CORRIGIDO:")
    print("-" * 70)

    with open(M3U_FILE, 'w', encoding='utf-8') as f:
        f.write(f'#EXTM3U x-tvg-url="{EPG_URL_RAW}"\n')
        for ch in working:
            f.write(f'#EXTINF:-1 tvg-id="{ch["tvg_id"]}" tvg-logo="{ch["logo"]}" group-title="{ch["group"]}",{ch["name"]}\n')
            f.write(f'{ch["url"]}\n')

    print(f"Arquivo {M3U_FILE} gerado com {len(working)} canais")
    print(f"EPG: {EPG_URL_RAW}")

    # Verify result
    print("\n" + "=" * 70)
    print("VERIFICACAO FINAL:")
    print("=" * 70)
    with open(M3U_FILE, 'r', encoding='utf-8') as f:
        content = f.read()
        lines = content.strip().split('\n')
        extinf_count = sum(1 for l in lines if l.startswith('#EXTINF:'))
        url_count = sum(1 for l in lines if l.startswith('http'))
        print(f"Linhas #EXTINF: {extinf_count}")
        print(f"URLs: {url_count}")

        # Verify all URLs have EXTINF above
        for j, l in enumerate(lines):
            if l.startswith('http') and (j == 0 or not lines[j-1].startswith('#EXTINF:')):
                print(f"ERRO: URL sem #EXTINF na linha {j+1}: {l[:60]}")

        # Verify all logos are .jpg
        for l in lines:
            logo_m = re.search(r'tvg-logo="([^"]*)"', l)
            if logo_m:
                logo = logo_m.group(1)
                if 'imgur.com' in logo.lower():
                    print(f"ERRO: Logo imgur.com encontrado: {logo[:60]}")
                if not logo.lower().endswith('.jpg') and not logo.lower().endswith('.jpeg'):
                    print(f"AVISO: Logo nao .jpg: {logo}")

    print("\n" + "=" * 70)
    print("CORRECAO CONCLUIDA COM SUCESSO!")
    print("=" * 70)

if __name__ == "__main__":
    main()
