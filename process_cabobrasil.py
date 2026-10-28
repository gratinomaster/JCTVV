#!/usr/bin/env python3
import os
import re
import gzip
import json
import time
from urllib.parse import urlparse
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

m3u_path = '/home/runner/work/JCTVV/JCTVV/CABOBRASIL.m3u'
epg_path = '/tmp/br1.xml.gz'

session = requests.Session()
retry = Retry(total=2, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
adapter = HTTPAdapter(max_retries=retry)
session.mount('http://', adapter)
session.mount('https://', adapter)

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': '*/*',
}
def parse_m3u(content):
    lines = content.splitlines()
    entries = []
    i = 0
    header_lines = []
    if lines and lines[0].startswith('#EXTM3U'):
        header_lines.append(lines[0])
        i = 1
    while i < len(lines):
        line = lines[i].rstrip()
        if not line.strip():
            i += 1
            continue
        if line.strip().startswith('#EXTINF'):
            extinf = line.strip()
            i += 1
            # find next non-comment line as url
            while i < len(lines):
                uline = lines[i].strip()
                i += 1
                if not uline:
                    continue
                if uline.startswith('#'):
                    continue  # skip comments
                entries.append((extinf, uline))
                break
            else:
                break
        elif line.strip().startswith('#'):
            header_lines.append(line.strip())
            i += 1
        else:
            i += 1
    return header_lines, entries

def get_attr(extinf, name):
    m = re.search(rf'{name}="([^"]*)"', extinf)
    if m:
        return m.group(1)
    return ''

def set_attr(extinf, name, value):
    # remove existing
    extinf2 = re.sub(rf'\s*{name}="[^"]*"', '', extinf)
    # add before last comma+name
    # simpler: insert
    if f'{name}=' in extinf2:
        extinf2 = re.sub(rf'{name}="[^"]*"', f'{name}="{value}"', extinf2)
    else:
        # add before comma before channel name
        if ',' in extinf2:
            # insert before the comma that separates attributes from name? attributes come before comma
            extinf2 = extinf2.replace(',', f' {name}="{value}",', 1) if extinf2.count(',') == 1 else extinf2  # handle
            # better general
            pass
    # easier approach
    return extinf2

def fix_extinf(extinf, **kwargs):
    # rebuild
    # get all attrs
    m_inf = re.match(r'(#EXTINF:-?\d+)', extinf)
    prefix = m_inf.group(1) if m_inf else '#EXTINF:-1'
    # extract existing attrs
    attrs = {}
    for aname in ['tvg-id','tvg-name','tvg-logo','group-title','tvg-chno','tvg-shift']:
        attrs[aname] = get_attr(extinf, aname)
    # override
    for k,v in kwargs.items():
        if v is not None and v != '':
            attrs[k] = v
        elif v == '':
            attrs.pop(k, None)
    # build
    parts = [prefix]
    for k in ['tvg-id','tvg-name','tvg-logo','group-title','tvg-chno']:
        if k in attrs and attrs[k] != '':
            parts.append(f'{k}="{attrs[k]}"')
    # name
    name = extinf.split(',')[-1]
    return ' '.join(parts) + ',' + name
def check_url(url, timeout=8):
    try:
        # try HEAD first
        r = session.head(url, headers=headers, timeout=timeout, allow_redirects=True, verify=False)
        if r.status_code == 405 or r.status_code == 400:
            r = session.get(url, headers=headers, timeout=timeout, allow_redirects=True, verify=False, stream=True)
            r.close()
        if r.status_code < 400:
            ct = r.headers.get('Content-Type','')
            return True, r.status_code, ct
        else:
            return False, r.status_code, ''
    except Exception as e:
        return False, str(e), ''

def load_epg_channels(epg_file):
    channels = {}
    try:
        with gzip.open(epg_file, 'rt', encoding='utf-8', errors='ignore') as f:
            data = f.read()
    except:
        return channels
    # find channels
    for m in re.finditer(r'<channel id="([^"]+)"[^>]*>(.*?)</channel>', data, re.S):
        cid = m.group(1)
        chblock = m.group(2)
        dn = re.search(r'<display-name[^>]*>([^<]+)</display-name>', chblock)
        name = dn.group(1) if dn else cid
        # check if has programmes for today
        channels[cid] = {'name': name, 'block': m.group(0)}
    return channels

def has_prog_today(epg_file, cid):
    try:
        with gzip.open(epg_file, 'rt', encoding='utf-8', errors='ignore') as f:
            data = f.read()
    except:
        return 0
    # count programmes for this channel with start containing today 20261028
    today = '20261028'
    count = len(re.findall(rf'channel="{re.escape(cid)}"[^>]*start="{today}', data))
    return count
BR_MAPPINGS = {
    'Arte 1': ['São.Paulo/SP..Arte.1.br'],
    'Band News': ['São.Paulo/SP..Band.News.br'],
    'Canal do Boi': ['São.Paulo/SP..Canal.do.Boi.br'],
    'Canal Futura': ['São.Paulo/SP..Futura.br'],
    'Canal Gov': [],
    'Canal Rural': ['São.Paulo/SP..Canal.Rural.br'],
    'Canal UOL': [],
    'Canção Nova': [],
    'CNN Brasil': ['São.Paulo/SP..CNN.Brasil.br'],
    'CNT': [],
    'GE TV': [],
    'Globo': ['São.Paulo/SP..Globo.br'],
    'Jovem Pan News': ['Jovem.Pan.News.br'],
    'Record News': ['São.Paulo/SP.Record.News.br'],
    'Rede Brasil': ['Rede.Brasil.HD.br'],
    'Rede Gospel': [],
    'Rede Vida': ['São.Paulo/SP..Rede.Vida.br'],
    'RedeTV!': [],
    'RIT TV': [],
    'SBT': ['São.Paulo/SP..SBT.HD.br'],
    'TV A Crítica': [],
    'TV Brasil': [],
    'TV Câmara': [],
    'TV Cultura': ['São.Paulo/SP..Cultura.br'],
    'TV Rá Tim Bum': [],
    'TV Gazeta': [],
    'TV Justiça': [],
    'TV Novo Tempo': [],
    'TV Senado': [],
    'WooHoo': [],
    'Band Sports': [],
    'ESPN 2': ['ESPN.2.br'],
    'ESPN 3': [],
    'ESPN 4': [],
    'ESPN Brasil': [],
    'SporTV': [],
    'AXN': ['São.Paulo/SP..AXN.br'],
    'Cartoon Network': ['São.Paulo/SP..Cartoon.Network.br'],
    'Discovery Channel': ['São.Paulo/SP..Discovery.Channel.br'],
    'Animal Planet': ['São.Paulo/SP..Animal.Planet.br'],
    'History': ['São.Paulo/SP..History.br'] if False else [],
}

def find_best_epg_for_name(name, epg_channels):
    # try direct mapping
    if name in BR_MAPPINGS:
        for cand in BR_MAPPINGS[name]:
            if cand in epg_channels and has_prog_today(epg_path, cand) > 0:
                return cand
    # try fuzzy
    name_clean = name.lower()
    best = None
    best_score = -1
    for cid, info in epg_channels.items():
        if not cid.endswith('.br'):
            continue
        if has_prog_today(epg_path, cid) == 0:
            continue
        score = 0
        if name_clean in info['name'].lower() or info['name'].lower() in name_clean:
            score += 10
        # token match
        for tok in name_clean.split():
            if tok in cid.lower() or tok in info['name'].lower():
                score += 1
        if score > best_score:
            best_score = score
            best = cid
    return best if best_score >= 2 else None
def main():
    print('Loading...')
    with open(m3u_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    header_lines, entries = parse_m3u(content)
    print(f'Found {len(entries)} entries')
    
    epg_channels = load_epg_channels(epg_path)
    print(f'Loaded {len(epg_channels)} epg channels')
    
    # Check each entry
    new_entries = []
    seen_urls = set()
    removed = []
    
    for extinf, url in entries:
        name = extinf.split(',')[-1].strip()
        tvg_id = get_attr(extinf, 'tvg-id')
        tvg_logo = get_attr(extinf, 'tvg-logo')
        group = get_attr(extinf, 'group-title')
        
        # skip if url already seen? maybe allow different qualities but user says "exclua os canais offline" - focus on removing offline ones
        ok, status, ct = check_url(url)
        if not ok:
            removed.append((name, url, status))
            continue  # remove offline
        
        # fix tvg-id if not working with EPG
        new_extinf = extinf
        # find better epg id
        best_epg = find_best_epg_for_name(name, epg_channels)
        if best_epg:
            # use real epg id
            new_extinf = fix_extinf(new_extinf, **{'tvg-id': best_epg})
            tvg_id_new = best_epg
        else:
            tvg_id_new = get_attr(new_extinf, 'tvg-id')
            # if tvg_id has weird format or no epg, try to find any br channel with today prog that matches loosely
            # but must be real
        
        # fix logo - if missing or looks invalid (svg) remove or replace
        tvg_logo_new = get_attr(new_extinf, 'tvg-logo')
        if not tvg_logo_new or tvg_logo_new.strip() == '' or tvg_logo_new.lower().endswith('.svg'):
            # try to get icon from epg
            best_epg_cur = get_attr(new_extinf, 'tvg-id')
            if best_epg_cur in epg_channels:
                # extract icon
                chblock = epg_channels[best_epg_cur]['block']
                icon_m = re.search(r'<icon src="([^"]+)"', chblock)
                if icon_m and not icon_m.group(1).lower().endswith('.svg'):
                    new_extinf = fix_extinf(new_extinf, **{'tvg-logo': icon_m.group(1)})
                else:
                    # remove logo if no good one
                    new_extinf = fix_extinf(new_extinf, **{'tvg-logo': ''})
            else:
                new_extinf = fix_extinf(new_extinf, **{'tvg-logo': ''})
        
        # remove EXTINF without links - but we have link, so ok
        new_entries.append((new_extinf, url))
    
    print(f'Removed: {len(removed)}')
    for r in removed[:5]:
        print('  ', r[0], r[2])
    
    # Build new m3u
    out_lines = []
    out_lines.append('#EXTM3U url-tvg="https://epgshare01.online/epgshare01/epg_ripper_BR1.xml.gz" x-tvg-url="https://epgshare01.online/epgshare01/epg_ripper_BR1.xml.gz"')
    for extinf, url in new_entries:
        out_lines.append(extinf)
        out_lines.append(url)
    
    # Try to add 1 more relevant channel if possible (open TV) - maybe add RecordTV if missing?
    names_present = [e[0].split(',')[-1].lower() for e in new_entries]
    if not any('record' in n for n in names_present):
        # try to find a working record stream
        record_candidates = [
            'https://cdn.jmvstream.com/w/LVW-10842/LVW10842_513N26MDBL/playlist.m3u8',
            'https://5cf4a2c2512a2.streamlock.net/rbatv/rbatv/playlist.m3u8',
        ]
        for rcand in record_candidates:
            ok, st, ct = check_url(rcand)
            if ok:
                best_epg = find_best_epg_for_name('Record', epg_channels) or 'São.Paulo/SP..Record.br'
                extinf_new = f'#EXTINF:-1 tvg-id="{best_epg}" tvg-name="RecordTV" group-title="TV ABERTA",RecordTV'
                out_lines.append(extinf_new)
                out_lines.append(rcand)
                break
    
    new_content = '\n'.join(out_lines) + '\n'
    with open(m3u_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print('Done writing')

if __name__ == '__main__':
    main()
