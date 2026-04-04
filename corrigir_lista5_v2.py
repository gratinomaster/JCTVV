#!/usr/bin/env python3
import requests
import gzip
import re
import base64
import json
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

EPG_SOURCES = {
    "global": "https://epg.pw/xmltv/epg.xml.gz",
    "us": "https://iptv-epg.org/files/epg-us.xml.gz",
    "br": "https://epg.pw/xmltv/epg_BR.xml.gz",
    "uk": "https://iptv-epg.org/files/epg-gb.xml.gz",
    "es": "https://iptv-epg.org/files/epg-es.xml.gz",
    "fr": "https://iptv-epg.org/files/epg-fr.xml.gz",
    "de": "https://iptv-epg.org/files/epg-de.xml.gz",
    "cl": "https://iptv-epg.org/files/epg-cl.xml.gz",
}

CHANNEL_EPG_MAPPING = {
    "DW English": {"tvg_id": "DWEnglish.de", "epg_key": "de"},
    "DW Arabic": {"tvg_id": "DWArabic.de", "epg_key": "de"},
    "DW Español": {"tvg_id": "DWEspanol.de", "epg_key": "es"},
    "RT English": {"tvg_id": "RT.com", "epg_key": "uk"},
    "RT Arabic": {"tvg_id": "RT.com", "epg_key": "uk"},
    "RT en Español": {"tvg_id": "RT.com", "epg_key": "es"},
    "France 24 English": {"tvg_id": "France24.com", "epg_key": "fr"},
    "France 24": {"tvg_id": "France24.com", "epg_key": "fr"},
    "France 24 Arabic": {"tvg_id": "France24.com", "epg_key": "fr"},
    "France24 Espanol": {"tvg_id": "France24Espanol", "epg_key": "es"},
    "France24 France": {"tvg_id": "France24.com", "epg_key": "fr"},
    "Euronews English": {"tvg_id": "Euronews.com", "epg_key": "uk"},
    "Euronews": {"tvg_id": "Euronews.com", "epg_key": "fr"},
    "Euronews Español": {"tvg_id": "Euronews.es", "epg_key": "es"},
    "EURONEWS EN ITALIANO": {"tvg_id": "Euronews.com", "epg_key": "fr"},
    "Sky News UK": {"tvg_id": "SkyNews.com", "epg_key": "uk"},
    "SKY NEWS": {"tvg_id": "SkyNews.com", "epg_key": "uk"},
    "Sky News": {"tvg_id": "SkyNews.uk", "epg_key": "uk"},
    "Sky News Arabia": {"tvg_id": "SkyNews.com", "epg_key": "uk"},
    "Sky News Extra": {"tvg_id": "SkyNewsExtra", "epg_key": "uk"},
    "Sky News Extra 1": {"tvg_id": "SkyNewsExtra1.au", "epg_key": "uk"},
    "Sky News Extra 2": {"tvg_id": "SkyNewsExtra2.au", "epg_key": "uk"},
    "Sky News Extra 3": {"tvg_id": "SkyNewsExtra3.au", "epg_key": "uk"},
    "Sky News Arabe": {"tvg_id": "SkyNews.com", "epg_key": "uk"},
    "NH World": {"tvg_id": "NHKWorld.jp", "epg_key": "uk"},
    "TRT World": {"tvg_id": "TRTWorld.tr", "epg_key": "uk"},
    "TRT Haber": {"tvg_id": "TRTHaber.tr", "epg_key": "uk"},
    "TRT Arabi": {"tvg_id": "TRTArabi.tr", "epg_key": "uk"},
    "Al Arabiya": {"tvg_id": "AlArabiya.ae", "epg_key": "uk"},
    "Al Jazeera English": {"tvg_id": "AlJazeeraEnglish.qa", "epg_key": "uk"},
    "Al Jazeera Arabic": {"tvg_id": "AlJazeeraArabic.qa", "epg_key": "uk"},
    "Al Jazeera Mubasher": {"tvg_id": "AlJazeeraMubasher.qa", "epg_key": "uk"},
    "Al Jazeera": {"tvg_id": "AlJazeeraEnglish.qa", "epg_key": "uk"},
    "Al Jazeera Balkans": {"tvg_id": "AlJazeeraBalkans.ba", "epg_key": "uk"},
    "Aljazeera Balkans": {"tvg_id": "AlJazeeraBalkans.ba", "epg_key": "uk"},
    "Aljazeera English": {"tvg_id": "AlJazeeraEnglish.qa", "epg_key": "uk"},
    "Aljazeera Channel": {"tvg_id": "AlJazeeraChannel.qa", "epg_key": "uk"},
    "Aljazeera Arabic": {"tvg_id": "AlJazeeraArabic.qa", "epg_key": "uk"},
    "CBS News": {"tvg_id": "CBSNews.us", "epg_key": "us"},
    "ABC News": {"tvg_id": "ABCNews.us", "epg_key": "us"},
    "ABC": {"tvg_id": "ABCNews.us", "epg_key": "us"},
    "Fox News": {"tvg_id": "Fox.News.us", "epg_key": "us"},
    "FOX News": {"tvg_id": "Fox.News.us", "epg_key": "us"},
    "FOX NEWS USA": {"tvg_id": "Fox.News.us", "epg_key": "us"},
    "Fox Business": {"tvg_id": "FRBD4100006OC", "epg_key": "us"},
    "MSNBC": {"tvg_id": "MSNBC.us", "epg_key": "us"},
    "Bloomberg US": {"tvg_id": "BloombergTelevision.us", "epg_key": "us"},
    "Bloomberg": {"tvg_id": "BloombergTelevision.us", "epg_key": "us"},
    "Bloomberg Television": {"tvg_id": "BloombergTelevision.us", "epg_key": "us"},
    "Bloomberg Politics": {"tvg_id": "BloombergTVEMEALiveEvent.us", "epg_key": "us"},
    "Bloomberg Europe Event": {"tvg_id": "BloombergTVEMEALiveEvent.us", "epg_key": "uk"},
    "Bloomberg EU": {"tvg_id": "BloombergTelevision.us", "epg_key": "uk"},
    "Bloomberg Asia": {"tvg_id": "BloombergTelevision.us", "epg_key": "uk"},
    "CNA": {"tvg_id": "CNA.sg", "epg_key": "uk"},
    "Africanews": {"tvg_id": "Africanews.com", "epg_key": "fr"},
    "NDTV India": {"tvg_id": "NDTV.in", "epg_key": "uk"},
    "WION": {"tvg_id": "WION.in", "epg_key": "uk"},
    "Reuters": {"tvg_id": "Reuters.uk", "epg_key": "uk"},
    "REUTERS": {"tvg_id": "Reuters.uk", "epg_key": "uk"},
    "VOA": {"tvg_id": "VOA.us", "epg_key": "us"},
    "VOA Persian": {"tvg_id": "VOA.us", "epg_key": "uk"},
    "RAI News 24": {"tvg_id": "RAINews.it", "epg_key": "uk"},
    "RAI NEWS24": {"tvg_id": "RAINews.it", "epg_key": "uk"},
    "IRIB": {"tvg_id": "IRIB1.ir", "epg_key": "uk"},
    "IRIB 1": {"tvg_id": "IRIB1.ir", "epg_key": "uk"},
    "IRIB 2": {"tvg_id": "IRIB2.ir", "epg_key": "uk"},
    "IRIB 3": {"tvg_id": "IRIB3.ir", "epg_key": "uk"},
    "IRIB1": {"tvg_id": "IRIB1.ir", "epg_key": "uk"},
    "IRIB2": {"tvg_id": "IRIB2.ir", "epg_key": "uk"},
    "IRIB3": {"tvg_id": "IRIB3.ir", "epg_key": "uk"},
    "IRIB4": {"tvg_id": "IRIB4.ir", "epg_key": "uk"},
    "IRINN": {"tvg_id": "IRINN.ir", "epg_key": "uk"},
    "IFILM IR": {"tvg_id": "IFilm.ir", "epg_key": "uk"},
    "Press TV English": {"tvg_id": "PressTV.ir", "epg_key": "uk"},
    "HispanTV": {"tvg_id": "HispanTV.ir", "epg_key": "es"},
    "Iran International": {"tvg_id": "IranInternational.uk", "epg_key": "uk"},
    "TV5Monde Info": {"tvg_id": "TV5MondeInfo.fr", "epg_key": "fr"},
    "Class CNBC": {"tvg_id": "ClassCNBC.it", "epg_key": "uk"},
    "BBC News TV": {"tvg_id": "BBCNews.uk", "epg_key": "uk"},
    "BBC News": {"tvg_id": "BBCNews.uk", "epg_key": "uk"},
    "BBC Arabic": {"tvg_id": "BBCArabic.uk", "epg_key": "uk"},
    "BBC World News North America": {"tvg_id": "BBCWorldNews.uk", "epg_key": "us"},
    "BBC News (North America)": {"tvg_id": "BBCWorldNews.uk", "epg_key": "us"},
    "BBC World News": {"tvg_id": "BBCWorldNews.uk", "epg_key": "uk"},
    "BBC News Radio": {"tvg_id": "BBCWorldService.uk", "epg_key": "uk"},
    "BBC News Asia Pacific": {"tvg_id": "BBCWorldNews.uk", "epg_key": "uk"},
    "CGTN": {"tvg_id": "CGTN.cn", "epg_key": "uk"},
    "CGTN Arabic": {"tvg_id": "CGTNArabic.cn", "epg_key": "uk"},
    "CGTN Documentary": {"tvg_id": "CGTNDocumentary.cn", "epg_key": "uk"},
    "CGTN Español": {"tvg_id": "CGTNSpanish.cn", "epg_key": "es"},
    "CNN": {"tvg_id": "cnn.us", "epg_key": "us"},
    "CNN INTERNACIONAL": {"tvg_id": "cnn.us", "epg_key": "us"},
    "CNN INTERNATIONAL": {"tvg_id": "cnn.us", "epg_key": "us"},
    "Global News": {"tvg_id": "GlobalNewsCanada.ca", "epg_key": "uk"},
    "Global News Canada": {"tvg_id": "GlobalNewsCanada.ca", "epg_key": "uk"},
    "GLOBO NEWS": {"tvg_id": "GLOBONEWS", "epg_key": "br"},
    "BAND NEWS": {"tvg_id": "Band.News.br", "epg_key": "br"},
    "CNN BRASIL": {"tvg_id": "CNNBrasil.br", "epg_key": "br"},
    "CNN Brasil": {"tvg_id": "CNNBrasil.br", "epg_key": "br"},
    "JOVEM PAN NEWS": {"tvg_id": "JovemPan.br", "epg_key": "br"},
    "Jovem Pan News": {"tvg_id": "JovemPan.br", "epg_key": "br"},
    "BM&C NEWS": {"tvg_id": "BM&CNews.br", "epg_key": "br"},
    "SBT News": {"tvg_id": "SBTNews.br", "epg_key": "br"},
    "RECORD NEWS": {"tvg_id": "RecordNews.br", "epg_key": "br"},
    "CNN BRASIL MONEY": {"tvg_id": "CNNBrasil.br", "epg_key": "br"},
    "CNN Money": {"tvg_id": "CNNBrasil.br", "epg_key": "br"},
    "TIMES BRASIL HD": {"tvg_id": "TimesBrasil.br", "epg_key": "br"},
    "TVG Eventos": {"tvg_id": "TVG.es", "epg_key": "es"},
    "+24": {"tvg_id": "24Horas.es", "epg_key": "es"},
    "24 HORAS CL": {"tvg_id": "24Horas.es", "epg_key": "cl"},
    "24Horas": {"tvg_id": "24Horas.es", "epg_key": "es"},
    "tagesschau24": {"tvg_id": "tagesschau24.de", "epg_key": "de"},
    "RTVE 24h": {"tvg_id": "24Horas.es", "epg_key": "es"},
    "Canal 24 Horas Canarias": {"tvg_id": "24HorasCanarias.es", "epg_key": "es"},
    "Canal 24 Horas Catalunya": {"tvg_id": "24HorasCatalunya.es", "epg_key": "es"},
    "El Trece": {"tvg_id": "ElTrece.ar", "epg_key": "uk"},
    "CNN CHILE": {"tvg_id": "CNNChile.cl", "epg_key": "cl"},
    "MEGANOTICIAS": {"tvg_id": "Mega.cl", "epg_key": "cl"},
    "Emol TV": {"tvg_id": "EmolTV.cl", "epg_key": "cl"},
    "UCV TV": {"tvg_id": "UCVTV.cl", "epg_key": "cl"},
    "COOPERATIVA": {"tvg_id": "Cooperativa.cl", "epg_key": "cl"},
    "LA RED": {"tvg_id": "LaRed.cl", "epg_key": "cl"},
    "RADIO T13": {"tvg_id": "T13Radio.cl", "epg_key": "cl"},
    "RADIO PUDAHUEL": {"tvg_id": "Pudahuel.cl", "epg_key": "cl"},
    "RADIO DUNA": {"tvg_id": "RadioDuna.cl", "epg_key": "cl"},
    "NTV NEWS 24": {"tvg_id": "NTVNews24.jp", "epg_key": "uk"},
    "UN Web TV": {"tvg_id": "UNWebTV.us", "epg_key": "us"},
    "NASA TV": {"tvg_id": "NASATV.us", "epg_key": "us"},
    "NASA TV MEDIA": {"tvg_id": "NASATV.us", "epg_key": "us"},
    "Newsmax": {"tvg_id": "NewsmaxTV.us", "epg_key": "us"},
    "Newsmax TV": {"tvg_id": "NewsmaxTV.us", "epg_key": "us"},
    "OAN": {"tvg_id": "OAN.us", "epg_key": "us"},
    "Cheddar News": {"tvg_id": "CheddarNews.us", "epg_key": "us"},
    "CNBC Indonesia": {"tvg_id": "CNBCIndonesia.id", "epg_key": "uk"},
    "CNN Indonesia": {"tvg_id": "CNN.Indonesia.id", "epg_key": "uk"},
    "NewsNet": {"tvg_id": "W14DKD2.us", "epg_key": "us"},
    "ABC News (Australia)": {"tvg_id": "ABCNewsAustralia.au", "epg_key": "uk"},
    "ABC Radio (Australia)": {"tvg_id": "ABCRadioAustralia.au", "epg_key": "uk"},
    "Current Time TV": {"tvg_id": "CurrentTimeTV.us", "epg_key": "us"},
    "VOA TV Africa": {"tvg_id": "VoATV.us", "epg_key": "fr"},
    "SABC News": {"tvg_id": "ABCNews.us", "epg_key": "uk"},
    "Sputnik Radio": {"tvg_id": "SputnikInternational.com", "epg_key": "uk"},
    "Expressen TV": {"tvg_id": "ExpressenTV.se", "epg_key": "uk"},
    "Yahoo! Finance": {"tvg_id": "YahooFinance.us", "epg_key": "us"},
    "The Wall Street Journal Live": {"tvg_id": "TheWallStreetJournalLive.us", "epg_key": "us"},
    "CAM CAPITOLIO EEUU": {"tvg_id": "USCapitol.us", "epg_key": "us"},
    "PRESIDENCIA USA": {"tvg_id": "USCapitol.us", "epg_key": "us"},
    "PENTAGONO USA": {"tvg_id": "USCapitol.us", "epg_key": "us"},
    "Zee Business": {"tvg_id": "ZeeBusiness.in", "epg_key": "uk"},
    "Arirang": {"tvg_id": "ArirangTV.kr", "epg_key": "uk"},
    "Arirang TV": {"tvg_id": "ArirangTV.kr", "epg_key": "uk"},
    "Astro Awani": {"tvg_id": "AstroAwani.my", "epg_key": "uk"},
    "Aaj Tak": {"tvg_id": "AajTak.in", "epg_key": "uk"},
    "India Today": {"tvg_id": "IndiaToday.in", "epg_key": "uk"},
    "Asharq News": {"tvg_id": "AsharqNews.sa", "epg_key": "uk"},
    "ATN News": {"tvg_id": "ATNNews.af", "epg_key": "uk"},
    "Afghanistan International": {"tvg_id": "AfghanistanInternational.uk", "epg_key": "uk"},
    "Aleph News": {"tvg_id": "AlephNews.ro", "epg_key": "uk"},
    "Alert": {"tvg_id": "AlertTV.gr", "epg_key": "uk"},
    "Telesur English": {"tvg_id": "TelesurEnglish.ve", "epg_key": "es"},
    "TELESUR": {"tvg_id": "TelesurEnglish.ve", "epg_key": "es"},
    "TELESUR ENG": {"tvg_id": "TelesurEnglish.ve", "epg_key": "es"},
    "teleSUR": {"tvg_id": "TelesurEnglish.ve", "epg_key": "es"},
    "teleSUR English": {"tvg_id": "TelesurEnglish.ve", "epg_key": "es"},
    "teleSUR Español": {"tvg_id": "TelesurEnglish.ve", "epg_key": "es"},
    "TV Rain": {"tvg_id": "TVRain.ru", "epg_key": "uk"},
    "Venezolana de Televisión": {"tvg_id": "VTV.ve", "epg_key": "es"},
    "AP Direct": {"tvg_id": "APDirect.us", "epg_key": "us"},
    "AP Live Choice": {"tvg_id": "APLiveChoice.us", "epg_key": "us"},
    "BFM Business": {"tvg_id": "BFMBusiness.fr", "epg_key": "fr"},
    "BFM TV": {"tvg_id": "BFMTV.fr", "epg_key": "fr"},
    "BFM Lyon": {"tvg_id": "BFMLyon.fr", "epg_key": "fr"},
    "CNews": {"tvg_id": "CNews.fr", "epg_key": "fr"},
    "Black News Channel": {"tvg_id": "BlackNewsChannel.us", "epg_key": "us"},
    "Fox Weather": {"tvg_id": "FOXWeather.us", "epg_key": "us"},
    "FOX WEATHER": {"tvg_id": "FOXWeather.us", "epg_key": "us"},
}

