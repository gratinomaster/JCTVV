#!/usr/bin/env python3
import requests
import json
import hashlib
import time
import re
from datetime import datetime, timedelta
from urllib.parse import quote

VT_API_KEY = ""

CHANNEL_MAPPING = {
    "ABC News Live": {
        "id": "ABCNewsLive.us",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/14/American_Broadcasting_Company_Logo.svg/200px-American_Broadcasting_Company_Logo.svg.png",
        "epg_id": "ABCNewsLive.us"
    },
    "ABCNL": {
        "id": "ABCNewsNetwork.us",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/14/American_Broadcasting_Company_Logo.svg/200px-American_Broadcasting_Company_Logo.svg.png",
        "epg_id": "ABCNewsLive.us"
    },
    "Fox News": {
        "id": "FoxNewsChannel.us",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0c/Fox_News_Channel_Logo.svg/200px-Fox_News_Channel_Logo.svg.png",
        "epg_id": "FoxNewsChannel.us"
    },
    "Fox Business": {
        "id": "FoxBusinessNetwork.us",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b9/Fox_Business_Logo.svg/200px-Fox_Business_Logo.svg.png",
        "epg_id": "FoxBusinessNetwork.us"
    },
    "CBS News": {
        "id": "CBSNews.us",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/00/CBS_Logo_-_2023.svg/200px-CBS_Logo_-_2023.svg.png",
        "epg_id": "CBSNews.us"
    },
}

PROGRAMS = {
    "ABCNewsLive.us": [
        ("0600", "1000", "ABC World News This Morning"),
        ("1000", "1130", "Good Morning America"),
        ("1130", "1230", "ABC World News Midday"),
        ("1230", "1330", "ABC World News Now"),
        ("1330", "1500", "The View"),
        ("1500", "1630", "ABC World News Afternoon"),
        ("1630", "1730", "ABC World News Tonight"),
        ("1730", "1830", "ABC World News Evening"),
        ("1830", "1900", "ABC World News Prime"),
        ("1900", "1930", "ABC World News Tonight"),
        ("1930", "2030", "ABC Live Prime Time"),
        ("2030", "2100", "Nightline"),
        ("2100", "2200", "ABC World News Now"),
        ("2200", "2300", "ABC World News Overnight"),
        ("2300", "0600", "ABC World News Overnight"),
    ],
    "FoxNewsChannel.us": [
        ("0600", "0900", "Fox & Friends First"),
        ("0900", "1100", "Fox & Friends"),
        ("1100", "1200", "America's Newsroom"),
        ("1200", "1300", "Fox News at Noon"),
        ("1300", "1500", "The Story"),
        ("1500", "1700", "The Five"),
        ("1700", "1800", "Fox News Tonight"),
        ("1800", "1900", "Fox News Sunday"),
        ("1900", "2000", "Tucker Carlson Tonight"),
        ("2000", "2100", "Hannity"),
        ("2100", "2200", "The Ingraham Angle"),
        ("2200", "2300", "Fox News @ Night"),
        ("2300", "0600", "Fox News Overnight"),
    ],
    "FoxBusinessNetwork.us": [
        ("0600", "0900", "Fox Business Morning"),
        ("0900", "1100", "Varney & Co."),
        ("1100", "1200", "The Big Money Show"),
        ("1200", "1300", "Fox Business Midday"),
        ("1300", "1400", "The Claman Countdown"),
        ("1400", "1500", "Making Money"),
        ("1500", "1700", "The Five"),
        ("1700", "1800", "Cavuto: Coast to Coast"),
        ("1800", "1900", "Fox Business Tonight"),
        ("1900", "2000", "Kudlow"),
        ("2000", "2100", "The Big Money Show"),
        ("2100", "2200", "Fox Business @ Night"),
        ("2200", "0600", "Fox Business Overnight"),
    ],
    "CBSNews.us": [
        ("0600", "0700", "CBS Morning News"),
        ("0700", "0900", "CBS This Morning"),
        ("0900", "1000", "CBS News Daily"),
        ("1000", "1230", "Let's Make a Deal"),
        ("1230", "1330", "CBS News Midday"),
        ("1330", "1430", "The Price Is Right"),
        ("1430", "1530", "The Young and the Restless"),
        ("1530", "1630", "CBS News Afternoon"),
        ("1630", "1730", "CBS Evening News"),
        ("1730", "1830", "CBS News Evening"),
        ("1830", "1900", "CBS World News Tonight"),
        ("1900", "2000", "60 Minutes"),
        ("2000", "2100", "The Simpsons"),
        ("2100", "2200", "CBS News Special"),
        ("2200", "2300", "CBS News Nightwatch"),
        ("2300", "0600", "CBS News Overnight"),
    ],
}

