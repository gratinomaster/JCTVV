#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import re
import shutil
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import requests

BASE = '/home/runner/work/JCTVV/JCTVV'
M3U_FILE = os.path.join(BASE, 'lista5.m3u')
REPORT = os.path.join(BASE, f'relatorio_lista5_final_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt')

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'

def log(msg):
    print(msg)
    with open(REPORT, 'a', encoding='utf-8') as f:
        f.write(msg + '\n')

def fix_logo(url):
    if not url:
        return None
    if 'imgur.com' in url.lower():
        return None
    url_clean = url.split('?')[0].split('#')[0]
    if url_clean.lower().endswith('.jpeg'):
        return url_clean[:-5] + '.jpg'
    if url_clean.lower().endswith('.jpg'):
        return url_clean
    for ext in ['.png', '.svg', '.webp', '.gif', '.bmp']:
        if url_clean.lower().endswith(ext):
            base = url_clean[:len(url_clean)-len(ext)]
            return base + '.jpg'
    m = re.search(r'\.([a-zA-Z0-9]+)$', url_clean)
    if m:
        base = url_clean[:m.start()]
        return base + '.jpg'
    return url_clean.rstrip('/') + '.jpg'

def check_stream(url, timeout=10):
    try:
        headers = {'User-Agent': USER_AGENT}
        r = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True, stream=True)
        if r.status_code >= 400:
            r.close()
            return False
        chunk = next(r.iter_content(chunk_size=4096), b'')
        r.close()
        if chunk.startswith(b'#EXTM3U'):
            return True
        if b'#EXT-X' in chunk:
            return True
        if len(chunk) > 50:
            return True
        return False
    except:
        return False

def load_epg():
    epg_files = ['lista5_epg.xml', 'lista5_epg_combinado.xml', 'lista5_epg_atualizado.xml']
    all_progs = []
    all_ch = {}
    for ef in epg_files:
        p = os.path.join(BASE, ef)
        if not os.path.exists(p): continue
        try:
            tree = ET.parse(p)
            root = tree.getroot()
            for ch in root.findall('channel'):
                cid = ch.attrib.get('id')
                if cid:
                    dn = ch.find('display-name')
                    all_ch[cid] = dn.text if dn is not None else cid
            for pr in root.findall('programme'):
                all_progs.append(pr.attrib)
        except:
            pass
    return all_ch, all_progs

def has_prog(all_progs, cid, day):
    for pr in all_progs:
        if pr.get('channel') == cid and pr.get('start','')[:8] == day:
            return True
    return False

