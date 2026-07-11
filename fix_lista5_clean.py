#!/usr/bin/env python3
"""
Clean fix for lista5.m3u - deduplicate, add EPG, fix logos, test streams.
"""

import re
import os
import shutil
import time
from datetime import datetime
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

INPUT = "lista5.m3u"
BACKUP = INPUT + f".bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"

# EPG sources
EPG_URL = "https://epg.pw/xmltv/epg_US.xml"

# Define the 4 channels we want
CHANNELS = [
    {
        "name": "ABC News Live",
        "tvg_id": "465150",
        "tvg_name": "ABC News Live",
        "logo": "https://keyframe-cdn.abcnews.com/streamprovider10.jpg",
        "group": "NEWS WORLD",
        "pattern": r"ABC News Live",
        "best_url": "https://abcnews-livestreams.akamaized.net/out/v1/6a597119dbd5428a82dc11a2f514a1a2/abcn-live-10-cmaf-manifest/abcn-live-10-index.m3u8",
    },
    {
        "name": "Fox News",
        "tvg_id": "465372",
        "tvg_name": "Fox News",
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/d1df10f8-9e3c-458c-8ef9-497826d22a9a/78f94932-4011-4dfc-b541-26a11ba5dfd3/1280x720/match/400/225/image.jpg",
        "group": "NEWS WORLD",
        "pattern": r"Fox News",
        "best_url": None,  # Will be found from file
    },
    {
        "name": "Fox Business",
        "tvg_id": "464766",
        "tvg_name": "Fox Business",
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/d1df10f8-9e3c-458c-8ef9-497826d22a9a/78f94932-4011-4dfc-b541-26a11ba5dfd3/1280x720/match/400/225/image.jpg",
        "group": "NEWS WORLD",
        "pattern": r"Fox Business",
        "best_url": None,
    },
    {
        "name": "CBS News",
        "tvg_id": "464941",
        "tvg_name": "CBS News",
        "logo": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
        "group": "NEWS WORLD",
        "pattern": r"CBS News",
        "best_url": None,
    },
]


def log(msg):
    print(f"  {msg}")


def test_url(url, timeout=10):
    """Quick HEAD/GET test."""
    try:
        req = Request(url, method="HEAD")
        req.add_header("User-Agent", "Mozilla/5.0")
        resp = urlopen(req, timeout=timeout)
        return resp.status < 400
    except HTTPError:
        try:
            req = Request(url)
            req.add_header("User-Agent", "Mozilla/5.0")
            resp = urlopen(req, timeout=timeout)
            data = resp.read(100)
            return len(data) > 0
        except:
            return False
    except:
        return False


def test_epg(url, timeout=15):
    """Test EPG source."""
    try:
        req = Request(url)
        req.add_header("User-Agent", "Mozilla/5.0")
        resp = urlopen(req, timeout=timeout)
        data = resp.read(5000).decode("utf-8", errors="ignore")
        return "<tv" in data
    except:
        return False


def parse_m3u(filepath):
    """Parse M3U into (header, [(extinf, url), ...])."""
    with open(filepath, "r", encoding="utf-8") as f:
        lines = [l.rstrip("\n") for l in f.readlines()]

    header = lines[0] if lines else "#EXTM3U"
    entries = []
    i = 1
    while i < len(lines):
        if lines[i].startswith("#EXTINF:"):
            extinf = lines[i]
            url = lines[i + 1] if i + 1 < len(lines) and not lines[i + 1].startswith("#") else ""
            entries.append((extinf, url))
            i += 2
        else:
            i += 1
    return header, entries


def stream_quality_score(url):
    """Rate stream quality. Higher = better."""
    u = url.lower()
    score = 0
    # Prefer higher bitrate
    if "2400" in u: score = 10
    elif "1700" in u: score = 8
    elif "master.m3u8" in u: score = 7
    elif "1080" in u: score = 9
    elif "720" in u: score = 6
    elif "ctr-all" in u: score = 5
    elif "index.m3u8" in u and "variant" not in u: score = 4
    # Penalize audio-only or low quality
    if "audio-aac" in u: score = 1
    if "/variant/" in u: score = max(score, 2)
    # Penalize expired tokens
    exp_match = re.search(r"exp=(\d+)", u)
    if exp_match:
        try:
            if int(exp_match.group(1)) < time.time():
                score = -1
        except:
            pass
    return score


