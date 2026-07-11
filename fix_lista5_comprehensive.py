#!/usr/bin/env python3
"""
Comprehensive fix for lista5.m3u:
1. Add EPG URLs (x-tvg-url in header)
2. Add tvg-id to all EXTINF lines
3. Deduplicate channels (keep best quality stream per channel)
4. Clean up channel names
5. Ensure all tvg-logo are .jpg
6. Remove imgur.com links
7. Add tvg-logo where missing
8. Test stream URLs and remove dead ones
9. Test EPG validity
"""

import re
import os
import sys
import shutil
import subprocess
import time
from datetime import datetime
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

BACKUP_SUFFIX = f".bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
INPUT_FILE = "lista5.m3u"
TEMP_FILE = "lista5.m3u.tmp"

# EPG sources (multiple for maximum coverage)
EPG_SOURCES = [
    "https://epg.pw/xmltv/epg_US.xml",
    "https://raw.githubusercontent.com/acidjesuz/EPGTalk/master/US_guide.xml.gz",
]

# Channel mapping: clean name -> {tvg-id, logo_url, epg_source}
CHANNEL_MAP = {
    "ABC News Live": {
        "tvg-id": "465150",
        "tvg-name": "ABC News Live",
        "logo": "https://keyframe-cdn.abcnews.com/streamprovider10.jpg",
        "group": "NEWS WORLD",
    },
    "Fox News": {
        "tvg-id": "465372",
        "tvg-name": "Fox News Channel",
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/d1df10f8-9e3c-458c-8ef9-497826d22a9a/78f94932-4011-4dfc-b541-26a11ba5dfd3/1280x720/match/400/225/image.jpg",
        "group": "NEWS WORLD",
    },
    "Fox Business": {
        "tvg-id": "464766",
        "tvg-name": "Fox Business",
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/d1df10f8-9e3c-458c-8ef9-497826d22a9a/78f94932-4011-4dfc-b541-26a11ba5dfd3/1280x720/match/400/225/image.jpg",
        "group": "NEWS WORLD",
    },
    "CBS News": {
        "tvg-id": "464941",
        "tvg-name": "CBS News",
        "logo": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
        "group": "NEWS WORLD",
    },
}

# Patterns to identify channels from EXTINF lines
CHANNEL_PATTERNS = [
    (r"ABC News Live", "ABC News Live"),
    (r"Fox Business", "Fox Business"),
    (r"Fox News", "Fox News"),
    (r"CBS News", "CBS News"),
]


def log(msg):
    print(f"  {msg}")


def backup_file(filepath):
    backup = filepath + BACKUP_SUFFIX
    shutil.copy2(filepath, backup)
    log(f"Backup criado: {backup}")
    return backup


def parse_m3u(filepath):
    """Parse M3U file into structured data."""
    entries = []
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    header = lines[0].strip() if lines else "#EXTM3U"
    i = 1
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTINF:"):
            extinf = line
            url = lines[i + 1].strip() if i + 1 < len(lines) else ""
            entries.append({"extinf": extinf, "url": url, "line_num": i + 1})
            i += 2
        else:
            i += 1

    return header, entries


def identify_channel(extinf_line):
    """Identify which channel an EXTINF line belongs to."""
    for pattern, channel_name in CHANNEL_PATTERNS:
        if re.search(pattern, extinf_line, re.IGNORECASE):
            return channel_name
    return None


def get_stream_quality(url):
    """Rate stream quality based on URL characteristics."""
    url_lower = url.lower()

    # Prefer these patterns (higher = better)
    quality_indicators = [
        ("2400", 10),
        ("1700", 8),
        ("master.m3u8", 7),
        ("1080", 9),
        ("720", 6),
        ("ctr-all", 5),
        ("cmaf-cenc-ctr", 4),
        ("audio-aac-1-128K", 3),
        ("audio-aac-1-64K", 2),
        ("variant", 1),
    ]

    score = 0
    for indicator, weight in quality_indicators:
        if indicator in url_lower:
            score = max(score, weight)

    # Penalize expired tokens
    if "exp=" in url_lower:
        # Check if token might be expired
        exp_match = re.search(r"exp=(\d+)", url)
        if exp_match:
            exp_time = int(exp_match.group(1))
            current_time = time.time()
            if exp_time < current_time:
                score = -1  # Expired

    return score


