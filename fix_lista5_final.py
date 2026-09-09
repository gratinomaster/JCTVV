#!/usr/bin/env python3
"""
Fix lista5.m3u: deduplicate, add EPG, test streams, fix logos, remove broken channels.
"""

import re
import os
import sys
import time
import gzip
import subprocess
import urllib.request
import urllib.error
import ssl
from datetime import datetime, timedelta
from collections import OrderedDict

# Disable SSL verification for testing
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

INPUT_FILE = "lista5.m3u"
OUTPUT_FILE = "lista5.m3u"
BACKUP_FILE = f"lista5.m3u.bak.pre_fix_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

# EPG source URLs (verified working)
EPG_SOURCES = [
    ("epg.pw US", "https://epg.pw/xmltv/epg_US.xml"),
]

# Channel definitions: tvg-id (from epg.pw verified), tvg-name, group, logo, stream_url
CHANNEL_DEFS = {
    "ABC News Live": {
        "tvg_id": "465150",
        "tvg_name": "ABC News Live",
        "group": "NEWS WORLD",
        "logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
        "stream_url": "https://abcnews-livestreams.akamaized.net/out/v1/6a597119dbd5428a82dc11a2f514a1a2/abcn-live-10-cmaf-manifest/abcn-live-10-index.m3u8",
    },
    "Fox Business": {
        "tvg_id": "464766",
        "tvg_name": "Fox Business",
        "group": "NEWS WORLD",
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/c9b2e2eb-7b87-435c-9510-eab2650ff944/8b584585-acf2-4c37-aa07-aaf2d077bb20/1280x720/match/676/380/image.jpg?ve=1&tl=1",
        "stream_url": "https://247preview.foxbusiness.com/hls/live/2020026/fbnv3preview/primary.m3u8",
    },
    "Fox News": {
        "tvg_id": "465372",
        "tvg_name": "Fox News Channel",
        "group": "NEWS WORLD",
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/15de0523-3be4-4a9a-8159-7020114e7036/b6ff623a-26d6-4fd9-8bb8-0856adbf38ce/1280x720/match/676/380/image.jpg?ve=1&tl=1",
        "stream_url": "http://247preview.foxnews.com/hls/live/2020027/fncv3preview/primary.m3u8",
    },
    "CBS News": {
        "tvg_id": "464941",
        "tvg_name": "CBS News",
        "group": "NEWS WORLD",
        "logo": "https://www.cbsnews.com/bundles/cbsnewsvideo/images/cbsn--main-bg.jpg",
        "stream_url": "https://cbsn-us.cbsnstream.cbsnews.com/out/v1/55a8648e8f134e82a470f83d562deeca/master.m3u8",
    },
}

def log(msg):
    print(f"[FIX] {msg}")

def read_m3u(filepath):
    """Read M3U file and parse into channel entries."""
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        lines = f.readlines()
    
    entries = []
    header = lines[0].strip() if lines else "#EXTM3U"
    
    i = 1
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXTINF:'):
            extinf = line
            url = lines[i + 1].strip() if i + 1 < len(lines) else ""
            i += 2
            # Skip any blank lines between entries
            while i < len(lines) and lines[i].strip() == "":
                i += 1
            entries.append((extinf, url))
        else:
            i += 1
    
    return header, entries

def identify_channel(extinf):
    """Identify which channel an EXTINF line represents."""
    extinf_lower = extinf.lower()
    name_match = re.search(r',(.+)$', extinf)
    name = name_match.group(1).strip() if name_match else ""
    
    if 'abc news' in name.lower() or 'good morning america' in name.lower():
        return "ABC News Live", name
    elif 'fox business' in name.lower():
        return "Fox Business", name
    elif 'fox news' in name.lower() or 'watch fox news' in name.lower():
        return "Fox News", name
    elif 'cbs news' in name.lower():
        return "CBS News", name
    return None, name

