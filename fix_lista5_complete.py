#!/usr/bin/env python3
import requests
import gzip
import io
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import base64
import sys
import time
import hashlib

EPG_URL = "https://epg.pw/xmltv/epg.xml.gz"
VIRUSTOTAL_API_URL = "https://www.virustotal.com/api/v3/urls"

CHANNEL_MAP = {
    "ABC News Live": {
        "epg_id": "465150",
        "tvg_name": "ABC News Live",
        "logo": "https://keyframe-cdn.abcnews.com/streamprovider1.jpg",
    },
    "Fox Business": {
        "epg_id": "464766",
        "tvg_name": "Fox Business HD",
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/c9b2e2eb-7b87-435c-9510-eab2650ff944/8b584585-acf2-4c37-aa07-aaf2d077bb20/1280x720/match/676/380/image.jpg?ve=1&tl=1",
    },
    "Fox News": {
        "epg_id": "412132",
        "tvg_name": "Fox News Channel",
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/15de0523-3be4-4a9a-8159-7020114e7036/b6ff623a-26d6-4fd9-8bb8-0856adbf38ce/1280x720/match/676/380/image.jpg?ve=1&tl=1",
    },
    "CBS News": {
        "epg_id": "464941",
        "tvg_name": "CBS News National Stream",
        "logo": "https://www.cbsnews.com/bundles/cbsnewsvideo/images/cbsn--main-bg.jpg",
    },
}

def load_epg() -> Tuple[Dict, Dict]:
    print("Baixando EPG...")
    r = requests.get(EPG_URL, timeout=120, headers={'Accept-Encoding': 'gzip'}, stream=True)
    r.raise_for_status()
    
    channels = {}
    programs = {}
    
    with gzip.open(io.BytesIO(r.content), 'rt', encoding='utf-8') as f:
        in_elem = None
        current_tag = ''
        current_attrs = {}
        current_text = ''
        elem_buffer = ''
        
        for line in f:
            line = line.strip()
            
            if line.startswith('<channel '):
                current_tag = 'channel'
                m = re.match(r'<channel\s+(.*?)>', line)
                if m:
                    attrs = m.group(1)
                    current_attrs = dict(re.findall(r'(\w+)="([^"]*)"', attrs))
                current_text = line
            elif line.startswith('<programme '):
                current_tag = 'programme'
                m = re.match(r'<programme\s+(.*?)>', line)
                if m:
                    attrs = m.group(1)
                    current_attrs = dict(re.findall(r'(\w+)="([^"]*)"', attrs))
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
                        programs[chan].append({
                            'start': start,
                            'stop': stop,
                            'title': title,
                            'desc': desc,
                        })
                except ET.ParseError:
                    pass
                
                current_tag = ''
                current_attrs = {}
                current_text = ''
            elif current_tag:
                current_text += line

    print(f"  Canais no EPG: {len(channels)}")
    total_progs = sum(len(v) for v in programs.values())
    print(f"  Programas no EPG: {total_progs}")
    
    return channels, programs

