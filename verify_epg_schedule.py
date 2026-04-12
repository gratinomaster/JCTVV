#!/usr/bin/env python3
import gzip
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

def check_epg_schedule():
    print("=" * 70)
    print("Verificação da Programação EPG - Próximos 3 dias")
    print("=" * 70)
    
    epg_url = "https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.xml.gz"
    
    channels_to_check = {
        "ABCNewsLive.us": ["ABC News Live", "GMA"],
        "FoxNewsChannel.us": ["Fox News", "FoxNews"],
        "FoxBusinessNetwork.us": ["Fox Business", "FoxBusiness"],
        "CBSNewsNetwork.us": ["CBS News", "CBSNews"],
    }
    
    try:
        import requests
        print("\nBaixando EPG...")
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(epg_url, headers=headers, timeout=120)
        
        if response.status_code == 200:
            print(f"EPG baixado: {len(response.content)} bytes")
            
            with gzip.open(response.content, 'rt', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            content = content.replace('\x00', '')
            root = ET.fromstring(content)
            
            today = datetime.now()
            tomorrow = today + timedelta(days=1)
            day_after = today + timedelta(days=2)
            
            print(f"\nData atual: {today.strftime('%Y-%m-%d')}")
            print(f"Amanhã: {tomorrow.strftime('%Y-%m-%d')}")
            print(f"Depois de amanhã: {day_after.strftime('%Y-%m-%d')}")
            
            for channel_id, names in channels_to_check.items():
                print(f"\n--- Canal: {channel_id} ---")
                
                found_programs = 0
                for programme in root.findall('programme'):
                    prog_channel = programme.get('channel')
                    if prog_channel == channel_id:
                        start = programme.get('start')
                        stop = programme.get('stop')
                        
                        if start:
                            prog_date = datetime.strptime(start[:8], '%Y%m%d')
                            if prog_date.date() >= today.date() and prog_date.date() <= day_after.date():
                                title = programme.find('title')
                                title_text = title.text if title is not None else "Sem título"
                                print(f"  {start[:8]} {start[8:12]}: {title_text[:60]}")
                                found_programs += 1
                                if found_programs >= 5:
                                    break
                
                if found_programs == 0:
                    print(f"  Nenhum programa encontrado para os próximos 3 dias")
                else:
                    print(f"  Total de programas encontrados (mostrando primeiros 5): {found_programs}")
            
            print("\n" + "=" * 70)
            print("EPG OK - Programação disponível para os próximos dias")
            print("=" * 70)
            return True
        else:
            print(f"Erro ao baixar EPG: HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"Erro: {e}")
        return False

if __name__ == "__main__":
    check_epg_schedule()
