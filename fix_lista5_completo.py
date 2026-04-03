#!/usr/bin/env python3
import requests
import gzip
import re
import base64
import json
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import xml.etree.ElementTree as ET

VIRUSTOTAL_API_URL = "https://www.virustotal.com/api/v3/urls"

EPG_SOURCES = [
    ("https://iptv-epg.org/files/epg-br.xml.gz", "IPTV-EPG BR"),
    ("https://iptv-org.github.io/epg/guides/br.xml", "IPTV-ORG BR"),
]

CHANNEL_MAPPING = {
    "RecordTV Conquista HD": {"tvg_id": "RecordTVBrasil.br", "epg_source": "br"},
    "TV Brasil Central": {"tvg_id": "TVBrasil.br", "epg_source": "br"},
    "Rede Meio Norte HD": {"tvg_id": "RedeMeioNorte.br", "epg_source": "br"},
    "Band Belém": {"tvg_id": "RBATV.br", "epg_source": "br"},
    "Nova Era TV": {"tvg_id": "NovaEraTV.br", "epg_source": "br"},
    "TV Cidade de Petrópolis": {"tvg_id": "TVCidadedePetropolis.br", "epg_source": "br"},
    "Aurora Arte (480p)": {"tvg_id": "AuroraArte.it", "epg_source": "it"},
    "RTL-TVI (1080p)": {"tvg_id": "RTLTVI.be", "epg_source": "be"},
    "Senado Italiano": {"tvg_id": "SenatoWebTV1.it", "epg_source": "it"},
    "Camara dos Deputados - ITALIA": {"tvg_id": "RadioRadicale.it", "epg_source": "it"},
    "FRANCE 2": {"tvg_id": "France2.fr", "epg_source": "fr"},
    "FRANCE 5": {"tvg_id": "France5.fr", "epg_source": "fr"},
    "RT Documentary": {"tvg_id": "RTDocumentary.ru", "epg_source": "ru"},
    "RT America": {"tvg_id": "RTAmerica.ru", "epg_source": "ru"},
    "RT News": {"tvg_id": "RTNews.ru", "epg_source": "ru"},
    "RT Español 2": {"tvg_id": "RTenEspanol.ru", "epg_source": "ru"},
    "ARTV": {"tvg_id": "artv.tv.vodafone.pt", "epg_source": "pt"},
    "ARTV 2": {"tvg_id": "artv.tv.vodafone.pt", "epg_source": "pt"},
    "ARTV 3": {"tvg_id": "artv.tv.vodafone.pt", "epg_source": "pt"},
    "ARTV 4": {"tvg_id": "artv.tv.vodafone.pt", "epg_source": "pt"},
    "TVI Ficção": {"tvg_id": "TVIFIC.meo.pt", "epg_source": "pt"},
    "TVI Ficção 2": {"tvg_id": "TVIFIC.meo.pt", "epg_source": "pt"},
    "TVI Ficção 3": {"tvg_id": "TVIFIC.meo.pt", "epg_source": "pt"},
    "V+ TVI": {"tvg_id": "VmaisTVI.pt", "epg_source": "pt"},
    "TVI REALITY": {"tvg_id": "tvireality.tv.vodafone.pt", "epg_source": "pt"},
    "Free Speech TV": {"tvg_id": "FreeSpeechTV.us", "epg_source": "us"},
    "TV Câmara": {"tvg_id": "TVCamara.br", "epg_source": "br"},
    "TV CÂMARA DOS DEPUTADOS HD": {"tvg_id": "TVCamara.br", "epg_source": "br"},
    "Telefe Canal 7 Jujuy": {"tvg_id": "TelefeArgentina.ar", "epg_source": "ar"},
    "Canal 57 Miami": {"tvg_id": "Canal57Miami.us", "epg_source": "us"},
    "Alcarria TV": {"tvg_id": "AlcarriaTV.es", "epg_source": "es"},
    "Canal 56": {"tvg_id": "Canal56.es", "epg_source": "es"},
    "ahlakid.com - Canal 2000 La Solana": {"tvg_id": "Canal2000LaSolana.es", "epg_source": "es"},
    "Deportivos: ETB Deportes": {"tvg_id": "ETBD.TV", "epg_source": "es"},
    "Informativos: 24h": {"tvg_id": "24Horas.TV", "epg_source": "es"},
    "Informativos: Negocios TV": {"tvg_id": "Negocios.TV", "epg_source": "es"},
    "REAL MADRID - ESPANHOL": {"tvg_id": "RealMadridTV.es", "epg_source": "es"},
    "REAL MADRID - INGLÊS": {"tvg_id": "RealMadridTV.en", "epg_source": "en"},
    "MyTime Movie Network (BR)": {"tvg_id": "MyTimeMovieNetwork.br", "epg_source": "br"},
    "Tracking Dangerous Heat and Severe Storms": {"tvg_id": "ABCNewsLive16.us", "epg_source": "us"},
    "View of Tel Aviv amid Iranian-Israeli ceasefire announcement": {"tvg_id": "ABCNewsLive16.us", "epg_source": "us"},
    "DC en route to the Netherlands": {"tvg_id": "ABCNewsLive16.us", "epg_source": "us"},
}