def get_url_info(url):
    url_hash = hashlib.md5(url.encode()).hexdigest()
    headers = {"x-apikey": VT_API_KEY} if VT_API_KEY else {}
    
    try:
        public_url = "https://www.virustotal.com/api/v3/urls"
        response = requests.post(public_url, 
                               headers={"Content-Type": "application/x-www-form-urlencoded"},
                               data=f"url={quote(url)}",
                               timeout=60)
        if response.status_code == 200:
            result = response.json()
            analysis_link = result.get("data", {}).get("links", {}).get("self")
            if analysis_link:
                time.sleep(3)
                analysis = requests.get(analysis_link, headers={"x-apikey": VT_API_KEY} if VT_API_KEY else {}, timeout=60)
                if analysis.status_code == 200:
                    data = analysis.json()
                    stats = data.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
                    return stats.get("malicious", 0), stats.get("suspicious", 0)
    except Exception:
        pass
    return None, None

def parse_m3u(filepath):
    channels = []
    current = None
    
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line.startswith('#EXTINF:'):
                attrs = line[9:]
                logo = re.search(r'tvg-logo="([^"]*)"', attrs)
                group = re.search(r'group-title="([^"]*)"', attrs)
                name = attrs
                comma = attrs.rfind(',')
                if comma != -1:
                    name = attrs[comma+1:].strip()
                current = {
                    'name': name,
                    'logo': logo.group(1) if logo else None,
                    'group': group.group(1) if group else None,
                }
            elif line and not line.startswith('#') and current:
                current['url'] = line
                
                name_lower = current['name'].lower()
                if 'fox business' in name_lower:
                    current['type'] = 'Fox Business'
                elif 'fox news' in name_lower:
                    current['type'] = 'Fox News'
                elif 'cbs news' in name_lower or 'cbsn' in name_lower or 'cbs news' in current.get('url', '').lower():
                    current['type'] = 'CBS News'
                elif 'abc' in name_lower or 'abcnl' in name_lower:
                    current['type'] = 'ABC News'
                else:
                    current['type'] = 'Unknown'
                
                channels.append(current)
                current = None
    return channels

def generate_epg():
    today = datetime.now()
    dates = [today, today + timedelta(days=1), today + timedelta(days=2)]
    
    xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<tv>']
    
    for channel_id, programs in PROGRAMS.items():
        for ch_name, info in CHANNEL_MAPPING.items():
            if info['epg_id'] == channel_id:
                xml.append(f'<channel id="{channel_id}"><display-name>{ch_name}</display-name><icon src="{info["logo"]}"/></channel>')
                break
        
        for date in dates:
            date_str = date.strftime("%Y%m%d")
            for prog in programs:
                start_time = f"{date_str}{prog[0]}00 +0000"
                end_time = f"{date_str}{prog[1]}00 +0000"
                xml.append(f'<programme channel="{channel_id}" start="{start_time}" stop="{end_time}">')
                xml.append(f'<title lang="en">{prog[2]}</title>')
                xml.append(f'<desc lang="en">Live news coverage</desc>')
                xml.append(f'</programme>')
    
    xml.append('</tv>')
    return '\n'.join(xml)

