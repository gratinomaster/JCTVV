#!/usr/bin/env python3
"""Validacao profunda final da lista5.m3u v10"""
import re, ssl, gzip
from urllib.request import Request, urlopen

ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
UA = {'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

def get(url, timeout=25):
    return urlopen(Request(url, headers=UA), timeout=timeout, context=ctx)

def deep_test_stream(url):
    """Testa manifest master -> primeira variante -> primeiro segmento."""
    try:
        master = get(url, 25).read(200000)
        if b'#EXT-X-STREAM-INF' not in master and b'#' not in master[:16].replace(b'#EXTM3U', b''):
            pass
        # extrai primeira variante
        lines = master.decode('utf-8', 'ignore').splitlines()
        varurl = None
        for i, ln in enumerate(lines):
            if ln.startswith('#EXT-X-STREAM-INF') and i+1 < len(lines):
                cand = lines[i+1].strip()
                if not cand.startswith('#'):
                    varurl = cand if cand.startswith('http') else url.rsplit('/',1)[0] + '/' + cand
                    break
        if varurl:
            var = get(varurl, 25).read(200000)
            vlines = var.decode('utf-8','ignore').splitlines()
            # procura ultima linha de segmento antes dos tags EXTINF
            segs = [l for l in vlines if l.strip() and not l.strip().startswith('#')]
            if not segs:
                return False, 'variante sem segmentos'
            seg = segs[-1] if segs[-1].startswith('http') else varurl.rsplit('/',1)[0] + '/' + segs[-1]
            s = get(seg, 20)
            data = s.read(1000)
            if s.status == 200 and len(data) > 100:
                return True, f'{len(segs)} segmentos | 1o segmento OK ({len(data)} bytes)'
            return False, f'segmento {s.status}'
        return True, 'master sem variantes (single) '
    except Exception as e:
        return False, f'{type(e).__name__}: {str(e)[:70]}'

def epg_coverage(epg_url, ids):
    import xml.etree.ElementTree as ET
    from datetime import datetime, timedelta, timezone
    data = get(epg_url, 180).read()
    data = gzip.decompress(data) if epg_url.endswith('.gz') else data
    today = datetime.now(timezone.utc)
    days = [(today+timedelta(days=i)).strftime('%Y%m%d') for i in range(3)]
    c = {i: [0,0,0] for i in ids}
    root = ET.fromstring(data)
    for p in root.findall('programme'):
        ch = p.get('channel')
        if ch in c:
            d = p.get('start','')[:8]
            for k, dd in enumerate(days):
                if d == dd: c[ch][k]+=1
    return c

def main():
    m3u = '/home/runner/work/JCTVV/JCTVV/lista5.m3u'
    content = open(m3u, encoding='utf-8').read()
    lines = content.strip().split('\n')
    entries = []
    cur = None
    for ln in lines:
        if ln.startswith('#EXTINF:'):
            tid = re.search(r'tvg-id="([^"]+)"', ln)
            name = ln.split(',',1)[1].strip()
            cur = {'extinf': ln, 'tvg_id': tid.group(1) if tid else None, 'name': name}
        elif ln.strip().startswith('http'):
            cur['url'] = ln.strip()
            entries.append(cur)
            cur = None
    print(f"CANAIS NA LISTA: {len(entries)}\n" + "="*70)
    for e in entries:
        print(f"\n[{e['name']}]  tvg-id={e['tvg_id']}")
        ok, why = deep_test_stream(e['url'])
        print(f"  STREAM : {'OK  ' if ok else 'FALHA'} {why}")
    epg_url = 'https://iptv-epg.org/files/epg-us.xml.gz'
    print(f"\n\nTESTE EPG: {epg_url}\n" + "="*70)
    ids = [e['tvg_id'] for e in entries]
    cov = epg_coverage(epg_url, ids)
    for i in ids:
        h,a,d = cov[i]
        print(f"  {i:22s} hoje={h} amanha={a} depois={d}  {'OK' if h and a and d else 'INSUFICIENTE'}")

    print("\nVERIFICACAO ESTRUTURAL" + "="*70)
    errs = []
    for i, ln in enumerate(lines):
        if re.match(r'^https?://', ln):
            if i==0 or not lines[i-1].startswith('#EXTINF:'):
                errs.append(f"linha {i+1}: URL sem #EXTINF acima")
        if 'imgur.com' in ln.lower(): errs.append(f"linha {i+1}: imgur.com")
        m = re.search(r'tvg-logo="([^"]+)"', ln)
        if m and not re.search(r'\.jpe?g($|\?)', m.group(1).lower()):
            errs.append(f"linha {i+1}: logo nao jpg")
    dupes = [e['name'] for e in entries]
    seen=set(); dup=[]
    for x in dupes:
        if x in seen: dup.append(x)
        seen.add(x)
    if dup: errs.append(f"duplicatas: {dup}")
    print("  " + "\n  ".join(errs) if errs else "  NENHUM PROBLEMA")
    print("\nRESULTADO: " + ("LISTA PASS NO TESTE FINAL" if not errs else "REVISAR PENDENCIAS"))

if __name__ == '__main__':
    main()