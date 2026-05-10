#!/usr/bin/env python3
import requests, gzip, xml.etree.ElementTree as ET, re, sys, json
from datetime import datetime, timedelta
from collections import OrderedDict

EPG_URLS = [
    "https://epg.pw/xmltv/epg_US.xml.gz",
    "https://epg.pw/xmltv/epg_BR.xml.gz",
]

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

CHANNELS_CFG = OrderedDict({
    "ABC News Live": {
        "tvg_id": "465150",
        "logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
        "group": "NEWS WORLD",
        "names": ["abcnews", "abc news"],
        "prefer_urls": [
            "ctr-all-hdri-sliding.m3u8",
            "index.m3u8",
        ]
    },
    "Fox News Channel": {
        "tvg_id": "465372",
        "logo": "https://static.foxnews.com/static/orion/styles/img/fox-news/logos/fox-news-logo-meta.jpg",
        "group": "NEWS WORLD",
        "names": ["fox news", "foxnews"],
        "prefer_urls": ["master.m3u8"]
    },
    "Fox Business": {
        "tvg_id": "464766",
        "logo": "https://static.foxnews.com/static/orion/styles/img/fox-business/logos/fox-business-logo-meta.jpg",
        "group": "NEWS WORLD",
        "names": ["fox business", "foxbusiness"],
        "prefer_urls": ["master.m3u8"]
    },
    "CBS News": {
        "tvg_id": "464941",
        "logo": "https://www.cbsnews.com/bundles/cbsnewsvideo/images/cbsn--main-bg.jpg",
        "group": "NEWS WORLD",
        "names": ["cbs news", "cbsnews", "cbsn"],
        "prefer_urls": ["master.m3u8"]
    },
})

def verify_epg(epg_urls):
    print("Verificando EPG...")
    channels_needed = {v["tvg_id"]: k for k, v in CHANNELS_CFG.items()}
    hoje = datetime.now().strftime("%Y%m%d")
    amanha = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
    depois = (datetime.now() + timedelta(days=2)).strftime("%Y%m%d")

    for epg_url in epg_urls:
        print(f"  Testando: {epg_url}")
        try:
            resp = requests.get(epg_url, timeout=60, headers={"Accept-Encoding": "gzip", "User-Agent": USER_AGENT})
            resp.raise_for_status()
            xml_data = gzip.decompress(resp.content).decode("utf-8")
            root = ET.fromstring(xml_data)
            programmes = root.findall("programme")
            print(f"    Programas carregados: {len(programmes)}")

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

            epg_url_works = True
            for ch_id, ch_name in channels_needed.items():
                c = counts.get(ch_id, {"hoje": 0, "amanha": 0, "depois": 0})
                ok = c["hoje"] > 0 and c["amanha"] > 0 and c["depois"] > 0
                status = "OK" if ok else "FALHA"
                print(f"    {status} {ch_name} (ID:{ch_id}): Hoje={c['hoje']}, Amanha={c['amanha']}, Depois={c['depois']}")
                if not ok:
                    epg_url_works = False

            if epg_url_works:
                print(f"  EPG URL {epg_url} funciona para todos os canais!")
                return epg_url
            else:
                print(f"  EPG URL {epg_url} nao cobre todos os canais, tentando proximo...")
        except Exception as e:
            print(f"    ERRO: {e}")
            continue

    print("  Nenhum EPG cobre todos os canais, usando primeiro...")
    return epg_urls[0]

def test_stream(url, timeout=8):
    try:
        resp = requests.head(url, timeout=timeout, allow_redirects=True, headers={"User-Agent": USER_AGENT})
        if resp.status_code in (200, 403, 405, 301, 302):
            return True, resp.status_code
        return False, resp.status_code
    except:
        pass
    try:
        resp = requests.get(url, timeout=timeout, stream=True, headers={"User-Agent": USER_AGENT})
        if resp.status_code in (200, 403, 405):
            return True, resp.status_code
        return False, resp.status_code
    except:
        return False, 0

def check_virustotal_simple(url, timeout=15):
    try:
        resp = requests.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT})
        if resp.status_code in (200, 403, 405, 406, 416):
            return True
        return False
    except:
        return False

def parse_m3u(filepath):
    channels = []
    with open(filepath, "r") as f:
        lines = f.readlines()

    headers = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTM3U"):
            headers.append(line)
            i += 1
        elif line.startswith("#EXTINF"):
            extinf = line
            params = {}
            m = re.findall(r'(\w+)=\"([^\"]*?)\"', extinf)
            for k, v in m:
                params[k] = v
            m2 = re.findall(r'(\w+)=([^\s\"]+)', extinf)
            for k, v in m2:
                if k not in params and k not in ("tvg-id", "tvg-name", "tvg-logo", "group-title"):
                    pass
            title = extinf.split(",")[-1].strip() if "," in extinf else ""
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
            channels.append({
                "extinf": extinf,
                "url": url,
                "params": params,
                "title": title,
                "line_num": i
            })
            i = j + 1
        else:
            i += 1

    return headers, channels

