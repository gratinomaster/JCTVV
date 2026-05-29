#!/usr/bin/env python3
import re

INPUT = "lista5.m3u"

def parse_m3u(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    header = None
    entries = []
    current_extinf = None
    for line in lines:
        s = line.strip()
        if s.startswith('#EXTM3U'):
            header = line
        elif s.startswith('#EXTINF:'):
            current_extinf = s
        elif s and not s.startswith('#') and current_extinf:
            entries.append((current_extinf, s))
            current_extinf = None
    if not header:
        header = '#EXTM3U\n'
    return header, entries

header, entries = parse_m3u(INPUT)

seen = {}
deduped = []
for extinf, url in entries:
    name = extinf.split(',')[-1].strip()
    if name not in seen:
        seen[name] = True
        deduped.append((extinf, url))

with open(INPUT, 'w', encoding='utf-8') as f:
    f.write(header.rstrip('\n') + '\n')
    for extinf, url in deduped:
        f.write(extinf + '\n')
        f.write(url + '\n')

print(f"Original: {len(entries)} entries -> Deduplicated: {len(deduped)} unique channels")
for extinf, url in deduped:
    name = extinf.split(',')[-1].strip()
    print(f"  - {name}")