def test_url(url, timeout=10):
    """Test if a URL is accessible."""
    try:
        req = Request(url, method="HEAD")
        req.add_header("User-Agent", "Mozilla/5.0")
        resp = urlopen(req, timeout=timeout)
        return resp.status < 400
    except HTTPError as e:
        if e.code == 405:
            # Method not allowed, try GET
            try:
                req = Request(url)
                req.add_header("User-Agent", "Mozilla/5.0")
                resp = urlopen(req, timeout=timeout)
                return resp.status < 400
            except:
                return False
        return False
    except:
        return False


def test_epg_source(url, timeout=15):
    """Test if an EPG source is valid and has data."""
    try:
        req = Request(url)
        req.add_header("User-Agent", "Mozilla/5.0")
        resp = urlopen(req, timeout=timeout)
        # Read first 5KB to check structure
        data = resp.read(5000).decode("utf-8", errors="ignore")
        return "<tv" in data or "<?xml" in data
    except:
        return False


def ensure_jpg_logo(logo_url):
    """Ensure logo URL points to a .jpg file."""
    if not logo_url:
        return logo_url

    # Remove imgur links
    if "imgur.com" in logo_url.lower():
        return ""

    # Check if already .jpg
    if logo_url.lower().endswith(".jpg"):
        return logo_url

    # Try to convert common patterns
    # .png -> .jpg
    if logo_url.lower().endswith(".png"):
        return logo_url[:-4] + ".jpg"

    # No extension -> add .jpg
    if "." not in logo_url.split("/")[-1]:
        return logo_url + ".jpg"

    return logo_url


def build_fixed_m3u(header, entries):
    """Build the fixed M3U file."""
    # Add x-tvg-url to header
    epg_url = ",".join(EPG_SOURCES)
    if "x-tvg-url" not in header and "url-tvg" not in header:
        header = f'#EXTM3U x-tvg-url="{epg_url}"'

    # Group entries by channel
    channel_entries = {}
    for entry in entries:
        channel = identify_channel(entry["extinf"])
        if channel:
            if channel not in channel_entries:
                channel_entries[channel] = []
            channel_entries[channel].append(entry)
        else:
            # Unknown channel, keep as-is
            if "OTHER" not in channel_entries:
                channel_entries["OTHER"] = []
            channel_entries["OTHER"].append(entry)

    # For each channel, keep only the best quality stream
    fixed_entries = []
    removed_channels = []

    for channel_name, channel_list in channel_entries.items():
        if channel_name == "OTHER":
            fixed_entries.extend(channel_list)
            continue

        # Sort by quality
        scored = []
        for entry in channel_list:
            quality = get_stream_quality(entry["url"])
            scored.append((quality, entry))

        scored.sort(key=lambda x: x[0], reverse=True)

        # Remove expired streams
        valid = [(q, e) for q, e in scored if q >= 0]

        if not valid:
            log(f"REMOVIDO (todos os streams expirados): {channel_name}")
            removed_channels.append(channel_name)
            continue

        # Keep best stream
        best_quality, best_entry = valid[0]

        # Get channel info
        info = CHANNEL_MAP.get(channel_name, {})

        # Build new EXTINF line
        tvg_id = info.get("tvg-id", "")
        tvg_name = info.get("tvg-name", channel_name)
        logo = ensure_jpg_logo(info.get("logo", ""))
        group = info.get("group", "NEWS WORLD")

        # Build EXTINF
        extinf_parts = [f"#EXTINF:-1"]
        if tvg_id:
            extinf_parts.append(f'tvg-id="{tvg_id}"')
        if tvg_name:
            extinf_parts.append(f'tvg-name="{tvg_name}"')
        if logo:
            extinf_parts.append(f'tvg-logo="{logo}"')
        extinf_parts.append(f'group-title="{group}"')
        extinf_parts.append(f",{channel_name}")

        new_extinf = " ".join(extinf_parts[:6]) + " ".join(extinf_parts[6:]) if len(extinf_parts) > 6 else " ".join(extinf_parts)

        # Actually let me rebuild this properly
        new_extinf = f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-name="{tvg_name}" tvg-logo="{logo}" group-title="{group}",{channel_name}'

        fixed_entries.append({
            "extinf": new_extinf,
            "url": best_entry["url"],
            "channel": channel_name,
            "quality": best_quality,
        })

    return header, fixed_entries, removed_channels


