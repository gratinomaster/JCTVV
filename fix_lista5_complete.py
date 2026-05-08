#!/usr/bin/env python3
import re
import gzip
import io
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from collections import OrderedDict

CHANNEL_MAP = OrderedDict([
    ("Fox Business", {
        "epg_id": "464766",
        "tvg_id": "464766",
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/c9b2e2eb-7b87-435c-9510-eab2650ff944/8b584585-acf2-4c37-aa07-aaf2d077bb20/1280x720/match/676/380/image.jpg",
        "group": "NEWS WORLD",
        "match_names": ["Fox Business"]
    }),
    ("Fox News Channel", {
        "epg_id": "465372",
        "tvg_id": "465372",
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/3b09e0ef-610a-43d4-960b-78dc97ae2bd2/dc2e6082-3de1-40e8-a3ab-b6a61b18c3b1/1280x720/match/400/225/image.jpg",
        "group": "NEWS WORLD",
        "match_names": ["Fox News"]
    }),
    ("ABC News Live", {
        "epg_id": "465150",
        "tvg_id": "465150",
        "logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
        "group": "NEWS WORLD",
        "match_names": ["ABC News"]
    }),
    ("CBS News 24/7", {
        "epg_id": "464941",
        "tvg_id": "464941",
        "logo": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
        "group": "NEWS WORLD",
        "match_names": ["CBS News"]
    })
])

CUSTOM_EPG_URL = "https://raw.githubusercontent.com/JCTV/JCTV/main/lista5_epg.xml"

def norm(s):
    return re.sub(r'[\s\-_\.]+', '', s).lower()

def detect_channel(channel_name, stream_url=""):
    name_lower = channel_name.lower()
    url_lower = stream_url.lower()
    for display_name, config in CHANNEL_MAP.items():
        for match_name in config["match_names"]:
            if match_name.lower() in name_lower:
                return display_name, config
    for display_name, config in CHANNEL_MAP.items():
        for match_name in config["match_names"]:
            if match_name.lower() in url_lower:
                return display_name, config
    return None, None

def find_best_url(variants):
    priority_orderings = [
        lambda u: 'master.m3u8' in u.lower(),
        lambda u: 'cmaf' in u.lower() and '2400' in u.lower(),
        lambda u: 'cmaf' in u.lower(),
        lambda u: '720' in u.lower() or '1080' in u.lower(),
        lambda u: 'hdri' in u.lower(),
        lambda u: True,
    ]
    scored = []
    for url in variants:
        score = sum(5 if cond(url) else 0 for cond in priority_orderings)
        scored.append((score, url))
    scored.sort(key=lambda x: -x[0])
    return scored[0][1] if scored else None

def generate_custom_epg():
    print("=" * 60)
    print("Generating custom EPG for lista5 channels from epg.pw US")
    print("=" * 60)

    target_ids = set()
    for display_name, config in CHANNEL_MAP.items():
        target_ids.add(config["epg_id"])

    epg_url = "https://epg.pw/xmltv/epg_US.xml.gz"
    print(f"Downloading: {epg_url}")
    r = requests.get(epg_url, timeout=120, headers={'User-Agent': 'Mozilla/5.0'})
    raw = r.content
    print(f"Received: {len(raw)} bytes")

    if raw[:2] == b'\x1f\x8b':
        raw = gzip.decompress(raw)

    root = ET.fromstring(raw)
    
    matching_channels = []
    for channel in root.findall("channel"):
        cid = channel.get("id", "")
        if cid in target_ids:
            matching_channels.append(channel)

    matching_programmes = []
    for prog in root.findall("programme"):
        ch = prog.get("channel", "")
        if ch in target_ids:
            matching_programmes.append(prog)

    print(f"Found {len(matching_channels)} channels, {len(matching_programmes)} programmes")

    output = ET.Element("tv", attrib={"generator-info-name": "lista5_epg"})
    for ch in matching_channels:
        output.append(ch)
    for prog in matching_programmes:
        output.append(prog)

    tree = ET.ElementTree(output)
    buf = io.BytesIO()
    tree.write(buf, encoding='utf-8', xml_declaration=True)

    filepath = "/home/runner/work/JCTV/JCTV/lista5_epg.xml"
    with open(filepath, 'wb') as f:
        f.write(buf.getvalue())
    
    filepath_gz = "/home/runner/work/JCTV/JCTV/lista5_epg.xml.gz"
    with gzip.open(filepath_gz, 'wb') as f:
        f.write(buf.getvalue())

    print(f"Saved: {filepath} ({len(buf.getvalue())} bytes)")
    print(f"Saved: {filepath_gz}")
    return filepath, matching_channels, matching_programmes

