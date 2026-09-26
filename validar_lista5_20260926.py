#!/usr/bin/env python3
"""Validacao independente do lista5.m3u gerado."""
import gzip, re, sys, requests
from datetime import date, datetime, timedelta
from urllib.parse import urljoin, urlsplit, urlunsplit

H={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36','Accept':'*/*'}
PL='lista5.m3u'
lines=[l.rstrip('\n').rstrip('\r') for l in open(PL,encoding='utf-8') if l.strip()]
fail=[]

def a(line,k):
    m=re.search(r'%s="([^"]*)"'%k,line); return m.group(1) if m else ''

# 1. estrutura: toda URL com #EXTINF na linha de cima
hdr=lines[0]
if not hdr.startswith('#EXTM3U'): fail.append('header nao começa com #EXTM3U')
epg_urls=[u for u in (a(hdr,'x-tvg-url')+','+a(hdr,'url-tvg')).split(',') if u]
if not epg_urls: fail.append('sem x-tvg-url/url-tvg no header')
pairs=[]; pending=None
for l in lines[1:]:
    if l.startswith('#EXTINF'): pending=l
    elif l.startswith('#'): fail.append('linha inesperada: '+l[:40])
    else:
        if pending is None: fail.append('URL sem #EXTINF: '+l[:60])
        else: pairs.append((pending,l))
        pending=None
if pending: fail.append('#EXTINF sem URL no final do arquivo')
print('Estrutura: %d entradas, %d EPG(s) no header' % (len(pairs),len(epg_urls)))

# 2. logos .jpg, sem imgur, respondendo
for extinf,url in pairs:
    lg=a(extinf,'tvg-logo')
    if not lg: fail.append('sem tvg-logo: '+a(extinf,'tvg-name')); continue
    if 'imgur' in lg.lower(): fail.append('logo imgur: '+lg)
    if not lg.lower().split('?')[0].endswith('.jpg'): fail.append('logo nao .jpg: '+lg)
    try:
        r=requests.get(lg,headers=H,timeout=20,stream=True); b=next(r.iter_content(8),b''); r.close()
        if r.status_code!=200 or b[:3]!=b'\xff\xd8\xff':
            fail.append('logo invalido (%s %s): %s'%(r.status_code,b[:3],lg))
    except Exception as e: fail.append('logo erro %s: %s'%(type(e).__name__,lg))

# 3. EPG: 200 + gzip + tvg-id com guia hoje/amanha/depois
guide={}
for src in epg_urls:
    try:
        r=requests.get(src,headers=H,timeout=240)
        if r.status_code!=200: fail.append('EPG HTTP %d: %s'%(r.status_code,src)); continue
        raw=gzip.decompress(r.content)
        today=date.today()
        want={today+timedelta(days=d) for d in (0,1,2)}
        names={}; prog={}
        for b in re.findall(rb'<channel\b.*?</channel>',raw,re.S):
            m=re.search(rb'<channel id="([^"]+)"',b)
            if m:
                d=re.search(rb'<display-name[^>]*>(.*?)</display-name>',b,re.S)
                names[m.group(1).decode()]=d.group(1).decode().strip() if d else ''
        for b in re.findall(rb'<programme\b[^>]*>',raw):
            m=re.search(rb'channel="([^"]+)"',b); s=re.search(rb'start="(\d{8})',b)
            if m and s:
                d=datetime.strptime(s.group(1).decode(),'%Y%m%d').date()
                if d in want: prog.setdefault(m.group(1).decode(),set()).add(d)
        guide[src]=(names,prog)
        print('EPG %s: %d canais' % (src,len(names)))
    except Exception as e:
        fail.append('EPG erro %s: %s'%(type(e).__name__,src))

for extinf,url in pairs:
    tid=a(extinf,'tvg-id'); nm=a(extinf,'tvg-name')
    if not tid: fail.append('sem tvg-id: '+nm); continue
    best=None
    for src,(names,prog) in guide.items():
        if tid in names:
            best=(src,names[tid],sorted(prog.get(tid,())))
            break
    if not best: fail.append('tvg-id %s (%s) nao existe em nenhum EPG'%(tid,nm)); continue
    src,disp,dias=best
    if len(dias)<3: fail.append('guia incompleta de %s: %d/3 dias'%(nm,len(dias)))
    print('  %-15s tvg-id=%-7s %-28s dias=%d/3' % (nm,tid,disp,len(dias)))

# 4. streams: master -> variante -> segmento
def inherit(u,b):
    if '?' in u: return u
    q=urlsplit(b).query
    if not q: return u
    s,n,p,_,f=urlsplit(u); return urlunsplit((s,n,p,q,f))
for extinf,url in pairs:
    nm=a(extinf,'tvg-name')
    try:
        t=requests.get(url,headers=H,timeout=25).text
        if '#EXTM3U' not in t: fail.append('stream nao e m3u8: '+nm); continue
        var=re.findall(r'(?m)^(?!\s*#)(\S+\.m3u8\S*)\s*$',t)
        if not var: fail.append('sem variante: '+nm); continue
        v=inherit(urljoin(url,var[0]),url)
        vt=requests.get(v,headers=H,timeout=25).text
        seg=re.findall(r'(?m)^(?!\s*#)(\S+\.(?:ts|m4s|mp4|mp4a|aac))\S*\s*$',vt)
        if not seg: fail.append('variante sem segmento: '+nm); continue
        s=inherit(urljoin(v,seg[-1]),url)
        init=re.search(r'#EXT-X-MAP:URI="([^"]+)"',vt)
        if init:
            ir=requests.get(inherit(urljoin(v,init.group(1)),v),headers=H,timeout=20)
            if ir.status_code!=200 or b'ftyp' not in ir.content[:64]:
                fail.append('init segment invalido: '+nm)
        r=requests.get(s,headers=H,timeout=30,stream=True); b=next(r.iter_content(65536),b''); r.close()
        magic = b[0]==0x47 or any(k in b[:64] for k in (b'ftyp',b'styp',b'moof',b'mdat',b'sidx'))
        ok=r.status_code==200 and len(b)>1024 and magic
        if not ok: fail.append('segmento invalido (%s, %dB): %s'%(r.status_code,len(b),nm))
        else: print('  STREAM %-15s %d variantes, segmento %s %d bytes OK'%(nm,len(var),r.headers.get('content-type'),len(b)))
    except Exception as e:
        fail.append('stream erro %s em %s'%(type(e).__name__,nm))

print('='*60)
if fail:
    print('FALHAS (%d):'%len(fail))
    for f in fail: print(' -',f)
    sys.exit(1)
print('TUDO OK: %d canais com EPG (hoje/amanha/depois), logo .jpg e stream testado'%len(pairs))
