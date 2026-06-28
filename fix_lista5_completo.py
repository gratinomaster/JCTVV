#!/usr/bin/env python3
import re
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from collections import OrderedDict
import gzip
import os

M3U_FILE = 'lista5.m3u'
BACKUP_FILE = 'lista5.m3u.bak.' + datetime.now().strftime('%Y%m%d_%H%M%S')

EPG_LOCAL = {
    'combinado': 'lista5_epg_combinado.xml',
    'globo': 'GLOBOEPG.xml',
    'epgfull': 'EPGFULL.xml.gz',
}

EPG_URLS = [
    'https://raw.githubusercontent.com/JCTV/JCTV/main/lista5_epg_combinado.xml',
    'https://raw.githubusercontent.com/JCTV/JCTV/main/GLOBOEPG.xml',
    'https://github.com/iptv-org/epg/raw/master/guide/us.xml.gz',
]

CHANNEL_CLEAN_NAMES = {
    'ABC News Live - ABC News': 'ABC News Live',
    'Watch Fox News Channel Online | Stream Fox News': 'Fox News Channel',
    'Fox Business Go | Fox News Video': 'Fox Business',
    'Watch CBS News 24/7, our free live news stream': 'CBS News 24/7',
    'Watch CBS News 24/7': 'CBS News 24/7',
}

TVG_IDS = {
    'ABC News Live': 'ABCNewsLive.us',
    'ABC News': 'ABCNewsLive.us',
    'Fox News': 'FoxNewsChannel.us',
    'Fox News Channel': 'FoxNewsChannel.us',
    'Fox Business': 'FoxBusiness.us',
    'CBS News': 'CBSNews.us',
    'CBS News 24/7': 'CBSNews.us',
}

TVG_LOGOS = {
    'ABC News Live': 'https://keyframe-cdn.abcnews.com/streamprovider11.jpg',
    'ABC News': 'https://keyframe-cdn.abcnews.com/streamprovider11.jpg',
    'Fox News': 'https://cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/ee1fa2bb-133a-4f23-8102-894bc6a8021d/957a8e3d-9f4f-4257-96fe-075b3ecba18b/1280x720/match/image.jpg',
    'Fox News Channel': 'https://cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/ee1fa2bb-133a-4f23-8102-894bc6a8021d/957a8e3d-9f4f-4257-96fe-075b3ecba18b/1280x720/match/image.jpg',
    'Fox Business': 'https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/4fdfb4e5-62fc-4225-ba49-de956771ead5/1431e2ca-03f8-4f71-badb-55618b0e2e09/1280x720/match/400/225/image.jpg',
    'CBS News': 'https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg',
    'CBS News 24/7': 'https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg',
}

AVOID_DOMAINS = ['imgur.com']


def log(msg):
    print(f'[{datetime.now().strftime("%H:%M:%S")}] {msg}')


def backup_file():
    if os.path.exists(M3U_FILE):
        os.system(f'cp {M3U_FILE} {BACKUP_FILE}')
        log(f'Backup criado: {BACKUP_FILE}')
    else:
        log(f'ERRO: {M3U_FILE} nao encontrado!')
        exit(1)


def read_epg_channels():
    epg_map = {}
    for name, path in EPG_LOCAL.items():
        try:
            if path.endswith('.gz'):
                with gzip.open(path, 'rb') as f:
                    content = f.read()
            else:
                with open(path, 'rb') as f:
                    content = f.read()
            root = ET.fromstring(content)
            for ch in root.findall('.//channel'):
                ch_id = ch.get('id')
                dn = ch.find('display-name')
                dn_text = dn.text if dn is not None else ch_id
                epg_map[ch_id] = {'id': ch_id, 'display_name': dn_text, 'source': name}
        except Exception as e:
            log(f'  Erro lendo {path}: {e}')

    log(f'Canais EPG carregados: {len(epg_map)}')
    for ch_id, info in epg_map.items():
        log(f'  {ch_id} ({info["source"]})')
    return epg_map


