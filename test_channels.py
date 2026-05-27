#!/usr/bin/env python3
import subprocess
import sys
import os
import re
from urllib.parse import urlparse

def test_url(url, timeout=10):
    try:
        result = subprocess.run(
            ['curl', '-s', '-o', '/dev/null', '-w', '%{http_code}', '--max-time', str(timeout), '-L', url],
            capture_output=True,
            text=True,
            timeout=timeout + 5
        )
        code = result.stdout.strip()
        if code and code.startswith('2'):
            return True
        return False
    except Exception as e:
        return False

def parse_m3u(filepath):
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    channels = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXTM3U'):
            i += 1
            continue
        if line.startswith('#EXTINF:'):
            if i + 1 < len(lines):
                url = lines[i + 1].strip()
                channels.append({'extinf': line, 'url': url, 'line': i})
                i += 2
                continue
        i += 1
    
    return channels

def main():
    filepath = 'lista5.m3u'
    channels = parse_m3u(filepath)
    
    print(f"Found {len(channels)} entries in {filepath}")
    
    # Group by channel name
    groups = {}
    for ch in channels:
        name = ch['extinf']
        if name not in groups:
            groups[name] = []
        groups[name].append(ch)
    
    print(f"Found {len(groups)} unique channel names")
    
    working_names = []
    for name, entries in groups.items():
        first_url = entries[0]['url']
        working = test_url(first_url)
        status = "OK" if working else "FAIL"
        print(f"  [{status}] {name.split(',')[-1].strip()}")
        if working:
            working_names.append(name)
    
    # Filter channels to only working ones
    working_entries = []
    for ch in channels:
        if ch['extinf'] in working_names:
            working_entries.append(ch)
    
    print(f"\nWorking: {len(working_entries)}/{len(channels)} entries")
    
    # Write new M3U
    with open(filepath, 'w') as f:
        f.write('#EXTM3U\n')
        for ch in working_entries:
            f.write(ch['extinf'] + '\n')
            f.write(ch['url'] + '\n')

if __name__ == '__main__':
    main()
