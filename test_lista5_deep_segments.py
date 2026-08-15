#!/usr/bin/env python3
"""Test lista5.m3u streams deeply by downloading an actual media segment."""

import subprocess
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlsplit, urlunsplit

SEG_EXTS = re.compile(r'\.(?:ts|m4s|mp4|aac|m4a|mp3|f4f|aac|aac)$', re.I)

def inherit_query(url, base_url):
    if '?' in url:
        return url
    q = urlsplit(base_url).query
    if q:
        scheme, netloc, path, _, frag = urlsplit(url)
        return urlunsplit((scheme, netloc, path, q, frag))
    return url

def fetch(url, timeout=20):
    return subprocess.run(
        ['curl', '-s', '-L', '--max-time', str(timeout), '--connect-timeout', '10', url],
        capture_output=True, text=True, timeout=timeout + 5
    )

def test_url_deep(url, timeout=25, depth=0):
    if depth > 3:
        return False, "profundidade máxima"
    m = fetch(url, timeout)
    if m.returncode != 0:
        return False, f"curl manifest error {m.returncode}"
    body = m.stdout
    if not body.strip():
        return False, "manifest vazio"
    if re.search(r'<(?:html|!doctype)', body, re.I):
        return False, "página de erro HTML"

    seg_urls = []
    lines = body.splitlines()
    i = 0
    for line in lines:
        s = line.strip()
        if not s or s.startswith('#'):
            continue
        if SEG_EXTS.search(s):
            seg_urls.append(s)
        elif s.endswith('.m3u8'):
            seg_urls.append(s)

    if not seg_urls:
        with open('/tmp/deep_fail_body.txt', 'w') as f:
            f.write(f"URL: {url}\nLEN: {len(body)}\nBODY:\n{body[:2000]}\n")
        return False, "manifest sem segmentos/streams"

    seg = seg_urls[0]
    seg_url = urljoin(url, seg)
    seg_url = inherit_query(seg_url, url)

    if '.m3u8' in seg:
        return test_url_deep(seg_url, timeout, depth + 1)

    probe = subprocess.run(
        ['curl', '-s', '-o', '/dev/null', '-w', '%{http_code} %{size_download}', '-I',
         '--max-time', '15', '--connect-timeout', '10', seg_url],
        capture_output=True, text=True, timeout=20
    )
    out = probe.stdout.strip()
    code = out.split()[0] if out else '000'
    if code == '200':
        return True, "segmento OK"
    if code == '403' or code == '000' or code == '429':
        try:
            probe2 = subprocess.run(
                ['curl', '-s', '-o', '/dev/null', '-w', '%{http_code} %{size_download}',
                 '--max-time', '20', '--connect-timeout', '10', seg_url],
                capture_output=True, text=True, timeout=25
            )
            out2 = probe2.stdout.strip()
            code2 = out2.split()[0] if out2 else '000'
            if code2 == '200':
                return True, "segmento OK (GET)"
            return False, f"segmento HTTP {code}/{code2}"
        except Exception:
            return False, f"segmento HTTP {code}"
    return False, f"segmento HTTP {code}"

def parse_m3u(filepath):
    entries = []
    with open(filepath, 'r') as f:
        lines = [l.rstrip('\n') for l in f.readlines()]
    i = 0
    while i < len(lines):
        if lines[i].startswith('#EXTINF:'):
            extinf = lines[i]
            i += 1
            if i < len(lines) and lines[i].strip() and not lines[i].startswith('#'):
                url = lines[i].strip()
                entries.append((extinf, url))
        i += 1
    return entries

def main():
    filepath = '/home/runner/work/JCTVV/JCTVV/lista5.m3u'
    entries = parse_m3u(filepath)
    print(f"Total de entradas: {len(entries)}")

    unique_urls = list(dict.fromkeys(url for _, url in entries))
    print(f"URLs únicas para testar: {len(unique_urls)}")

    results = {}
    with ThreadPoolExecutor(max_workers=4) as executor:
        future_to_url = {executor.submit(test_url_deep, url): url for url in unique_urls}
        for i, future in enumerate(as_completed(future_to_url)):
            url = future_to_url[future]
            ok, msg = future.result()
            if not ok:
                for attempt in range(3):
                    ok, msg = test_url_deep(url)
                    if ok:
                        break
            results[url] = ok
            name = ""
            for extinf, u in entries:
                if u == url:
                    m = re.search(r',(.+)$', extinf)
                    if m:
                        name = m.group(1).strip()[:60]
                    break
            status = "OK" if ok else f"FALHOU ({msg})"
            print(f"  [{i+1}/{len(unique_urls)}] {status} - {name}")

    new_entries = []
    removed = 0
    for extinf, url in entries:
        if results.get(url, False):
            new_entries.append((extinf, url))
        else:
            removed += 1

    print(f"\nRemovidas: {removed} entradas mortas")
    print(f"Mantidas: {len(new_entries)} entradas")

    with open(filepath, 'w') as f:
        f.write('#EXTM3U\n')
        for extinf, url in new_entries:
            f.write(extinf + '\n')
            f.write(url + '\n')

    print(f"Arquivo {filepath} sobrescrito com sucesso!")

    if removed > 0:
        print(f"\nCanais removidos:")
        seen = set()
        for extinf, url in entries:
            if not results.get(url, False) and url not in seen:
                m = re.search(r',(.+)$', extinf)
                name = m.group(1).strip() if m else url[:80]
                ok, reason = test_url_deep(url)
                print(f"  - {name} ({reason})")
                seen.add(url)

if __name__ == '__main__':
    main()
