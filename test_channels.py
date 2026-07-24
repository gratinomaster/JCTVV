#!/usr/bin/env python3
import subprocess
import re
import sys

def parse_m3u(filename):
    """Parse M3U file and return list of (extinf_line, url_line) tuples."""
    channels = []
    with open(filename, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXTINF:'):
            extinf = line
            if i + 1 < len(lines):
                url = lines[i + 1].strip()
                if url and not url.startswith('#'):
                    channels.append((extinf, url))
                    i += 2
                    continue
        i += 1
    return channels

def test_url(url, timeout=10):
    """Test if URL is accessible using curl."""
    try:
        result = subprocess.run(
            ['curl', '-s', '-o', '/dev/null', '-w', '%{http_code}', 
             '-m', str(timeout), '--connect-timeout', '5', url],
            capture_output=True, text=True, timeout=timeout + 5
        )
        http_code = result.stdout.strip()
        # Accept 2xx, 3xx as working; 4xx/5xx as not working
        if http_code.startswith(('2', '3')):
            return True
        return False
    except:
        return False

def main():
    filename = 'lista5.m3u'
    print(f"Arquivo: {filename}")
    
    # Parse channels
    channels = parse_m3u(filename)
    print(f"Total de entradas encontradas: {len(channels)}")
    
    # Extract unique URLs
    unique_urls = {}
    for extinf, url in channels:
        if url not in unique_urls:
            unique_urls[url] = (extinf, url)
    
    print(f"URLs únicas: {len(unique_urls)}")
    print("Testando URLs...\n")
    
    working = []
    not_working = []
    
    for i, (url, (extinf, _)) in enumerate(unique_urls.items(), 1):
        # Extract channel name from EXTINF
        name_match = re.search(r',(.+)$', extinf)
        name = name_match.group(1) if name_match else "Unknown"
        
        sys.stdout.write(f"[{i}/{len(unique_urls)}] {name[:50]}... ")
        sys.stdout.flush()
        
        if test_url(url):
            print("✓ OK")
            working.append((extinf, url))
        else:
            print("✗ FALHOU")
            not_working.append((extinf, url))
    
    print(f"\n{'='*50}")
    print(f"Resultados:")
    print(f"  Funcionando: {len(working)}")
    print(f"  Não funcionando: {len(not_working)}")
    
    if not_working:
        print(f"\nCanais removidos:")
        for extinf, url in not_working:
            name_match = re.search(r',(.+)$', extinf)
            name = name_match.group(1) if name_match else "Unknown"
            print(f"  - {name}")
    
    # Write filtered M3U file
    with open(filename, 'w', encoding='utf-8') as f:
        f.write("#EXTM3U\n")
        for extinf, url in working:
            f.write(f"{extinf}\n{url}\n")
    
    print(f"\nArquivo {filename} atualizado com {len(working)} canais.")

if __name__ == "__main__":
    main()