#!/usr/bin/env python3
"""
Fix lista5.m3u: add EPG, deduplicate, test streams, fix logos
"""
import os
import re
import subprocess
import sys
import time
from datetime import datetime

M3U_FILE = "lista5.m3u"
BACKUP_FILE = f"lista5.m3u.bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"

# EPG channel ID mapping (from epg.pw XMLTV US)
EPG_IDS = {
    "ABC News Live": "465150",
    "CBS News 24/7": "464941",
    "CBS News National": "464941",
    "Fox News Channel": "465372",
    "Fox News": "465372",
    "Fox Business": "464766",
}

# Better logos (not imgur, .jpg format)
LOGOS = {
    "ABC News Live": "https://keyframe-cdn.abcnews.com/streamprovider5.jpg",
    "CBS News 24/7": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
    "Fox News Channel": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/15de0523-3be4-4a9a-8159-7020114e7036/b6ff623a-26d6-4fd9-8bb8-0856adbf38ce/1280x720/match/676/380/image.jpg",
    "Fox Business": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/c9b2e2eb-7b87-435c-9510-eab2650ff944/8b584585-acf2-4c37-aa07-aaf2d077bb20/1280x720/match/676/380/image.jpg",
}

# Stream URL quality priority (lower = better, keep best working)
STREAM_PRIORITY = {
    # ABC News Live streams - prefer main manifest, then highest quality
    "abcn-live-05-index.m3u8": 1,
    "abcn-live-05-index_4_0.m3u8": 2,
    "abcn-live-05-index_3.m3u8": 3,
    "abcn-live-10-index.m3u8": 1,
    "abcn-live-10-index_4_0.m3u8": 2,
    "abcn-live-10-index_3.m3u8": 3,
    # Disney/ABC streams - prefer main manifest
    "ctr-all-hdri-sliding.m3u8": 1,
    "1700_hdri_slide.m3u8": 2,
    "2400_hdri_slide.m3u8": 2,
    "128_slide.m3u8": 4,
    "64_slide.m3u8": 5,
    # CBS streams - prefer main manifest
    "master.m3u8": 1,
    # Fox streams
    "master.m3u8": 1,
}


def test_stream_url(url, timeout=10):
    """Test if a stream URL is accessible and returns valid HLS content."""
    try:
        result = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
             "-L", "--max-time", str(timeout), url],
            capture_output=True, text=True, timeout=timeout + 5
        )
        http_code = result.stdout.strip()
        return http_code in ("200", "302", "301", "206")
    except Exception:
        return False


def test_stream_hls(url, timeout=15):
    """Test if URL is a valid HLS stream by checking for m3u8 content."""
    try:
        result = subprocess.run(
            ["curl", "-s", "-L", "--max-time", str(timeout), url],
            capture_output=True, text=True, timeout=timeout + 5
        )
        content = result.stdout[:2000]
        return "#EXTM3U" in content or "#EXT-X-" in content
    except Exception:
        return False


def get_channel_name(extinf_line):
    """Extract channel name from EXTINF line."""
    # Channel name is after the last comma
    match = re.search(r',\s*(.+)$', extinf_line)
    if match:
        return match.group(1).strip()
    return "Unknown"


def normalize_channel_name(name):
    """Normalize channel name for deduplication."""
    # Remove quality indicators and common suffixes
    name = re.sub(r'\s*\|\s*Watch.*$', '', name)
    name = re.sub(r'\s*\|\s*Stream.*$', '', name)
    name = re.sub(r'\s*-\s*ABC News$', '', name)
    name = re.sub(r'\s*24/7.*$', '', name)
    name = re.sub(r'\s*First.*$', '', name)
    return name.strip()


def get_stream_priority(url):
    """Get priority for a stream URL (lower = better)."""
    for pattern, priority in STREAM_PRIORITY.items():
        if pattern in url:
            return priority
    return 99


def parse_m3u(filepath):
    """Parse M3U file into list of (extinf_line, url_line) tuples."""
    channels = []
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    i = 0
    header = ""
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXTM3U'):
            header = line
            i += 1
            continue
        if line.startswith('#EXTINF:'):
            extinf = line
            # Next non-empty line should be URL
            i += 1
            while i < len(lines) and lines[i].strip() == '':
                i += 1
            if i < len(lines) and not lines[i].strip().startswith('#'):
                url = lines[i].strip()
                channels.append((extinf, url))
        i += 1

    return header, channels


