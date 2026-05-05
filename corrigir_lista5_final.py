#!/usr/bin/env python3
"""
Corrige lista5.m3u:
- Remove duplicatas
- Mantém apenas URLs master (não variantes/audio)
- Adiciona tvg-id para EPG
- Adiciona url-tvg com fonte EPG
- Verifica tvg-logo (.jpg, sem imgur)
- Testa URLs dos streams
- Verificação básica de segurança
"""
import requests
import re
from datetime import datetime
from urllib.parse import urlparse
import gzip
import xml.etree.ElementTree as ET

# EPG Configuration
EPG_URL = "https://epg.pw/xmltv/epg_US.xml.gz"

# Channel mapping: keyword -> (tvg-id, tvg-name, tvg-logo)
CHANNEL_MAP = {
    "abcnews": {
        "tvg_id": "465150",
        "tvg_name": "ABC News Live",
        "tvg_logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
        "group": "NEWS WORLD"
    },
    "foxbusiness": {
        "tvg_id": "464766",
        "tvg_name": "Fox Business HD",
        "tvg_logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/8f89f57f-8137-49ee-be15-e0daecf8c33e/cb79295d-7a26-48db-9f94-c2aaffd62260/1280x720/match/400/225/image.jpg",
        "group": "NEWS WORLD"
    },
    "foxnews": {
        "tvg_id": "465372",
        "tvg_name": "Fox News Channel HD",
        "tvg_logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/15de0523-3be4-4a9a-8159-7020114e7036/b6ff623a-26d6-4fd9-8bb8-0856adbf38ce/1280x720/match/676/380/image.jpg",
        "group": "NEWS WORLD"
    },
    "cbsnews": {
        "tvg_id": "464941",
        "tvg_name": "CBS News 24/7",
        "tvg_logo": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
        "group": "NEWS WORLD"
    }
}

def is_master_url(url):
    """Check if URL is a master playlist (not variant/audio)"""
    lower = url.lower()
    # Skip audio-only streams
    if 'audio' in lower:
        return False
    # Skip specific bitrate variants
    if re.search(r'/\d+[_-]', url.split('?')[0].split('/')[-1]):
        return False
    # Skip if path contains specific variant patterns
    if re.search(r'bandwidth/\d+', lower):
        return False
    return True

def classify_channel(url):
    """Classify URL by channel type"""
    lower = url.lower()
    if 'abcnews' in lower or 'abcn' in lower:
        return 'abcnews'
    elif 'foxbusiness' in lower or 'fbn' in lower:
        return 'foxbusiness'
    elif 'foxnews' in lower:
        return 'foxnews'
    elif 'cbsnews' in lower or 'cbsn' in lower or 'dai.google.com' in lower:
        return 'cbsnews'
    return None

def test_url(url, timeout=10):
    """Test if URL returns valid response"""
    try:
        resp = requests.head(url, timeout=timeout, allow_redirects=True,
                           headers={'User-Agent': 'Mozilla/5.0'})
        return resp.status_code < 400, resp.status_code
    except:
        try:
            resp = requests.get(url, timeout=timeout, stream=True,
                              headers={'User-Agent': 'Mozilla/5.0'})
            status = resp.status_code < 400
            resp.close()
            return status, resp.status_code
        except:
            return False, 0

def check_url_safety(url):
    """Basic URL safety check"""
    # Check for known malicious patterns
    dangerous_patterns = ['.ru/', '.tk/', '.ml/', '.ga/', '.cf/', 'bit.ly', 'tinyurl']
    lower = url.lower()
    for pattern in dangerous_patterns:
        if pattern in lower:
            return False, f"Contains suspicious pattern: {pattern}"
    
    # Check domain reputation (basic)
    domain = urlparse(url).netloc
    known_good_domains = [
        'dssott.com', 'akamaized.net', 'foxbusiness.com', 'foxnews.com',
        'cbsnewsstatic.com', 'google.com', 'gvt1.com', 'boldcdn.net',
        'boltdns.net', 'abcnews.com', 'keyframe-cdn.abcnews.com'
    ]
    for good in known_good_domains:
        if good in domain:
            return True, "Known good domain"
    
    return True, "Unknown domain (allowed)"

