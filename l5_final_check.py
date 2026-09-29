#!/usr/bin/env python3
"""Final validation of lista5.m3u: structure, logos, streams, EPG, anti-virus."""
import os, re, sys, gzip, json, subprocess, requests
import xml.etree.ElementTree as ET

F = "lista5.m3u"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
H = {"User-Agent": UA}
CACHE = "/tmp/opencode/final"
os.makedirs(CACHE, exist_ok=True)
fails, warns = [], []


def chk(cond, msg):
    print(("  PASS  " if cond else "  FAIL  ") + msg)
    if not cond:
        fails.append(msg)
    return cond


def warn(cond, msg):
    if not cond:
        print("  WARN  " + msg); warns.append(msg)
    return cond


raw = open(F, encoding="utf-8").read()
lines = raw.splitlines()

print("=" * 92)
print("FINAL VALIDATION --", F)
print("=" * 92)

# ---------- 1. structure ----------
print("\n[1] M3U structure")
chk(lines[0].startswith("#EXTM3U"), "first line is #EXTM3U")
chk(all(l.strip() for l in lines), "no blank / stray lines")
chk(raw == raw.rstrip() + "\n", "file ends with a single trailing newline")
chk("\r" not in raw, "unix line endings (no CR)")

entries, orphan, noinfo = [], [], []
info = None
for i, l in enumerate(lines):
    s = l.strip()
    if s.startswith("#EXTM3U"):
        continue
    if s.startswith("#EXTINF"):
        info = s
    elif s.startswith("#"):
        continue
    elif s:
        if info is None:
            orphan.append((i + 1, s))
        else:
            entries.append((info, s))
            info = None
chk(not orphan, f"no channel link without an #EXTINF line above it ({len(orphan)} orphans)")
for n, s in orphan[:5]:
    print(f"        line {n}: {s[:80]}")

chk(info is None, "no dangling #EXTINF without a link")
print(f"        -> {len(entries)} entries, {len({u for _, u in entries})} unique links")
chk(len({u for _, u in entries}) == len(entries), "no duplicate links")

# every entry has tvg-id, tvg-name, group-title, and a real name after the comma
bad_attr = [e for e, _ in entries if not all(k in e for k in ("tvg-id=", "tvg-name=", "tvg-logo=", "group-title="))]
chk(not bad_attr, f"every #EXTINF has tvg-id + tvg-name + tvg-logo + group-title ({len(bad_attr)} bad)")
for e, _ in bad_attr[:3]:
    print("        ", e[:110])

# ---------- 2. EPG declaration ----------
print("\n[2] EPG (url-tvg)")
m = re.match(r'#EXTM3U\s+url-tvg="([^"]+)"', lines[0])
chk(bool(m), "#EXTM3U header carries url-tvg")
epgs = m.group(1).split() if m else []
print(f"        -> {len(epgs)} EPG source(s):")
ok_epg = 0
for e in epgs:
    try:
        r = requests.get(e, headers=H, timeout=280, stream=True)
        p = os.path.join(CACHE, e.rsplit("/", 1)[-1])
        tot = 0
        with open(p, "wb") as fh:
            for ch in r.iter_content(1 << 20):
                fh.write(ch); tot += len(ch)
                if tot > 60 * 1024 * 1024:
                    break
        inf = subprocess.run(["sudo", "clamscan", "--no-summary", "--infected", p],
                             capture_output=True, timeout=1200).stdout.decode()
        inf = [l for l in inf.splitlines() if l.endswith("FOUND")]
        good = r.status_code == 200 and not inf
        print(f"           {e}\n             {r.status_code}  {tot/1e6:.1f}MB  clamscan={'INFECTED '+str(inf) if inf else 'clean'}")
        ok_epg += bool(good)
        if not good:
            fails.append(f"EPG {e}")
    except Exception as ex:
        print(f"           {e}\n             ERROR {ex}"); fails.append(f"EPG {e}")
chk(ok_epg == len(epgs) and epgs, f"all {len(epgs)} EPG url(s) reachable + AV clean")

# ---------- 3. tvg-id resolution + 3-day coverage ----------
print("\n[3] EPG resolution: every tvg-id found, with today / tomorrow / +2 days")
ids = [re.search(r'tvg-id="([^"]+)"', e).group(1) for e, _ in entries]
today = "20260929"
for e, u in entries:
    tid = re.search(r'tvg-id="([^"]+)"', e).group(1)
    nm = re.search(r'tvg-name="([^"]+)"', e).group(1)
    label = e.split(",", 1)[1]
    for e_src in epgs:
        p = os.path.join(CACHE, e_src.rsplit("/", 1)[-1])
        if not os.path.exists(p):
            continue
        op = gzip.open if p.endswith(".gz") else open
        found, days, n = False, set(), 0
        with op(p, "rb") as fh:
            for ev, el in ET.iterparse(fh, events=("end",)):
                if el.tag == "programme":
                    if el.get("channel") == tid:
                        found = True; n += 1; days.add(el.get("start")[:8])
                    el.clear()
                elif el.tag == "channel" and el.get("id") == tid:
                    found = found or True
        need = {"20260929", "20260930", "20261001"}
        have = need & days
        good = found and len(have) == 3
        src = "epg.pw" if "epg.pw" in e_src else "epgshare01"
        print(f"  {'PASS' if good else 'FAIL'}  {label[:44]:44} id={tid:7} {src:11} progs={n:4} dias={sorted(have)}")
        if not good:
            fails.append(f"EPG coverage {label} ({src})")
        break