BRAND_MAPPINGS = {
    "globo": "GloboBrasil.br",
    "record": "RecordTVBrasil.br",
    "sbt": "SBTBrasil.br",
    "band": "BandBrasil.br",
    "rede tv": "RedeTV.br",
    "cultura": "Cultura.br",
    "tv cultura": "Cultura.br",
    "gazeta": "TVGazeta.br",
    "futura": "Futura.br",
    "cnn": "CNN.br",
    "cnn brasil": "CNNBrasil.br",
    "globo news": "GloboNews.br",
    "band news": "BandNews.br",
    "record news": "RecordNews.br",
    "jovem pan": "JovemPanNews.br",
    "fox": "FoxNewsChannel.br",
    "hbo": "HBO.br",
    "cinemax": "Cinemax.br",
    "telecine": "TelecinePremium.br",
    "espn": "ESPN.br",
    "sportv": "SporTV.br",
    "premiere": "PremiereClubes.br",
    "premiere clubes": "PremiereClubes.br",
    " TNT": "TNT.br",
    "sony": "SonyChannel.br",
    "warner": "WarnerChannel.br",
    "axn": "AXN.br",
    "universal": "Universal.br",
    "space": "Space.br",
    "megapix": "Megapix.br",
    "paramount": "ParamountChannel.br",
    "studio universal": "StudioUniversal.br",
    "hbo": "HBO.br",
    "hbo 2": "HBO2.br",
    "hbo family": "HBOFamily.br",
    "hbo plus": "HBOPlus.br",
    "hbo pop": "HBOPop.br",
    "hbo signature": "HBOSignature.br",
    "hbo mundi": "HBOMundi.br",
    "hbo xtreme": "HBOXtreme.br",
    "star channel": "StarChannel.br",
    "star life": "StarLife.br",
    "star hitz": "FOXPremium1.br",
    "star action": "FOXPremiumAction.br",
    "fx": "FX.br",
    "amc": "AMC.br",
    "a&e": "AandE.br",
    "tbs": "TBS.br",
    "comedy central": "ComedyCentral.br",
    "viva": "Viva.br",
    "multishow": "Multishow.br",
    "gnt": "GNT.br",
    "canal brasil": "CanalBrasil.br",
    "curta": "Curta.br",
    "trutv": "TruTV.br",
    "off": "Off.br",
    "tlc": "TLC.br",
    "history": "HistoryChannel.br",
    "nat geo": "NatGeo.br",
    "discovery": "DiscoveryChannel.br",
    "animal planet": "AnimalPlanet.br",
    "discovery turbo": "DiscoveryTurbo.br",
    "discovery theater": "DiscoveryTheater.br",
    "discovery world": "DiscoveryWorld.br",
    "disney": "DisneyChannel.br",
    "disney channel": "DisneyChannel.br",
    "disney junior": "DisneyJunior.br",
    "disney xd": "DisneyXD.br",
    "nick": "Nick.br",
    "nick jr": "NickJr.br",
    "cartoon": "CartoonNetwork.br",
    "cartoonito": "Cartoonito.br",
    "boomerang": "Boomerang.br",
    "gloob": "Gloob.br",
    "gloobinho": "Gloobinho.br",
    "nat geo kids": "NatGeoKids.br",
    "baby tv": "BabyTV.br",
    "tv ra tim bum": "TVRaTimBum.br",
    "discovery kids": "DiscoveryKids.br",
    "tooncast": "Tooncast.br",
    "woo hoo": "WooHoo.br",
    "climatempo": "Climatempo.br",
    "conmebol": "CONMEBOLTV1.br",
    "fifa": "FIFA+.br",
    "band sports": "BandSports.br",
    "espn 2": "ESPN2.br",
    "espn plus": "ESPNPlus.br",
    "premiere 2": "Premiere2.br",
    "premiere 3": "Premiere3.br",
    "premiere 4": "Premiere4.br",
    "premiere 5": "Premiere5.br",
    "premiere 6": "Premiere6.br",
    "premiere 7": "Premiere7.br",
    "premiere 8": "Premiere8.br",
    "premiere 9": "Premiere9.br",
    "premiere 10": "Premiere10.br",
    "sportv 2": "SporTV2.br",
    "sportv 3": "SporTV3.br",
    "arte 1": "Arte1.br",
    "tnt series": "TNTSeries.br",
    "tcm": "TCM.br",
    "film and arts": "filmandarts.br",
    "canção nova": "CancaoNova.br",
    "cnt": "CNT.br",
}

