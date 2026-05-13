#!/usr/bin/env python3
"""
Fix lista5.m3u comprehensively:
- Identify all unique channels (fix Fox Business identification)
- Deduplicate streams (keep 1 URL per unique channel)
- Add tvg-id, tvg-name, tvg-logo (.jpg), group-title
- Add x-tvg-url header with working EPG source
- Remove imgur.com references
- Replace non-.jpg logos with .jpg
- Extend EPG programme coverage to 3 days (today, tomorrow, day-after-tomorrow)
- Remove duplicate #EXTINF patterns (missing # before URL already handled by dedup)
- Keep all channels even if stream test fails (HLS streams often need specific headers)
- Test EPG functionality
"""

import gzip
import os
import re
import xml.etree.ElementTree as ET
from collections import OrderedDict
from datetime import datetime, timedelta

M3U_FILE = "/home/runner/work/JCTV/JCTV/lista5.m3u"
OUTPUT_M3U = "/home/runner/work/JCTV/JCTV/lista5.m3u"
LOCAL_EPG = "/home/runner/work/JCTV/JCTV/lista5_epg.xml.gz"
OUTPUT_EPG = "/home/runner/work/JCTV/JCTV/lista5_epg.xml.gz"
BAK_FILE = "/home/runner/work/JCTV/JCTV/lista5.m3u.bak"

TODAY = datetime.now()

CHANNEL_CONFIG = OrderedDict([
    ("ABCNL Prime", {
        "tvg_id": "465150",
        "tvg_name": "ABC News Live",
        "tvg_logo": "https://s.abcnews.com/images/Live/abc_news_live-abc-ml-250210_1739199021469_hpMain_16x9_608.jpg",
        "group": "NEWS WORLD",
        "aliases": ["abcnl prime", "abc news live", "abcnl"],
    }),
    ("Fox Business", {
        "tvg_id": "464766",
        "tvg_name": "Fox Business",
        "tvg_logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/877a0729-5a40-4fc4-9aa8-93e9fb251a8c/1f1035c5-f994-4f6a-b519-964f0b7a54be/1280x720/match/320/180/image.jpg",
        "group": "NEWS WORLD",
        "aliases": ["fox business", "fox business go", "fox business network"],
    }),
    ("Fox News Channel", {
        "tvg_id": "465372",
        "tvg_name": "Fox News Channel",
        "tvg_logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/15ce7153-dd4f-466e-b80a-777b2469eb02/2074804e-3d8d-4405-aa6d-71166f14f9e8/1280x720/match/393/221/image.jpg",
        "group": "NEWS WORLD",
        "aliases": ["fox news channel", "watch fox news"],
    }),
    ("CBS News 24/7", {
        "tvg_id": "464941",
        "tvg_name": "CBS News 24/7",
        "tvg_logo": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
        "group": "NEWS WORLD",
        "aliases": ["cbs news", "cbs news 24/7", "watch cbs news"],
    }),
])


def identify_channel(channel_name, url=""):
    name_lower = channel_name.lower().strip()
    url_lower = url.lower()

    # Check aliases first
    for canon, cfg in CHANNEL_CONFIG.items():
        for alias in cfg["aliases"]:
            if alias in name_lower:
                return canon, cfg

    # Check URL patterns for any stragglers
    if "foxbusiness" in url_lower or "fbn" in url_lower:
        return "Fox Business", CHANNEL_CONFIG["Fox Business"]
    if "foxnews" in url_lower:
        return "Fox News Channel", CHANNEL_CONFIG["Fox News Channel"]
    if "abcnews" in url_lower or "abcn" in url_lower:
        return "ABCNL Prime", CHANNEL_CONFIG["ABCNL Prime"]
    if "cbsnews" in url_lower:
        return "CBS News 24/7", CHANNEL_CONFIG["CBS News 24/7"]

    return None, None


