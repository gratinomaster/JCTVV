#!/usr/bin/env python3
import re
import shutil
import concurrent.futures
import requests
from datetime import datetime

SRC = "lista5.m3u"
BAK = f"lista5.m3u.bak.pre_teste_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
TIMEOUT = 15

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept": "*/*",
    "Referer": "https://www.google.com/",
}

def parse_m3u(path):
    entries = []
    header = None
    with open(path, encoding="utf-8") as f:
        lines = [l.rstrip("\n") for l in f]
    i = 0
    if lines and lines[0].startswith("#EXTM3U"):
        header = lines[0]
        i = 1
    while i < len(lines):
        line = lines[i]
        if line.startswith("#EXTINF"):
            extinf = line
            url_lines = []
            i += 1
            while i < len(lines) and (lines[i].startswith("#") or lines[i].strip() == ""):
                if lines[i].startswith("#EXTINF"):
                    break
                i += 1
            while i < len(lines) and not lines[i].startswith("#") and lines[i].strip() != "":
                url_lines.append(lines[i])
                i += 1
            entries.append({"extinf": extinf, "urls": url_lines})
        else:
            i += 1
    return header, entries

def test_url(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, stream=True)
        ok = False
        if r.status_code == 200:
            ctype = (r.headers.get("Content-Type") or "").lower()
            chunk = next(r.iter_content(chunk_size=4096), b"")
            text = chunk.decode("utf-8", errors="ignore").lower()
            is_manifest = ("mpegurl" in ctype or "mp2t" in ctype or
                           text.startswith("#extm3u") or "#ext-x" in text)
            has_content = len(chunk) > 50
            bad_marker = any(m in text for m in ("<html", "<!doctype", "not found", "error"))
            ok = (is_manifest or "video" in ctype or "octet-stream" in ctype) and has_content and not bad_marker
        r.close()
        return ok
    except Exception:
        return False

def test_entry(entry):
    for u in entry["urls"]:
        if test_url(u):
            return entry, True
    return entry, False

shutil.copy(SRC, BAK)

header, entries = parse_m3u(SRC)
print(f"Total de canais a testar: {len(entries)}")

results = []
with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
    for res in ex.map(test_entry, entries):
        results.append(res)
        name = re.sub(r'^.*?,', '', res[0]["extinf"])[:60]
        print(f"[{'OK ' if res[1] else 'FALHA'}] {name}")

working = [e for e, ok in results if ok]
failed = [(e, False) for e, ok in results if not ok]

with open(SRC, "w", encoding="utf-8") as f:
    f.write((header or "#EXTM3U") + "\n")
    for e in working:
        f.write(e["extinf"] + "\n")
        for u in e["urls"]:
            f.write(u + "\n")

print("\n=== RESUMO ===")
print(f"Funcionando: {len(working)} | Removidos: {len(failed)}")
for e, _ in failed:
    name = re.sub(r'^.*?,', '', e["extinf"])[:70]
    print(f"  REMOVIDO: {name}")