def test_epg_for_today():
    """Testa se os EPGs tem programacao para hoje, amanha e depois."""
    log('=== TESTE DE EPG ===')
    results = {}
    for name, path in EPG_LOCAL.items():
        try:
            if path.endswith('.gz'):
                with gzip.open(path, 'rb') as f:
                    content = f.read()
            else:
                with open(path, 'rb') as f:
                    content = f.read()
            root = ET.fromstring(content)
            programmes = root.findall('.//programme')
            hoje = datetime.now().strftime('%Y%m%d')
            amanha = (datetime.now() + timedelta(days=1)).strftime('%Y%m%d')
            depois = (datetime.now() + timedelta(days=2)).strftime('%Y%m%d')
            c_hoje = sum(1 for p in programmes if p.get('start', '')[:8] == hoje)
            c_amanha = sum(1 for p in programmes if p.get('start', '')[:8] == amanha)
            c_depois = sum(1 for p in programmes if p.get('start', '')[:8] == depois)
            status = 'OK' if (c_hoje > 0 and c_amanha > 0) else 'INSUFICIENTE'
            log(f'  {name}: Hoje={c_hoje} Amanha={c_amanha} Depois={c_depois} -> {status}')
            results[name] = {'status': status, 'hoje': c_hoje, 'amanha': c_amanha, 'depois': c_depois}
        except Exception as e:
            log(f'  {name}: ERRO {e}')
            results[name] = {'status': 'ERRO', 'erro': str(e)}

    all_ok = all(r.get('status') == 'OK' for r in results.values() if r.get('status') != 'ERRO')
    if not all_ok:
        log('  AVISO: Alguns EPGs podem ter programacao insuficiente')
    return results


def parse_m3u(content):
    entries = []
    lines = content.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if line.startswith('#EXTM3U'):
            entries.append({'type': 'header', 'line': line})
            i += 1
        elif line.startswith('#EXTINF:'):
            extinf = line
            i += 1
            urls = []
            while i < len(lines) and lines[i].strip() and not lines[i].strip().startswith('#'):
                url = lines[i].strip()
                if url.startswith('http'):
                    urls.append(url)
                i += 1
            entries.append({'type': 'channel', 'extinf': extinf, 'urls': urls})
        elif line.startswith('#'):
            entries.append({'type': 'comment', 'line': line})
            i += 1
        elif line.startswith('http'):
            entries.append({'type': 'orphan_url', 'line': line})
            i += 1
        else:
            i += 1
    return entries


def extract_channel_name(extinf):
    # M3U format: #EXTINF:-1 attr="val" attr2="val2",Channel Name
    # Channel name is everything after the first unquoted comma
    # But channel names can contain commas, so we be smart about it.
    # Try getting everything after the last quoted attr
    m = re.search(r'"\s*,\s*(.+)$', extinf)
    if m:
        return m.group(1).strip()
    # Fallback: split on comma and take everything after attrs
    parts = extinf.split(',', 1)
    if len(parts) > 1:
        return parts[1].strip()
    return ''


def extract_attr(extinf, attr):
    m = re.search(rf'{attr}="([^"]*)"', extinf)
    if m:
        return m.group(1)
    return ''


def set_attr(extinf, attr, value):
    pattern = rf'{attr}="[^"]*"'
    new_attr = f'{attr}="{value}"'
    if re.search(pattern, extinf):
        return re.sub(pattern, new_attr, extinf)
    else:
        return re.sub(r'#EXTINF:-1', f'#EXTINF:-1 {new_attr}', extinf, count=1)


def deduplicate_channels(entries):
    seen = OrderedDict()
    for entry in entries:
        if entry['type'] == 'channel':
            name = extract_channel_name(entry['extinf'])
            if name in seen:
                seen[name]['urls'].extend(entry['urls'])
            else:
                seen[name] = entry
    return list(seen.values())


