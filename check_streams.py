#!/usr/bin/env python3
"""Test every URL in an .m3u playlist and rewrite the file keeping only working ones.

A channel is kept only when all of the following hold:

  1. the manifest URL answers HTTP 200 and is a valid M3U8 playlist;
  2. the referenced media playlist is reachable (master playlists are followed
     down to a variant), and
  3. a real media segment referenced by that playlist can actually be
     downloaded (not an error page, not empty).

With --live (default on) the playlist is fetched a second time after a short
wait and a segment that appeared in the meantime is downloaded, which proves
the encoder is really producing new content and the feed is not a frozen or
placeholder playlist.
"""

import concurrent.futures
import sys
import time
import urllib.parse
import urllib.request

PLAYLIST = sys.argv[1] if len(sys.argv) > 1 else "lista5.m3u"
ARGS = sys.argv[2:]
DRY_RUN = "--dry-run" in ARGS
LIVE = "--no-live" not in ARGS
LIVE_WAIT = 12
MIN_SEGMENT = 1024
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
TIMEOUT = 12


def fetch(url, limit=None, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        if r.status != 200:
            raise OSError(f"HTTP {r.status}")
        return r.read(limit if limit else 1 << 20)


def is_m3u8(data):
    head = data.lstrip()[:200]
    return head.startswith(b"#EXTM3U")


def inherit_query(parent, child):
    """Tokenized CDNs (Fox hdnea, etc.) require the parent's query string on
    child playlist/segment URLs. Forward it when the child has none."""
    if not child:
        return child
    pq = urllib.parse.urlsplit(parent).query
    if not pq:
        return child
    parts = urllib.parse.urlsplit(child)
    if parts.query:
        return child
    return urllib.parse.urlunsplit(parts._replace(query=pq))


def absolutize(base, ref):
    if not ref or ref.startswith("#"):
        return None
    if ref.startswith("//"):
        return "https:" + ref
    return inherit_query(base, urllib.parse.urljoin(base, ref))


def pick_variants(body, base, limit=4):
    """Return up to `limit` variant playlist URLs from a master playlist."""
    variants, expecting = [], False
    for raw in body.splitlines():
        line = raw.decode("utf-8", "replace").strip()
        if not line:
            continue
        if line.startswith("#EXT-X-STREAM-INF"):
            expecting = True
        elif line.startswith("#"):
            continue
        elif expecting:
            variants.append(absolutize(base, line))
            expecting = False
            if len(variants) >= limit:
                break
    return variants


def segment_urls(target, manifest):
    out = []
    for raw in manifest.splitlines():
        line = raw.decode("utf-8", "replace").strip()
        if line and not line.startswith("#"):
            out.append(absolutize(target, line))
    return out


def get_segment(url, min_size=MIN_SEGMENT):
    """Download a segment and sanity-check it. Returns (size, None) or (0, reason)."""
    try:
        data = fetch(url, limit=1 << 20)
    except Exception as e:
        return 0, f"HTTP {type(e).__name__} {e}"
    if len(data) < min_size:
        return len(data), f"too small ({len(data)}B)"
    return len(data), None


def probe(url):
    """Return (ok, reason). Requires a valid manifest chain and a real segment.

    With LIVE enabled, also requires the playlist to roll forward: a segment
    that appears after the wait must exist and be downloadable, proving the
    encoder is actively producing content.
    """
    try:
        manifest = fetch(url)
    except Exception as e:
        return False, f"manifest: {type(e).__name__} {e}"

    if not is_m3u8(manifest):
        return False, "manifest: not a valid m3u8 (no #EXTM3U)"

    target = url
    if b"#EXT-X-STREAM-INF" in manifest:
        variants = pick_variants(manifest, url)
        if not variants:
            return False, "master playlist: no variants listed"
        last = "no variant usable"
        for variant in variants:
            try:
                vman = fetch(variant)
            except Exception as e:
                last = f"variant: {type(e).__name__} {e}"
                continue
            if not is_m3u8(vman):
                last = "variant: not a valid m3u8"
                continue
            target, manifest = variant, vman
            break
        else:
            return False, last

    segs = segment_urls(target, manifest)
    if not segs:
        return False, "playlist: no media segments listed"

    size, err = get_segment(segs[0])
    if err:
        return False, f"segment: {err}"

    if not LIVE:
        return True, f"ok ({len(manifest)}B manifest, seg {size}B)"

    time.sleep(LIVE_WAIT)
    try:
        manifest2 = fetch(target)
        if not is_m3u8(manifest2):
            return False, "recheck: playlist no longer valid"
    except Exception as e:
        return False, f"recheck: {type(e).__name__} {e}"

    fresh = [s for s in segment_urls(target, manifest2) if s not in set(segs)]
    if not fresh:
        if b"#EXT-X-ENDLIST" in manifest2:
            return False, "not live: playlist ended (VOD/archived, no #EXT-X-MEDIA-SEQUENCE)"
        return False, "not live: playlist did not advance"

    new_size, err = get_segment(fresh[-1])
    if err:
        return False, f"fresh segment: {err}"

    return True, f"LIVE ok (+{len(fresh)} new seg, {new_size}B downloaded)"


def read_entries(path):
    entries, header = [], []
    with open(path, encoding="utf-8", errors="replace") as f:
        lines = f.read().splitlines()

    meta = None
    for line in lines:
        s = line.strip()
        if s.startswith("#EXTINF"):
            meta = line
        elif s and not s.startswith("#"):
            if meta is not None:
                entries.append((meta, s))
            meta = None
        elif s.startswith("#") and not entries and not header:
            header.append(line)
    return header, entries


def name_of(meta):
    return meta.split(",", 1)[-1].strip()


def main():
    header, entries = read_entries(PLAYLIST)
    print(f"{PLAYLIST}: {len(entries)} channel(s) to test\n")

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(probe, url): (meta, url) for meta, url in entries}
        for fut in concurrent.futures.as_completed(futures):
            meta, url = futures[fut]
            try:
                ok, reason = fut.result()
            except Exception as e:
                ok, reason = False, f"error: {e}"
            results.append((ok, meta, url, reason))

    results.sort(key=lambda r: entries.index((r[1], r[2])))

    good, bad = [], []
    for ok, meta, url, reason in results:
        (good if ok else bad).append((meta, url))
        print(f"{'OK  ' if ok else 'FAIL'} | {name_of(meta)[:58]:<58} | {reason}")

    # rewrite playlist
    keep_urls = {u for _, u in good}
    out = list(header) if header else ["#EXTM3U"]
    for meta, url in entries:
        if url in keep_urls:
            out.append(meta)
            out.append(url)

    if DRY_RUN:
        print("\nDRY RUN - not writing file")
    else:
        with open(PLAYLIST, "w", encoding="utf-8") as f:
            f.write("\n".join(out) + "\n")

    print(f"\n{'=' * 70}")
    print(f"working : {len(good)}")
    print(f"removed : {len(bad)}")
    if bad:
        print("\nRemoved channels:")
        for meta, url in bad:
            print(f"  - {name_of(meta)}")


if __name__ == "__main__":
    main()
