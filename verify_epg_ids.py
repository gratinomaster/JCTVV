#!/usr/bin/env python3
import urllib.request
import ssl
import gzip
import xml.etree.ElementTree as ET
import json

def download_epg(url, max_size=5*1024*1024):
    """Download EPG XML file"""
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0'
        })
        
        response = urllib.request.urlopen(req, timeout=30, context=ctx)
        data = response.read(max_size)
        
        if url.endswith('.gz'):
            data = gzip.decompress(data)
        
        return data.decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"  Erro ao baixar {url}: {e}")
        return None

def extract_channel_ids(xml_content):
    """Extract channel IDs from EPG XML"""
    ids = set()
    try:
        root = ET.fromstring(xml_content)
        for channel in root.findall('.//channel'):
            channel_id = channel.get('id')
            if channel_id:
                ids.add(channel_id)
    except Exception as e:
        print(f"  Erro ao parsear XML: {e}")
    return ids

def main():
    epg_urls = [
        "https://iptv-epg.org/files/epg-us.xml.gz",
        "https://iptv-epg.org/files/epg-br.xml.gz",
        "https://iptv-epg.org/files/epg-ar.xml.gz",
        "https://iptv-epg.org/files/epg-mx.xml.gz",
        "https://iptv-epg.org/files/epg-ve.xml.gz"
    ]
    
    all_ids = {}
    
    for url in epg_urls:
        print(f"\nBaixando: {url}")
        xml_content = download_epg(url)
        if xml_content:
            ids = extract_channel_ids(xml_content)
            all_ids[url] = ids
            print(f"  Encontrados {len(ids)} channel-IDs")
            # Print first 20 IDs
            for i, cid in enumerate(sorted(ids)[:20]):
                print(f"    {cid}")
            if len(ids) > 20:
                print(f"    ... e mais {len(ids) - 20} IDs")
    
    # Now check which tvg-ids from our M3U are real
    print("\n" + "="*60)
    print("VERIFICANDO TVG-IDs DO M3U")
    print("="*60)
    
    m3u_tvgids = [
        "ABCNewsLive.us", "DWEnglish.us", "Telefe.ar", "ELTrece.ar", 
        "AmericaTV.ar", "Canal26.ar", "24/7CanaldeNoticias.ar", "NetTV.ar",
        "ArgentinisimaSatelital.ar", "Telemax.ar", "ElGarageTv.ar",
        "CanalDeLaCiudad.ar", "TN.ar", "TyCSports.ar", "Canal21.ar",
        "AMC.ar", "ComedyCentral.ar", "DisneyChannel.ar", "DisneyJunior.ar",
        "ElGourmet.ar", "MTV.ar", "Quiero.ar", "Sony.ar",
        "TelemundoInternacional.ar", "VTV.ar", "AztecaUno.mx", "adn40.mx",
        "ImagenTV.mx", "MilenioTV.mx", "Canal14.mx", "TVUNAM.mx",
        "CanalDelCongreso.mx", "JusticiaTV.mx", "CanalMexiquense.mx",
        "TVCuatro.mx", "Canal44-udgtv.mx", "Canal4.mx", "Sony.mx",
        "TLNovelas.mx", "DePelícula.mx", "Telemundo.mx", "Univision.mx",
        "EstrellaTV.us", "EWTN.mx", "RussiaToday.mx",
        "Canal12TelevisaTijuana.mx", "AztecaInternacional.us",
        "NoticiasTelemundoAHORA.us", "RedeVida.br", "AlJazeera.us",
        "BBCWorldNews.us"
    ]
    
    # Check each tvg-id against all EPG sources
    found_in_epg = {}
    not_found = []
    
    for tvg_id in m3u_tvgids:
        found = False
        for url, ids in all_ids.items():
            if tvg_id in ids:
                if tvg_id not in found_in_epg:
                    found_in_epg[tvg_id] = []
                found_in_epg[tvg_id].append(url)
                found = True
        if not found:
            not_found.append(tvg_id)
    
    print(f"\nTVG-IDs encontrados no EPG: {len(found_in_epg)}")
    for tvg_id, sources in found_in_epg.items():
        print(f"  ✓ {tvg_id} -> {len(sources)} fonte(s)")
    
    print(f"\nTVG-IDs NÃO encontrados no EPG: {len(not_found)}")
    for tvg_id in not_found:
        print(f"  ✗ {tvg_id}")
    
    # Save results
    results = {
        'found_in_epg': found_in_epg,
        'not_found': not_found,
        'epg_ids_count': {url: len(ids) for url, ids in all_ids.items()}
    }
    
    with open('/home/runner/work/JCTVV/JCTVV/epg_verification.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print("\nResultados salvos em epg_verification.json")

if __name__ == '__main__':
    main()