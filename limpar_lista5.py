#!/usr/bin/env python3
import requests
import re
from datetime import datetime

def parse_m3u(path):
    channels = []
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXTINF:'):
            url = lines[i+1].strip() if i+1 < len(lines) else ""
            name = re.search(r',(.+)$', line)
            name = name.group(1).strip() if name else ""
            tvg_id = re.search(r'tvg-id="([^"]*)"', line)
            tvg_id = tvg_id.group(1) if tvg_id else ""
            tvg_logo = re.search(r'tvg-logo="([^"]*)"', line)
            tvg_logo = tvg_logo.group(1) if tvg_logo else ""
            group = re.search(r'group-title="([^"]*)"', line)
            group = group.group(1) if group else ""
            channels.append({"url": url, "name": name, "tvg_id": tvg_id, "tvg_logo": tvg_logo, "group": group})
            i += 2
        else:
            i += 1
    return channels

def is_valid_stream(url):
    if not url:
        return False, "sem_url"
    if "youtube.com" in url.lower():
        return False, "youtube"
    if "watch?v=" in url.lower():
        return False, "youtube"
    if ".onion" in url.lower():
        return False, "onion"
    if url.startswith("rtmp://") and "live" not in url.lower():
        return False, "rtmp"
    return True, "ok"

def main():
    print("=" * 60)
    print("LIMPEZA FINAL lista5.m3u")
    print("=" * 60)
    
    channels = parse_m3u("lista5.m3u")
    print(f"Canais encontrados: {len(channels)}")
    
    valid_channels = []
    removed = {"youtube": [], "onion": [], "outros": []}
    
    for ch in channels:
        url = ch["url"]
        name = ch["name"]
        
        valid, reason = is_valid_stream(url)
        if valid:
            valid_channels.append(ch)
        else:
            if reason == "youtube":
                removed["youtube"].append(name)
            elif reason == "onion":
                removed["onion"].append(name)
            else:
                removed["outros"].append(name)
    
    # Remover duplicatas
    unique = {}
    for ch in valid_channels:
        key = ch["url"]
        if key not in unique:
            unique[key] = ch
    
    print(f"\nRemovidos:")
    print(f"  YouTube: {len(removed['youtube'])}")
    print(f"  Onion: {len(removed['onion'])}")
    print(f"  Outros: {len(removed['outros'])}")
    print(f"  Total removidos: {len(channels) - len(unique)}")
    print(f"\nCanais finais (sem duplicatas): {len(unique)}")
    
    # Contadores
    with_tvg_id = sum(1 for c in unique.values() if c["tvg_id"])
    with_logo = sum(1 for c in unique.values() if c["tvg_logo"])
    
    print(f"Com tvg-id: {with_tvg_id}")
    print(f"Com logo: {with_logo}")
    
    # Salvar arquivo
    epg_url = "https://epg.pw/xmltv/epg.xml.gz"
    with open("lista5.m3u", 'w', encoding='utf-8') as f:
        f.write(f'#EXTM3U x-tvg-url="{epg_url}"\n')
        for ch in unique.values():
            attrs = []
            if ch["tvg_id"]: attrs.append(f'tvg-id="{ch["tvg_id"]}"')
            if ch["tvg_logo"]: attrs.append(f'tvg-logo="{ch["tvg_logo"]}"')
            if ch["group"]: attrs.append(f'group-title="{ch["group"]}"')
            f.write(f'#EXTINF:-1 {" ".join(attrs)},{ch["name"]}\n')
            f.write(f'{ch["url"]}\n')
    
    print(f"\nOK! lista5.m3u atualizada!")
    
    # Relatorio
    with open("lista5_relatorio.txt", 'w', encoding='utf-8') as f:
        f.write("=" * 60 + "\n")
        f.write("RELATORIO FINAL lista5.m3u\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        f.write(f"Canais encontrados: {len(channels)}\n")
        f.write(f"Canais finais: {len(unique)}\n")
        f.write(f"Canais removidos: {len(channels) - len(unique)}\n\n")
        f.write(f"Canais com tvg-id: {with_tvg_id}\n")
        f.write(f"Canais com logo: {with_logo}\n\n")
        f.write(f"EPG: {epg_url}\n\n")
        f.write("Removidos por tipo:\n")
        f.write(f"  YouTube: {len(removed['youtube'])}\n")
        f.write(f"  Onion: {len(removed['onion'])}\n")
        f.write(f"  Outros: {len(removed['outros'])}\n\n")
        if removed["youtube"]:
            f.write("Canais YouTube removidos:\n")
            for name in removed["youtube"]:
                f.write(f"  - {name}\n")
    
    print("\nRelatorio salvo: lista5_relatorio.txt")

if __name__ == "__main__":
    main()
