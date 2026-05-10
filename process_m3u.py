#!/usr/bin/env python3
"""
Process lista5.m3u:
- Remove duplicate channels (keep best quality stream per channel)
- Add tvg-id and tvg-name for EPG matching
- Add EPG URL sources to header
- Fix tvg-logo to .jpg
- Ensure every URL has #EXTINF above it
- Test URLs with HTTP check
- Test EPG data freshness
"""
import re
import sys
import subprocess
import gzip
import io
import xml.etree.ElementTree as ET
from collections import OrderedDict
from urllib.parse import urlparse
from datetime import datetime, timezone, timedelta

INPUT_FILE = "lista5.m3u"
OUTPUT_FILE = "lista5.m3u"
MAX_RETENTION_PER_CHANNEL = 1

# EPG sources - multiple for better coverage
EPG_SOURCES = [
    ("https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz", "epgshare01 US"),
    ("https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.xml.gz", "epgshare01 US Locals"),
]

# Channel mapping: channel name keywords -> tvg-id (from EPG source)
CHANNEL_EPG_MAP = [
    {
        "keywords": ["abc news live"],
        "tvg_id": "ABC.News.Live.us2",
        "tvg_name": "ABC News Live",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5c/ABC_News_Live_logo.svg/1200px-ABC_News_Live_logo.svg.jpg",
    },
    {
        "keywords": ["fox business"],
        "tvg_id": "Fox.Business.HD.us2",
        "tvg_name": "Fox Business",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0d/Fox_Business_logo.svg/1200px-Fox_Business_logo.svg.jpg",
    },
    {
        "keywords": ["fox news"],
        "tvg_id": "Fox.News.Channel.HD.us2",
        "tvg_name": "Fox News Channel",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/67/Fox_News_Channel_logo.svg/1200px-Fox_News_Channel_logo.svg.jpg",
    },
    {
        "keywords": ["cbs news"],
        "tvg_id": "CBS.News.National.Stream.us2",
        "tvg_name": "CBS News 24/7",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/9e/CBS_News_logo_2024.svg/1200px-CBS_News_logo_2024.svg.jpg",
    },
]

def get_channel_info(channel_name):
    """Find EPG info for a channel based on name keywords."""
    name_lower = channel_name.lower()
    for entry in CHANNEL_EPG_MAP:
        if any(kw in name_lower for kw in entry["keywords"]):
            return entry
    return None

def parse_m3u(filepath):
    """Parse M3U file, return list of (extinf_line, url) tuples."""
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    channels = []
    current_extinf = None
    header_lines = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith('#EXTM3U'):
            header_lines.append(line)
        elif stripped.startswith('#EXTINF:'):
            current_extinf = stripped
        elif stripped.startswith('#') and current_extinf is None:
            # Other header/comment lines
            header_lines.append(line)
        elif stripped and not stripped.startswith('#') and current_extinf:
            # URL line
            channels.append((current_extinf, stripped))
            current_extinf = None
        elif stripped.startswith('#') and current_extinf:
            # Comment after EXTINF but before URL - keep it
            pass
        else:
            if current_extinf is None:
                header_lines.append(line)

    # Handle case where last EXTINF has no URL
    return header_lines, channels

def extract_attrs(extinf_line):
    """Extract key=value attributes from EXTINF line."""
    # Remove '#EXTINF:-1 ' prefix
    content = re.sub(r'^#EXTINF:-1\s*', '', extinf_line)
    attrs = {}
    # Find all tvg-xxx="..." patterns
    for match in re.finditer(r'(\w+(?:-\w+)*)="([^"]*)"', content):
        attrs[match.group(1)] = match.group(2)
    # Get channel name (after all attributes)
    name_match = re.search(r'"[^"]*"\s*,\s*(.+)$', content)
    if name_match:
        attrs['name'] = name_match.group(1).strip()
    else:
        # Fallback: if no comma with quoted value
        parts = content.rsplit(',', 1)
        if len(parts) > 1:
            attrs['name'] = parts[-1].strip()
        else:
            attrs['name'] = content.strip()
    return attrs

def build_extinf(attrs):
    """Build EXTINF line from attributes dict."""
    name = attrs.pop('name', '')
    parts = ['#EXTINF:-1']
    for key in sorted(attrs.keys()):
        val = attrs[key]
        if val:
            parts.append(f'{key}="{val}"')
    parts.append(f',{name}')
    return ' '.join(parts)

