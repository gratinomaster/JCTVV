#!/usr/bin/env python3
import subprocess
import sys
import re
import time
from collections import OrderedDict

INPUT = "lista5.m3u"
OUTPUT = "lista5.m3u"

def parse_m3u(path):
    channels = []  # each: {"extinf": line, "urls": [ ... ]}
    with open(path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()

    cur_extinf = None
    cur_urls = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("#EXTM3U"):
            continue
        if line.startswith("#EXTINF:"):
            if cur_extinf is not None:
                channels.append({"extinf": cur_extinf, "urls": cur_urls})
            cur_extinf = line
            cur_urls = []
        elif line.startswith(("http://", "https://")):
            cur_urls.append(line)
        else:
            # other comment lines, ignore
            continue
    if cur_extinf is not None:
        channels.append({"extinf": cur_extinf, "urls": cur_urls})
    return channels

def test_url(url, timeout=15):
    cmd = [
        "curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
        "--connect-timeout", "8", "--max-time", str(timeout), "-L", url
    ]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
        code = out.stdout.strip()
        if code in ("200", "206"):
            return True, code
        return False, code
    except Exception as e:
        return False, str(e)

def channel_name(extinf):
    # name is after last comma
    return extinf.split(",")[-1].strip()

def main():
    channels = parse_m3u(INPUT)
    total = len(channels)
    print(f"Total de canais/grupos: {total}")
    print("=" * 70)

    kept_channels = []
    removed = []
    for idx, ch in enumerate(channels, 1):
        name = channel_name(ch["extinf"])
        # Test all urls in the channel group; keep if at least one works
        results = []
        working = False
        for url in ch["urls"]:
            ok, code = test_url(url)
            results.append((url, ok, code))
            if ok:
                working = True

        status = "OK " if working else "FAIL"
        good_urls = [r[0] for r in results if r[1]]
        print(f"[{idx}/{total}] {status} {name} ({len(good_urls)}/{len(ch['urls'])} urls ok)")

        if working:
            kept_channels.append({"extinf": ch["extinf"], "urls": good_urls})
        else:
            removed.append({"extinf": ch["extinf"], "urls": ch["urls"]})

    print("=" * 70)
    print(f"Canais OK: {len(kept_channels)}/{total}")
    print(f"Canais removidos (falha): {len(removed)}")
    removed_names = [channel_name(r["extinf"]) for r in removed]
    for n in removed_names:
        print(f"  - {n}")

    # Write output
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for ch in kept_channels:
            f.write(ch["extinf"] + "\n")
            for url in ch["urls"]:
                f.write(url + "\n")

    print(f"\nEscrito em {OUTPUT}")

if __name__ == "__main__":
    main()
