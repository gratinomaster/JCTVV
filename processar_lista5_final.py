#!/usr/bin/env python3
import re
import requests
from datetime import datetime
import hashlib
import gzip
import io

def extract_channels(m3u_content):
    channels = []
    lines = m3u_content.strip().split('\n')
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXTINF:'):
            info = line.replace('#EXTINF:', '').strip()
            
            tvg_logo = None
            if 'tvg-logo="' in info:
                match = re.search(r'tvg-logo="([^"]+)"', info)
                if match:
                    tvg_logo = match.group(1)
            
            group = None
            if 'group-title="' in info:
                match = re.search(r'group-title="([^"]+)"', info)
                if match:
                    group = match.group(1)
            
            name = info.split(',')[-1].strip() if ',' in info else 'Unknown'
            
            if i + 1 < len(lines):
                url = lines[i + 1].strip()
                if url and not url.startswith('#'):
                    channels.append({
                        'name': name,
                        'url': url,
                        'tvg_logo': tvg_logo,
                        'group': group,
                        'line_num': i + 1
                    })
        i += 1
    return channels

def check_url_health(url, timeout=15):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        resp = requests.head(url, headers=headers, timeout=timeout, allow_redirects=True)
        if resp.status_code == 200:
            return 'ok'
        elif resp.status_code == 401 or resp.status_code == 403:
            return 'auth'
        else:
            return f'http_{resp.status_code}'
    except requests.exceptions.Timeout:
        return 'timeout'
    except requests.exceptions.SSLError:
        return 'ssl_error'
    except Exception as e:
        return f'error_{str(e)[:20]}'

def fix_logo_extension(logo_url):
    if not logo_url:
        return None
    logo_url_lower = logo_url.lower()
    
    if 'imgur.com' in logo_url_lower:
        return None
    
    if logo_url_lower.endswith('.png') or logo_url_lower.endswith('.gif') or logo_url_lower.endswith('.webp'):
        return logo_url
    elif logo_url_lower.endswith('.jpg') or logo_url_lower.endswith('.jpeg'):
        return logo_url
    else:
        return logo_url
    
    return logo_url

def generate_programs_for_channel(channel_name, days=3):
    from datetime import timedelta
    
    today = datetime.now()
    programs = []
    
    time_slots = [
        (6, 9, 'Morning Show'),
        (9, 12, 'News Today'),
        (12, 13, 'Midday News'),
        (13, 18, 'Afternoon Edition'),
        (18, 19, 'Evening News'),
        (19, 22, 'Prime Time'),
        (22, 6, 'Night Edition'),
    ]
    
    for day_offset in range(days):
        current_day = today + timedelta(days=day_offset)
        
        for start_h, end_h, title in time_slots:
            if start_h == 22:
                start = current_day.replace(hour=22, minute=0, second=0)
                end = (current_day + timedelta(days=1)).replace(hour=6, minute=0, second=0)
            else:
                start = current_day.replace(hour=start_h, minute=0, second=0)
                end = current_day.replace(hour=end_h, minute=0, second=0)
            
            programs.append({
                'start': start,
                'end': end,
                'title': f'{title} - {current_day.strftime("%A")}',
                'desc': f'Programação {channel_name}'
            })
    
    return programs

def create_epg_xml(channel_list, output_file='lista5_epg.xml'):
    today = datetime.now()
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f'''<?xml version="1.0" encoding="UTF-8"?>
<tv date="{today.strftime('%Y%m%d%H%M%S')}">
''')
        
        for ch in channel_list:
            ch_id = hashlib.md5(ch['name'].encode()).hexdigest()[:16]
            logo = ch.get('tvg_logo', '')
            f.write(f'''  <channel id="{ch_id}">
    <display-name lang="en">{ch['name']}</display-name>
    <icon src="{logo}" />
  </channel>
''')
        
        for ch in channel_list:
            ch_id = hashlib.md5(ch['name'].encode()).hexdigest()[:16]
            programs = generate_programs_for_channel(ch['name'])
            
            for prog in programs:
                start_str = prog['start'].strftime('%Y%m%d%H%M%S') + ' +0000'
                end_str = prog['end'].strftime('%Y%m%d%H%M%S') + ' +0000'
                f.write(f'''  <programme channel="{ch_id}" start="{start_str}" stop="{end_str}">
    <title lang="en">{prog['title']}</title>
    <desc lang="en">{prog['desc']}</desc>
  </programme>
''')
        
        f.write('</tv>\n')

def process_lista5():
    print("=" * 70)
    print("Processando lista5.m3u")
    print("=" * 70)
    
    with open('lista5.m3u', 'r', encoding='utf-8') as f:
        content = f.read()
    
    channels = extract_channels(content)
    print(f"\nCanais encontrados: {len(channels)}")
    
    print("\n--- Verificando logos ---")
    for ch in channels:
        if ch['tvg_logo']:
            if ch['tvg_logo'].endswith('.png') or ch['tvg_logo'].endswith('.gif') or ch['tvg_logo'].endswith('.webp'):
                print(f"[NON-JPG] {ch['name']}: {ch['tvg_logo']}")
            elif 'imgur.com' in ch['tvg_logo']:
                print(f"[IMGUR] {ch['name']}: {ch['tvg_logo']}")
            else:
                print(f"[OK] {ch['name']}: {ch['tvg_logo'][:60]}...")
        else:
            print(f"[SEM LOGO] {ch['name']}")
    
    print("\n--- Testando streams ---")
    print("(Primeiros 3 canais para teste rápido)")
    
    test_results = []
    for i, ch in enumerate(channels[:3]):
        status = check_url_health(ch['url'])
        test_results.append((ch['name'], ch['url'], status))
        print(f"{'OK' if status == 'ok' else status}: {ch['name']}")
    
    create_epg_xml(channels)
    print("\n--- EPG gerado: lista5_epg.xml ---")
    
    return channels

if __name__ == "__main__":
    process_lista5()