def fix_m3u():
    log('=== INICIANDO CORRECAO DO LISTA5.M3U ===')

    # Backup
    backup_file()

    # Test EPG
    epg_map = read_epg_channels()
    test_epg_for_today()

    # Read current file
    with open(M3U_FILE, 'r', encoding='utf-8') as f:
        content = f.read()

    entries = parse_m3u(content)
    log(f'Entradas encontradas: {len(entries)}')

    # Count unique channels
    channel_entries = [e for e in entries if e['type'] == 'channel']
    unique_names = set()
    for e in channel_entries:
        unique_names.add(extract_channel_name(e['extinf']))
    log(f'Canais unicos encontrados: {len(unique_names)} -> {sorted(unique_names)}')

    # Deduplicate - group by channel name, keep all URLs
    seen_channels = OrderedDict()
    for e in entries:
        if e['type'] == 'channel':
            raw_name = extract_channel_name(e['extinf'])

            # Try to match against clean names first
            name = raw_name
            for dirty, clean in CHANNEL_CLEAN_NAMES.items():
                if dirty.lower() in raw_name.lower() or raw_name.lower() in dirty.lower():
                    name = clean
                    break

            if name not in seen_channels:
                entry = dict(e)
                seen_channels[name] = entry
            else:
                seen_channels[name]['urls'].extend(e['urls'])

    # Rebuild content
    output_lines = []

    # Header with EPG URLs
    epg_urls_str = ' '.join(EPG_URLS)
    output_lines.append(f'#EXTM3U x-tvg-url="{epg_urls_str}"')

    for name, entry in seen_channels.items():
        extinf = entry['extinf']

        # Remove existing tvg-* attrs to re-add cleanly
        for attr in ['tvg-id', 'tvg-name', 'tvg-logo']:
            extinf = re.sub(rf'\s*{attr}="[^"]*"', '', extinf)

        # Find best tvg-id and logo
        tvg_id = None
        tvg_logo = None

        for search_name, tid in TVG_IDS.items():
            if search_name.lower() in name.lower() or name.lower() in search_name.lower():
                tvg_id = tid
                break

        for search_name, logo in TVG_LOGOS.items():
            if search_name.lower() in name.lower() or name.lower() in search_name.lower():
                tvg_logo = logo
                break

        # Prefer the dedicated logo from our mapping over the original
        # Only keep original if we don't have a mapping for this channel
        if name not in TVG_LOGOS:
            existing_logo = extract_attr(entry['extinf'], 'tvg-logo')
            if existing_logo:
                tvg_logo = existing_logo

        if tvg_logo:
            # Ensure .jpg extension
            ext_clean = re.search(r'\.(\w+)(\?.*)?$', tvg_logo)
            if ext_clean:
                ext = ext_clean.group(1).lower()
                if ext not in ('jpg', 'jpeg'):
                    base = re.sub(r'\.[^.]+(\?.*)?$', '', tvg_logo)
                    tvg_logo = base + '.jpg'
                    log(f'  Logo convertido para .jpg: {name}')
            else:
                tvg_logo = tvg_logo.rstrip('/') + '/logo.jpg'
            # Check forbidden domains
            forbidden = False
            for domain in AVOID_DOMAINS:
                if domain in tvg_logo.lower():
                    forbidden = True
                    log(f'  Removendo logo imgur.com para: {name}')
                    break
            if forbidden:
                fallback = TVG_LOGOS.get(name, None)
                if fallback:
                    tvg_logo = fallback

        # Build extinf with proper order (no trailing space before comma)
        parts = ['#EXTINF:-1']
        if tvg_id:
            parts.append(f'tvg-id="{tvg_id}"')
        if tvg_logo:
            parts.append(f'tvg-logo="{tvg_logo}"')
        parts.append(f'tvg-name="{name}"')

        # Preserve group-title and other attributes
        group_title = extract_attr(extinf, 'group-title')
        if group_title:
            parts.append(f'group-title="{group_title}"')
        else:
            parts.append('group-title="NEWS WORLD"')

        attr_str = ' '.join(parts)
        extinf = f'{attr_str},{name}'

        # Keep only the first working URL (prefer non-DRM if multiple)
        if entry['urls']:
            best_url = entry['urls'][0]
        else:
            best_url = ''

        output_lines.append(extinf)
        if best_url:
            output_lines.append(best_url)

    # Write output
    output = '\n'.join(output_lines) + '\n'
    with open(M3U_FILE, 'w', encoding='utf-8') as f:
        f.write(output)

    log(f'=== ARQUIVO SALVO: {M3U_FILE} ===')
    log(f'Total de canais: {len(seen_channels)}')

    # Verify
    with open(M3U_FILE, 'r') as f:
        verify = f.read()
    verify_entries = parse_m3u(verify)
    verify_channels = [e for e in verify_entries if e['type'] == 'channel']
    log(f'Verificacao: {len(verify_channels)} canais no arquivo final')

    # Test URLs
    log('=== TESTE DE STREAMS ===')
    for entry in verify_channels:
        name = extract_channel_name(entry['extinf'])
        for url in entry['urls'][:1]:
            try:
                r = requests.head(url, timeout=10, allow_redirects=True,
                                  headers={'User-Agent': 'Mozilla/5.0'})
                status = r.status_code
                if status in (200, 301, 302, 307, 308, 405):
                    log(f'  OK: {name} (HTTP {status})')
                elif status == 403:
                    log(f'  PROVAVEL OK: {name} (HTTP 403 - streaming protegido)')
                else:
                    log(f'  PROBLEMA: {name} (HTTP {status})')
            except Exception as e:
                log(f'  ERRO: {name} - {str(e)[:60]}')


if __name__ == '__main__':
    fix_m3u()
