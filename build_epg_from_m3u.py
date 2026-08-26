#!/usr/bin/env python3
"""Download EPG data from multiple sources, filter to M3U channels, create EPGFULL.xml.gz"""

import re
import os
import gzip
import copy
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from io import BytesIO

M3U_URL = "https://github.com/gratinomaster/JCTV/raw/refs/heads/main/NEWSWORLDNOVOS.m3u"
M3U_FILE = "NEWSWORLDNOVOS.m3u"
OUTPUT_XML = "EPGFULL.xml"
OUTPUT_GZ = "EPGFULL.xml.gz"

EPG_SOURCES = [
    ("https://epgshare01.online/epgshare01/epg_ripper_ALL_SOURCES1.xml.gz", "gz"),
    ("https://iptv-epg.org/files/epg-ar.xml.gz", "gz"),
    ("https://iptv-epg.org/files/epg-mx.xml.gz", "gz"),
    ("https://iptv-epg.org/files/epg-cl.xml.gz", "gz"),
    ("https://iptv-epg.org/files/epg-ve.xml.gz", "gz"),
    ("https://iptv-epg.org/files/epg-br.xml.gz", "gz"),
    ("https://iptv-epg.org/files/epg-us.xml.gz", "gz"),
    ("https://iptv-epg.org/files/epg-il.xml.gz", "gz"),
    ("https://iptv-epg.org/files/epg-pt.xml.gz", "gz"),
    ("https://iptv-epg.org/files/epg-fr.xml.gz", "gz"),
    ("https://epg.pw/xmltv/epg_BR.xml.gz", "gz"),
    ("https://fastly.jsdelivr.net/gh/limaalef/BrazilTVEPG@main/epg.xml", "xml"),
    ("https://raw.githubusercontent.com/matthuisman/i.mjh.nz/master/PlutoTV/us.xml", "xml"),
]


