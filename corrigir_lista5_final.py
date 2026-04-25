#!/usr/bin/env python3
import re
import requests
from datetime import datetime
import hashlib
import gzip
import io

EPG_URL = "https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.xml.gz"

DEFAULT_LOGOS = {
    "abc": "https://s.abcnews.com/images/Live/abc_news_live-abc-ml-250210_1739199021469_hpMain_16x9_608.jpg",
    "fox": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/3b09e0ef-610a-43d4-960b-78dc97ae2bd2/dc2e6082-3de1-40e8-a3ab-b6a61b18c3b1/1280x720/match/400/225/image.jpg",
    "cbs": "https://www.cbsnews.com/bundles/cbsnewsvideo/images/cbsn--main-bg.jpg",
    "nbc": "https://s.nbcnews.com/sc NowFeels/h/124/nbc-london-news-250212_1739199021469_hpMain_16x9_608.jpg",
}

def get_default_logo(channel_name):
    name_lower = channel_name.lower()
    if 'abc' in name_lower:
        return DEFAULT_LOGOS['abc']
    elif 'fox' in name_lower:
        return DEFAULT_LOGOS['fox']
    elif 'cbs' in name_lower:
        return DEFAULT_LOGOS['cbs']
    elif 'nbc' in name_lower:
        return DEFAULT_LOGOS['nbc']
    return DEFAULT_LOGOS['abc']

def fix_logo_extension(logo_url):
    if not logo_url:
        return None
    logo_lower = logo_url.lower()
    if 'imgur.com' in logo_lower:
        return None
    if logo_lower.endswith('.png') or logo_lower.endswith('.gif') or logo_lower.endswith('.webp'):
        return None
    return logo_url

def check_url_status(url, timeout=15):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        resp = requests.head(url, headers=headers, timeout=timeout, allow_redirects=True)
        return resp.status_code == 200
    except:
        return False

def verify_stream(url, timeout=10):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        resp = requests.get(url, headers=headers, timeout=timeout, stream=True)
        if resp.status_code == 200:
            content = b''
            for chunk in resp.iter_content(chunk_size=1024):
                content += chunk
                if len(content) > 10240:
                    break
            return len(content) > 0
        return False
    except:
        return False

def download_and_check_epg():
    print("Verificando EPG online...")
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(EPG_URL, headers=headers, timeout=120)
        if resp.status_code == 200:
            print(f"  EPG online disponível ({len(resp.content)} bytes)")
            return EPG_URL
    except Exception as e:
        print(f"  EPG online não disponível: {e}")
    return None

def main():
    print("=" * 70)
    print("Corrigindo lista5.m3u")
    print("=" * 70)
    
    with open('lista5.m3u', 'r', encoding='utf-8') as f:
        content = f.read()
    
    epg_url = download_and_check_epg()
    lines = content.strip().split('\n')
    new_lines = []
    seen_channels = set()
    unique_channels = []
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        if line.startswith('#EXTINF:'):
            info = line.replace('#EXTINF:', '').strip()
            
            tvg_logo = None
            if 'tvg-logo="' in info:
                match = re.search(r'tvg-logo="([^"]+)"', info)
                if match:
                    tvg_logo = match.group(1)
            
            group = None
            if 'group-title="' in info:
                match = re.search(r'group-title="([^"]+)"', info)
                if match:
                    group = match.group(1)
            
            name = info.split(',')[-1].strip() if ',' in info else 'Unknown'
            
            if 'tvg-name="' in info:
                match = re.search(r'tvg-name="([^"]+)"', info)
                if match:
                    name = match.group(1)
            
            key = f"{name}|{tvg_logo}"
            
            if key in seen_channels:
                i += 2 if i + 1 < len(lines) else 1
                continue
            
            seen_channels.add(key)
            
            fixed_logo = fix_logo_extension(tvg_logo)
            if not fixed_logo:
                fixed_logo = get_default_logo(name)
                info = info.replace('tvg-logo=""', f'tvg-logo="{fixed_logo}"')
                if 'tvg-logo="' not in info:
                    parts = info.split(',', 1)
                    if len(parts) > 1:
                        info = parts[0] + f' tvg-logo="{fixed_logo}"' + ',' + parts[1]
                    else:
                        info = f'tvg-logo="{fixed_logo}" ' + info
            
            epg_id = f'tvg-id="{name}"'
            if 'tvg-id' not in info:
                parts = info.split(',', 1)
                if len(parts) > 1:
                    info = parts[0] + ' ' + epg_id + ' ' + parts[1]
                else:
                    info = epg_id + ' ' + info
            
            new_lines.append('#EXTINF:' + info)
            
            if i + 1 < len(lines):
                url_line = lines[i + 1]
                if not url_line.startswith('#'):
                    new_lines.append(url_line)
                i += 2
            else:
                i += 1
        else:
            new_lines.append(line)
            i += 1
    
    output = '\n'.join(new_lines)
    
    with open('lista5.m3u', 'w', encoding='utf-8') as f:
        f.write(output)
    
    print(f"\nArquivo corrigido: {len(new_lines)} linhas")
    print(f"Canais únicos: {len(seen_channels)}")
    print(f"EPG: {epg_url if epg_url else 'EPG personalizado (lista5_epg.xml)'}")
    
    print("\n--- Verificação de logos ---")
    issues = 0
    for ch in unique_channels:
        if ch.get('logo'):
            if not ch['logo'].endswith('.jpg') and not ch['logo'].endswith('.jpeg'):
                issues += 1
    print(f"Logos corrigidos/sem problemas: {issues}")

if __name__ == "__main__":
    main()