#!/usr/bin/env python3
import re
import urllib.request
import urllib.error
import ssl
import json
from datetime import datetime

def test_url(url, timeout=10):
    """Test if a URL is accessible"""
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        response = urllib.request.urlopen(req, timeout=timeout, context=ctx)
        return True, response.getcode()
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except urllib.error.URLError as e:
        return False, f"URL Error: {str(e.reason)}"
    except Exception as e:
        return False, str(e)

def parse_m3u(filepath):
    """Parse M3U file and extract channels"""
    channels = []
    current_extinf = None
    
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    for i, line in enumerate(lines):
        line = line.strip()
        if line.startswith('#EXTINF:'):
            current_extinf = {
                'line_num': i + 1,
                'content': line,
                'url': None,
                'has_url': False
            }
        elif current_extinf and line and not line.startswith('#'):
            current_extinf['url'] = line
            current_extinf['has_url'] = True
            channels.append(current_extinf)
            current_extinf = None
        elif current_extinf and not line:
            # Empty line after EXTINF - orphaned
            channels.append(current_extinf)
            current_extinf = None
    
    # Handle case where last EXTINF has no URL
    if current_extinf:
        channels.append(current_extinf)
    
    return channels

def extract_tvg_logo(extinf_line):
    """Extract tvg-logo from EXTINF line"""
    match = re.search(r'tvg-logo="([^"]*)"', extinf_line)
    return match.group(1) if match else None

def extract_tvg_id(extinf_line):
    """Extract tvg-id from EXTINF line"""
    match = re.search(r'tvg-id="([^"]*)"', extinf_line)
    return match.group(1) if match else None

def extract_channel_name(extinf_line):
    """Extract channel name from EXTINF line"""
    # Name is after the last comma
    parts = extinf_line.split(',')
    return parts[-1].strip() if len(parts) > 1 else "Unknown"

def main():
    print("=" * 60)
    print("ANÁLISE DO ARQUIVO NEWSWORLDNOVOS.m3u")
    print("=" * 60)
    
    channels = parse_m3u('/home/runner/work/JCTVV/JCTVV/NEWSWORLDNOVOS.m3u')
    
    print(f"\nTotal de canais encontrados: {len(channels)}")
    
    # 1. Check for orphaned EXTINF (no URL)
    orphaned = [ch for ch in channels if not ch['has_url']]
    print(f"\n{'='*60}")
    print(f"1. CANAIS ÓRFÃOS (sem link): {len(orphaned)}")
    print("="*60)
    for ch in orphaned:
        name = extract_channel_name(ch['content'])
        print(f"  Linha {ch['line_num']}: {name}")
    
    # 2. Check for missing tvg-logo
    missing_logo = []
    for ch in channels:
        if ch['has_url']:
            logo = extract_tvg_logo(ch['content'])
            if not logo:
                missing_logo.append(ch)
    
    print(f"\n{'='*60}")
    print(f"2. CANAIS SEM TVG-LOGO: {len(missing_logo)}")
    print("="*60)
    for ch in missing_logo:
        name = extract_channel_name(ch['content'])
        print(f"  Linha {ch['line_num']}: {name}")
    
    # 3. Check for missing tvg-id
    missing_tvgid = []
    for ch in channels:
        if ch['has_url']:
            tvg_id = extract_tvg_id(ch['content'])
            if not tvg_id:
                missing_tvgid.append(ch)
    
    print(f"\n{'='*60}")
    print(f"3. CANAIS SEM TVG-ID: {len(missing_tvgid)}")
    print("="*60)
    for ch in missing_tvgid:
        name = extract_channel_name(ch['content'])
        print(f"  Linha {ch['line_num']}: {name}")
    
    # 4. Check for .svg logos
    svg_logos = []
    for ch in channels:
        logo = extract_tvg_logo(ch['content'])
        if logo and '.svg' in logo.lower():
            svg_logos.append(ch)
    
    print(f"\n{'='*60}")
    print(f"4. LOGOS COM EXTENSÃO .svg: {len(svg_logos)}")
    print("="*60)
    for ch in svg_logos:
        name = extract_channel_name(ch['content'])
        logo = extract_tvg_logo(ch['content'])
        print(f"  Linha {ch['line_num']}: {name} -> {logo}")
    
    # 5. Test stream URLs
    print(f"\n{'='*60}")
    print("5. TESTANDO LINKS DE STREAM...")
    print("="*60)
    
    online_channels = []
    offline_channels = []
    error_channels = []
    
    for ch in channels:
        if ch['has_url']:
            url = ch['url']
            name = extract_channel_name(ch['content'])
            line_num = ch['line_num']
            
            print(f"  Testando linha {line_num}: {name}...", end=" ", flush=True)
            
            is_online, status = test_url(url, timeout=8)
            
            if is_online:
                print(f"✓ ONLINE ({status})")
                online_channels.append(ch)
            else:
                print(f"✗ OFFLINE ({status})")
                ch['error'] = status
                offline_channels.append(ch)
    
    print(f"\n{'='*60}")
    print(f"RESUMO DOS TESTES:")
    print(f"  Online: {len(online_channels)}")
    print(f"  Offline: {len(offline_channels)}")
    print("="*60)
    
    if offline_channels:
        print("\nCANAIS OFFLINE:")
        for ch in offline_channels:
            name = extract_channel_name(ch['content'])
            print(f"  Linha {ch['line_num']}: {name} ({ch['error']})")
    
    # 6. Check EPG sources
    print(f"\n{'='*60}")
    print("6. VERIFICANDO FONTES EPG...")
    print("="*60)
    
    with open('/home/runner/work/JCTVV/JCTVV/NEWSWORLDNOVOS.m3u', 'r', encoding='utf-8') as f:
        first_line = f.readline().strip()
    
    epg_match = re.search(r'x-tvg-url="([^"]*)"', first_line)
    if epg_match:
        epg_urls = epg_match.group(1).split(',')
        print(f"EPGs encontrados: {len(epg_urls)}")
        for epg_url in epg_urls:
            epg_url = epg_url.strip()
            print(f"\n  Testando: {epg_url}")
            
            if not epg_url.startswith('https'):
                print(f"    ⚠ AVISO: Não começa com https!")
            
            is_online, status = test_url(epg_url, timeout=15)
            if is_online:
                print(f"    ✓ ONLINE ({status})")
            else:
                print(f"    ✗ OFFLINE ({status})")
    
    # Save results to JSON
    results = {
        'total_channels': len(channels),
        'orphaned_count': len(orphaned),
        'missing_logo_count': len(missing_logo),
        'missing_tvgid_count': len(missing_tvgid),
        'svg_logo_count': len(svg_logos),
        'online_count': len(online_channels),
        'offline_count': len(offline_channels),
        'orphaned': [{'line': ch['line_num'], 'name': extract_channel_name(ch['content'])} for ch in orphaned],
        'missing_logo': [{'line': ch['line_num'], 'name': extract_channel_name(ch['content'])} for ch in missing_logo],
        'missing_tvgid': [{'line': ch['line_num'], 'name': extract_channel_name(ch['content'])} for ch in missing_tvgid],
        'offline': [{'line': ch['line_num'], 'name': extract_channel_name(ch['content']), 'error': ch.get('error', '')} for ch in offline_channels],
        'online': [{'line': ch['line_num'], 'name': extract_channel_name(ch['content']), 'url': ch['url']} for ch in online_channels]
    }
    
    with open('/home/runner/work/JCTVV/JCTVV/analysis_results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\nResultados salvos em analysis_results.json")

if __name__ == '__main__':
    main()