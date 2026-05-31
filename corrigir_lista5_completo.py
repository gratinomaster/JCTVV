#!/usr/bin/env python3
import requests
import re
import gzip
import sys
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from urllib.parse import urlparse

M3U_PATH = "lista5.m3u"
BACKUP_PATH = "lista5.m3u.bak." + datetime.now().strftime("%Y%m%d_%H%M%S")

EPG_SOURCES = [
    "https://epg.pw/xmltv/epg_US.xml.gz",
    "https://iptv-epg.org/files/epg-us.xml.gz",
]

CHANNEL_MAP = {
    "abc news live": {"tvg_id": "465150", "tvg_name": "ABC News Live"},
    "abc news": {"tvg_id": "465150", "tvg_name": "ABC News Live"},
    "fox business": {"tvg_id": "464766", "tvg_name": "Fox Business HD"},
    "fox news": {"tvg_id": "465372", "tvg_name": "Fox News Channel HD"},
    "cbs news": {"tvg_id": "464941", "tvg_name": "CBS News National Stream"},
}

LOGO_MAP = {
    "abc news": "https://raw.githubusercontent.com/gratinomaster/JCTV/main/abc_news.jpg",
    "fox news": "https://raw.githubusercontent.com/gratinomaster/JCTV/main/fox_news.jpg",
    "fox business": "https://raw.githubusercontent.com/gratinomaster/JCTV/main/fox_business.jpg",
    "cbs news": "https://raw.githubusercontent.com/gratinomaster/JCTV/main/cbs_news.jpg",
}

EPG_URLS = [
    "https://epg.pw/xmltv/epg_US.xml.gz",
    "https://iptv-epg.org/files/epg-us.xml.gz",
]

LOGO_TO_CHANNEL = {
    "s.abcnews.com": "abc news live",
    "keyframe-cdn.abcnews.com": "abc news live",
    "foxnews.com": "fox news",
    "cf-images.us-east-1.prod.boltdns.net": "fox news",
    "cbsnewsstatic.com": "cbs news",
    "cbsnews.com": "cbs news",
}

def download_epg(url):
    try:
        r = requests.get(url, timeout=120, headers={'User-Agent': 'Mozilla/5.0'})
        if r.status_code != 200:
            return None
        try:
            return gzip.decompress(r.content).decode('utf-8')
        except:
            return r.text
    except:
        return None

def get_epg_programs(epg_content, tvg_id):
    if not epg_content:
        return {}
    try:
        root = ET.fromstring(epg_content)
        hoje = datetime.now().strftime("%Y%m%d")
        amanha = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
        depois = (datetime.now() + timedelta(days=2)).strftime("%Y%m%d")
        dates = {"hoje": hoje, "amanha": amanha, "depois": depois}
        counts = {"hoje": 0, "amanha": 0, "depois": 0}
        for prog in root.findall("programme"):
            ch = prog.get("channel", "")
            if ch == tvg_id:
                start = prog.get("start", "")[:8]
                for key, val in dates.items():
                    if start == val:
                        counts[key] += 1
        return counts
    except:
        return {}

def parse_m3u(filepath):
    channels = []
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXTINF:'):
            url = lines[i + 1].strip() if i + 1 < len(lines) else ""
            m_id = re.search(r'tvg-id="([^"]*)"', line)
            tvg_id = m_id.group(1) if m_id else ""
            m_logo = re.search(r'tvg-logo="([^"]*)"', line)
            tvg_logo = m_logo.group(1) if m_logo else ""
            m_group = re.search(r'group-title="([^"]*)"', line)
            group = m_group.group(1) if m_group else ""
            name_match = re.search(r',(.+)$', line)
            name = name_match.group(1).strip() if name_match else ""
            channels.append({
                "extinf": line, "url": url, "name": name,
                "tvg_id": tvg_id, "tvg_logo": tvg_logo, "group": group
            })
            i += 2
        else:
            i += 1
    return channels

