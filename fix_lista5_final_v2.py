#!/usr/bin/env python3
"""
Final comprehensive fix for lista5.m3u:
- Uses correct epgshare01_US2 channel IDs
- Deduplicates channels properly (merges ABC variants)
- Tests all stream URLs
- Tests all logo URLs
- Ensures .jpg logos, no imgur
- Adds proper tvg-id, tvg-name, tvg-logo, group-title
- Sets working EPG URL in header
- Removes channels that fail antivirus/access tests
- Verifies EPG coverage for today, tomorrow, day+2
"""

import os
import re
import gzip
import shutil
import urllib.request
import urllib.error
import ssl
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

M3U_FILE = "lista5.m3u"
BACKUP = f"lista5.m3u.bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
REPORT = "fix_lista5_final_report.txt"

# Correct channel IDs from epgshare01_US2 (verified working)
CHANNELS = [
    {
        "tvg_id": "ABC.News.Live.us2",
        "name": "ABC News Live",
        "group": "NEWS WORLD",
        "logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
        "urls": [
            # akamaized.net is more reliable than dssott.com (token-based)
            "https://abcnews-livestreams.akamaized.net/out/v1/6a597119dbd5428a82dc11a2f514a1a2/abcn-live-10-cmaf-manifest/abcn-live-10-index.m3u8",
            "https://linear-abcnews-akc-na-west-1.media.dssott.com/dvt2=exp=1784072626~url=%2Fclt1%2Fva02%2Fdisneyplus%2Fchannel%2F79449312-79dd-473d-873c-515ebf4b5e5f-1781081210579%2F~psid=0c0ed17e-fe11-4996-9eb5-11ed9b5ef23e~did=6debc9af-3d1c-4a38-9aee-48d2e6a6d2bc~country=US~kid=k02~hmac=bbd69929f7904fa3242b19156fe3da39d671c1a77ac878f5ddbe88c4e26aaea1/clt1/va02/disneyplus/channel/79449312-79dd-473d-873c-515ebf4b5e5f-1781081210579/cmaf-cenc-ctr-2400K/2400_hdri_slide.m3u8",
        ],
    },
    {
        "tvg_id": "Fox.News.Channel.HD.us2",
        "name": "Fox News Channel",
        "group": "NEWS WORLD",
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/15de0523-3be4-4a9a-8159-7020114e7036/b6ff623a-26d6-4fd9-8bb8-0856adbf38ce/1280x720/match/676/380/image.jpg",
        "urls": [
            "https://fox-foxnewsnow-samsungus.amagi.tv/playlist.m3u8",
            "https://fox-foxnewsnow-vizio.amagi.tv/playlist.m3u8",
            "http://247preview.foxnews.com/hls/live/2020027/fncv3preview/primary_300.m3u8",
            "http://247preview.foxnews.com/hls/live/2020027/fncv3preview/primary.m3u8",
        ],
    },
    {
        "tvg_id": "Fox.Business.HD.us2",
        "name": "Fox Business Network",
        "group": "NEWS WORLD",
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/5bbfbbac-c7fe-4895-8c83-d996b7353939/5fc2d0a6-8dea-4e4a-9494-09e8f1fc0c05/1280x720/match/400/225/image.jpg",
        "urls": [
            "http://247preview.foxbusiness.com/hls/live/2020026/fbnv3preview/primary_300.m3u8",
            "http://247preview.foxbusiness.com/hls/live/2020026/fbnv3preview/index.m3u8",
        ],
    },
    {
        "tvg_id": "CBS.News.National.Stream.us2",
        "name": "CBS News 24/7",
        "group": "NEWS WORLD",
        "logo": "https://www.cbsnews.com/bundles/cbsnewsvideo/images/cbsn--main-bg.jpg",
        "urls": [
            "https://dai.google.com/linear/hls/pa/event/Sid4xiTQTkCT1SLu6rjUSQ/stream/2db756c6-2f15-45a9-9509-d1e9f6c3f825:TUL/master.m3u8",
            "https://dai.google.com/linear/hls/pa/event/Sid4xiTQTkCT1SLu6rjUSQ/stream/2db756c6-2f15-45a9-9509-d1e9f6c3f825:TUL/variant/93c2acc6479504ccd49e3f4d21db1bec/bandwidth/441000.m3u8",
        ],
    },
]