REGIONAL_BRASIL = [
    ("anhanguera", "GloboAnhanguera.br"),
    ("goiânia", "GloboAnhanguera.br"),
    ("goiania", "GloboAnhanguera.br"),
    ("rj", "GloboRJ.br"),
    ("rio", "GloboRJ.br"),
    ("sp", "GloboSP.br"),
    ("são paulo", "GloboSP.br"),
    ("sao paulo", "GloboSP.br"),
    ("bh", "GloboBH.br"),
    ("belo horizonte", "GloboBH.br"),
    ("belém", "GloboBelem.br"),
    ("belem", "GloboBelem.br"),
    ("ceará", "GloboCE.br"),
    ("ceara", "GloboCE.br"),
    ("fortaleza", "GloboCE.br"),
    ("brasília", "GloboBrasilia.br"),
    ("brasilia", "GloboBrasilia.br"),
    ("df", "GloboBrasilia.br"),
    ("amazonas", "GloboAmazonas.br"),
    ("manaus", "GloboAmazonas.br"),
    ("sul", "GloboSul.br"),
    ("sul de minas", "InterTV.br"),
    ("inter tv", "InterTV.br"),
    ("vale do paraíba", "GloboVale.br"),
    ("ribeirao", "EPTVRibeiro.br"),
    ("ribeirao preto", "EPTVRibeiro.br"),
    ("campinas", "EPTVCampinas.br"),
    ("sao carlos", "EPTVSaoCarlos.br"),
    ("cuiabá", "GloboCuiaba.br"),
    ("cuiaba", "GloboCuiaba.br"),
]

def extract_channel_name(line: str) -> str:
    line = line.strip()
    match = re.search(r',(.+)$', line)
    if match:
        return match.group(1).strip()
    return ""

def parse_m3u(filepath: str) -> List[Dict]:
    channels = []
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXTINF:'):
            url = lines[i + 1].strip() if i + 1 < len(lines) else ""
            channel_name = extract_channel_name(line)
            
            tvg_id_match = re.search(r'tvg-id="([^"]*)"', line)
            tvg_id = tvg_id_match.group(1) if tvg_id_match else ""
            
            tvg_logo_match = re.search(r'tvg-logo="([^"]*)"', line)
            tvg_logo = tvg_logo_match.group(1) if tvg_logo_match else ""
            
            group_match = re.search(r'group-title="([^"]*)"', line)
            group = group_match.group(1) if group_match else ""
            
            channels.append({
                "extinf": line,
                "url": url,
                "name": channel_name,
                "tvg_id": tvg_id,
                "tvg_logo": tvg_logo,
                "group": group,
            })
            i += 2
        else:
            i += 1
    return channels

def download_epg(epg_url: str) -> Optional[str]:
    try:
        print(f"  Baixando: {epg_url[:60]}...")
        response = requests.get(epg_url, timeout=120, headers={'Accept-Encoding': 'gzip'})
        response.raise_for_status()
        
        if epg_url.endswith('.gz'):
            content = gzip.decompress(response.content).decode('utf-8')
        else:
            content = response.text
        return content
    except Exception as e:
        print(f"  Erro: {e}")
        return None

def find_channel_in_epg(epg_content: str, tvg_id: str) -> Optional[Dict]:
    try:
        root = ET.fromstring(epg_content)
        for channel in root.findall("channel"):
            if channel.get("id") == tvg_id:
                display_name = channel.find("display-name")
                icon = channel.find("icon")
                return {
                    "id": channel.get("id"),
                    "name": display_name.text if display_name is not None else tvg_id,
                    "icon": icon.get("src") if icon is not None else ""
                }
        return None
    except Exception as e:
        return None