LOGO_MAPPING = {
    "DW English": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/75/DW_Logo.svg/512px-DW_Logo.svg.png",
    "DW Arabic": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/75/DW_Logo.svg/512px-DW_Logo.svg.png",
    "DW Español": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/75/DW_Logo.svg/512px-DW_Logo.svg.png",
    "RT English": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a0/Russia_today_logo.svg/512px-Russia_today_logo.svg.png",
    "France 24": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/07/France_24.svg/512px-France_24.svg.png",
    "Euronews": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/49/Euronews_2018.svg/512px-Euronews_2018.svg.png",
    "Sky News": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3e/Sky_News.svg/512px-Sky_News.svg.png",
    "NHK World": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1c/NHK_World_Japan.svg/512px-NHK_World_Japan.svg.png",
    "TRT World": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7c/TRT_World.svg/512px-TRT_World.svg.png",
    "Al Arabiya": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/00/Al_Arabiya.svg/512px-Al_Arabiya.svg.png",
    "Al Jazeera English": "https://upload.wikimedia.org/wikipedia/ms/thumb/f/f2/Aljazeera_eng.svg/1200px-Aljazeera_eng.svg.png",
    "CBS News": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0e/CBS_News.svg/512px-CBS_News.svg.png",
    "ABC News": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/63/ABC_News_Live_logo_2021.svg/512px-ABC_News_Live_logo_2021.svg.png",
    "Fox News": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/44/Fox_News_Channel_logo.svg/512px-Fox_News_Channel_logo.svg.png",
    "MSNBC": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/45/MSNBC_logo.svg/512px-MSNBC_logo.svg.png",
    "Bloomberg": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/58/Bloomberg_L.P.svg/512px-Bloomberg_L.P.svg.png",
    "CNN": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b1/CNN.svg/512px-CNN.svg.png",
    "BBC News": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4d/BBC_News.svg/512px-BBC_News.svg.png",
    "CGTN": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/96/CGTN_Logo.svg/512px-CGTN_Logo.svg.png",
    "VOA": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/41/Voice_of_America_logo.svg/512px-Voice_of_America_logo.svg.png",
    "Reuters": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c1/Reuters_logo.svg/1200px-Reuters_logo.svg.png",
    "GLOBO NEWS": "https://i.imgur.com/Wu4ykxo.jpg",
    "BAND NEWS": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/85/Band_News_TV_2021_Logo.png/800px-Band_News_TV_2021_Logo.png",
    "JOVEM PAN NEWS": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/41/Logotipo_da_TV_Jovem_Pan_News.png/120px-Logotipo_da_TV_Jovem_Pan_News.png",
}