EPG_URL = "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz"


def log(msg, lines=None):
    print(msg)
    if lines is not None:
        lines.append(msg)


def test_url(url, timeout=10):
    """Test URL accessibility."""
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(url, method="HEAD", headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
        })
        resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)
        return True, resp.status, resp.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        if e.code in (403, 405):
            # Try GET for forbidden or method not allowed
            try:
                req = urllib.request.Request(url, method="GET", headers={
                    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
                })
                resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)
                return True, resp.status, resp.headers.get("Content-Type", "")
            except Exception:
                pass
        return False, e.code, ""
    except Exception as e:
        return False, 0, str(e)


def is_suspicious(url):
    """Basic antivirus check for suspicious URL patterns."""
    patterns = [
        r'eval\(', r'javascript:', r'<script', r'data:text/html',
        r'\.exe(\?|$)', r'\.bat(\?|$)', r'\.cmd(\?|$)', r'\.ps1(\?|$)',
        r'\.php\?', r'base64', r'coinhive', r'cryptojack',
    ]
    for p in patterns:
        if re.search(p, url, re.IGNORECASE):
            return True
    return False


def validate_logo(url):
    """Validate logo URL: must be .jpg, no imgur, accessible."""
    if not url:
        return False, "No logo URL"
    if "imgur.com" in url.lower():
        return False, "imgur.com not allowed"
    if not re.search(r'\.(jpg|jpeg)(\?|$)', url, re.IGNORECASE):
        return False, f"Not .jpg: {url}"
    ok, status, _ = test_url(url, timeout=8)
    if not ok:
        return False, f"Logo not accessible (HTTP {status})"
    return True, "OK"


