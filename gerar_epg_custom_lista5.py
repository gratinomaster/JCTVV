#!/usr/bin/env python3
import requests
import gzip
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import List, Dict
import re
import html
import base64

CANAIS_EPG = {
    "ABCWBMA.us": {
        "nome": "ABC News Live",
        "logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
        "programas": [
            ("Morning News", "Live morning news broadcast from ABC News Live."),
            ("Afternoon News", "Live afternoon news broadcast from ABC News Live."),
            ("Evening News", "Live evening news broadcast from ABC News Live."),
            ("Overnight News", "Live overnight news broadcast from ABC News Live."),
        ]
    },
    "FoxNewsChannel.us": {
        "nome": "Fox News",
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/15de0523-3be4-4a9a-8159-7020114e7036/b6ff623a-26d6-4fd9-8bb8-0856adbf38ce/1280x720/match/676/380/image.jpg",
        "programas": [
            ("Fox and Friends", "Morning news and talk show on Fox News Channel."),
            ("Hannity", "Political talk show hosted by Sean Hannity."),
            ("Tucker Carlson Tonight", "Commentary and news analysis with Tucker Carlson."),
            ("The Ingraham Angle", "News and political commentary with Laura Ingraham."),
            ("The Five", "Panel discussion on the day news stories."),
        ]
    },
    "FoxBusiness.us": {
        "nome": "Fox Business",
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/c9b2e2eb-7b87-435c-9510-eab2650ff944/8b584585-acf2-4c37-aa07-aaf2d077bb20/1280x720/match/676/380/image.jpg",
        "programas": [
            ("Mornings with Maria", "Morning business news show hosted by Maria Bartiromo."),
            ("Making Money", "Business news and market analysis show."),
            ("The Claman Countdown", "Closing bell coverage and market recap."),
        ]
    },
    "CBSNews247.us": {
        "nome": "CBS News 24/7",
        "logo": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
        "programas": [
            ("CBS News Live", "24/7 live news coverage from CBS News."),
            ("CBS Mornings", "Morning news program with latest headlines."),
            ("Evening News", "Daily evening news broadcast from CBS."),
        ]
    }
}

def format_timestamp(data: datetime, hora: int) -> str:
    """Formata timestamp para o formato EPG: YYYYMMDDHHMMSS +0000"""
    if hora >= 24:
        data = data + timedelta(days=1)
        hora = hora - 24
    return data.strftime("%Y%m%d") + f"{hora:02d}0000 +0000"

def gerar_epg_customizado() -> str:
    """Gera um EPG XML customizado para os canais da lista5"""
    
    now = datetime.now()
    data = now.strftime("%Y%m%d%H%M%S %z")
    
    lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    lines.append(f'<tv date="{data}">')
    
    for canal_id, info in CANAIS_EPG.items():
        lines.append(f'  <channel id="{canal_id}">')
        lines.append(f'    <display-name lang="en">{html.escape(info["nome"])}</display-name>')
        lines.append(f'    <icon src="{html.escape(info["logo"])}"/>')
        lines.append('  </channel>')
    
    for dia in range(7):
        data_atual = now + timedelta(days=dia)
        
        for canal_id, info in CANAIS_EPG.items():
            for i, (titulo, desc) in enumerate(info["programas"]):
                hora_inicio = 6 + (i * 6)
                hora_fim = hora_inicio + 6
                
                start = format_timestamp(data_atual, hora_inicio)
                stop = format_timestamp(data_atual, hora_fim)
                
                lines.append(f'  <programme channel="{canal_id}" start="{start}" stop="{stop}">')
                lines.append(f'    <title lang="en">{html.escape(titulo)}</title>')
                lines.append(f'    <desc lang="en">{html.escape(desc)}</desc>')
                lines.append('  </programme>')
    
    lines.append('</tv>')
    
    return '\n'.join(lines)

def testar_epg(epg_content: str):
    """Testa o EPG gerado"""
    print("\n" + "="*60)
    print("TESTE DO EPG CUSTOMIZADO")
    print("="*60)
    
    try:
        root = ET.fromstring(epg_content)
        
        canais = root.findall("channel")
        programas = root.findall("programme")
        
        print(f"Canais: {len(canais)}")
        print(f"Programas: {len(programas)}")
        
        hoje = datetime.now().strftime("%Y%m%d")
        amanha = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
        depois_amanha = (datetime.now() + timedelta(days=2)).strftime("%Y%m%d")
        
        count_hoje = count_amanha = count_depois = 0
        for p in programas:
            start = p.get("start", "")[:8]
            if start == hoje:
                count_hoje += 1
            elif start == amanha:
                count_amanha += 1
            elif start == depois_amanha:
                count_depois += 1
        
        print(f"\nProgramação:")
        print(f"  Hoje: {count_hoje} programas")
        print(f"  Amanhã: {count_amanha} programas")
        print(f"  Depois de amanhã: {count_depois} programas")
        
        if count_hoje > 0 and count_amanha > 0:
            print("\n✓ EPG FUNCIONANDO!")
            return True
        else:
            print("\n✗ EPG com problemas")
            return False
            
    except Exception as e:
        print(f"✗ ERRO: {e}")
        return False

if __name__ == "__main__":
    epg = gerar_epg_customizado()
    print("EPG Gerado com sucesso!")
    print(f"Tamanho: {len(epg)} caracteres")
    
    testar_epg(epg)
    
    with open("lista5_epg_custom.xml", "w", encoding="utf-8") as f:
        f.write(epg)
    print("\nEPG salvo em lista5_epg_custom.xml")
    
    print("\nEPG URL: https://raw.githubusercontent.com/SEU_USUARIO/JCTV/main/lista5_epg_custom.xml")
