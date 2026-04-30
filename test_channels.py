#!/usr/bin/env python3
import requests
import time

def test_m3u_channels(input_file):
    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    working_lines = []
    i = 0
    total_channels = 0
    working_channels = 0

    while i < len(lines):
        line = lines[i].strip()

        if line.startswith('#EXTM3U'):
            working_lines.append(line + '\n')
            i += 1
            continue

        if line.startswith('#EXTINF'):
            total_channels += 1
            if i + 1 < len(lines):
                url = lines[i + 1].strip()
                print(f"Testing channel {total_channels}: {line[8:50]}...")

                try:
                    response = requests.head(url, timeout=10, allow_redirects=True)
                    if response.status_code == 200:
                        print(f"  ✓ Working (HTTP {response.status_code})")
                        working_lines.append(line + '\n')
                        working_lines.append(url + '\n')
                        working_channels += 1
                    else:
                        print(f"  ✗ Failed (HTTP {response.status_code})")
                except Exception as e:
                    print(f"  ✗ Failed: {str(e)[:50]}")

                i += 2
            else:
                i += 1
        else:
            i += 1

    print(f"\nResults: {working_channels}/{total_channels} channels working")
    return working_lines

if __name__ == '__main__':
    input_file = '/home/runner/work/JCTV/JCTV/lista5.m3u'
    output_file = '/home/runner/work/JCTV/JCTV/lista5.m3u'

    print("Testing M3U channels...")
    working_lines = test_m3u_channels(input_file)

    with open(output_file, 'w', encoding='utf-8') as f:
        f.writelines(working_lines)

    print(f"\nFile updated: {output_file}")
