#!/usr/bin/env python3
"""Test multiple EPG sources for US news channels"""
import requests
import gzip
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

EPG_SOURCES = [
    ("https://epg.pw/xmltv/epg_US.xml.gz", "EPG.pw US"),
    ("https://epg.pw/xmltv/epg.xml.gz", "EPG.pw Global"),
    ("https://xmltv.tvtome.press/xmltv.xml.gz", "TV Tome"),
    ("https://raw.githubusercontent.com/EPGProviders/xmltv/main/guide.xml.gz", "GitHub EPG"),
    ("https://epg.112114.xyz/epg.xml.gz", "112114 EPG"),
    ("https://raw.githubusercontent.com/AqFad2811/epg/main/epg.xml.gz", "AqFad EPG"),
    ("https://epg-guide.com/epg.xml.gz", "EPG Guide"),
    ("https://iptv.epgshare01.online/epg_share01_epg.xml.gz", "EPG Share01"),
]

CHANNELS_TO_FIND = ["ABC News", "Fox News", "Fox Business", "CBS News"]

def test_epg(url, name):
    print(f"\n{'='*60}")
    print(f"Testing: {name}")
    print(f"URL: {url}")
    print(f"{'='*60}")
    try:
        resp = requests.get(url, timeout=30, headers={'User-Agent': 'Mozilla/5.0', 'Accept-Encoding': 'gzip'})
        resp.raise_for_status()
        print(f"  HTTP Status: {resp.status_code}, Size: {len(resp.content)} bytes")

        try:
            xml_data = gzip.decompress(resp.content).decode('utf-8')
        except:
            xml_data = resp.text

        root = ET.fromstring(xml_data)
        channels = root.findall("channel")
        programmes = root.findall("programme")
        print(f"  Channels: {len(channels)}, Programmes: {len(programmes)}")

        hoje = datetime.now().strftime("%Y%m%d")
        amanha = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
        depois = (datetime.now() + timedelta(days=2)).strftime("%Y%m%d")

        count_hoje = count_amanha = count_depois = 0
        found_channels = []

        for ch in channels:
            ch_id = ch.get("id", "")
            display = ch.find("display-name")
            ch_name = display.text if display is not None else ch_id
            for target in CHANNELS_TO_FIND:
                if target.lower() in ch_name.lower():
                    found_channels.append((ch_id, ch_name))

        for prog in programmes:
            start = prog.get("start", "")[:8]
            if start == hoje:
                count_hoje += 1
            elif start == amanha:
                count_amanha += 1
            elif start == depois:
                count_depois += 1

        print(f"  Programmes - Hoje: {count_hoje}, Amanhã: {count_amanha}, Depois: {count_depois}")
        if found_channels:
            print(f"  MATCHED CHANNELS:")
            for ch_id, ch_name in found_channels:
                print(f"    ID: {ch_id} | Name: {ch_name}")
        
        has_prog = count_hoje > 0 and count_amanha > 0
        return {"ok": has_prog, "channels": found_channels, "hoje": count_hoje, "amanha": count_amanha, "depois": count_depois, "name": name, "url": url}
    except Exception as e:
        print(f"  ERROR: {e}")
        return {"ok": False, "error": str(e), "name": name, "url": url}

if __name__ == "__main__":
    results = []
    for url, name in EPG_SOURCES:
        r = test_epg(url, name)
        results.append(r)

    print(f"\n\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for r in results:
        status = "OK" if r.get("ok") else "FAIL"
        print(f"  [{status}] {r['name']}: {r.get('channels', [])}")