def download_epg(epg_url: str) -> Optional[str]:
    try:
        response = requests.get(epg_url, timeout=120, headers={'Accept-Encoding': 'gzip'})
        response.raise_for_status()
        
        if epg_url.endswith('.gz'):
            content = gzip.decompress(response.content).decode('utf-8')
        else:
            content = response.text
        return content
    except Exception as e:
        print(f"    Erro: {e}")
        return None

def test_epg_programming(epg_content: str, tvg_id: str) -> Dict:
    resultado = {"status": "sem_programacao", "hoje": 0, "amanha": 0, "depois_amanha": 0, "programas_hoje": []}
    
    try:
        root = ET.fromstring(epg_content)
        hoje = datetime.now().strftime("%Y%m%d")
        amanha = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
        depois_amanha = (datetime.now() + timedelta(days=2)).strftime("%Y%m%d")
        
        for prog in root.findall("programme"):
            channel = prog.get("channel", "")
            if channel == tvg_id or tvg_id.lower() in channel.lower():
                start = prog.get("start", "")[:8]
                title_elem = prog.find("title")
                title = title_elem.text if title_elem is not None else "Sem título"
                
                if start[:8] == hoje:
                    resultado["hoje"] += 1
                    if len(resultado["programas_hoje"]) < 3:
                        resultado["programas_hoje"].append(title)
                elif start[:8] == amanha:
                    resultado["amanha"] += 1
                elif start[:8] == depois_amanha:
                    resultado["depois_amanha"] += 1
        
        if resultado["hoje"] > 0 and resultado["amanha"] > 0 and resultado["depois_amanha"] > 0:
            resultado["status"] = "completo"
        elif resultado["hoje"] > 0 or resultado["amanha"] > 0:
            resultado["status"] = "parcial"
        
    except Exception as e:
        resultado["error"] = str(e)
    
    return resultado

