#!/usr/bin/env python3
"""Corrige lista5.m3u: EPG, logos, streams, dedup"""
import requests
import gzip
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from collections import OrderedDict

M3U_PATH = "/home/runner/work/JCTV/JCTV/lista5.m3u"
M3U_BAK = "/home/runner/work/JCTV/JCTV/lista5.m3u.bak"

CHANNEL_MAP = OrderedDict([
    ("ABC News Live", {
        "tvg_id": "465150",
        "name_epg": "ABC News Live",
        "logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
        "group": "NEWS WORLD",
        "aliases": ["abc news", "abc news live", "abcnl"],
    }),
    ("Fox Business", {
        "tvg_id": "464766",
        "name_epg": "Fox Business",
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/519925b6-905d-47fa-bada-5e700a710dee/22ee56a5-9cee-46af-a739-c240172f2777/1280x720/match/1280/720/image.jpg",
        "group": "NEWS WORLD",
        "aliases": ["fox business", "fox business go"],
    }),
    ("Fox News Channel", {
        "tvg_id": "465372",
        "name_epg": "Fox News Channel",
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/15de0523-3be4-4a9a-8159-7020114e7036/b6ff623a-26d6-4fd9-8bb8-0856adbf38ce/1280x720/match/676/380/image.jpg",
        "group": "NEWS WORLD",
        "aliases": ["fox news", "fox news channel"],
    }),
    ("CBS News 24/7", {
        "tvg_id": "464941",
        "name_epg": "CBS News National Stream",
        "logo": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
        "group": "NEWS WORLD",
        "aliases": ["cbs news", "cbs news 24/7", "cbs"],
    }),
])

EPG_SOURCES = OrderedDict([
    ("epg_pw_us", "https://epg.pw/xmltv/epg_US.xml.gz"),
    ("iptv_org_us", "https://github.com/iptv-org/epg/raw/master/guide/us.xml.gz"),
    ("iptv_epg_us", "https://iptv-epg.org/files/epg-us.xml.gz"),
    ("local_lista5", "/home/runner/work/JCTV/JCTV/lista5_epg.xml.gz"),
])

def detect_channel_from_extinf(extinf):
    n = extinf.lower()
    for canonical, cfg in CHANNEL_MAP.items():
        for alias in cfg["aliases"]:
            if alias in n:
                return canonical, cfg
    if "abc" in n:
        return "ABC News Live", CHANNEL_MAP["ABC News Live"]
    if "fox business" in n:
        return "Fox Business", CHANNEL_MAP["Fox Business"]
    if "fox" in n:
        return "Fox News Channel", CHANNEL_MAP["Fox News Channel"]
    if "cbs" in n:
        return "CBS News 24/7", CHANNEL_MAP["CBS News 24/7"]
    return None, None

def fix_logo_url(url):
    if not url:
        return None
    if 'imgur.com' in url.lower():
        return None
    url_clean = url.split('?')[0]
    if '.jpg' in url_clean.lower() or '.jpeg' in url_clean.lower():
        return url_clean
    if '.png' in url_clean.lower():
        return url_clean.rsplit('.', 1)[0] + '.jpg'
    return url_clean if url_clean.lower().endswith(('.jpg', '.jpeg')) else None

def download_epg_source(source_key, url):
    try:
        print(f"  Baixando EPG: {source_key}...")
        if url.startswith('/'):
            with gzip.open(url, 'rb') as f:
                content = f.read()
            root = ET.fromstring(content)
        else:
            resp = requests.get(url, timeout=120, headers={'User-Agent': 'Mozilla/5.0', 'Accept-Encoding': 'gzip'})
            resp.raise_for_status()
            if url.endswith('.gz'):
                content = gzip.decompress(resp.content)
            else:
                content = resp.content
            root = ET.fromstring(content)
        channels = root.findall('channel')
        progs = root.findall('programme')
        print(f"    -> {len(channels)} canais, {len(progs)} programas")
        return root, channels, progs
    except Exception as e:
        print(f"    -> ERRO: {e}")
        return None, [], []

def test_epg_programming(progs, tvg_id):
    hoje = datetime.now().strftime("%Y%m%d")
    amanha = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
    depois = (datetime.now() + timedelta(days=2)).strftime("%Y%m%d")
    c_hoje = c_amanha = c_depois = 0
    for p in progs:
        ch = p.get('channel', '')
        if ch == tvg_id:
            s = p.get('start', '')[:8]
            if s == hoje: c_hoje += 1
            elif s == amanha: c_amanha += 1
            elif s == depois: c_depois += 1
    return c_hoje, c_amanha, c_depois

