#!/usr/bin/env python3
import urllib.request
import os

EPG_SOURCES = [
    "https://epgshare01.online/epgshare01/epg_ripper_ALL_SOURCES1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_UK1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_IN1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_AU1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_FR1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_DE1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_ES1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_BR1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_KR1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_JP1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_TR1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_MX1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_IT1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_AR1.xml.gz",
    "https://fastly.jsdelivr.net/gh/limaalef/BrazilTVEPG@main/epg.xml",
    "https://raw.githubusercontent.com/matthuisman/i.mjh.nz/master/PlutoTV/us.xml",
]

def download(url, timeout=300):
    print(f"Baixando: {url.split('/')[-1]}", end=" ", flush=True)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
        if len(data) < 100:
            print(f"(pulado: {len(data)} bytes)")
            return None
        print(f"({len(data):,} bytes)")
        return data
    except Exception as e:
        print(f"(erro: {e})")
        return None

if __name__ == "__main__":
    print("Baixando fontes EPG...")
    for url in EPG_SOURCES:
        download(url)
