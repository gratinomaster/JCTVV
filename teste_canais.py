#!/usr/bin/env python3
import subprocess
import sys
import re
import concurrent.futures
import shutil
from datetime import datetime

M3U_FILE = "lista5.m3u"
BACKUP_SUFFIX = f".bak.pre_teste_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
TIMEOUT = 10  # seconds
MAX_WORKERS = 20

def parse_m3u(filepath):
    """Parse M3U file into list of (extinf_line, url_line) tuples."""
    entries = []
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        lines = [l.rstrip('\n') for l in f.readlines()]
    
    if not lines or not lines[0].startswith('#EXTM3U'):
        print("ERRO: Arquivo não é M3U válido")
        sys.exit(1)
    
    i = 1
    while i < len(lines):
        line = lines[i]
        if line.startswith('#EXTINF:'):
            extinf = line
            # Next non-empty line should be URL
            i += 1
            while i < len(lines) and lines[i].strip() == '':
                i += 1
            if i < len(lines) and not lines[i].startswith('#'):
                url = lines[i].strip()
                entries.append((extinf, url))
        i += 1
    
    return entries

def test_url(entry):
    """Test if a URL is reachable. Returns (entry, working, detail)."""
    extinf, url = entry
    # Extract channel name from EXTINF
    m = re.search(r',(.+)$', extinf)
    name = m.group(1).strip() if m else url[:60]
    
    try:
        # Use curl to test the URL with timeout
        result = subprocess.run(
            ['curl', '-s', '-o', '/dev/null', '-w', '%{http_code}',
             '-L', '--max-time', str(TIMEOUT), '--connect-timeout', '8',
             '-H', 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
             url],
            capture_output=True, text=True, timeout=TIMEOUT + 5
        )
        http_code = result.stdout.strip()
        if http_code in ('200', '201', '202', '203', '204', '206', '301', '302', '303', '307', '308'):
            return (entry, True, f"HTTP {http_code}")
        else:
            return (entry, False, f"HTTP {http_code}")
    except subprocess.TimeoutExpired:
        return (entry, False, "TIMEOUT")
    except Exception as e:
        return (entry, False, f"ERROR: {str(e)[:50]}")

def main():
    print(f"=== Teste de Canais - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
    
    # Parse
    entries = parse_m3u(M3U_FILE)
    print(f"Total de entradas encontradas: {len(entries)}\n")
    
    # Backup
    backup_path = M3U_FILE + BACKUP_SUFFIX
    shutil.copy2(M3U_FILE, backup_path)
    print(f"Backup criado: {backup_path}\n")
    
    # Test all URLs concurrently
    working = []
    failed = []
    
    print(f"Testando {len(entries)} URLs com {MAX_WORKERS} threads paralelas...\n")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(test_url, entry): entry for entry in entries}
        for i, future in enumerate(concurrent.futures.as_completed(futures), 1):
            entry, ok, detail = future.result()
            extinf, url = entry
            m = re.search(r',(.+)$', extinf)
            name = m.group(1).strip() if m else url[:60]
            status = "✓ OK" if ok else "✗ FALHOU"
            print(f"[{i:3d}/{len(entries)}] {status} ({detail}) - {name}")
            if ok:
                working.append(entry)
            else:
                failed.append((entry, detail))
    
    print(f"\n{'='*60}")
    print(f"RESULTADO: {len(working)} funcionando / {len(failed)} falharam / {len(entries)} total")
    print(f"{'='*60}\n")
    
    if failed:
        print("Canais que FALHARAM:")
        for (extinf, url), detail in failed:
            m = re.search(r',(.+)$', extinf)
            name = m.group(1).strip() if m else url[:60]
            print(f"  ✗ [{detail}] {name}")
        print()
    
    # Rewrite M3U with only working entries
    with open(M3U_FILE, 'w', encoding='utf-8') as f:
        f.write('#EXTM3U\n')
        for extinf, url in working:
            f.write(f'{extinf}\n{url}\n')
    
    print(f"lista5.m3u sobrescrito com {len(working)} canais funcionais.")
    print(f"Backup original: {backup_path}")

if __name__ == '__main__':
    main()
