#!/usr/bin/env python3
"""
Anti-virus / malware-reputation test for lista5.m3u candidates.

1. Reputation: cross-check stream host + full URL against live malware /
   phishing blocklists (URLhaus, OpenPhish, Phishing.Database) and DNSBL (Spamhaus DBL).
2. Payload AV scan: download the HLS playlist + real media segments and run
   ClamAV (fresh signatures) on the bytes actually delivered by the server.
"""
import os, re, subprocess, sys, json, gzip, requests, socket
from urllib.parse import urlparse, urljoin

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
WORK = "/tmp/opencode/avscan"
os.makedirs(WORK, exist_ok=True)
H = {"User-Agent": UA}

CANDIDATES = [
    ("ABC News Live", "https://abcnews-livestreams.akamaized.net/out/v1/6a597119dbd5428a82dc11a2f514a1a2/abcn-live-10-cmaf-manifest/abcn-live-10-index.m3u8"),
    ("ABC News Live (Disney CDN)", "https://pb-0n3n2ej0w8pl9.akamaized.net/ABCNewsLive_Disney.m3u8"),
    ("Fox News Channel", "https://247preview.foxnews.com/hls/live/2020027/fncv3preview/primary.m3u8"),
    ("Fox Business", "https://247preview.foxbusiness.com/hls/live/2020026/fbnv3preview/primary.m3u8"),
    ("CBS News 24/7", "https://cbsn-us.cbsnstream.cbsnews.com/out/v1/55a8648e8f134e82a470f83d562deeca/master.m3u8"),
    ("CBS News 24/7 (vtt)", "https://cbsn-us-vtt.cbsnstream.cbsnews.com/out/v1/ef868690d34144509eda696884bf1619/master.m3u8"),
]
EPG_URLS = [
    "https://epg.pw/xmltv/epg_US.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz",
]


def load_feeds():
    print(">> loading malware / phishing blocklists")
    urls, hosts = set(), set()

    def add(txt, url_mode):
        for line in txt.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if url_mode:
                urls.add(line.lower())
                p = urlparse(line)
                if p.hostname:
                    hosts.add(p.hostname.lower())
            else:
                hosts.add(line.lower().lstrip("."))

    f = "/tmp/opencode/uh.txt"
    if os.path.exists(f):
        add(open(f, encoding="utf-8", errors="replace").read(), True)
    f = "/tmp/opencode/openphish.txt"
    if os.path.exists(f):
        add(open(f, encoding="utf-8", errors="replace").read(), True)
    f = "/tmp/opencode/phishdom.txt"
    if os.path.exists(f):
        add(open(f, encoding="utf-8", errors="replace").read(), False)
    print(f"   blocklist entries: {len(urls)} urls / {len(hosts)} hosts")
    return urls, hosts


def dnsbl(host):
    """Spamhaus DBL + SURBL lookup (returns listed zones or None)."""
    hits = []
    for zone in ("dbl.spamhaus.org", "multi.surbl.org"):
        try:
            out = subprocess.run(["dig", "+short", f"{host}.{zone}", "A"],
                                 capture_output=True, timeout=15).stdout.decode().strip()
            if out:
                hits.append(f"{zone}={out}")
        except Exception:
            pass
    return hits


def domain_of(url):
    h = urlparse(url).hostname or ""
    return h.lower()


def registrable(host):
    p = host.split(".")
    return ".".join(p[-2:]) if len(p) >= 2 else host


def fetch_segments(url, limit=3):
    """Return list of (url, bytes) = playlist + media segments."""
    got = []
    r = requests.get(url, headers=H, timeout=25, stream=False)
    got.append((url, r.content))
    text = r.text
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    segs = [l for l in lines if l.startswith("http") and ".ts" in l or l.startswith("http") and ".m4s" in l or l.startswith("http") and ".aac" in l]
    for s in segs[:limit]:
        su = urljoin(url, s)
        try:
            rr = requests.get(su, headers=H, timeout=25)
            got.append((su, rr.content))
        except Exception:
            pass
    return got, r.headers.get("Content-Type", ""), r.status_code


def clamscan(paths):
    if not paths:
        return [], 0
    p = subprocess.run(["sudo", "clamscan", "--no-summary", "--infected", *paths],
                       capture_output=True, timeout=900)
    out = p.stdout.decode(errors="replace")
    infected = [l for l in out.splitlines() if l.endswith("FOUND")]
    return infected, len(paths)


