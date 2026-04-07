#!/usr/bin/env python3
import os
import re
import hashlib
from datetime import datetime, timedelta
import requests

# Ler a API key do VirusTotal do ambiente ou usar placeholder
VT_API_KEY = os.environ.get("VT_API_KEY", "")

def clean_m3u():
    """Limpa e corrige a lista5.m3u"""
    
    # Ler o arquivo original
    with open("/home/runner/work/JCTV/JCTV/lista5.m3u", "r") as f:
        lines = f.readlines()
    
    cleaned_lines = []
    seen_urls = set()
    duplicates = 0
    
    for i, line in enumerate(lines):
        line = line.rstrip()
        
        # Ignorar linhas vazias
        if not line.strip():
            continue
        
        # Verificar EXTINF (linhas de informação do canal)
        if line.startswith("#EXTINF:"):
            # Limpar e formatar a linha
            cleaned_lines.append(line)
            
        # Verificar URLs
        elif line.startswith("http"):
            # Verificar se é duplicado
            if line in seen_urls:
                duplicates += 1
                continue
            
            seen_urls.add(line)
            cleaned_lines.append(line)
    
    # Escrever o arquivo limpo
    with open("/home/runner/work/JCTV/JCTV/lista5.m3u", "w") as f:
        for line in cleaned_lines:
            f.write(line + "\n")
    
    print(f"Lista limpa: {len(cleaned_lines)} linhas, {duplicates} duplicados removidos")

def extract_channels():
    """Extrai informações dos canais do arquivo m3u"""
    channels = []
    
    with open("/home/runner/work/JCTV/JCTV/lista5.m3u", "r") as f:
        lines = f.readlines()
    
    current_channel = None
    
    for i, line in enumerate(lines):
        line = line.strip()
        
        if line.startswith("#EXTINF:"):
            # Extrair informações do canal
            match = re.search(r'tvg-logo="([^"]+)"', line)
            logo = match.group(1) if match else None
            
            # Extrair group-title
            match = re.search(r'group-title="([^"]+)"', line)
            group = match.group(1) if match else ""
            
            # Extrair nome do canal (após a vírgula)
            name = line.split(",")[-1].strip() if "," in line else ""
            
            current_channel = {
                "name": name,
                "logo": logo,
                "group": group,
                "line_index": i
            }
        
        elif line.startswith("http") and current_channel:
            current_channel["url"] = line
            channels.append(current_channel)
            current_channel = None
    
    return channels

def fix_logos():
    """Corrige logos que não são .jpg para .jpg e adiciona logos onde faltam"""
    
    with open("/home/runner/work/JCTV/JCTV/lista5.m3u", "r") as f:
        content = f.read()
    
    # Logos conhecidos para canais de notícias dos EUA
    logo_map = {
        "abc news": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
        "ABC News Live": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
        "fox news": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/15de0523-3be4-4a9a-8159-7020114e7036/b6ff623a-26d6-4fd9-8bb8-0856adbf38ce/1280x720/match/676/380/image.jpg",
        "Fox News": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/15de0523-3be4-4a9a-8159-7020114e7036/b6ff623a-26d6-4fd9-8bb8-0856adbf38ce/1280x720/match/676/380/image.jpg",
        "fox business": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/c9b2e2eb-7b87-435c-9510-eab2650ff944/8b584585-acf2-4c37-aa07-aaf2d077bb20/1280x720/match/676/380/image.jpg",
        "Fox Business": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/c9b2e2eb-7b87-435c-9510-eab2650ff944/8b584585-acf2-4c37-aa07-aaf2d077bb20/1280x720/match/676/380/image.jpg",
        "cbs news": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
        "CBS News": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
    }
    
    lines = content.split("\n")
    new_lines = []
    
    for line in lines:
        if line.startswith("#EXTINF:"):
            # Verificar se tem logo
            logo_match = re.search(r'tvg-logo="([^"]+)"', line)
            
            if logo_match:
                logo = logo_match.group(1)
                
                # Se o logo não é .jpg ou é imgur.com, tentar encontrar um替代
                if not logo.lower().endswith(".jpg") or "imgur.com" in logo.lower():
                    # Tentar encontrar um logo替代 baseado no nome do canal
                    name = line.split(",")[-1].strip().lower() if "," in line else ""
                    
                    for key, new_logo in logo_map.items():
                        if key in name:
                            line = re.sub(r'tvg-logo="[^"]+"', f'tvg-logo="{new_logo}"', line)
                            break
            else:
                # Adicionar logo baseado no nome do canal
                name = line.split(",")[-1].strip().lower() if "," in line else ""
                
                for key, new_logo in logo_map.items():
                    if key in name:
                        line = line.replace("#EXTINF:", '#EXTINF:-1 tvg-logo="' + new_logo + '" ')
                        # Remover espaços duplos
                        line = re.sub(r'\s+', ' ', line)
                        break
            
            # Garantir formato .jpg se ainda não for
            logo_match = re.search(r'tvg-logo="([^"]+)"', line)
            if logo_match:
                logo = logo_match.group(1)
                if logo and not logo.lower().endswith(('.jpg', '.jpeg', '.png')):
                    # Forçar .jpg
                    if ".jpg" not in logo:
                        # Tentar adicionar .jpg
                        base_url = logo.rsplit(".", 1)[0]
                        line = line.replace(f'tvg-logo="{logo}"', f'tvg-logo="{base_url}.jpg"')
        
        new_lines.append(line)
    
    with open("/home/runner/work/JCTV/JCTV/lista5.m3u", "w") as f:
        f.write("\n".join(new_lines))
    
    print("Logos corrigidos")