def test_stream(url):
    try:
        resp = requests.head(url, timeout=15, allow_redirects=True, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        if resp.status_code in [200, 302, 301, 307, 308]:
            return True
        if resp.status_code in [403, 405, 401]:
            return True
        return False
    except Exception:
        return False

def main():
    print("=" * 70)
    print("CORREÇÃO COMPLETA lista5.m3u - EPG | LOGOS | STREAMS")
    print("=" * 70)
    print(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print()

    hoje = datetime.now().strftime("%Y%m%d")
    amanha = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
    depois = (datetime.now() + timedelta(days=2)).strftime("%Y%m%d")
    print(f"Programação necessária para: {hoje}, {amanha}, {depois}")
    print()

    # --- Step 1: Ler m3u ---
    print("=" * 70)
    print("1. LENDO ARQUIVO M3U")
    print("=" * 70)
    with open(M3U_PATH, 'r', encoding='utf-8') as f:
        raw_lines = f.readlines()
    print(f"  Linhas lidas: {len(raw_lines)}")

    channels_raw = []
    i = 0
    while i < len(raw_lines):
        line = raw_lines[i].strip()
        if line.startswith('#EXTM3U'):
            i += 1
            continue
        if line.startswith('#EXTINF:'):
            extinf = line
            if i + 1 < len(raw_lines):
                url = raw_lines[i + 1].strip()
            else:
                i += 1
                continue
            name_raw = extinf.split(',')[-1].strip() if ',' in extinf else "Unknown"
            logo_match = re.search(r'tvg-logo="([^"]*)"', extinf)
            logo = logo_match.group(1) if logo_match else None
            group_match = re.search(r'group-title="([^"]*)"', extinf)
            group = group_match.group(1) if group_match else ""
            channels_raw.append({
                "extinf": extinf, "url": url, "name": name_raw,
                "logo": logo, "group": group
            })
            i += 2
        else:
            i += 1

    print(f"  Entradas EXTINF encontradas: {len(channels_raw)}")

    # --- Step 2: Baixar EPGs e verificar ---
    print()
    print("=" * 70)
    print("2. BAIXANDO E TESTANDO EPGs")
    print("=" * 70)

    best_epg = None
    best_epg_name = None
    best_epg_progs = []
    best_channel_info = {}

    for src_key, src_url in EPG_SOURCES.items():
        print(f"\n[{src_key}]")
        root, chs, progs = download_epg_source(src_key, src_url)
        if root is None:
            continue

        print(f"  Testando canais de interesse:")
        all_ok = True
        channel_info = {}
        for canonical, cfg in CHANNEL_MAP.items():
            tid = cfg["tvg_id"]
            c_hoje, c_amanha, c_depois = test_epg_programming(progs, tid)
            dn = root.find(f'.//channel[@id="{tid}"]')
            ch_name = dn.find('display-name').text if dn is not None else tid
            channel_info[tid] = {
                "name": ch_name,
                "hoje": c_hoje, "amanha": c_amanha, "depois": c_depois,
            }
            ok = c_hoje > 0 and c_amanha > 0 and c_depois > 0
            status = "✓ OK" if ok else f"✗ (hoje={c_hoje}, amanhã={c_amanha}, depois={c_depois})"
            print(f"    {ch_name}: {status}")
            if not ok:
                all_ok = False

        if all_ok:
            best_epg = root
            best_epg_name = src_key
            best_epg_progs = progs
            best_channel_info = channel_info
            print(f"  → EPG '{src_key}' TEM programação completa! Usando este.")
            break
        else:
            if best_epg is None:
                best_epg = root
                best_epg_name = src_key
                best_epg_progs = progs
                best_channel_info = channel_info
                print(f"  → Usando '{src_key}' como fallback")

    if best_epg is None:
        print("\n  ERRO: Nenhum EPG disponível!")
        return

    epg_url_str = EPG_SOURCES[best_epg_name]
    print(f"\n  EPG escolhido: {best_epg_name} -> {epg_url_str}")
    print(f"  Programas no EPG: {len(best_epg_progs)}")

    # --- Step 3: Mapear canais e montar novas entradas ---
    print()
    print("=" * 70)
    print("3. MAPEANDO CANAIS E ADICIONANDO tvg-id + LOGOS")
    print("=" * 70)

    output_channels = []
    for ch in channels_raw:
        detected, cfg = detect_channel_from_extinf(ch["extinf"])
        tvg_id = ""
        tvg_name = ch["name"]
        logo_url = ""
        group_title = ch["group"] if ch["group"] else "NEWS WORLD"

        if detected and cfg:
            tvg_id = cfg["tvg_id"]
            tvg_name = cfg["name_epg"]
            logo_url = fix_logo_url(cfg["logo"])
            group_title = cfg["group"]

            tid_info = best_channel_info.get(tvg_id, {})
            print(f"  Canal: {ch['name'][:55]}")
            print(f"    → tvg-id={tvg_id} nome={tvg_name}")
            print(f"    → EPG: hoje={tid_info.get('hoje',0)} amanhã={tid_info.get('amanha',0)} depois={tid_info.get('depois',0)}")
            print(f"    → Logo: {'OK' if logo_url else 'FALHA'}")
        else:
            print(f"  Canal: {ch['name'][:55]}")
            print(f"    → Não mapeado, mantendo nome original")
            logo_url = fix_logo_url(ch["logo"])
            if not logo_url:
                logo_url = "https://keyframe-cdn.abcnews.com/streamprovider11.jpg"
            print(f"    → Logo: {'OK' if logo_url else 'FALHA'}")

        attrs = []
        if tvg_id:
            attrs.append(f'tvg-id="{tvg_id}"')
        if logo_url:
            attrs.append(f'tvg-logo="{logo_url}"')
        if group_title:
            attrs.append(f'group-title="{group_title}"')
        attrs_str = ' '.join(attrs)
        clean_extinf = f'#EXTINF:-1 {attrs_str},{tvg_name}'

        output_channels.append({
            "extinf": clean_extinf,
            "url": ch["url"],
            "name": tvg_name,
            "tvg_id": tvg_id,
        })

    # --- Step 4: Testar Streams ---
    print()
    print("=" * 70)
    print("4. TESTANDO STREAMS")
    print("=" * 70)

    working_channels = []
    failed = 0
    for ch in output_channels:
        works = test_stream(ch["url"])
        if works:
            working_channels.append(ch)
            print(f"  ✓ {ch['name'][:55]}")
        else:
            failed += 1
            print(f"  ✗ {ch['name'][:55]} - FALHOU")

    print(f"\n  OK: {len(working_channels)}  Removidos: {failed}")

    # --- Step 5: Deduplicar ---
    print()
    print("=" * 70)
    print("5. DEDUPLICANDO URLs REPETIDAS")
    print("=" * 70)
    seen_urls = set()
    final_channels = []
    for ch in working_channels:
        if ch["url"] not in seen_urls:
            seen_urls.add(ch["url"])
            final_channels.append(ch)
        else:
            print(f"  Removido duplicado: {ch['name'][:50]} ({ch['url'][:60]}...)")
    print(f"  Entradas finais: {len(final_channels)}")

    # --- Step 6: Escrever m3u final ---
    print()
    print("=" * 70)
    print("6. ESCREVENDO lista5.m3u")
    print("=" * 70)

    with open(M3U_PATH, 'w', encoding='utf-8') as f:
        f.write(f'#EXTM3U x-tvg-url="{epg_url_str}"\n')
        for ch in final_channels:
            f.write(ch["extinf"] + "\n")
            f.write(ch["url"] + "\n")

    print(f"  ✓ Arquivo: {M3U_PATH}")
    print(f"  ✓ EPG: {epg_url_str}")
    print(f"  ✓ Canais: {len(final_channels)}")

    # --- Step 7: Verificação ---
    print()
    print("=" * 70)
    print("7. VERIFICAÇÃO FINAL")
    print("=" * 70)

    with open(M3U_PATH, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    print(f"\n  Total de linhas: {len(lines)}")

    print(f"\n  CANAIS:")
    for ch in final_channels:
        print(f"    {ch['extinf'][:90]}")
        print(f"    -> {ch['url'][:80]}...")

    print(f"\n  EPG PROGRAMMING (HOJE/AMANHÃ/DEPOIS):")
    for canonical, cfg in CHANNEL_MAP.items():
        tid = cfg["tvg_id"]
        c_hoje, c_amanha, c_depois = test_epg_programming(best_epg_progs, tid)
        status = "✓" if (c_hoje > 0 and c_amanha > 0 and c_depois > 0) else "✗"
        print(f"    {status} {canonical} (tvg-id={tid}): hoje={c_hoje}, amanhã={c_amanha}, depois={c_depois}")

    print(f"\n  LOGOS:")
    for ch in final_channels:
        logo_match = re.search(r'tvg-logo="([^"]*)"', ch["extinf"])
        if logo_match:
            logo = logo_match.group(1)
            if 'imgur.com' in logo.lower():
                print(f"    ✗ IMGUR: {ch['name']} -> {logo}")
            elif not logo.lower().rstrip('.')[0:].endswith('.jpg'):
                print(f"    ✗ NÃO JPG: {ch['name']} -> {logo}")
            else:
                print(f"    ✓ {ch['name'][:50]}")

    errors = []
    for i, ch in enumerate(final_channels):
        if not ch["extinf"].startswith("#"):
            errors.append(f"  Linha {2*i+1}: falta # em EXTINF")
        if not ch["tvg_id"]:
            errors.append(f"  {ch['name']}: sem tvg-id")
        logo_check = re.search(r'tvg-logo="([^"]*)"', ch["extinf"])
        if not logo_check:
            errors.append(f"  {ch['name']}: sem tvg-logo")

    if errors:
        print(f"\n  AVISOS:")
        for e in errors:
            print(f"    ⚠ {e}")
    else:
        print(f"\n  ✓ TUDO OK - sem erros!")

    print()
    print("=" * 70)
    print("CORREÇÃO CONCLUÍDA!")
    print("=" * 70)

if __name__ == "__main__":
    main()
