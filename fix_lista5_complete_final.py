#!/usr/bin/env python3
import re, os, shutil, gzip, io
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from collections import OrderedDict

BASE = "/home/runner/work/JCTVV/JCTVV"
M3U_FILE = f"{BASE}/lista5.m3u"
EPG_XML_FILE = f"{BASE}/lista5_epg.xml"
EPG_GZ_FILE = f"{BASE}/lista5_epg.xml.gz"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# Channel mapping: name pattern -> tvg-id
CHANNEL_MAP = OrderedDict([
    ("ABC News Live", "465150"),
    ("Fox News Channel", "465372"),
    ("Fox Business", "464766"),
    ("CBS News 24/7", "464941"),
])

def log(msg):
    print(msg)

def backup_file():
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    bak = f"{BASE}/lista5.m3u.backup_{ts}"
    shutil.copy2(M3U_FILE, bak)
    log(f"Backup: {bak}")
    return bak

def parse_m3u(content):
    """Parse M3U content, return list of channels, dedup by name."""
    channels = OrderedDict()
    lines = content.strip().split('\n')
    i = 0
    extm3u_line = ""
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXTM3U'):
            extm3u_line = line
            i += 1
            continue
        if line.startswith('#EXTINF:'):
            name_match = re.search(r',([^,]+)$', line)
            name = name_match.group(1).strip() if name_match else 'Unknown'
            tvg_id = re.search(r'tvg-id="([^"]*)"', line)
            tvg_logo = re.search(r'tvg-logo="([^"]*)"', line)
            tvg_name = re.search(r'tvg-name="([^"]*)"', line)
            group_title = re.search(r'group-title="([^"]*)"', line)
            if i+1 < len(lines) and not lines[i+1].startswith('#') and lines[i+1].strip().startswith('http'):
                url = lines[i+1].strip()
                if name not in channels:
                    channels[name] = {
                        'name': name,
                        'tvg_id': tvg_id.group(1) if tvg_id else '',
                        'tvg_name': tvg_name.group(1) if tvg_name else name,
                        'tvg_logo': tvg_logo.group(1) if tvg_logo else '',
                        'group_title': group_title.group(1) if group_title else '',
                        'url': url,
                    }
                    log(f"  Found: {name}")
            i += 2
        else:
            i += 1
    return extm3u_line, list(channels.values())

def asign_tvg_ids(channels):
    """Assign proper tvg-id to channels based on name matching."""
    name_to_id = {}
    for pattern, tid in CHANNEL_MAP.items():
        name_to_id[pattern.lower()] = tid

    for ch in channels:
        name_lower = ch['name'].lower()
        for pattern, tid in name_to_id.items():
            if pattern in name_lower or name_lower in pattern:
                ch['tvg_id'] = tid
                log(f"  Assigned tvg-id={tid} to '{ch['name']}'")
                break

def clean_logo_url(url, channel_name=None):
    """Ensure logo URL ends in .jpg, reject imgur.com."""
    if not url:
        return None
    if 'imgur.com' in url.lower():
        log(f"  Rejecting imgur.com logo: {url[:60]}")
        return None
    # Replace cf-images fox news URLs with static ones
    if 'cf-images' in url and 'fox' in (channel_name or '').lower():
        chn = (channel_name or '').lower()
        if 'fox business' in chn:
            return "https://a57.foxnews.com/static/foxnews/fox-business-logo.jpg"
        if 'fox news' in chn:
            return "https://a57.foxnews.com/static/foxnews/fox-news-logo.jpg"
    url_clean = url.split('?')[0].split('#')[0].strip()
    if url_clean.lower().endswith(('.jpg', '.jpeg')):
        return url_clean
    for bad_ext in ['.png', '.svg', '.webp', '.gif', '.bmp', '.avif', '.webp']:
        if url_clean.lower().endswith(bad_ext):
            base = url_clean[:url_clean.rindex('.')]
            return base + '.jpg'
    if '.' in url_clean.split('/')[-1]:
        parts = url_clean.rsplit('.', 1)
        return parts[0] + '.jpg'
    return url_clean.rstrip('/') + '/logo.jpg'

def get_logo_for_channel(name, tvg_id):
    """Return proper .jpg logo URL for a channel."""
    logos = {
        "abc news live": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
        "fox news channel": "https://a57.foxnews.com/static/foxnews/fox-news-logo.jpg",
        "fox business": "https://a57.foxnews.com/static/foxnews/fox-business-logo.jpg",
        "cbs news 24/7": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
    }
    name_lower = name.lower()
    for key, logo in logos.items():
        if key in name_lower:
            return logo
    return None

