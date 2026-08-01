#!/usr/bin/env python3
import subprocess
import sys
import concurrent.futures

INPUT = "lista5.m3u"
OUTPUT = "lista5.m3u"


def parse_m3u(path):
    groups = []
    cur = None
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n")
            if line.startswith("#EXTM3U"):
                continue
            if line.startswith("#EXTINF:"):
                if cur:
                    groups.append(cur)
                cur = {"extinf": line, "urls": []}
            elif line.startswith("http://") or line.startswith("https://"):
                if cur:
                    cur["urls"].append(line)
    if cur:
        groups.append(cur)
    return groups


def test_url(url):
    cmd = [
        "curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
        "--connect-timeout", "8", "--max-time", "15", "-L", url,
    ]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        code = out.stdout.strip()
        if code in ("200", "206", "201", "202", "203"):
            return url, True, code
        return url, False, code
    except subprocess.TimeoutExpired:
        return url, False, "TIMEOUT"


def main():
    groups = parse_m3u(INPUT)
    print(f"Parsed {len(groups)} entries from {INPUT}")

    all_urls = sorted({u for g in groups for u in g["urls"]})
    print(f"Testing {len(all_urls)} unique URLs...")

    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(test_url, u): u for u in all_urls}
        for i, fut in enumerate(
            concurrent.futures.as_completed(futures), 1
        ):
            url, ok, code = fut.result()
            results[url] = ok
            status = "OK " if ok else "FAIL"
            print(f"[{i}/{len(all_urls)}] {status} ({code}) {url[:100]}")

    good_groups = []
    removed = 0
    for g in groups:
        good_urls = [u for u in g["urls"] if results.get(u)]
        if good_urls:
            g["urls"] = good_urls
            good_groups.append(g)
        else:
            removed += 1
            name = g["extinf"].split(",")[-1]
            print(f"REMOVING: {name}")

    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for g in good_groups:
            f.write(g["extinf"] + "\n")
            for u in g["urls"]:
                f.write(u + "\n")

    print("")
    print(f"Working entries kept: {len(good_groups)}")
    print(f"Removed entries: {removed}")
    print(f"Overwrote {OUTPUT}")


if __name__ == "__main__":
    sys.exit(main())
