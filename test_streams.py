#!/usr/bin/env python3
import re
import subprocess
import sys
from pathlib import Path

M3U_FILE = '/home/runner/work/JCTVV/JCTVV/lista5.m3u'

def test_url(url):
    try:
        # Test with curl
        result = subprocess.run(
            ['curl', '-sI', '--connect-timeout', '10', '-L', url],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=15
        )
        # Check status code
        output = result.stdout.decode('utf-8', errors='ignore')
        # Look for HTTP status
        for line in output.splitlines():
            if line.startswith('HTTP/'):
                if '200' in line or '206' in line or '302' in line:
                    return True
                else:
                    return False
        return False
    except Exception as e:
        return False

def process():
    with open(M3U_FILE, 'r') as f:
        content = f.read()
    
    lines = content.splitlines()
    new_lines = []
    i = 0
    removed = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith('#EXTM3U'):
            new_lines.append(line)
            i += 1
            continue
        if line.startswith('#EXTINF'):
            # Look ahead for URL
            if i + 1 < len(lines):
                url = lines[i + 1].strip()
                if url and not url.startswith('#'):
                    print(f'Testing: {url[:80]}...')
                    if test_url(url):
                        new_lines.append(line)
                        new_lines.append(lines[i + 1])
                        i += 2
                        continue
                    else:
                        print(f'  FAILED - removing')
                        removed += 1
                        i += 2
                        continue
            new_lines.append(line)
            i += 1
            continue
        new_lines.append(line)
        i += 1
    
    with open(M3U_FILE, 'w') as f:
        f.write('\n'.join(new_lines) + '\n')
    
    print(f'Removed {removed} failed streams')

if __name__ == '__main__':
    process()