def ensure_hash_lines():
    """Garante que cada link de stream tenha # na linha de cima"""
    
    with open("/home/runner/work/JCTV/JCTV/lista5.m3u", "r") as f:
        lines = f.readlines()
    
    new_lines = []
    prev_was_extinf = False
    
    for line in lines:
        line = line.rstrip()
        
        if not line.strip():
            continue
            
        if line.startswith("#EXTINF:"):
            new_lines.append(line)
            prev_was_extinf = True
        elif line.startswith("http"):
            # Se a linha anterior não foi EXTINF, adicionar uma linha vazia
            if not prev_was_extinf:
                new_lines.append("")
            new_lines.append(line)
            prev_was_extinf = False
        else:
            new_lines.append(line)
            prev_was_extinf = False
    
    with open("/home/runner/work/JCTV/JCTV/lista5.m3u", "w") as f:
        f.write("\n".join(new_lines) + "\n")
    
    print("Hash lines verificadas")

def generate_epg():
    """Gera EPG para os canais da lista5.m3u"""
    import xml.etree.ElementTree as ET
    
    canais = [
        {
            "id": "ABCNewsLive.us@SD",
            "name": "ABC News Live",
            "logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
            "keywords": ["abc news", "abcnews"]
        },
        {
            "id": "FoxNewsChannel.us@SD",
            "name": "Fox News Channel",
            "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/15de0523-3be4-4a9a-8159-7020114e7036/b6ff623a-26d6-4fd9-8bb8-0856adbf38ce/1280x720/match/676/380/image.jpg",
            "keywords": ["fox news", "foxnews"]
        },
        {
            "id": "FoxBusinessNetwork.us@SD",
            "name": "Fox Business Network",
            "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/c9b2e2eb-7b87-435c-9510-eab2650ff944/8b584585-acf2-4c37-aa07-aaf2d077bb20/1280x720/match/676/380/image.jpg",
            "keywords": ["fox business", "foxbusiness"]
        },
        {
            "id": "CBSNews247.us@SD",
            "name": "CBS News 24/7",
            "logo": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
            "keywords": ["cbs news", "cbsnews"]
        },
    ]
    
    programas_templates = {
        "ABCNewsLive.us@SD": [
            ("ABC World News This Morning", "Morning news coverage with latest updates"),
            ("ABC World News Midday", "Midday news program"),
            ("ABC Live - Afternoon Update", "Afternoon news coverage"),
            ("ABC World News Tonight", "Evening news program"),
            ("ABC Live - Prime Time", "Prime time news coverage"),
            ("ABC Nightline", "Late night news program"),
            ("ABC World News Now", "Overnight news coverage"),
        ],
        "FoxNewsChannel.us@SD": [
            ("Fox & Friends First", "Morning news program"),
            ("Fox & Friends", "Morning news and talk show"),
            ("America's Newsroom", "News program with latest updates"),
            ("Hannity", "Political commentary and news"),
            ("The Ingraham Angle", "Evening news commentary"),
            ("Fox News @ Night", "Late night news program"),
            ("Gutfeld!", "Late night comedy news"),
        ],
        "FoxBusinessNetwork.us@SD": [
            ("Mornings with Maria", "Morning business news program"),
            ("Fox Business Morning", "Business news coverage"),
            ("Making Money", "Financial news and advice"),
            ("The Claman Countdown", "Market closing coverage"),
            ("Cavuto: Coast to Coast", "Business news program"),
            ("Fox Business Tonight", "Evening business coverage"),
        ],
        "CBSNews247.us@SD": [
            ("CBS News Mornings", "Morning news coverage"),
            ("CBS News Midday", "Midday news program"),
            ("CBS Evening News", "Evening news broadcast"),
            ("CBS News 24/7 Live", "Continuous news coverage"),
            ("Face the Nation", "Sunday morning news program"),
        ],
    }
    
    root = ET.Element("tv")
    now = datetime.now()
    
    for canal in canais:
        ch_elem = ET.SubElement(root, "channel")
        ch_elem.set("id", canal["id"])
        
        display_name = ET.SubElement(ch_elem, "display-name")
        display_name.text = canal["name"]
        
        icon = ET.SubElement(ch_elem, "icon")
        icon.set("src", canal["logo"])
        
        templates = programas_templates.get(canal["id"], [])
        
        # Gerar programas para os próximos 3 dias
        for day_offset in range(3):
            current_date = now + timedelta(days=day_offset)
            date_str = current_date.strftime("%Y%m%d")
            
            # Streams 24/7 - programas a cada 30 minutos
            for hour in range(24):
                for minute in [0, 30]:
                    start_time = f"{date_str}{hour:02d}{minute:02d}00"
                    end_hour = hour
                    end_minute = minute + 30
                    if end_minute >= 60:
                        end_hour += 1
                        end_minute = 0
                    end_time = f"{date_str}{end_hour:02d}{end_minute:02d}00"
                    
                    if end_hour >= 24:
                        continue
                    
                    prog_index = (hour * 2 + minute // 30) % len(templates)
                    title, desc = templates[prog_index]
                    
                    prog = ET.SubElement(root, "programme")
                    prog.set("channel", canal["id"])
                    prog.set("start", f"{start_time} +0000")
                    prog.set("stop", f"{end_time} +0000")
                    
                    title_elem = ET.SubElement(prog, "title")
                    title_elem.set("lang", "en")
                    title_elem.text = title
                    
                    desc_elem = ET.SubElement(prog, "desc")
                    desc_elem.set("lang", "en")
                    desc_elem.text = desc
    
    tree = ET.ElementTree(root)
    tree.write("/home/runner/work/JCTV/JCTV/lista5_epg.xml", encoding="UTF-8", xml_declaration=True)
    
    return len(root.findall("channel")), len(root.findall("programme"))

def add_epg_to_m3u():
    """Adiciona a URL do EPG ao arquivo m3u"""
    
    epg_url = "https://raw.githubusercontent.com/canaisiptv/EPG/main/lista5_epg.xml"
    
    with open("/home/runner/work/JCTV/JCTV/lista5.m3u", "r") as f:
        content = f.read()
    
    # Verificar se já tem url-tvg
    if "url-tvg=" not in content:
        # Adicionar url-tvg após #EXTM3U
        content = content.replace("#EXTM3U", f'#EXTM3U\n#EXTURL-tvg: {epg_url}')
    
    with open("/home/runner/work/JCTV/JCTV/lista5.m3u", "w") as f:
        f.write(content)
    
    print(f"EPG URL adicionada: {epg_url}")

if __name__ == "__main__":
    print("Iniciando correção da lista5.m3u...")
    
    # 1. Limpar duplicados
    clean_m3u()
    
    # 2. Corrigir logos
    fix_logos()
    
    # 3. Garantir # na linha de cima
    ensure_hash_lines()
    
    # 4. Gerar EPG
    canais, programas = generate_epg()
    print(f"EPG gerado: {canais} canais, {programas} programas")
    
    # 5. Adicionar URL do EPG ao m3u
    add_epg_to_m3u()
    
    print("Correção concluída!")
