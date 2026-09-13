#!/usr/bin/env python3
import re
import gzip
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import subprocess

M3U = 'lista5.m3u'
EPG_URL = 'https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz'

def parse_m3u(path):
    with open(path, encoding='utf-8') as f:
        lines = [l.rstrip('\n') for l in f]
    header = lines[0] if lines else ''
    entries = []
    for i, line in enumerate(lines):
        if line.startswith('#EXTINF:'):
            for j in range(i + 1, len(lines)):
                if lines[j].strip() and not lines[j].startswith('#'):
                    entries.append({'extinf': line, 'url': lines[j].strip(), 'extinf_line': i + 1, 'url_line': j + 1})
                    break
    return header, entries

def main():
    print("=" * 70)
    print("VALIDATION: lista5.m3u")
    print("=" * 70)

    header, entries = parse_m3u(M3U)
    print(f"\nHeader: {header}")
    print(f"Total entries: {len(entries)}")

    ok = True

    # 1. Structural checks
    print("\n[1] STRUCTURE")
    seen_urls = set()
    for e in entries:
        # each URL must have a # line directly above
        if not e['extinf'].startswith('#'):
            print(f"  FAIL: line {e['extinf_line']} does not start with #")
            ok = False
        # no duplicates
        if e['url'] in seen_urls:
            print(f"  FAIL: duplicate URL line {e['url_line']}")
            ok = False
        seen_urls.add(e['url'])
        # imgur check
        if 'imgur' in e['extinf'].lower():
            print(f"  FAIL: imgur in line {e['extinf_line']}")
            ok = False
        # logo .jpg check
        m = re.search(r'tvg-logo="([^"]*)"', e['extinf'])
        if m:
            logo = m.group(1)
            base = logo.split('?')[0]
            if not base.lower().endswith('.jpg'):
                print(f"  FAIL: logo not .jpg line {e['extinf_line']}: {logo}")
                ok = False
            if 'imgur' in logo.lower():
                print(f"  FAIL: imgur logo line {e['extinf_line']}")
                ok = False
        else:
            print(f"  FAIL: missing tvg-logo line {e['extinf_line']}")
            ok = False
        # tvg-id check
        if 'tvg-id=' not in e['extinf']:
            print(f"  FAIL: missing tvg-id line {e['extinf_line']}")
            ok = False
    print("  Structure: " + ("OK" if ok else "PROBLEMS FOUND"))

    # Extract tvg-ids and logos
    tvg_ids = []
    logos = []
    for e in entries:
        m = re.search(r'tvg-id="([^"]*)"', e['extinf'])
        if m:
            tvg_ids.append(m.group(1))
        m = re.search(r'tvg-logo="([^"]*)"', e['extinf'])
        if m:
            logos.append(m.group(1).split('?')[0])

    # 2. EPG check
    print("\n[2] EPG")
    resp = requests.get(EPG_URL, timeout=120, headers={'Accept-Encoding': 'gzip'})
    print(f"  HTTP {resp.status_code}, {len(resp.content)} bytes")
    xml_data = gzip.decompress(resp.content).decode('utf-8', 'replace')
    root = ET.fromstring(xml_data)
    epg_channels = set(c.get('id') for c in root.findall('channel'))

    hoje = datetime.now().strftime("%Y%m%d")
    amanha = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
    depois = (datetime.now() + timedelta(days=2)).strftime("%Y%m%d")

    for tid in tvg_ids:
        if tid not in epg_channels:
            print(f"  FAIL: tvg-id {tid} NOT in EPG")
            ok = False
        else:
            counts = {'hoje': 0, 'amanha': 0, 'depois': 0}
            for p in root.findall('programme'):
                if p.get('channel') == tid:
                    d = p.get('start', '')[:8]
                    if d == hoje:
                        counts['hoje'] += 1
                    elif d == amanha:
                        counts['amanha'] += 1
                    elif d == depois:
                        counts['depois'] += 1
            print(f"  {tid}: in EPG. hoje={counts['hoje']} amanha={counts['amanha']} depois={counts['depois']}")
            if counts['hoje'] == 0 or counts['amanha'] == 0 or counts['depois'] == 0:
                print("  FAIL: missing program data for one of the 3 days")
                ok = False

    # 3. Logo check
    print("\n[3] LOGOS (must be .jpg and reachable)")
    for logo in sorted(set(logos)):
        r = subprocess.run(['curl', '-s', '-o', '/dev/null', '-w', '%{http_code}', '-L', '--max-time', '30', logo],
                           capture_output=True, text=True)
        print(f"  {r.stdout.strip()} | {logo}")
        if r.stdout.strip() != '200':
            print("  FAIL: logo not reachable")
            ok = False

    # 4. Stream check (fetches m3u8 manifest)
    print("\n[4] STREAMS (must return valid HLS manifest)")
    for e in entries:
        r = subprocess.run(['curl', '-s', '-L', '--max-time', '30', '-H', 'User-Agent: Mozilla/5.0',
                            '-r', '0-1500', e['url']], capture_output=True, text=True)
        body = r.stdout
        valid = '#EXTM3U' in body and '#EXT-X' in body
        print(f"  {'OK ' if valid else 'FAIL'} | {e['url'][:90]}...")
        if not valid:
            print(f"         body={body[:100]!r}")
            ok = False

    print("\n" + "=" * 70)
    print("RESULT: " + ("ALL CHECKS PASSED ✓" if ok else "PROBLEMS FOUND ✗"))
    print("=" * 70)
    return ok

if __name__ == '__main__':
    ok = main()
    raise SystemExit(0 if ok else 1)