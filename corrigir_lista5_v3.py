#!/usr/bin/env python3
import requests
import gzip
import re
import json
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

EPG_URLS = [
    "https://epg.pw/xmltv/epg.xml.gz",
    "https://iptv-epg.org/files/epg-us.xml.gz",
    "https://iptv-epg.org/files/epg-gb.xml.gz",
    "https://epg.pw/xmltv/epg_BR.xml.gz",
]

CHANNEL_MAPPING = {
    "DW English": {"tvg_id": "DWEnglish.de"},
    "France 24": {"tvg_id": "France24.com"},
    "Euronews": {"tvg_id": "Euronews.com"},
    "Sky News UK": {"tvg_id": "SkyNews.com"},
    "Sky News": {"tvg_id": "SkyNews.com"},
    "NHK World": {"tvg_id": "NHKWorld.jp"},
    "TRT World": {"tvg_id": "TRTWorld.tr"},
    "Al Arabiya": {"tvg_id": "AlArabiya.ae"},
    "Al Jazeera English": {"tvg_id": "AlJazeeraEnglish.qa"},
    "CBS News": {"tvg_id": "CBSNews.us"},
    "ABC News": {"tvg_id": "ABCNews.us"},
    "Fox News": {"tvg_id": "Fox.News.us"},
    "FOX News": {"tvg_id": "Fox.News.us"},
    "MSNBC": {"tvg_id": "MSNBC.us"},
    "Bloomberg": {"tvg_id": "BloombergTelevision.us"},
    "CNN": {"tvg_id": "cnn.us"},
    "BBC News": {"tvg_id": "BBCNews.uk"},
    "CGTN": {"tvg_id": "CGTN.cn"},
    "VOA": {"tvg_id": "VOA.us"},
    "Reuters": {"tvg_id": "Reuters.uk"},
    "GLOBO NEWS": {"tvg_id": "GLOBONEWS"},
    "BAND NEWS": {"tvg_id": "Band.News.br"},
    "CNN Brasil": {"tvg_id": "CNNBrasil.br"},
    "JOVEM PAN NEWS": {"tvg_id": "JovemPan.br"},
    "BM&C NEWS": {"tvg_id": "BM&CNews.br"},
    "RECORD NEWS": {"tvg_id": "RecordNews.br"},
    "RAI News 24": {"tvg_id": "RAINews.it"},
    "IRIB": {"tvg_id": "IRIB1.ir"},
    "IRIB 1": {"tvg_id": "IRIB1.ir"},
    "IRIB1": {"tvg_id": "IRIB1.ir"},
    "IRINN": {"tvg_id": "IRINN.ir"},
    "BBC World News": {"tvg_id": "BBCWorldNews.uk"},
    "RT English": {"tvg_id": "RT.com"},
    "Press TV English": {"tvg_id": "PressTV.ir"},
    "CNA": {"tvg_id": "CNA.sg"},
    "Africanews": {"tvg_id": "Africanews.com"},
    "Newsmax": {"tvg_id": "NewsmaxTV.us"},
    "OAN": {"tvg_id": "OAN.us"},
    "NASA TV": {"tvg_id": "NASATV.us"},
    "Yahoo! Finance": {"tvg_id": "YahooFinance.us"},
    "ESPN": {"tvg_id": "ESPN.us"},
    "SPORTV": {"tvg_id": "Sportv.br"},
    "ESPN 2": {"tvg_id": "ESPN2.us"},
    "ESPN 3": {"tvg_id": "ESPN3.us"},
    "ESPN 5": {"tvg_id": "ESPN5.us"},
    "ESPN 6": {"tvg_id": "ESPN6.us"},
}

LOGO_JPG = {
    "GLOBO NEWS": "https://i.imgur.com/Wu4ykxo.jpg",
    "BAND NEWS": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/85/Band_News_TV_2021_Logo.png/800px-Band_News_TV_2021_Logo.png",
    "JOVEM PAN NEWS": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/41/Logotipo_da_TV_Jovem_Pan_News.png/120px-Logotipo_da_TV_Jovem_Pan_News.png",
    "DW English": "https://i.imgur.com/Wu4ykxo.jpg",
    "NEWS WORLD": "https://i.imgur.com/placeholder.jpg",
}

def download_epg(url):
    try:
        resp = requests.get(url, timeout=60, headers={'Accept-Encoding': 'gzip'})
        resp.raise_for_status()
        if url.endswith('.gz'):
            return gzip.decompress(resp.content).decode('utf-8')
        return resp.text
    except:
        return None

def test_epg(epg_content, tvg_id):
    if not epg_content:
        return {"status": "sem_epg", "hoje": 0, "amanha": 0, "depois_amanha": 0}
    
    try:
        root = ET.fromstring(epg_content)
        hoje = datetime.now().strftime("%Y%m%d")
        amanha = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
        depois = (datetime.now() + timedelta(days=2)).strftime("%Y%m%d")
        
        h = a = d = 0
        for prog in root.findall("programme"):
            ch = prog.get("channel", "")
            if ch == tvg_id or tvg_id.lower() in ch.lower():
                start = prog.get("start", "")[:8]
                if start[:8] == hoje: h += 1
                elif start[:8] == amanha: a += 1
                elif start[:8] == depois: d += 1
        
        if h > 0 and a > 0 and d > 0:
            return {"status": "completo", "hoje": h, "amanha": a, "depois_amanha": d}
        elif h > 0 or a > 0:
            return {"status": "parcial", "hoje": h, "amanha": a, "depois_amanha": d}
        return {"status": "sem_epg", "hoje": h, "amanha": a, "depois_amanha": d}
    except:
        return {"status": "sem_epg", "hoje": 0, "amanha": 0, "depois_amanha": 0}

