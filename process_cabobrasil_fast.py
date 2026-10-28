#!/usr/bin/env python3
import os
import re
import gzip
import time
from urllib.parse import urlparse
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

m3u_path = '/home/runner/work/JCTVV/JCTVV/CABOBRASIL.m3u'
epg_path = '/tmp/br1.xml.gz'

session = requests.Session()
retry = Retry(total=1, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504])
adapter = HTTPAdapter(max_retries=retry)
session.mount('http://', adapter)
session.mount('https://', adapter)

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
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
            while i < len(lines):
                uline = lines[i].strip()
                i += 1
                if not uline:
                    continue
                if uline.startswith('#'):
                    continue
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

def fix_extinf(extinf, **kwargs):
    m_inf = re.match(r'(#EXTINF:-?\d+)', extinf)
    prefix = m_inf.group(1) if m_inf else '#EXTINF:-1'
    attrs = {}
    for aname in ['tvg-id','tvg-name','tvg-logo','group-title','tvg-chno']:
        attrs[aname] = get_attr(extinf, aname)
    for k,v in kwargs.items():
        if v == '':
            attrs.pop(k, None)
        elif v is not None:
            attrs[k] = v
    parts = [prefix]
    for k in ['tvg-id','tvg-name','tvg-logo','group-title','tvg-chno']:
        if k in attrs and attrs[k] != '':
            parts.append(f'{k}="{attrs[k]}"')
    name = extinf.split(',')[-1]
    return ' '.join(parts) + ',' + name
def check_url(url, timeout=5):
    try:
        r = session.head(url, headers=headers, timeout=timeout, allow_redirects=True, verify=False)
        if r.status_code in (405, 400, 403) or r.status_code >= 400:
            try:
                r = session.get(url, headers=headers, timeout=timeout, allow_redirects=True, verify=False, stream=True)
                code = r.status_code
                r.close()
                if code < 400:
                    return True, code
                return False, code
            except:
                return False, r.status_code
        if r.status_code < 400:
            return True, r.status_code
        return False, r.status_code
    except Exception as e:
        return False, str(e)[:20]

def load_epg_channels(epg_file):
    channels = {}
    try:
        with gzip.open(epg_file, 'rt', encoding='utf-8', errors='ignore') as f:
            data = f.read()
    except Exception as e:
        print(e)
        return channels
    for m in re.finditer(r'<channel id="([^"]+)"[^>]*>(.*?)</channel>', data, re.S):
        cid = m.group(1)
        chblock = m.group(2)
        dn = re.search(r'<display-name[^>]*>([^<]+)</display-name>', chblock)
        name = dn.group(1) if dn else cid
        icon_m = re.search(r'<icon src="([^"]+)"', chblock)
        icon = icon_m.group(1) if icon_m else ''
        channels[cid] = {'name': name, 'icon': icon}
    return channels

def has_prog_today(epg_file, cid):
    try:
        with gzip.open(epg_file, 'rt', encoding='utf-8', errors='ignore') as f:
            data = f.read()
    except:
        return 0
    today = '20261028'
    # quick check
    count = data.count(f'channel="{cid}"')  # rough
    # better precise
    count = len(re.findall(rf'channel="{re.escape(cid)}"[^>]+start="{today}', data))
    return count
MAPPINGS = {
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
    'History': ['São.Paulo/SP..History.br'],
}
def find_best_epg(name, epg_channels):
    name_clean = name.lower()
    if name in MAPPINGS:
        for cand in MAPPINGS[name]:
            if cand in epg_channels:
                if has_prog_today(epg_path, cand) > 0:
                    return cand
    # fuzzy
    best = None
    best_score = -1
    for cid, info in epg_channels.items():
        if not cid.endswith('.br'):
            continue
        if has_prog_today(epg_path, cid) == 0:
            continue
        score = 0
        iname = info['name'].lower()
        if name_clean in iname or iname in name_clean:
            score += 5
        for tok in re.split(r'[\s\-\!]+', name_clean):
            if len(tok) > 2 and tok in cid.lower():
                score += 2
            if len(tok) > 2 and tok in iname:
                score += 1
        if score > best_score:
            best_score = score
            best = cid
    if best_score >= 3:
        return best
    return None
def main():
    print('Loading m3u...')
    with open(m3u_path, 'r', encoding='utf-8') as f:
        content = f.read()
    header_lines, entries = parse_m3u(content)
    print(f'Entries: {len(entries)}')
    print('Loading epg...')
    epg_channels = load_epg_channels(epg_path)
    print(f'Epg channels: {len(epg_channels)}')
    
    out_list = []
    removed = []
    for extinf, url in entries:
        name = extinf.split(',')[-1].strip()
        # test url
        ok, status = check_url(url)
        if not ok:
            removed.append(name)
            continue
        new_extinf = extinf
        # find best epg
        best = find_best_epg(name, epg_channels)
        if best:
            new_extinf = fix_extinf(new_extinf, **{'tvg-id': best})
        # logo
        logo = get_attr(new_extinf, 'tvg-logo')
        if not logo or logo.strip() == '' or logo.lower().endswith('.svg'):
            best_cur = get_attr(new_extinf, 'tvg-id')
            if best_cur in epg_channels:
                icon = epg_channels[best_cur]['icon']
                if icon and not icon.lower().endswith('.svg'):
                    new_extinf = fix_extinf(new_extinf, **{'tvg-logo': icon})
                else:
                    new_extinf = fix_extinf(new_extinf, **{'tvg-logo': ''})
            else:
                new_extinf = fix_extinf(new_extinf, **{'tvg-logo': ''})
        out_list.append((new_extinf, url))
    
    print(f'Removed {len(removed)}: {removed}')
    
    # add 1 more relevant if possible
    names_present = [e[0].split(',')[-1].lower() for e in out_list]
    if not any('record' in n for n in names_present):
        # try Record
        for rcand in ['https://playplusspo-lh.akamaihd.net/i/pp_sp@350176/index_720_av-p.m3u8', 'https://cdn.jmvstream.com/w/LVW-10842/LVW10842_513N26MDBL/playlist.m3u8']:
            ok, st = check_url(rcand)
            if ok:
                best = find_best_epg('RecordTV', epg_channels) or 'São.Paulo/SP..Record.br'
                best_cur = best if best in epg_channels else 'São.Paulo/SP..Record.br'
                logo = epg_channels.get(best_cur, {}).get('icon','')
                if logo.lower().endswith('.svg'):
                    logo = ''
                extinf_new = f'#EXTINF:-1 tvg-id="{best_cur}" tvg-name="RecordTV" group-title="TV ABERTA"'
                if logo:
                    extinf_new = f'#EXTINF:-1 tvg-id="{best_cur}" tvg-name="RecordTV" tvg-logo="{logo}" group-title="TV ABERTA"'
                else:
                    extinf_new = f'#EXTINF:-1 tvg-id="{best_cur}" tvg-name="RecordTV" group-title="TV ABERTA"'
                extinf_new += ',RecordTV'
                out_list.append((extinf_new, rcand))
                break
    
    out_lines = []
    out_lines.append('#EXTM3U url-tvg="https://epgshare01.online/epgshare01/epg_ripper_BR1.xml.gz" x-tvg-url="https://epgshare01.online/epgshare01/epg_ripper_BR1.xml.gz"')
    for extinf, url in out_list:
        out_lines.append(extinf)
        out_lines.append(url)
    
    new_content = '\n'.join(out_lines) + '\n'
    with open(m3u_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print('Done. Total:', len(out_list))
    
if __name__ == '__main__':
    main()