def test_epg_programming(epg_content: str, tvg_id: str) -> Dict:
    resultado = {
        "status": "sem_programacao",
        "hoje": 0,
        "amanha": 0,
        "depois_amanha": 0,
        "programas_hoje": [],
        "programas_amanha": [],
        "programas_depois": []
    }
    
    try:
        root = ET.fromstring(epg_content)
        
        hoje = datetime.now().strftime("%Y%m%d")
        amanha = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
        depois_amanha = (datetime.now() + timedelta(days=2)).strftime("%Y%m%d")
        
        for prog in root.findall("programme"):
            channel = prog.get("channel", "")
            if channel == tvg_id:
                start = prog.get("start", "")[:8]
                title_elem = prog.find("title")
                title = title_elem.text if title_elem is not None else "Sem título"
                
                if start[:8] == hoje:
                    resultado["hoje"] += 1
                    resultado["programas_hoje"].append(title)
                elif start[:8] == amanha:
                    resultado["amanha"] += 1
                    resultado["programas_amanha"].append(title)
                elif start[:8] == depois_amanha:
                    resultado["depois_amanha"] += 1
                    resultado["programas_depois"].append(title)
        
        if resultado["hoje"] > 0 and resultado["amanha"] > 0 and resultado["depois_amanha"] > 0:
            resultado["status"] = "completo"
        elif resultado["hoje"] > 0 or resultado["amanha"] > 0:
            resultado["status"] = "parcial"
        
        return resultado
    except Exception as e:
        return resultado

def get_tvg_id_for_channel(channel_name: str) -> Tuple[Optional[str], Optional[str]]:
    name_lower = channel_name.lower()
    
    if channel_name in CHANNEL_MAPPING:
        return CHANNEL_MAPPING[channel_name]["tvg_id"], CHANNEL_MAPPING[channel_name]["epg_source"]
    
    for keyword, tvg_id in BRAND_MAPPINGS.items():
        if keyword in name_lower:
            return tvg_id, "br"
    
    for keywords, tvg_id in REGIONAL_BRASIL:
        if isinstance(keywords, tuple):
            for kw in keywords:
                if kw in name_lower:
                    return tvg_id, "br"
        elif keywords in name_lower:
            return tvg_id, "br"
    
    return None, None

