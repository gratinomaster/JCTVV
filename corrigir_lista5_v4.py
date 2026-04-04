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

EPG_URL = "https://epg.pw/xmltv/epg.xml.gz"

CHANNEL_MAPPING = {
    "DW English": "DWEnglish.de",
    "France 24": "France24.com",
    "Euronews": "Euronews.com",
    "Sky News UK": "SkyNews.com",
    "Sky News": "SkyNews.com",
    "NHK World": "NHKWorld.jp",
    "TRT World": "TRTWorld.tr",
    "TRT Haber": "TRTHaber.tr",
    "Al Arabiya": "AlArabiya.ae",
    "Al Jazeera English": "AlJazeeraEnglish.qa",
    "Al Jazeera": "AlJazeeraEnglish.qa",
    "CBS News": "CBSNews.us",
    "ABC News": "ABCNews.us",
    "Fox News": "Fox.News.us",
    "FOX News": "Fox.News.us",
    "MSNBC": "MSNBC.us",
    "Bloomberg": "BloombergTelevision.us",
    "Bloomberg US": "BloombergTelevision.us",
    "CNN": "cnn.us",
    "BBC News": "BBCNews.uk",
    "BBC World News": "BBCWorldNews.uk",
    "CGTN": "CGTN.cn",
    "VOA": "VOA.us",
    "Reuters": "Reuters.uk",
    "GLOBO NEWS": "GLOBONEWS",
    "BAND NEWS": "Band.News.br",
    "CNN Brasil": "CNNBrasil.br",
    "CNN BRASIL": "CNNBrasil.br",
    "JOVEM PAN NEWS": "JovemPan.br",
    "Jovem Pan News": "JovemPan.br",
    "BM&C NEWS": "BM&CNews.br",
    "RECORD NEWS": "RecordNews.br",
    "RAI News 24": "RAINews.it",
    "RAI NEWS24": "RAINews.it",
    "IRIB 1": "IRIB1.ir",
    "IRIB 2": "IRIB2.ir",
    "IRIB 3": "IRIB3.ir",
    "IRIB1": "IRIB1.ir",
    "IRIB2": "IRIB2.ir",
    "IRIB3": "IRIB3.ir",
    "IRIB4": "IRIB4.ir",
    "IRINN": "IRINN.ir",
    "RT English": "RT.com",
    "RT": "RT.com",
    "RT Arabic": "RT.com",
    "RT en Español": "RT.com",
    "Press TV English": "PressTV.ir",
    "CNA": "CNA.sg",
    "Africanews": "Africanews.com",
    "NDTV India": "NDTV.in",
    "WION": "WION.in",
    "Newsmax": "NewsmaxTV.us",
    "OAN": "OAN.us",
    "NASA TV": "NASATV.us",
    "Yahoo! Finance": "YahooFinance.us",
    "ESPN": "ESPN.us",
    "SPORTV": "Sportv.br",
    "ESPN 2": "ESPN2.us",
    "ESPN 3": "ESPN3.us",
    "ESPN 5": "ESPN5.us",
    "ESPN 6": "ESPN6.us",
    "Telesur English": "TelesurEnglish.ve",
    "TELESUR": "TelesurEnglish.ve",
    "teleSUR": "TelesurEnglish.ve",
    "BFM TV": "BFMTV.fr",
    "BFM Business": "BFMBusiness.fr",
    "tagesschau24": "tagesschau24.de",
    "+24": "24Horas.es",
    "24 HORAS CL": "24Horas.es",
    "TV5Monde Info": "TV5MondeInfo.fr",
    "Class CNBC": "ClassCNBC.it",
    "Global News": "GlobalNewsCanada.ca",
    "Global News Canada": "GlobalNewsCanada.ca",
}

