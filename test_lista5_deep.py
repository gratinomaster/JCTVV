#!/usr/bin/env python3
import re
import shutil
import concurrent.futures
import requests
from datetime import datetime

SRC = "lista5.m3u"
BAK = f"lista5.m3u.bak.pre_teste_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
TIMEOUT = 15

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept": "*/*",
    "Referer": "https://www.google.com/",
}

def parse_m3u(path):
    entries = []
    header = None
    with open(path, encoding="utf-8") as f:
        lines = [l.rstrip("\n") for l in f]
    i = 0
    if lines and lines[0].startswith("#EXTM3U"):
        header = lines[0]
        i = 1
    while i < len(lines):
        line = lines[i]
        if line.startswith("#EXTINF"):
            extinf = line
            url_lines = []
            i += 1
            while i < len(lines) and (lines[i].startswith("#") or lines[i].strip() == ""):
                if lines[i].startswith("#EXTINF"):
                    break
                i += 1
            while i < len(lines) and not lines[i].startswith("#") and lines[i].strip() != "":
                url_lines.append(lines[i])
                i += 1
            entries.append({"extinf": extinf, "urls": url_lines})
        else:
            i += 1
    return header, entries

def join(base, path):
    from urllib.parse import urljoin
    return urljoin(base, path)

def get_manifest(url):
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    if r.status_code != 200:
        return None
    return r.text

def deep_test(url):
    """master -> variante -> segmento real"""
    try:
        txt = get_manifest(url)
        if not txt or "#EXTM3U" not in txt:
            return False
        lines = [l.strip() for l in txt.splitlines() if l.strip()]
        # master playlist: contém URIs de outras playlists
        variants = [l for l in lines if not l.startswith("#")]
        if any("#EXT-X-STREAM-INF" in l for l in lines):
            # pegar variante de maior bandwidth possível
            best = None
            cur_bw = -1
            for idx, l in enumerate(lines):
                if l.startswith("#EXT-X-STREAM-INF"):
                    m = re.search(r'BANDWIDTH=(\d+)', l)
                    bw = int(m.group(1)) if m else 0
                    uri = lines[idx + 1] if idx + 1 < len(lines) and not lines[idx + 1].startswith("#") else None
                    if uri and bw >= cur_bw:
                        best, cur_bw = uri, bw
            target = best or (variants[0] if variants else None)
            if not target:
                return True
            vurl = join(url, target)
            vtxt = get_manifest(vurl)
            if not vtxt or "#EXTINF" not in vtxt:
                return False
            segs = [l.strip() for l in vtxt.splitlines() if l.strip() and not l.startswith("#")]
            if not segs:
                return False
            surl = join(vurl, segs[-1])
            try:
                rs = requests.get(surl, headers=HEADERS, timeout=TIMEOUT, stream=True)
                ok = rs.status_code == 200 and len(next(rs.iter_content(2048), b"")) > 100
                rs.close()
                return ok
            except Exception:
                return False
        else:
            # media playlist direta: baixar um segmento
            segs = [l for l in lines if not l.startswith("#")]
            if not segs:
                return False
            surl = join(url, segs[-1])
            try:
                rs = requests.get(surl, headers=HEADERS, timeout=TIMEOUT, stream=True)
                ok = rs.status_code == 200 and len(next(rs.iter_content(2048), b"")) > 100
                rs.close()
                return ok
            except Exception:
                return False
    except Exception:
        return False

def test_entry(entry):
    # tenta cada URL; canal funciona se pelo menos 1 URL tocar de verdade
    ok_any = False
    for u in entry["urls"]:
        if deep_test(u):
            ok_any = True
            break
    return entry, ok_any

shutil.copy(SRC, BAK)

header, entries = parse_m3u(SRC)
print(f"Teste profundo (manifesto -> variante -> segmento): {len(entries)} canais")

results = []
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
    for res in ex.map(test_entry, entries):
        results.append(res)
        name = re.sub(r'^.*?,', '', res[0]["extinf"])[:60]
        print(f"[{'OK ' if res[1] else 'FALHA'}] {name}")

working = [e for e, ok in results if ok]
failed = [e for e, ok in results if not ok]

with open(SRC, "w", encoding="utf-8") as f:
    f.write((header or "#EXTM3U") + "\n")
    for e in working:
        f.write(e["extinf"] + "\n")
        for u in e["urls"]:
            f.write(u + "\n")

print("\n=== RESUMO ===")
print(f"Funcionando: {len(working)} | Removidos: {len(failed)}")
for e in failed:
    name = re.sub(r'^.*?,', '', e["extinf"])[:70]
    print(f"  REMOVIDO: {name}")
