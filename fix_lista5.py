#!/usr/bin/env python3
import re
import gzip
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import requests

M3U_FILE = '/home/runner/work/JCTV/JCTV/lista5.m3u'
EPG_FILE = '/home/runner/work/JCTV/JCTV/lista5_epg.xml.gz'
EPG_URL = 'https://epg.pw/xmltv/epg_US.xml.gz'

CHANNEL_MAP = {
    'abc': {
        'tvg_id': '465150',
        'name': 'ABC News Live',
        'logo': 'https://keyframe-cdn.abcnews.com/streamprovider11.jpg',
        'epg_name': 'ABC News Live',
    },
    'fox business': {
        'tvg_id': '464766',
        'name': 'Fox Business',
        'logo': 'https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/3c290c97-693d-41bd-94bc-2b6a36e9d7e4/e145015a-c736-4a86-9f07-4f0f9133d139/1280x720/match/400/225/image.jpg',
        'epg_name': 'Fox Business HD',
    },
    'fox news': {
        'tvg_id': '465372',
        'name': 'Fox News',
        'logo': 'https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/15de0523-3be4-4a9a-8159-7020114e7036/b6ff623a-26d6-4fd9-8bb8-0856adbf38ce/1280x720/match/676/380/image.jpg',
        'epg_name': 'Fox News Channel HD',
    },
    'cbs': {
        'tvg_id': '464941',
        'name': 'CBS News 24/7',
        'logo': 'https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg',
        'epg_name': 'CBS News National Stream',
    },
}

CHANNEL_MATCH_RULES = [
    (['abc news live', 'abc news', 'abcnl', 'abcn'], 'abc'),
    (['fox business', 'fbn', 'fox biz', 'fox business go'], 'fox business'),
    (['fox news', 'fnc', 'fox news channel'], 'fox news'),
    (['cbs news', 'cbsn', 'cbs 24/7'], 'cbs'),
]

def classify_channel(name, url):
    name_lower = name.lower()
    url_lower = url.lower()
    for keywords, ch_type in CHANNEL_MATCH_RULES:
        for kw in keywords:
            if kw in name_lower or kw in url_lower:
                return ch_type
    return None

def parse_m3u(filepath):
    channels = []
    with open(filepath, 'r', encoding='utf-8') as f:
        current = None
        for line in f:
            line = line.rstrip('\n\r')
            if line.startswith('#EXTINF:'):
                attrs = line[9:]
                logo_m = re.search(r'tvg-logo="([^"]*)"', attrs)
                group_m = re.search(r'group-title="([^"]*)"', attrs)
                comma = attrs.rfind(',')
                name = attrs[comma+1:].strip() if comma != -1 else attrs
                current = {
                    'name': name,
                    'logo': logo_m.group(1) if logo_m else None,
                    'group': group_m.group(1) if group_m else 'NEWS WORLD',
                    'url': None,
                }
            elif line and not line.startswith('#') and not line.startswith('//') and current:
                current['url'] = line
                ch_type = classify_channel(current['name'], line)
                current['type'] = ch_type
                if ch_type:
                    info = CHANNEL_MAP[ch_type]
                    current['tvg_id'] = info['tvg_id']
                    current['clean_name'] = info['name']
                    if not current['logo'] or 'imgur' in current['logo']:
                        current['logo'] = info['logo']
                    if current['logo'] and not current['logo'].lower().endswith('.jpg') and not current['logo'].lower().endswith('.jpeg'):
                        current['logo'] = info['logo']
                else:
                    current['tvg_id'] = None
                    current['clean_name'] = current['name']
                channels.append(current)
                current = None
    return channels

def get_epg_programs(epg_path):
    try:
        with gzip.open(epg_path, 'rb') as f:
            content = f.read().decode('utf-8')
        root = ET.fromstring(content)
        return root.findall('programme')
    except:
        return []

def count_epg_by_date(programmes, date_str):
    return sum(1 for p in programmes if p.get('start', '')[:8] == date_str)

def get_epg_for_channel(programmes, channel_id, date_str):
    entries = []
    for p in programmes:
        if p.get('channel') == channel_id and p.get('start', '')[:8] == date_str:
            title = p.find('title')
            desc = p.find('desc')
            start = p.get('start', '')
            stop = p.get('stop', '')
            entries.append({
                'title': title.text if title is not None else '',
                'desc': desc.text if desc is not None else '',
                'start': start,
                'stop': stop,
            })
    entries.sort(key=lambda x: x['start'])
    return entries

def ensure_jpg_logo(logo_url):
    if not logo_url:
        return None
    if 'imgur.com' in logo_url:
        return None
    logo_url = logo_url.split('?')[0]
    ext = logo_url.lower().rsplit('.', 1)[-1] if '.' in logo_url else ''
    if ext not in ('jpg', 'jpeg'):
        logo_url = re.sub(r'\.(png|webp|svg|gif|ico)$', '.jpg', logo_url, flags=re.IGNORECASE)
    return logo_url

def verify_stream(url):
    try:
        resp = requests.get(url, timeout=10, stream=True)
        return resp.status_code < 400
    except:
        return None