def test_epg():
    print("\n" + "=" * 60)
    print("Testing EPG functionality")
    print("=" * 60)

    filepath = "/home/runner/work/JCTV/JCTV/lista5_epg.xml"
    today = datetime.now().strftime("%Y%m%d")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
    day_after = (datetime.now() + timedelta(days=2)).strftime("%Y%m%d")

    print(f"Today: {today}")
    print(f"Tomorrow: {tomorrow}")
    print(f"Day after: {day_after}")

    tree = ET.parse(filepath)
    root = tree.getroot()

    channels = {}
    for ch in root.findall("channel"):
        cid = ch.get("id", "")
        dn = ch.find("display-name")
        channels[cid] = dn.text if dn is not None else cid

    programmes = root.findall("programme")
    
    stats = {cid: {"today": 0, "tomorrow": 0, "day_after": 0} for cid in channels}
    
    for prog in programmes:
        ch = prog.get("channel", "")
        start = prog.get("start", "")[:8]
        if ch in stats:
            if start == today:
                stats[ch]["today"] += 1
            elif start == tomorrow:
                stats[ch]["tomorrow"] += 1
            elif start == day_after:
                stats[ch]["day_after"] += 1

    all_ok = True
    for cid, ch_name in channels.items():
        s = stats[cid]
        ok = s["today"] > 0 and s["tomorrow"] > 0
        status = "OK" if ok else "FAIL"
        print(f"  [{status}] {ch_name} (ID: {cid}):")
        print(f"         Today: {s['today']} | Tomorrow: {s['tomorrow']} | Day after: {s['day_after']}")
        if not ok:
            all_ok = False

    if all_ok:
        print("\n  EPG is valid and working for all channels!")
    else:
        print("\n  WARNING: Some channels have missing EPG data")

    return all_ok

def fix_m3u():
    print("\n" + "=" * 60)
    print("Fixing lista5.m3u")
    print("=" * 60)

    with open("lista5.m3u", "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.strip().split("\n")

    attr_pattern = re.compile(r'(tvg-id|tvg-logo|tvg-name|group-title)="([^"]*)"')

    def extract_extinf(extinf_line):
        params_part = re.sub(r'^#EXTINF:-?\d+\s*', '', extinf_line)
        attrs = {}
        pos = 0
        while True:
            m = attr_pattern.search(params_part, pos)
            if not m:
                break
            key, val = m.group(1), m.group(2)
            attrs[key] = val
            pos = m.end()
        after_attrs = params_part[pos:].strip()
        channel_name = after_attrs.lstrip(',').strip()
        return channel_name, attrs

    variants = {}
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line.startswith('#EXTINF:'):
            i += 1
            continue
        
        channel_name, attrs = extract_extinf(line)
        logo = attrs.get('tvg-logo', '')
        group = attrs.get('group-title', 'NEWS WORLD')
        
        url_line = ""
        if i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            if next_line and not next_line.startswith("#"):
                url_line = next_line
        
        if url_line and channel_name:
            display_name, config = detect_channel(channel_name, url_line)
            key = display_name if display_name else channel_name
            if key not in variants:
                variants[key] = {
                    "name": display_name if display_name else channel_name,
                    "logo": logo,
                    "group": group,
                    "urls": [],
                    "config": config,
                }
            variants[key]["urls"].append(url_line)
        
        i += 2

    print(f"Found {len(variants)} unique channels")

    output_lines = []
    output_lines.append(f'#EXTM3U url-tvg="{CUSTOM_EPG_URL}"')

    for display_name, v in variants.items():
        if v["config"]:
            best_url = find_best_url(v["urls"])
            if best_url:
                logo = v["config"]["logo"]
                tvg_id = v["config"]["tvg_id"]
                
                extinf = f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-logo="{logo}" group-title="{v["group"]}",{v["name"]}'
                output_lines.append(extinf)
                output_lines.append(best_url)
        else:
            best_url = find_best_url(v["urls"])
            if best_url:
                logo = v["logo"]
                if not logo.lower().endswith(".jpg"):
                    logo = ""
                extinf = f'#EXTINF:-1 tvg-logo="{logo}" group-title="{v["group"]}",{v["name"]}'
                output_lines.append(extinf)
                output_lines.append(best_url)

    output = "\n".join(output_lines) + "\n"

    with open("lista5.m3u", "w", encoding="utf-8") as f:
        f.write(output)

    channel_count = len([l for l in output_lines if l.startswith("#EXTINF:")])
    print(f"Written {channel_count} channels to lista5.m3u")
    return output_lines

def test_streams():
    print("\n" + "=" * 60)
    print("Testing stream URLs")
    print("=" * 60)

    with open("lista5.m3u", "r", encoding="utf-8") as f:
        lines = f.readlines()

    urls = [l.strip() for l in lines if l.strip().startswith("http")]
    
    results = {}
    for url in urls:
        try:
            r = requests.head(url, timeout=15, allow_redirects=True, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            results[url] = r.status_code
            status = "OK" if r.status_code < 400 else f"HTTP {r.status_code}"
            print(f"  [{status}] {url[:80]}...")
        except Exception as e:
            results[url] = str(e)
            print(f"  [FAIL] {url[:80]}... -> {e}")

    working = sum(1 for v in results.values() if isinstance(v, int) and v < 400)
    failed = len(results) - working
    print(f"\nStreams: {working}/{len(results)} working, {failed} failed")
    return results

def main():
    generate_custom_epg()
    test_epg()
    fix_m3u()
    test_streams()

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print("  Custom EPG: lista5_epg.xml (generated from epg.pw US)")
    print(f"  EPG URL: {CUSTOM_EPG_URL}")
    print("  M3U: lista5.m3u (fixed)")
    print("  To use EPG in player, add the url-tvg to your playlist")

if __name__ == "__main__":
    main()
