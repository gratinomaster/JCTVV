#!/usr/bin/env python3
import requests
import gzip
import re
import xml.etree.ElementTree as ET
from datetime import datetime

EPG_URL = "https://epg.pw/xmltv/epg.xml.gz"

CORRECT_TVG_IDS = {
    "DW English": "524147",
    "DW English": "524147",
    "DW Arabic": "524147",
    "DW Español": "524147",
    "RT English": "RT.com",
    "RT": "RT.com",
    "RT Arabic": "RT.com",
    "RT en Español": "RT.com",
    "France 24 English": "524078",
    "France 24": "524078",
    "France 24 Arabic": "524122",
    "France24 Espanol": "524078",
    "Euronews English": "534189",
    "Euronews": "534189",
    "Euronews Español": "534189",
    "Sky News UK": "463753",
    "Sky News": "463753",
    "Sky News Arabia": "55795",
    "NHK World": "524022",
    "NHK G": "524022",
    "TRT World": "12173",
    "TRT Haber": "TRTHaber.tr",
    "TRT Arabi": "TRTArabi.tr",
    "Al Arabiya": "AlArabiya.ae",
    "Al Jazeera English": "369587",
    "Al Jazeera": "369587",
    "Al Jazeera Arabic": "AlJazeeraArabic.qa",
    "Al Jazeera Mubasher": "AlJazeeraMubasher.qa",
    "Al Jazeera Balkans": "AlJazeeraBalkans.ba",
    "CBS News": "CBSNews.us",
    "ABC News": "ABCNews.us",
    "Fox News": "Fox.News.us",
    "FOX News": "Fox.News.us",
    "MSNBC": "447005",
    "Bloomberg US": "12427",
    "Bloomberg": "12427",
    "CNN": "12013",
    "BBC News TV": "492871",
    "BBC News": "492871",
    "BBC World News": "492871",
    "BBC Arabic": "BBCArabic.uk",
    "CGTN": "CGTN.cn",
    "CGTN Arabic": "CGTNArabic.cn",
    "VOA": "VOA.us",
    "VOA Persian": "VOA.us",
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
    "IRIB": "IRIB1.ir",
    "IRIB 1": "IRIB1.ir",
    "IRIB 2": "IRIB2.ir",
    "IRIB 3": "IRIB3.ir",
    "IRIB1": "IRIB1.ir",
    "IRIB2": "IRIB2.ir",
    "IRIB3": "IRIB3.ir",
    "IRIB4": "IRIB4.ir",
    "IRINN": "IRINN.ir",
    "IFILM IR": "IFilm.ir",
    "Press TV English": "PressTV.ir",
    "CNA": "CNA.sg",
    "Africanews": "Africanews.com",
    "NDTV India": "463951",
    "WION": "WION.in",
    "Newsmax": "NewsmaxTV.us",
    "Newsmax TV": "NewsmaxTV.us",
    "OAN": "OAN.us",
    "NASA TV": "NASATV.us",
    "NASA TV MEDIA": "NASATV.us",
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
    "teleSUR English": "TelesurEnglish.ve",
    "TV5Monde Info": "TV5MondeInfo.fr",
    "Class CNBC": "ClassCNBC.it",
    "BFM TV": "BFMTV.fr",
    "BFM Business": "BFMBusiness.fr",
    "tagesschau24": "tagesschau24.de",
    "+24": "24Horas.es",
    "24 HORAS CL": "24Horas.es",
    "Canal 24 Horas Canarias": "24HorasCanarias.es",
    "Canal 24 Horas Catalunya": "24HorasCatalunya.es",
    "Global News Canada": "GlobalNewsCanada.ca",
    "Global News": "GlobalNewsCanada.ca",
    "Global News British Columbia": "GlobalNewsCanada.ca",
    "Global News Calgary": "GlobalNewsCanada.ca",
    "Global News Toronto": "GlobalNewsCanada.ca",
    "Global News Winnipeg": "GlobalNewsCanada.ca",
    "Global News Saskatoon": "GlobalNewsCanada.ca",
    "Global News Regina": "GlobalNewsCanada.ca",
    "Global News Halifax": "GlobalNewsCanada.ca",
    "Global News Okanagan": "GlobalNewsCanada.ca",
    "Global News Lethbridge": "GlobalNewsCanada.ca",
    "Global News Peterborough": "GlobalNewsCanada.ca",
    "Global News Montreal": "GlobalNewsCanada.ca",
    "Global News Kingston": "GlobalNewsCanada.ca",
    "Global News National": "GlobalNewsCanada.ca",
    "SABC News": "ABCNews.us",
    "Current Time TV": "CurrentTimeTV.us",
    "VOA TV Africa": "VoATV.us",
    "AP Direct": "AP_Direct",
    "AP Live Choice": "AP_LC_1",
    "ABC News (Australia)": "ABCNewsAustralia.au",
    "ABC Radio (Australia)": "ABCRadioAustralia.au",
    "Al Araby": "AlAraby.tv",
    "Al-Manar": "AlManar.lb",
    "Alhurra": "Alhurra.iq",
    "Alhurra Iraq": "AlhurraIraq.us",
    "Al Eshraq TV": "AlEshraqTV.iq",
    "Al Ghad TV": "AlGhadTV.eg",
    "Al Ghad Plus": "AlGhadPlus.eg",
    "Al Hadath": "AlHadath.sa",
    "Al Iraqia News": "AlIraqiaNews.iq",
    "Al Janoub TV": "AlJanoubTV.iq",
    "Al Masar TV": "AlMasarTV.ly",
    "Al Masirah": "AlMasirah.ye",
    "Al Mayadeen": "AlMayadeenTV.lb",
    "Al Mamlaka TV": "AlMamlakaTV.jo",
    "Al Nujaba": "AlNujabaTV.iq",
    "Al Najah News": "AlNajahNews.ps",
    "Al Qahera News": "AlQaheraNews.eg",
    "Al Sharqiya News": "AlSharqiyaNews.iq",
    "Al Yaum TV": "AlYaumTV.ae",
    "Al Arabiya Al Hadath": "AlHadath.sa",
    "Alarabiya Portrait": "AlarabiyaPortrait.ae",
    "Al Ekhbariya": "AlEkhbariya.sa",
    "Arirang": "ArirangTV.kr",
    "Arirang TV": "ArirangTV.kr",
    "Astro Awani": "AstroAwani.my",
    "ABP News": "ABPNews.in",
    "ABP Majha": "ABPMajha.in",
    "ABP Ganga": "ABPGanga.in",
    "Aaj Tak": "AajTak.in",
    "India Today": "IndiaToday.in",
    "Asianet News": "AsianetNews.in",
    "Bharat Samachar TV": "BharatSamacharTV.in",
    "CCTV+": "CCTVPlus.cn",
    "CCTV+ 1": "CCTVPlus.cn",
    "CCTV+ 2": "CCTVPlus.cn",
    "CCTV+ 3": "CCTVPlus.cn",
    "CCTV+ 4": "CCTVPlus.cn",
    "РБК": "RBKTV.ru",
    "24 Канал": "Channel24.ua",
    "News 24": "News24.al",
    "NTV News24": "NTVNews24.jp",
    "Asharq News": "AsharqNews.sa",
    "ATN News": "ATNNews.af",
    "Afghanistan International": "AfghanistanInternational.uk",
    "Aleph News": "AlephNews.ro",
    "NewsNet": "W14DKD2.us",
    "W14DK-D": "W14DKD2.us",
    "HispanTV": "HispanTV.ir",
    "Iran International": "IranInternational.uk",
    "TV Rain": "TVRain.ru",
    "Venezolana de Televisión": "VTV.ve",
    "Notícias Univision 24/7": "Noticias_Univision_24_7",
    "Noticias Univision 24/7": "Noticias_Univision_24_7",
    "Noticias Telemundo Ahora": "Noticias_Telemundo_Ahora",
    "CNN CHILE": "CNNChile.cl",
    "El Trece": "ElTrece.ar",
    "MEGANOTICIAS": "Mega.cl",
    "Emol TV 1": "EmolTV.cl",
    "Emol TV 2": "EmolTV2.cl",
    "UCV TV": "UCVTV.cl",
    "UCV TV 2": "UCVTV2.cl",
    "COOPERATIVA": "Cooperativa.cl",
    "LA RED": "LaRed.cl",
    "RADIO T13": "T13Radio.cl",
    "RADIO PUDAHUEL": "Pudahuel.cl",
    "RADIO DUNA": "RadioDuna.cl",
    "NTV NEWS 24": "NTVNews24.jp",
    "UN Web TV": "UNWebTV.us",
    "UN Web TV 2": "UNWebTV.us",
    "Fox Business": "FRBD4100006OC",
    "Black News Channel": "BlackNewsChannel.us",
    "Cheddar News": "CheddarNews.us",
    "CNBC Indonesia": "CNBCIndonesia.id",
    "CNN Indonesia": "CNN.Indonesia.id",
    "Yahoo! Finance (1080p)": "YahooFinance.us",
    "The Wall Street Journal Live": "TheWallStreetJournalLive.us",
    "CAM CAPITOLIO EEUU": "USCapitol.us",
    "PRESIDENCIA USA": "USCapitol.us",
    "PENTAGONO USA": "USCapitol.us",
    "Zee Business": "ZeeBusiness.in",
    "Ameritrade": "TD Ameritrade.us",
    "30A Investment Pitch": "30AInvestmentPitch.us",
    "30A TV": "30ATV.us",
    "100% News": "100News.ua",
    "ARB 24": "ARB24.az",
    "Fox Weather": "FOXWeather.us",
    "FOX WEATHER": "FOXWeather.us",
    "AnewZ": "AnewZ.com",
    "News 1 (Tailandia)": "News1.th",
    "Real News Kerala": "RealNewsKerala.in",
    "Palitra News": "PalitraNews.ge",
    "3AW Melbourne": "3AW.au",
    "2GB Sydney": "2GB.au",
    "DNA": "DNA.cl",
    "TN": "TN.cl",
    "BTV": "ITBD4400010WK",
    "Baku TV": "BakuTV.az",
    "Blaze Live": "BlazeLive.us",
    "Astra TV": "AstraTV.gr",
    "BEK TV News": "BEKNews.us",
    "CityNews Toronto": "CityNewsTo.ca",
    "CityNews Calgary": "CityNewsCa.ca",
    "CityNews Vancouver": "CityNewsVa.ca",
    "TVP": "TVPWorld.pl",
    "ATV+": "ATVPlus.pe",
    "Canal Parlamento": "Parlamento.es",
    "YNET NEWS": "YnetNews.il",
    "DHA": "DHA.tr",
    "Atameken Business": "AtamekenBusiness.kz",
    "Башкортостан 24": "Bashkortostan24.ru",
    "Беларусь 24": "Belarus24.by",
    "TVG Eventos": "TVG.es",
    "REUTERS": "Reuters.uk",
    "CNN INTERNACIONAL": "cnn.us",
    "CNN INTERNATIONAL": "cnn.us",
    "CNN SERVIÇO 1": "cnn.us",
    "CNN SERVIÇO 2": "cnn.us",
    "CNN SERVIÇO 3": "cnn.us",
    "CNN SERVIÇO 4": "cnn.us",
    "Deutsche Welle Arabic": "DWArabic.de",
    "Deutsche Welle Español": "DWEspanol.de",
    "Deutsche Welle Deutsch+": "DWDeutsch.de",
}