def deduplicate_channels(entries):
    """Keep only unique channel names, one entry per channel."""
    seen = set()
    kept = []
    for extinf, url in entries:
        channel_key, original_name = identify_channel(extinf)
        if not channel_key or channel_key in seen:
            continue
        seen.add(channel_key)
        kept.append((channel_key, extinf, url, original_name))
    return kept

def build_extinf(channel_key, url):
    """Build a proper EXTINF line with tvg-id, tvg-name, tvg-logo."""
    ch = CHANNEL_DEFS[channel_key]
    return f'#EXTINF:-1 tvg-id="{ch["tvg_id"]}" tvg-name="{ch["tvg_name"]}" tvg-logo="{ch["logo"]}" group-title="{ch["group"]}",{ch["tvg_name"]}'

def test_url(url, timeout=10):
    """Test if a URL is accessible."""
    try:
        req = urllib.request.Request(url, method='HEAD')
        req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)
        return resp.getcode() in (200, 301, 302, 303, 307, 308)
    except:
        try:
            req = urllib.request.Request(url)
            req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
            resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)
            data = resp.read(1024)
            return len(data) > 0
        except:
            return False

def test_stream_url(url, timeout=15):
    """Test if a stream URL works by checking if it returns valid HLS content."""
    try:
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)
        data = resp.read(2048).decode('utf-8', errors='replace')
        # Check if it looks like HLS
        return '#EXTM3U' in data or '#EXT-X-' in data or '.m3u8' in data.lower()
    except:
        return False

def test_logo_url(url, timeout=10):
    """Test if a logo URL returns a valid JPG image."""
    try:
        req = urllib.request.Request(url, method='HEAD')
        req.add_header('User-Agent', 'Mozilla/5.0')
        resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)
        content_type = resp.headers.get('Content-Type', '')
        return resp.getcode() == 200 and ('image' in content_type or 'jpeg' in content_type or 'jpg' in content_type or url.lower().endswith('.jpg'))
    except:
        # Try GET as fallback
        try:
            req = urllib.request.Request(url)
            req.add_header('User-Agent', 'Mozilla/5.0')
            resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)
            data = resp.read(32)
            # Check JPEG magic bytes
            return len(data) >= 3 and data[0] == 0xFF and data[1] == 0xD8
        except:
            return False

def fetch_epg_source(name, url, timeout=30):
    """Download and parse EPG source, check for our channels."""
    log(f"Fetching EPG source: {name} ({url})")
    try:
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'Mozilla/5.0')
        resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)
        data = resp.read()
        
        # Decompress if gzipped
        if url.endswith('.gz') or data[:2] == b'\x1f\x8b':
            data = gzip.decompress(data)
        
        text = data.decode('utf-8', errors='replace')
        
        # Check which channel IDs are present
        found_channels = {}
        for ch_key, ch_def in CHANNEL_DEFS.items():
            tvg_id = ch_def["tvg_id"]
            if tvg_id in text:
                # Find programs for this channel
                pattern = rf'<programme[^>]*channel="{re.escape(tvg_id)}"[^>]*>'
                programs = re.findall(pattern, text)
                found_channels[ch_key] = {
                    "tvg_id": tvg_id,
                    "program_count": len(programs),
                    "found": True
                }
                log(f"  ✓ Found {ch_key} (tvg-id: {tvg_id}) - {len(programs)} programs")
            else:
                # Try alternative IDs
                alt_ids = get_alternative_tvg_ids(ch_key)
                for alt_id in alt_ids:
                    if alt_id in text:
                        pattern = rf'<programme[^>]*channel="{re.escape(alt_id)}"[^>]*>'
                        programs = re.findall(pattern, text)
                        found_channels[ch_key] = {
                            "tvg_id": alt_id,
                            "program_count": len(programs),
                            "found": True,
                            "original_tvg_id": tvg_id
                        }
                        log(f"  ✓ Found {ch_key} as '{alt_id}' - {len(programs)} programs")
                        break
                else:
                    found_channels[ch_key] = {
                        "tvg_id": tvg_id,
                        "program_count": 0,
                        "found": False
                    }
                    log(f"  ✗ NOT found: {ch_key} (tvg-id: {tvg_id})")
        
        return found_channels, text
    except Exception as e:
        log(f"  ✗ Error fetching {name}: {e}")
        return {}, ""

