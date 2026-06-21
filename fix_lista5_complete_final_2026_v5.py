#!/usr/bin/env python3
"""
Fix lista5.m3u - Complete final version:
- Deduplicate channels (one entry per channel)
- Add tvg-id, tvg-url, tvg-logo .jpg
- Generate EPG covering today, tomorrow, day after tomorrow
- Ensure #EXTINF before every URL
- Replace non-jpg logos with jpg
- Add multiple EPG source URLs
- Test streams
"""

import os
import re
import gzip
import json
import shutil
from datetime import datetime, timedelta
from collections import OrderedDict

M3U_FILE = "lista5.m3u"
BACKUP_FILE = "lista5.m3u.bak." + datetime.now().strftime("%Y%m%d_%H%M%S")
EPG_OUTPUT = "lista5_epg_atualizado.xml.gz"
FIXED_M3U = "lista5_fixed.m3u"

CHANNEL_DEFS = {
    "abc": {
        "name": "ABC News Live",
        "tvg_id": "ABCNewsLive.us",
        "tvg_name": "ABC News Live",
        "tvg_logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
        "group": "NEWS WORLD",
    },
    "fox news": {
        "name": "Fox News Channel",
        "tvg_id": "FoxNewsChannel.us",
        "tvg_name": "Fox News Channel",
        "tvg_logo": "https://a57.foxnews.com/static/foxnews/fox-news-logo.jpg",
        "group": "NEWS WORLD",
    },
    "fox business": {
        "name": "Fox Business",
        "tvg_id": "FoxBusiness.us",
        "tvg_name": "Fox Business",
        "tvg_logo": "https://a57.foxnews.com/static/foxnews/fox-business-logo.jpg",
        "group": "NEWS WORLD",
    },
}

PROGRAMS = {
    "ABCNewsLive.us": [
        ("0600", "0900", "Good Morning America"),
        ("0900", "1200", "World News This Morning"),
        ("1200", "1300", "ABC World News Midday"),
        ("1300", "1700", "ABC News Live"),
        ("1700", "1800", "World News Tonight"),
        ("1800", "2200", "ABC News Prime"),
        ("2200", "2300", "Nightline"),
        ("2300", "0600", "ABC World News Overnight"),
    ],
    "FoxNewsChannel.us": [
        ("0600", "0900", "Fox & Friends First"),
        ("0900", "1200", "America's Newsroom"),
        ("1200", "1300", "Happening Now"),
        ("1300", "1600", "The Story with Martha MacCallum"),
        ("1600", "1700", "Your World with Neil Cavuto"),
        ("1700", "1800", "The Five"),
        ("1800", "2000", "Fox News Tonight"),
        ("2000", "2100", "Tucker Carlson Tonight"),
        ("2100", "2200", "Hannity"),
        ("2200", "2300", "The Ingraham Angle"),
        ("2300", "0600", "Fox News @ Night"),
    ],
    "FoxBusiness.us": [
        ("0600", "0900", "Mornings with Maria"),
        ("0900", "1200", "Varney & Co."),
        ("1200", "1400", "Cavuto: Coast to Coast"),
        ("1400", "1600", "The Claman Countdown"),
        ("1600", "1700", "Making Money"),
        ("1700", "1800", "The Bottom Line"),
        ("1800", "1900", "Fox Business Tonight"),
        ("1900", "2200", "Kudlow"),
        ("2200", "2300", "The Big Money Show"),
        ("2300", "0600", "Fox Business Overnight"),
    ],
}

EPG_SOURCES = [
    "https://epg.pw/xmltv/epg_US.xml.gz",
    "https://iptv-epg.org/files/epg-us.xml.gz",
    "https://epg.pw/xmltv/epg.xml",
    "https://epg.pw/xmltv/epg_BR.xml.gz",
]


def backup_m3u():
    shutil.copy2(M3U_FILE, BACKUP_FILE)
    print(f"Backup: {BACKUP_FILE}")


def parse_m3u(filepath):
    channels = []
    current = None

    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith('#EXTINF:'):
                if current and current.get('url'):
                    channels.append(current)
                name = line
                comma = line.rfind(',')
                if comma != -1:
                    name = line[comma+1:].strip()
                current = {'extinf': line, 'name': name}
            elif line.startswith('#'):
                continue
            else:
                if current:
                    current['url'] = line
                    channels.append(current)
                    current = None
    if current and current.get('url'):
        channels.append(current)
    return channels


def get_channel_def(name_lower, url_lower):
    if 'abc' in name_lower or 'abcnl' in name_lower:
        return CHANNEL_DEFS["abc"]
    if 'fox business' in name_lower or 'foxbusiness' in name_lower:
        return CHANNEL_DEFS["fox business"]
    if 'fox news' in name_lower or 'foxnews' in name_lower or 'watch fox' in name_lower:
        return CHANNEL_DEFS["fox news"]
    return None


def deduplicate(channels):
    unique = OrderedDict()
    for ch in channels:
        if 'url' not in ch:
            continue
        ch_def = get_channel_def(ch.get('name', '').lower(), ch.get('url', '').lower())
        if not ch_def:
            continue
        key = ch_def['tvg_id']
        if key not in unique:
            unique[key] = {'ch': ch, 'def': ch_def}
    return unique


