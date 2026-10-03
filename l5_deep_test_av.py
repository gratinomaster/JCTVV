#!/usr/bin/env python3
"""Deep HLS validation + ClamAV/reputation scan for lista5 candidates."""
import os, re, sys, json, subprocess, requests
from urllib.parse import urljoin

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36")
H = {"User-Agent": UA, "Accept": "*/*"}
WORK = "/tmp/opencode/avscan"
os.makedirs(WORK, exist_ok=True)

CANDIDATES = [
    ("FOX NEWS",       "https://247preview.foxnews.com/hls/live/2020027/fncv3preview/index.m3u8"),
    ("FOX BUSINESS",   "https://247preview.foxbusiness.com/hls/live/2020026/fbnv3preview/index.m3u8"),
    ("ABC NEWS LIVE",  "https://abcnews-livestreams.akamaized.net/out/v1/6a597119dbd5428a82dc11a2f514a1a2/abcn-live-10-cmaf-manifest/abcn-live-10-index.m3u8"),
    ("CBS NEWS DAI",   "https://dai.google.com/linear/hls/pa/event/Sid4xiTQTkCT1SLu6rjUSQ/stream/648ec254-e176-4376-9f0a-73b4b794de47:CHS/master.m3u8"),
    ("CBS NEWS VTT",   "https://cbsn-us-vtt.cbsnstream.cbsnews.com/out/v1/ef868690d34144509eda696884bf1619/master.m3u8"),
    ("CBS NEWS US",    "https://cbsn-us.cbsnstream.cbsnews.com/out/v1/55a8648e8f134e82a470f83d562deeca/master.m3u8"),
]

MEDIA_MAGIC = {
    "ts": bytes.fromhex("47"),
    "fmp4": None,  # styp/moof/mdat
    "aac": bytes.fromhex("fff1"),
}


def get(url, timeout=25):
    r = requests.get(url, headers=H, timeout=timeout, stream=True)
    return r


def pick_variant(master_text, base):
    variants = []
    lines = [l.strip() for l in master_text.splitlines()]
    for i, l in enumerate(lines):
        if l.startswith("#EXT-X-STREAM-INF"):
            res = re.search(r'RESOLUTION=(\d+x\d+)', l)
            bw = re.search(r'(?:AVERAGE-)?BANDWIDTH=(\d+)', l)
            nxt = next((x for x in lines[i + 1:] if x and not x.startswith("#")), None)
            if nxt:
                variants.append((int(bw.group(1)) if bw else 0,
                                 res.group(1) if res else "?",
                                 urljoin(base, nxt)))
    variants.sort(reverse=True)
    return variants


def probe(name, url):
    out = {"name": name, "url": url}
    try:
        r = get(url)
        if r.status_code != 200 or b"#EXTM3U" not in r.content[:200]:
            out["ok"] = False
            out["err"] = f"master http={r.status_code}"
            return out
        text = r.content.decode("utf-8", "ignore")
        master_bytes = r.content
        variants = pick_variant(text, url)
        out["variants"] = len(variants)
        if not variants:
            out["ok"] = False
            out["err"] = "no variants"
            return out
        bw, res, vurl = variants[0]
        out["best_res"] = res
        out["best_bw"] = bw
        vr = get(vurl)
        if vr.status_code != 200:
            out["ok"] = False
            out["err"] = f"variant http={vr.status_code}"
            return out
        vtext = vr.content.decode("utf-8", "ignore")
        segs = [l.strip() for l in vtext.splitlines()
                if l.strip() and not l.startswith("#")]
        out["segments_in_pl"] = len(segs)
        if not segs:
            out["ok"] = False
            out["err"] = "no segments"
            return out
        got = 0
        seg_paths = []
        for s in segs[-3:]:
            su = urljoin(vurl, s)
            sr = requests.get(su, headers=H, timeout=30)
            body = sr.content
            if sr.status_code != 200 or len(body) < 2000:
                out["err"] = f"seg http={sr.status_code} len={len(body)}"
                continue
            good = (body[:1] == b"G" or body[4:8] == b"styp"
                    or body[4:8] == b"moof" or body[4:8] == b"ftyp"
                    or body[:2] == b"\xff\xf1" or body[:2] == b"\xff\xf9")
            p = os.path.join(WORK, f"{name.replace(' ', '_')}_seg{got}.bin")
            open(p, "wb").write(body)
            seg_paths.append(p)
            got += 1
            if got == 2:
                break
        # master playlist bytes for scanning too
        mp = os.path.join(WORK, f"{name.replace(' ', '_')}_master.m3u8")
        open(mp, "wb").write(master_bytes + b"\n" + vr.content)
        out["segments_ok"] = got
        out["scan_paths"] = seg_paths + [mp]
        out["ok"] = got > 0
        if not out["ok"]:
            out.setdefault("err", "no playable segment")
    except Exception as e:
        out["ok"] = False
        out["err"] = f"EXC {type(e).__name__}: {e}"
    return out


