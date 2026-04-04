#!/usr/bin/env python3
import requests
import gzip
import re
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import xml.etree.ElementTree as ET

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
    "DW English": "https://i.imgur.com/8MRNFb9.jpg",
    "DW Arabic": "https://i.imgur.com/8MRNFb9.jpg",
    "DW Español": "https://i.imgur.com/8MRNFb9.jpg",
    "RT English": "https://i.imgur.com/8MRNFb9.jpg",
    "RT Arabic": "https://i.imgur.com/8MRNFb9.jpg",
    "RT en Español": "https://i.imgur.com/8MRNFb9.jpg",
    "France 24": "https://i.imgur.com/BFMMPwP.jpg",
    "France 24 English": "https://i.imgur.com/BFMMPwP.jpg",
    "Euronews": "https://i.imgur.com/BFMMPwP.jpg",
    "Sky News": "https://i.imgur.com/ZsPb8nL.jpg",
    "Sky News UK": "https://i.imgur.com/ZsPb8nL.jpg",
    "NHK World": "https://i.imgur.com/nhkworld.jpg",
    "TRT World": "https://i.imgur.com/NCvRHC3.jpg",
    "TRT Haber": "https://i.imgur.com/NCvRHC3.jpg",
    "Al Arabiya": "https://i.imgur.com/NXFkYFj.jpg",
    "Al Jazeera English": "https://i.imgur.com/NXFkYFj.jpg",
    "Al Jazeera": "https://i.imgur.com/NXFkYFj.jpg",
    "CBS News": "https://i.imgur.com/cbsnews.jpg",
    "ABC News": "https://i.imgur.com/abcnews.jpg",
    "Fox News": "https://i.imgur.com/foxnews.jpg",
    "FOX News": "https://i.imgur.com/foxnews.jpg",
    "MSNBC": "https://i.imgur.com/JmKvove.jpg",
    "Bloomberg": "https://i.imgur.com/idRFfhY.jpg",
    "Bloomberg US": "https://i.imgur.com/idRFfhY.jpg",
    "CNN": "https://i.imgur.com/xWglicB.jpg",
    "BBC News": "https://i.imgur.com/vSz2WEp.jpg",
    "BBC World News": "https://i.imgur.com/vSz2WEp.jpg",
    "CGTN": "https://i.imgur.com/cgtn.jpg",
    "VOA": "https://i.imgur.com/rtRnlqN.jpg",
    "Reuters": "https://i.imgur.com/4xSEoNK.jpg",
    "GLOBO NEWS": "https://i.imgur.com/Wu4ykxo.jpg",
    "BAND NEWS": "https://i.imgur.com/jCZzNjF.jpg",
    "CNN Brasil": "https://i.imgur.com/cnnbrasil.jpg",
    "CNN BRASIL": "https://i.imgur.com/cnnbrasil.jpg",
    "JOVEM PAN NEWS": "https://i.imgur.com/aqgaka0.jpg",
    "Jovem Pan News": "https://i.imgur.com/aqgaka0.jpg",
    "BM&C NEWS": "https://i.imgur.com/tyW3Ppf.jpg",
    "RECORD NEWS": "https://i.imgur.com/record.jpg",
    "RAI News 24": "https://i.imgur.com/rainews.jpg",
    "RAI NEWS24": "https://i.imgur.com/rainews.jpg",
    "IRIB 1": "https://i.imgur.com/8tzsC9h.jpg",
    "IRIB 2": "https://i.imgur.com/8tzsC9h.jpg",
    "IRIB 3": "https://i.imgur.com/8tzsC9h.jpg",
    "IRIB1": "https://i.imgur.com/8tzsC9h.jpg",
    "IRIB2": "https://i.imgur.com/8tzsC9h.jpg",
    "IRIB3": "https://i.imgur.com/8tzsC9h.jpg",
    "IRIB4": "https://i.imgur.com/8tzsC9h.jpg",
    "IRINN": "https://i.imgur.com/8tzsC9h.jpg",
    "Press TV English": "https://i.imgur.com/8tzsC9h.jpg",
    "CNA": "https://i.imgur.com/xJZ9ChT.jpg",
    "Africanews": "https://i.imgur.com/jHJR3LN.jpg",
    "NDTV India": "https://i.imgur.com/ndtv.jpg",
    "WION": "https://i.imgur.com/wion.jpg",
    "Newsmax": "https://i.imgur.com/newsmax.jpg",
    "OAN": "https://i.imgur.com/oan.jpg",
    "NASA TV": "https://i.imgur.com/nasa.jpg",
    "Yahoo! Finance": "https://i.imgur.com/Y3vQaf5.jpg",
    "SPORTV": "https://i.imgur.com/sportv.jpg",
    "BFM TV": "https://i.imgur.com/bfmtv.jpg",
    "BFM Business": "https://i.imgur.com/bfmbusiness.jpg",
    "Telesur English": "https://i.imgur.com/telesur.jpg",
    "TELESUR": "https://i.imgur.com/telesur.jpg",
    "teleSUR": "https://i.imgur.com/telesur.jpg",
    "+24": "https://i.imgur.com/24horas.jpg",
    "tagesschau24": "https://i.imgur.com/tagesschau.jpg",
    "Global News": "https://i.imgur.com/IZFEJsu.jpg",
    "Global News Canada": "https://i.imgur.com/IZFEJsu.jpg",
    "ESPN": "https://i.imgur.com/espn.jpg",
    "ESPN 2": "https://i.imgur.com/espn2.jpg",
    "ESPN 3": "https://i.imgur.com/espn3.jpg",
}

def is_valid_jpg_url(url):
    if not url:
        return False
    return url.lower().endswith('.jpg') or url.lower().endswith('.jpeg') or 'imgur.com' in url.lower()

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

def main():
    print("=" * 60)
    print("CORRECAO lista5.m3u - ULTRA RAPIDA")
    print("=" * 60)
    
    channels = parse_m3u("lista5.m3u")
    print(f"Canais encontrados: {len(channels)}")
    
    print("\nProcessando canais...")
    processed = []
    matched = 0
    logo_added = 0
    logo_fixed = 0
    
    for ch in channels:
        name = ch["name"]
        tvg_id = ch["tvg_id"]
        tvg_logo = ch["tvg_logo"]
        group = ch["group"]
        url = ch["url"]
        
        if not tvg_id and name in CHANNEL_MAPPING:
            tvg_id = CHANNEL_MAPPING[name]
            matched += 1
        
        if not tvg_logo:
            if name in LOGO_JPG:
                tvg_logo = LOGO_JPG[name]
                logo_added += 1
        elif not is_valid_jpg_url(tvg_logo):
            if name in LOGO_JPG:
                tvg_logo = LOGO_JPG[name]
                logo_fixed += 1
            else:
                tvg_logo = ""
        
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
    
    print(f"\nResumo:")
    print(f"  tvg-id adicionados: {matched}")
    print(f"  logos adicionados: {logo_added}")
    print(f"  logos corrigidos: {logo_fixed}")
    print(f"  canais unicos: {len(unique)}")
    
    with open("lista5.m3u", 'w', encoding='utf-8') as f:
        f.write(f'#EXTM3U x-tvg-url="{EPG_URL}"\n')
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
        f.write(f"logos adicionados: {logo_added}\n")
        f.write(f"logos corrigidos: {logo_fixed}\n")
        f.write(f"EPG: {EPG_URL}\n")
    
    print("\nRelatorio: lista5_relatorio.txt")

if __name__ == "__main__":
    main()