def check_url_accessible(url: str) -> bool:
    try:
        response = requests.head(url, timeout=10, allow_redirects=True, headers={'User-Agent': 'Mozilla/5.0'})
        return response.status_code in [200, 301, 302, 405]
    except:
        return False

def parse_m3u(filepath: str) -> List[Dict]:
    channels = []
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXTINF:'):
            url = lines[i + 1].strip() if i + 1 < len(lines) else ""
            channel_name = ""
            tvg_id = ""
            tvg_logo = ""
            group = ""
            
            match = re.search(r',(.+)$', line)
            if match:
                channel_name = match.group(1).strip()
            
            tvg_id_match = re.search(r'tvg-id="([^"]*)"', line)
            if tvg_id_match:
                tvg_id = tvg_id_match.group(1)
            
            tvg_logo_match = re.search(r'tvg-logo="([^"]*)"', line)
            if tvg_logo_match:
                tvg_logo = tvg_logo_match.group(1)
            
            group_match = re.search(r'group-title="([^"]*)"', line)
            if group_match:
                group = group_match.group(1)
            
            channels.append({"extinf": line, "url": url, "name": channel_name, "tvg_id": tvg_id, "tvg_logo": tvg_logo, "group": group, "line_number": i + 1})
            i += 2
        else:
            i += 1
    return channels

