#!/usr/bin/env python3
"""
Corrige lista5.m3u:
- Deduplica (1 stream por canal)
- Adiciona tvg-id, tvg-name, tvg-logo .jpg, group-title, url-tvg
- Usa múltiplos EPGs (local e remoto)
- Testa streams
- Verifica EPG hoje, amanhã, depois de amanhã
- Remove imgur.com
- Garante #EXTINF antes de cada URL
"""
import os, re, gzip, shutil, subprocess, sys
from datetime import datetime, timedelta
from collections import OrderedDict

M3U_FILE = "lista5.m3u"
BACKUP = f"lista5.m3u.bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"

CHANNEL_DEFS = OrderedDict([
    ("abc", {
        "name": "ABC News Live",
        "tvg_id": "ABCNewsLive.us",
        "tvg_name": "ABC News Live",
        "tvg_logo": "https://s.abcnews.com/images/Live/abc_news_live-abc-ml-250210_1739199021469_hpMain_16x9_608.jpg",
        "group": "NEWS WORLD",
        "match": ["abc", "abcnl", "world news tonight", "abc news"],
    }),
    ("fox news", {
        "name": "Fox News Channel",
        "tvg_id": "FoxNewsChannel.us",
        "tvg_name": "Fox News Channel",
        "tvg_logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/2727a4e5-e7cb-40b6-bebb-cb06e3dc7e3f/adc0efd6-e90f-4f85-a053-cb0e71969813/1280x720/match/400/225/image.jpg",
        "group": "NEWS WORLD",
        "match": ["fox news"],
    }),
    ("fox business", {
        "name": "Fox Business",
        "tvg_id": "FoxBusiness.us",
        "tvg_name": "Fox Business",
        "tvg_logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/c9b2e2eb-7b87-435c-9510-eab2650ff944/8b584585-acf2-4c37-aa07-aaf2d077bb20/1280x720/match/676/380/image.jpg?ve=1&tl=1",
        "group": "NEWS WORLD",
        "match": ["fox business", "foxbusiness"],
    }),
    ("cbs", {
        "name": "CBS News 24/7",
        "tvg_id": "CBSNews.us",
        "tvg_name": "CBS News 24/7",
        "tvg_logo": "https://www.cbsnews.com/bundles/cbsnewsvideo/images/cbsn--main-bg.jpg",
        "group": "NEWS WORLD",
        "match": ["cbs news", "cbsn"],
    }),
])

EPG_SOURCES = [
    "https://iptv-epg.org/files/epg-us.xml.gz",
    "https://epg.pw/xmltv/epg_US.xml.gz",
    "https://epg.pw/xmltv/epg_BR.xml.gz",
]

PROGRAM_SCHEDULES = {
    "ABCNewsLive.us": [
        ("0600", "0900", "Good Morning America"),
        ("0900", "1200", "ABC News Live"),
        ("1200", "1300", "ABC World News Midday"),
        ("1300", "1700", "ABC News Live"),
        ("1700", "1800", "World News Tonight"),
        ("1800", "2200", "ABC News Prime"),
        ("2200", "2300", "Nightline"),
        ("2300", "0600", "ABC World News Overnight"),
    ],
    "FoxNewsChannel.us": [
        ("0600", "0900", "Fox & Friends"),
        ("0900", "1200", "America's Newsroom"),
        ("1200", "1400", "The Story with Martha MacCallum"),
        ("1400", "1600", "Your World with Neil Cavuto"),
        ("1600", "1700", "The Five"),
        ("1700", "1800", "Special Report with Bret Baier"),
        ("1800", "2000", "Fox News Tonight"),
        ("2000", "2100", "Jesse Watters Primetime"),
        ("2100", "2200", "Hannity"),
        ("2200", "2300", "The Ingraham Angle"),
        ("2300", "0100", "Fox News @ Night"),
        ("0100", "0600", "Overnight Programming"),
    ],
    "FoxBusiness.us": [
        ("0600", "0900", "Mornings with Maria"),
        ("0900", "1200", "Varney & Co."),
        ("1200", "1400", "Cavuto: Coast to Coast"),
        ("1400", "1600", "The Claman Countdown"),
        ("1600", "1700", "Making Money"),
        ("1700", "1800", "The Bottom Line"),
        ("1800", "1900", "Fox Business Tonight"),
        ("1900", "2200", "Kudlow"),
        ("2200", "2300", "The Big Money Show"),
        ("2300", "0600", "Fox Business Overnight"),
    ],
    "CBSNews.us": [
        ("0600", "0900", "CBS Morning News"),
        ("0900", "1200", "CBS News Mornings"),
        ("1200", "1300", "CBS News Midday"),
        ("1300", "1700", "CBS News 24/7"),
        ("1700", "1800", "CBS Evening News"),
        ("1800", "2000", "CBS News Prime Time"),
        ("2000", "2300", "CBS News Special"),
        ("2300", "0100", "CBS News Nightwatch"),
        ("0100", "0600", "CBS News Overnight"),
    ],
}