# ---------- 4. logos ----------
print("\n[4] tvg-logo (.jpg, no imgur, reachable)")
logos = []
for e, _ in entries:
    logos.append(re.search(r'tvg-logo="([^"]+)"', e).group(1))
uniq = sorted(set(logos))
for lg in uniq:
    jpg = ".jpg" in lg.split("?")[0].lower()
    noim = "imgur.com" not in lg.lower()
    try:
        r = requests.get(lg, headers=H, timeout=30)
        jpeg = r.content[:2] == b"\xff\xd8"
        good = r.status_code == 200 and jpeg and jpg and noim and len(r.content) > 3000
        ct = r.headers.get("Content-Type", "")
        chk(good, f"{lg[:66]:66} {r.status_code} {len(r.content)//1024:3d}KB {ct} jpg={jpg} noImgur={noim}")
    except Exception as ex:
        chk(False, f"{lg[:66]:66} ERROR {ex}")

# ---------- 5. streams ----------
print("\n[5] Stream playback test (ffmpeg decodes real A/V)")
for e, u in entries:
    label = e.split(",", 1)[1]
    cmd = ["ffmpeg", "-hide_banner", "-v", "error", "-user_agent", UA,
           "-rw_timeout", "25000000", "-i", u, "-t", "6",
           "-map", "0:v:0", "-map", "0:a:0?", "-f", "null", "-"]
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=70)
        err = p.stderr.decode(errors="replace").strip()
        chk(p.returncode == 0 and not err, f"{label[:44]:44} rc={p.returncode} {err[:60]}")
    except subprocess.TimeoutExpired:
        chk(False, f"{label[:44]:44} TIMEOUT")

# ---------- 6. anti-virus on final streams ----------
print("\n[6] Anti-virus (ClamAV) on the delivered media payloads")
def walk(url, d, blobs, seen, md=3):
    if d > md or url in seen or len(blobs) > 10: return
    seen.add(url)
    r = None
    for attempt in range(3):
        try:
            r = requests.get(url, headers=H, timeout=30)
            if r.status_code == 200: break
        except Exception as ex:
            print(f"        (retry {attempt+1} {url[:60]}: {ex.__class__.__name__})")
            r = None
    if r is None or r.status_code != 200:
        print(f"        !! could not fetch {url[:90]}")
        return
    t = r.text
    if not t.lstrip().startswith("#EXTM3U"): return
    ls = [x.strip() for x in t.splitlines() if x.strip() and not x.strip().startswith("#")]
    from urllib.parse import urljoin
    kids = [urljoin(url, x) for x in ls if x.split("?")[0].endswith(".m3u8")]
    med  = [urljoin(url, x) for x in ls if not x.split("?")[0].endswith(".m3u8")]
    if kids and not med:
        for k in kids[:2]: walk(k, d + 1, blobs, seen, md)
    else:
        blobs.append(r.content)
        for m in med[:2]:
            for attempt in range(3):
                try:
                    rr = requests.get(m, headers=H, timeout=30)
                    if rr.status_code == 200:
                        blobs.append(rr.content); break
                except Exception:
                    pass
for e, u in entries:
    label = e.split(",", 1)[1]
    blobs, seen = [], set()
    walk(u, 0, blobs, seen)
    paths = []
    for i, b in enumerate(blobs):
        if b:
            pth = os.path.join(CACHE, f"av_{abs(hash(u))%9999}_{i}.bin")
            open(pth, "wb").write(b); paths.append(pth)
    inf = []
    if paths:
        inf = [l for l in subprocess.run(["sudo", "clamscan", "--no-summary", "--infected", *paths],
              capture_output=True, timeout=1200).stdout.decode().splitlines() if l.endswith("FOUND")]
    total = sum(len(b) for b in blobs)
    html = any(b"<!DOCTYPE html" in b[:1500] or b"<html" in b[:1500].lower() for b in blobs)
    chk(len(blobs) >= 3 and not inf and not html,
        f"{label[:44]:44} payloads={len(blobs)} {total/1e6:.2f}MB infected={len(inf)}")

print("\n" + "=" * 92)
print(f"RESULT: {len(fails)} FAILURES, {len(warns)} warnings")
for f in fails: print("  FAIL:", f)
print("=" * 92)
sys.exit(1 if fails else 0)