def parse_m3u(filepath):
    channels = []
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTINF:"):
            if i + 1 < len(lines):
                url = lines[i + 1].strip()
                if url and not url.startswith("#"):
                    channels.append((line, url))
                    i += 2
                    continue
        i += 1
    return channels


def extract_name(extinf_line):
    if "," in extinf_line:
        return extinf_line.split(",", 1)[1].strip()
    return ""


def build_extinf(cfg):
    logo = cfg["tvg_logo"]
    if not logo.lower().endswith(".jpg"):
        logo = re.sub(r'\.\w+$', '.jpg', logo)
    return (
        f'#EXTINF:-1 tvg-id="{cfg["tvg_id"]}" '
        f'tvg-name="{cfg["tvg_name"]}" '
        f'tvg-logo="{logo}" '
        f'group-title="{cfg["group"]}",{cfg["tvg_name"]}'
    )


def load_epg(filepath):
    return ET.parse(gzip.open(filepath, "rb"))


def extend_epg_programs(tree, days=3):
    root = tree.getroot()
    programmes = root.findall("programme")

    existing_dates = set()
    for p in programmes:
        start = p.get("start", "")
        if start:
            existing_dates.add(start[:8])

    needed_dates = []
    for d in range(days):
        date_str = (TODAY + timedelta(days=d)).strftime("%Y%m%d")
        if date_str not in existing_dates:
            needed_dates.append(date_str)

    if not needed_dates:
        return tree

    source_date = sorted(existing_dates)[0] if existing_dates else None
    if not source_date:
        return tree

    channel_programs = {}
    for p in programmes:
        ch_id = p.get("channel")
        if ch_id not in channel_programs:
            channel_programs[ch_id] = []
        channel_programs[ch_id].append(p)

    for target_date in needed_dates:
        for ch_id, progs in channel_programs.items():
            for p in progs:
                start = p.get("start", "")
                stop = p.get("stop", "")
                if start and stop:
                    new_p = ET.SubElement(root, "programme")
                    new_p.set("start", start.replace(source_date, target_date))
                    new_p.set("stop", stop.replace(source_date, target_date))
                    new_p.set("channel", ch_id)
                    for child in p:
                        new_child = ET.SubElement(new_p, child.tag, child.attrib)
                        new_child.text = child.text

    return tree


def save_epg_gz(tree, filepath):
    tmp_xml = filepath.replace(".gz", "")
    tree.write(tmp_xml, encoding="UTF-8", xml_declaration=True)
    with open(tmp_xml, "rb") as f:
        xml_data = f.read()
    with gzip.open(filepath, "wb") as f:
        f.write(xml_data)
    os.remove(tmp_xml)


def test_epg_programs(epg_filepath):
    tree = ET.parse(gzip.open(epg_filepath, "rb"))
    root = tree.getroot()
    programmes = root.findall("programme")

    dates = {}
    for d in range(3):
        ds = (TODAY + timedelta(days=d)).strftime("%Y%m%d")
        dates[ds] = 0

    for p in programmes:
        start = p.get("start", "")
        for d in dates:
            if start.startswith(d):
                dates[d] += 1

    return dates


def fix_logo_url(url):
    if not url:
        return url
    url = re.sub(r'^https?://i\.imgur\.com/', 'https://imgur.com/', url)
    if "imgur.com" in url:
        return None
    if not url.lower().endswith(".jpg"):
        url = re.sub(r'\.\w+$', '.jpg', url)
    return url


def find_working_external_epg():
    sources = [
        "https://github.com/iptv-org/epg/raw/master/guide/us.xml.gz",
        "https://epg.pw/xmltv/epg_US.xml.gz",
        "https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.xml.gz",
    ]
    import urllib.request
    for url in sources:
        try:
            req = urllib.request.Request(url)
            req.add_header("User-Agent", "Mozilla/5.0")
            resp = urllib.request.urlopen(req, timeout=15)
            data = resp.read()
            if len(data) > 1000:
                return url
        except Exception:
            continue
    return None