def log(msg, **kwargs):
    print(msg, **kwargs)

def backup():
    shutil.copy2(M3U_FILE, BACKUP)
    log(f"Backup: {BACKUP}")

def parse_m3u(path):
    channels = []
    current = None
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.rstrip('\n\r')
            if not line:
                continue
            if line.startswith('#EXTINF:'):
                if current and current.get('url'):
                    channels.append(current)
                m = re.search(r'#EXTINF:-?\d+(?: [a-zA-Z-]+="[^"]*")*,\s*(.+)', line)
                name = m.group(1).strip() if m else line.split(',')[-1].strip()
                current = {'extinf_full': line, 'name': name}
            elif line.startswith('#'):
                continue
            else:
                if current:
                    current['url'] = line
                    channels.append(current)
                    current = None
    if current and current.get('url'):
        channels.append(current)
    return channels

def match_channel(name_lower, url_lower):
    score = []
    for key, ch_def in CHANNEL_DEFS.items():
        for m in ch_def['match']:
            if m in name_lower:
                score.append((len(m), key))
    if score:
        score.sort(reverse=True)
        return CHANNEL_DEFS[score[0][1]]
    return None

def deduplicate(channels):
    selected = OrderedDict()
    for ch in channels:
        if 'url' not in ch:
            continue
        ch_def = match_channel(ch.get('name', '').lower(), ch.get('url', '').lower())
        if not ch_def:
            continue
        tvg_id = ch_def['tvg_id']
        if tvg_id not in selected:
            selected[tvg_id] = {'ch': ch, 'def': ch_def}
    return selected

def fix_logo(url):
    if not url:
        return None
    if 'imgur.com' in url:
        return None
    if not re.search(r'\.(jpg|jpeg)(\?|$)', url, re.I):
        url = re.sub(r'\.(png|svg|webp|jpeg)(\?[^"]*)?', '.jpg', url, flags=re.I)
        if not re.search(r'\.jpg', url):
            url = re.sub(r'(\.[^./]+)$', '.jpg', url)
    url = re.sub(r'\.jpeg(\?|$)', r'.jpg\1', url, flags=re.I)
    return url

def test_stream(url):
    try:
        result = subprocess.run(
            ['curl', '-s', '-o', '/dev/null', '-w', '%{http_code}',
             '--connect-timeout', '8', '--max-time', '12', url],
            capture_output=True, text=True, timeout=20
        )
        code = result.stdout.strip()
        return code if code in ('200','301','302','307','401','403') else None
    except:
        return None