def check_virustotal(url: str, api_key: Optional[str] = None) -> Dict:
    resultado = {
        "status": "nao_verificado",
        "malicious": False,
        "suspicious": 0,
        "detection_ratio": "",
        "error": None
    }
    
    if not api_key:
        resultado["status"] = "sem_api_key"
        return resultado
    
    try:
        url_id = base64.urlsafe_b64encode(url.encode()).decode().strip("=")
        headers = {"x-apikey": api_key}
        
        response = requests.get(f"{VIRUSTOTAL_API_URL}/{url_id}", headers=headers, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            stats = data.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
            
            malicious = stats.get("malicious", 0)
            suspicious = stats.get("suspicious", 0)
            harmless = stats.get("harmless", 0)
            undetected = stats.get("undetected", 0)
            total = malicious + suspicious + harmless + undetected
            
            resultado["malicious"] = malicious > 0
            resultado["suspicious"] = suspicious
            resultado["detection_ratio"] = f"{malicious}/{total}" if total > 0 else "N/A"
            resultado["status"] = "verificado"
            
        elif response.status_code == 404:
            resultado["status"] = "nao_encontrado"
        else:
            resultado["error"] = f"HTTP {response.status_code}"
            
    except Exception as e:
        resultado["error"] = str(e)
    
    return resultado

def check_url_head(url: str) -> bool:
    try:
        response = requests.head(url, timeout=10, allow_redirects=True, 
                                 headers={'User-Agent': 'Mozilla/5.0'})
        return response.status_code in [200, 405]
    except:
        return False

def get_epg_url_for_source(epg_source: Optional[str], epg_sources: Dict) -> Optional[str]:
    if not epg_source:
        return None
    source_map = {
        "br": ["IPTV-EPG BR", "IPTV-ORG BR", "IPTV-EPG BR (local)"],
        "us": ["IPTV-ORG US"],
        "pt": ["IPTV-ORG PT"],
        "es": ["IPTV-ORG ES"],
        "it": ["IPTV-ORG IT"],
        "fr": ["IPTV-ORG FR"],
        "ru": ["IPTV-ORG RU"],
        "be": ["IPTV-EPG BE"],
        "ar": ["IPTV-EPG AR"],
    }
    
    preferred = source_map.get(epg_source, [])
    for name, url in epg_sources.items():
        if name in preferred:
            return url
    return None

def main():
    print("=" * 70)
    print("CORREÇÃO lista5.m3u - EPG + VIRUSTOTAL")
    print("=" * 70)
    
    m3u_path = "lista5.m3u"
    api_key = sys.argv[1] if len(sys.argv) > 1 else None
    
    channels = parse_m3u(m3u_path)
    print(f"\nCanais encontrados: {len(channels)}")
    
    print("\n" + "-" * 70)
    print("BAIXANDO EPGs...")
    print("-" * 70)
    
    epg_contents = {}
    epg_urls = {}
    
    for epg_url, name in EPG_SOURCES:
        print(f"\nTestando: {name}")
        if epg_url.startswith("epg-"):
            try:
                with open(epg_url, 'r', encoding='utf-8') as f:
                    content = f.read()
                if content and len(content) > 1000:
                    epg_contents[name] = content
                    epg_urls[name] = epg_url
                    print(f"  OK! (local) Tamanho: {len(content):,} bytes")
            except Exception as e:
                print(f"  Erro ao ler arquivo local: {e}")
        else:
            content = download_epg(epg_url)
            if content and len(content) > 1000:
                epg_contents[name] = content
                epg_urls[name] = epg_url
                print(f"  OK! Tamanho: {len(content):,} bytes")
            else:
                print(f"  FALHOU")
    
    br_epg = None
    br_epg_url = None
    if "IPTV-EPG BR" in epg_contents:
        br_epg = epg_contents["IPTV-EPG BR"]
        br_epg_url = epg_urls["IPTV-EPG BR"]
    
    print("\n" + "-" * 70)
    print("MAPEANDO CANAIS E ADICIONANDO EPG...")
    print("-" * 70)
    
    updated_channels = []
    channels_with_epg = {}
    
    for ch in channels:
        channel_name = ch["name"]
        tvg_id, epg_source = get_tvg_id_for_channel(channel_name)
        
        epg_url = None
        if tvg_id:
            epg_url = get_epg_url_for_source(epg_source, epg_urls)
            if not epg_url and br_epg_url:
                epg_url = br_epg_url
            
            attrs = []
            attrs.append(f'tvg-id="{tvg_id}"')
            if ch["tvg_logo"]:
                attrs.append(f'tvg-logo="{ch["tvg_logo"]}"')
            if ch["group"]:
                attrs.append(f'group-title="{ch["group"]}"')
            if epg_url:
                attrs.append(f'x-tvg-url="{epg_url}"')
            
            attrs_str = ' '.join(attrs)
            new_extinf = f'#EXTINF:-1 {attrs_str},{channel_name}'
            
            if tvg_id not in channels_with_epg:
                channels_with_epg[tvg_id] = {
                    "epg_source": epg_source,
                    "epg_url": epg_url
                }
                print(f"  {channel_name[:40]:<40} -> {tvg_id}")
            
            updated_channels.append({
                "extinf": new_extinf,
                "url": ch["url"],
                "name": channel_name,
                "tvg_id": tvg_id,
                "epg_source": epg_source
            })
        else:
            attrs = []
            if ch["tvg_id"] and ch["tvg_id"] != "N/A" and ch["tvg_id"] != "Undefined":
                attrs.append(f'tvg-id="{ch["tvg_id"]}"')
            if ch["tvg_logo"]:
                attrs.append(f'tvg-logo="{ch["tvg_logo"]}"')
            if ch["group"]:
                attrs.append(f'group-title="{ch["group"]}"')
            if br_epg_url:
                attrs.append(f'x-tvg-url="{br_epg_url}"')
            
            attrs_str = ' '.join(attrs)
            new_extinf = f'#EXTINF:-1 {attrs_str},{channel_name}'
            
            updated_channels.append({
                "extinf": new_extinf,
                "url": ch["url"],
                "name": channel_name,
                "tvg_id": ch["tvg_id"],
                "epg_source": None
            })
    
    print("\n" + "-" * 70)
    print("TESTANDO PROGRAMAÇÃO EPG (HOJE/AMANHÃ/DEPOIS DE AMANHÃ)...")
    print("-" * 70)
    
    epg_to_test = {}
    for tvg_id, info in channels_with_epg.items():
        epg_name = info["epg_source"]
        if epg_name and epg_name in epg_contents:
            epg_to_test[tvg_id] = epg_contents[epg_name]
        elif br_epg:
            epg_to_test[tvg_id] = br_epg
    
    channels_with_valid_epg = []
    channels_without_valid_epg = []
    
    for ch in updated_channels:
        tvg_id = ch.get("tvg_id")
        if tvg_id and tvg_id in epg_to_test:
            epg_content = epg_to_test[tvg_id]
            prog = test_epg_programming(epg_content, tvg_id)
            
            if prog["status"] in ["completo", "parcial"]:
                channels_with_valid_epg.append(ch)
                print(f"  OK  {tvg_id[:30]:<30} Hoje:{prog['hoje']:>3} Amanhã:{prog['amanha']:>3} Depois:{prog['depois_amanha']:>3}")
            else:
                channels_without_valid_epg.append((ch, prog))
                print(f"  LOW {tvg_id[:30]:<30} Hoje:{prog['hoje']:>3} Amanhã:{prog['amanha']:>3} Depois:{prog['depois_amanha']:>3}")
        else:
            channels_without_valid_epg.append((ch, {"status": "sem_epg"}))
    
    print("\n" + "-" * 70)
    print("VERIFICANDO URLs (VIRUSTOTAL + ACESSIBILIDADE)...")
    print("-" * 70)
    
    unique_urls = {}
    for ch in updated_channels:
        url = ch["url"]
        if url and url not in unique_urls:
            unique_urls[url] = ch["name"]
    
    print(f"URLs únicas para verificar: {len(unique_urls)}")
    
    malicious_channels = []
    inaccessible_channels = []
    
    if api_key:
        print("\nVerificando VirusTotal...")
        for url, name in list(unique_urls.items())[:20]:
            result = check_virustotal(url, api_key)
            if result["status"] == "verificado":
                if result["malicious"]:
                    malicious_channels.append(name)
                    print(f"  X  {name[:40]:<40} {result['detection_ratio']} - MALICIOSO!")
                elif result["suspicious"] > 0:
                    print(f"  !  {name[:40]:<40} {result['detection_ratio']} - SUSPEITO")
                else:
                    print(f"  OK {name[:40]:<40} {result['detection_ratio']}")
            else:
                print(f"  -  {name[:40]:<40} {result['status']}")
    else:
        print("\nSem API key do VirusTotal - verificando apenas acessibilidade")
    
    print("\nVerificando acessibilidade das URLs...")
    for url, name in unique_urls.items():
        if not check_url_head(url):
            inaccessible_channels.append(name)
            print(f"  X  {name[:40]:<40} - inacessivel")
    
    print("\n" + "-" * 70)
    print("GERANDO lista5.m3u FINAL...")
    print("-" * 70)
    
    final_channels = []
    removed_count = 0
    
    for ch in updated_channels:
        name = ch["name"]
        if name in malicious_channels:
            removed_count += 1
            print(f"  - Removido (VirusTotal): {name}")
        elif name in inaccessible_channels:
            removed_count += 1
            print(f"  - Removido (inacessível): {name}")
        else:
            final_channels.append(ch)
    
    unique_final = {}
    for ch in final_channels:
        key = ch["extinf"] + ch["url"]
        if key not in unique_final:
            unique_final[key] = ch
    
    print(f"\nCanais removidos: {removed_count}")
    print(f"Canais finais: {len(unique_final)}")
    
    with open(m3u_path, 'w', encoding='utf-8') as f:
        f.write("#EXTM3U\n")
        for key, ch in unique_final.items():
            f.write(ch["extinf"] + "\n")
            f.write(ch["url"] + "\n")
    
    print(f"\nOK! lista5.m3u atualizada!")
    print(f"  - Canais: {len(unique_final)}")
    print(f"  - EPG BR: {br_epg_url[:50] if br_epg_url else 'N/A'}...")
    
    if channels_without_valid_epg:
        print(f"\nCanais com EPG limitado:")
        for ch, prog in channels_without_valid_epg[:10]:
            status = prog.get("status", "unknown")
            print(f"  - {ch['name']} ({status})")

if __name__ == "__main__":
    main()
