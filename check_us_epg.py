#!/usr/bin/env python3
import urllib.request
import ssl
import gzip
import xml.etree.ElementTree as ET

def download_epg_portion(url, max_size=10*1024*1024):
    """Download EPG XML file (partial)"""
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0'
        })
        
        response = urllib.request.urlopen(req, timeout=60, context=ctx)
        data = response.read(max_size)
        
        if url.endswith('.gz'):
            data = gzip.decompress(data)
        
        return data.decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"Erro ao baixar {url}: {e}")
        return None

def search_channel_ids(xml_content, search_terms):
    """Search for channel IDs containing search terms"""
    found = {}
    try:
        root = ET.fromstring(xml_content)
        for channel in root.findall('.//channel'):
            channel_id = channel.get('id', '')
            display_names = [dn.text for dn in channel.findall('display-name') if dn.text]
            
            for term in search_terms:
                if term.lower() in channel_id.lower() or any(term.lower() in dn.lower() for dn in display_names):
                    if term not in found:
                        found[term] = []
                    found[term].append({
                        'id': channel_id,
                        'names': display_names
                    })
    except Exception as e:
        print(f"Erro ao parsear XML: {e}")
    return found

def main():
    # Download US EPG (partial - first 10MB)
    print("Baixando EPG dos EUA (parcial)...")
    xml_content = download_epg_portion("https://iptv-epg.org/files/epg-us.xml.gz", max_size=10*1024*1024)
    
    if not xml_content:
        print("Falha ao baixar EPG")
        return
    
    print(f"Tamanho baixado: {len(xml_content)} caracteres")
    
    # Search for specific channels
    search_terms = [
        "ABC News", "DW", "Deutsche Welle", "Estrella", 
        "Telemundo", "Al Jazeera", "BBC", "Fox News",
        "CNN", "Bloomberg", "NHK"
    ]
    
    print("\nBuscando canais no EPG...")
    found = search_channel_ids(xml_content, search_terms)
    
    for term, channels in found.items():
        print(f"\n'{term}' encontrado:")
        for ch in channels[:5]:  # Show first 5 results
            print(f"  ID: {ch['id']}")
            print(f"  Nomes: {ch['names']}")
    
    # Also search for exact matches
    print("\n" + "="*60)
    print("Buscando IDs exatos que estão no M3U...")
    m3u_ids = [
        "ABCNewsLive.us", "DWEnglish.us", "EstrellaTV.us",
        "AztecaInternacional.us", "NoticiasTelemundoAHORA.us",
        "AlJazeera.us", "BBCWorldNews.us"
    ]
    
    for channel in ET.fromstring(xml_content).findall('.//channel'):
        channel_id = channel.get('id', '')
        if channel_id in m3u_ids:
            display_names = [dn.text for dn in channel.findall('display-name') if dn.text]
            print(f"  ✓ Encontrado: {channel_id} -> {display_names}")

if __name__ == '__main__':
    main()