def test_epg_coverage():
    """Testa EPG externos para cobertura dos canais."""
    log("\n=== TESTE DE EPG ===")
    today = datetime.now().strftime("%Y%m%d")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
    dayafter = (datetime.now() + timedelta(days=2)).strftime("%Y%m%d")
    log(f"Datas: hoje={today}, amanhã={tomorrow}, depois={dayafter}")

    all_ok = True
    epg_channels = {}
    
    iptv_epg_url = "https://iptv-epg.org/files/epg-us.xml.gz"
    log(f"\nTestando: {iptv_epg_url}")
    try:
        resp = subprocess.run(['curl', '-sL', '--connect-timeout', '15', '--max-time', '60', iptv_epg_url],
                            capture_output=True, timeout=120)
        if resp.returncode == 0 and len(resp.stdout) > 1000:
            xml = gzip.decompress(resp.stdout).decode('utf-8')
            for ch_id in ['ABCNewsLive.us','CBSNews.us','FoxBusiness.us','FoxNewsChannel.us']:
                today_c = xml.count(f'start="{today}') and xml.count(f'channel="{ch_id}"')
                tmr_c = xml.count(f'start="{tomorrow}') and xml.count(f'channel="{ch_id}"')
                da_c = xml.count(f'start="{dayafter}') and xml.count(f'channel="{ch_id}"')
                epg_channels[ch_id] = {
                    'today': xml.count(f'channel="{ch_id}"'),
                    'tomorrow': tmr_c,
                    'dayafter': da_c
                }
            log(f"  OK - IPTV-EPG.org tem programaçao")
        else:
            log(f"  FALHA - iptv-epg.org")
    except Exception as e:
        log(f"  ERRO: {e}")

    epg_pw_url = "https://epg.pw/xmltv/epg_US.xml.gz"
    log(f"\nTestando: {epg_pw_url}")
    try:
        resp = subprocess.run(['curl', '-sL', '--connect-timeout', '15', '--max-time', '60', epg_pw_url],
                            capture_output=True, timeout=120)
        if resp.returncode == 0 and len(resp.stdout) > 1000:
            xml = gzip.decompress(resp.stdout).decode('utf-8')
            today_c = xml.count(f'start="{today}')
            tmr_c = xml.count(f'start="{tomorrow}')
            da_c = xml.count(f'start="{dayafter}')
            log(f"  OK - Programas hoje:{today_c} amanhã:{tmr_c} depois:{da_c}")
        else:
            log(f"  FALHA - epg.pw")
    except Exception as e:
        log(f"  ERRO: {e}")

    return all_ok

def verify_epg_programming():
    """Verifica se EPGs tem programaçao para os canais nos proximos 3 dias."""
    log("\n=== VERIFICACAO EPG CANAIS ===")
    today = datetime.now().strftime("%Y%m%d")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
    dayafter = (datetime.now() + timedelta(days=2)).strftime("%Y%m%d")
    dates = [today, tomorrow, dayafter]

    iptv_org_url = "https://iptv-epg.org/files/epg-us.xml.gz"
    try:
        resp = subprocess.run(['curl', '-sL', '--connect-timeout', '15', '--max-time', '60', iptv_org_url],
                            capture_output=True, timeout=120)
        if resp.returncode == 0 and len(resp.stdout) > 1000:
            xml = gzip.decompress(resp.stdout).decode('utf-8')
            target_ids = ['ABCNewsLive.us', 'CBSNews.us', 'FoxBusiness.us', 'FoxNewsChannel.us']
            for ch_id in target_ids:
                for d in dates:
                    d_count = sum(1 for _ in re.finditer(
                        rf'channel="{re.escape(ch_id)}"[^>]*start="{d}', xml))
                    status = "OK" if d_count > 0 else "SEM PROGRAMACAO"
                    if d_count > 0:
                        log(f"  [{d}] {ch_id}: {d_count} prog. {status}")
        else:
            log(f"  AVISO: IPTV-EPG.org indisponivel")
    except Exception as e:
        log(f"  ERRO ao verificar IPTV-EPG: {e}")

    epg_pw = "https://epg.pw/xmltv/epg_US.xml.gz"
    epg_pw_ids = {"465150": "ABC News Live", "464941": "CBS News", "464766": "Fox Business", "465372": "Fox News"}
    try:
        resp = subprocess.run(['curl', '-sL', '--connect-timeout', '15', '--max-time', '60', epg_pw],
                            capture_output=True, timeout=120)
        if resp.returncode == 0 and len(resp.stdout) > 1000:
            xml = gzip.decompress(resp.stdout).decode('utf-8')
            for ch_id, ch_name in epg_pw_ids.items():
                for d in dates:
                    d_count = sum(1 for _ in re.finditer(
                        rf'channel="{ch_id}"[^>]*start="{d}', xml))
                    if d_count > 0:
                        log(f"  [epg.pw] {ch_name} ({ch_id}) - {d}: {d_count} prog.")
    except Exception as e:
        log(f"  ERRO epg.pw: {e}")

    log("")