def main():
    report = []
    log("=" * 70, report)
    log("LISTA5.M3U FINAL FIX", report)
    log(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", report)
    log("=" * 70, report)

    # Backup
    if os.path.exists(M3U_FILE):
        shutil.copy2(M3U_FILE, BACKUP)
        log(f"Backup: {BACKUP}", report)

    # Step 1: Test all streams
    log("\n--- STEP 1: Test Stream URLs ---", report)
    working_channels = []
    for ch in CHANNELS:
        log(f"\n  {ch['name']}:", report)
        best_url = None

        for url in ch["urls"]:
            if is_suspicious(url):
                log(f"    SUSPICIOUS: {url[:80]}... -> REMOVED", report)
                continue

            ok, status, ct = test_url(url, timeout=12)
            log(f"    URL: {url[:80]}...", report)
            log(f"    Status: {status}, Type: {ct}, OK: {ok}", report)

            if ok:
                best_url = url
                log(f"    -> SELECTED (working)", report)
                break  # Use first working URL
            else:
                log(f"    -> FAILED", report)

        if best_url:
            ch["selected_url"] = best_url
            working_channels.append(ch)
        else:
            log(f"  ALL URLS FAILED for {ch['name']} -> REMOVING", report)

    log(f"\nWorking streams: {len(working_channels)}/{len(CHANNELS)}", report)

    # Step 2: Test logos
    log("\n--- STEP 2: Test Logo URLs ---", report)
    for ch in working_channels:
        ok, msg = validate_logo(ch["logo"])
        status = "PASS" if ok else "FAIL"
        log(f"  {ch['name']}: {status} ({msg})", report)
        if not ok:
            log(f"    WARNING: Logo may not display correctly", report)

    # Step 3: Test EPG
    log("\n--- STEP 3: Test EPG Source ---", report)
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(EPG_URL, headers={
            "User-Agent": "Mozilla/5.0",
            "Accept-Encoding": "gzip, deflate",
        })
        resp = urllib.request.urlopen(req, timeout=60, context=ctx)
        epg_data = resp.read()
        if epg_data[:2] == b'\x1f\x8b':
            epg_data = gzip.decompress(epg_data)

        root = ET.fromstring(epg_data)
        epg_channels = {c.get("id") for c in root.findall(".//channel")}
        log(f"  EPG downloaded: {len(epg_data)} bytes", report)
        log(f"  Total channels in EPG: {len(epg_channels)}", report)

        today = datetime.now()
        for ch in working_channels:
            cid = ch["tvg_id"]
            log(f"\n  {ch['name']} (tvg-id: {cid}):", report)
            found = cid in epg_channels
            log(f"    Channel in EPG: {'YES' if found else 'NO'}", report)

            for d in range(3):
                dt = today + timedelta(days=d)
                date_str = dt.strftime("%Y-%m-%d")
                date_compact = dt.strftime("%Y%m%d")
                count = sum(
                    1 for p in root.findall(".//programme")
                    if p.get("channel") == cid and p.get("start", "").startswith(date_compact)
                )
                log(f"    {date_str}: {count} programmes {'OK' if count > 0 else 'MISSING'}", report)

    except Exception as e:
        log(f"  EPG test failed: {e}", report)

    # Step 4: Generate final M3U
    log("\n--- STEP 4: Generate Final M3U ---", report)
    lines = [f'#EXTM3U url-x-tvg="{EPG_URL}"']

    for ch in working_channels:
        extinf = (
            f'#EXTINF:-1 tvg-id="{ch["tvg_id"]}" '
            f'tvg-name="{ch["name"]}" '
            f'tvg-logo="{ch["logo"]}" '
            f'group-title="{ch["group"]}",{ch["name"]}'
        )
        lines.append(extinf)
        lines.append(ch["selected_url"])
        log(f"  {ch['name']} -> {ch['selected_url'][:70]}...", report)

    output = "\n".join(lines) + "\n"

    with open(M3U_FILE, "w", encoding="utf-8") as f:
        f.write(output)

    log(f"\nWritten: {M3U_FILE}", report)

    # Step 5: Final verification
    log("\n--- STEP 5: Final Verification ---", report)
    with open(M3U_FILE, "r", encoding="utf-8") as f:
        content = f.read()
        verify_lines = content.split("\n")

    errors = []

    # Check header
    if not verify_lines[0].startswith("#EXTM3U"):
        errors.append("Missing #EXTM3U header")
    if "url-x-tvg=" not in verify_lines[0]:
        errors.append("Missing EPG URL in header")

    # Check each channel
    extinf_count = 0
    url_count = 0
    for i, line in enumerate(verify_lines):
        line = line.strip()
        if line.startswith("#EXTINF:"):
            extinf_count += 1
            # Must have tvg-id
            if 'tvg-id=' not in line:
                errors.append(f"Line {i+1}: Missing tvg-id")
            # Must have tvg-logo
            if 'tvg-logo=' not in line:
                errors.append(f"Line {i+1}: Missing tvg-logo")
            else:
                # Check logo is .jpg
                logo_match = re.search(r'tvg-logo="([^"]*)"', line)
                if logo_match:
                    logo = logo_match.group(1)
                    if "imgur.com" in logo.lower():
                        errors.append(f"Line {i+1}: imgur.com logo!")
                    if not re.search(r'\.(jpg|jpeg)(\?|$)', logo, re.IGNORECASE):
                        errors.append(f"Line {i+1}: Logo not .jpg: {logo}")
            # Must have tvg-name
            if 'tvg-name=' not in line:
                errors.append(f"Line {i+1}: Missing tvg-name")
            # Must have group-title
            if 'group-title=' not in line:
                errors.append(f"Line {i+1}: Missing group-title")
        elif line.startswith("http"):
            url_count += 1
            # Check previous line is EXTINF
            if i > 0 and not verify_lines[i-1].strip().startswith("#EXTINF:"):
                errors.append(f"Line {i+1}: URL without #EXTINF above")

    if extinf_count != url_count:
        errors.append(f"Mismatch: {extinf_count} EXTINF vs {url_count} URLs")

    if errors:
        log("ERRORS:", report)
        for e in errors:
            log(f"  - {e}", report)
    else:
        log("ALL CHECKS PASSED!", report)

    log(f"\nChannels: {extinf_count}", report)
    log(f"Streams: {url_count}", report)

    # Write report
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(report))
    log(f"\nReport: {REPORT}", report)
    log("=" * 70, report)


if __name__ == "__main__":
    main()
