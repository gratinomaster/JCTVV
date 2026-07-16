import subprocess
import re
import sys

def test_url(url, timeout=10):
    """Testa se a URL retorna dados válidos (HTTP 200)."""
    try:
        result = subprocess.run(
            ['curl', '-o', '/dev/null', '-s', '-w', '%{http_code}', 
             '--connect-timeout', str(timeout), '--max-time', str(timeout),
             '-L', url],
            capture_output=True, text=True, timeout=timeout + 5
        )
        http_code = result.stdout.strip()
        return http_code.startswith('2') or http_code.startswith('3')
    except:
        return False

def parse_m3u(filename):
    """Analisa o arquivo M3U e retorna uma lista de entradas."""
    with open(filename, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    entries = []
    current_entry = None
    
    for line in lines:
        line = line.strip()
        if line.startswith('#EXTM3U'):
            continue
        elif line.startswith('#EXTINF:'):
            current_entry = {'metadata': line, 'url': None}
        elif line and current_entry and current_entry['url'] is None:
            current_entry['url'] = line
            entries.append(current_entry)
            current_entry = None
    
    return entries

def main():
    filename = 'lista5.m3u'
    print(f"Analisando {filename}...")
    
    entries = parse_m3u(filename)
    print(f"Encontradas {len(entries)} entradas")
    
    # Remove duplicatas por URL
    unique_entries = {}
    for entry in entries:
        url = entry['url']
        if url not in unique_entries:
            unique_entries[url] = entry
    
    print(f"Encontradas {len(unique_entries)} URLs únicas")
    
    working_entries = []
    non_working = []
    
    for url, entry in unique_entries.items():
        print(f"Testando: {entry['metadata'].split(',')[-1][:50]}...")
        if test_url(url):
            working_entries.append(entry)
            print("  ✓ Funcionando")
        else:
            non_working.append(entry)
            print("  ✗ Não funcionando")
    
    # Remove duplicatas mantendo apenas a primeira ocorrência de cada canal
    seen_channels = set()
    final_entries = []
    
    for entry in working_entries:
        channel_name = entry['metadata'].split(',')[-1]
        if channel_name not in seen_channels:
            seen_channels.add(channel_name)
            final_entries.append(entry)
    
    # Escreve o arquivo limpo
    with open(filename, 'w', encoding='utf-8') as f:
        f.write('#EXTM3U\n')
        for entry in final_entries:
            f.write(f"{entry['metadata']}\n{entry['url']}\n")
    
    print(f"\nResultado:")
    print(f"  Canais funcionando: {len(final_entries)}")
    print(f"  Canais removidos: {len(non_working)}")
    print(f"  Lista atualizada em {filename}")

if __name__ == '__main__':
    main()
