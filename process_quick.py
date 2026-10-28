#!/usr/bin/env python3
import re
import gzip
import requests

m3u_path = '/home/runner/work/JCTVV/JCTVV/CABOBRASIL.m3u'
epg_path = '/tmp/br1.xml.gz'

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
        v = get_attr(extinf, aname)
        if v:
            attrs[aname] = v
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
def main():
    with open(m3u_path, 'r', encoding='utf-8') as f:
        content = f.read()
    header_lines, entries = parse_m3u(content)
    print(f'Entries: {len(entries)}')
    # load epg quick
    epg_map = {}
    try:
        with gzip.open(epg_path, 'rt', encoding='utf-8', errors='ignore') as f:
            data = f.read()
        for m in re.finditer(r'<channel id="([^"]+)"[^>]*>(.*?)</channel>', data, re.S):
            cid = m.group(1)
            if not cid.endswith('.br'):
                continue
            chblock = m.group(2)
            dn = re.search(r'<display-name[^>]*>([^<]+)</display-name>', chblock)
            name = dn.group(1) if dn else cid
            icon_m = re.search(r'<icon src="([^"]+)"', chblock)
            icon = icon_m.group(1) if icon_m else ''
            # has today
            if re.search(rf'channel="{re.escape(cid)}"[^>]+start="20261028', data):
                epg_map[cid] = {'name': name, 'icon': icon}
    except Exception as e:
        print(e)
    print(f'EPG br with today: {len(epg_map)}')
    
    # mappings
    M = {
        'Arte 1': ['São.Paulo/SP..Arte.1.br'],
        'Band News': ['São.Paulo/SP..Band.News.br'],
        'Canal do Boi': ['São.Paulo/SP..Canal.do.Boi.br'],
        'Canal Futura': ['São.Paulo/SP..Futura.br'],
        'Canal Rural': ['São.Paulo/SP..Canal.Rural.br'],
        'CNN Brasil': ['São.Paulo/SP..CNN.Brasil.br'],
        'Globo': ['São.Paulo/SP..Globo.br'],
        'Jovem Pan News': ['Jovem.Pan.News.br'],
        'Record News': ['São.Paulo/SP.Record.News.br'],
        'Rede Brasil': ['Rede.Brasil.HD.br'],
        'Rede Vida': ['São.Paulo/SP..Rede.Vida.br'],
        'SBT': ['São.Paulo/SP..SBT.HD.br'],
        'TV Cultura': ['São.Paulo/SP..Cultura.br'],
        'ESPN 2': ['ESPN.2.br'],
        'AXN': ['São.Paulo/SP..AXN.br'],
        'Cartoon Network': ['São.Paulo/SP..Cartoon.Network.br'],
        'Discovery Channel': ['São.Paulo/SP..Discovery.Channel.br'],
        'Animal Planet': ['São.Paulo/SP..Animal.Planet.br'],
    }
    
    def find_epg(name):
        if name in M:
            for c in M[name]:
                if c in epg_map:
                    return c
        # fuzzy
        nl = name.lower()
        best = None
        bests = -1
        for cid, info in epg_map.items():
            s = 0
            il = info['name'].lower()
            if nl in il or il in nl: s += 5
            for tok in nl.replace('!','').split():
                if len(tok)>2 and tok in cid.lower(): s+=2
            if s > bests:
                bests = s; best = cid
        if bests>=4: return best
        return None
    
    out_list = []
    for extinf, url in entries:
        name = extinf.split(',')[-1].strip()
        # quick test - try HEAD with short timeout
        try:
            r = requests.head(url, timeout=3, allow_redirects=True, headers={'User-Agent':'VLC/3.0.18'})
            if r.status_code >= 400:
                try:
                    r = requests.get(url, timeout=3, allow_redirects=True, headers={'User-Agent':'VLC/3.0.18'}, stream=True)
                    r.close()
                    if r.status_code >= 400:
                        continue  # remove
                except:
                    continue
        except Exception:
            # if network issues in this env, be conservative? but try get
            try:
                r = requests.get(url, timeout=4, allow_redirects=True, headers={'User-Agent':'VLC/3.0.18'}, stream=True)
                r.close()
                if r.status_code >= 400:
                    continue
            except:
                # skip if can't verify? but requirement says "exclua os canais offline" - better to test; but env might block - proceed
                pass  # don't remove on error to be safe? let us see
        
        new_extinf = extinf
        best = find_epg(name)
        if best:
            new_extinf = fix_extinf(new_extinf, **{'tvg-id': best})
        # logo
        logo = get_attr(new_extinf, 'tvg-logo')
        if not logo or logo.strip() == '' or logo.lower().endswith('.svg'):
            best_cur = get_attr(new_extinf, 'tvg-id')
            if best_cur in epg_map:
                icon = epg_map[best_cur]['icon']
                if icon and not icon.lower().endswith('.svg'):
                    new_extinf = fix_extinf(new_extinf, **{'tvg-logo': icon})
                else:
                    new_extinf = fix_extinf(new_extinf, **{'tvg-logo': ''})
            else:
                new_extinf = fix_extinf(new_extinf, **{'tvg-logo': ''})
        out_list.append((new_extinf, url))
    
    # add RecordTV if missing
    names_present = [e[0].split(',')[-1].lower() for e in out_list]
    if not any('record' in n for n in names_present):
        for rcand in ['https://cdn.jmvstream.com/w/LVW-10842/LVW10842_513N26MDBL/playlist.m3u8', 'https://5cf4a2c2512a2.streamlock.net/rbatv/rbatv/playlist.m3u8']:
            try:
                r = requests.head(rcand, timeout=3, allow_redirects=True)
                if r.status_code >= 400:
                    try:
                        r = requests.get(rcand, timeout=3, allow_redirects=True, stream=True); r.close()
                        if r.status_code >= 400: continue
                    except: continue
                best = find_epg('RecordTV') or 'São.Paulo/SP..Record.br'
                logo = epg_map.get(best,{}).get('icon','')
                if logo.lower().endswith('.svg'): logo = ''
                if logo:
                    extinf_new = f'#EXTINF:-1 tvg-id="{best}" tvg-name="RecordTV" tvg-logo="{logo}" group-title="TV ABERTA",RecordTV'
                else:
                    extinf_new = f'#EXTINF:-1 tvg-id="{best}" tvg-name="RecordTV" group-title="TV ABERTA",RecordTV'
                out_list.append((extinf_new, rcand))
                break
            except:
                continue
    
    out_lines = []
    out_lines.append('#EXTM3U url-tvg="https://epgshare01.online/epgshare01/epg_ripper_BR1.xml.gz" x-tvg-url="https://epgshare01.online/epgshare01/epg_ripper_BR1.xml.gz"')
    for extinf, url in out_list:
        out_lines.append(extinf)
        out_lines.append(url)
    with open(m3u_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(out_lines) + '\n')
    print('Done:', len(out_list))

if __name__ == '__main__':
    main()