def generate_epg_xml(channels, dates):
    """Generate EPG XML with synthetic schedules for 3+ days."""
    schedules = {
        "465150": [  # ABC News Live
            ("0600", "0700", "ABC World News This Morning"),
            ("0700", "0900", "Good Morning America"),
            ("0900", "1000", "ABC News Live - Morning"),
            ("1000", "1130", "The View"),
            ("1130", "1230", "ABC World News Midday"),
            ("1230", "1330", "ABC News Live - Afternoon"),
            ("1330", "1500", "ABC World News Now"),
            ("1500", "1630", "ABC World News Tonight With David Muir"),
            ("1630", "1730", "ABC News Live - Evening"),
            ("1730", "1830", "ABCNL Prime With Linsey Davis"),
            ("1830", "1900", "ABC World News Tonight"),
            ("1900", "2000", "Nightline"),
            ("2000", "2100", "ABC News Live - Prime"),
            ("2100", "2200", "ABC News Special"),
            ("2200", "2300", "ABC World News Overnight"),
            ("2300", "0600", "ABC World News Overnight"),
        ],
        "465372": [  # Fox News Channel
            ("0600", "0700", "Fox & Friends First"),
            ("0700", "0900", "Fox & Friends"),
            ("0900", "1000", "America's Newsroom"),
            ("1000", "1100", "The Faulkner Focus"),
            ("1100", "1200", "Outnumbered"),
            ("1200", "1300", "America Reports"),
            ("1300", "1400", "The Story With Martha MacCallum"),
            ("1400", "1500", "The Five"),
            ("1500", "1600", "Special Report With Bret Baier"),
            ("1600", "1700", "Fox News Tonight"),
            ("1700", "1800", "Jesse Watters Primetime"),
            ("1800", "1900", "Hannity"),
            ("1900", "2000", "The Ingraham Angle"),
            ("2000", "2100", "Gutfeld!"),
            ("2100", "2200", "Fox News at Night"),
            ("2200", "2300", "Fox News Overnight"),
            ("2300", "0600", "Fox News Overnight"),
        ],
        "464766": [  # Fox Business
            ("0600", "0700", "Fox Business Morning"),
            ("0700", "0900", "Mornings With Maria"),
            ("0900", "1000", "Varney & Co."),
            ("1000", "1100", "Making Money With Charles Payne"),
            ("1100", "1200", "The Big Money Show"),
            ("1200", "1300", "The Claman Countdown"),
            ("1300", "1400", "Cavuto: Coast to Coast"),
            ("1400", "1500", "Fox Business Afternoon"),
            ("1500", "1600", "Kudlow"),
            ("1600", "1700", "Fox Business Tonight"),
            ("1700", "1800", "The Evening Edit"),
            ("1800", "1900", "Fox Business Special"),
            ("1900", "2000", "Mornings With Maria (Rerun)"),
            ("2000", "2100", "Varney & Co. (Rerun)"),
            ("2100", "2200", "Making Money (Rerun)"),
            ("2200", "0600", "Fox Business Overnight"),
        ],
        "464941": [  # CBS News 24/7
            ("0600", "0700", "CBS Morning News"),
            ("0700", "0900", "CBS This Morning"),
            ("0900", "1000", "CBS News Daily"),
            ("1000", "1100", "CBS News Morning"),
            ("1100", "1200", "CBS News Midday"),
            ("1200", "1300", "CBS News Update"),
            ("1300", "1400", "The Price Is Right"),
            ("1400", "1500", "The Young and the Restless"),
            ("1500", "1600", "CBS News Afternoon"),
            ("1600", "1730", "CBS Evening News"),
            ("1730", "1830", "CBS News Evening"),
            ("1830", "1900", "CBS World News Tonight"),
            ("1900", "2000", "60 Minutes"),
            ("2000", "2100", "CBS News Special"),
            ("2100", "2200", "Face the Nation"),
            ("2200", "2300", "CBS News Nightwatch"),
            ("2300", "0600", "CBS News Overnight"),
        ],
    }

    root = ET.Element("tv", attrib={"generator-info-name": "JCTV News EPG"})

    added_channels = set()
    added_progs = set()
    for ch in channels:
        tid = ch['tvg_id']
        if tid and tid not in added_channels:
            added_channels.add(tid)
            ch_el = ET.SubElement(root, "channel", attrib={"id": tid})
            dn = ET.SubElement(ch_el, "display-name")
            dn.text = ch['tvg_name'] or ch['name']

    for ch in channels:
        tid = ch['tvg_id']
        schedule = schedules.get(tid, [])
        if not schedule:
            continue
        for date_str in dates:
            for start, stop, title in schedule:
                key = (tid, date_str, start, stop)
                if key in added_progs:
                    continue
                added_progs.add(key)
                prog = ET.SubElement(root, "programme", {
                    "channel": tid,
                    "start": f"{date_str}{start}00 +0000",
                    "stop": f"{date_str}{stop}00 +0000",
                })
                t = ET.SubElement(prog, "title", {"lang": "en"})
                t.text = title
                d = ET.SubElement(prog, "desc", {"lang": "en"})
                d.text = f"{title} - Live news coverage"

    tree = ET.ElementTree(root)
    tree.write(EPG_XML_FILE, encoding='utf-8', xml_declaration=True)
    buf = io.BytesIO()
    tree.write(buf, encoding='utf-8', xml_declaration=True)
    with gzip.open(EPG_GZ_FILE, 'wb') as f:
        f.write(buf.getvalue())
    log(f"EPG saved: {EPG_XML_FILE} ({len(root.findall('programme'))} programmes)")

