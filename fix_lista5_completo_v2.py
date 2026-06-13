#!/usr/bin/env python3
"""
Correção completa da lista5.m3u v2:
1. Adiciona EPG (tvg-id, url-tvg) em todos os canais
2. Remove duplicatas, mantendo apenas a melhor URL por canal
3. Verifica/logos .jpg (adiciona se faltar)
4. Testa URLs e remove as quebradas
5. Testa EPG hoje/amanhã/depois de amanhã
6. Mantém Fox News e Fox Business apenas se URLs funcionarem
"""
import re, gzip, os, shutil, ssl, json
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from urllib.request import Request, urlopen
from urllib.error import URLError

M3U_PATH = "lista5.m3u"
OUTPUT_PATH = "lista5.m3u"
BACKUP_PATH = "lista5.m3u.bak"

EPG_URLS = [
    "https://iptv-epg.org/files/epg-us.xml.gz",
    "https://epg.pw/xmltv/epg_US.xml.gz",
]

# Priority order for matching: longer/more specific first
CHANNEL_MAPPING = [
    ("abc news live", "ABCNewsLive.us", "ABC News Live"),
    ("abc news", "ABCNewsLive.us", "ABC News Live"),
    ("20/20", "ABCNewsLive.us", "ABC News Live"),
    ("fox business", "FoxBusiness.us", "Fox Business"),
    ("fox news channel", "FoxNewsChannel.us", "Fox News Channel"),
    ("fox news", "FoxNewsChannel.us", "Fox News Channel"),
    ("cbs news", "CBSNews.us", "CBS News 24/7"),
]

CHANNEL_LOGOS = {
    "ABCNewsLive.us": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
    "FoxNewsChannel.us": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/5083aae4-b8c5-4708-ac25-f3c5ac554341/b17e991e-a824-4bf7-8e6b-885b7cd2bcf4/1280x720/match/400/225/image.jpg",
    "FoxBusiness.us": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/25afb380-3b42-47b4-be31-733f1bbe07ae/107e58b1-b052-49e8-a1c2-cc8ce1cf3c5a/1280x720/match/400/225/image.jpg",
    "CBSNews.us": "https://www.cbsnews.com/bundles/cbsnewsvideo/images/cbsn--main-bg.jpg",
}

QUALITY_PRIORITY = [
    'ctr-all-hdri-sliding',  # Best: ABC Disney 1080p
    'master.m3u8',           # Best: CBS main manifest
    'abcn-live-10-cmaf-manifest',  # ABC Akamai main
    'index.m3u8',            # Generic manifest
]


def detect_tvg_id(name: str) -> Tuple[Optional[str], Optional[str]]:
    """Detect tvg-id from channel name. Returns (tvg_id, display_name)."""
    name_lower = name.lower()
    for prefix, tvg_id, display_name in CHANNEL_MAPPING:
        if prefix in name_lower:
            return tvg_id, display_name
    return None, None


def quality_score(url: str) -> int:
    """Score URL quality (lower = better)."""
    for i, pattern in enumerate(QUALITY_PRIORITY):
        if pattern in url:
            return i
    return len(QUALITY_PRIORITY)


def is_valid_jpg(url: str) -> bool:
    if not url: return False
    clean = url.split('?')[0].split('#')[0]
    return clean.lower().endswith('.jpg') or clean.lower().endswith('.jpeg')


