#!/usr/bin/env python3
"""Add programme entries for June 20 and June 21 to the EPG XML for all channels."""

import xml.etree.ElementTree as ET

FILE = "/home/runner/work/JCTVV/JCTVV/lista5_epg_atualizado.xml"

tree = ET.parse(FILE)
root = tree.getroot()

namespaces = {"": "unknown"}  # no default ns; we use plain tags

# Extract per-channel programme pattern from existing entries.
# We look at the first full day's entries (June 17) for each channel.
channels = {}
for prog in root.findall("programme"):
    ch = prog.get("channel")
    start = prog.get("start")
    # Parse start time: e.g. "20260617T06000000 +0000"
    # We extract the time portion after T: HHMMSS
    time_part = start.split("T")[1].split(" ")[0]  # "06000000"
    title = prog.find("title").text
    desc = prog.find("desc").text
    duration_s = prog.get("stop")
    # Compute offset in hours: stop - start
    # start and stop have same format, so we can subtract
    start_h = int(time_part[:2])
    start_m = int(time_part[2:4])
    stop_time = duration_s.split("T")[1].split(" ")[0]
    stop_h = int(stop_time[:2])
    stop_m = int(stop_time[2:4])
    hours = (stop_h - start_h) % 24
    mins = (stop_m - start_m) % 60
    dur_hours = hours + mins / 60.0

    if ch not in channels:
        channels[ch] = {}
    # Use start hour as key
    channels[ch][start_h] = {
        "title": title,
        "desc": desc,
        "hours": dur_hours,
    }

# Sort each channel's schedule by start hour
for ch in channels:
    channels[ch] = dict(sorted(channels[ch].items()))

# Generate entries for June 20 and June 21
def make_time_str(date_str, hour):
    return f"{date_str}T{hour:02d}000000 +0000"

def make_stop_time_str(date_str, hour, add_hours):
    end_hour = (hour + add_hours) % 24
    end_day_offset = (hour + add_hours) // 24
    if end_day_offset > 0 and end_hour == 0:
        # special case: exactly midnight
        end_day_offset = (hour + add_hours) // 24
        end_hour = 0
    # Calculate the date for stop
    # If add_hours crosses midnight, we need to increment date
    from datetime import datetime, timedelta
    base = datetime.strptime(date_str, "%Y%m%d")
    stop_date = base + timedelta(days=end_day_offset)
    return f"{stop_date.strftime('%Y%m%d')}T{end_hour:02d}000000 +0000"

from datetime import datetime, timedelta

for date_str in ["20260620", "20260621"]:
    for ch, schedule in channels.items():
        for start_h, info in schedule.items():
            add_hours = int(info["hours"])
            start_time = make_time_str(date_str, start_h)
            stop_time = make_stop_time_str(date_str, start_h, add_hours)

            prog = ET.SubElement(root, "programme")
            prog.set("channel", ch)
            prog.set("start", start_time)
            prog.set("stop", stop_time)
            title_el = ET.SubElement(prog, "title")
            title_el.set("lang", "en")
            title_el.text = info["title"]
            desc_el = ET.SubElement(prog, "desc")
            desc_el.set("lang", "en")
            desc_el.text = info["desc"]

tree.write(FILE, encoding="UTF-8", xml_declaration=True)
print("Done. Updated EPG with June 20 and June 21 entries.")
