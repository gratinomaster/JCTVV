#!/usr/bin/env python3
import re
import subprocess
import concurrent.futures
from urllib.parse import urlparse

HEADERS = "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"


def test_stream(url, timeout=20):
    """GET a bit of the manifest, check for HLS marker."""
    try:
        r = subprocess.run(
            ["curl", "-sL", "--max-time", str(timeout), "-A", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36", "-r", "0-8000", url],
            capture_output=True, text=True, timeout=timeout + 10)
        body = r.stdout
        low = body[:500].lower()
        if "#extm3u" in low or "#EXTM3U" in body[:200]:
            return {"ok": True, "status": 200, "kind": "hls", "detail": body[:80].replace(chr(10), " | ")}
        if body.strip() == "":
            return {"ok": False, "status": "vazio", "kind": "?", "detail": ""}
        if "<html" in low or "error" in low[:200]:
            # try HTTP status
            r2 = subprocess.run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", "15", "-A", "Mozilla/5.0", url], capture_output=True, text=True)
            return {"ok": False, "status": r2.stdout, "kind": "http", "detail": body[:80].replace(chr(10), " | ")}
        return {"ok": True, "status": 200, "kind": "manifest", "detail": body[:80].replace(chr(10), " | ")}
    except Exception as e:
        return {"ok": False, "status": "ERRO", "kind": "?", "detail": str(e)}


def test_logo(url, timeout=20):
    try:
        r = subprocess.run(
            ["curl", "-sL", "-o", "/dev/null", "-w", "%{http_code} %{content_type} %{size_download}", "--max-time", str(timeout), "-A", "Mozilla/5.0", url],
            capture_output=True, text=True, timeout=timeout + 10)
        return r.stdout.strip()
    except Exception as e:
        return f"ERRO {e}"


def main():
    with open("lista5.m3u", "r", encoding="utf-8") as f:
        lines = f.read().strip().split("\n")

    streams = []
    logos = set()
    current = None
    for line in lines:
        if line.startswith("#EXTINF:"):
            m = re.match(r'#EXTINF:-?\d+\s+(.*?),(.*)$', line)
            attrs = m.group(1) if m else ""
            name = m.group(2) if m else line
            lg = re.search(r'tvg-logo="([^"]*)"', attrs)
            if lg:
                logos.add((name, lg.group(1)))
            current = name
        elif line.startswith("http"):
            streams.append((current, line))

    print("=" * 70)
    print("TESTE DE STREAMS", len(streams))
    print("=" * 70)

    def run_stream(item):
        name, url = item
        key = re.sub(r"exp=\d+", "exp=XXX", url)
        return name, key, url, test_stream(url)

    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
        for name, key, url, res in ex.map(run_stream, streams):
            results.setdefault(key, {"name": name, "url": url, "test": res, "count": 0})
            results[key]["count"] += 1

    print(f"\nURLs unicas testadas: {len(results)}\n")
    for key, data in sorted(results.items(), key=lambda kv: kv[1]["name"]):
        res = data["test"]
        status = "OK " if res["ok"] else "FAIL"
        print(f"[{status}] {data['name']} (x{data['count']})\n   {res['kind']} status={res['status']}\n   {data['url'][:120]}")

    print("\n" + "=" * 70)
    print("TESTE DE LOGOS (.jpg?)")
    print("=" * 70)
    for name, logo in sorted(logos):
        ext = urlparse(logo).path.rsplit(".", 1)[-1].lower() if "." in urlparse(logo).path else "?"
        imgur = "IMGER!" if "imgur.com" in logo else ""
        res = test_logo(logo)
        print(f"[{ext}] {name}: {res} {imgur}\n   {logo[:110]}")


if __name__ == "__main__":
    main()