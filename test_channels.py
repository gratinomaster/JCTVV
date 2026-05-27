#!/usr/bin/env python3
import re
import subprocess
import sys
import os

def parse_m3u(filepath):
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    if not lines or not lines[0].strip().startswith('#EXTM3U'):
        print("Invalid M3U file: missing #EXTM3U header", file=sys.stderr)
        sys.exit(1)
    
    header = lines[0]
    entries = []
    i = 1
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXTINF:'):
            extinf = lines[i]
            if i + 1 < len(lines):
                url = lines[i + 1]
                entries.append((extinf, url))
                i += 2
            else:
                i += 1
        else:
            i += 1
    
    return header, entries

def get_channel_name(extinf_line):
    match = re.search(r',([^,]+)$', extinf_line.strip())
    if match:
        return match.group(1).strip()
    return "Unknown"

def group_by_channel(entries):
    groups = {}
    for extinf, url in entries:
        name = get_channel_name(extinf)
        if name not in groups:
            groups[name] = []
        groups[name].append((extinf, url))
    return groups

def test_url(url, timeout=10):
    try:
        result = subprocess.run(
            ['curl', '-s', '-o', '/dev/null', '-w', '%{http_code}', '--max-time', str(timeout), url],
            capture_output=True, text=True, timeout=timeout + 5
        )
        http_code = result.stdout.strip()
        if http_code and http_code.startswith('2'):
            return True, http_code
        elif http_code:
            return False, http_code
        else:
            return False, 'no_response'
    except subprocess.TimeoutExpired:
        return False, 'timeout'
    except Exception as e:
        return False, str(e)

def main():
    input_file = 'lista5.m3u'
    header, entries = parse_m3u(input_file)
    groups = group_by_channel(entries)
    
    print(f"Found {len(groups)} unique channels, {len(entries)} total entries")
    
    working_channels = []
    for name, channel_entries in groups.items():
        test_url_str = channel_entries[0][1].strip()
        print(f"  Testing: {name[:50]}... ", end='', flush=True)
        ok, code = test_url(test_url_str)
        if ok:
            print(f"OK (HTTP {code})")
            working_channels.append((name, channel_entries))
        else:
            print(f"FAIL ({code})")
    
    print(f"\n{len(working_channels)}/{len(groups)} channels working")
    
    with open(input_file, 'w') as f:
        f.write(header)
        for name, channel_entries in working_channels:
            for extinf, url in channel_entries:
                f.write(extinf)
                f.write(url)
    
    print(f"Overwritten {input_file} with working channels")

if __name__ == '__main__':
    main()
