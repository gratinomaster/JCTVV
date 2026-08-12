#!/usr/bin/env python3
"""Deep validation v2: follow master->variant (keeping query token), fetch newest segment."""

import subprocess
import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

FILEPATH = '/home/runner/work/JCTVV/JCTVV/lista5.m3u'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'


def fetch(url, timeout=20, binary=False):
    try:
        r = subprocess.run(
            ['curl', '-s', '-L', '--max-time', str(timeout), '--connect-timeout', '10',
             '-H', f'User-Agent: {UA}', url],
            capture_output=True, timeout=timeout + 5
        )
        if r.returncode != 0:
            return None, f"curl error {r.returncode}"
        return (r.stdout if binary else r.stdout.decode('utf-8', errors='replace')), None
    except subprocess.TimeoutExpired:
        return None, "timeout"
    except Exception as e:
        return None, str(e)[:80]


def merge(base, ref):
    """Resolve ref against base, preserving base's query string if ref has none."""
    parsed = urllib.parse.urlsplit(ref)
    if not parsed.scheme:
        ref = urllib.parse.urljoin(base, ref)
        parsed = urllib.parse.urlsplit(ref)
    if not parsed.query:
        bq = urllib.parse.urlsplit(base).query
        if bq:
            ref = ref + ('?' if '?' not in ref else '&') + bq
    return ref


def parse_m3u(filepath):
    entries = []
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = [l.rstrip('\n') for l in f.readlines()]
    i = 0
    while i < len(lines):
        if lines[i].startswith('#EXTINF:'):
            extinf = lines[i]
            i += 1
            while i < len(lines) and lines[i].strip() and not lines[i].startswith('#'):
                entries.append((extinf, lines[i].strip()))
                i += 1
            i -= 1
        i += 1
    return entries


def deep_check(url):
    body, err = fetch(url)
    if body is None:
        return False, err
    if '#EXTM3U' not in body:
        return False, "not m3u8"

    variants = re.findall(r'^#EXT-X-STREAM-INF[^\n]*\n(\S+)', body, re.M)
    media_url = url
    if variants:
        v_url = merge(url, variants[0])
        vbody, verr = fetch(v_url)
        if vbody is None:
            return False, f"variant failed: {verr}"
        if '#EXTM3U' not in vbody:
            return False, f"variant not m3u8: {vbody[:60]}"
        body = vbody
        media_url = v_url

    segs = re.findall(r'^[^#]\S+', body, re.M)
    if not segs:
        return False, "media playlist with no segments"

    for seg in reversed(segs[-5:]):
        s_url = merge(media_url, seg)
        sbody, serr = fetch(s_url, timeout=25, binary=True)
        if sbody is None:
            continue
        if len(sbody) >= 1000:
            return True, f"segment OK ({len(sbody)} bytes)"
    return False, "segments unavailable/small"


def name_of(extinf):
    m = re.search(r',(.+)$', extinf)
    return m.group(1).strip() if m else extinf


def main():
    entries = parse_m3u(FILEPATH)
    unique = list(dict.fromkeys(url for _, url in entries))
    print(f"Total entradas: {len(entries)} | URLs únicas: {len(unique)}")

    results = {}
    with ThreadPoolExecutor(max_workers=10) as ex:
        futs = {ex.submit(deep_check, u): u for u in unique}
        for i, f in enumerate(as_completed(futs)):
            u = futs[f]
            ok, msg = f.result()
            results[u] = (ok, msg)
            status = "OK" if ok else f"FALHOU ({msg})"
            print(f"  [{i+1}/{len(unique)}] {status} - {name_of(next(e for e, uu in entries if uu == u))[:55]}")

    working = sum(1 for ok, _ in results.values() if ok)
    print(f"\nDeep check: {working}/{len(unique)} URLs reproduzíveis")
    for u, (ok, msg) in results.items():
        if not ok:
            print(f"  DEAD: {u[:100]} -> {msg}")


if __name__ == '__main__':
    main()
