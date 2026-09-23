#!/usr/bin/env python3
"""Deep HLS test: master -> variante -> segmento real. Usado como validacao
de stream e anti-virus substituta (dominios oficiais + video real)."""
import subprocess, sys, re, urllib.parse

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36"

def fetch(url, timeout=25):
    r = subprocess.run(["curl", "-sL", "--max-time", str(timeout), "-A", UA, url],
                       capture_output=True, timeout=timeout + 10)
    return r.stdout.decode("utf-8", "ignore")

def http_code(url, timeout=25):
    r = subprocess.run(["curl", "-sL", "--max-time", str(timeout), "-A", UA, "-o", "/dev/null",
                        "-w", "%{http_code}", url], capture_output=True, timeout=timeout + 10)
    return r.stdout.decode()

def resolve_uri(base, uri):
    return urllib.parse.urljoin(base, uri)

def deep_test(url, name):
    print(f"\n=== {name} ===")
    master = fetch(url)
    if "#EXTM3U" not in master:
        print(f"  FALHA: master nao e HLS (size={len(master)})")
        return False
    variants = re.findall(r'(?m)^#EXT-X-STREAM-INF:.*\n(\S+)', master)
    if not variants:
        print("  master OK, sem variantes listadas (verificando segmentos diretos)")
        segments = re.findall(r'^[^#][^\s]+(?:\?.*)?$', master, re.M)
        seg = segments[0] if segments else None
        if not seg:
            return False
        return check_segment(url, seg, name)
    print(f"  master OK, {len(variants)} variantes")
    ok_variants = 0
    for v in variants[:4]:
        vurl = resolve_uri(url, v.strip())
        code = http_code(vurl)
        vbody = fetch(vurl)
        if code == "200" and "#EXTM3U" in vbody:
            ok_variants += 1
        else:
            print(f"  variante {v} -> {code} FAIL")
    print(f"  variantes OK: {ok_variants}/{min(len(variants),4)}")
    if ok_variants == 0:
        return False
    # pega segmento de uma variante que funcionou
    for v in variants[:4]:
        vurl = resolve_uri(url, v.strip())
        vbody = fetch(vurl)
        if "#EXTM3U" not in vbody:
            continue
        seglines = [l.strip() for l in vbody.splitlines() if l.strip() and not l.startswith("#")]
        if not seglines:
            continue
        # procura segmento com extensao ts/m4s
        for sl in seglines:
            if re.search(r'\.(ts|m4s|mp4)(\?|$)', resolve_uri(vurl, sl)):
                return check_segment(url, vurl, name, sl)
        # fallback: primeiro segmento
        return check_segment(url, vurl, name, seglines[0])
    return False

def check_segment(root_url, vurl, name, sl=None):
    segurl = resolve_uri(vurl, sl) if sl else vurl
    print(f"  segmento: {segurl[-80:]}")
    r = subprocess.run(["curl", "-sL", "--max-time", "25", "-A", UA, "-o", "/tmp/opencode/seg.bin",
                        "-w", "%{http_code}", segurl], capture_output=True, timeout=35)
    code = r.stdout.decode()
    data = open("/tmp/opencode/seg.bin", "rb").read()
    is_ts = False
    if data[:1] == b"\x47":
        aligned = sum(1 for i in range(0, min(len(data) - 188, 188 * 8), 188) if data[i] == 0x47)
        is_ts = aligned >= 6
    boxes = re.findall(rb'[a-zA-Z0-9]{4}', data[:64])
    is_mp4 = any(b in (b"ftyp", b"styp", b"moof", b"moov", b"mdat") for b in boxes)
    hint = re.findall(rb'(ftyp|styp|moof|moov|mdat)', data[:64])
    ok = code == "200" and len(data) > 1000 and (is_ts or is_mp4)
    print(f"  segmento {code} size={len(data)} TS={is_ts} MP4={is_mp4} boxes={[b.decode() for b in hint]} -> {'OK' if ok else 'FAIL'}")
    return ok

if __name__ == "__main__":
    import json
    urls = json.load(open(sys.argv[1])) if len(sys.argv) > 1 else None
    items = urls or [
        ("ABC akamaized", "https://abcnews-livestreams.akamaized.net/out/v1/6a597119dbd5428a82dc11a2f514a1a2/abcn-live-10-cmaf-manifest/abcn-live-10-index.m3u8"),
        ("CBS Google DAI", "https://dai.google.com/linear/hls/pa/event/Sid4xiTQTkCT1SLu6rjUSQ/stream/e369630b-44dc-4e6d-a047-6e9bd6080f7d:ATL/master.m3u8"),
        ("Fox News preview", "https://247preview.foxnews.com/hls/live/2020027/fncv3preview/primary.m3u8"),
        ("Fox Business preview", "https://247preview.foxbusiness.com/hls/live/2020026/fbnv3preview/primary.m3u8"),
    ]
    results = {}
    for name, url in items:
        ok = deep_test(url, name)
        results[name] = "OK" if ok else "FAIL"
        print(f"  >> {name}: {'OK' if ok else 'FAIL'}")
    print("\nRESUMO:", json.dumps(results))