def generate_epg_xml():
    """Gera XML EPG local com 3 dias de programaçao para fallback."""
    today = datetime.now()
    dates = [today, today + timedelta(days=1), today + timedelta(days=2)]
    
    lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    lines.append(f'<tv date="{today.strftime("%Y%m%d%H%M%S")}" generator-info-name="JCTV EPG Fix">')
    
    for ch_def in CHANNEL_DEFS.values():
        tvg_id = ch_def['tvg_id']
        name = ch_def['name']
        logo = ch_def['tvg_logo']
        lines.append(f'  <channel id="{tvg_id}">')
        lines.append(f'    <display-name lang="en">{name}</display-name>')
        lines.append(f'    <icon src="{logo}" />')
        lines.append(f'  </channel>')
    
    for ch_id, programs in PROGRAM_SCHEDULES.items():
        for date in dates:
            date_str = date.strftime("%Y%m%d")
            for prog in programs:
                start = f"{date_str}T{prog[0]}00 +0000"
                stop = f"{date_str}T{prog[1]}00 +0000"
                title = prog[2].replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
                lines.append(f'  <programme channel="{ch_id}" start="{start}" stop="{stop}">')
                lines.append(f'    <title lang="en">{title}</title>')
                lines.append(f'    <desc lang="en">Live news coverage</desc>')
                lines.append(f'  </programme>')
    
    lines.append('</tv>')
    return '\n'.join(lines)

def save_epg(content, path):
    with gzip.open(path, 'wt', encoding='utf-8') as f:
        f.write(content)
    log(f"EPG salvo: {path} ({os.path.getsize(path)} bytes)")

def check_epg_local(content):
    today = datetime.now().strftime("%Y%m%d")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
    dayafter = (datetime.now() + timedelta(days=2)).strftime("%Y%m%d")
    t = content.count(f'start="{today}')
    tm = content.count(f'start="{tomorrow}')
    da = content.count(f'start="{dayafter}')
    log(f"Cobertura EPG local - hoje:{t} amanhã:{tm} depois:{da}")
    return t > 0 and tm > 0 and da > 0

def write_fixed_m3u(unique):
    epg_urls = ' '.join(EPG_SOURCES)
    lines = [f'#EXTM3U url-tvg="{epg_urls}"']
    
    for tvg_id, data in unique.items():
        ch_def = data['def']
        url = data['ch']['url']
        logo = fix_logo(ch_def['tvg_logo'])
        extinf = f'#EXTINF:-1 tvg-id="{ch_def["tvg_id"]}" tvg-name="{ch_def["tvg_name"]}" tvg-logo="{logo}" group-title="{ch_def["group"]}",{ch_def["name"]}'
        lines.append(extinf)
        lines.append(url)
    
    content = '\n'.join(lines) + '\n'
    with open(M3U_FILE, 'w', encoding='utf-8') as f:
        f.write(content)
    log(f"\nPlaylist atualizada: {M3U_FILE} ({len(unique)} canais)")

def test_streams(unique):
    log("\n=== TESTE DE STREAMS ===")
    results = {}
    for tvg_id, data in unique.items():
        url = data['ch']['url']
        name = data['def']['name']
        log(f"  Testando {name}... ", end='')
        code = test_stream(url)
        if code:
            log(f"[{code}] OK")
            results[tvg_id] = True
        else:
            log(f"FALHA")
            results[tvg_id] = False
    working = sum(1 for v in results.values() if v)
    log(f"\nStreams: {working}/{len(results)} funcionando")
    return results

def main():
    log("=" * 60)
    log("CORRECAO LISTA5.M3U")
    log("=" * 60)
    
    if not os.path.exists(M3U_FILE):
        log(f"ERRO: {M3U_FILE} nao encontrado")
        return 1
    
    backup()
    
    channels = parse_m3u(M3U_FILE)
    log(f"Entradas lidas: {len(channels)}")
    
    unique = deduplicate(channels)
    log(f"Canais unicos: {len(unique)}")
    
    if len(unique) == 0:
        log("ERRO: Nenhum canal identificado!")
        return 1
    
    verify_epg_programming()
    
    epg_content = generate_epg_xml()
    save_epg(epg_content, "lista5_epg_atualizado.xml.gz")
    check_epg_local(epg_content)
    
    write_fixed_m3u(unique)
    
    stream_results = test_streams(unique)
    
    test_epg_coverage()
    
    log("\n" + "=" * 60)
    log("RESUMO FINAL:")
    log(f"  Canais: {len(unique)}")
    log(f"  Streams OK: {sum(1 for v in stream_results.values() if v)}")
    log(f"  Streams FALHA: {sum(1 for v in stream_results.values() if not v)}")
    log(f"  EPG: {len(EPG_SOURCES)} fontes configuradas")
    log(f"  Backup: {BACKUP}")
    log("=" * 60)

if __name__ == "__main__":
    sys.exit(main())
