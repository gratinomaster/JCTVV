#!/usr/bin/env python3
import re
import concurrent.futures
import urllib.request
import ssl

INPUT = "lista5.m3u"

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept": "*/*",
}

def fetch(url, timeout=15):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        return resp.read(65536)

def deep_test(url):
    try:
        body = fetch(url).decode("utf-8", errors="ignore")
        if "#EXTM3U" not in body:
            return False, "manifesto invalido"
        lines = [l.strip() for l in body.splitlines() if l.strip()]
        # se ja e media playlist, pega primeiro segmento
        segs = [l for l in lines if l and not l.startswith("#")]
        target = None
        if "#EXT-X-TARGETDURATION" in body or "#EXTINF" in body:
            if segs:
                from urllib.parse import urljoin
                target = urljoin(url, segs[0])
        else:
            # master playlist: pega primeira variante
            variants = [l for l in lines if l and not l.startswith("#")]
            if variants:
                vurl = variants[0].split('"')[1] if '"' in variants[0] else variants[0]
                vurl = re.sub(r"^.*?https?://", "https://", vurl) if not vurl.startswith("http") and "http" in vurl else vurl
                from urllib.parse import urljoin
                vfull = urljoin(url, vurl)
                try:
                    vbody = fetch(vfull).decode("utf-8", errors="ignore")
                    vlines = [l.strip() for l in vbody.splitlines() if l.strip() and not l.startswith("#")]
                    if vlines:
                        from urllib.parse import urljoin as uj
                        target = uj(vfull, vlines[0])
                except Exception as e:
                    return False, f"variante falhou: {str(e)[:50]}"
        if target is None:
            return False, "sem segmentos"
        data = fetch(target)
        # segmento HLS valido: ts (0x47 sync) ou fmp4 (ftyp/moof)
        if len(data) > 1000 and (data[0:1] == b"\x47" or b"ftyp" in data[:32] or b"moof" in data[:1024]):
            return True, f"OK segmento {len(data)}B ({data[0:1]==b'\x47' and 'ts' or 'fmp4'})"
        return False, f"segmento suspeito ({len(data)}B)"
    except Exception as e:
        return False, str(e)[:70]

with open(INPUT, encoding="utf-8") as f:
    lines = f.read().splitlines()

urls = [l for l in lines if l.startswith("http")]

results = {}
with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
    futs = {ex.submit(deep_test, u): u for u in urls}
    for fut in concurrent.futures.as_completed(futs):
        u = futs[fut]
        ok, msg = fut.result()
        results[u] = (ok, msg)

ok_count = sum(1 for ok, _ in results.values() if ok)
print(f"\n=== RESULTADO PROFUNDO ===")
for u in urls:
    ok, msg = results[u]
    short = u[:60] + ("..." if len(u) > 60 else "")
    print(f"[{'OK    ' if ok else 'FALHOU'}] {short} -> {msg}")
print(f"\nTotal OK: {ok_count} / {len(urls)}")
