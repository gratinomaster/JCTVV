import urllib.request
import urllib.error
import ssl
import time
import sys

input_file = "lista5.m3u"
output_file = "lista5_new.m3u"

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

lines = open(input_file, "r", encoding="utf-8").readlines()
lines = [l.rstrip("\n\r") for l in lines]

if not lines or not lines[0].startswith("#EXTM3U"):
    print("Invalid M3U file")
    sys.exit(1)

entries = []
i = 1
while i < len(lines):
    if lines[i].startswith("#EXTINF:"):
        name = lines[i]
        i += 1
        if i < len(lines) and not lines[i].startswith("#"):
            url = lines[i]
            i += 1
            entries.append((name, url))
        else:
            i += 1
    else:
        i += 1

stat_counts = {"ok": 0, "fail": 0}
working = []
failed = []

def test_url(url, name, idx, total):
    chan = name.split(",", 1)[-1].strip() if "," in name else "unknown"
    sys.stdout.write(f"[{idx}/{total}] {chan[:45]:45s} ")
    sys.stdout.flush()
    
    # Try HEAD first
    try:
        req = urllib.request.Request(url, method="HEAD")
        resp = urllib.request.urlopen(req, timeout=10, context=ssl_ctx)
        status = resp.getcode()
        resp.close()
        if status < 400:
            sys.stdout.write(f"OK (HEAD {status})\n")
            sys.stdout.flush()
            return True
    except:
        pass
    
    # Try GET with small range
    try:
        req = urllib.request.Request(url, method="GET")
        req.add_header("Range", "bytes=0-0")
        resp = urllib.request.urlopen(req, timeout=15, context=ssl_ctx)
        status = resp.getcode()
        resp.close()
        if status in (200, 206) or status < 400:
            sys.stdout.write(f"OK (GET {status})\n")
            sys.stdout.flush()
            return True
    except urllib.error.HTTPError as e:
        if e.code == 405:
            # Try without Range
            pass
        sys.stdout.write(f"FAIL (HTTP {e.code})\n")
        sys.stdout.flush()
        return False
    except Exception as e:
        sys.stdout.write(f"FAIL ({type(e).__name__})\n")
        sys.stdout.flush()
        return False
    
    # Try plain GET with short timeout
    try:
        req = urllib.request.Request(url, method="GET")
        resp = urllib.request.urlopen(req, timeout=8, context=ssl_ctx)
        status = resp.getcode()
        # Read just a bit
        data = resp.read(1024)
        resp.close()
        sys.stdout.write(f"OK (GET {status})\n")
        sys.stdout.flush()
        return True
    except Exception as e:
        sys.stdout.write(f"FAIL ({type(e).__name__})\n")
        sys.stdout.flush()
        return False

print(f"Testing {len(entries)} entries...\n")
for idx, (name, url) in enumerate(entries, 1):
    if test_url(url, name, idx, len(entries)):
        working.append((name, url))
        stat_counts["ok"] += 1
    else:
        failed.append((name, url))
        stat_counts["fail"] += 1
    time.sleep(0.3)

with open(output_file, "w", encoding="utf-8") as f:
    f.write("#EXTM3U\n")
    for name, url in working:
        f.write(name + "\n")
        f.write(url + "\n")

print(f"\n=== Summary ===")
print(f"Working: {stat_counts['ok']}")
print(f"Failed:  {stat_counts['fail']}")
print(f"Output:  {output_file}")
