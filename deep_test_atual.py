#!/usr/bin/env python3
"""Deep HLS stream test: follow manifest->variant->segment."""
import re
import subprocess
import concurrent.futures

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"


def curl(url, max_time=25):
    try:
        r = subprocess.run(["curl", "-sL", "--max-time", str(max_time), "-A", UA, "-r", "0-300000", url],
                           capture_output=True, text=True, timeout=max_time + 10)
        return r.stdout
    except Exception as e:
        return ""


def test_deep(url):
    result = {"url": url, "ok": False, "steps": []}
    # 1. master manifest
    master = curl(url)
    if "#EXTM3U" not in master[:200] and "#EXT-X-" not in master[:2000]:
        low = master[:300].lower()
        result["steps"].append(("master", "FALHA (nao-HLS: %s)" % low[:60]))
        return result
    result["steps"].append(("master", "OK (%d bytes)" % len(master)))
    # 2. find variant playlist URI
    variant_line = None
    for line in master.splitlines():
        if line.startswith("#EXT-X-STREAM-INF"):
            pass
        elif line.strip() and not line.startswith("#"):
            variant_line = line.strip()
            break
    if not variant_line:
        # single playlist variant (could be media playlist directly)
        variant_line = url
    vurl = variant_line if variant_line.startswith("http") else _join(url, variant_line)
    # 3. fetch variant
    variant = curl(vurl)
    has_segments = any(l for l in variant.splitlines() if l.strip() and not l.startswith("#") and ".ts" in l or ".m4s" in l or ".aac" in l)
    if "#EXT-" not in variant[:4000] or not has_segments:
        seg_markers = [l for l in variant.splitlines() if l.strip() and not l.startswith("#")]
        result["steps"].append(("variante", "SEM SEGMENTOS (%d bytes): %s" % (len(variant), variant[:120].replace("\n", " | "))))
        return result
    # pick first segment
    seg_line = next(l.strip() for l in variant.splitlines() if l.strip() and not l.startswith("#") and not l.startswith("http") or (l.strip() and l.startswith("http")) )
    surl = seg_line if seg_line.startswith("http") else _join(vurl, seg_line)
    seg = curl(surl, max_time=20)
    result["steps"].append(("segmento", "OK (%d bytes)" % len(seg)))
    result["ok"] = len(seg) > 1000
    return result


def _join(base, rel):
    from urllib.parse import urljoin
    return urljoin(base, rel)


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

    print("Deep test de", len(seen), "URLs unicas")
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(test_deep, u): (n, u) for (n, u) in seen.values()}
        for fut in concurrent.futures.as_completed(futs):
            n, u = futs[fut]
            res = fut.result()
            results[u] = (n, res)

    for n, res in sorted(results.values(), key=lambda x: x[0]):
        status = "PASSOU" if res["ok"] else "FALHOU"
        print(f"[{status}] {n}")
        for step in res["steps"]:
            print(f"      {step[0]}: {step[1]}")


if __name__ == "__main__":
    main()