def fix_logo_extension(logo_url: str) -> str:
    if not logo_url:
        return logo_url
    
    parsed = urlparse(logo_url)
    path = parsed.path.lower()
    
    if path.endswith('.svg') or path.endswith('.png') or path.endswith('.webp') or path.endswith('.gif'):
        base_url = logo_url.rsplit('.', 1)[0]
        logo_url = base_url + '.jpg'
    
    return logo_url

def main():
    print("=" * 70)
    print("CORREÇÃO COMPLETA lista5.m3u")
    print("=" * 70)
    
    m3u_path = "lista5.m3u"
    api_key = sys.argv[1] if len(sys.argv) > 1 else None
    
    channels = parse_m3u(m3u_path)
    print(f"\nCanais encontrados: {len(channels)}")
    
    print("\n" + "-" * 70)
    print("BAIXANDO EPGs (apenas fontes principais)...")
    print("-" * 70)
    
    epg_contents = {}
    epg_urls = {}
    
    epg_keys_to_download = ["global", "us", "uk", "es", "fr", "br"]
    
    for key in epg_keys_to_download:
        if key in EPG_SOURCES:
            url = EPG_SOURCES[key]
            print(f"\nBaixando: {key.upper()} EPG...")
            content = download_epg(url)
            if content and len(content) > 1000:
                epg_contents[key] = content
                epg_urls[key] = url
                print(f"  OK! Tamanho: {len(content):,} bytes")
            else:
                print(f"  FALHOU")
    
    print("\n" + "-" * 70)
    print("PROCESSANDO CANAIS...")
    print("-" * 70)
    
    processed_channels = []
    channels_with_valid_epg = []
    channels_without_epg = []
    
    for ch in channels:
        channel_name = ch["name"]
        tvg_id = ch["tvg_id"]
        tvg_logo = ch["tvg_logo"]
        group = ch["group"]
        url = ch["url"]
        
        mapping = CHANNEL_EPG_MAPPING.get(channel_name, {})
        
        if not tvg_id and mapping.get("tvg_id"):
            tvg_id = mapping["tvg_id"]
        
        epg_key = mapping.get("epg_key", "global")
        
        if epg_key not in epg_contents:
            epg_key = "global"
        
        epg_url = epg_urls.get(epg_key, "")
        
        if not tvg_logo:
            if channel_name in LOGO_MAPPING:
                tvg_logo = LOGO_MAPPING[channel_name]
        
        if tvg_logo:
            tvg_logo = fix_logo_extension(tvg_logo)
        
        epg_result = {"status": "sem_epg", "hoje": 0, "amanha": 0, "depois_amanha": 0}
        
        if tvg_id and epg_key in epg_contents:
            epg_content = epg_contents[epg_key]
            epg_result = test_epg_programming(epg_content, tvg_id)
        
        attrs = []
        if tvg_id:
            attrs.append(f'tvg-id="{tvg_id}"')
        if tvg_logo:
            attrs.append(f'tvg-logo="{tvg_logo}"')
        if group:
            attrs.append(f'group-title="{group}"')
        
        attrs_str = ' '.join(attrs)
        new_extinf = f'#EXTINF:-1 {attrs_str},{channel_name}'
        
        if epg_result["status"] in ["completo", "parcial"]:
            channels_with_valid_epg.append({
                "extinf": new_extinf,
                "url": url,
                "name": channel_name,
                "tvg_id": tvg_id,
                "epg_key": epg_key,
                "epg_url": epg_url,
                "epg_result": epg_result,
                "logo_ok": ".jpg" in tvg_logo.lower() if tvg_logo else False
            })
        else:
            channels_without_epg.append({
                "extinf": new_extinf,
                "url": url,
                "name": channel_name,
                "tvg_id": tvg_id,
                "epg_key": epg_key,
                "epg_result": epg_result,
                "logo_ok": ".jpg" in tvg_logo.lower() if tvg_logo else False
            })
    
    all_channels = channels_with_valid_epg + channels_without_epg
    
    print(f"\nCanais com EPG valido: {len(channels_with_valid_epg)}")
    print(f"Canais sem EPG valido: {len(channels_without_epg)}")
    
    print("\n" + "-" * 70)
    print("VERIFICANDO ACESSIBILIDADE DAS URLs...")
    print("-" * 70)
    
    unique_urls = {}
    for ch in all_channels:
        url = ch["url"]
        if url and url not in unique_urls:
            unique_urls[url] = ch["name"]
    
    print(f"URLs unicas: {len(unique_urls)}")
    
    inaccessible_channels = []
    checked = 0
    
    print("\nVerificando primeiras 30 URLs...")
    for url, name in list(unique_urls.items())[:30]:
        if not check_url_accessible(url):
            inaccessible_channels.append(name)
            print(f"  INACC: {name[:40]}")
        checked += 1
    
    print("\n" + "-" * 70)
    print("RESULTADOS...")
    print("-" * 70)
    
    print(f"Canais inacessiveis: {len(inaccessible_channels)}")
    
    final_channels = []
    removed_count = 0
    
    for ch in all_channels:
        name = ch["name"]
        if name in inaccessible_channels:
            removed_count += 1
            print(f"  - Removido: {name}")
        else:
            final_channels.append(ch)
    
    unique_final = {}
    for ch in final_channels:
        key = ch["extinf"] + ch["url"]
        if key not in unique_final:
            unique_final[key] = ch
    
    all_epg_urls = list(set(ch["epg_url"] for ch in final_channels if ch.get("epg_url")))
    epg_header = ",".join(all_epg_urls[:5])
    
    print("\n" + "-" * 70)
    print("GERANDO lista5.m3u FINAL...")
    print("-" * 70)
    
    with open(m3u_path, 'w', encoding='utf-8') as f:
        if epg_header:
            f.write(f'#EXTM3U x-tvg-url="{epg_header}"\n')
        else:
            f.write("#EXTM3U\n")
        
        for key, ch in unique_final.items():
            f.write(ch["extinf"] + "\n")
            f.write(ch["url"] + "\n")
    
    print(f"\nOK! lista5.m3u atualizada!")
    print(f"  - Canais finais: {len(unique_final)}")
    print(f"  - Canais removidos: {removed_count}")
    print(f"  - EPGs incluidos: {len(all_epg_urls)}")
    
    report = []
    report.append("=" * 70)
    report.append("RELATORIO lista5.m3u")
    report.append("=" * 70)
    report.append(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    report.append(f"Canais com EPG valido: {len(channels_with_valid_epg)}")
    report.append(f"Canais sem EPG valido: {len(channels_without_epg)}")
    report.append(f"Canais removidos: {removed_count}")
    report.append(f"Canais finais: {len(unique_final)}")
    report.append("")
    
    report.append("-" * 70)
    report.append("CANAIS COM EPG:")
    report.append("-" * 70)
    for ch in channels_with_valid_epg[:50]:
        prog = ch.get("epg_result", {})
        report.append(f"  {ch['name'][:40]:<40} | Hoje:{prog.get('hoje',0):>3} Ama:{prog.get('amanha',0):>3} Dep:{prog.get('depois_amanha',0):>3}")
    
    with open("lista5_relatorio.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(report))
    
    print("\nRelatorio salvo em: lista5_relatorio.txt")

if __name__ == "__main__":
    main()