def clamav(paths):
    res = {"scanned": 0, "infected": []}
    for p in paths:
        if not os.path.exists(p):
            continue
        res["scanned"] += 1
        try:
            cp = subprocess.run(["clamscan", "--no-summary", "--infected", p],
                                capture_output=True, text=True, timeout=180)
            o = (cp.stdout or "") + (cp.stderr or "")
            if ": " in o and "FOUND" in o:
                res["infected"].append({"file": p, "detail": o.strip()[:300]})
        except Exception as e:
            res.setdefault("errors", []).append(f"{p}: {e}")
    return res


def reputation(urls):
    urls = [u.lower() for u in urls]
    hosts = set()
    for u in urls:
        m = re.match(r'https?://([^/]+)', u)
        if m:
            hosts.add(m.group(1).split(":")[0])
    bad_urls, bad_hosts = set(), set()
    feeds = [
        ("https://urlhaus.abuse.ch/downloads/text/", "url"),
        ("https://openphish.com/feed.txt", "url"),
        ("https://raw.githubusercontent.com/mitchellkrogza/Phishing.Database/master/phishing-domains-ACTIVE.txt", "host"),
    ]
    for fu, mode in feeds:
        try:
            t = requests.get(fu, timeout=60, headers={"User-Agent": "Mozilla/5.0"}).text
        except Exception:
            continue
        for line in t.splitlines():
            line = line.strip().lower()
            if not line or line.startswith("#"):
                continue
            if mode == "url":
                bad_urls.add(line)
                m = re.match(r'https?://([^/]+)', line)
                if m:
                    bad_hosts.add(m.group(1).split(":")[0])
            else:
                bad_hosts.add(line.lstrip("."))
    hits = [u for u in urls if u in bad_urls]
    hhits = sorted(h for h in hosts if h in bad_hosts)
    return {"flagged_urls": hits, "flagged_hosts": hhits,
            "feeds_loaded": len(bad_urls) + len(bad_hosts)}


if __name__ == "__main__":
    results = [probe(n, u) for n, u in CANDIDATES]
    for r in results:
        print(f"{r['name']:15s} ok={r.get('ok')} res={r.get('best_res','-'):>9s} "
              f"bw={r.get('best_bw',0):>8d} segs={r.get('segments_ok',0)} "
              f"err={r.get('err','')}")
    allp = [p for r in results for p in r.get("scan_paths", [])]
    print(f"\n>> clamscan on {len(allp)} files")
    av = clamav(allp)
    print(f"   scanned={av['scanned']} infected={len(av['infected'])}")
    for i in av["infected"]:
        print("   !!", i["detail"])
    rep = reputation([u for _, u in CANDIDATES])
    print(f">> reputation: flagged_urls={len(rep['flagged_urls'])} flagged_hosts={rep['flagged_hosts']}")
    json.dump({"probe": results, "av": av, "rep": rep},
              open("/tmp/opencode/l5_deep_av.json", "w"), indent=2)
    print("\nwrote /tmp/opencode/l5_deep_av.json")