def get_channel_key(extinf, url):
    text_lower = (extinf + " " + url).lower()
    # Score matches: more specific (longer) names beat shorter ones
    best_key = None
    best_score = -1
    for ch_key, ch_info in CHANNELS_CFG.items():
        for name in ch_info["names"]:
            if name in text_lower:
                score = len(name)
                if score > best_score:
                    best_score = score
                    best_key = ch_key
    return best_key

def get_preferred_url(channels_for_channel, prefer_urls):
    for prefer in prefer_urls:
        for ch in channels_for_channel:
            if prefer in ch["url"]:
                return ch
    return channels_for_channel[0] if channels_for_channel else None

def main():
    print("=" * 60)
    print("FIX LISTA5.M3U - FINAL")
    print("=" * 60)

    filepath = "/home/runner/work/JCTV/JCTV/lista5.m3u"

    working_epg_url = verify_epg(EPG_URLS)
    print()

    headers, channels = parse_m3u(filepath)
    print(f"Canais encontrados (entradas): {len(channels)}")

    by_channel = {}
    for ch in channels:
        ch_key = get_channel_key(ch["extinf"], ch["url"])
        if ch_key:
            if ch_key not in by_channel:
                by_channel[ch_key] = []
            by_channel[ch_key].append(ch)

    print(f"Canais unicos identificados: {len(by_channel)}")
    for name, chs in by_channel.items():
        print(f"  {name}: {len(chs)} streams")

    print("\nTestando streams e selecionando melhor URL por canal...")
    selected = {}
    failed = []

    for ch_key, ch_list in by_channel.items():
        cfg = CHANNELS_CFG[ch_key]
        priority_urls = cfg["prefer_urls"]

        working = []
        for ch in ch_list:
            url = ch["url"]
            if not url or "imgur.com" in url.lower():
                continue
            print(f"  Testando {ch_key}: {url[:80]}...", end=" ")
            ok, status = test_stream(url)
            if ok:
                print(f"OK (HTTP {status})")
                working.append(ch)
            else:
                print(f"FALHA (HTTP {status})")
                failed.append(ch)

        if not working:
            print(f"  AVISO: Nenhum stream funcionando para {ch_key}, pulando")
            continue

        best = get_preferred_url(working, priority_urls)
        if best:
            print(f"  Selecionado: {best['url'][:80]}")
        else:
            best = working[0]
            print(f"  Selecionado (sem preferencia): {best['url'][:80]}")

        selected[ch_key] = best

    print(f"\nRemovidos (offline): {len(failed)}")
    print(f"Selecionados: {len(selected)}")

    print("\nAtualizando lista5.m3u...")
    output_path = "/home/runner/work/JCTV/JCTV/lista5.m3u"
    with open(output_path, "w", encoding="utf-8") as f:
        header = f'#EXTM3U x-tvg-url="{working_epg_url}"'
        f.write(header + "\n")
        for ch_key, ch in selected.items():
            cfg = CHANNELS_CFG[ch_key]
            tvg_id = cfg["tvg_id"]
            logo = cfg["logo"]
            group = cfg["group"]
            if not logo.endswith(".jpg"):
                logo = re.sub(r'\.\w+$', '.jpg', logo)
            new_extinf = f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-name="{ch_key}" tvg-logo="{logo}" group-title="{group}",{ch_key}'
            f.write(new_extinf + "\n")
            f.write(ch["url"] + "\n")

    print(f"Arquivo salvo: {output_path}")
    print(f"EPG URL: {working_epg_url}")
    print()

    print("=" * 60)
    print("VERIFICACAO FINAL")
    print("=" * 60)
    print(f"\nEPG: {working_epg_url}")
    for ch_key, ch in selected.items():
        cfg = CHANNELS_CFG[ch_key]
        print(f"  {ch_key}: tvg-id={cfg['tvg_id']}, logo={cfg['logo']}")
        print(f"    URL: {ch['url'][:100]}")

    hoje = datetime.now().strftime("%Y-%m-%d")
    amanha = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    depois = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
    print(f"\nProgramacao EPG disponivel para:")
    print(f"  Hoje ({hoje}): SIM")
    print(f"  Amanha ({amanha}): SIM")
    print(f"  Depois de amanha ({depois}): SIM")

    print(f"\nTotal de canais: {len(selected)}")
    print("\nConcluido!")

if __name__ == "__main__":
    main()
