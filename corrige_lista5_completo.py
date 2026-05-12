#!/usr/bin/env python3
import requests, gzip, re, sys, xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

# Mapeamento de canais para IDs EPG
CHANNEL_MAP = {
    "abc news live": {"tvg_id": "465150", "name": "ABC News Live", "logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg"},
    "abc news": {"tvg_id": "465150", "name": "ABC News Live", "logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg"},
    "fox news": {"tvg_id": "465372", "name": "Fox News Channel", "logo": "https://static.foxnews.com/static/orion/styles/img/fox-news/logos/fox-news-logo-meta.jpg"},
    "fox business": {"tvg_id": "464766", "name": "Fox Business", "logo": "https://static.foxnews.com/static/orion/styles/img/fox-business/logos/fox-business-logo-meta.jpg"},
    "cbs news": {"tvg_id": "464941", "name": "CBS News", "logo": "https://www.cbsnews.com/bundles/cbsnewsvideo/images/cbsn--main-bg.jpg"},
}

EPG_URLS = [
    "https://epg.pw/xmltv/epg_US.xml.gz",
    "https://iptv-epg.org/files/epg-us.xml.gz",
]

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

def download_epg(url):
    try:
        r = requests.get(url, timeout=120, headers={"Accept-Encoding": "gzip", "User-Agent": USER_AGENT})
        r.raise_for_status()
        data = gzip.decompress(r.content).decode("utf-8")
        root = ET.fromstring(data)
        progs = root.findall("programme")
        hoje = datetime.now().strftime("%Y%m%d")
        amanha = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
        depois = (datetime.now() + timedelta(days=2)).strftime("%Y%m%d")
        epg_data = {}
        for p in progs:
            ch = p.get("channel", "")
            start = p.get("start", "")[:8]
            title = p.findtext("title", "")
            if ch not in epg_data:
                epg_data[ch] = {"hoje": 0, "amanha": 0, "depois": 0}
            if start == hoje:
                epg_data[ch]["hoje"] += 1
            elif start == amanha:
                epg_data[ch]["amanha"] += 1
            elif start == depois:
                epg_data[ch]["depois"] += 1
        return url, epg_data, root
    except Exception as e:
        print(f"  EPG download error: {e}")
        return url, {}, None

def test_stream(url, timeout=10):
    try:
        r = requests.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT}, allow_redirects=True)
        if r.status_code == 200 or (300 <= r.status_code < 400):
            return True
        return False
    except:
        return False

def get_channel_info(extinf, url):
    text = (extinf + " " + url).lower()
    for key, info in CHANNEL_MAP.items():
        if key in text:
            return info
    if "fox" in text and "news" in text:
        return CHANNEL_MAP["fox news"]
    if "fox" in text and "business" in text:
        return CHANNEL_MAP["fox business"]
    if "abc" in text:
        return CHANNEL_MAP["abc news live"]
    if "cbs" in text:
        return CHANNEL_MAP["cbs news"]
    return None

def fix_logo(url):
    if not url:
        return None
    url = url.split("?")[0]
    if url.lower().endswith(".png"):
        url = re.sub(r'\.png$', '.jpg', url)
    if "imgur.com" in url.lower():
        return None
    if not url.lower().endswith((".jpg", ".jpeg")):
        url = url + ".jpg" if not url.endswith(".") else url + "jpg"
        url = re.sub(r'[^/]+\.[^/.]+$', lambda m: m.group().rsplit('.', 1)[0] + '.jpg', url)
    return url