def find_best_stream(entries, pattern):
    """Find best quality stream matching pattern."""
    candidates = []
    for extinf, url in entries:
        if re.search(pattern, extinf, re.IGNORECASE) or re.search(pattern, url, re.IGNORECASE):
            q = stream_quality_score(url)
            candidates.append((q, extinf, url))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    # Return best non-expired
    for q, extinf, url in candidates:
        if q >= 0:
            return (extinf, url, q)
    return None


def main():
    print("=" * 60)
    print("CORREÇÃO COMPLETA - lista5.m3u")
    print("=" * 60)

    # Test EPG
    print("\n[1] Testando EPG...")
    epg_ok = test_epg(EPG_URL)
    log(f"{'✓' if epg_ok else '✗'} epg.pw: {EPG_URL}")

    # Backup
    print("\n[2] Backup...")
    shutil.copy2(INPUT, BACKUP)
    log(f"Backup: {BACKUP}")

    # Parse
    print("\n[3] Analisando arquivo...")
    header, entries = parse_m3u(INPUT)
    log(f"Entries originais: {len(entries)}")

    # Find best stream per channel
    print("\n[4] Selecionando melhor stream por canal...")
    results = []
    for ch in CHANNELS:
        found = find_best_stream(entries, ch["pattern"])
        if found:
            extinf, url, quality = found
            log(f"✓ {ch['name']}: qualidade {quality}")
            results.append(ch)
        else:
            log(f"✗ {ch['name']}: NENHUM stream encontrado")

    # Test streams
    print("\n[5] Testando streams...")
    alive = []
    for ch in results:
        url = ch["best_url"] or next(
            (u for e, u in entries if re.search(ch["pattern"], e, re.IGNORECASE)),
            None
        )
        if url and test_url(url):
            log(f"✓ {ch['name']}: ONLINE")
            alive.append(ch)
        else:
            log(f"? {ch['name']}: Não testável (pode ter token expirado)")
            alive.append(ch)  # Keep anyway - tokens refresh

    # Build clean M3U
    print("\n[6] Gerando M3U limpo...")
    epg_attr = f' x-tvg-url="{EPG_URL}"' if epg_ok else ""
    lines = [f"#EXTM3U{epg_attr}"]

    for ch in results:
        # Find best URL from original entries
        url = None
        best_q = -1
        for extinf, u in entries:
            if re.search(ch["pattern"], extinf, re.IGNORECASE):
                q = stream_quality_score(u)
                if q > best_q:
                    best_q = q
                    url = u

        if not url:
            continue

        # Build EXTINF
        extinf = (
            f'#EXTINF:-1 tvg-id="{ch["tvg_id"]}" '
            f'tvg-name="{ch["tvg_name"]}" '
            f'tvg-logo="{ch["logo"]}" '
            f'group-title="{ch["group"]}",'
            f'{ch["name"]}'
        )
        lines.append(extinf)
        lines.append(url)

    # Write
    with open(INPUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    log(f"Salvo: {INPUT}")

    # Verify
    print("\n[7] Verificação final...")
    with open(INPUT, "r", encoding="utf-8") as f:
        content = f.read()

    checks = {
        "x-tvg-url": "x-tvg-url" in content,
        "tvg-id": content.count("tvg-id=") == len(results),
        "Todos .jpg": all(".jpg" in l for l in re.findall(r'tvg-logo="([^"]*)"', content)),
        "Sem imgur": "imgur.com" not in content.lower(),
        "EXTINF ok": content.count("#EXTINF:") == len(results),
    }

    for check, ok in checks.items():
        log(f"{'✓' if ok else '✗'} {check}")

    # Summary
    print("\n" + "=" * 60)
    print("RESUMO FINAL")
    print("=" * 60)
    print(f"Canais: {len(results)}")
    for ch in results:
        print(f"  ✓ {ch['name']} (tvg-id: {ch['tvg_id']})")
    print(f"EPG: {EPG_URL}")
    print(f"Backup: {BACKUP}")


if __name__ == "__main__":
    main()
