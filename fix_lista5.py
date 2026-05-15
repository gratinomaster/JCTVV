#!/usr/bin/env python3
import re
import requests
import gzip
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from collections import OrderedDict

M3U_PATH = "/home/runner/work/JCTV/JCTV/lista5.m3u"
EPG_URL = "https://iptv-epg.org/files/epg-us.xml.gz"

CHANNEL_MAP = OrderedDict([
    ("ABC News Live", {
        "tvg_id": "ABCWBMA.us",
        "logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
        "group": "NEWS WORLD",
        "detect": lambda n, u: ('abc news live' in n or 'abc news' in n) and 'abcnl' not in n and 'watch live' not in n,
    }),
    ("ABC News Live - Prime", {
        "tvg_id": "ABCWBMA.us",
        "logo": "https://keyframe-cdn.abcnews.com/streamprovider10.jpg",
        "group": "NEWS WORLD",
        "detect": lambda n, u: ('watch live news on abcnl' in n or 'abcnl' in n or 'multi-day' in n or 'marine' in n or 'heat wave' in n or 'tracking' in n),
    }),
    ("Fox News", {
        "tvg_id": "FoxNewsChannel.us",
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/15de0523-3be4-4a9a-8159-7020114e7036/b6ff623a-26d6-4fd9-8bb8-0856adbf38ce/1280x720/match/676/380/image.jpg",
        "group": "NEWS WORLD",
        "detect": lambda n, u: ('fox news' in n and 'business' not in n.lower()),
    }),
    ("Fox Business", {
        "tvg_id": "FoxBusiness.us",
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/c9b2e2eb-7b87-435c-9510-eab2650ff944/8b584585-acf2-4c37-aa07-aaf2d077bb20/1280x720/match/676/380/image.jpg",
        "group": "NEWS WORLD",
        "detect": lambda n, u: 'fox business' in n or ('fox' in n and 'business' in n.lower()),
    }),
    ("CBS News 24/7", {
        "tvg_id": "CBSWCBS.us",
        "logo": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
        "group": "NEWS WORLD",
        "detect": lambda n, u: 'cbs' in n,
    }),
])

def detect_channel(name, url):
    nl = name.lower()
    for canonical, cfg in CHANNEL_MAP.items():
        if cfg["detect"](nl, url.lower()):
            return canonical, cfg
    return None, None

def fix_logo(url):
    if not url:
        return None
    if 'imgur.com' in url.lower():
        return None
    url = url.split('?')[0]
    if url.lower().endswith(('.jpg', '.jpeg')):
        return url
    if '.jpg' in url.lower() or '.jpeg' in url.lower():
        return url
    if '.png' in url.lower():
        return url.rsplit('.', 1)[0] + '.jpg'
    return url

def is_master_url(url):
    u = url.lower()
    if '/master.m3u8' in u:
        return True
    if '/ctr-all-hdri-sliding.m3u8' in u:
        return True
    if '/index.m3u8' in u and 'index_' not in u.split('/')[-1]:
        return True
    return False

def is_variant_url(url):
    u = url.lower()
    if '/bandwidth/' in u:
        return True
    if 'index_' in u.split('/')[-1]:
        return True
    if '/64_slide.m3u8' in u or '/128_slide.m3u8' in u or '/1700_' in u or '/2400_' in u:
        return True
    return False

