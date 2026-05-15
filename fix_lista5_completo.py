#!/usr/bin/env python3
import re, requests, gzip, sys, os, base64
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

M3U_FILE = 'lista5.m3u'
EPG_GLOBAL = 'https://epg.pw/xmltv/epg.xml.gz'

CHANNEL_EPG_MAP = [
    ("abc news live", {
        "tvg-id": "408627", "tvg-name": "ABC News Live",
        "tvg-logo": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/united-states/abcnewslive-us.jpg"
    }),
    ("abc news", {
        "tvg-id": "408627", "tvg-name": "ABC News Live",
        "tvg-logo": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/united-states/abcnewslive-us.jpg"
    }),
    ("fox business", {
        "tvg-id": "408654", "tvg-name": "Fox Business",
        "tvg-logo": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/united-states/foxbusiness-us.jpg"
    }),
    ("watch fox news", {
        "tvg-id": "369713", "tvg-name": "Fox News Channel",
        "tvg-logo": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/united-states/foxnewschannel-us.jpg"
    }),
    ("fox news", {
        "tvg-id": "369713", "tvg-name": "Fox News Channel",
        "tvg-logo": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/united-states/foxnewschannel-us.jpg"
    }),
    ("cbs news 24/7", {
        "tvg-id": "464941", "tvg-name": "CBS News",
        "tvg-logo": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/united-states/cbsnewsnetwork-us.jpg"
    }),
    ("watch cbs news", {
        "tvg-id": "464941", "tvg-name": "CBS News",
        "tvg-logo": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/united-states/cbsnewsnetwork-us.jpg"
    }),
    ("cbs news", {
        "tvg-id": "464941", "tvg-name": "CBS News",
        "tvg-logo": "https://raw.githubusercontent.com/tv-logo/tv-logos/main/united-states/cbsnewsnetwork-us.jpg"
    }),
]

def extract_channel_name(extinf):
    m = re.search(r',(.+)$', extinf.strip())
    return m.group(1).strip() if m else ""

def parse_m3u(path):
    channels = []
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXTINF:'):
            url = lines[i+1].strip() if i+1 < len(lines) else ""
            name = extract_channel_name(line)
            tvg_id_m = re.search(r'tvg-id="([^"]*)"', line)
            tvg_logo_m = re.search(r'tvg-logo="([^"]*)"', line)
            group_m = re.search(r'group-title="([^"]*)"', line)
            channels.append({
                "extinf": line, "url": url, "name": name,
                "tvg_id": tvg_id_m.group(1) if tvg_id_m else "",
                "tvg_logo": tvg_logo_m.group(1) if tvg_logo_m else "",
                "group": group_m.group(1) if group_m else "",
            })
            i += 2
        else:
            i += 1
    return channels

def download_epg(url):
    try:
        print(f"  Baixando EPG: {url}")
        r = requests.get(url, timeout=180, headers={'Accept-Encoding': 'gzip'})
        r.raise_for_status()
        if url.endswith('.gz'):
            return gzip.decompress(r.content).decode('utf-8')
        return r.text
    except Exception as e:
        print(f"  ERRO: {e}")
        return None

def test_epg_programming(epg_content, tvg_id):
    result = {"today": 0, "tomorrow": 0, "day_after": 0, "programs": []}
    try:
        root = ET.fromstring(epg_content)
        hoje = datetime.now().strftime("%Y%m%d")
        amanha = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
        depois = (datetime.now() + timedelta(days=2)).strftime("%Y%m%d")
        for prog in root.findall("programme"):
            ch = prog.get("channel", "")
            if ch == tvg_id:
                start = prog.get("start", "")[:8]
                title_elem = prog.find("title")
                title = title_elem.text if title_elem is not None else "?"
                if start == hoje:
                    result["today"] += 1
                elif start == amanha:
                    result["tomorrow"] += 1
                elif start == depois:
                    result["day_after"] += 1
                if len(result["programs"]) < 6:
                    result["programs"].append((start, title))
    except:
        pass
    return result

def check_url(url):
    try:
        r = requests.head(url, timeout=10, allow_redirects=True,
                          headers={'User-Agent': 'Mozilla/5.0'})
        if r.status_code in (200, 301, 302, 307, 308, 405):
            return True
    except:
        pass
    try:
        r = requests.get(url, timeout=10, stream=True,
                         headers={'User-Agent': 'Mozilla/5.0'})
        return r.status_code in (200, 301, 302, 307, 308, 405, 403)
    except:
        return False

def find_epg_info(name):
    nl = name.lower()
    for key, info in CHANNEL_EPG_MAP:
        if key in nl:
            return dict(info)
    return None

def is_master_playlist(url):
    path = url.split('?')[0].lower()
    excludes = ['_slide.m3u8', '-index_', '/bandwidth/', '/64_', '/128_', '1700k', '2400k']
    for excl in excludes:
        if excl in path:
            return False
    return True

