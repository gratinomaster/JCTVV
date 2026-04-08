#!/usr/bin/env python3
import re
from datetime import datetime, timedelta

JPG_LOGOS = {
    "ABC News": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/14/American_Broadcasting_Company_Logo.svg/200px-American_Broadcasting_Company_Logo.svg.png",
    "Fox News": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0c/Fox_News_Channel_Logo.svg/200px-Fox_News_Channel_Logo.svg.png",
    "Fox Business": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b9/Fox_Business_Logo.svg/200px-Fox_Business_Logo.svg.png",
    "CBS News": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/00/CBS_Logo_-_2023.svg/200px-CBS_Logo_-_2023.svg.png",
}

def parse_m3u(filepath):
    channels = []
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXTINF:'):
            attrs = line[9:]
            logo = re.search(r'tvg-logo="([^"]*)"', attrs)
            group = re.search(r'group-title="([^"]*)"', attrs)
            comma = attrs.rfind(',')
            name = attrs[comma+1:].strip() if comma != -1 else attrs
            
            url_line = lines[i+1].strip() if i+1 < len(lines) else ""
            
            if url_line and not url_line.startswith('#'):
                channels.append({
                    'name': name,
                    'logo': logo.group(1) if logo else None,
                    'group': group.group(1) if group else None,
                    'url': url_line
                })
                i += 2
            else:
                i += 1
        else:
            i += 1
    return channels

def generate_epg():
    today = datetime.now()
    dates = [today, today + timedelta(days=1), today + timedelta(days=2)]
    
    programs = {
        "ABCNewsLive": [
            ("0600", "0900", "ABC World News This Morning"),
            ("0900", "1100", "Good Morning America"),
            ("1100", "1230", "ABC World News Midday"),
            ("1230", "1400", "ABC Live Now"),
            ("1400", "1600", "The View"),
            ("1600", "1730", "ABC World News This Afternoon"),
            ("1730", "1830", "ABC World News Tonight"),
            ("1830", "1900", "ABC World News Prime"),
            ("1900", "2000", "ABC Evening News"),
            ("2000", "2200", "ABC Live Prime Time"),
            ("2200", "2300", "Nightline"),
            ("2300", "0600", "ABC World News Now"),
        ],
        "FoxNews": [
            ("0600", "0900", "Fox & Friends First"),
            ("0900", "1100", "Fox & Friends"),
            ("1100", "1200", "America's Newsroom"),
            ("1200", "1300", "Fox News @ Noon"),
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
        "FoxBusiness": [
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
        "CBSNews": [
            ("0600", "0700", "CBS Morning News"),
            ("0700", "0900", "CBS This Morning"),
            ("0900", "1000", "CBS News Daily"),
            ("1000", "1200", "CBS This Morning"),
            ("1200", "1230", "CBS News Midday"),
            ("1230", "1330", "CBS News Update"),
            ("1330", "1400", "The Price Is Right"),
            ("1400", "1430", "CBS News Update"),
            ("1430", "1530", "The Young and the Restless"),
            ("1530", "1630", "CBS News Afternoon"),
            ("1630", "1730", "CBS Evening News"),
            ("1730", "1830", "CBS News Evening"),
            ("1830", "1900", "CBS World News Tonight"),
            ("1900", "2000", "60 Minutes"),
            ("2000", "2100", "CBS News Special"),
            ("2100", "2200", "CBS News Special"),
            ("2200", "2300", "CBS News Nightwatch"),
            ("2300", "0600", "CBS News Overnight"),
        ],
    }
    
    channel_ids = {
        "ABCNewsLive": "ABCNewsLive.us",
        "FoxNews": "FoxNewsChannel.us",
        "FoxBusiness": "FoxBusinessNetwork.us",
        "CBSNews": "CBSNewsNetwork.us",
    }
    
    xml = ['<?xml version="1.0" encoding="UTF-8"?>\n<tv>']
    
    for prog_key, prog_list in programs.items():
        ch_id = channel_ids[prog_key]
        
        for date in dates:
            date_str = date.strftime("%Y%m%d")
            for start, stop, title in prog_list:
                xml.append(f'  <programme channel="{ch_id}" start="{date_str}{start}00 +0000" stop="{date_str}{stop}00 +0000">')
                xml.append(f'    <title lang="en">{title}</title>')
                xml.append(f'    <desc lang="en">Live news coverage and programming</desc>')
                xml.append(f'  </programme>')
    
    xml.append('</tv>')
    return '\n'.join(xml)

def main():
    print("Final correction of lista5.m3u...")
    
    channels = parse_m3u('lista5.m3u')
    print(f"Found {len(channels)} channel entries")
    
    seen_urls = set()
    unique_channels = []
    
    for ch in channels:
        url = ch['url']
        if url in seen_urls:
            continue
        seen_urls.add(url)
        
        name = ch['name']
        name_lower = name.lower()
        
        if 'abc news live' in name_lower:
            name = "ABC News Live"
            ch_type = "ABC News"
        elif 'abc news network' in name_lower:
            name = "ABC News Network"
            ch_type = "ABC News"
        elif 'fox business' in name_lower:
            name = "Fox Business"
            ch_type = "Fox Business"
        elif 'fox news' in name_lower:
            name = "Fox News"
            ch_type = "Fox News"
        elif 'cbs' in name_lower or 'cbs' in url.lower():
            name = "CBS News 24/7"
            ch_type = "CBS News"
        else:
            ch_type = name
        
        ch['name'] = name
        ch['type'] = ch_type
        ch['logo'] = JPG_LOGOS.get(ch_type, '')
        
        unique_channels.append(ch)
    
    print(f"Unique channels after deduplication: {len(unique_channels)}")
    
    output_lines = ["#EXTM3U"]
    
    for ch in unique_channels:
        logo = ch.get('logo', '')
        if not logo:
            logo = JPG_LOGOS.get(ch.get('type', ''), '')
        
        group = ch.get('group') or "NEWS WORLD"
        
        output_lines.append(f"#EXTINF:-1 tvg-logo=\"{logo}\" group-title=\"{group}\",{ch['name']}")
        output_lines.append(ch['url'])
    
    with open('lista5.m3u', 'w', encoding='utf-8') as f:
        f.write('\n'.join(output_lines))
    
    print(f"\nSaved lista5.m3u with {len(unique_channels)} channels")
    
    epg = generate_epg()
    with open('lista5_epg_news.xml', 'w', encoding='utf-8') as f:
        f.write(epg)
    
    print(f"Saved lista5_epg_news.xml ({len(epg)} bytes)")
    
    today = datetime.now().strftime("%Y%m%d")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
    dayafter = (datetime.now() + timedelta(days=2)).strftime("%Y%m%d")
    
    print(f"\nEPG programmes:")
    print(f"  Today ({today}): {epg.count(today)} entries")
    print(f"  Tomorrow ({tomorrow}): {epg.count(tomorrow)} entries")
    print(f"  Day After ({dayafter}): {epg.count(dayafter)} entries")

if __name__ == "__main__":
    main()
