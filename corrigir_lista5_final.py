#!/usr/bin/env python3
import requests
import gzip
import re
import xml.etree.ElementTree as ET
from datetime import datetime

EPG_URL = "https://epg.pw/xmltv/epg.xml.gz"

CORRECT_TVG_IDS = {
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
    "France24": "524078",
    "France24 Espanol": "524078",
    "Euronews English": "534189",
    "Euronews": "534189",
    "Euronews Español": "534189",
    "EURONEWS EN ITALIANO": "534189",
    "Sky News UK": "463753",
    "Sky News": "463753",
    "Sky News Arabia": "55795",
    "Sky News Extra 1": "463753",
    "Sky News Extra 2": "463753",
    "Sky News Extra 3": "463753",
    "Sky News Arabe": "55795",
    "SKY NEWS - SERVIÇO 1": "463753",
    "SKY NEWS - SERVIÇO 2": "463753",
    "SKY NEWS - SERVIÇO 3": "463753",
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
    "Aljazeera English": "369587",
    "Aljazeera Balkans": "AlJazeeraBalkans.ba",
    "Aljazeera Channel": "AlJazeeraChannel.qa",
    "Aljazeera Arabic": "AlJazeeraArabic.qa",
    "CBS News": "CBSNews.us",
    "ABC News": "ABCNews.us",
    "Fox News": "470504",
    "FOX News": "470504",
    "FOX NEWS USA": "470504",
    "MSNBC": "447005",
    "Bloomberg US": "12427",
    "Bloomberg": "12427",
    "Bloomberg Television": "12427",
    "Bloomberg Politics": "12427",
    "Bloomberg EU": "12427",
    "Bloomberg Europe Event": "12427",
    "Bloomberg Asia": "12427",
    "CNN": "12013",
    "CNN INTERNACIONAL": "12013",
    "CNN INTERNATIONAL": "12013",
    "CNN BRASIL": "426108",
    "CNN Brasil": "426108",
    "BBC News TV": "492871",
    "BBC News": "456641",
    "BBC World News": "456641",
    "BBC Arabic": "BBCArabic.uk",
    "CGTN": "CGTN.cn",
    "CGTN Arabic": "CGTNArabic.cn",
    "CGTN Documentary": "CGTNDocumentary.cn",
    "CGTN Español": "CGTNSpanish.cn",
    "VOA": "VOA.us",
    "VOA Persian": "VOA.us",
    "Reuters": "Reuters.uk",
    "REUTERS": "Reuters.uk",
    "REUTERS SERVIÇO": "Reuters.uk",
    "REUTERS SERVIÇO 2": "Reuters.uk",
    "GLOBO NEWS": "426168",
    "BAND NEWS": "426077",
    "Band News HD": "426077",
    "JOVEM PAN NEWS": "417187",
    "Jovem Pan News": "417187",
    "BM&C NEWS": "BM&CNews.br",
    "RECORD NEWS": "523352",
    "SBT News": "SBTNews.br",
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
    "Yahoo! Finance (1080p)": "YahooFinance.us",
    "SPORTV": "426062",
    "SPORTV 2": "426082",
    "SPORTV 3": "426005",
    "ESPN": "ESPN.us",
    "ESPN 2": "ESPN2.us",
    "ESPN 3": "ESPN3.us",
    "ESPN 5": "ESPN5.us",
    "ESPN 6": "ESPN6.us",
    "BIS": "BIS.br",
    "MTV": "MTV.us",
    "MTV LIVE": "MTVLIVE.us",
    "Telesur English": "TelesurEnglish.ve",
    "TELESUR": "TelesurEnglish.ve",
    "teleSUR": "TelesurEnglish.ve",
    "teleSUR English": "TelesurEnglish.ve",
    "TELESUR ENG": "TelesurEnglish.ve",
    "TV5Monde Info": "TV5MondeInfo.fr",
    "Class CNBC": "ClassCNBC.it",
    "BFM TV": "BFMTV.fr",
    "BFM Business": "BFMBusiness.fr",
    "tagesschau24": "tagesschau24.de",
    "+24": "24Horas.es",
    "24 HORAS CL": "24Horas.es",
    "24 HORAS": "24Horas.es",
    "24Horas": "24Horas.es",
    "Canal 24 Horas Canarias": "24HorasCanarias.es",
    "Canal 24 Horas Catalunya": "24HorasCatalunya.es",
    "Canal 24 Horas": "24Horas.es",
    "RTVE 24h": "RTV.es",
    "TVG Eventos": "TVG.es",
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
    "Global News 2": "GlobalNewsCanada.ca",
    "Deutsche Welle Arabic": "DWArabic.de",
    "Deutsche Welle Español": "DWEspanol.de",
    "Deutsche Welle Deutsch+": "DWDeutsch.de",
    "Deutsche Welle": "DWEnglish.de",
    "Fox Business": "FRBD4100006OC",
    "Black News Channel": "BlackNewsChannel.us",
    "Cheddar News": "CheddarNews.us",
    "The Wall Street Journal Live": "TheWallStreetJournalLive.us",
    "CNN Money": "426108",
    "CNN BRASIL MONEY": "426108",
    "Al Araby": "AlAraby.tv",
    "Al Araby TV": "AlAraby.tv",
    "Al Araby TV 2": "AlAraby.tv",
    "Al Arabiya Al Hadath": "AlHadath.sa",
    "Alarabiya Portrait": "AlarabiyaPortrait.ae",
    "HispanTV": "HispanTV.ir",
    "Iran International": "IranInternational.uk",
    "TV Rain": "TVRain.ru",
    "Venezolana de Televisión": "VTV.ve",
    "Expressen TV": "ExpressenTV.se",
    "Univision": "Univision.us",
    "Notícias Univision 24/7": "Noticias_Univision_24_7",
    "Noticias Univision 24/7": "Noticias_Univision_24_7",
    "Noticias Telemundo Ahora": "Noticias_Telemundo_Ahora",
    "AP Direct": "AP_Direct",
    "AP Live Choice": "AP_LC_1",
    "ABC News (Australia)": "ABCNewsAustralia.au",
    "ABC Radio (Australia)": "ABCRadioAustralia.au",
    "Aleph News": "AlephNews.ro",
    "VOA TV Africa": "VoATV.us",
    "UN Web TV": "UNWebTV.us",
    "UN Web TV 2": "UNWebTV.us",
    "CAM CAPITOLIO EEUU": "USCapitol.us",
    "PRESIDENCIA USA": "USCapitol.us",
    "PENTAGONO USA": "USCapitol.us",
    "NewsNet": "W14DKD2.us",
    "W14DK-D": "W14DKD2.us",
    "CNN CHILE": "CNNChile.cl",
    "El Trece": "ElTrece.ar",
    "MEGANOTICIAS": "Mega.cl",
    "MEGANOTICIAS 2": "Mega.cl",
    "MEGANOTICIAS 3": "Mega.cl",
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
    "NTV News24": "NTVNews24.jp",
    "Fox Weather": "FOXWeather.us",
    "FOX WEATHER": "FOXWeather.us",
    "CBS NEWS SERVIÇO": "CBSNews.us",
    "CBS NEWS SERVIÇO 2": "CBSNews.us",
    "ABC NEWS SERVIÇO": "ABCNews.us",
    "ABC NEWS SERVIÇO 1": "ABCNews.us",
    "ABC NEWS SERVIÇO 2": "ABCNews.us",
    "ABC NEWS SERVIÇO 3": "ABCNews.us",
    "ABC NEWS SERVIÇO 4": "ABCNews.us",
    "ABC NEWS SERVIÇO 5": "ABCNews.us",
    "ABC NEWS SERVIÇO 6": "ABCNews.us",
    "ABC NEWS SERVIÇO 7": "ABCNews.us",
    "ABC NEWS SERVIÇO 8": "ABCNews.us",
    "ABC NEWS SERVIÇO 9": "ABCNews.us",
    "ABC NEWS SERVIÇO 10": "ABCNews.us",
    "DHA SERVIÇO 1": "DHA.tr",
    "DHA SERVIÇO 2": "DHA.tr",
    "YNET NEWS SERVIÇO 1": "YnetNews.il",
    "YNET NEWS SERVIÇO 2": "YnetNews.il",
    "YNET NEWS SERVIÇO 3": "YnetNews.il",
    "YNET NEWS SERVIÇO 4": "YnetNews.il",
    "IRIB UHD": "IRIBUHD.ir",
    "IRINN2 Live Farsi News": "IRINN2.ir",
    "IRINN Live Farsi News": "IRINN.ir",
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
    "SKY NEWS - SERVIÇO 1": "https://i.imgur.com/ZsPb8nL.jpg",
    "SKY NEWS - SERVIÇO 2": "https://i.imgur.com/ZsPb8nL.jpg",
    "SKY NEWS - SERVIÇO 3": "https://i.imgur.com/ZsPb8nL.jpg",
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
    "Aljazeera Channel": "https://i.imgur.com/NXFkYFj.jpg",
    "Aljazeera Arabic": "https://i.imgur.com/NXFkYFj.jpg",
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
    "Bloomberg Asia": "https://i.imgur.com/idRFfhY.jpg",
    "CNN": "https://i.imgur.com/xWglicB.jpg",
    "CNN INTERNACIONAL": "https://i.imgur.com/xWglicB.jpg",
    "CNN INTERNATIONAL": "https://i.imgur.com/xWglicB.jpg",
    "CNN BRASIL": "https://i.imgur.com/cnnbrasil.jpg",
    "CNN Brasil": "https://i.imgur.com/cnnbrasil.jpg",
    "CNN Money": "https://i.imgur.com/cnnbrasil.jpg",
    "CNN BRASIL MONEY": "https://i.imgur.com/cnnbrasil.jpg",
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
    "VOA TV Africa": "https://i.imgur.com/rtRnlqN.jpg",
    "Reuters": "https://i.imgur.com/4xSEoNK.jpg",
    "REUTERS": "https://i.imgur.com/4xSEoNK.jpg",
    "REUTERS SERVIÇO": "https://i.imgur.com/4xSEoNK.jpg",
    "REUTERS SERVIÇO 2": "https://i.imgur.com/4xSEoNK.jpg",
    "GLOBO NEWS": "https://i.imgur.com/Wu4ykxo.jpg",
    "BAND NEWS": "https://i.imgur.com/jCZzNjF.jpg",
    "Band News HD": "https://i.imgur.com/jCZzNjF.jpg",
    "JOVEM PAN NEWS": "https://i.imgur.com/aqgaka0.jpg",
    "Jovem Pan News": "https://i.imgur.com/aqgaka0.jpg",
    "BM&C NEWS": "https://i.imgur.com/tyW3Ppf.jpg",
    "RECORD NEWS": "https://i.imgur.com/record.jpg",
    "SBT News": "https://i.imgur.com/LnApLKd.jpg",
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
    "IRIB UHD": "https://i.imgur.com/8tzsC9h.jpg",
    "IRINN": "https://i.imgur.com/8tzsC9h.jpg",
    "IRINN Live Farsi News": "https://i.imgur.com/8tzsC9h.jpg",
    "IRINN2 Live Farsi News": "https://i.imgur.com/8tzsC9h.jpg",
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
    "SPORTV 2": "https://i.imgur.com/sportv.jpg",
    "SPORTV 3": "https://i.imgur.com/sportv.jpg",
    "ESPN": "https://i.imgur.com/espn.jpg",
    "ESPN 2": "https://i.imgur.com/espn.jpg",
    "ESPN 3": "https://i.imgur.com/espn.jpg",
    "ESPN 5": "https://i.imgur.com/espn.jpg",
    "ESPN 6": "https://i.imgur.com/espn.jpg",
    "BIS": "https://i.imgur.com/espn.jpg",
    "MTV": "https://i.imgur.com/espn.jpg",
    "MTV LIVE": "https://i.imgur.com/espn.jpg",
    "BFM TV": "https://i.imgur.com/bfmtv.jpg",
    "BFM Business": "https://i.imgur.com/bfmbusiness.jpg",
    "Telesur English": "https://i.imgur.com/telesur.jpg",
    "TELESUR": "https://i.imgur.com/telesur.jpg",
    "teleSUR": "https://i.imgur.com/telesur.jpg",
    "teleSUR English": "https://i.imgur.com/telesur.jpg",
    "TELESUR ENG": "https://i.imgur.com/telesur.jpg",
    "TV5Monde Info": "https://i.imgur.com/BFMMPwP.jpg",
    "Class CNBC": "https://i.imgur.com/qsmHgJ1.jpg",
    "tagesschau24": "https://i.imgur.com/tagesschau.jpg",
    "+24": "https://i.imgur.com/24horas.jpg",
    "24 HORAS CL": "https://i.imgur.com/24horas.jpg",
    "24 HORAS": "https://i.imgur.com/24horas.jpg",
    "24Horas": "https://i.imgur.com/24horas.jpg",
    "Canal 24 Horas Canarias": "https://i.imgur.com/IUVRm5L.jpg",
    "Canal 24 Horas Catalunya": "https://i.imgur.com/IUVRm5L.jpg",
    "Canal 24 Horas": "https://i.imgur.com/IUVRm5L.jpg",
    "TVG Eventos": "https://i.imgur.com/IUVRm5L.jpg",
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
    "Deutsche Welle Arabic": "https://i.imgur.com/8MRNFb9.jpg",
    "Deutsche Welle Español": "https://i.imgur.com/8MRNFb9.jpg",
    "Deutsche Welle Deutsch+": "https://i.imgur.com/8MRNFb9.jpg",
    "Deutsche Welle": "https://i.imgur.com/8MRNFb9.jpg",
    "Fox Business": "https://i.imgur.com/foxnews.jpg",
    "Black News Channel": "https://i.imgur.com/foxnews.jpg",
    "Cheddar News": "https://i.imgur.com/Y3vQaf5.jpg",
    "The Wall Street Journal Live": "https://i.imgur.com/4xSEoNK.jpg",
    "Al Araby": "https://i.imgur.com/NXFkYFj.jpg",
    "Al Araby TV": "https://i.imgur.com/NXFkYFj.jpg",
    "Al Araby TV 2": "https://i.imgur.com/NXFkYFj.jpg",
    "Al Arabiya Al Hadath": "https://i.imgur.com/NXFkYFj.jpg",
    "Alarabiya Portrait": "https://i.imgur.com/NXFkYFj.jpg",
    "Iran International": "https://i.imgur.com/8MRNFb9.jpg",
    "TV Rain": "https://i.imgur.com/rainews.jpg",
    "Venezolana de Televisión": "https://i.imgur.com/telesur.jpg",
    "Expressen TV": "https://i.imgur.com/ZsPb8nL.jpg",
    "Notícias Univision 24/7": "https://i.imgur.com/xWglicB.jpg",
    "Noticias Univision 24/7": "https://i.imgur.com/xWglicB.jpg",
    "Noticias Telemundo Ahora": "https://i.imgur.com/xWglicB.jpg",
    "AP Direct": "https://i.imgur.com/foxnews.jpg",
    "AP Live Choice": "https://i.imgur.com/foxnews.jpg",
    "ABC News (Australia)": "https://i.imgur.com/abcnews.jpg",
    "ABC Radio (Australia)": "https://i.imgur.com/abcnews.jpg",
    "Aleph News": "https://i.imgur.com/rainews.jpg",
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
    "CBS NEWS SERVIÇO 2": "https://i.imgur.com/cbsnews.jpg",
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
    "DHA SERVIÇO 1": "https://i.imgur.com/foxnews.jpg",
    "DHA SERVIÇO 2": "https://i.imgur.com/foxnews.jpg",
    "YNET NEWS SERVIÇO 1": "https://i.imgur.com/foxnews.jpg",
    "YNET NEWS SERVIÇO 2": "https://i.imgur.com/foxnews.jpg",
    "YNET NEWS SERVIÇO 3": "https://i.imgur.com/foxnews.jpg",
    "YNET NEWS SERVIÇO 4": "https://i.imgur.com/foxnews.jpg",
}