def main():
    log(f"=== FIX LISTA5 === {datetime.now()}")
    bak = os.path.join(BASE, f'lista5.m3u.bak.pre_fix2_{datetime.now().strftime("%Y%m%d_%H%M%S")}')
    shutil.copy2(M3U_FILE, bak)
    log(f"Backup: {bak}")
    
    all_ch, all_progs = load_epg()
    log(f"EPG: {len(all_ch)} channels, {len(all_progs)} programmes")
    hoje = datetime.now().strftime('%Y%m%d')
    amanha = (datetime.now()+timedelta(days=1)).strftime('%Y%m%d')
    depois = (datetime.now()+timedelta(days=2)).strftime('%Y%m%d')
    
    # Define canonical channels
    CANON = [
        {
            'tvg_id': 'ABCNewsLive.us',
            'name': 'ABC News Live - ABC News',
            'logo': 'https://keyframe-cdn.abcnews.com/streamprovider11.jpg',
            'group': 'NEWS WORLD',
            'urls': [
                'https://linear-abcnews-akc-na-west-1.media.dssott.com/dvt2=exp=1792978309~url=%2Flas1%2Fva01%2Fdisneyplus%2Fchannel%2F79449312-79dd-473d-873c-515ebf4b5e5f-1781164031838%2F~psid=64e7dbfb-d9a5-48c7-9212-250a369955c1~did=d46f21a5-3d31-486d-b9f3-3e830d6204e1~country=US~kid=k02~hmac=5ddec94cb854fae3d4faa99b9238df7177e3291cbb054c5dacb184998d995d95/las1/va01/disneyplus/channel/79449312-79dd-473d-873c-515ebf4b5e5f-1781164031838/ctr-all-hdri-sliding.m3u8?r=1080&v=1&hash=81fb88da5aab33fe54dc3f8d7ae5f0b2eaa56a8c',
                'https://linear-abcnews-akc-na-west-1.media.dssott.com/dvt2=exp=1792978309~url=%2Flas1%2Fva01%2Fdisneyplus%2Fchannel%2F79449312-79dd-473d-873c-515ebf4b5e5f-1781164031838%2F~psid=64e7dbfb-d9a5-48c7-9212-250a369955c1~did=d46f21a5-3d31-486d-b9f3-3e830d6204e1~country=US~kid=k02~hmac=5ddec94cb854fae3d4faa99b9238df7177e3291cbb054c5dacb184998d995d95/las1/va01/disneyplus/channel/79449312-79dd-473d-873c-515ebf4b5e5f-1781164031838/cmaf-cenc-ctr-1700K/1700_hdri_slide.m3u8',
                'https://linear-abcnews-akc-na-west-1.media.dssott.com/dvt2=exp=1792978309~url=%2Flas1%2Fva01%2Fdisneyplus%2Fchannel%2F79449312-79dd-473d-873c-515ebf4b5eopsdd=64e7dbfb-d9a5-48c7-9212-250a369955c1~did=d46f21a5-3d31-486d-b9f3-3e830d6204e1~country=US~kid=k02~hmac=5ddec94cb854fae3d4faa99b9238df7177e3291cbb054c5dacb184998d995d95/las1/va01/disneyplus/channel/79449312-79dd-473d-873c-515ebf4b5e5f-1781164031838/audio-aac-1-64K/64_slide.m3u8',
                'https://abcnews-livestreams.akamaized.net/out/v1/6a597119dbd5428a82dc11a2f514a1a2/abcn-live-10-cmaf-manifest/abcn-live-10-index.m3u8',
                'https://abcnews-livestreams.akamaized.net/out/v1/6a597119dbd5428a82dc11a2f514a1a2/abcn-live-10-cmaf-manifest/abcn-live-10-index_3.m3u8',
                'https://abcnews-livestreams.akamaized.net/out/v1/6a597119dbd5428a82dc11a2f514a1a2/abcn-live-10-cmaf-manifest/abcn-live-10-index_4_0.m3u8',
            ]
        },
        {
            'tvg_id': 'FoxNewsChannel.us',
            'name': 'Fox News Channel',
            'logo': 'https://raw.githubusercontent.com/gratinomaster/JCTV/main/fox_news.jpg',
            'group': 'NEWS WORLD',
            'urls': [
                'https://247.foxnews.com/hls/live/2003586/FNCHLSv3/master.m3u8?hdnea=exp=1792895510~acl=/*~hmac=598dc5010f4c8f77056d601c211275ba5cf0094fa6da2af989a8a5347a3a035f',
            ]
        },
        {
            'tvg_id': 'FoxBusiness.us',
            'name': 'Fox Business',
            'logo': 'https://raw.githubusercontent.com/gratinomaster/JCTV/main/fox_business.jpg',
            'group': 'NEWS WORLD',
            'urls': [
                'https://247.foxbusiness.com/hls/live/2003756/FBNHLSv3/master.m3u8?hdnea=exp=1792895509~acl=/*~hmac=c70fd93705fac4af9f0ce57fda16b17ea6a4a58642862ebaa37f48f48c341a8b',
            ]
        },
        {
            'tvg_id': 'CBSNews.us',
            'name': 'CBS News 24/7',
            'logo': 'https://raw.githubusercontent.com/gratinomaster/JCTV/main/cbsnews.jpg',
            'group': 'NEWS WORLD',
            'urls': [
                'https://dai.google.com/linear/hls/pa/event/Sid4xiTQTkCT1SLu6rjUSQ/stream/3a0c1d9a-c838-4be8-b928-136c4c6105ae:CHS/master.m3u8',
                'https://dai.google.com/linear/hls/pa/event/Sid4xiTQTkCT1SLu6rjUSQ/stream/3a0c1d9a-c838-4be8-b928-136c4c6105ae:CHS/variant/2ed2c78fd57ae51fb6ba5d4bbd59e953/bandwidth/441000.m3u8',
                'https://dai.google.com/linear/hls/pa/event/Sid4xiTQTkCT1SLu6rjUSQ/stream/3a0c1d9a-c838-4be8-b928-136c4c6105ae:CHS/variant/c1de5c45f7968bb580d02bc76f3a9e7e/bandwidth/1083000.m3u8',
                'https://dai.google.com/linear/hls/pa/event/Sid4xiTQTkCT1SLu6rjUSQ/stream/3a0c1d9a-c838-4be8-b928-136c4c6105ae:CHS/variant/b93ad8358bd5b2b671e137cb4cd530a7/bandwidth/2249000.m3u8',
            ]
        },
    ]
    
    # Build EPG URLs
    epg_urls = []
    for ef in ['lista5_epg.xml', 'lista5_epg_combinado.xml', 'lista5_epg_atualizado.xml']:
        if os.path.exists(os.path.join(BASE, ef)):
            epg_urls.append(f'https://raw.githubusercontent.com/JCTV/JCTV/main/{ef}')
    epg_url_str = ' '.join(epg_urls)
    
    m3u_lines = [f'#EXTM3U x-tvg-url="{epg_url_str}"']
    
    for ch in CANON:
        tvg_id = ch['tvg_id']
        # Check EPG coverage
        if tvg_id in all_ch:
            h = has_prog(all_progs, tvg_id, hoje)
            a = has_prog(all_progs, tvg_id, amanha)
            d = has_prog(all_progs, tvg_id, depois)
            log(f"{ch['name']} EPG: hoje={h} amanha={a} depois={d}")
        else:
            log(f"{ch['name']} EPG: NO ID FOUND")
        
        logo = fix_logo(ch['logo'])
        for url in ch['urls']:
            log(f"Testando stream {ch['name']}...")
            ok = check_stream(url)
            log(f"  OK={ok}")
            if not ok:
                continue
            extinf = f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-name="{ch["name"]}" tvg-logo="{logo}" group-title="{ch["group"]}",{ch["name"]}'
            m3u_lines.append(extinf)
            m3u_lines.append(url)
    
    with open(M3U_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(m3u_lines) + '\n')
    
    log(f"Salvo {M3U_FILE} com {len([l for l in m3u_lines if l.startswith('http')])} streams")

if __name__ == '__main__':
    main()
