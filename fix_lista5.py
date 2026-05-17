#!/usr/bin/env python3
import requests, gzip, re, sys, xml.etree.ElementTree as ET
from datetime import datetime, timedelta

CHANNEL_MAP = [
    ("abc news live", {"tvg_id": "465150", "name": "ABC News Live", "logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg"}),
    ("abc news", {"tvg_id": "465150", "name": "ABC News Live", "logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg"}),
    ("fox business", {"tvg_id": "464766", "name": "Fox Business", "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/c9b2e2eb-7b87-435c-9510-eab2650ff944/8b584585-acf2-4c37-aa07-aaf2d077bb20/1280x720/match/676/380/image.jpg"}),
    ("fox news", {"tvg_id": "465372", "name": "Fox News Channel", "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/63eca216-d4fe-42c6-91f3-08cfdfb8159f/03a45698-b51f-47d3-af85-f706cc9f6872/1280x720/match/400/225/image.jpg"}),
    ("cbs news", {"tvg_id": "464941", "name": "CBS News", "logo": "https://www.cbsnews.com/bundles/cbsnewsvideo/images/cbsn--main-bg.jpg"}),
]

EPG_URLS = [
    "https://epg.pw/xmltv/epg_US.xml.gz",
    "https://iptv-epg.org/files/epg-us.xml.gz",
]

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

def fix_logo(url):
    if not url:
        return None
    url = url.split("?")[0]
    if "imgur.com" in url.lower():
        return None
    if not url.lower().endswith((".jpg", ".jpeg")):
        url = re.sub(r'\.(png|webp|svg|gif)(\?.*)?$', '.jpg', url)
    return url

def get_channel_info(extinf, url):
    text = (extinf + " " + url).lower()
    for key, info in CHANNEL_MAP:
        if key in text:
            return info
    if "fox" in text and "business" in text:
        return dict(CHANNEL_MAP[2][1])
    if "fox" in text and "news" in text:
        return dict(CHANNEL_MAP[3][1])
    if "abc" in text:
        return dict(CHANNEL_MAP[0][1])
    if "cbs" in text:
        return dict(CHANNEL_MAP[4][1])
    return None

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
        return r.status_code in [200, 201, 202, 203, 204, 205, 206, 301, 302, 303, 307, 308]
    except:
        return False

print("=" * 60)
print("CORRECAO COMPLETA lista5.m3u")
print("=" * 60)

filepath = "lista5.m3u"
with open(filepath, "r") as f:
    raw = f.read()
lines = raw.strip().split("\n")

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

print(f"\nCanais encontrados no arquivo: {len(channels)}")

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

print("\nVerificacao EPG por canal:")
seen_ids = set()
for key, info in CHANNEL_MAP:
    tid = info["tvg_id"]
    if tid in seen_ids:
        continue
    seen_ids.add(tid)
    c = epg_data.get(tid, {"hoje": 0, "amanha": 0, "depois": 0})
    total = c["hoje"] + c["amanha"] + c["depois"]
    status = "OK" if c["hoje"] > 0 and c["amanha"] > 0 and c["depois"] > 0 else "FALHA"
    print(f"  {status} {info['name']} (ID:{tid}): Hoje={c['hoje']}, Amanha={c['amanha']}, Depois={c['depois']}")

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
        logo = fix_logo(info["logo"])
        new_extinf = f'#EXTINF:-1 tvg-id="{info["tvg_id"]}" tvg-name="{channel_name}" group-title="NEWS WORLD",{channel_name}'
        if logo:
            new_extinf = f'#EXTINF:-1 tvg-id="{info["tvg_id"]}" tvg-name="{channel_name}" tvg-logo="{logo}" group-title="NEWS WORLD",{channel_name}'
            if not re.search(r'\.jpe?g["\s]', new_extinf):
                new_extinf = re.sub(r'(tvg-logo=")([^"]+?)(\.\w+)?(")', 
                    lambda m: f'{m.group(1)}{re.sub(r"\.(png|webp|svg|gif)", ".jpg", m.group(2))}{m.group(4)}', new_extinf)
        seen_channels[channel_name] = {"extinf": new_extinf, "url": url, "tvg_id": info["tvg_id"]}
        valid.append(seen_channels[channel_name])
        print(f"  [{idx+1}/{len(channels)}] OK: {channel_name} -> {url[:60]}...")
    else:
        removed["duplicate"] += 1

print(f"\nResumo:")
print(f"  Validos: {len(valid)}")
print(f"  Removidos - Offline: {removed['offline']}, Duplicados: {removed['duplicate']}, Sem match: {removed['no_match']}, Invalidos: {removed['invalid']}")

epg_urls_str = ",".join(EPG_URLS)
print(f"\nEscrevendo {filepath}...")
with open(filepath, "w", encoding="utf-8") as f:
    f.write(f'#EXTM3U x-tvg-url="{epg_urls_str}"\n')
    for ch in valid:
        f.write(f"{ch['extinf']}\n")
        f.write(f"{ch['url']}\n")

print(f"Concluido! {len(valid)} canais no arquivo.")
print(f"EPGs: {epg_urls_str}")

print(f"\nVerificacao final do formato:")
today_str = datetime.now().strftime("%Y-%m-%d")
tomorrow_str = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
after_str = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
print(f"  Programacao: Hoje ({today_str}), Amanha ({tomorrow_str}), Depois ({after_str})")

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
    print("AVISOS:")
    for e in errors:
        print(e)
else:
    print("  Formato OK - todas as URLs tem #EXTINF antes e sem imgur.com")