def parse_m3u(path):
    channels = []
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXTINF:'):
            url = lines[i+1].strip() if i+1 < len(lines) else ""
            name = re.search(r',(.+)$', line)
            name = name.group(1).strip() if name else ""
            tvg_id = re.search(r'tvg-id="([^"]*)"', line)
            tvg_id = tvg_id.group(1) if tvg_id else ""
            tvg_logo = re.search(r'tvg-logo="([^"]*)"', line)
            tvg_logo = tvg_logo.group(1) if tvg_logo else ""
            group = re.search(r'group-title="([^"]*)"', line)
            group = group.group(1) if group else ""
            channels.append({"extinf": line, "url": url, "name": name, "tvg_id": tvg_id, "tvg_logo": tvg_logo, "group": group})
            i += 2
        else:
            i += 1
    return channels

def fix_logo(logo):
    if not logo:
        return logo
    p = urlparse(logo)
    if p.path.lower().endswith('.svg') or p.path.lower().endswith('.png') or p.path.lower().endswith('.webp'):
        return logo.rsplit('.', 1)[0] + '.jpg'
    return logo

def main():
    print("=" * 60)
    print("CORRECAO lista5.m3u")
    print("=" * 60)
    
    channels = parse_m3u("lista5.m3u")
    print(f"Canais encontrados: {len(channels)}")
    
    print("\nBaixando EPGs...")
    epg_contents = {}
    for url in EPG_URLS[:3]:
        name = url.split('/')[-1][:20]
        print(f"  {name}...")
        content = download_epg(url)
        if content and len(content) > 1000:
            epg_contents[url] = content
            print(f"    OK ({len(content):,} bytes)")
        else:
            print(f"    FALHOU")
    
    print("\nProcessando canais...")
    processed = []
    with_epg = []
    without_epg = []
    
    for ch in channels:
        name = ch["name"]
        tvg_id = ch["tvg_id"]
        tvg_logo = ch["tvg_logo"]
        group = ch["group"]
        url = ch["url"]
        
        if not tvg_id and name in CHANNEL_MAPPING:
            tvg_id = CHANNEL_MAPPING[name].get("tvg_id", "")
        
        if not tvg_logo:
            if name in LOGO_JPG:
                tvg_logo = LOGO_JPG[name]
        
        tvg_logo = fix_logo(tvg_logo)
        
        epg_result = {"status": "sem_epg", "hoje": 0, "amanha": 0, "depois_amanha": 0}
        epg_url = ""
        
        if tvg_id:
            for epg_url_test, content in epg_contents.items():
                epg_result = test_epg(content, tvg_id)
                if epg_result["status"] != "sem_epg":
                    epg_url = epg_url_test
                    break
        
        attrs = []
        if tvg_id: attrs.append(f'tvg-id="{tvg_id}"')
        if tvg_logo: attrs.append(f'tvg-logo="{tvg_logo}"')
        if group: attrs.append(f'group-title="{group}"')
        
        new_extinf = f'#EXTINF:-1 {" ".join(attrs)},{name}'
        
        if epg_result["status"] != "sem_epg":
            with_epg.append({"name": name, "epg": epg_result, "tvg_id": tvg_id})
        else:
            without_epg.append({"name": name, "tvg_id": tvg_id})
        
        processed.append({"extinf": new_extinf, "url": url, "name": name, "epg": epg_result, "epg_url": epg_url})
    
    unique = {}
    for ch in processed:
        key = ch["extinf"] + ch["url"]
        if key not in unique:
            unique[key] = ch
    
    epg_header = ",".join(list(set(ch["epg_url"] for ch in unique.values() if ch["epg_url"]))[:3])
    
    print(f"\nCanais com EPG: {len(with_epg)}")
    print(f"Canais sem EPG: {len(without_epg)}")
    
    with open("lista5.m3u", 'w', encoding='utf-8') as f:
        if epg_header:
            f.write(f'#EXTM3U x-tvg-url="{epg_header}"\n')
        else:
            f.write("#EXTM3U\n")
        for ch in unique.values():
            f.write(ch["extinf"] + "\n")
            f.write(ch["url"] + "\n")
    
    print(f"\nOK! lista5.m3u atualizada!")
    print(f"Canais finais: {len(unique)}")
    
    report = [f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
              f"Canais com EPG: {len(with_epg)}",
              f"Canais sem EPG: {len(without_epg)}",
              "", "CANAIS COM EPG:"]
    for ch in with_epg[:30]:
        e = ch["epg"]
        report.append(f"  {ch['name'][:35]:<35} Hoje:{e['hoje']:>2} Ama:{e['amanha']:>2} Dep:{e['depois_amanha']:>2}")
    
    with open("lista5_relatorio.txt", 'w', encoding='utf-8') as f:
        f.write("\n".join(report))
    
    print("\nRelatorio: lista5_relatorio.txt")

if __name__ == "__main__":
    main()
