#!/usr/bin/env python3
import subprocess
import re
import sys
import shutil
from datetime import datetime

M3U_FILE = "/home/runner/work/JCTVV/JCTVV/lista5.m3u"
TIMEOUT = 10

def parse_m3u(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = [l.rstrip('\n') for l in f.readlines()]
    entries = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith('#EXTINF:'):
            extinf = line
            name_match = re.search(r',(.+)$', extinf)
            name = name_match.group(1).strip() if name_match else 'Unknown'
            i += 1
            if i < len(lines) and not lines[i].startswith('#'):
                url = lines[i]
                entries.append({'extinf': extinf, 'url': url, 'name': name})
        i += 1
    return entries

def test_url(url):
    try:
        result = subprocess.run(
            ['curl', '-s', '-o', '/dev/null', '-w', '%{http_code}',
             '-L', '--max-time', str(TIMEOUT), '--max-filesize', '51200', url],
            capture_output=True, text=True, timeout=TIMEOUT + 5
        )
        code = result.stdout.strip()
        return code in ('200', '206', '302', '301', '303', '307')
    except Exception:
        return False

def test_url_content(url):
    try:
        result = subprocess.run(
            ['curl', '-s', '-L', '--max-time', str(TIMEOUT), '--max-filesize', '102400', url],
            capture_output=True, text=True, timeout=TIMEOUT + 5
        )
        content = result.stdout[:2000]
        if '#EXTM3U' in content or '#EXT-X-' in content or '#EXTINF' in content:
            return True
        if result.returncode == 0 and len(content) > 100:
            return True
        return False
    except Exception:
        return False

entries = parse_m3u(M3U_FILE)
print(f"Total de entradas: {len(entries)}")

unique_urls = {}
for e in entries:
    if e['url'] not in unique_urls:
        unique_urls[e['url']] = e

print(f"URLs unicas: {len(unique_urls)}")
print()

working = []
not_working = []

for url, entry in unique_urls.items():
    sys.stdout.write(f"Testando: {entry['name'][:50]:50s} ... ")
    sys.stdout.flush()
    
    ok = test_url(url)
    if not ok:
        ok = test_url_content(url)
    
    if ok:
        print("OK")
        working.append(entry)
    else:
        print("FALHOU")
        not_working.append(entry)

print(f"\n--- Resultado ---")
print(f"Funcionando: {len(working)}")
print(f"Nao funcionando: {len(not_working)}")

if not_working:
    print("\nCanais removidos:")
    for e in not_working:
        print(f"  - {e['name']}")

header = "#EXTM3U\n"
with open(M3U_FILE, 'w', encoding='utf-8') as f:
    f.write(header)
    for entry in working:
        f.write(entry['extinf'] + '\n')
        f.write(entry['url'] + '\n')

print(f"\nArquivo {M3U_FILE} atualizado com {len(working)} canais.")
