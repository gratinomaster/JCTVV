#!/usr/bin/env python3
import gzip, sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

EPG_FILE = "EPGFULL.xml.gz"

try:
    f = gzip.open(EPG_FILE, "rb")
except FileNotFoundError:
    print(f"ERROR: {EPG_FILE} not found!")
    sys.exit(1)

today = datetime.now(timezone.utc).strftime("%Y%m%d")
tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y%m%d")

channels = set()
today_progs = {}
tomorrow_progs = {}
total_progs = 0

for event, elem in ET.iterparse(f, events=("end",)):
    if elem.tag == "channel":
        cid = elem.get("id")
        if cid:
            channels.add(cid)
    elif elem.tag == "programme":
        ch = elem.get("channel", "")
        start = elem.get("start", "")
        total_progs += 1
        if start.startswith(today):
            today_progs.setdefault(ch, 0)
            today_progs[ch] += 1
        elif start.startswith(tomorrow):
            tomorrow_progs.setdefault(ch, 0)
            tomorrow_progs[ch] += 1
    elem.clear()
f.close()

print(f"File: {EPG_FILE}")
print(f"Channels: {len(channels)}")
print(f"Total programmes: {total_progs}")
print(f"Today ({today}): {sum(today_progs.values())} programmes across {len(today_progs)} channels")
print(f"Tomorrow ({tomorrow}): {sum(tomorrow_progs.values())} programmes across {len(tomorrow_progs)} channels")
print()

if not channels:
    print("FAIL: No channels found!")
    sys.exit(1)

if sum(today_progs.values()) == 0:
    print("FAIL: No programmes for today!")
    sys.exit(1)

if sum(tomorrow_progs.values()) == 0:
    print("FAIL: No programmes for tomorrow!")
    sys.exit(1)

print("PASS: EPG has programmes for today and tomorrow")

missing_today = sorted(channels - set(today_progs.keys()))
if missing_today:
    print(f"  Warning - channels with no programmes today: {missing_today}")

missing_tomorrow = sorted(channels - set(tomorrow_progs.keys()))
if missing_tomorrow:
    print(f"  Warning - channels with no programmes tomorrow: {missing_tomorrow}")

print("\nProgrammes per channel today:")
for ch in sorted(today_progs):
    print(f"  {ch}: {today_progs[ch]} programmes")

print("\nProgrammes per channel tomorrow:")
for ch in sorted(tomorrow_progs):
    print(f"  {ch}: {tomorrow_progs[ch]} programmes")