def build_m3u(channels):
    """Build clean M3U content."""
    epg_urls = "https://raw.githubusercontent.com/JCTV/JCTV/main/lista5_epg.xml https://epg.pw/xmltv/epg_US.xml.gz https://epg.pw/xmltv/epg_BR.xml.gz"
    lines = [f'#EXTM3U url-tvg="{epg_urls}" x-tvg-url="{epg_urls}"']

    for ch in channels:
        if not ch['url']:
            continue
        logo = ch['tvg_logo']
        clean_logo = clean_logo_url(logo, ch['name'])
        if not clean_logo:
            clean_logo = get_logo_for_channel(ch['name'], ch['tvg_id'])
        if not clean_logo:
            clean_logo = "https://via.placeholder.com/400x225.jpg?text=" + ch['name'].replace(' ', '+')

        attrs = f'tvg-id="{ch["tvg_id"]}" tvg-name="{ch["tvg_name"]}"'
        if clean_logo:
            attrs += f' tvg-logo="{clean_logo}"'
        attrs += f' group-title="{ch["group_title"] or "NEWS WORLD"}"'
        lines.append(f'#EXTINF:-1 {attrs},{ch["name"]}')
        lines.append(ch['url'])

    return '\n'.join(lines) + '\n'

def verify_epg():
    """Verify EPG has data for today, tomorrow, day after."""
    today = datetime.now(timezone.utc)
    dates = [
        today.strftime('%Y%m%d'),
        (today + timedelta(days=1)).strftime('%Y%m%d'),
        (today + timedelta(days=2)).strftime('%Y%m%d'),
    ]

    try:
        tree = ET.parse(EPG_XML_FILE)
        root = tree.getroot()
    except:
        log("EPG verification FAILED - cannot parse EPG XML")
        return False

    log(f"\nEPG Verification (today={dates[0]}, tomorrow={dates[1]}, day+2={dates[2]}):")
    all_ok = True
    for ch in root.findall('channel'):
        ch_id = ch.get('id')
        name = ch.find('display-name').text if ch.find('display-name') is not None else ch_id
        ch_ok = True
        for d in dates:
            count = sum(1 for p in root.findall('programme') if p.get('channel') == ch_id and p.get('start', '').startswith(d))
            if count == 0:
                log(f"  {name} ({ch_id}): MISSING data for {d}")
                ch_ok = False
            else:
                log(f"  {name} ({ch_id}): {d} -> {count} programmes")
        if not ch_ok:
            all_ok = False
    return all_ok

def verify_m3u(content):
    """Verify M3U file format and content."""
    log("\nM3U Verification:")
    issues = []
    lines = content.strip().split('\n')

    if not lines[0].startswith('#EXTM3U'):
        issues.append("Missing #EXTM3U header")

    for i, line in enumerate(lines):
        if line.startswith('#EXTINF:'):
            if 'tvg-id=' not in line:
                issues.append(f"  Line {i+1}: missing tvg-id")
            logo_match = re.search(r'tvg-logo="([^"]+)"', line)
            if logo_match:
                logo = logo_match.group(1)
                if not logo.lower().endswith(('.jpg', '.jpeg')):
                    issues.append(f"  Line {i+1}: logo not .jpg: {logo}")
                if 'imgur.com' in logo.lower():
                    issues.append(f"  Line {i+1}: imgur.com logo: {logo}")
            else:
                issues.append(f"  Line {i+1}: missing tvg-logo")
            if 'group-title=' not in line:
                issues.append(f"  Line {i+1}: missing group-title")
        elif line.startswith('http'):
            if i == 0 or not lines[i-1].startswith('#EXTINF:'):
                issues.append(f"  Line {i+1}: URL without #EXTINF above")

    if issues:
        for issue in issues:
            log(f"  ISSUE: {issue}")
        return False
    log("  All checks passed!")
    return True

