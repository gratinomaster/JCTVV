#!/usr/bin/env python3
import concurrent.futures
import requests
import sys

def test_channel(url, timeout=10):
    try:
        response = requests.head(url, timeout=timeout, allow_redirects=True)
        return response.status_code == 200
    except:
        try:
            response = requests.get(url, timeout=timeout, stream=True)
            return response.status_code == 200
        except:
            return False

def parse_m3u(filename):
    channels = []
    current_extinf = None
    
    with open(filename, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line.startswith('#EXTINF'):
                current_extinf = line
            elif line and not line.startswith('#'):
                if current_extinf:
                    channels.append((current_extinf, line))
                    current_extinf = None
    return channels

def main():
    input_file = '/home/runner/work/JCTV/JCTV/lista5.m3u'
    channels = parse_m3u(input_file)
    
    print(f"Testing {len(channels)} channels...")
    
    working = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        future_to_channel = {executor.submit(test_channel, url): (extinf, url) 
                           for extinf, url in channels}
        
        for i, future in enumerate(concurrent.futures.as_completed(future_to_channel)):
            extinf, url = future_to_channel[future]
            try:
                is_working = future.result()
                if is_working:
                    working.append((extinf, url))
                    print(f"✓ Working: {extinf[:60]}...")
                else:
                    print(f"✗ Failed: {extinf[:60]}...")
            except:
                print(f"✗ Error: {extinf[:60]}...")
    
    print(f"\nResults: {len(working)} working, {len(channels) - len(working)} failed")
    
    with open(input_file, 'w', encoding='utf-8') as f:
        f.write('#EXTM3U\n')
        for extinf, url in working:
            f.write(extinf + '\n')
            f.write(url + '\n')
    
    print(f"Updated {input_file}")

if __name__ == '__main__':
    main()
