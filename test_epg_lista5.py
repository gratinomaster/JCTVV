#!/usr/bin/env python3
"""Test EPG sources for lista5.m3u channels (US news) - coverage today/tomorrow/day-after."""
import requests, gzip, io
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

TARGETS = ["ABC News Live", "ABC News", "Fox News", "Fox Business", "CBS News", "CBSN"]
# search terms per channel target for display-name matching
SEARCH = {
    "ABCNewsLive": ["ABC News Live", "ABC News", "ABCNL"],
    "FoxNews": ["Fox News Channel", "Fox News"],
    "FoxBusiness": ["Fox Business"],
    "CBSNews": ["CBS News", "CBSN"],
}

SOURCES = [
    "https://iptv-epg.org/files/epg-us.xml.gz",
    "https://epg.pw/xmltv/epg_US.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_US1.xml.gz",
]

def fetch(url):
    r = requests.get(url, timeout=120, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    data = r.content
    try:
        if data[:2] == b"\x1f\x8b":
            data = gzip.decompress(data)
    except Exception:
        pass
    return data

def analyze(url):
    print(f"\n{'='*70}\nSOURCE: {url}\n{'='*70}")
    try:
        data = fetch(url)
        print(f"  Downloaded {len(data)} bytes")
        root = ET.fromstring(data)
        channels = {c.get("id"): c for c in root.findall("channel")}
        programmes = root.findall("programme")
        print(f"  Channels: {len(channels)}, Programmes: {len(programmes)}")

        today = datetime.now().strftime("%Y%m%d")
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
        dayafter = (datetime.now() + timedelta(days=2)).strftime("%Y%m%d")

        # map display names
        name_to_id = {}
        for cid, ch in channels.items():
            for dn in ch.findall("display-name"):
                nm = dn.text or ""
                name_to_id.setdefault(nm, []).append(cid)
                for key, terms in SEARCH.items():
                    for t in terms:
                        if t.lower() in nm.lower():
                            name_to_id.setdefault(key, []).append(cid)

        # count programmes per channel id per date
        prog = {}
        for p in programmes:
            cid = p.get("channel")
            start = p.get("start", "")[:8]
            prog.setdefault(cid, {"today": 0, "tomorrow": 0, "dayafter": 0})
            if start == today:
                prog[cid]["today"] += 1
            elif start == tomorrow:
                prog[cid]["tomorrow"] += 1
            elif start == dayafter:
                prog[cid]["dayafter"] += 1

        for key in SEARCH:
            ids = name_to_id.get(key, [])
            ids = list(dict.fromkeys(ids))[:10]
            print(f"\n  [{key}] matching IDs:")
            if not ids:
                print("    NONE")
            for cid in ids:
                pc = prog.get(cid, {})
                t = pc.get("today", 0); tm = pc.get("tomorrow", 0); da = pc.get("dayafter", 0)
                names = [dn.text for dn in channels[cid].findall("display-name")][:2]
                print(f"    {cid} | {names} | hoje={t} amanha={tm} depois={da}")
    except Exception as e:
        print(f"  ERROR: {e}")

for s in SOURCES:
    analyze(s)