LOGO_JPG = {
    "DW English": "https://i.imgur.com/8MRNFb9.jpg",
    "DW Arabic": "https://i.imgur.com/8MRNFb9.jpg",
    "DW Español": "https://i.imgur.com/8MRNFb9.jpg",
    "DW": "https://i.imgur.com/8MRNFb9.jpg",
    "RT English": "https://i.imgur.com/8MRNFb9.jpg",
    "RT": "https://i.imgur.com/8MRNFb9.jpg",
    "RT Arabic": "https://i.imgur.com/8MRNFb9.jpg",
    "RT en Español": "https://i.imgur.com/8MRNFb9.jpg",
    "France 24": "https://i.imgur.com/BFMMPwP.jpg",
    "France 24 English": "https://i.imgur.com/BFMMPwP.jpg",
    "France 24 Arabic": "https://i.imgur.com/BFMMPwP.jpg",
    "France24": "https://i.imgur.com/BFMMPwP.jpg",
    "France24 Espanol": "https://i.imgur.com/BFMMPwP.jpg",
    "France24 France": "https://i.imgur.com/BFMMPwP.jpg",
    "Euronews": "https://i.imgur.com/BFMMPwP.jpg",
    "Euronews English": "https://i.imgur.com/BFMMPwP.jpg",
    "Euronews Español": "https://i.imgur.com/BFMMPwP.jpg",
    "EURONEWS EN ITALIANO": "https://i.imgur.com/BFMMPwP.jpg",
    "Sky News": "https://i.imgur.com/ZsPb8nL.jpg",
    "Sky News UK": "https://i.imgur.com/ZsPb8nL.jpg",
    "Sky News Arabia": "https://i.imgur.com/ZsPb8nL.jpg",
    "Sky News Extra 1": "https://i.imgur.com/ZsPb8nL.jpg",
    "Sky News Extra 2": "https://i.imgur.com/ZsPb8nL.jpg",
    "Sky News Extra 3": "https://i.imgur.com/ZsPb8nL.jpg",
    "Sky News Arabe": "https://i.imgur.com/ZsPb8nL.jpg",
    "NHK World": "https://i.imgur.com/nhkworld.jpg",
    "NHK G": "https://i.imgur.com/nhkworld.jpg",
    "TRT World": "https://i.imgur.com/NCvRHC3.jpg",
    "TRT Haber": "https://i.imgur.com/NCvRHC3.jpg",
    "TRT Arabi": "https://i.imgur.com/NCvRHC3.jpg",
    "Al Arabiya": "https://i.imgur.com/NXFkYFj.jpg",
    "Al Jazeera English": "https://i.imgur.com/NXFkYFj.jpg",
    "Al Jazeera": "https://i.imgur.com/NXFkYFj.jpg",
    "Al Jazeera Arabic": "https://i.imgur.com/NXFkYFj.jpg",
    "Al Jazeera Mubasher": "https://i.imgur.com/NXFkYFj.jpg",
    "Al Jazeera Balkans": "https://i.imgur.com/NXFkYFj.jpg",
    "Aljazeera English": "https://i.imgur.com/NXFkYFj.jpg",
    "Aljazeera Balkans": "https://i.imgur.com/NXFkYFj.jpg",
    "CBS News": "https://i.imgur.com/cbsnews.jpg",
    "ABC News": "https://i.imgur.com/abcnews.jpg",
    "Fox News": "https://i.imgur.com/foxnews.jpg",
    "FOX News": "https://i.imgur.com/foxnews.jpg",
    "FOX NEWS USA": "https://i.imgur.com/foxnews.jpg",
    "MSNBC": "https://i.imgur.com/JmKvove.jpg",
    "Bloomberg": "https://i.imgur.com/idRFfhY.jpg",
    "Bloomberg US": "https://i.imgur.com/idRFfhY.jpg",
    "Bloomberg Television": "https://i.imgur.com/idRFfhY.jpg",
    "Bloomberg Politics": "https://i.imgur.com/idRFfhY.jpg",
    "Bloomberg EU": "https://i.imgur.com/idRFfhY.jpg",
    "Bloomberg Europe Event": "https://i.imgur.com/idRFfhY.jpg",
    "CNN": "https://i.imgur.com/xWglicB.jpg",
    "CNN INTERNACIONAL": "https://i.imgur.com/xWglicB.jpg",
    "CNN INTERNATIONAL": "https://i.imgur.com/xWglicB.jpg",
    "CNN BRASIL": "https://i.imgur.com/cnnbrasil.jpg",
    "CNN Brasil": "https://i.imgur.com/cnnbrasil.jpg",
    "BBC News": "https://i.imgur.com/vSz2WEp.jpg",
    "BBC News TV": "https://i.imgur.com/vSz2WEp.jpg",
    "BBC World News": "https://i.imgur.com/vSz2WEp.jpg",
    "BBC Arabic": "https://i.imgur.com/vSz2WEp.jpg",
    "CGTN": "https://i.imgur.com/cgtn.jpg",
    "CGTN Arabic": "https://i.imgur.com/cgtn.jpg",
    "CGTN Documentary": "https://i.imgur.com/cgtn.jpg",
    "CGTN Español": "https://i.imgur.com/cgtn.jpg",
    "VOA": "https://i.imgur.com/rtRnlqN.jpg",
    "VOA Persian": "https://i.imgur.com/rtRnlqN.jpg",
    "Reuters": "https://i.imgur.com/4xSEoNK.jpg",
    "REUTERS": "https://i.imgur.com/4xSEoNK.jpg",
    "GLOBO NEWS": "https://i.imgur.com/Wu4ykxo.jpg",
    "BAND NEWS": "https://i.imgur.com/jCZzNjF.jpg",
    "JOVEM PAN NEWS": "https://i.imgur.com/aqgaka0.jpg",
    "Jovem Pan News": "https://i.imgur.com/aqgaka0.jpg",
    "BM&C NEWS": "https://i.imgur.com/tyW3Ppf.jpg",
    "RECORD NEWS": "https://i.imgur.com/record.jpg",
    "RAI News 24": "https://i.imgur.com/rainews.jpg",
    "RAI NEWS24": "https://i.imgur.com/rainews.jpg",
    "IRIB": "https://i.imgur.com/8tzsC9h.jpg",
    "IRIB 1": "https://i.imgur.com/8tzsC9h.jpg",
    "IRIB 2": "https://i.imgur.com/8tzsC9h.jpg",
    "IRIB 3": "https://i.imgur.com/8tzsC9h.jpg",
    "IRIB1": "https://i.imgur.com/8tzsC9h.jpg",
    "IRIB2": "https://i.imgur.com/8tzsC9h.jpg",
    "IRIB3": "https://i.imgur.com/8tzsC9h.jpg",
    "IRIB4": "https://i.imgur.com/8tzsC9h.jpg",
    "IRINN": "https://i.imgur.com/8tzsC9h.jpg",
    "IFILM IR": "https://i.imgur.com/8tzsC9h.jpg",
    "Press TV English": "https://i.imgur.com/8tzsC9h.jpg",
    "HispanTV": "https://i.imgur.com/8tzsC9h.jpg",
    "CNA": "https://i.imgur.com/xJZ9ChT.jpg",
    "Africanews": "https://i.imgur.com/jHJR3LN.jpg",
    "NDTV India": "https://i.imgur.com/ndtv.jpg",
    "WION": "https://i.imgur.com/wion.jpg",
    "Newsmax": "https://i.imgur.com/newsmax.jpg",
    "Newsmax TV": "https://i.imgur.com/newsmax.jpg",
    "OAN": "https://i.imgur.com/oan.jpg",
    "NASA TV": "https://i.imgur.com/nasa.jpg",
    "NASA TV MEDIA": "https://i.imgur.com/nasa.jpg",
    "Yahoo! Finance": "https://i.imgur.com/Y3vQaf5.jpg",
    "Yahoo! Finance (1080p)": "https://i.imgur.com/Y3vQaf5.jpg",
    "SPORTV": "https://i.imgur.com/sportv.jpg",
    "ESPN": "https://i.imgur.com/espn.jpg",
    "ESPN 2": "https://i.imgur.com/espn2.jpg",
    "ESPN 3": "https://i.imgur.com/espn3.jpg",
    "ESPN 5": "https://i.imgur.com/espn.jpg",
    "ESPN 6": "https://i.imgur.com/espn.jpg",
    "BFM TV": "https://i.imgur.com/bfmtv.jpg",
    "BFM Business": "https://i.imgur.com/bfmbusiness.jpg",
    "Telesur English": "https://i.imgur.com/telesur.jpg",
    "TELESUR": "https://i.imgur.com/telesur.jpg",
    "teleSUR": "https://i.imgur.com/telesur.jpg",
    "teleSUR English": "https://i.imgur.com/telesur.jpg",
    "TELESUR ENG": "https://i.imgur.com/telesur.jpg",
    "+24": "https://i.imgur.com/24horas.jpg",
    "24 HORAS CL": "https://i.imgur.com/24horas.jpg",
    "Canal 24 Horas Canarias": "https://i.imgur.com/IUVRm5L.jpg",
    "Canal 24 Horas Catalunya": "https://i.imgur.com/IUVRm5L.jpg",
    "tagesschau24": "https://i.imgur.com/tagesschau.jpg",
    "Global News": "https://i.imgur.com/IZFEJsu.jpg",
    "Global News Canada": "https://i.imgur.com/IZFEJsu.jpg",
    "Global News British Columbia": "https://i.imgur.com/IZFEJsu.jpg",
    "Global News Calgary": "https://i.imgur.com/IZFEJsu.jpg",
    "Global News Toronto": "https://i.imgur.com/IZFEJsu.jpg",
    "Global News Winnipeg": "https://i.imgur.com/IZFEJsu.jpg",
    "Global News Saskatoon": "https://i.imgur.com/IZFEJsu.jpg",
    "Global News Regina": "https://i.imgur.com/IZFEJsu.jpg",
    "Global News Halifax": "https://i.imgur.com/IZFEJsu.jpg",
    "Global News Okanagan": "https://i.imgur.com/IZFEJsu.jpg",
    "Global News Lethbridge": "https://i.imgur.com/IZFEJsu.jpg",
    "Global News Peterborough": "https://i.imgur.com/IZFEJsu.jpg",
    "Global News Montreal": "https://i.imgur.com/IZFEJsu.jpg",
    "Global News Kingston": "https://i.imgur.com/IZFEJsu.jpg",
    "Global News National": "https://i.imgur.com/IZFEJsu.jpg",
    "Global News 2": "https://i.imgur.com/IZFEJsu.jpg",
    "Global News 2": "https://i.imgur.com/IZFEJsu.jpg",
    "Deutsche Welle Arabic": "https://i.imgur.com/8MRNFb9.jpg",
    "Deutsche Welle Español": "https://i.imgur.com/8MRNFb9.jpg",
    "Deutsche Welle Deutsch+": "https://i.imgur.com/8MRNFb9.jpg",
    "Deutsche Welle": "https://i.imgur.com/8MRNFb9.jpg",
    "TV5Monde Info": "https://i.imgur.com/BFMMPwP.jpg",
    "Class CNBC": "https://i.imgur.com/qsmHgJ1.jpg",
    "Fox Business": "https://i.imgur.com/foxnews.jpg",
    "Black News Channel": "https://i.imgur.com/foxnews.jpg",
    "Cheddar News": "https://i.imgur.com/Y3vQaf5.jpg",
    "The Wall Street Journal Live": "https://i.imgur.com/4xSEoNK.jpg",
    "REUTERS SERVIÇO": "https://i.imgur.com/4xSEoNK.jpg",
    "CNN Money": "https://i.imgur.com/cnnbrasil.jpg",
    "CNN BRASIL MONEY": "https://i.imgur.com/cnnbrasil.jpg",
    "Al Araby": "https://i.imgur.com/NXFkYFj.jpg",
    "Al Araby TV": "https://i.imgur.com/NXFkYFj.jpg",
    "Al Araby TV 2": "https://i.imgur.com/NXFkYFj.jpg",
    "Al Arabiya Al Hadath": "https://i.imgur.com/NXFkYFj.jpg",
    "Alarabiya Portrait": "https://i.imgur.com/NXFkYFj.jpg",
    "TVG Eventos": "https://i.imgur.com/IUVRm5L.jpg",
    "TV Rain": "https://i.imgur.com/rainews.jpg",
    "Expressen TV": "https://i.imgur.com/ZsPb8nL.jpg",
    "Univision": "https://i.imgur.com/xWglicB.jpg",
    "Notícias Univision 24/7": "https://i.imgur.com/xWglicB.jpg",
    "Noticias Univision 24/7": "https://i.imgur.com/xWglicB.jpg",
    "Noticias Telemundo Ahora": "https://i.imgur.com/xWglicB.jpg",
    "AP Direct": "https://i.imgur.com/foxnews.jpg",
    "AP Live Choice": "https://i.imgur.com/foxnews.jpg",
    "ABC News (Australia)": "https://i.imgur.com/abcnews.jpg",
    "ABC Radio (Australia)": "https://i.imgur.com/abcnews.jpg",
    "Aleph News": "https://i.imgur.com/rainews.jpg",
    "VOA TV Africa": "https://i.imgur.com/rtRnlqN.jpg",
    "UN Web TV": "https://i.imgur.com/foxnews.jpg",
    "UN Web TV 2": "https://i.imgur.com/foxnews.jpg",
    "CAM CAPITOLIO EEUU": "https://i.imgur.com/foxnews.jpg",
    "PRESIDENCIA USA": "https://i.imgur.com/foxnews.jpg",
    "PENTAGONO USA": "https://i.imgur.com/foxnews.jpg",
    "NewsNet": "https://i.imgur.com/ZsPb8nL.jpg",
    "W14DK-D": "https://i.imgur.com/ZsPb8nL.jpg",
    "CNN CHILE": "https://i.imgur.com/xWglicB.jpg",
    "El Trece": "https://i.imgur.com/xWglicB.jpg",
    "MEGANOTICIAS": "https://i.imgur.com/xWglicB.jpg",
    "MEGANOTICIAS 2": "https://i.imgur.com/xWglicB.jpg",
    "MEGANOTICIAS 3": "https://i.imgur.com/xWglicB.jpg",
    "24Horas": "https://i.imgur.com/24horas.jpg",
    "24 HORAS": "https://i.imgur.com/24horas.jpg",
    "24 HORAS CL": "https://i.imgur.com/24horas.jpg",
    "Emol TV 1": "https://i.imgur.com/xWglicB.jpg",
    "Emol TV 2": "https://i.imgur.com/xWglicB.jpg",
    "UCV TV": "https://i.imgur.com/xWglicB.jpg",
    "UCV TV 2": "https://i.imgur.com/xWglicB.jpg",
    "COOPERATIVA": "https://i.imgur.com/xWglicB.jpg",
    "LA RED": "https://i.imgur.com/xWglicB.jpg",
    "RADIO T13": "https://i.imgur.com/xWglicB.jpg",
    "RADIO PUDAHUEL": "https://i.imgur.com/xWglicB.jpg",
    "RADIO DUNA": "https://i.imgur.com/xWglicB.jpg",
    "NTV NEWS 24": "https://i.imgur.com/nhkworld.jpg",
    "NTV News24": "https://i.imgur.com/nhkworld.jpg",
    "Fox Weather": "https://i.imgur.com/foxnews.jpg",
    "FOX WEATHER": "https://i.imgur.com/foxnews.jpg",
    "CBS NEWS SERVIÇO": "https://i.imgur.com/cbsnews.jpg",
    "ABC NEWS SERVIÇO": "https://i.imgur.com/abcnews.jpg",
    "ABC NEWS SERVIÇO 1": "https://i.imgur.com/abcnews.jpg",
    "ABC NEWS SERVIÇO 2": "https://i.imgur.com/abcnews.jpg",
    "ABC NEWS SERVIÇO 3": "https://i.imgur.com/abcnews.jpg",
    "ABC NEWS SERVIÇO 4": "https://i.imgur.com/abcnews.jpg",
    "ABC NEWS SERVIÇO 5": "https://i.imgur.com/abcnews.jpg",
    "ABC NEWS SERVIÇO 6": "https://i.imgur.com/abcnews.jpg",
    "ABC NEWS SERVIÇO 7": "https://i.imgur.com/abcnews.jpg",
    "ABC NEWS SERVIÇO 8": "https://i.imgur.com/abcnews.jpg",
    "ABC NEWS SERVIÇO 9": "https://i.imgur.com/abcnews.jpg",
    "ABC NEWS SERVIÇO 10": "https://i.imgur.com/abcnews.jpg",
    "REUTERS SERVIÇO": "https://i.imgur.com/4xSEoNK.jpg",
    "REUTERS SERVIÇO 2": "https://i.imgur.com/4xSEoNK.jpg",
    "DHA SERVIÇO 1": "https://i.imgur.com/foxnews.jpg",
    "DHA SERVIÇO 2": "https://i.imgur.com/foxnews.jpg",
    "YNET NEWS SERVIÇO 1": "https://i.imgur.com/foxnews.jpg",
    "YNET NEWS SERVIÇO 2": "https://i.imgur.com/foxnews.jpg",
    "YNET NEWS SERVIÇO 3": "https://i.imgur.com/foxnews.jpg",
    "YNET NEWS SERVIÇO 4": "https://i.imgur.com/foxnews.jpg",
    "SKY NEWS - SERVIÇO 1": "https://i.imgur.com/ZsPb8nL.jpg",
    "SKY NEWS - SERVIÇO 2": "https://i.imgur.com/ZsPb8nL.jpg",
    "SKY NEWS - SERVIÇO 3": "https://i.imgur.com/ZsPb8nL.jpg",
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
    print("CORRECAO COMPLETA lista5.m3u v7")
    print("=" * 60)
    
    channels = parse_m3u("lista5.m3u")
    print(f"Canais encontrados: {len(channels)}")
    
    print("\nProcessando canais...")
    processed = []
    tvg_added = 0
    logo_added = 0
    logo_fixed = 0
    
    for ch in channels:
        name = ch["name"]
        tvg_id = ch["tvg_id"]
        tvg_logo = ch["tvg_logo"]
        group = ch["group"]
        url = ch["url"]
        
        if not tvg_id and name in CORRECT_TVG_IDS:
            tvg_id = CORRECT_TVG_IDS[name]
            tvg_added += 1
        
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
    print(f"  tvg-id adicionados: {tvg_added}")
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
        f.write(f"tvg-id adicionados: {tvg_added}\n")
        f.write(f"logos adicionados: {logo_added}\n")
        f.write(f"logos corrigidos: {logo_fixed}\n")
        f.write(f"EPG: {EPG_URL}\n")
        f.write(f"\nCanais com tvg-id:\n")
        for ch in processed:
            if ch["tvg_id"]:
                f.write(f"  {ch['name'][:40]:<40} -> {ch['tvg_id']}\n")
    
    print("\nRelatorio: lista5_relatorio.txt")

if __name__ == "__main__":
    main()
