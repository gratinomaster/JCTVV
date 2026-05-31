#!/usr/bin/env python3
import urllib.request
import urllib.error
import socket
import sys
import ssl

TIMEOUT = 10

def test_url(url):
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(url, method='GET')
        resp = urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx)
        code = resp.getcode()
        ct = resp.headers.get('Content-Type', '')
        resp.close()
        if code in (200, 201, 202, 204, 301, 302, 303, 307, 308):
            return True, f"HTTP {code} {ct[:40]}"
        return False, f"HTTP {code}"
    except urllib.error.HTTPError as e:
        if e.code in (301, 302, 303, 307, 308):
            return True, f"HTTP {e.code}"
        return False, f"HTTP {e.code}"
    except Exception as e:
        return False, str(e)[:60]


with open('lista5.m3u', 'r') as f:
    lines = f.read().splitlines()

entries = []
i = 0
while i < len(lines):
    if lines[i].startswith('#EXTM3U'):
        entries.append((lines[i], None))
        i += 1
    elif lines[i].startswith('#EXTINF:'):
        if i + 1 < len(lines):
            url = lines[i + 1].strip()
            entries.append((lines[i], url))
            i += 2
        else:
            entries.append((lines[i], None))
            i += 1
    elif lines[i].strip() == '':
        entries.append((lines[i], None))
        i += 1
    else:
        # orphan URL
        entries.append((None, lines[i].strip()))
        i += 1

print(f"Total entries: {len(entries)}")
print(f"Total EXTINF entries: {sum(1 for e in entries if e[0] and e[0].startswith('#EXTINF:'))}")

results = []
for extinf, url in entries:
    if url:
        ok, msg = test_url(url)
        results.append((extinf, url, ok, msg))
        status = "OK" if ok else "FAIL"
        name = extinf.split(',')[-1][:50] if extinf and extinf.startswith('#EXTINF:') else url[:50]
        print(f"  {status}: {msg:20s} | {name}")
    else:
        results.append((extinf, None, True, 'no-url'))

# Filter out non-working entries
working_results = []
removed = 0
for extinf, url, ok, msg in results:
    if ok:
        working_results.append((extinf, url))
    elif url:
        removed += 1

print(f"\nRemoved {removed} non-working entries")
print(f"Keeping {len(working_results)} entries")

# Write back
with open('lista5.m3u', 'w') as f:
    for extinf, url in working_results:
        if extinf:
            f.write(extinf + '\n')
        if url:
            f.write(url + '\n')

print("Written to lista5.m3u")
