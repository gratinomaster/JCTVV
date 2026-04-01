#!/usr/bin/env python3
import requests
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import hashlib
import re

EPG_SOURCES = {
    "ABC News Live": {
        "channel_id": "408627",
        "tvg_id": "abcnews.us",
        "epg_url": "https://epg.pw/api/epg.xml",
    },
    "Fox News": {
        "channel_id": "369713",
        "tvg_id": "foxnews.us",
        "epg_url": "https://epg.pw/api/epg.xml",
    },
    "Fox Business": {
        "channel_id": "369713",
        "tvg_id": "foxbusiness.us",
        "epg_url": "https://epg.pw/api/epg.xml",
    },
    "CBS News": {
        "channel_id": "464941",
        "tvg_id": "cbsnews.us",
        "epg_url": "https://epg.pw/api/epg.xml",
    },
}

def fetch_epg(channel_id):
    url = f"https://epg.pw/api/epg.xml?channel_id={channel_id}"
    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            return response.text
    except Exception as e:
        print(f"Error fetching EPG: {e}")
    return None

def check_programming(epg_xml, days_ahead=0):
    if not epg_xml:
        return False, []
    
    try:
        root = ET.fromstring(epg_xml)
        target_date = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y%m%d")
        programs = []
        
        programmes = []
        for programme in root.findall(".//programme"):
            start_time = programme.get("start", "")[:8]
            prog_date = start_time[:8] if start_time else ""
            if prog_date == target_date:
                title = programme.find("title")
                prog_title = title.text if title is not None else "Unknown"
                programmes.append((start_time, prog_title))
        
        return len(programmes) > 0, programmes
    except Exception as e:
        print(f"Error parsing EPG: {e}")
        return False, []

def get_virustotal_verdict(url):
    url_hash = hashlib.md5(url.encode()).hexdigest()
    api_url = f"https://www.virustotal.com/api/v3/urls/{url_hash}"
    headers = {"x-apikey": "YOUR_VIRUSTOTAL_API_KEY"}
    try:
        response = requests.get(api_url, headers=headers, timeout=30)
        if response.status_code == 200:
            data = response.json()
            stats = data.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
            malicious = stats.get("malicious", 0)
            suspicious = stats.get("suspicious", 0)
            if malicious > 0 or suspicious > 0:
                return False, f"Malicious: {malicious}, Suspicious: {suspicious}"
            return True, "Clean"
        elif response.status_code == 404:
            return None, "Not found in VT database"
    except Exception as e:
        print(f"VT Error: {e}")
    return None, "Could not check"

def check_url_with_virustotal(url):
    api_url = "https://www.virustotal.com/api/v3/urls"
    headers = {"x-apikey": "YOUR_VIRUSTOTAL_API_KEY", "Content-Type": "application/x-www-form-urlencoded"}
    try:
        response = requests.post(api_url, headers=headers, data=f"url={url}", timeout=60)
        if response.status_code == 200:
            result = response.json()
            analysis_url = result.get("data", {}).get("links", {}).get("self")
            if analysis_url:
                import time
                time.sleep(2)
                analysis = requests.get(analysis_url, headers=headers, timeout=30)
                if analysis.status_code == 200:
                    data = analysis.json()
                    stats = data.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
                    malicious = stats.get("malicious", 0)
                    suspicious = stats.get("suspicious", 0)
                    harmless = stats.get("harmless", 0)
                    undetected = stats.get("undetected", 0)
                    total = malicious + suspicious + harmless + undetected
                    if total > 0:
                        threat_score = (malicious + suspicious) / total * 100
                        if malicious > 0:
                            return False, f"Malicious: {malicious}/{total}"
                        elif suspicious > 0:
                            return None, f"Suspicious: {suspicious}/{total}"
                        else:
                            return True, f"Clean: {harmless}/{total}"
    except Exception as e:
        print(f"VT Error: {e}")
    return None, "Could not check"

def test_epg_for_channel(channel_name, channel_id, days_ahead=0):
    epg_xml = fetch_epg(channel_id)
    if epg_xml:
        has_prog, programmes = check_programming(epg_xml, days_ahead)
        return has_prog, programmes
    return False, []

def main():
    print("=" * 60)
    print("Testing EPG for lista5.m3u channels")
    print("=" * 60)
    
    today = datetime.now()
    tomorrow = today + timedelta(days=1)
    day_after = today + timedelta(days=2)
    
    print(f"\nToday: {today.strftime('%Y-%m-%d')}")
    print(f"Tomorrow: {tomorrow.strftime('%Y-%m-%d')}")
    print(f"Day after: {day_after.strftime('%Y-%m-%d')}")
    
    for name, info in EPG_SOURCES.items():
        print(f"\n{'='*60}")
        print(f"Testing: {name} (ID: {info['channel_id']})")
        print(f"tvg-id: {info['tvg_id']}")
        
        has_today, prog_today = test_epg_for_channel(name, info['channel_id'], 0)
        has_tomorrow, prog_tomorrow = test_epg_for_channel(name, info['channel_id'], 1)
        has_day_after, prog_day_after = test_epg_for_channel(name, info['channel_id'], 2)
        
        print(f"\nToday ({today.strftime('%Y-%m-%d')}): {'OK' if has_today else 'NO PROGRAMS'}")
        if prog_today:
            for time, title in prog_today[:3]:
                print(f"  {time} - {title}")
        
        print(f"Tomorrow ({tomorrow.strftime('%Y-%m-%d')}): {'OK' if has_tomorrow else 'NO PROGRAMS'}")
        if prog_tomorrow:
            for time, title in prog_tomorrow[:3]:
                print(f"  {time} - {title}")
        
        print(f"Day after ({day_after.strftime('%Y-%m-%d')}): {'OK' if has_day_after else 'NO PROGRAMS'}")
        if prog_day_after:
            for time, title in prog_day_after[:3]:
                print(f"  {time} - {title}")
        
        epg_xml = fetch_epg(info['channel_id'])
        print(f"\nEPG XML Available: {'Yes' if epg_xml else 'No'}")
        
        if epg_xml:
            print(f"EPG URL: https://epg.pw/api/epg.xml?channel_id={info['channel_id']}")
            print(f"M3U EPG attribute: tvg-id=\"{info['tvg_id']}\" tvg-url=\"https://epg.pw/api/epg.xml?channel_id={info['channel_id']}\"")

if __name__ == "__main__":
    main()
