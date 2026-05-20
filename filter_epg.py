#!/usr/bin/env python3
"""Filter EPG XML to only include channels present in an M3U file."""
import re
import gzip
import sys
import tempfile
import os
import shutil

M3U_FILE = "/tmp/NEWSWORLDNOVOS.m3u"
OLD_EPG = "/home/runner/work/JCTV/JCTV/EPGFULL.xml.gz"
NEW_EPG = "/home/runner/work/JCTV/JCTV/EPGFULL.xml.gz"

tvg_ids = set()
with open(M3U_FILE, "r") as f:
    for line in f:
        for m in re.finditer(r'tvg-id="([^"]*)"', line):
            tid = m.group(1)
            if tid:
                tvg_ids.add(tid)

print(f"Found {len(tvg_ids)} unique tvg-id values in M3U", file=sys.stderr)

channel_ids_in_epg = set()
kept_channels = 0
kept_programmes = 0
skipped_channels = 0
skipped_programmes = 0

# Check if old EPG exists and has content
if not os.path.exists(OLD_EPG) or os.path.getsize(OLD_EPG) == 0:
    print(f"ERROR: Old EPG file {OLD_EPG} does not exist or is empty", file=sys.stderr)
    sys.exit(1)

# Read entire old EPG into memory first (it's ~1MB compressed, manageable)
with gzip.open(OLD_EPG, "rt", encoding="utf-8", errors="replace") as fin:
    old_content = fin.read()

print(f"Read {len(old_content)} bytes from EPG", file=sys.stderr)

# Write filtered content to temp file, then replace
tmp_fd, tmp_path = tempfile.mkstemp(suffix=".xml.gz", dir="/tmp")
os.close(tmp_fd)

try:
    with gzip.open(tmp_path, "wt", encoding="utf-8", errors="replace") as fout:
        in_channel = False
        keep_channel = False
        channel_buf = []

        in_programme = False
        keep_programme = False
        programme_buf = []

        for line in old_content.splitlines(keepends=True):
            if line.startswith("<?xml") or line.startswith("<tv>"):
                fout.write(line)
                continue
            if line.startswith("</tv>"):
                fout.write(line)
                break

            if not in_channel and not in_programme:
                cm = re.match(r'\s*<channel\s+id="([^"]+)"', line)
                if cm:
                    cid = cm.group(1)
                    in_channel = True
                    keep_channel = cid in tvg_ids
                    channel_buf = [line]
                    if keep_channel:
                        channel_ids_in_epg.add(cid)
                        kept_channels += 1
                    else:
                        skipped_channels += 1
                    continue

                pm = re.match(r'\s*<programme\s', line)
                if pm:
                    in_programme = True
                    chan_match = re.search(r'channel="([^"]+)"', line)
                    keep_programme = chan_match is not None and chan_match.group(1) in tvg_ids
                    programme_buf = [line]
                    if keep_programme:
                        kept_programmes += 1
                    else:
                        skipped_programmes += 1
                    continue

                fout.write(line)
                continue

            if in_channel:
                channel_buf.append(line)
                if "</channel>" in line:
                    in_channel = False
                    if keep_channel:
                        fout.writelines(channel_buf)
                    channel_buf = []
                continue

            if in_programme:
                programme_buf.append(line)
                if "</programme>" in line:
                    in_programme = False
                    if keep_programme:
                        fout.writelines(programme_buf)
                    programme_buf = []
                continue

    shutil.move(tmp_path, NEW_EPG)
    print(f"Moved temp file to {NEW_EPG}", file=sys.stderr)

except Exception as e:
    if os.path.exists(tmp_path):
        os.unlink(tmp_path)
    print(f"ERROR: {e}", file=sys.stderr)
    sys.exit(1)

print(f"Kept {kept_channels} channels, skipped {skipped_channels}", file=sys.stderr)
print(f"Kept {kept_programmes} programmes, skipped {skipped_programmes}", file=sys.stderr)
print(f"Channel IDs in both M3U and EPG: {len(channel_ids_in_epg)}", file=sys.stderr)

missing = tvg_ids - channel_ids_in_epg
if missing:
    print(f"Channels in M3U but NOT in EPG ({len(missing)}):", file=sys.stderr)
    for m in sorted(missing):
        print(f"  {m}", file=sys.stderr)

# Restore backup if available
bak_file = "/home/runner/work/JCTV/JCTV/EPGFULL.xml.gz.bak"
if not os.path.exists(OLD_EPG) or os.path.getsize(OLD_EPG) == 0:
    if os.path.exists(bak_file):
        print(f"Restoring from backup {bak_file}", file=sys.stderr)
        shutil.copy2(bak_file, OLD_EPG)