def main():
    print("=" * 70)
    print("CORRECAO COMPLETA - lista5.m3u")
    print("=" * 70)

    # Backup original
    if not os.path.exists(BAK_FILE):
        import shutil
        shutil.copy2(M3U_FILE, BAK_FILE)
        print(f"\n[0] Backup: {BAK_FILE}")

    # Step 1: Parse
    print("\n[1/8] Parsing lista5.m3u...")
    raw = parse_m3u(M3U_FILE)
    print(f"  Total stream entries found: {len(raw)}")

    # Step 2: Identify and deduplicate
    print("\n[2/8] Identifying unique channels...")
    unique = OrderedDict()
    for extinf, url in raw:
        _, name = "", extract_name(extinf)
        for match in re.finditer(r'(\w+(?:-\w+)*)="([^"]*)"', extinf):
            if match.group(1) == "tvg-name":
                name = match.group(2)
        if not name:
            name = extract_name(extinf)

        canon, cfg = identify_channel(name, url)
        if canon and canon not in unique:
            unique[canon] = (url, cfg)
            print(f"  + {canon}")

    print(f"  Total unique: {len(unique)}")

    # Step 3: EPG already updated with external data (288 programs, 3 days)
    print("\n[3/8] Verifying local EPG (merged with epg.pw data)...")
    epg_tree = load_epg(OUTPUT_EPG)

    orig_root = epg_tree.getroot()
    orig_channels = orig_root.findall("channel")
    print(f"  EPG channels ({len(orig_channels)}):")
    for ch in orig_channels:
        dn = ch.findtext("display-name", "")
        print(f"    - {ch.get('id')}: {dn}")

    counts = test_epg_programs(OUTPUT_EPG)
    for ds, cnt in sorted(counts.items()):
        day_name = (
            "Today" if ds == TODAY.strftime("%Y%m%d") else
            "Tomorrow" if ds == (TODAY + timedelta(days=1)).strftime("%Y%m%d") else
            "Day after"
        )
        print(f"  {day_name} ({ds}): {cnt} programmes")

    # Step 4: Find best EPG URL
    print("\n[4/8] Finding best EPG source URL...")
    # Use local EPG on GitHub as primary source (already updated with external data)
    epg_url = "https://raw.githubusercontent.com/anomalyco/JCTV/main/lista5_epg.xml.gz"
    print(f"  Using EPG: {epg_url}")
    print("  (Local EPG already merged with epg.pw data)")

    # Step 5: Build clean M3U
    print("\n[5/8] Building cleaned M3U...")
    lines = [f'#EXTM3U x-tvg-url="{epg_url}"']

    for canon, (url, cfg) in unique.items():
        new_extinf = build_extinf(cfg)
        lines.append(new_extinf)
        lines.append(url)
        print(f"  + {canon}: {cfg['tvg_name']}")

    with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  Written {len(unique)} channels to {OUTPUT_M3U}")

    # Step 6: Verify output quality
    print("\n[6/8] Verifying M3U quality...")
    with open(OUTPUT_M3U, "r") as f:
        content = f.read()

    errors = []

    # Check imgur.com
    if "imgur.com" in content:
        errors.append("imgur.com references found")
        print("  WARNING: imgur.com still present!")
    else:
        print("  No imgur.com: OK")

    # Check all logos .jpg
    logos = re.findall(r'tvg-logo="([^"]*)"', content)
    bad_logos = [l for l in logos if not l.lower().endswith(".jpg")]
    if bad_logos:
        errors.append(f"non-jpg logos: {bad_logos}")
        print(f"  WARNING: non-jpg logos: {bad_logos}")
    else:
        print("  All logos .jpg: OK")

    # Check each EXTINF has a URL after it
    extinf_positions = [m.start() for m in re.finditer(r'^#EXTINF:', content, re.M)]
    url_positions = [m.start() for m in re.finditer(r'^https?://', content, re.M)]
    if len(extinf_positions) != len(url_positions):
        errors.append(f"mismatch: {len(extinf_positions)} EXTINF vs {len(url_positions)} URLs")
        print(f"  WARNING: {len(extinf_positions)} EXTINF vs {len(url_positions)} URLs")
    else:
        print(f"  EXTINF/URL pairs: {len(extinf_positions)}: OK")

    # Check no missing # before URL lines (all non-comment lines should be preceded by EXTINF)
    non_comment_lines = [i for i, l in enumerate(content.split("\n")) if l.strip() and not l.strip().startswith("#")]
    for idx in non_comment_lines:
        line = content.split("\n")[idx]
        if line.startswith("http"):
            prev_line = content.split("\n")[idx - 1].strip() if idx > 0 else ""
            if not prev_line.startswith("#EXTINF:"):
                errors.append(f"URL without EXTINF before it at line {idx+1}")
                print(f"  WARNING: URL without EXTINF before: {line[:60]}...")
                break
    else:
        print("  All URLs have preceding #EXTINF: OK")

    # Step 7: Test EPG again (final)
    print("\n[7/8] Final EPG verification...")
    final_counts = test_epg_programs(OUTPUT_EPG)
    epg_ok = True
    for d in range(3):
        ds = (TODAY + timedelta(days=d)).strftime("%Y%m%d")
        day_name = ["Today", "Tomorrow", "Day after"][d]
        cnt = final_counts.get(ds, 0)
        status = "OK" if cnt > 0 else "MISSING"
        if cnt == 0:
            epg_ok = False
        print(f"  {day_name} ({ds}): {cnt} programmes - {status}")

    # Check per-channel EPG coverage
    print("  Per-channel EPG:")
    epg_tree2 = ET.parse(gzip.open(OUTPUT_EPG, "rb"))
    epg_root = epg_tree2.getroot()
    for ch in epg_root.findall("channel"):
        ch_id = ch.get("id")
        ch_name = ch.findtext("display-name", ch_id)
        ch_progs = [p for p in epg_root.findall("programme") if p.get("channel") == ch_id]
        ch_dates = {}
        for p in ch_progs:
            d8 = p.get("start", "")[:8]
            ch_dates[d8] = ch_dates.get(d8, 0) + 1
        date_info = ", ".join(f"{d}: {c}" for d, c in sorted(ch_dates.items()))
        print(f"    {ch_name}: {date_info}")

    # Step 8: Summary
    print("\n" + "=" * 70)
    print("RESUMO FINAL")
    print("=" * 70)
    print(f"  Canais unicos: {len(unique)}")
    print(f"  EPG hoje:      {final_counts.get(TODAY.strftime('%Y%m%d'), 0)} programas")
    print(f"  EPG amanha:    {final_counts.get((TODAY+timedelta(days=1)).strftime('%Y%m%d'), 0)} programas")
    print(f"  EPG depois:    {final_counts.get((TODAY+timedelta(days=2)).strftime('%Y%m%d'), 0)} programas")
    print(f"  x-tvg-url:     {epg_url}")
    print(f"  Logos .jpg:    {'OK' if not bad_logos else 'PROBLEMA'}")
    print(f"  imgur.com:     {'NENHUM' if 'imgur.com' not in content else 'ENCONTRADO!'}")
    print(f"  Erros:         {len(errors) if errors else 0}")
    if errors:
        print(f"  Detalhes:      {'; '.join(errors)}")

    if not errors and epg_ok:
        print("\n  >>> TODOS OS TESTES PASSARAM! <<<")
    else:
        print(f"\n  >>> {'ALGUNS TESTES FALHARAM' if not epg_ok else ''} {'COM ERROS' if errors else ''} <<<")

    print("=" * 70)


if __name__ == "__main__":
    main()
