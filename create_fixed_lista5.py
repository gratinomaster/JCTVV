#!/usr/bin/env python3
import requests
import re
import gzip
import io
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import time

EPG_BASE_URL = "https://epg.pw/xmltv/epg.xml.gz"

CHANNEL_CONFIG = {
    "ABC News Live": {
        "epg_id": "465150",
        "tvg_name": "ABC News Live",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f7/ABC_News_%282019%29.svg/200px-ABC_News_%282019%29.svg.jpg",
        "url": "https://abcnews-livestreams.akamaized.net/out/v1/6a597119dbd5428a82dc11a2f514a1a2/abcn-live-10-cmaf-manifest/abcn-live-10-index.m3u8",
    },
    "Fox News Channel": {
        "epg_id": "412132",
        "tvg_name": "Fox News Channel",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/17/Fox_News_Channel_logo.svg/200px-Fox_News_Channel_logo.svg.jpg",
        "url": "http://247preview.foxnews.com/hls/live/2020027/fncv3preview/primary.m3u8",
    },
    "Fox Business": {
        "epg_id": "464766",
        "tvg_name": "Fox Business",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/77/Fox_Business_logo.svg/200px-Fox_Business_logo.svg.jpg",
        "url": "http://247preview.foxnews.com/hls/live/2020027/fncv3preview/primary.m3u8",
    },
    "CBS News 24/7": {
        "epg_id": "464941",
        "tvg_name": "CBS News 24/7",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/43/CBS_News.svg/200px-CBS_News.svg.jpg",
        "url": "https://cbsn-us.cbsnstream.cbsnews.com/out/v1/55a8648e8f134e82a470f83d562deeca/master.m3u8",
    },
}

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def test_url(url: str) -> Tuple[bool, int]:
    try:
        r = requests.head(url, timeout=10, allow_redirects=True)
        return r.status_code < 400, r.status_code
    except Exception as e:
        return False, 0

def download_epg() -> Tuple[Dict, Dict]:
    log("Baixando EPG...")
    try:
        r = requests.get(EPG_BASE_URL, timeout=120, headers={'Accept-Encoding': 'gzip'}, stream=True)
        r.raise_for_status()
        
        channels = {}
        programs = {}
        
        with gzip.open(io.BytesIO(r.content), 'rt', encoding='utf-8') as f:
            current_tag = ''
            current_text = ''
            
            for line in f:
                line = line.strip()
                
                if line.startswith('<channel ') or line.startswith('<programme '):
                    current_tag = 'programme' if line.startswith('<programme') else 'channel'
                    current_text = line
                elif line.startswith('</channel>') or line.startswith('</programme>'):
                    current_text += line
                    try:
                        root = ET.fromstring(current_text)
                        if current_tag == 'channel':
                            cid = root.get('id', '')
                            name = root.findtext('display-name', '')
                            icon_elem = root.find('icon')
                            icon = icon_elem.get('src', '') if icon_elem is not None else ''
                            channels[cid] = {'name': name, 'logo': icon}
                        elif current_tag == 'programme':
                            chan = root.get('channel', '')
                            start = root.get('start', '')
                            stop = root.get('stop', '')
                            title = root.findtext('title', '')
                            desc = root.findtext('desc', '')
                            if chan not in programs:
                                programs[chan] = []
                            programs[chan].append({'start': start, 'stop': stop, 'title': title, 'desc': desc})
                    except ET.ParseError:
                        pass
                    current_tag = ''
                    current_text = ''
                elif current_tag:
                    current_text += line
        
        log(f"  Canais no EPG: {len(channels)}")
        return channels, programs
    except Exception as e:
        log(f"Erro ao baixar EPG: {e}")
        return {}, {}

def check_epg_programming(programs: Dict, epg_ids: List[str]) -> Dict:
    result = {"today": 0, "tomorrow": 0, "day_after": 0}
    hoje = datetime.now().strftime("%Y%m%d")
    amanha = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
    depois = (datetime.now() + timedelta(days=2)).strftime("%Y%m%d")
    
    for eid in epg_ids:
        if eid in programs:
            for p in programs[eid]:
                start = p['start'][:8] if p['start'] else ''
                if start == hoje:
                    result["today"] += 1
                elif start == amanha:
                    result["tomorrow"] += 1
                elif start == depois:
                    result["day_after"] += 1
    
    return result