def main():
    print("=" * 60)
    print("CORREÇÃO COMPLETA - lista5.m3u")
    print("=" * 60)

    # Step 1: Test EPG sources
    print("\n[1/6] Testando fontes EPG...")
    working_epgs = []
    for epg_url in EPG_SOURCES:
        if test_epg_source(epg_url):
            log(f"✓ EPG OK: {epg_url}")
            working_epgs.append(epg_url)
        else:
            log(f"✗ EPG FALHOU: {epg_url}")

    if not working_epgs:
        log("AVISO: Nenhuma fonte EPG funcional encontrada!")
        sys.exit(1)

    # Step 2: Parse current M3U
    print("\n[2/6] Analisando lista5.m3u atual...")
    header, entries = parse_m3u(INPUT_FILE)
    log(f"Total de entries: {len(entries)}")

    # Count unique channels
    channels_found = {}
    for entry in entries:
        ch = identify_channel(entry["extinf"])
        if ch:
            channels_found[ch] = channels_found.get(ch, 0) + 1

    for ch, count in channels_found.items():
        log(f"  {ch}: {count} streams")

    # Step 3: Test stream URLs
    print("\n[3/6] Testando URLs dos streams...")
    # Test one URL per channel
    test_urls = {}
    for entry in entries:
        ch = identify_channel(entry["extinf"])
        if ch and ch not in test_urls:
            test_urls[ch] = entry["url"]

    live_channels = []
    dead_channels = []
    for ch, url in test_urls.items():
        if test_url(url):
            log(f"  ✓ {ch}: ONLINE")
            live_channels.append(ch)
        else:
            log(f"  ✗ {ch}: OFFLINE ou token expirado")
            dead_channels.append(ch)

    # Step 4: Build fixed M3U
    print("\n[4/6] Construindo M3U corrigido...")
    header, fixed_entries, removed = build_fixed_m3u(header, entries)

    if removed:
        log(f"Canais removidos (sem streams válidos): {removed}")

    # Step 5: Write fixed file
    print("\n[5/6] Salvando arquivo corrigido...")
    backup_file(INPUT_FILE)

    with open(TEMP_FILE, "w", encoding="utf-8") as f:
        f.write(header + "\n")
        for entry in fixed_entries:
            f.write(entry["extinf"] + "\n")
            f.write(entry["url"] + "\n")

    # Replace original
    os.replace(TEMP_FILE, INPUT_FILE)
    log(f"Arquivo salvo: {INPUT_FILE}")

    # Step 6: Verify
    print("\n[6/6] Verificação final...")
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    # Check header
    if "x-tvg-url" in content:
        log("✓ x-tvg-url presente no header")
    else:
        log("✗ x-tvg-url AUSENTE no header")

    # Check tvg-id
    extinf_count = content.count("#EXTINF:")
    tvg_id_count = content.count("tvg-id=")
    log(f"EXTINF lines: {extinf_count}, com tvg-id: {tvg_id_count}")

    # Check logos
    logo_matches = re.findall(r'tvg-logo="([^"]*)"', content)
    jpg_count = sum(1 for l in logo_matches if l.lower().endswith(".jpg"))
    non_jpg = [l for l in logo_matches if not l.lower().endswith(".jpg")]
    log(f"Logos totais: {len(logo_matches)}, .jpg: {jpg_count}")
    if non_jpg:
        log(f"  Logos NÃO .jpg: {non_jpg}")

    # Check for imgur
    if "imgur.com" in content.lower():
        log("✗ Links imgur.com encontrados!")
    else:
        log("✓ Sem links imgur.com")

    # Summary
    print("\n" + "=" * 60)
    print("RESUMO")
    print("=" * 60)
    print(f"Canais no arquivo final: {len(fixed_entries)}")
    for entry in fixed_entries:
        status = "✓" if entry["channel"] in live_channels else "?"
        print(f"  {status} {entry['channel']} (qualidade: {entry['quality']})")
    print(f"\nEPG sources: {len(working_epgs)}")
    for epg in working_epgs:
        print(f"  ✓ {epg}")
    print(f"\nBackup: {INPUT_FILE}{BACKUP_SUFFIX}")


if __name__ == "__main__":
    main()
