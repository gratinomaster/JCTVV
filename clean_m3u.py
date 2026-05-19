import subprocess
from collections import OrderedDict

INPUT_FILE = "lista5.m3u"

with open(INPUT_FILE, "r") as f:
    lines = [line.rstrip("\n") for line in f]

header = lines[0]
entries = []
i = 1
while i < len(lines):
    extinf = lines[i]
    url = lines[i + 1] if i + 1 < len(lines) else ""
    entries.append((extinf, url))
    i += 2

unique_urls = OrderedDict()
for extinf, url in entries:
    if url not in unique_urls:
        unique_urls[url] = None

results = {}
for url in unique_urls:
    try:
        result = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", "10", url],
            capture_output=True, text=True, timeout=15
        )
        http_code = result.stdout.strip()
        is_working = http_code and http_code[0] == "2"
        results[url] = (http_code, is_working)
        status = "WORKING" if is_working else "FAILED"
        print(f"[{status}] HTTP {http_code} -> {url[:80]}...")
    except Exception as e:
        results[url] = ("ERROR", False)
        print(f"[FAILED] ERROR -> {url[:80]}... ({e})")

working_urls = {url for url, (code, ok) in results.items() if ok}

working_entries = [(extinf, url) for extinf, url in entries if url in working_urls]

with open(INPUT_FILE, "w") as f:
    f.write(header + "\n")
    for extinf, url in working_entries:
        f.write(extinf + "\n")
        f.write(url + "\n")

print(f"\nSummary: {len(working_entries)} working entries out of {len(entries)} total")
print(f"Unique URLs tested: {len(unique_urls)}, working: {len(working_urls)}")
print(f"Cleaned playlist written to {INPUT_FILE}")