def main():
    print(f"=== Fixing {M3U_FILE} ===")
    print(f"Backup: {BACKUP_FILE}")

    # Backup
    if os.path.exists(M3U_FILE):
        subprocess.run(["cp", M3U_FILE, BACKUP_FILE])
        print(f"Backup created: {BACKUP_FILE}")

    # Parse
    header, channels = parse_m3u(M3U_FILE)
    print(f"\nFound {len(channels)} total entries")

    # Group by normalized channel name
    grouped = {}
    for extinf, url in channels:
        name = get_channel_name(extinf)
        norm_name = normalize_channel_name(name)
        if norm_name not in grouped:
            grouped[norm_name] = []
        grouped[norm_name].append((extinf, url, name))

    print(f"Unique channels: {len(grouped)}")
    for name, entries in grouped.items():
        print(f"  - {name}: {len(entries)} variants")

    # Test streams and keep best working one per channel
    fixed_channels = []
    for norm_name, entries in grouped.items():
        print(f"\nTesting {norm_name}...")

        # Sort by priority
        entries_with_priority = []
        for extinf, url, name in entries:
            priority = get_stream_priority(url)
            entries_with_priority.append((priority, extinf, url, name))

        entries_with_priority.sort(key=lambda x: x[0])

        best_working = None
        for priority, extinf, url, name in entries_with_priority:
            is_valid = test_stream_hls(url)
            status = "OK" if is_valid else "FAIL"
            print(f"  [{status}] (p{priority}) {url[:80]}...")

            if is_valid and best_working is None:
                best_working = (extinf, url, name)
                # Don't break - test all to report status

        if best_working:
            print(f"  => Keeping: {best_working[2]}")
            fixed_channels.append(best_working)
        else:
            print(f"  => NO WORKING STREAM for {norm_name}!")

    # Now build the fixed M3U
    print(f"\n=== Building fixed M3U ===")

    # EPG URL
    epg_url = "https://epg.pw/xmltv/epg_US.xml"

    # New header with url-tvg
    new_header = f'#EXTM3U url-tvg="{epg_url}" x-tvg-url="{epg_url}"'

    # Write fixed file
    with open(M3U_FILE, 'w', encoding='utf-8') as f:
        f.write(new_header + '\n')

        for extinf, url, name in fixed_channels:
            # Get EPG ID
            epg_id = None
            for key, val in EPG_IDS.items():
                if key.lower() in name.lower():
                    epg_id = val
                    break

            # Get logo
            logo = None
            for key, val in LOGOS.items():
                if key.lower() in name.lower():
                    logo = val
                    break

            if logo is None:
                # Extract from original extinf
                logo_match = re.search(r'tvg-logo="([^"]+)"', extinf)
                if logo_match:
                    logo = logo_match.group(1)
                    # Remove imgur links
                    if 'imgur.com' in logo:
                        logo = None

            if logo is None:
                logo = ""

            # Ensure .jpg
            if logo and not logo.lower().endswith('.jpg'):
                # Try to fix common issues
                if '.png' in logo:
                    logo = logo.replace('.png', '.jpg')
                elif '.jpeg' in logo:
                    logo = logo.replace('.jpeg', '.jpg')
                elif '?' in logo:
                    logo = logo.split('?')[0] + '.jpg'
                elif not '.' in logo.split('/')[-1]:
                    logo = logo + '.jpg'

            # Build new EXTINF
            # Extract group-title
            group_match = re.search(r'group-title="([^"]*)"', extinf)
            group = group_match.group(1) if group_match else "NEWS WORLD"

            # Build clean EXTINF with tvg-id
            if epg_id:
                new_extinf = f'#EXTINF:-1 tvg-id="{epg_id}" tvg-logo="{logo}" group-title="{group}",{name}'
            else:
                new_extinf = f'#EXTINF:-1 tvg-logo="{logo}" group-title="{group}",{name}'

            f.write(new_extinf + '\n')
            f.write(url + '\n')

    print(f"\nFixed file written: {M3U_FILE}")
    print(f"Total channels: {len(fixed_channels)}")

    # Verify
    print("\n=== Verification ===")
    header2, channels2 = parse_m3u(M3U_FILE)
    print(f"Header: {header2[:100]}...")
    print(f"Channels: {len(channels2)}")

    for extinf, url in channels2:
        name = get_channel_name(extinf)
        has_tvg_id = 'tvg-id=' in extinf
        has_logo = 'tvg-logo=' in extinf
        logo_val = re.search(r'tvg-logo="([^"]*)"', extinf)
        logo = logo_val.group(1) if logo_val else "MISSING"
        is_jpg = logo.endswith('.jpg') if logo else False
        is_imgur = 'imgur.com' in logo if logo else False

        print(f"  {name}")
        print(f"    tvg-id: {'OK' if has_tvg_id else 'MISSING'}")
        print(f"    logo: {'OK (.jpg)' if is_jpg else 'NOT JPG'} {logo[:60]}")
        if is_imgur:
            print(f"    WARNING: imgur.com logo detected!")

    print("\nDone!")


if __name__ == "__main__":
    main()
