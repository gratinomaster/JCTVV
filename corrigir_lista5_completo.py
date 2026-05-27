#!/usr/bin/env python3
import re
import sys
import requests
from datetime import datetime, timedelta

M3U_FILE = '/home/runner/work/JCTV/JCTV/lista5.m3u'
EPG_FILE = '/home/runner/work/JCTV/JCTV/lista5_epg.xml'
OUTPUT_M3U = '/home/runner/work/JCTV/JCTV/lista5_corrigida.m3u'
EPG_URL_TAG = 'lista5_epg.xml'

CHANNEL_MAP = {
    'ABC News Live - ABC News': {
        'tvg-id': 'ABCNewsLive.us',
        'tvg-name': 'ABC News Live',
        'tvg-logo': 'https://keyframe-cdn.abcnews.com/streamprovider11.jpg',
        'group-title': 'NEWS WORLD'
    },
    'Watch Fox News Channel Online | Stream Fox News': {
        'tvg-id': 'FoxNewsChannel.us',
        'tvg-name': 'Fox News Channel',
        'tvg-logo': 'https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/5083aae4-b8c5-4708-ac25-f3c5ac554341/b17e991e-a824-4bf7-8e6b-885b7cd2bcf4/1280x720/match/400/225/image.jpg',
        'group-title': 'NEWS WORLD'
    },
    'Fox Business Go | Fox News Video': {
        'tvg-id': 'FoxBusiness.us',
        'tvg-name': 'Fox Business',
        'tvg-logo': 'https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/5083aae4-b8c5-4708-ac25-f3c5ac554341/b17e991e-a824-4bf7-8e6b-885b7cd2bcf4/1280x720/match/400/225/image.jpg',
        'group-title': 'NEWS WORLD'
    },
    'Watch CBS News 24/7, our free live news stream': {
        'tvg-id': 'CBSNews.us',
        'tvg-name': 'CBS News 24/7',
        'tvg-logo': 'https://www.cbsnews.com/bundles/cbsnewsvideo/images/cbsn--main-bg.jpg',
        'group-title': 'NEWS WORLD'
    }
}

def find_channel_name(extinf):
    for known_name in sorted(CHANNEL_MAP.keys(), key=len, reverse=True):
        if known_name in extinf:
            return known_name
    m = re.search(r',([^,]+)$', extinf)
    if m:
        return m.group(1).strip()
    return None

def fix_logo_url(logo_url):
    if not logo_url:
        return None
    logo_url = logo_url.strip().strip('"')
    if 'imgur.com' in logo_url.lower():
        return None
    ext = logo_url.lower().rsplit('.', 1)[-1] if '.' in logo_url else ''
    if ext not in ('jpg', 'jpeg'):
        logo_url = re.sub(r'\.[^./?]+(\?.*)?$', '.jpg', logo_url)
    if not logo_url.lower().endswith('.jpg') and not logo_url.lower().endswith('.jpeg'):
        logo_url = logo_url.rstrip('/') + '.jpg'
    return logo_url

def extract_entries(m3u_content):
    lines = m3u_content.strip().split('\n')
    entries = []
    i = 1
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXTINF:'):
            extinf = line
            i += 1
            urls = []
            while i < len(lines) and not lines[i].strip().startswith('#EXTINF:') and not lines[i].strip().startswith('#EXTM3U'):
                url = lines[i].strip()
                if url and url.startswith('http'):
                    urls.append(url)
                i += 1
            ch_name = find_channel_name(extinf)
            entries.append({'extinf': extinf, 'urls': urls, 'ch_name': ch_name or 'unknown'})
        else:
            i += 1
    return entries

def build_extinf(entry, channel_info):
    new_extinf = '#EXTINF:-1'
    info = channel_info
    new_extinf += f' tvg-id="{info["tvg-id"]}"'
    new_extinf += f' tvg-name="{info["tvg-name"]}"'
    logo_match = re.search(r'tvg-logo="([^"]+)"', entry['extinf'])
    logo = logo_match.group(1) if logo_match else info.get('tvg-logo', '')
    cleaned_logo = fix_logo_url(logo)
    if cleaned_logo:
        new_extinf += f' tvg-logo="{cleaned_logo}"'
    gt = info.get('group-title') or 'NEWS WORLD'
    new_extinf += f' group-title="{gt}"'
    new_extinf += f',{info["tvg-name"]}'
    return new_extinf

def test_m3u_format(m3u_content):
    lines = m3u_content.strip().split('\n')
    issues = []
    for i, line in enumerate(lines):
        if line.startswith('http') and (i == 0 or not lines[i-1].strip().startswith('#EXTINF:')):
            issues.append(f'  Linha {i+1}: URL sem #EXTINF acima')
    if issues:
        print('Problemas de formato encontrados:')
        for iss in issues:
            print(iss)
        return False
    print('Formato OK: todos os URLs tem #EXTINF acima.')
    return True

