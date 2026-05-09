#!/usr/bin/env python3
import re
import requests
import hashlib
import time
import gzip
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from urllib.parse import quote

CHANNEL_CONFIG = {
    "ABC News Live": {
        "epg_id": "465150",
        "logo": "https://keyframe-cdn.abcnews.com/streamprovider10.jpg",
        "group": "NEWS WORLD",
        "name": "ABC News Live"
    },
    "Marine Traffic": {
        "epg_id": "465150",
        "logo": "https://keyframe-cdn.abcnews.com/streamprovider5.jpg",
        "group": "NEWS WORLD",
        "name": "ABC News Live - Marine Traffic"
    },
    "Fox News": {
        "epg_id": "465372",
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/6d456354-76bb-420c-ad05-597a04616fdf/bacf2a09-caf7-427f-9485-ab2f93800dce/1280x720/match/390/219/image.jpg",
        "group": "NEWS WORLD",
        "name": "Fox News Channel"
    },
    "Fox Business": {
        "epg_id": "464766",
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/c9b2e2eb-7b87-435c-9510-eab2650ff944/8b584585-acf2-4c37-aa07-aaf2d077bb20/1280x720/match/676/380/image.jpg?ve=1&tl=1",
        "group": "NEWS WORLD",
        "name": "Fox Business Network"
    },
    "CBS News": {
        "epg_id": "464941",
        "logo": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
        "group": "NEWS WORLD",
        "name": "CBS News 24/7"
    }
}

def identify_channel(extinf, url):
    text = (extinf + " " + url).lower()
    if "fox business" in text or "fbn" in text:
        return "Fox Business"
    if "fox news" in text or "fnc" in text:
        return "Fox News"
    if "cbs news" in text or "cbsn" in text:
        return "CBS News"
    if "marine" in text or "traffic" in text or "strait" in text:
        return "Marine Traffic"
    if "abc news" in text or "abc" in text or "abcn" in text or "abcnl" in text:
        return "ABC News Live"
    return None

def check_virustotal(url):
    try:
        vt_url = "https://www.virustotal.com/api/v3/urls"
        headers = {"Accept": "application/json"}
        data = {"url": url}
        resp = requests.post(vt_url, headers=headers, data=data, timeout=30)
        if resp.status_code == 200:
            analysis_id = resp.json().get("data", {}).get("id", "")
            if analysis_id:
                time.sleep(15)
                analysis_url = f"https://www.virustotal.com/api/v3/analyses/{analysis_id}"
                ar = requests.get(analysis_url, headers=headers, timeout=30)
                if ar.status_code == 200:
                    stats = ar.json().get("data", {}).get("attributes", {}).get("stats", {})
                    return stats.get("malicious", 0), stats.get("suspicious", 0)
    except Exception as e:
        print(f"    VT Error: {e}")
    return None, None

def test_stream(url):
    try:
        resp = requests.get(url, timeout=15, allow_redirects=True,
                          headers={'User-Agent': 'Mozilla/5.0'})
        if resp.status_code == 200:
            return True, resp.status_code
        return False, resp.status_code
    except Exception as e:
        return False, str(e)[:40]

def test_logo(url):
    try:
        resp = requests.head(url, timeout=10, allow_redirects=True,
                           headers={'User-Agent': 'Mozilla/5.0'})
        if resp.status_code == 200:
            ct = resp.headers.get("content-type", "")
            if "image" in ct:
                return True, ct
            return False, f"Not image: {ct}"
        return False, f"HTTP {resp.status_code}"
    except Exception as e:
        return False, str(e)[:40]

def parse_m3u(filepath):
    channels = []
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTINF:"):
            extinf = line
            i += 1
            while i < len(lines):
                url = lines[i].strip()
                if url and not url.startswith("#"):
                    channels.append({"extinf": extinf, "url": url})
                    break
                i += 1
        i += 1
    return channels

def select_best_url(urls):
    if not urls:
        return None
    if len(urls) == 1:
        return urls[0]
    preferred = [u for u in urls if "master.m3u8" in u]
    if preferred:
        return preferred[0]
    non_audio = [u for u in urls if "audio" not in u.lower()]
    if non_audio:
        return non_audio[0]
    return urls[0]