def get_alternative_tvg_ids(channel_key):
    """Get alternative tvg-ids for a channel (used for fallback matching)."""
    alternatives = {
        "ABC News Live": ["465150"],
        "Fox Business": ["464766"],
        "Fox News": ["465372"],
        "CBS News": ["464941"],
    }
    return alternatives.get(channel_key, [])

def check_programs_for_dates(epg_text, tvg_id, dates):
    """Check if a channel has programs for specific dates."""
    results = {}
    for date in dates:
        date_str = date.strftime('%Y%m%d')
        pattern = rf'<programme[^>]*channel="{re.escape(tvg_id)}"[^>]*start="{date_str}'
        matches = re.findall(pattern, epg_text)
        results[date.strftime('%Y-%m-%d')] = len(matches)
    return results

def main():
    log("=== Starting lista5.m3u fix ===")
    
    # Backup
    log(f"Creating backup: {BACKUP_FILE}")
    with open(INPUT_FILE, 'r', encoding='utf-8', errors='replace') as f:
        backup_content = f.read()
    with open(BACKUP_FILE, 'w', encoding='utf-8') as f:
        f.write(backup_content)
    
    # Read and parse
    header, entries = read_m3u(INPUT_FILE)
    log(f"Found {len(entries)} entries in original file")
    
    # Deduplicate
    kept = deduplicate_channels(entries)
    log(f"After dedup: {len(kept)} unique channels")
    
    for channel_key, extinf, url, orig_name in kept:
        log(f"  - {channel_key}: {orig_name}")
    
    # Test stream URLs - use verified working URLs from CHANNEL_DEFS
    log("\n=== Testing stream URLs ===")
    working_channels = []
    for channel_key, extinf, url, orig_name in kept:
        ch = CHANNEL_DEFS[channel_key]
        verified_url = ch["stream_url"]
        log(f"Testing stream: {channel_key} ...")
        if test_stream_url(verified_url, timeout=12):
            log(f"  ✓ {channel_key}: Stream WORKS")
            working_channels.append((channel_key, extinf, verified_url, orig_name))
        else:
            log(f"  ✗ {channel_key}: Stream FAILED - removing")
    
    log(f"\nWorking channels after stream test: {len(working_channels)}/{len(kept)}")
    
    # Test logos
    log("\n=== Testing logo URLs ===")
    for channel_key, extinf, url, orig_name in working_channels:
        ch = CHANNEL_DEFS[channel_key]
        logo_url = ch["logo"]
        log(f"Testing logo: {channel_key} ...")
        if test_logo_url(logo_url, timeout=8):
            log(f"  ✓ Logo OK: {logo_url[:80]}...")
        else:
            log(f"  ✗ Logo FAILED: {logo_url[:80]}...")
            # Try to find alternative logo
            alt_logo = find_alternative_logo(channel_key)
            if alt_logo:
                ch["logo"] = alt_logo
                log(f"  → Using alternative logo: {alt_logo[:80]}...")
    
    # Test EPG sources
    log("\n=== Testing EPG sources ===")
    today = datetime.now()
    dates_to_check = [today, today + timedelta(days=1), today + timedelta(days=2)]
    
    best_epg = None
    best_epg_text = ""
    best_coverage = 0
    
    for name, url in EPG_SOURCES:
        channels_found, epg_text = fetch_epg_source(name, url)
        if not channels_found:
            continue
        
        # Check program dates
        coverage = 0
        for ch_key, info in channels_found.items():
            if info["found"] and ch_key in [w[0] for w in working_channels]:
                tvg_id = info["tvg_id"]
                date_results = check_programs_for_dates(epg_text, tvg_id, dates_to_check)
                log(f"  {ch_key} programs: {date_results}")
                total_programs = sum(date_results.values())
                if total_programs > 0:
                    coverage += 1
        
        if coverage > best_coverage:
            best_coverage = coverage
            best_epg = (name, url)
            best_epg_text = epg_text
            log(f"  → New best EPG source: {name} ({coverage}/{len(working_channels)} channels covered)")
    
    # If best single source doesn't cover all, try combining
    epg_urls_to_use = []
    if best_epg:
        epg_urls_to_use.append(best_epg[1])
        log(f"\nBest EPG source: {best_epg[0]}")
    
    # Always include epg.pw as backup (it's reliable)
    if best_epg and best_epg[0] != "epg.pw US":
        epg_urls_to_use.append("https://epg.pw/xmltv/epg_US.xml")
    
    # Build final M3U
    log("\n=== Building final M3U ===")
    
    # Build header with EPG URL(s)
    epg_attr = ""
    if epg_urls_to_use:
        if len(epg_urls_to_use) == 1:
            epg_attr = f' url-tvg="{epg_urls_to_use[0]}"'
        else:
            epg_attr = f' url-tvg="{" ".join(epg_urls_to_use)}"'
    
    final_lines = [f"#EXTM3U{epg_attr}"]
    
    for channel_key, extinf, url, orig_name in working_channels:
        new_extinf = build_extinf(channel_key, url)
        final_lines.append(new_extinf)
        final_lines.append(url)
    
    # Write output
    log(f"\nWriting {OUTPUT_FILE} with {len(working_channels)} channels")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(final_lines) + '\n')
    
    # Final validation
    log("\n=== Final Validation ===")
    header_final, entries_final = read_m3u(OUTPUT_FILE)
    log(f"Total lines: {len(open(OUTPUT_FILE).readlines())}")
    log(f"Total entries: {len(entries_final)}")
    
    for extinf, url in entries_final:
        # Check tvg-logo exists and is .jpg
        if 'tvg-logo=' not in extinf:
            log(f"  ✗ MISSING tvg-logo: {extinf[:80]}...")
        elif '.jpg' not in extinf:
            log(f"  ✗ tvg-logo not .jpg: {extinf[:80]}...")
        else:
            log(f"  ✓ OK: {extinf[:100]}...")
        
        # Check # before URL line
        if not extinf.startswith('#EXTINF'):
            log(f"  ✗ MISSING # prefix: {extinf[:80]}...")
        
        # Check for imgur
        if 'imgur.com' in extinf:
            log(f"  ✗ Contains imgur.com: {extinf[:80]}...")
        
        # Check tvg-id exists
        if 'tvg-id=' not in extinf:
            log(f"  ✗ MISSING tvg-id: {extinf[:80]}...")
    
    log("\n=== DONE ===")
    log(f"Backup saved as: {BACKUP_FILE}")
    log(f"Fixed file: {OUTPUT_FILE}")

def find_alternative_logo(channel_key):
    """Find an alternative .jpg logo for a channel."""
    alternatives = {
        "ABC News Live": [
            "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
            "https://keyframe-cdn.abcnews.com/streamprovider10.jpg",
            "https://s.abcnews.com/images/Live/abc_news_live-abc-ml-250210_1739199021469_hpMain_16x9_608.jpg",
        ],
        "Fox Business": [
            "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/c9b2e2eb-7b87-435c-9510-eab2650ff944/8b584585-acf2-4c37-aa07-aaf2d077bb20/1280x720/match/676/380/image.jpg",
        ],
        "Fox News": [
            "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/15de0523-3be4-4a9a-8159-7020114e7036/b6ff623a-26d6-4fd9-8bb8-0856adbf38ce/1280x720/match/676/380/image.jpg",
        ],
        "CBS News": [
            "https://www.cbsnews.com/bundles/cbsnewsvideo/images/cbsn--main-bg.jpg",
        ],
    }
    for logo in alternatives.get(channel_key, []):
        if test_logo_url(logo, timeout=8):
            return logo
    return None

if __name__ == "__main__":
    main()