LOGO_JPG = {
    "GLOBO NEWS": "https://i.imgur.com/Wu4ykxo.jpg",
    "BAND NEWS": "https://i.imgur.com/jCZzNjF.jpg",
    "JOVEM PAN NEWS": "https://i.imgur.com/aqgaka0.jpg",
    "DW English": "https://i.imgur.com/8MRNFb9.jpg",
    "RT English": "https://i.imgur.com/8MRNFb9.jpg",
    "NEWS WORLD": "https://i.imgur.com/placeholder.jpg",
    "Bloomberg": "https://i.imgur.com/idRFfhY.jpg",
}

def download_epg(url):
    try:
        resp = requests.get(url, timeout=90, headers={'Accept-Encoding': 'gzip'})
        resp.raise_for_status()
        if url.endswith('.gz'):
            return gzip.decompress(resp.content).decode('utf-8')
        return resp.text
    except Exception as e:
        print(f"Erro: {e}")
        return None

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
    if p.path.lower().endswith('.svg') or p.path.lower().endswith('.png') or p.path.lower().endswith('.webp') or p.path.lower().endswith('.gif'):
        return logo.rsplit('.', 1)[0] + '.jpg'
    return logo

def main():
    print("=" * 60)
    print("CORRECAO lista5.m3u - Rapida")
    print("=" * 60)
    
    channels = parse_m3u("lista5.m3u")
    print(f"Canais encontrados: {len(channels)}")
    
    print("\nBaixando EPG principal...")
    epg_content = download_epg(EPG_URL)
    if epg_content:
        print(f"  OK ({len(epg_content):,} bytes)")
    else:
        print("  FALHOU")
        epg_content = None
    
    print("\nProcessando canais...")
    processed = []
    matched = 0
    added_logo = 0
    fixed_logo = 0
    
    for ch in channels:
        name = ch["name"]
        tvg_id = ch["tvg_id"]
        tvg_logo = ch["tvg_logo"]
        group = ch["group"]
        url = ch["url"]
        
        if not tvg_id and name in CHANNEL_MAPPING:
            tvg_id = CHANNEL_MAPPING[name]
            matched += 1
        
        if not tvg_logo and name in LOGO_JPG:
            tvg_logo = LOGO_JPG[name]
            added_logo += 1
        
        tvg_logo = fix_logo(tvg_logo)
        if tvg_logo and not tvg_logo.endswith('.jpg') and not tvg_logo.endswith('.png'):
            fixed_logo += 1
        
        attrs = []
        if tvg_id: attrs.append(f'tvg-id="{tvg_id}"')
        if tvg_logo: attrs.append(f'tvg-logo="{tvg_logo}"')
        if group: attrs.append(f'group-title="{group}"')
        
        new_extinf = f'#EXTINF:-1 {" ".join(attrs)},{name}'
        
        processed.append({"extinf": new_extinf, "url": url, "name": name, "tvg_id": tvg_id})
    
    unique = {}
    for ch in processed:
        key = ch["extinf"] + ch["url"]
        if key not in unique:
            unique[key] = ch
    
    epg_header = EPG_URL if epg_content else ""
    
    print(f"\nResumo:")
    print(f"  tvg-id adicionados: {matched}")
    print(f"  logos adicionados: {added_logo}")
    print(f"  logos corrigidos: {fixed_logo}")
    print(f"  canais unicos: {len(unique)}")
    
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
    
    with open("lista5_relatorio.txt", 'w', encoding='utf-8') as f:
        f.write(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"Canais encontrados: {len(channels)}\n")
        f.write(f"Canais unicos finais: {len(unique)}\n")
        f.write(f"tvg-id adicionados: {matched}\n")
        f.write(f"logos adicionados: {added_logo}\n")
        f.write(f"logos corrigidos: {fixed_logo}\n")
        f.write(f"EPG: {EPG_URL if epg_content else 'N/A'}\n")
        f.write(f"\nCanais com tvg-id:\n")
        for ch in processed:
            if ch["tvg_id"]:
                f.write(f"  {ch['name'][:40]:<40} -> {ch['tvg_id']}\n")
    
    print("\nRelatorio: lista5_relatorio.txt")

if __name__ == "__main__":
    main()
