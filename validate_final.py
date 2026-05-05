#!/usr/bin/env python3
"""Final validation of lista5.m3u"""
import requests
import gzip
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

print("=" * 70)
print("VALIDACAO FINAL - lista5.m3u")
print("=" * 70)

errors = []
warnings = []

with open('lista5.m3u', 'r') as f:
    lines = [l.strip() for l in f.readlines()]

# Check #EXTM3U header
if not lines[0].startswith('#EXTM3U'):
    errors.append("Missing #EXTM3U header")
else:
    print("[OK] #EXTM3U header present")
    if 'url-tvg=' in lines[0]:
        print(f"[OK] EPG URL defined: {lines[0].split('url-tvg=')[1].strip(chr(34))}")

# Parse channels
channels = []
i = 0
while i < len(lines):
    if lines[i].startswith('#EXTINF'):
        if i + 1 < len(lines) and not lines[i+1].startswith('#'):
            channels.append((lines[i], lines[i+1]))
            i += 2
        else:
            errors.append(f"Line {i+1}: #EXTINF without URL below")
            i += 1
    elif lines[i] and not lines[i].startswith('#'):
        errors.append(f"Line {i+1}: URL without #EXTINF above: {lines[i][:60]}...")
        i += 1
    else:
        i += 1

print(f"\n[OK] {len(channels)} channels parsed")

for idx, (info, url) in enumerate(channels, 1):
    print(f"\n--- Channel {idx} ---")
    
    # Check tvg-id
    if 'tvg-id=' in info:
        tvg_id = info.split('tvg-id="')[1].split('"')[0]
        print(f"  [OK] tvg-id: {tvg_id}")
    else:
        errors.append(f"Channel {idx}: Missing tvg-id")
    
    # Check tvg-logo
    if 'tvg-logo=' in info:
        logo = info.split('tvg-logo="')[1].split('"')[0]
        if '.jpg' in logo.lower():
            print(f"  [OK] tvg-logo (.jpg): {logo[:70]}...")
        else:
            errors.append(f"Channel {idx}: Logo not .jpg: {logo}")
        if 'imgur.com' in logo.lower():
            errors.append(f"Channel {idx}: Logo uses imgur.com")
    else:
        errors.append(f"Channel {idx}: Missing tvg-logo")
    
    # Check group-title
    if 'group-title=' in info:
        group = info.split('group-title="')[1].split('"')[0]
        print(f"  [OK] group-title: {group}")
    
    # Test URL
    try:
        r = requests.get(url, timeout=10, stream=True, headers={'User-Agent': 'VLC/3.0'})
        is_m3u8 = '#EXTM3U' in r.text[:300]
        print(f"  [{'OK' if r.status_code < 400 else 'FAIL'}] URL: {r.status_code}, M3U8: {is_m3u8}")
        r.close()
    except Exception as e:
        errors.append(f"Channel {idx}: URL error: {e}")

# Verify EPG
print(f"\n{'='*70}")
print("VERIFICACAO EPG")
print(f"{'='*70}")

epg_url = "https://epg.pw/xmltv/epg_US.xml.gz"
try:
    resp = requests.get(epg_url, timeout=30, headers={'Accept-Encoding': 'gzip'})
    resp.raise_for_status()
    xml_data = gzip.decompress(resp.content).decode('utf-8')
    root = ET.fromstring(xml_data)
    
    hoje = datetime.now().strftime("%Y%m%d")
    amanha = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
    depois = (datetime.now() + timedelta(days=2)).strftime("%Y%m%d")
    
    count_hoje = count_amanha = count_depois = 0
    channel_ids = {ch.get("id") for ch in root.findall("channel")}
    
    for prog in root.findall("programme"):
        start = prog.get("start", "")[:8]
        if start == hoje:
            count_hoje += 1
        elif start == amanha:
            count_amanha += 1
        elif start == depois:
            count_depois += 1
    
    print(f"[OK] Hoje: {count_hoje} programas")
    print(f"[OK] Amanha: {count_amanha} programas")
    print(f"[OK] Depois de amanha: {count_depois} programas")
    
    for info, url in channels:
        tvg_id = info.split('tvg-id="')[1].split('"')[0] if 'tvg-id=' in info else None
        if tvg_id and tvg_id in channel_ids:
            print(f"[OK] EPG channel {tvg_id} found")
        else:
            warnings.append(f"EPG channel {tvg_id} not found")
except Exception as e:
    errors.append(f"EPG error: {e}")

# Summary
print(f"\n{'='*70}")
print("RESUMO")
print(f"{'='*70}")
if errors:
    print(f"ERROS ({len(errors)}):")
    for e in errors:
        print(f"  - {e}")
else:
    print("[OK] No errors found!")

if warnings:
    print(f"\nAVISOS ({len(warnings)}):")
    for w in warnings:
        print(f"  - {w}")

print(f"\nTotal channels: {len(channels)}")
print("VALIDACAO COMPLETA!")