def main():
    print("=" * 70)
    print("Lista5 News Channels - Final Correction")
    print("=" * 70)
    
    channels = parse_m3u('lista5.m3u')
    print(f"\nFound {len(channels)} channels")
    
    unique = {}
    for ch in channels:
        base = ch['url'].split('?')[0]
        if base not in unique:
            unique[base] = {'ch': ch, 'variants': []}
        unique[base]['variants'].append(ch)
    
    print(f"Found {len(unique)} unique streams")
    
    print("\n" + "-" * 70)
    print("VirusTotal Check...")
    print("-" * 70)
    
    keep_urls = {}
    for base, data in unique.items():
        print(f"Checking: {base[:60]}...")
        malicious, suspicious = get_url_info(data['ch']['url'])
        
        if malicious is None:
            status = "UNKNOWN (keeping)"
            keep = True
        elif malicious > 0:
            status = f"MALICIOUS ({malicious}) - removing"
            keep = False
        elif suspicious > 0:
            status = f"SUSPICIOUS ({suspicious}) - removing"
            keep = False
        else:
            status = "CLEAN"
            keep = True
        
        print(f"  {status}")
        keep_urls[base] = keep
        time.sleep(1.5)
    
    print("\n" + "-" * 70)
    print("Generating EPG...")
    print("-" * 70)
    
    epg_content = generate_epg()
    with open('lista5_epg_news.xml', 'w', encoding='utf-8') as f:
        f.write(epg_content)
    print(f"EPG saved to lista5_epg_news.xml ({len(epg_content)} bytes)")
    
    print("\n" + "-" * 70)
    print("Generating final lista5.m3u...")
    print("-" * 70)
    
    epg_url = "lista5_epg_news.xml"
    
    output = ["#EXTM3U"]
    seen = set()
    count = 0
    
    for base, data in unique.items():
        if not keep_urls.get(base, True):
            print(f"Removing: {data['ch']['name']}")
            continue
        
        if base in seen:
            continue
        seen.add(base)
        
        ch = data['ch']
        
        name = ch['name']
        if 'abc news live - abc news' in name.lower():
            name = "ABC News Live"
        elif 'watch live news' in name.lower():
            name = "ABC News Network"
        elif 'fox business' in name.lower():
            name = "Fox Business"
        elif 'fox news' in name.lower():
            name = "Fox News"
        elif 'cbs' in name.lower():
            name = "CBS News 24/7"
        
        logo = ch.get('logo')
        for key, info in CHANNEL_MAPPING.items():
            if key.lower() in name.lower() or key.lower() in ch.get('name', '').lower():
                logo = info['logo']
                break
        
        group = ch.get('group') or "NEWS WORLD"
        
        output.append(f"#EXTINF:-1 tvg-logo=\"{logo}\" group-title=\"{group}\",{name}")
        output.append(ch['url'])
        count += 1
    
    with open('lista5.m3u', 'w', encoding='utf-8') as f:
        f.write('\n'.join(output))
    
    print(f"\nFinal list: {count} channels")
    print("Saved lista5.m3u")
    
    print("\n" + "=" * 70)
    print("Testing EPG - checking today's programming...")
    print("=" * 70)
    
    today = datetime.now().strftime("%Y%m%d")
    today_programs = epg_content.count(today)
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
    tomorrow_programs = epg_content.count(tomorrow)
    dayafter = (datetime.now() + timedelta(days=2)).strftime("%Y%m%d")
    dayafter_programs = epg_content.count(dayafter)
    
    print(f"Today ({today}): {today_programs} programme entries")
    print(f"Tomorrow ({tomorrow}): {tomorrow_programs} programme entries")
    print(f"Day After ({dayafter}): {dayafter_programs} programme entries")
    
    print("\n" + "=" * 70)
    print("DONE!")
    print("=" * 70)

if __name__ == "__main__":
    main()
