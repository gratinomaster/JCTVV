#!/usr/bin/env python3
import re, sys, requests
from urllib.parse import urljoin, urlsplit, urlunsplit

PL = '/home/runner/work/JCTVV/JCTVV/lista5.m3u'
H = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': '*/*'
}

def inherit(base, ref):
    if '?' in base:
        return base
    q = urlsplit(ref).query
    if not q:
        return base
    s, n, p, _, f = urlsplit(base)
    return urlunsplit((s, n, p, q, f))

def test_stream(url, name):
    try:
        r = requests.get(url, headers=H, timeout=40)
        if r.status_code != 200:
            return False, f'HTTP {r.status_code}'
        if '#EXTM3U' not in r.text:
            return False, 'not m3u8'
        # look for variants (.m3u8) but not AUDIO URI in media
        lines = r.text.splitlines()
        var_urls = []
        for line in lines:
            if line.startswith('#'):
                continue
            if line.strip().endswith('.m3u8') and not line.strip().startswith('audio-'):
                var_urls.append(line.strip())
        if not var_urls:
            # fallback
            var = re.findall(r'(?m)^(?!\s*#)(\S+\.m3u8\S*)$', r.text)
            var_urls = var
        if not var_urls:
            return False, 'no variant'
        vurl = inherit(urljoin(url, var_urls[0]), url)
        vr = requests.get(vurl, headers=H, timeout=40)
        if vr.status_code != 200:
            return False, f'var HTTP {vr.status_code}'
        seg = re.findall(r'(?m)^(?!\s*#)(\S+\.(?:ts|m4s))\S*$', vr.text)
        if not seg:
            # maybe mp4
            seg = re.findall(r'(?m)^(?!\s*#)(\S+\.(?:mp4|aac))\S*$', vr.text)
        if not seg:
            return False, 'no segment'
        surl = inherit(urljoin(vurl, seg[-1]), vurl)
        sr = requests.get(surl, headers=H, timeout=60, stream=True)
        if sr.status_code != 200:
            return False, f'seg HTTP {sr.status_code}'
        b = next(sr.iter_content(65536), b'')
        sr.close()
        magic = b[0] == 0x47 or any(k in b[:64] for k in (b'ftyp', b'styp', b'moof', b'mdat', b'sidx'))
        if len(b) < 1024 or not magic:
            return False, 'bad segment'
        return True, 'ok'
    except Exception as e:
        return False, type(e).__name__

def main():
    with open(PL, encoding='utf-8') as f:
        lines = [l.rstrip('\n').rstrip('\r') for l in f]

    hdr = lines[0] if lines else ''
    kept = []
    removed = []

    pending = None
    for l in lines[1:]:
        if l.startswith('#EXTINF'):
            pending = l
        elif l.startswith('#'):
            continue
        elif pending is not None:
            url = l.strip()
            name = re.search(r'tvg-name="([^"]+)"', pending)
            n = name.group(1) if name else (re.search(r',(.+)$', pending).group(1).strip() if ',' in pending else pending)
            ok, reason = test_stream(url, n)
            if ok:
                kept.append((pending, url))
            else:
                removed.append((n, reason))
            pending = None
        else:
            pending = None

    out = [hdr]
    for extinf, url in kept:
        out.append(extinf)
        out.append(url)
    with open(PL, 'w', encoding='utf-8') as f:
        f.write('\n'.join(out) + ('\n' if out else ''))

    print(f'kept={len(kept)} removed={len(removed)}')
    for r in removed[:10]:
        print('REM:', r[0], r[1])

if __name__ == '__main__':
    main()