def normalize_logo_url(url):
    """Ensure logo URL ends with .jpg. If it doesn't, try to convert."""
    if not url:
        return url
    parsed = urlparse(url)
    path = parsed.path.lower()
    # If already .jpg, return as-is
    if path.endswith('.jpg') or path.endswith('.jpeg'):
        return url
    # If .png, .webp, etc - try to find a .jpg version
    # Strip extension and add .jpg
    if any(path.endswith(ext) for ext in ['.png', '.webp', '.gif', '.svg', '.bmp']):
        # Replace extension with .jpg
        base = re.sub(r'\.[a-zA-Z]+$', '', url)
        return base + '.jpg'
    # Also check if there's a non-standard extension or no extension
    has_known_ext = any(path.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.svg'])
    if not has_known_ext:
        # Check if URL has an image path
        if any(word in url.lower() for word in ['image', 'logo', 'icon', 'jpg', 'jpeg', 'png']):
            return url + '.jpg'
    return url

def is_likely_logo_jpg(url):
    """Check if URL looks like it could serve a JPG."""
    if not url:
        return False
    path = urlparse(url).path.lower()
    return path.endswith('.jpg') or path.endswith('.jpeg')

def test_url(url, timeout=10):
    """Test if URL is accessible. Returns (success, status_code, error_msg)."""
    try:
        result = subprocess.run(
            ['curl', '-s', '-o', '/dev/null', '-w', '%{http_code}', '--max-time', str(timeout), url],
            capture_output=True, text=True, timeout=timeout + 5
        )
        code = result.stdout.strip()
        if code and code[0] in ('2', '3'):
            return True, code, None
        return False, code, f"HTTP {code}"
    except subprocess.TimeoutExpired:
        return False, None, "Timeout"
    except Exception as e:
        return False, None, str(e)

def test_epg_url(epg_url, timeout=30):
    """Test EPG URL and check if it has recent program data."""
    try:
        # Download the gzipped EPG
        result = subprocess.run(
            ['curl', '-s', '--max-time', str(timeout), epg_url],
            capture_output=True, timeout=timeout + 10
        )
        if result.returncode != 0 or len(result.stdout) == 0:
            return False, "Failed to download EPG"

        # Try to decompress and parse
        try:
            with gzip.GzipFile(fileobj=io.BytesIO(result.stdout)) as f:
                xml_content = f.read()
        except:
            xml_content = result.stdout

        # Parse XML
        root = ET.fromstring(xml_content)
        now = datetime.now(timezone.utc)
        today = now.date()
        tomorrow = today + timedelta(days=1)
        day_after = today + timedelta(days=2)

        # Count programmes per day
        dates_found = set()
        total_progs = 0
        for programme in root.findall('programme'):
            start_str = programme.get('start', '')
            if start_str:
                try:
                    # XMLTV format: 20240510000000 +0000
                    dt = datetime.strptime(start_str[:14], '%Y%m%d%H%M%S')
                    dates_found.add(dt.date())
                    total_progs += 1
                except:
                    pass

        has_today = today in dates_found
        has_tomorrow = tomorrow in dates_found
        has_day_after = day_after in dates_found

        return True, {
            'total_programmes': total_progs,
            'dates_found': sorted(dates_found),
            'has_today': has_today,
            'has_tomorrow': has_tomorrow,
            'has_day_after': has_day_after,
            'unique_channels': len(set(p.get('channel', '') for p in root.findall('programme'))),
        }
    except Exception as e:
        return False, str(e)

def check_malware_url(url, timeout=15):
    """Basic URL safety check - verify URL format, check against known bad patterns, HTTP test."""
    issues = []
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        issues.append("Invalid URL format")
    # Check against imgur.com (user doesn't like it)
    if 'imgur.com' in parsed.netloc:
        issues.append("Uses imgur.com (not allowed)")
    # Check for obviously suspicious patterns
    suspicious_patterns = [r'\.exe$', r'\.dll$', r'\.scr$', r'\.bat$', r'\.vbs$', r'\.ps1$']
    for pat in suspicious_patterns:
        if re.search(pat, parsed.path, re.I):
            issues.append(f"Suspicious file extension in URL")
    # HTTP status check
    success, code, err = test_url(url, timeout)
    if not success:
        issues.append(f"URL not accessible: {err}")
    return issues

def main():
    print("=" * 60)
    print("PROCESSING lista5.m3u")
    print("=" * 60)

    # Step 1: Parse M3U
    print("\n[1] Parsing M3U file...")
    header_lines, channels = parse_m3u(INPUT_FILE)
    print(f"  Found {len(channels)} entries in file")

    # Step 2: Group by channel name and remove duplicates
    print("\n[2] Grouping channels and removing duplicates...")
    unique_channels = OrderedDict()
    for extinf, url in channels:
        attrs = extract_attrs(extinf)
        name = attrs.get('name', 'Unknown')

        # Determine group and simpler name for dedup
        group = attrs.get('group-title', 'General')
        # Normalize name for dedup - remove quality indicators
        dedup_key = re.sub(r'\s*-\s*\d+[kK]?\s*$', '', name).strip()

        if dedup_key not in unique_channels:
            # For ABC News, prefer the higher quality links (like cmaf-cenc-ctr-2400K)
            unique_channels[dedup_key] = (extinf, url, name, dedup_key, group)
        else:
            # Keep the one with better quality (higher bitrate in URL)
            old_extinf, old_url, old_name, old_key, old_group = unique_channels[dedup_key]
            # Prefer URLs with 2400K or higher quality indicators
            def quality_score(u):
                s = 0
                if '2400' in u or 'hdri' in u.lower():
                    s += 10
                if '1700' in u:
                    s += 5
                if '128' in u:
                    s += 1
                if '64' in u:
                    s -= 1
                return s
            if quality_score(url) > quality_score(old_url):
                unique_channels[dedup_key] = (extinf, url, name, dedup_key, group)

    print(f"  Unique channels: {len(unique_channels)} (removed {len(channels) - len(unique_channels)} duplicates)")

    # Step 3: Test URLs and check safety
    print("\n[3] Testing URL accessibility and safety...")
    working_channels = OrderedDict()
    for ch_key, (extinf, url, name, _, group) in unique_channels.items():
        attrs = extract_attrs(extinf)
        print(f"  Testing: {name[:50]}...", end=" ")
        sys.stdout.flush()

        # Safety check
        safety_issues = check_malware_url(url, timeout=8)
        
        # URL accessibility test
        success, code, err = test_url(url, timeout=8)
        
        if not success:
            print(f"FAILED (HTTP {code or err})")
            ch_info = get_channel_info(name)
            if safety_issues:
                print(f"    Safety issues: {'; '.join(safety_issues)}")
            # Still keep the channel, but note the issue
            working_channels[ch_key] = (extinf, url, name, group, safety_issues, False)
        else:
            print(f"OK (HTTP {code})")
            if safety_issues:
                print(f"    Warning: {'; '.join(safety_issues)}")
            working_channels[ch_key] = (extinf, url, name, group, safety_issues, True)

    # Step 4: Enhance with EPG info and fix logos
    print("\n[4] Adding EPG info and fixing logos...")
    m3u_header = '#EXTM3U'
    for epg_url, epg_name in EPG_SOURCES:
        m3u_header += f' x-tvg-url="{epg_url}"'
    
    output_lines = [m3u_header + '\n']
    
    for ch_key, (orig_extinf, url, name, group, safety_issues, working) in working_channels.items():
        try:
            attrs = extract_attrs(orig_extinf)
        except:
            attrs = {'name': name}
        
        # Get EPG mapping
        ch_info = get_channel_info(name)
        if ch_info:
            attrs['tvg-id'] = ch_info['tvg_id']
            attrs['tvg-name'] = ch_info['tvg_name']
            # Set logo
            if not attrs.get('tvg-logo') or not is_likely_logo_jpg(attrs.get('tvg-logo', '')):
                attrs['tvg-logo'] = ch_info['logo']
        else:
            # Try to set logo even without EPG match
            if not attrs.get('tvg-logo'):
                attrs['tvg-logo'] = ''  # Will use default
        
        # Normalize logo URL to .jpg
        if attrs.get('tvg-logo'):
            attrs['tvg-logo'] = normalize_logo_url(attrs['tvg-logo'])
        
        # Remove imgur.com logos
        if attrs.get('tvg-logo') and 'imgur.com' in attrs['tvg-logo']:
            del attrs['tvg-logo']
        
        attrs['group-title'] = group
        
        new_extinf = build_extinf(attrs)
        output_lines.append(new_extinf + '\n')
        output_lines.append(url + '\n')

    # Step 5: Write output
    print(f"\n[5] Writing {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.writelines(output_lines)
    print(f"  Written {len(working_channels)} channels")

    # Step 6: Test EPGs
    print("\n[6] Testing EPG sources...")
    epg_results = {}
    for epg_url, epg_name in EPG_SOURCES:
        print(f"\n  Testing EPG: {epg_name}")
        print(f"    URL: {epg_url}")
        success, result = test_epg_url(epg_url, timeout=45)
        if success:
            print(f"    OK - {result['total_programmes']} programmes, {result['unique_channels']} channels")
            print(f"    Dates found: {result['dates_found'][:5]}...")
            print(f"    Today: {'YES' if result['has_today'] else 'NO'}")
            print(f"    Tomorrow: {'YES' if result['has_tomorrow'] else 'NO'}")
            print(f"    Day after: {'YES' if result['has_day_after'] else 'NO'}")
            epg_results[epg_name] = result
        else:
            print(f"    FAILED: {result}")
            epg_results[epg_name] = None

    # Step 7: Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Original entries: {len(channels)}")
    print(f"Unique channels kept: {len(working_channels)}")
    working_count = sum(1 for v in working_channels.values() if v[5])
    failed_count = sum(1 for v in working_channels.values() if not v[5])
    print(f"URLs accessible: {working_count}")
    print(f"URLs failed: {failed_count}")
    
    channels_with_epg = sum(1 for v in working_channels.values() if get_channel_info(v[2]))
    print(f"Channels with EPG mapping: {channels_with_epg}")
    
    for epg_name, result in epg_results.items():
        if result:
            print(f"  EPG '{epg_name}': OK ({result['total_programmes']} progs, today={result['has_today']}, tomorrow={result['has_tomorrow']}, day after={result['has_day_after']})")
        else:
            print(f"  EPG '{epg_name}': FAILED")
    
    print("\nDone!")

if __name__ == '__main__':
    main()
