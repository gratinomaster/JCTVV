import subprocess
import re
import sys
import os

M3U_FILE = "lista5.m3u"
TIMEOUT = 15
MAX_CONCURRENT = 10

def read_m3u(path):
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    channels = []
    header = None
    if lines and lines[0].strip() == "#EXTM3U":
        header = lines[0].strip()
        lines = lines[1:]
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTINF:"):
            extinf = line
            if i + 1 < len(lines):
                url = lines[i + 1].strip()
                channels.append((extinf, url))
                i += 2
            else:
                i += 1
        else:
            i += 1
    
    return header, channels

def test_url(url, timeout=TIMEOUT):
    try:
        result = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", str(timeout), url],
            capture_output=True, text=True, timeout=timeout + 5
        )
        http_code = result.stdout.strip()
        return http_code == "200"
    except Exception:
        return False

def main():
    header, channels = read_m3u(M3U_FILE)
    if header is None:
        print("Invalid M3U file: missing #EXTM3U header")
        sys.exit(1)
    
    print(f"Found {len(channels)} channel entries to test")
    
    working_channels = []
    for i, (extinf, url) in enumerate(channels, 1):
        print(f"[{i}/{len(channels)}] Testing: {extinf[:60]}...", end=" ", flush=True)
        working = test_url(url)
        if working:
            print("OK")
            working_channels.append((extinf, url))
        else:
            print("DEAD")
    
    print(f"\nResults: {len(working_channels)}/{len(channels)} channels working")
    
    with open(M3U_FILE, "w", encoding="utf-8") as f:
        f.write(header + "\n")
        for extinf, url in working_channels:
            f.write(extinf + "\n")
            f.write(url + "\n")
    
    print(f"Overwrote {M3U_FILE} with {len(working_channels)} working channels")

if __name__ == "__main__":
    main()