def main():
    print("=" * 70)
    print("CORRECAO COMPLETA DO lista5.m3u")
    print("=" * 70)

    backup = M3U_FILE + '.bak2'
    if not os.path.exists(backup):
        import shutil
        shutil.copy2(M3U_FILE, backup)
        print(f"Backup criado: {backup}")

    channels = parse_m3u(M3U_FILE)
    print(f"Linhas EXTINF encontradas: {len(channels)}")

    unique_names = set()
    for ch in channels:
        unique_names.add(ch["name"])
    print(f"Canais unicos: {len(unique_names)}")

    print("\n--- Baixando EPG ---")
    epg_content = download_epg(EPG_GLOBAL)
    if not epg_content:
        print("ERRO: Nao foi possivel baixar EPG!")
        return
    print(f"EPG baixado: {len(epg_content):,} bytes")

    print("\n--- Testando EPG para cada canal ---")
    epg_results = {}
    for name in sorted(unique_names):
        info = find_epg_info(name)
        if info:
            tvg_id = info["tvg-id"]
            prog = test_epg_programming(epg_content, tvg_id)
            epg_results[name] = {**info, "programming": prog}
            hoje = datetime.now().strftime("%d/%m")
            amanha = (datetime.now() + timedelta(days=1)).strftime("%d/%m")
            depois = (datetime.now() + timedelta(days=2)).strftime("%d/%m")
            status = "OK" if (prog["today"] > 0 and prog["tomorrow"] > 0) else "PARCIAL"
            print(f"  [{status}] {info['tvg-name']:30s} | {hoje}:{prog['today']:4d}  {amanha}:{prog['tomorrow']:4d}  {depois}:{prog['day_after']:4d}")
        else:
            epg_results[name] = {"tvg-id": "", "tvg-name": name, "tvg-logo": "", "programming": {"today": 0, "tomorrow": 0, "day_after": 0}}
            print(f"  [SEM EPG] {name:30s}")

    print("\n--- Verificando URLs ---")
    unique_urls = {}
    for ch in channels:
        if ch["url"] and ch["url"] not in unique_urls:
            unique_urls[ch["url"]] = ch["name"]

    working_urls = set()
    dead_urls = set()
    for url, name in unique_urls.items():
        ok = check_url(url)
        status = "OK" if ok else "FALHOU"
        short_name = name[:45]
        print(f"  [{status}] {short_name}")
        if ok:
            working_urls.add(url)
        else:
            dead_urls.add(url)

    print(f"\n  URLs funcionando: {len(working_urls)}")
    if dead_urls:
        print(f"  URLs falhando: {len(dead_urls)}")
        for url in dead_urls:
            print(f"    - {unique_urls[url][:50]}")

    print("\n--- Gerando lista5.m3u corrigida ---")
    output_lines = [f'#EXTM3U x-tvg-url="{EPG_GLOBAL}"']

    channels_by_name = {}
    for ch in channels:
        name = ch["name"]
        if name not in channels_by_name:
            channels_by_name[name] = []
        channels_by_name[name].append(ch)

    for name, ch_list in channels_by_name.items():
        info = find_epg_info(name)
        group = "NEWS WORLD"
        tvg_id = info["tvg-id"] if info else ""
        tvg_name = info["tvg-name"] if info else name
        tvg_logo = info["tvg-logo"] if (info and info.get("tvg-logo")) else ""

        added_one = False
        for ch in ch_list:
            url = ch["url"]
            if not url or not url.startswith('http'):
                continue
            if url in dead_urls:
                continue

            attrs = []
            if tvg_id:
                attrs.append(f'tvg-id="{tvg_id}"')
            if tvg_name:
                attrs.append(f'tvg-name="{tvg_name}"')
            if tvg_logo:
                attrs.append(f'tvg-logo="{tvg_logo}"')
            attrs.append(f'group-title="{group}"')

            extinf = f'#EXTINF:-1 {" ".join(attrs)},{name}'
            output_lines.append(extinf)
            output_lines.append(url)
            added_one = True
            break

        if not added_one and not dead_urls:
            print(f"  AVISO: Nenhuma URL funcional para {name}")

    print(f"\nCanais na lista final: {(len(output_lines)-1)//2}")

    with open(M3U_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(output_lines) + '\n')

    print(f"Arquivo {M3U_FILE} atualizado!")

    print("\n" + "=" * 70)
    print("RESUMO EPG")
    print("=" * 70)
    hoje_fmt = datetime.now().strftime("%d/%m/%Y")
    amanha_fmt = (datetime.now() + timedelta(days=1)).strftime("%d/%m/%Y")
    depois_fmt = (datetime.now() + timedelta(days=2)).strftime("%d/%m/%Y")
    for name in sorted(epg_results.keys()):
        r = epg_results[name]
        p = r["programming"]
        print(f"  {r['tvg-name']:30s} | {hoje_fmt}: {p['today']:4d} | {amanha_fmt}: {p['tomorrow']:4d} | {depois_fmt}: {p['day_after']:4d}")
        for s, t in p["programs"][:3]:
            print(f"    {s[6:8]}/{s[4:6]}/{s[:4]} {s[8:10]}:{s[10:12]} - {t}")

if __name__ == "__main__":
    main()
