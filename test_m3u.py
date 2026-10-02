import sys
import requests

M3U_PATH = '/home/runner/work/JCTVV/JCTVV/lista5.m3u'

def parse_m3u(path):
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    entries = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.strip().startswith('#EXTINF'):
            extinf = line
            # next line is URL if present
            j = i + 1
            while j < len(lines) and lines[j].strip() == '':
                j += 1
            url = lines[j].strip() if j < len(lines) else ''
            entries.append((extinf, url))
            i = j + 1
            continue
        i += 1
    return entries, lines

def is_working(url):
    if not url or not (url.startswith('http://') or url.startswith('https://')):
        return False
    try:
        # Try HEAD first, fallback to GET with range/short
        r = requests.head(url, allow_redirects=True, timeout=5, headers={'User-Agent':'curl/7.88.1'})
        if r.status_code < 400:
            return True
        # some servers don't support HEAD
        r = requests.get(url, allow_redirects=True, timeout=8, headers={'User-Agent':'curl/7.88.1', 'Range':'bytes=0-0'})
        return r.status_code < 400
    except Exception:
        return False

def main():
    entries, _ = parse_m3u(M3U_PATH)
    print(f'Testing {len(entries)} entries...')
    working = []
    for k, (extinf, url) in enumerate(entries, 1):
        ok = is_working(url)
        if ok:
            working.append((extinf, url))
        if k % 5 == 0:
            print(f'{k}/{len(entries)} tested, working so far: {len(working)}')
    # rebuild m3u
    out = ['#EXTM3U\n']
    for extinf, url in working:
        out.append(extinf)
        out.append(url + '\n')
    with open(M3U_PATH, 'w', encoding='utf-8') as f:
        f.writelines(out)
    print(f'Done. Kept {len(working)}/{len(entries)} channels.')

if __name__ == '__main__':
    main()