def create_custom_epg(channel_id: str, channel_name: str, logo: str, days: int = 3) -> str:
    root = ET.Element('tv')
    ch_elem = ET.SubElement(root, 'channel', id=channel_id)
    dn = ET.SubElement(ch_elem, 'display-name')
    dn.text = channel_name
    icon = ET.SubElement(ch_elem, 'icon')
    icon.set('src', logo)
    
    schedule = [
        ("060000", "090000", "World News This Morning", "Morning news coverage"),
        ("090000", "110000", "Good Morning America", "Morning news and entertainment"),
        ("110000", "123000", "World News Midday", "Midday news update"),
        ("123000", "140000", "Live Now", "Breaking news and updates"),
        ("140000", "160000", "The View", "Talk show with guest discussions"),
        ("160000", "173000", "World News This Afternoon", "Afternoon news coverage"),
        ("173000", "183000", "World News Tonight", "Evening news broadcast"),
        ("183000", "190000", "World News Prime", "Prime time news hour"),
        ("190000", "200000", "Evening News", "Main evening news broadcast"),
        ("200000", "220000", "Prime Time News", "Prime time news coverage"),
        ("220000", "230000", "Nightline", "Late night news program"),
        ("230000", "235959", "World News Now", "Overnight news coverage"),
    ]
    
    today = datetime.now()
    for day_offset in range(days):
        current_day = today + timedelta(days=day_offset)
        date_str = current_day.strftime("%Y%m%d")
        
        for start_time, stop_time, title, desc in schedule:
            if day_offset == days - 1 and stop_time == "235959":
                next_day = current_day + timedelta(days=1)
                stop = f"{next_day.strftime('%Y%m%d')}060000 +0000"
            else:
                stop = f"{date_str}{stop_time} +0000"
            
            prog = ET.SubElement(root, 'programme')
            prog.set('channel', channel_id)
            prog.set('start', f"{date_str}{start_time} +0000")
            prog.set('stop', stop)
            
            t = ET.SubElement(prog, 'title', lang='en')
            t.text = title
            d = ET.SubElement(prog, 'desc', lang='en')
            d.text = desc
    
    return ET.tostring(root, encoding='unicode')

def main():
    log("Iniciando correção da lista5.m3u")
    
    channels, programs = download_epg()
    
    output_lines = ['#EXTM3U']
    valid_channels = []
    epg_report = []
    
    log("\nProcessando canais...")
    for name, config in CHANNEL_CONFIG.items():
        log(f"\n  {name}:")
        
        works, code = test_url(config['url'])
        log(f"    Stream: {'OK' if works else f'FALHOU ({code})'}")
        
        epg_prog = check_epg_programming(programs, [config['epg_id']])
        has_epg = epg_prog['today'] > 0 and epg_prog['tomorrow'] > 0
        
        log(f"    EPG: Hoje={epg_prog['today']}, Amanha={epg_prog['tomorrow']}, Depois={epg_prog['day_after']}")
        
        if works:
            logo = config['logo']
            
            epg_line = f'tvg-id="{config["epg_id"]}"' if config['epg_id'] else ''
            logo_line = f'tvg-logo="{logo}"' if logo else ''
            group_line = 'group-title="NEWS WORLD"'
            
            attrs = ' '.join(filter(None, [epg_line, logo_line, group_line]))
            extinf = f"#EXTINF:-1 {attrs},{name}"
            
            output_lines.append(extinf)
            output_lines.append(config['url'])
            output_lines.append('')
            
            valid_channels.append(name)
            epg_report.append({
                'name': name,
                'has_stream': True,
                'has_epg': has_epg,
                'epg_today': epg_prog['today'],
                'epg_tomorrow': epg_prog['tomorrow'],
                'epg_day_after': epg_prog['day_after'],
            })
        else:
            epg_report.append({
                'name': name,
                'has_stream': False,
                'has_epg': False,
            })
    
    if valid_channels:
        with open('lista5.m3u', 'w') as f:
            f.write('\n'.join(output_lines))
        log(f"\nLista salva: lista5.m3u ({len(valid_channels)} canais)")
    else:
        log("\nNenhum canal válido!")
    
    log("\n" + "="*60)
    log("RELATÓRIO EPG")
    log("="*60)
    for r in epg_report:
        status = []
        if r['has_stream']:
            status.append("STREAM OK")
        if r['has_epg']:
            status.append(f"EPG OK ({r['epg_today']}/{r['epg_tomorrow']}/{r['epg_day_after']})")
        else:
            status.append("SEM EPG")
        
        if not r['has_stream']:
            status = ["SEM STREAM"]
        
        log(f"  {r['name']}: {' | '.join(status)}")
    
    with_epg = sum(1 for r in epg_report if r.get('has_epg'))
    without_epg = sum(1 for r in epg_report if not r.get('has_epg') and r.get('has_stream'))
    with_stream = sum(1 for r in epg_report if r.get('has_stream'))
    
    log(f"\nCanais com stream: {with_stream}")
    log(f"Canais com EPG: {with_epg}")
    log(f"Canais sem EPG: {without_epg}")
    
    if without_epg > 0:
        log("\nGerando EPG personalizado para canais sem EPG...")
        for r in epg_report:
            if r.get('has_stream') and not r.get('has_epg'):
                for name, config in CHANNEL_CONFIG.items():
                    if name == r['name']:
                        epg_xml = create_custom_epg(config['epg_id'], name, config['logo'], days=3)
                        filename = f"lista5_epg_{name.replace(' ', '_').lower()}.xml"
                        with open(filename, 'w') as f:
                            f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
                            f.write(epg_xml)
                        log(f"  {name}: {filename}")

if __name__ == '__main__':
    main()
