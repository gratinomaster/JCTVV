#!/usr/bin/env python3
import requests
import re
import hashlib
import json
import concurrent.futures
from datetime import datetime, timedelta
from urllib.parse import urlparse
import sys

class M3UProcessor:
    def __init__(self, filename):
        self.filename = filename
        self.channels = []
        self.parse_m3u()
    
    def parse_m3u(self):
        with open(self.filename, 'r', encoding='utf-8') as f:
            content = f.read()
        
        lines = content.strip().split('\n')
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith('#EXTINF:'):
                info = self.parse_extinf(line)
                if i + 1 < len(lines) and not lines[i + 1].startswith('#'):
                    url = lines[i + 1].strip()
                    self.channels.append({'info': info, 'url': url})
                    i += 2
                else:
                    i += 1
            else:
                i += 1
    
    def parse_extinf(self, line):
        result = {
            'tvg_id': None,
            'tvg_name': None,
            'tvg_logo': None,
            'group_title': None,
            'name': None
        }
        
        match = re.search(r'tvg-id="([^"]*)"', line)
        if match:
            result['tvg_id'] = match.group(1)
        
        match = re.search(r'tvg-name="([^"]*)"', line)
        if match:
            result['tvg_name'] = match.group(1)
        
        match = re.search(r'tvg-logo="([^"]*)"', line)
        if match:
            result['tvg_logo'] = match.group(1)
        
        match = re.search(r'group-title="([^"]*)"', line)
        if match:
            result['group_title'] = match.group(1)
        
        match = re.search(r',(.+)$', line)
        if match:
            result['name'] = match.group(1)
        
        return result

    def get_unique_channels(self):
        seen = set()
        unique = []
        for ch in self.channels:
            key = ch['url']
            if key not in seen:
                seen.add(key)
                unique.append(ch)
        return unique

    def test_stream(self, channel):
        url = channel['url']
        try:
            response = requests.head(url, timeout=10, allow_redirects=True)
            if response.status_code == 200:
                return {'url': url, 'status': 'ok', 'code': 200}
            else:
                response = requests.get(url, timeout=10, stream=True, headers={'User-Agent': 'Mozilla/5.0'})
                if response.status_code == 200:
                    content = next(response.iter_content(1024), None)
                    if content and b'#EXTM3U' in content[:100]:
                        return {'url': url, 'status': 'ok', 'code': 200}
                    return {'url': url, 'status': 'error', 'code': response.status_code, 'reason': 'Not a valid m3u8'}
                return {'url': url, 'status': 'error', 'code': response.status_code}
        except Exception as e:
            return {'url': url, 'status': 'error', 'code': 0, 'reason': str(e)}

def check_virustotal(url, api_key=None):
    if not api_key:
        return None
    
    try:
        url_hash = hashlib.sha256(url.encode()).hexdigest()
        headers = {'x-apikey': api_key}
        response = requests.get(
            f'https://www.virustotal.com/api/v3/urls/{url_hash}',
            headers=headers,
            timeout=30
        )
        if response.status_code == 200:
            data = response.json()
            stats = data.get('data', {}).get('attributes', {}).get('last_analysis_stats', {})
            malicious = stats.get('malicious', 0)
            suspicious = stats.get('suspicious', 0)
            total = sum(stats.values())
            return {
                'malicious': malicious,
                'suspicious': suspicious,
                'total': total,
                'is_safe': malicious == 0 and suspicious == 0
            }
    except Exception as e:
        print(f"VirusTotal error: {e}")
    return None

def main():
    processor = M3UProcessor('lista5.m3u')
    unique_channels = processor.get_unique_channels()
    
    print(f"Total de canais: {len(processor.channels)}")
    print(f"Canais únicos: {len(unique_channels)}")
    
    print("\n=== Testando streams ===")
    working = []
    broken = []
    
    for ch in unique_channels:
        print(f"\nTestando: {ch['info']['name']}")
        print(f"URL: {ch['url'][:80]}...")
        result = processor.test_stream(ch)
        
        if result['status'] == 'ok':
            print(f"✅ STATUS: OK ({result['code']})")
            working.append((ch, result))
        else:
            reason = result.get('reason', '')
            code = result.get('code', 'N/A')
            print(f"❌ STATUS: ERRO ({code}) - {reason}")
            broken.append((ch, result))
    
    print(f"\n\n=== RESUMO ===")
    print(f"Streams funcionando: {len(working)}")
    print(f"Streams quebrados: {len(broken)}")
    
    if broken:
        print("\n=== STREAMS QUE SERÃO REMOVIDOS ===")
        for ch, result in broken:
            print(f"- {ch['info']['name']}")
            print(f"  URL: {ch['url']}")
            reason = result.get('reason') or f"HTTP {result.get('code', 'N/A')}"
            print(f"  Motivo: {reason}")

    return working, broken

if __name__ == '__main__':
    main()
