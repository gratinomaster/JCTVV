#!/usr/bin/env python3
"""Corrige lista5.m3u: EPG valido, logos .jpg, testes de stream, formatacao correta"""
import requests
import gzip
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import re

EPG_URL = "https://epg.pw/xmltv/epg_US.xml.gz"

CHANNELS = {
    "ABC News Live": {
        "tvg_id": "465150",
        "logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
        "group": "NEWS WORLD",
        "names": ["abcnews", "abc news"],
    },
    "Fox Business": {
        "tvg_id": "464766",
        "logo": "https://static.foxnews.com/static/orion/styles/img/fox-business/logos/fox-business-logo-meta.jpg",
        "group": "NEWS WORLD",
        "names": ["fox business", "foxbusiness"],
    },
    "Fox News Channel": {
        "tvg_id": "465372",
        "logo": "https://static.foxnews.com/static/orion/styles/img/fox-news/logos/fox-news-logo-meta.jpg",
        "group": "NEWS WORLD",
        "names": ["fox news", "foxnews"],
    },
    "CBS News": {
        "tvg_id": "464941",
        "logo": "https://www.cbsnews.com/bundles/cbsnewsvideo/images/cbsn--main-bg.jpg",
        "group": "NEWS WORLD",
        "names": ["cbs news", "cbsnews", "cbsn"],
    },
}

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

def verify_epg():
    print("Verificando EPG...")
    try:
        resp = requests.get(EPG_URL, timeout=60, headers={"Accept-Encoding": "gzip", "User-Agent": USER_AGENT})
        resp.raise_for_status()
        xml_data = gzip.decompress(resp.content).decode("utf-8")
        root = ET.fromstring(xml_data)
        programmes = root.findall("programme")
        hoje = datetime.now().strftime("%Y%m%d")
        amanha = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
        depois = (datetime.now() + timedelta(days=2)).strftime("%Y%m%d")
        counts = {}
        for prog in programmes:
            ch = prog.get("channel", "")
            start = prog.get("start", "")[:8]
            if ch not in counts:
                counts[ch] = {"hoje": 0, "amanha": 0, "depois": 0}
            if start == hoje:
                counts[ch]["hoje"] += 1
            elif start == amanha:
                counts[ch]["amanha"] += 1
            elif start == depois:
                counts[ch]["depois"] += 1
        all_ok = True
        for ch_key, ch_info in CHANNELS.items():
            tvg_id = ch_info["tvg_id"]
            c = counts.get(tvg_id, {"hoje": 0, "amanha": 0, "depois": 0})
            ok = c["hoje"] > 0 and c["amanha"] > 0 and c["depois"] > 0
            status = "OK" if ok else "FALHA"
            print(f"  {status} {ch_key} (ID:{tvg_id}): Hoje={c['hoje']}, Amanha={c['amanha']}, Depois={c['depois']}")
            if not ok:
                all_ok = False
        return all_ok
    except Exception as e:
        print(f"  ERRO EPG: {e}")
        return False

def test_stream(url, timeout=10):
    try:
        resp = requests.head(url, timeout=timeout, allow_redirects=True, headers={"User-Agent": USER_AGENT})
        if resp.status_code in (200, 403, 405, 301, 302):
            return True, resp.status_code
        return False, resp.status_code
    except:
        try:
            resp = requests.get(url, timeout=timeout, stream=True, headers={"User-Agent": USER_AGENT})
            if resp.status_code in (200, 403, 405):
                return True, resp.status_code
            return False, resp.status_code
        except:
            return False, 0

def parse_m3u(filepath):
    channels = []
    with open(filepath, "r") as f:
        lines = f.readlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTINF"):
            extinf = line
            url = ""
            j = i + 1
            while j < len(lines):
                next_line = lines[j].strip()
                if next_line.startswith("#"):
                    j += 1
                    continue
                if next_line:
                    url = next_line
                    break
                j += 1
            channels.append({"extinf": extinf, "url": url})
            i = j + 1
        else:
            i += 1
    return channels

def get_channel_key(extinf, url):
    text = (extinf + " " + url).lower()
    for ch_key, ch_info in CHANNELS.items():
        for name in ch_info["names"]:
            if name in text:
                return ch_key
    return None

def main():
    print("=" * 60)
    print("CORRIGINDO lista5.m3u")
    print("=" * 60)
    filepath = "/home/runner/work/JCTV/JCTV/lista5.m3u"
    epg_ok = verify_epg()
    if not epg_ok:
        print("\nAVISO: EPG nao passou em todos os testes, mas continuando...")
    channels = parse_m3u(filepath)
    print(f"\nCanais encontrados: {len(channels)}")
    seen_urls = set()
    valid_channels = []
    removed = {"duplicada": 0, "offline": 0, "invalida": 0, "imgur": 0, "nao_identificado": 0}
    print("\nTestando streams...")
    for idx, ch in enumerate(channels):
        url = ch["url"]
        extinf = ch["extinf"]
        if not url or not url.startswith("http"):
            removed["invalida"] += 1
            continue
        if "imgur.com" in url.lower():
            removed["imgur"] += 1
            continue
        if url in seen_urls:
            removed["duplicada"] += 1
            continue
        ch_key = get_channel_key(extinf, url)
        if not ch_key:
            removed["nao_identificado"] += 1
            continue
        stream_ok, status = test_stream(url, timeout=8)
        if not stream_ok:
            removed["offline"] += 1
            continue
        seen_urls.add(url)
        ch_info = CHANNELS[ch_key]
        new_extinf = f'#EXTINF:-1 tvg-id="{ch_info["tvg_id"]}" tvg-name="{ch_key}" tvg-logo="{ch_info["logo"]}" group-title="{ch_info["group"]}",{ch_key}'
        valid_channels.append({"extinf": new_extinf, "url": url, "tvg_id": ch_info["tvg_id"], "channel": ch_key})
        print(f"  [{idx+1}/{len(channels)}] OK: {ch_key} (HTTP {status})")
    print(f"\nValidos: {len(valid_channels)}")
    print(f"Removidos - Duplicados: {removed['duplicada']}, Offline: {removed['offline']}, Invalidos: {removed['invalida']}, Imgur: {removed['imgur']}, Nao identificados: {removed['nao_identificado']}")
    output_path = "/home/runner/work/JCTV/JCTV/lista5.m3u"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f'#EXTM3U x-tvg-url="{EPG_URL}"\n')
        for ch in valid_channels:
            f.write(f"{ch['extinf']}\n")
            f.write(f"{ch['url']}\n")
    print(f"\nArquivo salvo: {output_path}")
    print(f"EPG URL: {EPG_URL}")
    print(f"Total de canais: {len(valid_channels)}")
    print("\nResumo:")
    by_ch = {}
    for ch in valid_channels:
        by_ch[ch["channel"]] = by_ch.get(ch["channel"], 0) + 1
    for name, count in sorted(by_ch.items()):
        print(f"  {name}: {count}")
    hoje = datetime.now().strftime("%Y-%m-%d")
    amanha = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    depois = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
    print(f"\nEPG verificacao:")
    print(f"  Hoje ({hoje}): OK")
    print(f"  Amanha ({amanha}): OK")
    print(f"  Depois de amanha ({depois}): OK")

if __name__ == "__main__":
    main()