def test_url_access(url):
    try:
        base = url.split('?')[0]
        r = requests.head(base, timeout=15, allow_redirects=True,
                          headers={'User-Agent': 'Mozilla/5.0'})
        if r.status_code == 405:
            return True, 200
        if r.status_code < 400:
            return True, r.status_code
        if r.status_code in [403, 401]:
            return True, r.status_code
        return False, r.status_code
    except requests.exceptions.Timeout:
        try:
            r = requests.get(base, timeout=15, allow_redirects=True,
                             headers={'User-Agent': 'Mozilla/5.0'})
            if r.status_code < 400:
                return True, r.status_code
            return False, r.status_code
        except:
            return False, "timeout"
    except Exception as e:
        return False, str(e)[:30]

def get_channel_key(name, logo=""):
    name_lower = name.lower().strip()
    keys = sorted(CHANNEL_MAP.keys(), key=len, reverse=True)
    for key in keys:
        if key in name_lower:
            return key
    if logo:
        logo_lower = logo.lower()
        for logo_pattern, channel_key in LOGO_TO_CHANNEL.items():
            if logo_pattern in logo_lower:
                return channel_key
    return None

def url_priority(url):
    url_lower = url.lower()
    if 'ctr-all-hdri-sliding' in url_lower or 'ctr-all-hdri' in url_lower:
        return 5
    if 'master.m3u8' in url_lower:
        return 4
    if 'index.m3u8' in url_lower and 'index_' not in url_lower:
        return 3
    if 'akamai' in url_lower:
        return 2
    return 1

def fix_logo_url(logo_url, channel_key):
    if not logo_url:
        return LOGO_MAP.get(channel_key, "")
    if "imgur.com" in logo_url.lower():
        return LOGO_MAP.get(channel_key, "")
    if channel_key == "fox business" and "foxnews" in logo_url.lower():
        return LOGO_MAP.get(channel_key, logo_url)
    parsed = urlparse(logo_url)
    path = parsed.path.lower()
    if path.endswith(('.png', '.webp', '.gif', '.svg', '.ico', '.bmp')):
        new_path = re.sub(r'\.(png|webp|gif|svg|ico|bmp)$', '.jpg', path)
        logo_url = parsed._replace(path=new_path).geturl()
    elif not path.endswith('.jpg') and not path.endswith('.jpeg'):
        logo_url = LOGO_MAP.get(channel_key, logo_url)
    return logo_url

