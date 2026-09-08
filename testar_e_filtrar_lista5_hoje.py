#!/usr/bin/env python3
import subprocess
import time
import shutil
import sys

INPUT = "lista5.m3u"
TIMEOUT = 45
CONNECT_TIMEOUT = "10"

def parse_playlist(path):
    entries = []
    with open(path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTM3U"):
            i += 1
            continue
        if line.startswith("#EXTINF"):
            extinf = lines[i]
            url = ""
            if i + 1 < len(lines):
                url = lines[i + 1].strip()
            entries.append((extinf, url))
            i += 2
        else:
            i += 1
    return entries

def test_url(url):
    cmd = [
        "timeout", str(TIMEOUT),
        "ffprobe",
        "-v", "error",
        "-rw_timeout", "15000000",
        "-user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "-show_entries", "format=format_name:stream=codec_type",
        "-of", "default=noprint_wrappers=1",
        url,
    ]
    try:
        start = time.time()
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT + 10)
        elapsed = time.time() - start
        out = proc.stdout
        if proc.returncode == 0 and "format_name" in out:
            return True, proc.returncode, elapsed
        return False, proc.returncode, elapsed
    except subprocess.TimeoutExpired:
        return False, "TIMEOUT", TIMEOUT
    except Exception as e:
        return False, str(e), 0

def main():
    backup = f"{INPUT}.bak.{time.strftime('%Y%m%d_%H%M%S')}"
    shutil.copy(INPUT, backup)
    print(f"Backup criado: {backup}")

    entries = parse_playlist(INPUT)
    total = len(entries)
    print(f"Total de entradas: {total}\n")

    working = [("#EXTM3U", "")]
    ok = 0
    fail = 0

    for idx, (extinf, url) in enumerate(entries, 1):
        name = extinf.split(",", 1)[-1]
        if not url or not url.startswith("http"):
            print(f"[{idx}/{total}] SKIP (sem URL) {name}")
            fail += 1
            continue
        good, rc, elapsed = test_url(url)
        status = "OK" if good else "FAIL"
        if good:
            working.append((extinf, url))
            ok += 1
        else:
            fail += 1
        print(f"[{idx}/{total}] {status:4s} ({rc}, {elapsed:.1f}s) {name}")

    with open(INPUT + ".tmp", "w", encoding="utf-8") as f:
        for extinf, url in working:
            f.write(extinf)
            if url:
                f.write("\n" + url)
            f.write("\n")

    if ok == 0 and fail > 0:
        print("\nNenhum canal funcionou; lista nao foi alterada.")
        sys.exit(1)

    shutil.move(INPUT + ".tmp", INPUT)
    print("\n=== RESULTADO ===")
    print(f"Total: {total} | OK: {ok} | FAIL: {fail}")
    print(f"Lista atualizada em {INPUT}")

if __name__ == "__main__":
    main()