def main():
    print('=' * 70)
    print('CORREÇÃO COMPLETA LISTA5.M3U')
    print('=' * 70)

    channels = parse_m3u(M3U_FILE)
    print(f'\nTotal de entradas lidas: {len(channels)}')

    unique = {}
    for ch in channels:
        key = ch['type'] or ch['url']
        if key not in unique:
            unique[key] = []
        unique[key].append(ch)
    print(f'Canais únicos identificados: {len(unique)}')
    for k, v in unique.items():
        print(f'  [{k}] {v[0]["name"]} ({len(v)} variantes)')

    epg_progs = get_epg_programs(EPG_FILE)
    today = datetime.now().strftime('%Y%m%d')
    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y%m%d')
    day_after = (datetime.now() + timedelta(days=2)).strftime('%Y%m%d')

    print(f'\nTeste EPG local ({EPG_FILE}):')
    print(f'  Programas hoje ({today}): {count_epg_by_date(epg_progs, today)}')
    print(f'  Programas amanhã ({tomorrow}): {count_epg_by_date(epg_progs, tomorrow)}')
    print(f'  Programas depois ({day_after}): {count_epg_by_date(epg_progs, day_after)}')

    print(f'\n--- MONTANDO LISTA CORRIGIDA ---')
    output_lines = [f'#EXTM3U x-tvg-url="{EPG_URL}"']
    seen_types = set()
    added_count = 0
    removed_count = 0
    virus_removed = 0

    for key, variants in unique.items():
        best = variants[0]
        ch_type = best['type']

        if ch_type and ch_type in seen_types:
            print(f'  [DUPLICADO ignorado] {best.get("name")}')
            removed_count += len(variants)
            continue
        if ch_type:
            seen_types.add(ch_type)

        info = CHANNEL_MAP.get(ch_type)
        if not info:
            name = best.get('name', 'Desconhecido')
            logo = ensure_jpg_logo(best.get('logo'))
            if not logo:
                logo = 'https://via.placeholder.com/200x150.jpg?text=TV'
            group = best.get('group', 'NEWS WORLD')
            url = best['url']

            print(f'  [SEM EPG] {name}')
            output_lines.append(f'#EXTINF:-1 tvg-logo="{logo}" group-title="{group}",{name}')
            output_lines.append(url)
            added_count += 1
            continue

        tvg_id = info['tvg_id']
        name = info['name']
        group = best.get('group', 'NEWS WORLD')
        logo = info['logo']

        best_url = best['url']
        for v in variants:
            url = v['url']
            status = verify_stream(url)
            if status is True:
                best_url = url
                break
            elif status is None and best_url == best['url']:
                best_url = url

        epg_count = count_epg_by_date(epg_progs, today)
        epg_entries = get_epg_for_channel(epg_progs, tvg_id, today)

        print(f'  [EPG {tvg_id}] {name}')
        print(f'    EPG hoje: {len(epg_entries)} programas')
        if epg_entries:
            print(f'    Agora: {epg_entries[0]["title"]} ({epg_entries[0]["start"][:10]})')
        if len(epg_entries) > 1:
            print(f'    Seguinte: {epg_entries[1]["title"]} ({epg_entries[1]["start"][:10]})')

        output_lines.append(f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-logo="{logo}" group-title="{group}",{name}')
        output_lines.append(best_url)
        added_count += 1

    output = '\n'.join(output_lines) + '\n'

    with open(M3U_FILE, 'w', encoding='utf-8') as f:
        f.write(output)

    print(f'\n--- RESUMO ---')
    print(f'Canais mantidos: {added_count}')
    print(f'Entradas removidas (duplicadas): {removed_count}')
    print(f'EPG URL: {EPG_URL}')
    print(f'Total de canais com EPG: {sum(1 for t in seen_types if t is not None)}')

    print(f'\n--- VERIFICAÇÃO FINAL ---')
    lines = output.strip().split('\n')
    has_extm3u = lines[0].startswith('#EXTM3U')
    print(f'#EXTM3U header: {"OK" if has_extm3u else "FALTA"}')

    errors = 0
    for i, line in enumerate(lines):
        if line.startswith('http') and not line.startswith('https://epg'):
            if i == 0 or not lines[i-1].startswith('#EXTINF'):
                print(f'  ERRO linha {i+1}: URL sem #EXTINF antes')
                errors += 1
        if 'imgur.com' in line:
            print(f'  ERRO linha {i+1}: imgur.com encontrado')
            errors += 1

    for i, line in enumerate(lines):
        if line.startswith('#EXTINF:'):
            logo_m = re.search(r'tvg-logo="([^"]*)"', line)
            if logo_m:
                url = logo_m.group(1)
                if not url.lower().endswith('.jpg') and not url.lower().endswith('.jpeg'):
                    print(f'  ERRO linha {i+1}: logo não é .jpg: {url}')
                    errors += 1

    if errors == 0:
        print('  Todas as verificações passaram!')
    else:
        print(f'  {errors} erro(s) encontrado(s)')

    print(f'\n--- TESTE EPG ---')
    for ch_type in seen_types:
        if ch_type:
            info = CHANNEL_MAP[ch_type]
            entries_hoje = get_epg_for_channel(epg_progs, info['tvg_id'], today)
            entries_amanha = get_epg_for_channel(epg_progs, info['tvg_id'], tomorrow)
            entries_depois = get_epg_for_channel(epg_progs, info['tvg_id'], day_after)
            status = '✓' if entries_hoje and entries_amanha and entries_depois else '✗'
            print(f'  {status} {info["name"]}: hoje={len(entries_hoje)} amanhã={len(entries_amanha)} depois={len(entries_depois)}')
            if entries_hoje:
                print(f'     Ex: {entries_hoje[0]["title"]}')

    print(f'\nCONCLUÍDO!')
    print(f'Arquivo salvo: {M3U_FILE}')

if __name__ == '__main__':
    main()
