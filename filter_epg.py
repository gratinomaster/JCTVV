#!/usr/bin/env python3
"""Build EPGFULL.xml.gz from epgshare01, matching channels by ID and display name."""

import re, gzip, io, sys, subprocess

M3U_FILE = "/tmp/NEWSWORLDNOVOS.m3u"
OUTPUT_FILE = "EPGFULL.xml.gz"
EPG_URL = "https://epgshare01.online/epgshare01/epg_ripper_ALL_SOURCES1.xml.gz"

# --- Read M3U channel info ---
m3u_by_id = {}       # tvg-id -> cleaned display name
m3u_by_name = {}     # cleaned display name -> tvg-id
m3u_ids = set()

with open(M3U_FILE) as f:
    for line in f:
        m = re.search(r'tvg-id="([^"]*)"', line)
        if m and ',' in line:
            tid = m.group(1)
            name = line.rsplit(',', 1)[1].strip()
            name = re.sub(r'\s*\(\d+p\)', '', name)
            name = re.sub(r'\s*\[.*?\]', '', name)
            name = re.sub(r'\s*tvg-logo=".*?"', '', name)
            name = re.sub(r'&amp;', '&', name).strip()
            m3u_by_id[tid] = name
            m3u_by_name[name.lower()] = tid
            m3u_ids.add(tid)

print(f"M3U: {len(m3u_ids)} unique tvg-ids", file=sys.stderr)

# --- Stream process epgshare01 ---
# We'll build a mapping: epg_channel_id -> m3u_tvg_id
id_map = {}  # epg_share_id -> m3u_tvg_id

channel_count = 0
programme_count = 0
written_ids = set()

out = gzip.open(OUTPUT_FILE, "wt", encoding="utf-8")
out.write('<?xml version="1.0" encoding="utf-8"?>\n')
out.write("<tv>\n")

def normalize_name(n):
    return re.sub(r'[^a-z0-9]', '', n.lower())

print("Streaming epgshare01 and filtering...", file=sys.stderr)

proc = subprocess.Popen(
    ["curl", "-sL", EPG_URL],
    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
)
gz_file = gzip.GzipFile(fileobj=proc.stdout)

ch_names_seen = {}  # epg_id -> display_name (for logging)

# We need to track what epg IDs map to what M3U IDs for programme rewriting
# Since channels come first in the file, we can build the map as we go

in_channel = False
in_programme = False
keep = False
current_lines = []
current_tag = ""
current_epg_id = ""
buffer = []  # buffer for current element

for line_bytes in gz_file:
    line = line_bytes.decode("utf-8", errors="replace")

    if "<tv>" in line or "<?xml" in line:
        continue

    # --- Channel start ---
    chm = re.search(r'<channel\s+id="([^"]*)"', line)
    if chm:
        in_channel = True
        current_tag = "channel"
        current_epg_id = chm.group(1)
        keep = False
        buffer = [line]
        continue

    if in_channel:
        if "</channel>" in line:
            buffer.append(line)
            # Check if this channel matches an M3U channel
            ch_text = "".join(buffer)
            dn = re.search(r'<display-name[^>]*>(.*?)</display-name>', ch_text)
            dn_name = dn.group(1).strip() if dn else ""
            
            matched_m3u_id = None
            
            # 1. Exact ID match
            if current_epg_id in m3u_ids:
                matched_m3u_id = current_epg_id
            
            # 2. Name match
            if not matched_m3u_id and dn_name:
                dn_lower = dn_name.lower().strip()
                dn_norm = normalize_name(dn_name)
                
                # Exact name match
                if dn_lower in m3u_by_name:
                    matched_m3u_id = m3u_by_name[dn_lower]
                
                # Normalized match
                if not matched_m3u_id:
                    for m3u_name, m3u_tid in m3u_by_name.items():
                        m3u_norm = normalize_name(m3u_name)
                        if dn_norm == m3u_norm:
                            matched_m3u_id = m3u_tid
                            break
                
                # Partial: if M3U name is contained in EPG display name or vice versa
                # Minimum 5 chars for the shorter
                if not matched_m3u_id:
                    for m3u_name, m3u_tid in m3u_by_name.items():
                        if len(m3u_name) >= 5 and len(dn_lower) >= 5:
                            if m3u_name in dn_lower or dn_lower in m3u_name:
                                # Avoid very generic matches
                                matched_m3u_id = m3u_tid
                                break

            if matched_m3u_id and matched_m3u_id not in written_ids:
                id_map[current_epg_id] = matched_m3u_id
                written_ids.add(matched_m3u_id)
                ch_text = "".join(buffer)
                ch_text = ch_text.replace(f'id="{current_epg_id}"', f'id="{matched_m3u_id}"', 1)
                out.write(ch_text)
                channel_count += 1

            in_channel = False
            buffer = []
        else:
            buffer.append(line)
        continue

    # --- Programme start ---
    pm = re.search(r'<programme\s+[^>]*channel="([^"]*)"', line)
    if pm:
        in_programme = True
        current_tag = "programme"
        current_epg_id = pm.group(1)
        keep = current_epg_id in id_map
        buffer = [line]
        continue

    if in_programme:
        if "</programme>" in line:
            buffer.append(line)
            if current_epg_id in id_map:
                m3u_id = id_map[current_epg_id]
                for l in buffer:
                    out.write(l.replace(f'channel="{current_epg_id}"', f'channel="{m3u_id}"'))
                programme_count += 1
            in_programme = False
            buffer = []
        else:
            buffer.append(line)
        continue

proc.wait()

out.write("</tv>\n")
out.close()

import os
size = os.path.getsize(OUTPUT_FILE)
print(f"\nFinal: {channel_count} channels, {programme_count} programmes -> {OUTPUT_FILE} ({size} bytes)", file=sys.stderr)
print(f"ID map size: {len(id_map)}", file=sys.stderr)