def verify_epg_programming():
    """Verify EPG has programming for today, tomorrow, day after"""
    print("Verificando programação EPG...")
    try:
        resp = requests.get(EPG_URL, timeout=30, headers={'Accept-Encoding': 'gzip'})
        resp.raise_for_status()
        xml_data = gzip.decompress(resp.content).decode('utf-8')
        root = ET.fromstring(xml_data)
        
        hoje = datetime.now().strftime("%Y%m%d")
        amanha = (datetime.now().replace(day=datetime.now().day + 1) if datetime.now().day < 28 
                  else (datetime.now().replace(month=datetime.now().month + 1, day=1) if datetime.now().month < 12 
                        else datetime.now().replace(year=datetime.now().year + 1, month=1, day=1))).strftime("%Y%m%d")
        
        from datetime import timedelta
        amanha = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
        depois = (datetime.now() + timedelta(days=2)).strftime("%Y%m%d")
        
        count_hoje = count_amanha = count_depois = 0
        channel_ids = set()
        
        for prog in root.findall("programme"):
            start = prog.get("start", "")[:8]
            if start == hoje:
                count_hoje += 1
            elif start == amanha:
                count_amanha += 1
            elif start == depois:
                count_depois += 1
        
        for ch in root.findall("channel"):
            channel_ids.add(ch.get("id"))
        
        print(f"  Hoje: {count_hoje} programas")
        print(f"  Amanhã: {count_amanha} programas")
        print(f"  Depois de amanhã: {count_depois} programas")
        print(f"  Canais: {len(channel_ids)}")
        
        target_ids = ["465150", "464766", "465372", "464941"]
        for tid in target_ids:
            if tid in channel_ids:
                print(f"  [OK] Canal {tid} encontrado no EPG")
            else:
                print(f"  [WARN] Canal {tid} NÃO encontrado no EPG")
        
        return count_hoje > 0 and count_amanha > 0
    except Exception as e:
        print(f"  ERRO: {e}")
        return False

def fix_logo_url(logo_url):
    """Ensure logo URL is .jpg and not imgur"""
    if not logo_url:
        return None
    if 'imgur.com' in logo_url.lower():
        return None  # Will be replaced with default
    return logo_url

def main():
    print("=" * 70)
    print("CORREÇÃO lista5.m3u")
    print("=" * 70)
    
    # Verify EPG first
    epg_ok = verify_epg_programming()
    print(f"\nEPG válido: {'SIM' if epg_ok else 'NÃO'}")
    
    # Read original file
    with open('lista5.m3u', 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    print(f"\nLinhas originais: {len(lines)}")
    
    # Parse channels
    channels = []
    current_info = None
    
    for line in lines:
        line = line.strip()
        if line.startswith('#EXTINF'):
            current_info = line
        elif line and not line.startswith('#') and current_info:
            channels.append((current_info, line))
            current_info = None
    
    print(f"Canais encontrados: {len(channels)}")
    
    # Process channels
    seen_urls = set()
    processed = []
    skipped_dup = 0
    skipped_variant = 0
    skipped_unsafe = 0
    tested = 0
    working = 0
    
    for info, url in channels:
        # Skip duplicates
        if url in seen_urls:
            skipped_dup += 1
            continue
        seen_urls.add(url)
        
        # Skip non-master URLs
        if not is_master_url(url):
            skipped_variant += 1
            continue
        
        # Classify channel
        channel_type = classify_channel(url)
        if not channel_type:
            print(f"  [WARN] Canal não classificado: {url[:80]}...")
            continue
        
        ch = CHANNEL_MAP[channel_type]
        
        # Safety check
        safe, reason = check_url_safety(url)
        if not safe:
            print(f"  [SKIP] URL insegura: {reason}")
            skipped_unsafe += 1
            continue
        
        # Test URL
        tested += 1
        is_working, status = test_url(url)
        if is_working:
            working += 1
            status_str = f"OK ({status})"
        else:
            status_str = f"FALHA ({status})"
        
        print(f"  [{status_str}] {ch['tvg_name']}: {url[:70]}...")
        
        # Build new EXTINF with tvg-id and url-tvg
        new_info = (
            f'#EXTINF:-1 tvg-id="{ch["tvg_id"]}" '
            f'tvg-name="{ch["tvg_name"]}" '
            f'tvg-logo="{ch["tvg_logo"]}" '
            f'group-title="{ch["group"]}" '
            f'url-tvg="{EPG_URL}",'
            f'{ch["tvg_name"]}'
        )
        
        processed.append((new_info, url))
    
    print(f"\nResumo:")
    print(f"  Duplicatas removidas: {skipped_dup}")
    print(f"  Variantes/audio removidos: {skipped_variant}")
    print(f"  URLs inseguras: {skipped_unsafe}")
    print(f"  URLs testadas: {tested}")
    print(f"  URLs funcionando: {working}")
    print(f"  Canais finais: {len(processed)}")
    
    # Write output
    output_path = 'lista5.m3u'
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('#EXTM3U\n')
        for info, url in processed:
            f.write(f'{info}\n')
            f.write(f'{url}\n')
    
    print(f"\nArquivo salvo: {output_path}")
    
    # Verify output
    with open(output_path, 'r') as f:
        final_lines = f.readlines()
    print(f"Linhas no arquivo final: {len(final_lines)}")
    
    # Verify all channels have tvg-id and url-tvg
    for line in final_lines:
        if line.startswith('#EXTINF'):
            if 'tvg-id=' not in line:
                print(f"  [ERRO] Canal sem tvg-id: {line[:80]}")
            if 'url-tvg=' not in line:
                print(f"  [ERRO] Canal sem url-tvg: {line[:80]}")
            if 'tvg-logo=' not in line:
                print(f"  [ERRO] Canal sem tvg-logo: {line[:80]}")
            elif '.jpg' not in line.lower():
                print(f"  [ERRO] Logo não é .jpg: {line[:80]}")
            if 'imgur.com' in line.lower():
                print(f"  [ERRO] Logo usa imgur: {line[:80]}")

if __name__ == "__main__":
    main()