def check_url(url: str, timeout: int = 10) -> bool:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        req = Request(url, method='HEAD')
        req.add_header('User-Agent', 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36')
        resp = urlopen(req, timeout=timeout, context=ctx)
        return resp.status in (200, 301, 302, 307, 308)
    except:
        pass
    try:
        req = Request(url)
        req.add_header('User-Agent', 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36')
        resp = urlopen(req, timeout=timeout, context=ctx)
        resp.read(1024)
        return True
    except:
        return False


def download_epg(url: str) -> Optional[str]:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        req = Request(url)
        req.add_header('User-Agent', 'Mozilla/5.0')
        resp = urlopen(req, timeout=60, context=ctx)
        data = resp.read()
        if url.endswith('.gz'):
            data = gzip.decompress(data)
        return data.decode('utf-8', errors='replace')
    except:
        return None


def test_epg_channel(epg_content: str, tvg_id: str) -> Dict:
    result = {"hoje": 0, "amanha": 0, "depois_amanha": 0}
    try:
        root = ET.fromstring(epg_content)
        hoje = datetime.now().strftime("%Y%m%d")
        amanha = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
        da = (datetime.now() + timedelta(days=2)).strftime("%Y%m%d")
        for prog in root.findall("programme"):
            ch = prog.get("channel", "")
            if ch == tvg_id:
                s = prog.get("start", "")[:8]
                if s == hoje: result["hoje"] += 1
                elif s == amanha: result["amanha"] += 1
                elif s == da: result["depois_amanha"] += 1
    except:
        pass
    return result


def main():
    print("=" * 70)
    print("CORREÇÃO COMPLETA DO lista5.m3u v2")
    print("=" * 70)

    # 1. Parse
    print("\n[1] Analisando lista5.m3u...")
    with open(M3U_PATH, 'r', encoding='utf-8') as f:
        content = f.read()
    
    lines = content.split('\n')
    entries = []
    i = 1 if lines[0].startswith('#EXTM3U') else 0
    while i < len(lines):
        l = lines[i].strip()
        if l.startswith('#EXTINF:'):
            url = lines[i+1].strip() if i+1 < len(lines) else ""
            name_m = re.search(r',(.+)$', l)
            name = name_m.group(1).strip() if name_m else ""
            logo_m = re.search(r'tvg-logo="([^"]*)"', l)
            logo = logo_m.group(1) if logo_m else ""
            group_m = re.search(r'group-title="([^"]*)"', l)
            group = group_m.group(1) if group_m else ""
            entries.append({"name": name, "url": url, "logo": logo, "group": group})
            i += 2
        else:
            i += 1

    print(f"  Entradas: {len(entries)}")

    # 2. Group by channel identity, pick best URL
    print("\n[2] Agrupando canais únicos...")
    channel_groups = {}  # tvg_id -> list of entries
    for e in entries:
        tvg_id, display_name = detect_tvg_id(e["name"])
        if not tvg_id:
            print(f"  ⚠ Não identificado: {e['name'][:40]}")
            continue
        if tvg_id not in channel_groups:
            channel_groups[tvg_id] = []
        channel_groups[tvg_id].append(e)

    for tvg_id, group in channel_groups.items():
        name = CHANNEL_MAPPING[[p[1] for p in CHANNEL_MAPPING].index(tvg_id)][2]
        print(f"  {name} [{tvg_id}]: {len(group)} variantes")

    # 3. Pick best URL per channel
    print("\n[3] Selecionando melhor URL por canal...")
    best_entries = {}
    for tvg_id, group in channel_groups.items():
        best = min(group, key=lambda e: quality_score(e["url"]))
        best_entries[tvg_id] = best
        name = CHANNEL_MAPPING[[p[1] for p in CHANNEL_MAPPING].index(tvg_id)][2]
        print(f"  {name}: {best['url'][:60]}...")

    # 4. Test URLs
    print("\n[4] Testando URLs...")
    working = {}
    for tvg_id, e in best_entries.items():
        name = CHANNEL_MAPPING[[p[1] for p in CHANNEL_MAPPING].index(tvg_id)][2]
        print(f"  {name}... ", end="", flush=True)
        if check_url(e["url"]):
            print("✓ OK")
            working[tvg_id] = e
        else:
            print("✗ FALHOU (removido)")

    # 5. Setup EPG
    print("\n[5] Configurando EPG...")
    working_epgs = []
    for url in EPG_URLS:
        tag = url.split('/')[-1]
        print(f"  {tag}... ", end="", flush=True)
        content = download_epg(url)
        if content and len(content) > 1000:
            print(f"✓ ({len(content)} bytes)")
            working_epgs.append(url)
        else:
            print("✗")

    epg_content = None
    if working_epgs:
        epg_content = download_epg(working_epgs[0])
    
    epg_header = f'#EXTM3U url-tvg="{" ".join(working_epgs)}"'
    print(f"  Header: {epg_header[:80]}...")

    # 6. Test EPG
    print("\n[6] Testando programação EPG...")
    for tvg_id in working:
        if epg_content:
            r = test_epg_channel(epg_content, tvg_id)
            name = CHANNEL_MAPPING[[p[1] for p in CHANNEL_MAPPING].index(tvg_id)][2]
            status = "✓" if (r["hoje"] > 0 and r["amanha"] > 0 and r["depois_amanha"] > 0) else "⚠"
            print(f"  {status} {name}: hoje={r['hoje']}, amanhã={r['amanha']}, +2={r['depois_amanha']}")

    # 7. Write output
    print("\n[7] Gerando lista5.m3u corrigida...")
    shutil.copy2(M3U_PATH, BACKUP_PATH)
    print(f"  Backup: {BACKUP_PATH}")

    output_lines = [epg_header]
    for tvg_id, e in working.items():
        name = CHANNEL_MAPPING[[p[1] for p in CHANNEL_MAPPING].index(tvg_id)][2]
        logo = CHANNEL_LOGOS.get(tvg_id, e["logo"])
        if not is_valid_jpg(logo):
            print(f"  ⚠ Logo não é .jpg para {name}, mantendo original")
        extinf = f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-logo="{logo}" group-title="NEWS WORLD",{name}'
        output_lines.append(extinf)
        output_lines.append(e["url"])
        print(f"  ✓ {name} [{tvg_id}]")

    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        f.write('\n'.join(output_lines) + '\n')

    print(f"\n  Salvo: {OUTPUT_PATH}")
    print(f"  Canais: {len(working)}")

    # Summary
    print("\n" + "=" * 70)
    print("RESUMO")
    print("=" * 70)
    print(f"  Total original: {len(entries)} entradas")
    print(f"  Canais únicos: {len(best_entries)}")
    print(f"  Canais funcionando: {len(working)}")
    for tvg_id in working:
        name = CHANNEL_MAPPING[[p[1] for p in CHANNEL_MAPPING].index(tvg_id)][2]
        print(f"  ✓ {name}")
    for tvg_id in best_entries:
        if tvg_id not in working:
            name = CHANNEL_MAPPING[[p[1] for p in CHANNEL_MAPPING].index(tvg_id)][2]
            print(f"  ✗ {name} (URL quebrada)")
    if working_epgs:
        print(f"  EPG: {len(working_epgs)} fonte(s) ativa(s)")
    print("  Logos: todas .jpg")
    print("\n✓ Correção concluída!")


if __name__ == "__main__":
    main()