def main():
    print("=" * 70)
    print("CORRECAO COMPLETA lista5.m3u")
    print(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 70)

    # Step 1: Backup
    if os.path.exists(M3U_PATH):
        import shutil
        shutil.copy2(M3U_PATH, BACKUP_PATH)
        print(f"\n[1] Backup: {BACKUP_PATH}")

    # Step 2: Parse current file
    channels = parse_m3u(M3U_PATH)
    print(f"\n[2] Canais lidos: {len(channels)}")

    # Step 3: Download EPG
    print(f"\n[3] Baixando EPG...")
    epg_content = None
    epg_url = None
    for src in EPG_SOURCES:
        print(f"  Testando: {src[:50]}...")
        content = download_epg(src)
        if content and len(content) > 10000:
            epg_content = content
            epg_url = src
            print(f"  OK! {len(content):,} bytes")
            break
        print(f"  FALHOU")
    
    if not epg_content:
        print("  Usando EPG offline (lista5_epg.xml)...")
        epg_path = "lista5_epg.xml"
        if os.path.exists(epg_path):
            with open(epg_path, 'r') as f:
                epg_content = f.read()
            epg_url = "https://raw.githubusercontent.com/gratinomaster/JCTV/main/lista5_epg.xml"
        elif os.path.exists(epg_path + ".gz"):
            import gzip
            with gzip.open(epg_path + ".gz", 'rt') as f:
                epg_content = f.read()
            epg_url = "https://raw.githubusercontent.com/gratinomaster/JCTV/main/lista5_epg.xml.gz"

    # Step 4: Group unique channels, pick best URL per channel
    unique = {}
    for ch in channels:
        key = get_channel_key(ch["name"], ch["tvg_logo"])
        if key:
            if key not in unique or url_priority(ch["url"]) > url_priority(unique[key]["url"]):
                unique[key] = ch
        else:
            if ch["name"] not in [c.get("name", "") for c in unique.values()]:
                unique[ch["name"]] = ch
    
    print(f"\n[4] Canais unicos: {len(unique)}")
    for k, v in unique.items():
        print(f"  {k}: {v['name'][:50]}")

    # Step 5: Test EPG coverage
    print(f"\n[5] Testando EPG (hoje/amanha/depois)...")
    epg_results = {}
    for ch_key, ch_data in unique.items():
        info = CHANNEL_MAP.get(ch_key)
        if not info:
            continue
        tvg_id = info["tvg_id"]
        counts = get_epg_programs(epg_content, tvg_id)
        epg_results[ch_key] = counts
        status = "OK" if counts.get("hoje", 0) > 0 and counts.get("amanha", 0) > 0 else "PARCIAL"
        print(f"  {ch_key}: tvg-id={tvg_id} | Hoje={counts.get('hoje',0)} Amanha={counts.get('amanha',0)} Depois={counts.get('depois',0)} | {status}")

    # Step 6: Test URLs
    print(f"\n[6] Testando acessibilidade das URLs...")
    valid_urls = {}
    bad_urls = []
    for ch_key, ch_data in unique.items():
        url = ch_data["url"]
        ok, status = test_url_access(url)
        if ok:
            valid_urls[ch_key] = url
            print(f"  {ch_key}: OK ({status})")
        else:
            bad_urls.append(ch_key)
            print(f"  {ch_key}: FALHA ({status}) - sera removido")

    # Step 7: Remove bad channels
    for k in bad_urls:
        if k in unique:
            del unique[k]
            print(f"  Removido: {k}")

    # Step 8: Build corrected file
    print(f"\n[7] Gerando lista5.m3u corrigida...")
    lines = []
    
    # Header with multiple EPG URLs
    epg_url_m3u = " ".join(EPG_SOURCES)
    lines.append('#EXTM3U url-tvg="' + epg_url_m3u + '"')
    
    # Write channel entries (one best stream per channel)
    for ch_key, ch_data in unique.items():
        info = CHANNEL_MAP.get(ch_key, {})
        tvg_id = info.get("tvg_id", "")
        tvg_name = info.get("tvg_name", ch_data["name"])
        
        logo = fix_logo_url(ch_data["tvg_logo"], ch_key)
        group = ch_data["group"] if ch_data["group"] else "NEWS WORLD"
        
        attrs = f'tvg-id="{tvg_id}" tvg-name="{tvg_name}" tvg-logo="{logo}" group-title="{group}"'
        extinf = f'#EXTINF:-1 {attrs},{tvg_name}'
        
        lines.append(extinf)
        lines.append(ch_data["url"])
        lines.append("")
    
    # Remove trailing empty line
    while lines and lines[-1] == "":
        lines.pop()
    
    with open(M3U_PATH, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
        f.write('\n')
    
    print(f"  Canais escritos: {len(unique)}")
    print(f"  EPG URL: {epg_url_m3u}")

    # Summary
    print(f"\n[8] RESUMO FINAL:")
    print(f"  Backup: {BACKUP_PATH}")
    print(f"  Canais processados: {len(channels)}")
    print(f"  Canais unicos mantidos: {len(unique)}")
    print(f"  Canais removidos (URL invalida): {len(bad_urls)}")
    for ch_key, counts in epg_results.items():
        info = CHANNEL_MAP.get(ch_key, {})
        print(f"  {ch_key} (tvg-id={info.get('tvg_id','')}): EPG Hoje={counts.get('hoje',0)} Amanha={counts.get('amanha',0)} Depois={counts.get('depois',0)}")

    print(f"\nArquivo {M3U_PATH} atualizado com sucesso!")

if __name__ == "__main__":
    main()
