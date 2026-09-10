#!/usr/bin/env python3
import subprocess
import sys
import concurrent.futures

INPUT = "lista5.m3u"
OUTPUT = "lista5.m3u"
TIMEOUT = 30


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
        "curl", "-s", "-L", "-o", "/tmp/opencode/test_chunk.bin",
        "-r", "0-262143", "-w", "%{http_code} %{content_type}",
        "--connect-timeout", "10", "--max-time", "25",
        "-H", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
        "-H", "Accept: */*",
        url,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        meta = proc.stdout.strip().strip("\n")
        code = meta.split()[0] if meta else ""
        ctype = meta.split()[1] if len(meta.split()) > 1 else ""
        ok = False
        reason = f"http={code} type={ctype}"
        if code in ("200", "206", "201", "202", "203"):
            try:
                with open("/tmp/opencode/test_chunk.bin", "rb") as fh:
                    chunk = fh.read()
                head = chunk[:2048].decode("utf-8", errors="ignore")
                if "#EXTM3U" in head or "#EXT-X-STREAM-INF" in head or "EXT-X-TARGETDURATION" in head:
                    ok = True
                    reason += " [HLS-OK]"
                elif len(chunk) > 0 and (("video" in ctype) or ("audio" in ctype) or ("mpegurl" in ctype) or ("application" in ctype)):
                    ok = True
                    reason += f" [BODY {len(chunk)}B]"
                else:
                    reason += f" [NOT-HLS BODY {len(chunk)}B: {head[:80]!r}]"
            except FileNotFoundError:
                reason += " [NO-BODY]"
        return url, ok, reason
    except subprocess.TimeoutExpired:
        return url, False, "TIMEOUT"


def main():
    groups = parse_m3u(INPUT)
    print(f"Parsed {len(groups)} entries from {INPUT}")

    all_urls = sorted({u for g in groups for u in g["urls"]})
    print(f"Testing {len(all_urls)} unique URLs...")

    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        futures = {ex.submit(test_url, u): u for u in all_urls}
        for i, fut in enumerate(concurrent.futures.as_completed(futures), 1):
            url, ok, reason = fut.result()
            results[url] = ok
            status = "OK  " if ok else "FAIL"
            name = next(
                (g["extinf"].split(",")[-1] for g in groups if url in g["urls"]),
                "?",
            )
            print(f"[{i}/{len(all_urls)}] {status} {reason} | {name} | {url[:80]}")

    good_groups = []
    removed = 0
    for g in groups:
        good_urls = [u for u in g["urls"] if results.get(u)]
        if good_urls:
            g["urls"] = good_urls
            good_groups.append(g)
            print(f"KEEP: {g['extinf'].split(',')[-1]} ({len(good_urls)} URL(s))")
        else:
            removed += 1
            print(f"REMOVE: {g['extinf'].split(',')[-1]}")

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