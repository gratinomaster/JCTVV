#!/usr/bin/env python3
import re
import requests
import gzip
from datetime import datetime, timedelta

M3U_FILE = "lista5.m3u"
OUTPUT_FILE = "lista5_fixed.m3u"

EPG_URL = "https://raw.githubusercontent.com/gratinomaster/JCTV/main/lista5_epg.xml.gz"

CHANNEL_TVG_IDS = [
    ("abc news live", "ABCNewsLive.us"),
    ("abcnl", "ABCNewsLive.us"),
    ("abc news", "ABCNewsLive.us"),
    ("fox business", "FoxBusiness.us"),
    ("fox news", "FoxNewsChannel.us"),
    ("cbs news", "CBSNews.us"),
    ("cbs 24/7", "CBSNews.us"),
]

SAFE_LOGOS = {
    "abc news": "https://keyframe-cdn.abcnews.com/streamprovider5.jpg",
    "fox news": "https://a57.foxnews.com/static/694940094001/a6a5c792-7fc5-4cbd-a17f-5c17b855647d/d5bbc9d6-134a-4eb2-a923-931842d1e2dd/1280x720/match/400/225/image.jpg",
    "fox business": "https://a57.foxnews.com/static/694940094001/a6a5c792-7fc5-4cbd-a17f-5c17b855647d/d5bbc9d6-134a-4eb2-a923-931842d1e2dd/1280x720/match/400/225/image.jpg",
    "cbs news": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
}

def get_tvg_id(channel_name):
    name_lower = channel_name.lower().strip()
    for key, tvg_id in CHANNEL_TVG_IDS:
        if key in name_lower:
            return tvg_id
    return None

def get_safe_logo(channel_name, current_logo):
    if current_logo and "imgur.com" in current_logo.lower():
        return None
    if current_logo and current_logo.lower().endswith('.jpg'):
        return current_logo
    name_lower = channel_name.lower().strip()
    for key, logo in SAFE_LOGOS.items():
        if key in name_lower:
            return logo
    return None

def test_stream(url, timeout=10):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36', 'Accept': '*/*'}
        response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        if response.status_code == 200:
            return True, "OK"
        elif response.status_code in [301, 302, 303, 307, 308]:
            return True, f"Redirect ({response.status_code})"
        else:
            return False, f"HTTP {response.status_code}"
    except requests.exceptions.Timeout:
        return False, "Timeout"
    except requests.exceptions.ConnectionError:
        return False, "Connection Error"
    except Exception as e:
        return False, str(e)[:60]

def test_epg():
    print("Verificando EPG...")
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(EPG_URL, headers=headers, timeout=30)
        if resp.status_code != 200:
            print(f"  EPG URL: FALHOU (HTTP {resp.status_code})")
            try:
                with gzip.open("lista5_epg.xml.gz", 'rt', encoding='utf-8') as f:
                    data = f.read()
                print(f"  EPG local: OK ({len(data)} bytes)")
            except:
                print(f"  EPG local: NAO ENCONTRADO")
                return False
        else:
            try:
                data = gzip.decompress(resp.content).decode('utf-8')
                print(f"  EPG URL: OK ({len(data)} bytes)")
            except:
                data = resp.text
                print(f"  EPG URL: OK ({len(data)} bytes, raw)")

        today = datetime.now()
        for offset, label in [(0, "Hoje"), (1, "Amanha"), (2, "Depois de amanha")]:
            d = today + timedelta(days=offset)
            ds = d.strftime('%Y%m%d')
            count = data.count(f'start="{ds}')
            print(f"  {label} ({ds}): {count} programas")

        channels = re.findall(r'channel id="([^"]+)"', data)
        print(f"  Canais no EPG: {channels}")

        if channels:
            print("  EPG VALIDO - OK")
            return True
        print("  EPG SEM CANAIS - FALHOU")
        return False
    except Exception as e:
        print(f"  EPG: ERRO - {e}")
        return False

def parse_m3u(filepath):
    channels = []
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.read().split('\n')
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXTINF:'):
            extinf = line
            i += 1
            while i < len(lines):
                n = lines[i].strip()
                if n and not n.startswith('#'):
                    channels.append({'extinf': extinf, 'url': n})
                    break
                elif n.startswith('#EXTINF:'):
                    break
                i += 1
        i += 1
    return channels

def get_channel_name(extinf):
    m = re.search(r',(.+)$', extinf)
    return m.group(1).strip() if m else "Unknown"

def get_group_title(extinf):
    m = re.search(r'group-title="([^"]*)"', extinf)
    return m.group(1) if m else ""

def quality_score(url):
    score = 0
    if 'master.m3u8' in url: score += 5
    if 'primary_2692' in url: score += 4
    if 'primary_792' in url: score += 1
    if '2400K' in url or '2249' in url: score += 3
    if '1700K' in url or '1549' in url: score += 2
    if '4231' in url: score += 4
    if '_hdri_' in url: score += 2
    return score

def main():
    print("=" * 70)
    print("CORRECAO COMPLETA - lista5.m3u")
    print("=" * 70)

    print("\n[1/5] Testando EPG...")
    epg_ok = test_epg()
    if not epg_ok:
        print("  AVISO: Continuando sem EPG valido...")

    print(f"\n[2/5] Carregando {M3U_FILE}...")
    channels = parse_m3u(M3U_FILE)
    print(f"  Total de entradas: {len(channels)}")

    unique = {}
    for ch in channels:
        name = get_channel_name(ch['extinf'])
        if name not in unique or quality_score(ch['url']) > quality_score(unique[name]['url']):
            unique[name] = ch

    print(f"  Canais unicos: {len(unique)}")

    print(f"\n[3/5] Testando streams...")
    working = {}
    dead = []
    for i, (name, ch) in enumerate(unique.items(), 1):
        print(f"  [{i}/{len(unique)}] {name[:50]}...", end=" ", flush=True)
        ok, status = test_stream(ch['url'])
        if ok:
            print(f"OK ({status})")
            working[name] = ch
        else:
            print(f"FALHOU ({status})")
            dead.append((name, status))

    print(f"\n[4/5] Gerando {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(f'#EXTM3U x-tvg-url="{EPG_URL}"\n')
        for name, ch in working.items():
            extinf = ch['extinf']
            logo_m = re.search(r'tvg-logo="([^"]*)"', extinf)
            current_logo = logo_m.group(1) if logo_m else None
            tvg_id = get_tvg_id(name)
            safe_logo = get_safe_logo(name, current_logo)
            group_title = get_group_title(extinf)
            line = '#EXTINF:-1'
            if tvg_id:
                line += f' tvg-id="{tvg_id}"'
            if safe_logo:
                line += f' tvg-logo="{safe_logo}"'
            if group_title:
                line += f' group-title="{group_title}"'
            line += f',{name}'
            f.write(line + '\n')
            f.write(ch['url'] + '\n')

    print(f"\n[5/5] RESUMO FINAL")
    print("=" * 70)
    print(f"EPG: {EPG_URL}")
    print(f"Canais mantidos: {len(working)}")
    print(f"Canais removidos (streams mortos): {len(dead)}")
    print(f"Arquivo gerado: {OUTPUT_FILE}")
    if dead:
        print(f"\nCanais removidos:")
        for name, s in dead:
            print(f"  - {name[:50]}: {s}")
    print(f"\nCanais no arquivo:")
    for name in working:
        tid = get_tvg_id(name)
        print(f"  - {name} (tvg-id: {tid or 'NENHUM'})")

if __name__ == "__main__":
    main()