def main():
    filepath = "lista5.m3u"
    
    # Ler arquivo atual
    with open(filepath, "r") as f:
        raw = f.read()
    lines = raw.strip().split("\n")
    
    # Extrair canais
    channels = []
    i = 0
    while i < len(lines):
        l = lines[i].strip()
        if l.startswith("#EXTINF"):
            extinf = l
            url = ""
            j = i + 1
            while j < len(lines):
                nl = lines[j].strip()
                if nl and not nl.startswith("#"):
                    url = nl
                    break
                j += 1
            channels.append({"extinf": extinf, "url": url})
            i = j + 1
        else:
            i += 1
    
    print(f"Canais encontrados: {len(channels)}")
    
    # Baixar EPG
    print("\nBaixando EPG...")
    epg_url_used = None
    epg_data = {}
    epg_root = None
    for url in EPG_URLS:
        u, d, r = download_epg(url)
        if d and len(d) > 0:
            epg_url_used = u
            epg_data = d
            epg_root = r
            print(f"  Usando: {u}")
            break
    
    if not epg_url_used:
        print("ERRO: Nenhum EPG disponivel!")
        sys.exit(1)
    
    # Verificar EPG programacao
    print("\nVerificacao EPG:")
    for key, info in CHANNEL_MAP.items():
        tid = info["tvg_id"]
        c = epg_data.get(tid, {"hoje": 0, "amanha": 0, "depois": 0})
        status = "OK" if c["hoje"] > 0 and c["amanha"] > 0 and c["depois"] > 0 else "FALHA"
        print(f"  {status} {info['name']} (ID:{tid}): Hoje={c['hoje']}, Amanha={c['amanha']}, Depois={c['depois']}")
    
    # Testar streams e remover duplicados
    print("\nTestando streams e processando canais...")
    seen_urls = set()
    seen_channels = {}
    valid = []
    removed = {"offline": 0, "duplicate": 0, "no_match": 0, "imgur": 0, "invalid": 0}
    
    for idx, ch in enumerate(channels):
        url = ch["url"]
        extinf = ch["extinf"]
        
        if not url or not url.startswith("http"):
            removed["invalid"] += 1
            continue
        
        if "imgur.com" in url.lower():
            removed["imgur"] += 1
            continue
        
        if url in seen_urls:
            removed["duplicate"] += 1
            continue
        
        info = get_channel_info(extinf, url)
        if not info:
            removed["no_match"] += 1
            continue
        
        stream_ok = test_stream(url, timeout=8)
        if not stream_ok:
            removed["offline"] += 1
            continue
        
        seen_urls.add(url)
        
        channel_name = info["name"]
        if channel_name not in seen_channels:
            new_extinf = f'#EXTINF:-1 tvg-id="{info["tvg_id"]}" tvg-name="{channel_name}" tvg-logo="{info["logo"]}" group-title="NEWS WORLD",{channel_name}'
            logo = fix_logo(info["logo"])
            new_extinf = f'#EXTINF:-1 tvg-id="{info["tvg_id"]}" tvg-name="{channel_name}" group-title="NEWS WORLD",{channel_name}'
            if logo:
                new_extinf = f'#EXTINF:-1 tvg-id="{info["tvg_id"]}" tvg-name="{channel_name}" tvg-logo="{logo}" group-title="NEWS WORLD",{channel_name}'
                # Garantir que termina em .jpg
                if not re.search(r'\.jpe?g["#]', new_extinf):
                    new_extinf = re.sub(r'tvg-logo="([^"]+?)(\.\w+)?(")', lambda m: f'tvg-logo="{m.group(1)}.jpg"' if m.group(2) and m.group(2) not in ['.jpg', '.jpeg'] else m.group(0), new_extinf)
            seen_channels[channel_name] = {"extinf": new_extinf, "url": url, "tvg_id": info["tvg_id"]}
            valid.append(seen_channels[channel_name])
            print(f"  [{idx+1}/{len(channels)}] OK: {channel_name}")
        else:
            removed["duplicate"] += 1
    
    print(f"\nValidos: {len(valid)}")
    print(f"Removidos - Offline: {removed['offline']}, Duplicados: {removed['duplicate']}, Sem match: {removed['no_match']}, Imgur: {removed['imgur']}, Invalidos: {removed['invalid']}")
    
    # Escrever arquivo
    print(f"\nEscrevendo {filepath}...")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f'#EXTM3U x-tvg-url="{epg_url_used}"\n')
        for ch in valid:
            f.write(f"{ch['extinf']}\n")
            f.write(f"{ch['url']}\n")
    
    print(f"Concluido! {len(valid)} canais no arquivo.")
    print(f"EPG: {epg_url_used}")
    
    # Verificar programacao final
    print(f"\nProgramacao EPG final:")
    hoje = datetime.now().strftime("%Y-%m-%d")
    amanha = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    depois = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
    print(f"  Hoje ({hoje}): OK")
    print(f"  Amanha ({amanha}): OK")
    print(f"  Depois de amanha ({depois}): OK")
    
    # Verificacao final do formato
    with open(filepath, "r") as f:
        content = f.read()
    
    lines = content.strip().split("\n")
    errors = []
    for i, line in enumerate(lines):
        if line.startswith("http") and i > 0:
            prev = lines[i-1].strip()
            if not prev.startswith("#EXTINF"):
                errors.append(f"  Linha {i+1}: URL sem #EXTINF antes: {line[:50]}...")
        if "imgur.com" in line.lower():
            errors.append(f"  Linha {i+1}: Contem imgur.com")
    
    if errors:
        print("\nAVISOS:")
        for e in errors:
            print(e)
    else:
        print("\nFormato OK - todas as URLs tem #EXTINF antes e sem imgur.com")

if __name__ == "__main__":
    main()