def verify_stream(url: str) -> Dict:
    result = {
        "status": "unknown",
        "http_code": None,
        "error": None
    }
    try:
        resp = requests.head(url, timeout=10, allow_redirects=True, 
                            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
        result["http_code"] = resp.status_code
        if resp.status_code == 200:
            result["status"] = "ok"
        elif resp.status_code in (301, 302, 303, 307, 308):
            result["status"] = "redirect_ok"
        elif resp.status_code == 405:
            result["status"] = "ok_method_not_allowed"
        elif resp.status_code == 403:
            result["status"] = "forbidden_may_work"
        else:
            result["status"] = f"http_{resp.status_code}"
    except requests.exceptions.Timeout:
        result["status"] = "timeout"
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
    return result

def verify_virustotal(url: str, api_key: Optional[str] = None) -> Dict:
    result = {"status": "not_verified", "malicious": None, "votes": {}, "error": None}
    
    if not api_key:
        result["error"] = "no_api_key"
        return result
    
    try:
        url_id = base64.urlsafe_b64encode(url.encode()).decode().strip("=")
        headers = {"x-apikey": api_key}
        resp = requests.get(f"{VIRUSTOTAL_API_URL}/{url_id}", headers=headers, timeout=30)
        
        if resp.status_code == 200:
            data = resp.json()
            stats = data.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
            result["votes"] = stats
            result["malicious"] = stats.get("malicious", 0) > 0 or stats.get("malicious", 0) > 2
            result["status"] = "verified"
        elif resp.status_code == 404:
            result["status"] = "not_in_db"
        else:
            result["error"] = f"api_error_{resp.status_code}"
    except Exception as e:
        result["error"] = str(e)
    
    return result

def test_epg_programming(programs: Dict, epg_ids: List[str]) -> Dict:
    result = {
        "has_programming": False,
        "today": 0,
        "tomorrow": 0,
        "day_after": 0,
    }
    
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
    
    result["has_programming"] = result["today"] > 0 and result["tomorrow"] > 0
    
    return result

def normalize_name(name: str) -> str:
    name = name.strip()
    name = re.sub(r'\s*\|\s*', ' - ', name)
    name = re.sub(r'\s+', ' ', name)
    return name

def get_canonical_name(name: str) -> str:
    n = name.lower()
    if 'abc' in n and 'news' in n:
        return 'ABC News Live'
    if 'fox business' in n:
        return 'Fox Business'
    if 'fox news' in n:
        return 'Fox News'
    if 'cbs news' in n:
        return 'CBS News'
    return name

def fix_logo_url(url: str) -> str:
    if not url:
        return url
    if 'imgur.com' in url.lower():
        return ''
    url = url.split('?')[0]
    if not url.lower().endswith('.jpg'):
        return ''
    return url

def stream_score(status: str) -> int:
    scores = {
        'ok': 100,
        'redirect_ok': 90,
        'ok_method_not_allowed': 80,
        'forbidden_may_work': 30,
    }
    return scores.get(status, 0)

def main():
    api_key = sys.argv[1] if len(sys.argv) > 1 else None
    
    channels, programs = load_epg()
    
    print("\nCarregando lista5.m3u...")
    with open("lista5.m3u", "r") as f:
        content = f.read()
    
    lines = content.strip().split('\n')
    
    i = 0
    all_channels = []
    
    while i < len(lines):
        line = lines[i].strip()
        
        if line.startswith('#EXTINF:'):
            name_match = re.search(r',([^,]+)$', line)
            name = name_match.group(1).strip() if name_match else "Unknown"
            normalized_name = normalize_name(name)
            canonical = get_canonical_name(normalized_name)
            
            logo_match = re.search(r'tvg-logo="([^"]*)"', line)
            logo = logo_match.group(1) if logo_match else ''
            logo = fix_logo_url(logo)
            
            group_match = re.search(r'group-title="([^"]*)"', line)
            group = group_match.group(1) if group_match else 'NEWS WORLD'
            
            i += 1
            if i >= len(lines):
                i += 1
                continue
            
            url = lines[i].strip()
            
            if not url or not url.startswith('http'):
                i += 1
                continue
            
            epg_info = CHANNEL_MAP.get(canonical)
            epg_id = epg_info['epg_id'] if epg_info else ''
            
            epg_prog = test_epg_programming(programs, [epg_id] if epg_id else [])
            stream_result = verify_stream(url)
            
            if api_key:
                vt_result = verify_virustotal(url, api_key)
                if vt_result.get('malicious'):
                    print(f"  REMOVIDO (malicioso): {normalized_name}")
                    i += 1
                    continue
            
            use_logo = logo if logo else (epg_info['logo'] if epg_info else '')
            
            all_channels.append({
                'name': normalized_name,
                'canonical': canonical,
                'url': url,
                'logo': use_logo,
                'group': group,
                'epg_id': epg_id,
                'has_epg': epg_prog.get('has_programming', False),
                'stream_status': stream_result['status'],
                'stream_score': stream_score(stream_result['status']),
                'epg_today': epg_prog.get('today', 0),
                'epg_tomorrow': epg_prog.get('tomorrow', 0),
                'epg_day_after': epg_prog.get('day_after', 0),
            })
        
        i += 1
    
    print(f"\nTotal de canais brutos: {len(all_channels)}")
    
    seen_canonical = {}
    best_channels = []
    
    for ch in all_channels:
        canon = ch['canonical']
        score = ch['stream_score']
        
        if canon not in seen_canonical:
            seen_canonical[canon] = len(best_channels)
            best_channels.append(ch)
        else:
            existing = best_channels[seen_canonical[canon]]
            if score > existing['stream_score']:
                best_channels[seen_canonical[canon]] = ch
            elif score == existing['stream_score'] and ch['has_epg'] and not existing['has_epg']:
                best_channels[seen_canonical[canon]] = ch
    
    print(f"Canais únicos: {len(best_channels)}")
    
    output_lines = ['#EXTM3U url-tvg="https://epg.pw/xmltv/epg.xml.gz"']
    
    for ch in best_channels:
        tvg_id_attr = f'tvg-id="{ch["epg_id"]}"' if ch["epg_id"] else ''
        logo_attr = f'tvg-logo="{ch["logo"]}"' if ch["logo"] else ''
        group_attr = f'group-title="{ch["group"]}"'
        
        parts = [p for p in [tvg_id_attr, logo_attr, group_attr] if p]
        new_extinf = f"#EXTINF:-1 {' '.join(parts)},{ch['name']}"
        
        output_lines.append(new_extinf)
        output_lines.append(ch['url'])
        
        epg_status = "EPG OK" if ch['has_epg'] else "SEM EPG"
        print(f"  {ch['canonical']} | {epg_status} | Stream: {ch['stream_status']} | EPG: {ch['epg_today']}/{ch['epg_tomorrow']}/{ch['epg_day_after']}")
    
    with open("lista5.m3u", "w") as f:
        f.write('\n'.join(output_lines) + '\n')
    
    print(f"\nArquivo lista5.m3u atualizado com {len(best_channels)} canais!")
    
    print("\n" + "="*60)
    print("RESUMO")
    print("="*60)
    
    with_epg = sum(1 for c in best_channels if c['has_epg'])
    without_epg = sum(1 for c in best_channels if not c['has_epg'])
    
    print(f"Canais com EPG válido: {with_epg}")
    print(f"Canais sem EPG: {without_epg}")

if __name__ == "__main__":
    main()