def main():
    urls_bl, hosts_bl = load_feeds()
    report = []

    print("\n" + "=" * 96)
    print("ANTI-VIRUS / MALWARE TEST  --  lista5.m3u candidates")
    print("=" * 96)

    # ---- 1. reputation -----------------------------------------------------
    print("\n[1] URL / domain reputation (blocklists + DNSBL)")
    rep = {}
    for name, u in CANDIDATES + [("EPG", e) for e in EPG_URLS]:
        host = domain_of(u)
        reg = registrable(host)
        bl_url = u.lower() in urls_bl or u.split("?")[0].lower() in urls_bl
        bl_host = host in hosts_bl or reg in hosts_bl
        dns = dnsbl(reg)
        clean = not (bl_url or bl_host or dns)
        rep[u] = dict(host=host, url_blocklisted=bl_url, host_blocklisted=bl_host, dnsbl=dns, clean=clean)
        flag = "CLEAN" if clean else "FLAGGED"
        print(f"  {flag:8} {name:28} host={host}")
        if not clean:
            print(f"           url_bl={bl_url} host_bl={bl_host} dnsbl={dns}")

    # ---- 2. payload AV scan ------------------------------------------------
    print("\n[2] ClamAV payload scan (HLS playlist + real media segments)")
    for name, u in CANDIDATES:
        d = os.path.join(WORK, re.sub(r"[^A-Za-z0-9]+", "_", name)[:40])
        os.makedirs(d, exist_ok=True)
        try:
            blobs, ctype, code = fetch_segments(u)
        except Exception as e:
            print(f"  ERROR  {name:28} fetch failed: {e}")
            report.append(dict(name=name, url=u, ok=False, reason=f"fetch {e}"))
            continue

        paths, kinds = [], []
        for i, (su, data) in enumerate(blobs):
            if not data:
                continue
            ext = ".ts" if (data[:1] == b"\x47" or b"\x47" in data[:188]) else (
                  ".m4s" if data[4:8] == b"ftyp" else ".bin")
            p = os.path.join(d, f"blob{i}{ext}")
            open(p, "wb").write(data)
            paths.append(p)
            kinds.append((ext, len(data)))

        infected, n = clamscan(paths)
        bad = bool(infected)
        # heuristic: server must deliver media/playlist, never HTML/JS/EXE
        ctype_susp = re.search(r"text/html|javascript|x-msdownload|x-executable", ctype or "", re.I)
        if bad or ctype_susp:
            verdict = "FAIL"
        else:
            verdict = "PASS"
        print(f"  {verdict:6} {name:28} http={code} ct={ctype[:24]:24} files={n} {kinds[:2]}")
        if infected:
            for i in infected:
                print("           INFECTED:", i)
        if ctype_susp:
            print("           suspicious content-type:", ctype)
        report.append(dict(name=name, url=u, ok=(verdict == "PASS"),
                           reason="; ".join(infected) + (f" ct={ctype}" if ctype_susp else ""),
                           files=n, content_type=ctype, http=code))

    # ---- 3. EPG AV scan ----------------------------------------------------
    print("\n[3] ClamAV scan of EPG downloads")
    for e in EPG_URLS:
        p = os.path.join(WORK, e.rsplit("/", 1)[-1])
        try:
            r = requests.get(e, headers=H, timeout=280, stream=True)
            total = 0
            with open(p, "wb") as f:
                for ch in r.iter_content(1 << 20):
                    f.write(ch); total += len(ch)
                    if total > 60 * 1024 * 1024:
                        break
            inf, _ = clamscan([p])
            print(f"  {'FAIL' if inf else 'PASS':6} {e.rsplit('/',1)[-1]:26} bytes={total/1e6:.1f}MB infected={inf}")
            report.append(dict(name="EPG " + e.rsplit("/", 1)[-1], url=e, ok=not inf,
                               reason="; ".join(inf), bytes=total))
        except Exception as ex:
            print(f"  ERROR  {e}: {ex}")
            report.append(dict(name="EPG " + e, url=e, ok=False, reason=str(ex)))

    # ---- 4. EPG structural validity (no AV, but parsed as XMLTV) -----------
    print("\n[4] EPG structural validation")
    import xml.etree.ElementTree as ET
    ids = {"465372", "465150", "464766", "464941"}
    ids2 = {"Fox.News.Channel.HD.us2", "ABC.News.Live.us2", "Fox.Business.HD.us2", "CBS.News.National.Stream.us2"}
    for e in EPG_URLS:
        p = os.path.join(WORK, e.rsplit("/", 1)[-1])
        if not os.path.exists(p):
            continue
        opener = gzip.open if p.endswith(".gz") else open
        want = ids if "epg.pw" in e else ids2
        seen, chfound = set(), set()
        with opener(p, "rb") as f:
            for ev, el in ET.iterparse(f, events=("end",)):
                if el.tag == "programme" and el.get("channel") in want:
                    seen.add(el.get("start")[:8]); chfound.add(el.get("channel"))
                el.clear()
        days = sorted(seen)
        ok = len(chfound) == 4 and len([d for d in days if d >= "20260929"]) >= 3
        print(f"  {'PASS' if ok else 'FAIL':6} {e.rsplit('/',1)[-1]:26} channels={len(chfound)}/4 days={days}")
        report.append(dict(name="EPGVALID " + e, url=e, ok=ok, channels=len(chfound), days=days))

    json.dump(report, open("/tmp/opencode/av_report.json", "w"), indent=1)
    print("\n" + "=" * 96)
    fails = [r for r in report if not r["ok"]]
    print(f"RESULT: {len(report)-len(fails)}/{len(report)} PASS   |   {len(fails)} FAIL")
    for f in fails:
        print("  FAIL:", f["name"], "->", f.get("reason", "")[:120])
    print("=" * 96)


if __name__ == "__main__":
    main()