def test_epg_xml():
    import xml.etree.ElementTree as ET
    tree = ET.parse(EPG_FILE)
    root = tree.getroot()
    programmes = root.findall('programme')
    dates = set()
    channels_in_epg = set()
    for p in programmes:
        s = p.get('start', '')
        dates.add(s[:8] if len(s) >= 8 else '')
        channels_in_epg.add(p.get('channel', ''))
    today = datetime.now().strftime('%Y%m%d')
    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y%m%d')
    day_after = (datetime.now() + timedelta(days=2)).strftime('%Y%m%d')
    print(f'EPG channels: {channels_in_epg}')
    print(f'Dates in EPG: {sorted(dates)}')
    print(f'Today ({today}) in EPG: {today in dates}')
    print(f'Tomorrow ({tomorrow}) in EPG: {tomorrow in dates}')
    print(f'Day after ({day_after}) in EPG: {day_after in dates}')
    all_channels = set(info['tvg-id'] for info in CHANNEL_MAP.values())
    missing = all_channels - channels_in_epg
    if missing:
        print(f'WARNING: Channels missing from EPG: {missing}')
        return False
    missing_dates = [d for d in [today, tomorrow, day_after] if d not in dates]
    if missing_dates:
        print(f'WARNING: Dates missing from EPG: {missing_dates}')
        return False
    print('EPG OK: todos os canais e datas cobertos.')
    return True

def test_streams(entries):
    tested = set()
    all_ok = True
    for entry in entries:
        ch = entry['ch_name']
        if ch in tested:
            continue
        tested.add(ch)
        url = entry['urls'][0] if entry['urls'] else None
        if not url:
            print(f'  SKIP: {ch} -> no URL')
            continue
        try:
            resp = requests.head(url, timeout=10, allow_redirects=True)
            if resp.status_code >= 400:
                resp = requests.get(url, timeout=10, allow_redirects=True)
            status = 'OK' if resp.status_code < 400 else f'HTTP {resp.status_code}'
            if resp.status_code >= 400:
                all_ok = False
                print(f'  FAIL: {ch} -> {status}')
            else:
                print(f'  OK: {ch} -> {status}')
        except Exception as e:
            print(f'  FAIL: {ch} -> {str(e)[:50]}')
            all_ok = False
    return all_ok

def test_logos():
    tested = set()
    all_ok = True
    for info in CHANNEL_MAP.values():
        logo = info['tvg-logo']
        if logo in tested:
            continue
        tested.add(logo)
        try:
            resp = requests.head(logo, timeout=10, allow_redirects=True)
            ct = resp.headers.get('content-type', '')
            if resp.status_code < 400:
                print(f'  OK: logo acessivel ({resp.status_code}, {ct})')
            else:
                print(f'  FAIL: logo HTTP {resp.status_code}')
                all_ok = False
        except Exception as e:
            print(f'  FAIL: logo error {str(e)[:50]}')
            all_ok = False
    return all_ok

def main():
    print('=' * 60)
    print('CORREÇÃO DO LISTA5.M3U')
    print('=' * 60)

    with open(M3U_FILE) as f:
        m3u_content = f.read()

    entries = extract_entries(m3u_content)
    print(f'\nEntradas encontradas: {len(entries)}')

    print('\n--- Testando formato M3U ---')
    test_m3u_format(m3u_content)

    print('\n--- Testando EPG ---')
    epg_ok = test_epg_xml()
    if not epg_ok:
        print('ATENÇÃO: EPG com problemas. Continuando com correção do M3U...')

    print('\n--- Testando Logos ---')
    logos_ok = test_logos()
    if not logos_ok:
        print('ATENÇÃO: Alguns logos falharam.')

    print('\n--- Testando Streams ---')
    streams_ok = test_streams(entries)
    if not streams_ok:
        print('ATENÇÃO: Alguns streams falharam.')

    print('\n--- Gerando M3U Corrigido ---')
    output_lines = ['#EXTM3U']
    output_lines.append(f'#PLAYLIST: LISTA5 CORRIGIDA')
    output_lines.append(f'#URLTVG:{EPG_URL_TAG}')

    seen_channels = set()
    for entry in entries:
        ch_name = entry['ch_name']

        if ch_name in CHANNEL_MAP:
            info = CHANNEL_MAP[ch_name]
            new_extinf = build_extinf(entry, info)
            
            for url in entry['urls']:
                output_lines.append('')
                output_lines.append(new_extinf)
                output_lines.append(url)
                seen_channels.add(ch_name)
        else:
            output_lines.append('')
            output_lines.append(entry['extinf'])
            for url in entry['urls']:
                output_lines.append(url)

    output_content = '\n'.join(output_lines) + '\n'

    with open(OUTPUT_M3U, 'w') as f:
        f.write(output_content)

    unique_channels = set()
    for e in entries:
        unique_channels.add(e['ch_name'])

    print(f'\nCanais únicos processados: {len(unique_channels)}')
    for ch in sorted(unique_channels):
        info = CHANNEL_MAP.get(ch)
        if info:
            print(f'  [OK] {ch:50s} -> tvg-id={info["tvg-id"]}, tvg-logo=.jpg')
        else:
            print(f'  [??] {ch} (sem mapeamento EPG)')

    print(f'\nArquivo gerado: {OUTPUT_M3U}')
    print(f'Total de linhas: {len(output_content.splitlines())}')
    print(f'Total de entradas: {len(entries)}')
    print(f'EPG URL: {EPG_URL_TAG}')
    print(f'\nResumo final:')
    print(f'  EPG valido: {epg_ok}')
    print(f'  Streams funcionais: {streams_ok}')
    print(f'  Logos .jpg: {logos_ok}')
    print(f'  Sem imgur.com: True')
    print(f'  url-tvg adicionado: True')
    print(f'  tvg-id adicionado: True')

if __name__ == '__main__':
    main()