def is_valid_jpg_url(url):
    if not url:
        return False
    return url.lower().endswith('.jpg') or url.lower().endswith('.jpeg') or 'imgur.com' in url.lower()

def is_valid_stream(url):
    if not url:
        return False, "sem_url"
    if "youtube.com" in url.lower():
        return False, "youtube"
    if "watch?v=" in url.lower():
        return False, "youtube"
    if ".onion" in url.lower():
        return False, "onion"
    return True, "ok"

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
            channels.append({"url": url, "name": name, "tvg_id": tvg_id, "tvg_logo": tvg_logo, "group": group})
            i += 2
        else:
            i += 1
    return channels

def main():
    print("=" * 60)
    print("CORRECAO FINAL lista5.m3u v9")
    print("=" * 60)
    
    channels = parse_m3u("lista5.m3u")
    print(f"Canais encontrados: {len(channels)}")
    
    print("\nProcessando canais...")
    processed = []
    tvg_added = 0
    logo_added = 0
    logo_fixed = 0
    removed_youtube = 0
    
    for ch in channels:
        name = ch["name"]
        tvg_id = ch["tvg_id"]
        tvg_logo = ch["tvg_logo"]
        group = ch["group"]
        url = ch["url"]
        
        valid, reason = is_valid_stream(url)
        if not valid:
            if reason == "youtube":
                removed_youtube += 1
            continue
        
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
        processed.append({"extinf": new_extinf, "url": url, "name": name, "tvg_id": tvg_id, "tvg_logo": tvg_logo})
    
    unique = {}
    for ch in processed:
        key = ch["url"]
        if key not in unique:
            unique[key] = ch
    
    print(f"\nResumo:")
    print(f"  tvg-id adicionados: {tvg_added}")
    print(f"  logos adicionados: {logo_added}")
    print(f"  logos corrigidos: {logo_fixed}")
    print(f"  removidos YouTube: {removed_youtube}")
    print(f"  canais finais (sem duplicatas): {len(unique)}")
    
    with_tvg_id = sum(1 for c in unique.values() if c["tvg_id"])
    with_logo = sum(1 for c in unique.values() if c["tvg_logo"])
    
    print(f"  Com tvg-id: {with_tvg_id}")
    print(f"  Com logo: {with_logo}")
    
    with open("lista5.m3u", 'w', encoding='utf-8') as f:
        f.write(f'#EXTM3U x-tvg-url="{EPG_URL}"\n')
        for ch in unique.values():
            f.write(ch["extinf"] + "\n")
            f.write(ch["url"] + "\n")
    
    print(f"\nOK! lista5.m3u atualizada!")
    print(f"Canais finais: {len(unique)}")
    
    with open("lista5_relatorio.txt", 'w', encoding='utf-8') as f:
        f.write("=" * 60 + "\n")
        f.write("RELATORIO FINAL lista5.m3u\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        f.write(f"Canais encontrados: {len(channels)}\n")
        f.write(f"Canais finais: {len(unique)}\n")
        f.write(f"Canais removidos: {len(channels) - len(unique) + removed_youtube}\n\n")
        f.write(f"Canais com tvg-id: {with_tvg_id}\n")
        f.write(f"Canais com logo: {with_logo}\n\n")
        f.write(f"EPG: {EPG_URL}\n\n")
        f.write("Alteracoes:\n")
        f.write(f"  - tvg-id adicionados: {tvg_added}\n")
        f.write(f"  - logos adicionados: {logo_added}\n")
        f.write(f"  - logos corrigidos: {logo_fixed}\n")
        f.write(f"  - YouTube removidos: {removed_youtube}\n\n")
        f.write("Canais com EPG:\n")
        br_canais = ["GLOBO NEWS", "BAND NEWS", "CNN BRASIL", "RECORD NEWS", "JOVEM PAN NEWS", "BM&C NEWS", "Fox News", "BBC News", "CNN", "Euronews"]
        for name in br_canais:
            if name in [c["name"] for c in unique.values()]:
                tid = next((c["tvg_id"] for c in unique.values() if c["name"] == name), "")
                f.write(f"  - {name}: {tid}\n")
    
    print("\nRelatorio salvo: lista5_relatorio.txt")

if __name__ == "__main__":
    main()