def test_stream(url, timeout=15):
    try:
        resp = requests.get(url, timeout=timeout, allow_redirects=True, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        if resp.status_code < 400 and len(resp.content) > 50:
            return True
        return False
    except:
        return False

def download_epg(url):
    try:
        print(f"  Downloading EPG: {url[:70]}...")
        resp = requests.get(url, timeout=120, headers={
            'User-Agent': 'Mozilla/5.0', 'Accept-Encoding': 'gzip'
        })
        if resp.status_code != 200:
            return None
        content = resp.content
        if url.endswith('.gz'):
            content = gzip.decompress(content)
        if isinstance(content, bytes):
            content = content.decode('utf-8', errors='replace')
        root = ET.fromstring(content)
        progs = root.findall('programme')
        print(f"    {len(progs)} programmes found")
        return root, progs
    except Exception as e:
        print(f"    Error: {e}")
        return None

def test_epg_programming(progs, tvg_id):
    today = datetime.now().strftime("%Y%m%d")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
    day_after = (datetime.now() + timedelta(days=2)).strftime("%Y%m%d")
    c_today = c_tomorrow = c_day_after = 0
    for p in progs:
        ch = p.get('channel', '')
        if ch == tvg_id:
            s = p.get('start', '')[:8]
            if s == today: c_today += 1
            elif s == tomorrow: c_tomorrow += 1
            elif s == day_after: c_day_after += 1
    return c_today, c_tomorrow, c_day_after

def main():
    print("=" * 70)
    print("CORREÇÃO COMPLETA lista5.m3u")
    print("=" * 70)
    print(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    # Step 1: Read m3u
    print("=" * 70)
    print("1. LENDO lista5.m3u")
    print("=" * 70)
    with open(M3U_PATH, 'r', encoding='utf-8') as f:
        content = f.read()
    lines = content.split('\n')

    raw_entries = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXTM3U'):
            i += 1
            continue
        if line.startswith('#EXTINF:'):
            extinf = line
            if i + 1 < len(lines) and lines[i+1].strip() and not lines[i+1].strip().startswith('#'):
                url = lines[i+1].strip()
                name_m = re.search(r',(.+)$', extinf)
                name = name_m.group(1).strip() if name_m else ""
                raw_entries.append({'extinf': extinf, 'url': url, 'name': name})
                i += 2
            else:
                i += 1
        else:
            i += 1
    print(f"  EXTINF entries found: {len(raw_entries)}")

    # Step 2: Test EPG
    print("\n" + "=" * 70)
    print("2. TESTANDO EPG")
    print("=" * 70)
    epg_result = download_epg(EPG_URL)
    if not epg_result:
        print("  ERRO: EPG unavailable!")
        return
    _, epg_progs = epg_result

    print("\n  EPG program count by channel:")
    for canonical, cfg in CHANNEL_MAP.items():
        c_today, c_tomorrow, c_day_after = test_epg_programming(epg_progs, cfg["tvg_id"])
        status = "✓" if (c_today > 0 and c_tomorrow > 0 and c_day_after > 0) else "⚠" if (c_today > 0 and c_tomorrow > 0) else "✗"
        print(f"  {status} {canonical:25s} tvg-id={cfg['tvg_id']:25s} hoje={c_today:2d}  amanhã={c_tomorrow:2d}  depois={c_day_after:2d}")

    # Step 3: Classify entries into channel groups
    print("\n" + "=" * 70)
    print("3. CLASSIFICANDO ENTRADAS")
    print("=" * 70)

    channel_groups = {}
    for entry in raw_entries:
        canonical, cfg = detect_channel(entry['name'], entry['url'])
        if not canonical:
            print(f"  ? Unclassified: {entry['name'][:60]}")
            continue
        if canonical not in channel_groups:
            channel_groups[canonical] = {'cfg': cfg, 'entries': []}
        channel_groups[canonical]['entries'].append(entry)

    for canonical, data in channel_groups.items():
        print(f"  {canonical:25s}: {len(data['entries'])} entries")

    # Step 4: Select best URL per channel, test streams
    print("\n" + "=" * 70)
    print("4. SELECIONANDO MELHOR URL POR CANAL")
    print("=" * 70)

    selected = []
    for canonical, data in channel_groups.items():
        cfg = data['cfg']
        entries = data['entries']

        masters = [e for e in entries if is_master_url(e['url'])]
        non_variants = [e for e in entries if not is_variant_url(e['url'])]
        all_sorted = masters + non_variants + entries

        best_url = None
        for candidate in all_sorted:
            if test_stream(candidate['url']):
                best_url = candidate['url']
                print(f"  ✓ {canonical:25s} -> {best_url[:70]}...")
                break

        if not best_url:
            print(f"  ✗ {canonical}: nenhuma URL funcional, usando primeira")
            best_url = entries[0]['url'] if entries else None
            if not best_url:
                continue

        logo = fix_logo(cfg["logo"])
        if not logo:
            logo = "https://keyframe-cdn.abcnews.com/streamprovider11.jpg"

        attrs = f'tvg-id="{cfg["tvg_id"]}" tvg-logo="{logo}" group-title="{cfg["group"]}" x-tvg-url="{EPG_URL}"'
        extinf = f'#EXTINF:-1 {attrs},{canonical}'

        selected.append({'extinf': extinf, 'url': best_url, 'name': canonical, 'tvg_id': cfg["tvg_id"]})

    # Step 5: Write m3u
    print("\n" + "=" * 70)
    print("5. GERANDO lista5.m3u")
    print("=" * 70)

    with open(M3U_PATH, 'w', encoding='utf-8') as f:
        f.write(f'#EXTM3U x-tvg-url="{EPG_URL}"\n')
        for ch in selected:
            f.write(ch['extinf'] + '\n')
            f.write(ch['url'] + '\n')

    print(f"  Saved: {M3U_PATH}")
    print(f"  EPG: {EPG_URL}")
    print(f"  Channels: {len(selected)}")

    # Step 6: Verify
    print("\n" + "=" * 70)
    print("6. VERIFICAÇÃO")
    print("=" * 70)

    print("\n  FINAL CHANNELS:")
    for ch in selected:
        print(f"    {ch['extinf']}")
        print(f"    {ch['url']}")
        print()

    print("\n  LOGO CHECK:")
    all_ok = True
    for ch in selected:
        m = re.search(r'tvg-logo="([^"]*)"', ch['extinf'])
        logo = m.group(1) if m else "NONE"
        is_jpg = logo.lower().endswith('.jpg') or logo.lower().endswith('.jpeg')
        is_imgur = 'imgur.com' in logo.lower()
        status = "✓" if (is_jpg and not is_imgur) else "✗"
        if not is_jpg or is_imgur:
            all_ok = False
        print(f"    {status} {ch['name']:25s} -> {logo[:70]}...")
    if all_ok:
        print(f"    ✓ Todas as logos em .jpg e sem imgur.com!")

    print("\n  EPG VALIDATION:")
    for ch in selected:
        c_today, c_tomorrow, c_day_after = test_epg_programming(epg_progs, ch['tvg_id'])
        status = "✓" if (c_today > 0 and c_tomorrow > 0 and c_day_after > 0) else "⚠" if (c_today > 0 and c_tomorrow > 0) else "✗"
        print(f"    {status} {ch['name']:25s} tvg-id={ch['tvg_id']:25s} hoje={c_today:2d}  amanhã={c_tomorrow:2d}  depois={c_day_after:2d}")

    print("\n  STRUCTURE CHECK:")
    for ch in selected:
        has_hash = ch['extinf'].startswith('#EXTINF:-1')
        has_tvg_id = bool(ch['tvg_id'])
        has_logo = 'tvg-logo=' in ch['extinf']
        has_epg = 'x-tvg-url=' in ch['extinf']
        print(f"    {'✓' if has_hash else '✗'} {'✓' if has_tvg_id else '✗'} {'✓' if has_logo else '✗'} {'✓' if has_epg else '✗'} {ch['name']}")

    print("\n" + "=" * 70)
    print("CONCLUÍDO!")
    print("=" * 70)

if __name__ == "__main__":
    main()