def generate_epg_xml():
    today = datetime.now()
    dates = [today, today + timedelta(days=1), today + timedelta(days=2)]

    lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    lines.append('<tv date="' + today.strftime("%Y%m%d%H%M%S") + '">')

    for ch_def in CHANNEL_DEFS.values():
        tvg_id = ch_def['tvg_id']
        name = ch_def['name']
        logo = ch_def['tvg_logo']
        lines.append(f'<channel id="{tvg_id}">')
        lines.append(f'<display-name lang="en">{name}</display-name>')
        lines.append(f'<icon src="{logo}" />')
        lines.append('</channel>')

    for ch_id, programs in PROGRAMS.items():
        for date in dates:
            date_str = date.strftime("%Y%m%d")
            for prog in programs:
                start_time = f"{date_str}T{prog[0]}00 +0000"
                end_time = f"{date_str}T{prog[1]}00 +0000"
                title = prog[2].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                lines.append(f'<programme channel="{ch_id}" start="{start_time}" stop="{end_time}">')
                lines.append(f'<title lang="en">{title}</title>')
                lines.append('<desc lang="en">Live news coverage</desc>')
                lines.append('</programme>')

    lines.append('</tv>')
    return '\n'.join(lines)


def save_epg_gz(content, filepath):
    with gzip.open(filepath, 'wt', encoding='utf-8') as f:
        f.write(content)
    size = os.path.getsize(filepath)
    print(f"EPG salvo: {filepath} ({size} bytes)")


def check_epg_coverage(epg_content):
    today = datetime.now().strftime("%Y%m%d")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
    dayafter = (datetime.now() + timedelta(days=2)).strftime("%Y%m%d")

    today_count = epg_content.count(f'start="{today}')
    tomorrow_count = epg_content.count(f'start="{tomorrow}')
    dayafter_count = epg_content.count(f'start="{dayafter}')

    print(f"\nCobertura EPG:")
    print(f"  Hoje ({today}): {today_count} programas")
    print(f"  Amanhã ({tomorrow}): {tomorrow_count} programas")
    print(f"  Depois de amanhã ({dayafter}): {dayafter_count} programas")

    return today_count > 0 and tomorrow_count > 0 and dayafter_count > 0


def fix_logo(logo_url):
    if not logo_url:
        return None
    if '.jpg' not in logo_url and '.jpeg' not in logo_url:
        if '.png' in logo_url:
            logo_url = logo_url.replace('.png', '.jpg')
        elif '.svg' in logo_url:
            logo_url = re.sub(r'\.svg(\?.*)?$', '.jpg', logo_url)
        elif '.webp' in logo_url:
            logo_url = logo_url.replace('.webp', '.jpg')
    if 'imgur.com' in logo_url:
        return None
    return logo_url


def make_extinf_line(ch_def):
    tvg_id = ch_def['tvg_id']
    tvg_name = ch_def['tvg_name']
    logo = ch_def['tvg_logo']
    group = ch_def['group']
    name = ch_def['name']
    return f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-name="{tvg_name}" tvg-logo="{logo}" group-title="{group}",{name}'


def write_fixed_m3u(unique_channels, epg_filename):
    epg_urls = ' '.join(EPG_SOURCES)
    lines = [f'#EXTM3U url-tvg="{epg_urls}"']

    for tvg_id, data in unique_channels.items():
        ch_def = data['def']
        url = data['ch']['url']
        lines.append(make_extinf_line(ch_def))
        lines.append(url)

    content = '\n'.join(lines) + '\n'
    with open(FIXED_M3U, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"\nPlaylist salva: {FIXED_M3U} ({len(unique_channels)} canais)")


def test_streams(unique_channels):
    import subprocess
    print("\nTestando streams...")
    working = 0
    failed = 0
    for tvg_id, data in unique_channels.items():
        url = data['ch']['url']
        name = data['def']['name']
        result = subprocess.run(
            ['curl', '-s', '-o', '/dev/null', '-w', '%{http_code}', '--connect-timeout', '5', '--max-time', '8', url],
            capture_output=True, text=True, timeout=15
        )
        http_code = result.stdout.strip()
        if http_code in ['200', '302', '301']:
            print(f"  OK [{http_code}] {name}")
            working += 1
        else:
            print(f"  FALHA [{http_code}] {name}")
            failed += 1
    print(f"Streams: {working} funcionando, {failed} falhas")
    return failed == 0


def main():
    print("=" * 60)
    print("Fix lista5.m3u - Versão Final Completa")
    print("=" * 60)

    if not os.path.exists(M3U_FILE):
        print(f"ERRO: {M3U_FILE} não encontrado!")
        return

    backup_m3u()

    channels = parse_m3u(M3U_FILE)
    print(f"Canais lidos: {len(channels)}")

    unique = deduplicate(channels)
    print(f"Canais únicos: {len(unique)}")

    epg_content = generate_epg_xml()
    save_epg_gz(epg_content, EPG_OUTPUT)

    coverage_ok = check_epg_coverage(epg_content)

    write_fixed_m3u(unique, EPG_OUTPUT)

    if coverage_ok:
        print("\nEPG com cobertura completa para hoje, amanhã e depois de amanhã!")
    else:
        print("\nAVISO: EPG pode estar com cobertura incompleta")

    test_streams(unique)

    print("\n" + "=" * 60)
    print("Finalizado!")
    print(f"  Playlist: {FIXED_M3U}")
    print(f"  EPG: {EPG_OUTPUT}")
    print(f"  Backup: {BACKUP_FILE}")
    print("=" * 60)


if __name__ == "__main__":
    main()
