#!/usr/bin/env python3
import re
import concurrent.futures
import urllib.request
import urllib.error
import ssl

INPUT = "lista5.m3u"
OUTPUT = "lista5.m3u"

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept": "*/*",
}

def test_url(url, timeout=15):
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            if resp.status != 200:
                return False, f"HTTP {resp.status}"
            data = resp.read(4096).decode("utf-8", errors="ignore")
            if "#EXTM3U" in data:
                return True, "OK (HLS)"
            if data.strip().startswith("<?xml") or "<MPD" in data:
                return True, "OK (DASH/XML)"
            return False, "conteudo invalido"
    except Exception as e:
        return False, str(e)[:80]

with open(INPUT, encoding="utf-8") as f:
    lines = f.read().splitlines()

entries = []
i = 0
while i < len(lines):
    line = lines[i]
    if line.startswith("#EXTINF"):
        extinf = line
        url = None
        j = i + 1
        while j < len(lines) and not lines[j].startswith("http"):
            j += 1
        if j < len(lines):
            url = lines[j]
            entries.append((extinf, url))
            i = j + 1
            continue
    i += 1

print(f"Total de canais encontrados: {len(entries)}")

results = {}
with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
    futs = {ex.submit(test_url, e[1]): e for e in entries}
    for fut in concurrent.futures.as_completed(futs):
        extinf, url = futs[fut]
        ok, msg = fut.result()
        results[url] = (ok, msg)
        name = re.search(r",(.*)$", extinf)
        name = name.group(1)[:45] if name else "?"
        status = "OK  " if ok else "FALHOU"
        print(f"[{status}] {name:<47} {msg}")

kept = []
for extinf, url in entries:
    ok, _ = results[url]
    if ok:
        kept.append((extinf, url))

out = ["#EXTM3U"]
for extinf, url in kept:
    out.append(extinf)
    out.append(url)

with open(OUTPUT, "w", encoding="utf-8") as f:
    f.write("\n".join(out) + "\n")

print(f"\nFuncionando: {len(kept)} | Removidos: {len(entries) - len(kept)}")
print(f"{OUTPUT} atualizado.")