def download_m3u():
    print("Downloading M3U file...")
    if os.path.exists(M3U_FILE):
        with open(M3U_FILE, "r", encoding="utf-8") as f:
            content = f.read()
        print(f"  Using local M3U file")
    else:
        req = urllib.request.Request(M3U_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read().decode("utf-8")
        with open(M3U_FILE, "w", encoding="utf-8") as f:
            f.write(content)
    tvg_ids = set()
    for match in re.finditer(r'tvg-id="([^"]+)"', content):
        tvg_ids.add(match.group(1))
    print(f"  Found {len(tvg_ids)} unique tvg-ids")
    return tvg_ids


def normalize_id(channel_id):
    return re.sub(r'[^a-z0-9]', '', channel_id.lower())


EXTRA_MAPPINGS = {
    "tviiptv": "TVI.HD.pt", "tvirealityiptv": "TVI.Reality.HD.pt",
    "tvihdpt": "TVI.HD.pt", "tvirealityhdpt": "TVI.Reality.HD.pt",
    "telefe": "Telefe.ar", "telefear": "Telefe.ar",
    "canaltelefeargentinaar": "Canal.Telefé.(Argentina).ar",
    "canaltelefe": "Canal.Telefé.(Argentina).ar",
    "cbseastwcbsus": "CBS.Streaming.SD.East.feed.us2",
    "cbseastus": "CBS.Streaming.SD.East.feed.us2",
    "cbsus": "CBS.Streaming.SD.East.feed.us2",
    "bigbrotherpluto": "BigBrother.us",
    "bigbrother247plutotv": "BigBrother.us",
    "telemundoeastus": "Telemundo.mx",
    "telemundous": "NoticiasTelemundoAHORA.us",
    "tmcfr": "TMC.fr", "tmc": "TMC.fr",
    "redevidabr": "Rede.Vida.br", "redevida": "Rede.Vida.br",
    "aljazeeraenglish": "AlJazeera.Arabic.net",
    "france24espanol": "France24enEspanol.ar",
    "tviusa": "TVI.HD.pt", "tvirealityusa": "TVI.Reality.HD.pt",
    "tvchilecl": "TVChile.cl",
    "teleformulamx": "TeleFormula.mx",
}


def resolve_ch_id(ch_id, m3u_ids, id_mapping):
    if ch_id in m3u_ids:
        return ch_id
    norm = normalize_id(ch_id)
    if norm in id_mapping:
        return id_mapping[norm]
    if norm in EXTRA_MAPPINGS:
        real_id = EXTRA_MAPPINGS[norm]
        if real_id in m3u_ids:
            return real_id
    return None


def parse_epg_chunks(xml_data, m3u_ids, id_mapping, existing_channels):
    channels_found = {}
    programmes_found = []
    context = ET.iterparse(BytesIO(xml_data), events=("start", "end"))

    for event, elem in context:
        if event == "end":
            if elem.tag == "channel":
                ch_id = elem.get("id", "")
                real_id = resolve_ch_id(ch_id, m3u_ids, id_mapping)
                if real_id and real_id not in existing_channels:
                    # Serialize to string, then parse to get independent element
                    ch_str = ET.tostring(elem, encoding="unicode")
                    new_elem = ET.fromstring(ch_str)
                    new_elem.set("id", real_id)  # Ensure correct ID
                    channels_found[real_id] = new_elem
                    existing_channels.add(real_id)
                elem.clear()
            elif elem.tag == "programme":
                ch = elem.get("channel", "")
                real_id = resolve_ch_id(ch, m3u_ids, id_mapping)
                if real_id:
                    prog_str = ET.tostring(elem, encoding="unicode")
                    prog = ET.fromstring(prog_str)
                    prog.set("channel", real_id)
                    programmes_found.append(prog)
                elem.clear()

    return channels_found, programmes_found


def filter_programmes_by_date(programmes, max_days=2):
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(days=max_days)
    cutoff_past = now - timedelta(days=1)
    filtered = []
    for prog in programmes:
        start_str = prog.get("start", "")
        try:
            dt = datetime.strptime(start_str[:14], "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
            if cutoff_past <= dt <= cutoff:
                filtered.append(prog)
        except:
            filtered.append(prog)
    return filtered


def build_epg_xml(channels, programmes):
    lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    lines.append('<tv generator-info-name="JCTVV EPG Builder">')
    for ch_id in sorted(channels.keys()):
        lines.append(ET.tostring(channels[ch_id], encoding="unicode"))
    programmes.sort(key=lambda p: p.get("start", ""))
    for prog in programmes:
        lines.append(ET.tostring(prog, encoding="unicode"))
    lines.append("</tv>")
    return "\n".join(lines)


def main():
    print("=" * 60)
    print("EPGFULL.xml.gz Builder (v2 - fixed channel IDs)")
    print("=" * 60)

    m3u_ids = download_m3u()
    id_mapping = {normalize_id(tid): tid for tid in m3u_ids}

    all_channels = {}
    all_programmes = []
    existing_channel_ids = set()

    for url, fmt in EPG_SOURCES:
        print(f"\n--- {url.split('/')[-1]} ---")
        xml_data = download_epg_source(url, fmt)
        if xml_data is None:
            continue

        channels, programmes = parse_epg_chunks(xml_data, m3u_ids, id_mapping, existing_channel_ids)
        all_channels.update(channels)
        all_programmes.extend(programmes)

        missing = m3u_ids - set(all_channels.keys())
        print(f"    Matched: {len(channels)} ch, {len(programmes)} prog | Total: {len(all_channels)}/{len(m3u_ids)}")
        if not missing:
            print("  All channels matched!")
            break

    print(f"\nFiltering programmes (today + tomorrow)...")
    all_programmes = filter_programmes_by_date(all_programmes, max_days=2)
    print(f"  Programmes: {len(all_programmes)}")

    xml_content = build_epg_xml(all_channels, all_programmes)

    with open(OUTPUT_XML, "w", encoding="utf-8") as f:
        f.write(xml_content)
    with gzip.open(OUTPUT_GZ, "wb", compresslevel=9) as f:
        f.write(xml_content.encode("utf-8"))
    gz_size = os.path.getsize(OUTPUT_GZ)

    print(f"\n{'='*60}")
    print(f"OUTPUT: {OUTPUT_GZ} ({gz_size/1024:.1f} KB)")
    print(f"Channels: {len(all_channels)}, Programmes: {len(all_programmes)}")
    missing = sorted(m3u_ids - set(all_channels.keys()))
    print(f"Missing ({len(missing)}): {', '.join(missing)}")


def download_epg_source(url, fmt):
    print(f"  Downloading: {url[:80]}...")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw_data = resp.read()
        if fmt == "gz":
            data = gzip.decompress(raw_data)
        else:
            data = raw_data
        print(f"    Size: {len(data)/1024/1024:.1f} MB")
        return data
    except Exception as e:
        print(f"    FAILED: {e}")
        return None


if __name__ == "__main__":
    main()