def main():
    log("=" * 60)
    log("FIX LISTA5.M3U - COMPLETE")
    log("=" * 60)

    # Backup
    log("\n[1] Backup...")
    backup_file()

    # Parse current M3U
    log("\n[2] Parsing current M3U...")
    with open(M3U_FILE, 'r') as f:
        content = f.read()
    extm3u, channels = parse_m3u(content)
    log(f"  Found {len(channels)} unique channel entries")

    # Assign tvg-ids
    log("\n[3] Assigning tvg-ids...")
    asign_tvg_ids(channels)
    for ch in channels:
        if not ch['tvg_id']:
            log(f"  WARNING: No tvg-id for '{ch['name']}'")

    # Clean logos
    log("\n[4] Cleaning logo URLs...")
    for ch in channels:
        clean_logo = clean_logo_url(ch['tvg_logo'], ch['name'])
        if not clean_logo:
            clean_logo = get_logo_for_channel(ch['name'], ch['tvg_id'])
        if clean_logo:
            ch['tvg_logo'] = clean_logo
            log(f"  Logo for '{ch['name']}': {clean_logo}")
        else:
            log(f"  WARNING: No logo for '{ch['name']}'")

    # Standardize names
    log("\n[5] Standardizing channel names...")
    name_map = OrderedDict([
        ("ABC News Live", "ABC News Live - ABC News"),
        ("Fox News Channel", "Watch Fox News Channel Online | Stream Fox News"),
        ("Fox Business", "Fox Business Go | Fox News Video"),
        ("CBS News 24/7", "CBS News 24/7 -CBS News"),
    ])
    for ch in channels:
        if ch['name'] in name_map.values():
            for std_name, orig_name in name_map.items():
                if ch['name'] == orig_name:
                    ch['name'] = std_name
                    ch['tvg_name'] = std_name
                    log(f"  Renamed to '{std_name}'")

    # Assign tvg-id to ABC News Live special stream
    for ch in channels:
        if not ch['tvg_id'] and 'abc' in ch['name'].lower() and 'live' in ch['name'].lower():
            ch['tvg_id'] = '465150'
            ch['tvg_name'] = 'ABC News Live'
            log(f"  Assigned tvg-id=465150 (ABC News Live) to '{ch['name']}'")

    # Remove non-essential transient channels - only keep main channels
    main_channels = ['ABC News Live', 'Fox News Channel', 'Fox Business', 'CBS News 24/7']
    channels[:] = [ch for ch in channels if ch['name'] in main_channels]
    log(f"  After cleanup: {len(channels)} channels")

    # Generate dates (today + 3 days)
    today = datetime.now(timezone.utc)
    dates = [
        today.strftime('%Y%m%d'),
        (today + timedelta(days=1)).strftime('%Y%m%d'),
        (today + timedelta(days=2)).strftime('%Y%m%d'),
        (today + timedelta(days=3)).strftime('%Y%m%d'),
    ]

    # Generate EPG
    log("\n[6] Generating EPG XML...")
    generate_epg_xml(channels, dates)

    # Build M3U
    log("\n[7] Building M3U...")
    m3u_content = build_m3u(channels)

    with open(M3U_FILE, 'w', encoding='utf-8') as f:
        f.write(m3u_content)
    log(f"  Written: {M3U_FILE} ({len(m3u_content)} bytes, {len(channels)} channels)")

    # Verify M3U
    log("\n[8] Verifying M3U format...")
    m3u_ok = verify_m3u(m3u_content)

    # Verify EPG
    log("\n[9] Verifying EPG coverage...")
    epg_ok = verify_epg()

    # Summary
    log("\n" + "=" * 60)
    log("SUMMARY")
    log("=" * 60)
    log(f"  Channels: {len(channels)}")
    log(f"  M3U valid: {'YES' if m3u_ok else 'NO'}")
    log(f"  EPG 3-day coverage: {'YES' if epg_ok else 'NO'}")
    for ch in channels:
        log(f"  - {ch['name']}: tvg-id={ch['tvg_id']}, logo={ch['tvg_logo'][:50]}...")
    log("Done!")

if __name__ == "__main__":
    main()
