#!/usr/bin/env python3
"""Re-test HLS with curl without -r, checking variant/full playlists and media."""
import re
import subprocess
import concurrent.futures
from urllib.parse import urljoin

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
REF = "https://www.google.com/"


def curl(url, max_time=25, headers=True):
    cmd = ["curl", "-sL", "--max-time", str(max_time), "-A", UA]
    if headers:
        cmd += ["-e", REF]
    cmd.append(url)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=max_time + 10)
        return r.stdout
    except Exception:
        return ""


def test_deep(url):
    res = {"url": url, "ok": False, "info": []}
    master = curl(url)
    if "#EXTM3U" not in master[:300]:
        res["info"].append("master FALHA: " + master[:80].replace("\n", " | "))
        return res
    res["info"].append("master OK (%d B)" % len(master))

    # gather all non-comment lines (variants / slave playlists)
    variant_urls = []
    for line in master.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            if line.startswith("http"):
                variant_urls.append(line)
            else:
                variant_urls.append(urljoin(url, line))
    if not variant_urls:
        variant_urls = [url]

    ok_variants = 0
    for i, vurl in enumerate(variant_urls[:6]):
        v = curl(vurl)
        # media playlist check
        if "#EXT-X-" in v[:3000]:
            segs = [l for l in v.splitlines() if l.startswith("http")]
            if not segs:
                # relative URI segments
                segs = [l.strip() for l in v.splitlines() if l.strip() and not l.startswith("#")]
            ok_variants += 1
            res["info"].append(f"  pavariante#{i} OK ({len(v)} B, {len(segs)} segs)")
        else:
            res["info"].append(f"  pavariante#{i} FALHA ({v[:70]}".replace("\n", " | "))

    res["ok"] = ok_variants > 0
    return res


def main():
    with open("lista5.m3u", "r", encoding="utf-8") as f:
        lines = f.read().strip().split("\n")
    streams = []
    name = None
    for line in lines:
        if line.startswith("#EXTINF:"):
            m = re.match(r'#EXTINF:-?\d+\s+(.*?),(.*)$', line)
            name = m.group(2) if m else line
        elif line.startswith("http"):
            streams.append((name, line))
    seen = {}
    for n, u in streams:
        key = re.sub(r"exp=\d+", "exp=XXX", u)
        if key not in seen:
            seen[key] = (n, u)
    print("Deep test (sem range) de", len(seen), "URLs")
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(test_deep, u): (n, u) for n, u in seen.values()}
        for fut in concurrent.futures.as_completed(futs):
            n, u = futs[fut]
            r = fut.result()
            print(f"\n[{('PASSOU' if r['ok'] else 'FALHOU')}] {n}\n   {u[:100]}")
            for line in r["info"]:
                print("   ", line)


if __name__ == "__main__":
    main()