def main():
    print("=" * 70)
    print("CORRECAO COMPLETA DO lista5.m3u")
    print("=" * 70)

    EPG_URL = "https://epg.pw/xmltv/epg_US.xml.gz"

    channels = parse_m3u("lista5.m3u")
    print(f"\nTotal EXTINF entries found: {len(channels)}")

    grouped = {}
    for ch in channels:
        key = identify_channel(ch["extinf"], ch["url"])
        if key:
            if key not in grouped:
                grouped[key] = {"extinf": ch["extinf"], "urls": []}
            grouped[key]["urls"].append(ch["url"])

    print(f"Unique channels identified: {list(grouped.keys())}")

    print("\n" + "-" * 70)
    print("VERIFICACAO DE STREAMS")
    print("-" * 70)
    valid_channels = {}
    for key, data in grouped.items():
        best_url = select_best_url(data["urls"])
        if not best_url:
            print(f"  {key}: No valid URL found - SKIPPED")
            continue
        print(f"  Testing {key}...", end=" ")
        works, status = test_stream(best_url)
        if works:
            print(f"OK (HTTP {status})")
            valid_channels[key] = best_url
        else:
            print(f"FAILED ({status}) - trying alternatives")
            alt_found = False
            for alt_url in data["urls"]:
                if alt_url != best_url:
                    w2, s2 = test_stream(alt_url)
                    if w2:
                        print(f"    Alternative works: {alt_url[:80]}...")
                        valid_channels[key] = alt_url
                        alt_found = True
                        break
            if not alt_found:
                print(f"    No working URL found - SKIPPED")

    print("\n" + "-" * 70)
    print("VERIFICACAO DE LOGOS")
    print("-" * 70)
    logo_status = {}
    for key in valid_channels:
        cfg = CHANNEL_CONFIG.get(key)
        if cfg and cfg["logo"]:
            print(f"  Testing logo for {key}...", end=" ")
            works, info = test_logo(cfg["logo"])
            if works:
                print(f"OK ({info})")
                logo_status[key] = True
            else:
                print(f"FAILED ({info})")
                logo_status[key] = False

    print("\n" + "-" * 70)
    print("VERIFICACAO VIRUSTOTAL")
    print("-" * 70)
    vt_results = {}
    for key, url in valid_channels.items():
        print(f"  Checking VirusTotal for {key}...")
        malicious, suspicious = check_virustotal(url)
        if malicious is None:
            print(f"    VT: No API key or error - mantido")
            vt_results[key] = True
        elif malicious > 0 or suspicious > 0:
            print(f"    VT: MALICIOUS({malicious})/SUSPICIOUS({suspicious}) - REMOVIDO")
            vt_results[key] = False
        else:
            print(f"    VT: CLEAN")
            vt_results[key] = True
        time.sleep(2)

    print("\n" + "-" * 70)
    print("VERIFICACAO DO EPG")
    print("-" * 70)
    try:
        print(f"  Downloading EPG: {EPG_URL}")
        resp = requests.get(EPG_URL, timeout=120, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code == 200:
            xml_data = gzip.decompress(resp.content)
            root = ET.fromstring(xml_data)

            today = datetime.now().strftime("%Y%m%d")
            tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
            dayafter = (datetime.now() + timedelta(days=2)).strftime("%Y%m%d")

            for key in list(valid_channels.keys()):
                cfg = CHANNEL_CONFIG.get(key)
                if not cfg:
                    continue
                epg_id = cfg["epg_id"]
                progs = [p for p in root.findall("programme") if p.get("channel") == epg_id]
                hoje = sum(1 for p in progs if p.get("start", "")[:8] == today)
                amanha = sum(1 for p in progs if p.get("start", "")[:8] == tomorrow)
                depois = sum(1 for p in progs if p.get("start", "")[:8] == dayafter)
                print(f"  {key} (ID {epg_id}): Hoje={hoje}, Amanha={amanha}, Depois={depois}")
                if hoje == 0 and amanha == 0:
                    print(f"    WARNING: No EPG data for {key}!")
                else:
                    print(f"    OK - EPG funcionando")
        else:
            print(f"  EPG download failed: HTTP {resp.status_code}")
    except Exception as e:
        print(f"  EPG check error: {e}")

    print("\n" + "-" * 70)
    print("GERANDO LISTA CORRIGIDA")
    print("-" * 70)

    epg_urls = [EPG_URL]
    lines = ['#EXTM3U x-tvg-url="' + ",".join(epg_urls) + '"']
    lines.append('')

    for key, url in valid_channels.items():
        if not vt_results.get(key, True):
            print(f"  Removido (VT): {key}")
            continue

        cfg = CHANNEL_CONFIG.get(key)
        if not cfg:
            print(f"  Sem config: {key}")
            continue

        extinf = f'#EXTINF:-1 tvg-id="{cfg["epg_id"]}" tvg-logo="{cfg["logo"]}" group-title="{cfg["group"]}",{cfg["name"]}'
        lines.append(extinf)
        lines.append(url)
        lines.append('')
        print(f"  Adicionado: {cfg['name']} (ID: {cfg['epg_id']})")

    output = '\n'.join(lines)

    with open("lista5.m3u", "w", encoding="utf-8") as f:
        f.write(output)

    print(f"\nArquivo salvo: lista5.m3u ({len(output)} bytes)")
    print(f"\nCanais na lista final: {sum(1 for k in valid_channels if vt_results.get(k, True))}")
    print(f"EPG URL: {EPG_URL}")

    print("\n" + "=" * 70)
    print("RESUMO")
    print("=" * 70)
    for key, url in valid_channels.items():
        vt_ok = vt_results.get(key, True)
        cfg = CHANNEL_CONFIG.get(key, {})
        print(f"  {'✓' if vt_ok else '✗'} {cfg.get('name', key)}")
        print(f"     EPG ID: {cfg.get('epg_id', 'N/A')}")
        print(f"     Logo: {cfg.get('logo', 'N/A')[:60]}...")
        print(f"     URL: {url[:60]}...")
        print()

if __name__ == "__main__":
    main()
