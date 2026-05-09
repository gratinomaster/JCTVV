#!/usr/bin/env python3
import requests
import gzip
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import re

EPG_SOURCE = "https://epg.pw/xmltv/epg_US.xml.gz"

CHANNEL_MAP = {
    "ABC News Live": {
        "tvg_id": "465150",
        "tvg_name": "ABC News Live",
        "logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
    },
    "Fox Business": {
        "tvg_id": "464766",
        "tvg_name": "Fox Business",
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/c9b2e2eb-7b87-435c-9510-eab2650ff944/8b584585-acf2-4c37-aa07-aaf2d077bb20/1280x720/match/676/380/image.jpg",
    },
    "Fox News": {
        "tvg_id": "465372",
        "tvg_name": "Fox News",
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/15de0523-3be4-4a9a-8159-7020114e7036/b6ff623a-26d6-4fd9-8bb8-0856adbf38ce/1280x720/match/676/380/image.jpg",
    },
    "CBS News": {
        "tvg_id": "464941",
        "tvg_name": "CBS News",
        "logo": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
    },
}

def detect_channel(name):
    n = name.lower()
    if 'abc' in n:
        return "ABC News Live"
    if 'fox business' in n:
        return "Fox Business"
    if 'fox news' in n or 'fox' in n:
        return "Fox News"
    if 'cbs' in n:
        return "CBS News"
    return None

def fix_logo(url):
    if not url:
        return None
    if 'imgur.com' in url.lower():
        return None
    if '.jpg' in url.lower() or '.jpeg' in url.lower():
        return url
    return None

def test_epg_source():
    print("\n=== Testando EPG ===")
    try:
        resp = requests.get(EPG_SOURCE, timeout=60, headers={'User-Agent': 'Mozilla/5.0'})
        xml = gzip.decompress(resp.content).decode('utf-8')
        root = ET.fromstring(xml)

        hoje = datetime.now().strftime("%Y%m%d")
        amanha = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
        depois = (datetime.now() + timedelta(days=2)).strftime("%Y%m%d")

        canais_ok = {}
        for ch_name, cfg in CHANNEL_MAP.items():
            tid = cfg['tvg_id']
            ct = chn = 0
            for p in root.findall('programme'):
                if p.get('channel') == tid:
                    s = p.get('start', '')[:8]
                    if s == hoje: ct += 1
                    elif s == amanha: ct += 1
                    elif s == depois: ct += 1
                    chn += 1
            canais_ok[ch_name] = {"total": chn, "prox_3dias": ct}
            status = "OK" if ct > 0 else "SEM PROGRAMAÇÃO"
            print(f"  {ch_name} (ID {tid}): {ct} programas nos proximos 3 dias - {status}")

        return root, canais_ok
    except Exception as e:
        print(f"  ERRO: {e}")
        return None, {}

def test_stream(url):
    try:
        base = url.split('?')[0] if '?' in url else url
        resp = requests.head(base, timeout=10, allow_redirects=True, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        if resp.status_code == 200:
            return True, 200
        if resp.status_code in [403, 405, 401]:
            return True, resp.status_code
        return False, resp.status_code
    except Exception as e:
        return False, str(e)

def main():
    print("="*60)
    print("CORREÇÃO lista5.m3u")
    print("="*60)

    epg_xml, canais_epg = test_epg_source()

    with open('lista5.m3u', 'r', encoding='utf-8') as f:
        lines = f.readlines()

    output = []
    output.append('#EXTM3U x-tvg-url="https://epg.pw/xmltv/epg_US.xml.gz"')

    channels_found = 0
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line or line.startswith('#EXTM3U'):
            i += 1
            continue
        if line.startswith('#EXTINF:'):
            extinf = line
            if i + 1 < len(lines):
                url = lines[i + 1].strip()
            else:
                i += 1
                continue

            name_raw = extinf.split(',')[-1].strip() if ',' in extinf else "Unknown"
            detected = detect_channel(name_raw)
            group = "NEWS WORLD"

            if detected and detected in CHANNEL_MAP:
                cfg = CHANNEL_MAP[detected]
                tvg_id = cfg['tvg_id']
                tvg_name = cfg['tvg_name']
                logo = cfg['logo']

                print(f"\nProcessando: {name_raw}")
                print(f"  -> Canal: {tvg_name} (tvg-id: {tvg_id})")

                logo_ok, logo_status = test_stream(logo)
                print(f"  -> Logo: {'OK' if logo_ok else 'FALHOU'} ({logo_status})")

                stream_ok, stream_status = test_stream(url)
                print(f"  -> Stream: {'OK' if stream_ok else 'FALHOU'} ({stream_status})")

                extinf_clean = f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-logo="{logo}" group-title="{group}",{tvg_name}'
                output.append(extinf_clean)
                output.append(url)
                channels_found += 1
            else:
                stream_ok, stream_status = test_stream(url)
                print(f"\nProcessando: {name_raw}")
                print(f"  -> Stream: {'OK' if stream_ok else 'FALHOU'} ({stream_status})")
                logo_match = re.search(r'tvg-logo="([^"]*)"', extinf)
                logo = fix_logo(logo_match.group(1) if logo_match else None)
                if not logo:
                    logo = "https://keyframe-cdn.abcnews.com/streamprovider11.jpg"
                tvg_id_match = re.search(r'tvg-id="([^"]*)"', extinf)
                tvg_id_attr = f'tvg-id="{tvg_id_match.group(1)}" ' if tvg_id_match else ''
                extinf_clean = f'#EXTINF:-1 {tvg_id_attr}tvg-logo="{logo}" group-title="{group}",{name_raw}'
                output.append(extinf_clean)
                output.append(url)
                channels_found += 1

            i += 2
        else:
            i += 1

    with open('lista5.m3u', 'w', encoding='utf-8') as f:
        f.write('\n'.join(output) + '\n')

    print(f"\n=== RESUMO ===")
    print(f"Canais processados: {channels_found}")
    print(f"Arquivo lista5.m3u atualizado")
    print(f"EPG URL: https://epg.pw/xmltv/epg_US.xml.gz")

    if epg_xml:
        print(f"\n=== VERIFICAÇÃO EPG ===")
        hoje = datetime.now().strftime("%Y%m%d")
        amanha = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
        depois = (datetime.now() + timedelta(days=2)).strftime("%Y%m%d")
        print(f"HOJE: {hoje}")
        print(f"AMANHÃ: {amanha}")
        print(f"DEPOIS: {depois}")

        for ch_name, info in canais_epg.items():
            prog_hoje = sum(1 for p in epg_xml.findall('programme')
                          if p.get('channel') == CHANNEL_MAP[ch_name]['tvg_id']
                          and p.get('start', '')[:8] == hoje)
            prog_amanha = sum(1 for p in epg_xml.findall('programme')
                            if p.get('channel') == CHANNEL_MAP[ch_name]['tvg_id']
                            and p.get('start', '')[:8] == amanha)
            prog_depois = sum(1 for p in epg_xml.findall('programme')
                            if p.get('channel') == CHANNEL_MAP[ch_name]['tvg_id']
                            and p.get('start', '')[:8] == depois)
            print(f"  {ch_name}:")
            print(f"    Hoje: {prog_hoje} programas")
            print(f"    Amanhã: {prog_amanha} programas")
            print(f"    Depois: {prog_depois} programas")
            if prog_hoje > 0 and prog_amanha > 0:
                print(f"    ✓ EPG OK")
            else:
                print(f"    ✗ EPG INSUFICIENTE")

    print("\n✓ Processo concluído")

if __name__ == "__main__":
    main()
