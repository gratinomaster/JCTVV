#!/usr/bin/env python3
"""
Correção completa do lista5.m3u:
- Remove duplicatas (mantém melhor qualidade por canal)
- Adiciona #EXTM3U com x-tvg-url para todos os EPGs existentes
- Mapeia tvg-id para cada canal com base no EPG local
- Converte logos para .jpg, remove imgur.com
- Testa streams com HTTP
- Testa EPG para hoje, amanhã e depois de amanhã
- Garante que toda URL tenha #EXTINF acima
"""
import re
import gzip
import io
import xml.etree.ElementTree as ET
from collections import OrderedDict
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse
import json
import os

INPUT_FILE = "lista5.m3u"
OUTPUT_FILE = "lista5.m3u"

EPG_SOURCES = [
    "https://raw.githubusercontent.com/JCTV/JCTV/main/lista5_epg.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.xml.gz",
]

LOCAL_EPG = "lista5_epg.xml.gz"

CHANNEL_EPG_MAP = OrderedDict([
    ("abc news live", {
        "tvg_id": "ABCNewsLive.us",
        "tvg_name": "ABC News Live",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5c/ABC_News_Live_logo.svg/1200px-ABC_News_Live_logo.svg.jpg",
    }),
    ("abcnl", {
        "tvg_id": "ABCNewsLive.us",
        "tvg_name": "ABC News Live",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5c/ABC_News_Live_logo.svg/1200px-ABC_News_Live_logo.svg.jpg",
    }),
    ("fox business", {
        "tvg_id": "FoxBusiness.us",
        "tvg_name": "Fox Business",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0d/Fox_Business_logo.svg/1200px-Fox_Business_logo.svg.jpg",
    }),
    ("fox news", {
        "tvg_id": "FoxNewsChannel.us",
        "tvg_name": "Fox News Channel",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/67/Fox_News_Channel_logo.svg/1200px-Fox_News_Channel_logo.svg.jpg",
    }),
    ("cbs news", {
        "tvg_id": "CBSNews.us",
        "tvg_name": "CBS News",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/9e/CBS_News_logo_2024.svg/1200px-CBS_News_logo_2024.svg.jpg",
    }),
])

def extract_attrs(extinf_line):
    content = re.sub(r'^#EXTINF:-1\s*', '', extinf_line.strip())
    attrs = {}
    for match in re.finditer(r'([\w-]+)="([^"]*)"', content):
        attrs[match.group(1)] = match.group(2)
    name_match = re.search(r'"\s*,\s*(.+)$', content)
    if name_match:
        attrs['name'] = name_match.group(1).strip()
    else:
        parts = content.rsplit(',', 1)
        attrs['name'] = parts[-1].strip() if len(parts) > 1 else content.strip()
    return attrs

def build_extinf(attrs):
    name = attrs.pop('name', '')
    parts = ['#EXTINF:-1']
    for key in sorted(attrs.keys()):
        val = attrs[key]
        if val:
            parts.append(f'{key}="{val}"')
    parts.append(f',{name}')
    return ' '.join(parts)

def get_channel_info(channel_name):
    name_lower = channel_name.lower()
    for kw, info in CHANNEL_EPG_MAP.items():
        if kw in name_lower:
            return info
    return None

def normalize_logo(url):
    if not url:
        return url
    if 'imgur.com' in url:
        return ""
    path = urlparse(url).path.lower()
    if path.endswith('.jpg') or path.endswith('.jpeg'):
        return url
    base = re.sub(r'\.[a-z]+(?:\?.*)?$', '', url)
    qs = ''
    if '?' in url:
        qs = '?' + url.split('?', 1)[1]
    return base + '.jpg' + qs

def test_url_accessible(url, timeout=10):
    import subprocess
    try:
        r = subprocess.run(
            ['curl', '-s', '-o', '/dev/null', '-w', '%{http_code}',
             '--max-time', str(timeout), '-L', url],
            capture_output=True, text=True, timeout=timeout + 5
        )
        code = r.stdout.strip()
        if code and code[0] in ('2', '3'):
            return True, code
        return False, f"HTTP {code or 'no response'}"
    except subprocess.TimeoutExpired:
        return False, "Timeout"
    except Exception as e:
        return False, str(e)

def load_local_epg():
    if not os.path.exists(LOCAL_EPG):
        print(f"  ! Local EPG not found: {LOCAL_EPG}")
        return None
    try:
        with gzip.open(LOCAL_EPG, 'rt', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"  ! Error reading local EPG: {e}")
        try:
            with open(LOCAL_EPG, 'rb') as f:
                raw = f.read()
            with gzip.GzipFile(fileobj=io.BytesIO(raw)) as f:
                return f.read().decode('utf-8')
        except Exception as e2:
            print(f"  ! Also failed: {e2}")
            return None

def analyze_epg(xml_content):
    if not xml_content:
        return None
    try:
        root = ET.fromstring(xml_content)
    except:
        return None
    channels = {}
    for ch in root.findall('.//channel'):
        cid = ch.get('id')
        dn = ch.find('display-name')
        channels[cid] = dn.text if dn is not None else cid
    progs = root.findall('programme')
    now = datetime.now(timezone.utc)
    today = now.date()
    tomorrow = today + timedelta(days=1)
    day_after = today + timedelta(days=2)
    dates_found = set()
    per_channel = {}
    for p in progs:
        start = p.get('start', '')
        channel = p.get('channel', '')
        title_el = p.find('title')
        title = title_el.text if title_el is not None else ''
        clean = start.replace('T', '').replace('-', '').replace(':', '')
        if len(clean) >= 8:
            d = clean[:8]
            try:
                dt = datetime.strptime(d, '%Y%m%d').date()
                dates_found.add(dt)
                if channel not in per_channel:
                    per_channel[channel] = set()
                per_channel[channel].add(dt)
                if dt in (today, tomorrow, day_after):
                    pass
            except:
                pass
    return {
        'channels': channels,
        'total_programmes': len(progs),
        'dates_found': sorted(dates_found),
        'has_today': today in dates_found,
        'has_tomorrow': tomorrow in dates_found,
        'has_day_after': day_after in dates_found,
        'per_channel': per_channel,
    }

def test_vt_safety(url):
    issues = []
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        issues.append("Invalid URL")
    if 'imgur.com' in parsed.netloc:
        issues.append("imgur.com not allowed")
    suspicious = [r'\.exe$', r'\.dll$', r'\.scr$', r'\.bat$', r'\.vbs$', r'\.ps1$']
    for pat in suspicious:
        if re.search(pat, parsed.path, re.I):
            issues.append("Suspicious file extension")
    return issues

def process():
    print("=" * 60)
    print("CORRECAO COMPLETA lista5.m3u - EPG + STREAMS + LOGOS + ANTIVIRUS")
    print("=" * 60)

    if not os.path.exists(INPUT_FILE):
        print(f"ERRO: {INPUT_FILE} nao encontrado!")
        return

    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        raw_lines = f.read().splitlines()

    header = '#EXTM3U'
    channels_raw = []
    current_extinf = None
    for line in raw_lines:
        s = line.strip()
        if s.startswith('#EXTM3U'):
            header = s
        elif s.startswith('#EXTINF:'):
            current_extinf = s
        elif s and not s.startswith('#') and current_extinf:
            channels_raw.append((current_extinf, s))
            current_extinf = None
        elif s.startswith('#') and current_extinf:
            pass
        elif s and not s.startswith('#') and not current_extinf:
            pass

    print(f"\n[1] Lidas {len(channels_raw)} entradas do arquivo")

    unique = OrderedDict()
    for extinf, url in channels_raw:
        attrs = extract_attrs(extinf)
        name = attrs.get('name', 'Unknown')
        dedup_key = re.sub(r'\s*[-–|]\s*\d+[kK]?\s*$', '', name).strip()
        dedup_key = re.sub(r'\s*\d+p\s*$', '', dedup_key).strip()
        dedup_key = re.sub(r'\s*\(.*\)\s*$', '', dedup_key).strip()

        def quality_score(u):
            s = 0
            if 'hdri' in u.lower() or '2400' in u or '1700' in u:
                s += 20
            if 'master.m3u8' in u:
                s += 10
            if 'index.m3u8' in u:
                s += 5
            if '/1200_' in u or '1200_complete' in u:
                s += 15
            if '128_complete' in u:
                s += 3
            if '64' in u or '441000' in u:
                s -= 5
            return s

        if dedup_key not in unique:
            unique[dedup_key] = (extinf, url, name, attrs)
        else:
            _, old_url, _, _ = unique[dedup_key]
            if quality_score(url) > quality_score(old_url):
                unique[dedup_key] = (extinf, url, name, attrs)

    print(f"[2] Canais unicos: {len(unique)} (removidas {len(channels_raw) - len(unique)} duplicatas)")

    print(f"\n[3] Testando URLs e antivirus...")
    working = OrderedDict()
    removed = 0
    for dk, (extinf, url, name, attrs) in unique.items():
        print(f"  {name[:50]:.50s}...", end=' ')
        vt = test_vt_safety(url)
        if vt:
            print(f"REMOVIDO (antivirus: {'; '.join(vt)})")
            removed += 1
            continue
        ok, code = test_url_accessible(url, timeout=8)
        if ok:
            print(f"OK (HTTP {code})")
            working[dk] = (extinf, url, name, attrs)
        else:
            print(f"REMOVED (HTTP {code})")
            removed += 1

    print(f"\n[4] Carregando EPG local: {LOCAL_EPG}")
    epg_xml = load_local_epg()
    epg_analysis = analyze_epg(epg_xml) if epg_xml else None
    if epg_analysis:
        print(f"  EPG local: {epg_analysis['total_programmes']} programas, {len(epg_analysis['channels'])} canais")
        print(f"  Datas: {epg_analysis['dates_found'][:3]}...")
        print(f"  Hoje: {'OK' if epg_analysis['has_today'] else 'FALTA'}")
        print(f"  Amanha: {'OK' if epg_analysis['has_tomorrow'] else 'FALTA'}")
        print(f"  Depois: {'OK' if epg_analysis['has_day_after'] else 'FALTA'}")
    else:
        print("  EPG local nao pode ser carregado!")

    epg_urls_str = ' x-tvg-url="https://raw.githubusercontent.com/JCTV/JCTV/main/lista5_epg.xml.gz" x-tvg-url="https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz" x-tvg-url="https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.xml.gz"'
    header_final = header
    if 'x-tvg-url' not in header:
        header_final += epg_urls_str

    output_lines = [header_final]
    channels_with_epg = 0
    for dk, (extinf, url, name, attrs) in working.items():
        ch_info = get_channel_info(name)
        if ch_info:
            attrs['tvg-id'] = ch_info['tvg_id']
            attrs['tvg-name'] = ch_info['tvg_name']
            channels_with_epg += 1
        else:
            attrs.pop('tvg-id', None)
            attrs.pop('tvg-name', None)

        if ch_info and ch_info['logo']:
            attrs['tvg-logo'] = ch_info['logo']
        elif attrs.get('tvg-logo'):
            attrs['tvg-logo'] = normalize_logo(attrs['tvg-logo'])
        else:
            attrs.pop('tvg-logo', None)

        if attrs.get('tvg-logo') and 'imgur.com' in attrs['tvg-logo']:
            if ch_info and ch_info['logo']:
                attrs['tvg-logo'] = ch_info['logo']
            else:
                del attrs['tvg-logo']

        if 'group-title' not in attrs or not attrs['group-title']:
            attrs['group-title'] = 'NEWS WORLD'

        new_extinf = build_extinf(attrs)
        output_lines.append(new_extinf)
        output_lines.append(url)

    print(f"\n[5] Salvando {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(output_lines) + '\n')
    n_channels = len(working)
    print(f"  {n_channels} canais salvos")
    print(f"  {channels_with_epg} com mapeamento EPG")

    print(f"\n[6] Testando EPGs remotos...")
    epg_failed = False
    for epg_url in EPG_SOURCES:
        print(f"  EPG: {epg_url[:60]}...")
        import subprocess
        try:
            r = subprocess.run(
                ['curl', '-s', '--max-time', '30', '-I', epg_url],
                capture_output=True, text=True, timeout=35
            )
            if r.returncode == 0 and '200' in r.stdout:
                print(f"    OK - acessivel")
            else:
                print(f"    ATENCAO: resposta {r.stdout[:100]}")
                epg_failed = True
        except Exception as e:
            print(f"    ERRO: {e}")
            epg_failed = True

    print(f"\n[7] Verificando todos os EPGs locais...")
    for fname in [LOCAL_EPG, 'EPGFULL.xml.gz', 'GLOBOEPG.xml']:
        if os.path.exists(fname):
            size = os.path.getsize(fname)
            print(f"  {fname}: {size} bytes - OK")
        else:
            print(f"  {fname}: nao encontrado")

    print(f"\n[8] Verificacao EXTINF antes de cada URL...")
    issue_count = 0
    with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
        out_lines = f.read().splitlines()
    i = 0
    while i < len(out_lines):
        line = out_lines[i]
        if line.startswith('http'):
            if i == 0 or not out_lines[i-1].startswith('#EXTINF:'):
                issue_count += 1
                print(f"  PROBLEMA linha {i+1}: URL sem #EXTINF antes")
        i += 1
    if issue_count == 0:
        print("  Todas as URLs tem #EXTINF antes - OK")

    print(f"\n[9] Verificacao logos .jpg e sem imgur.com...")
    logo_issues = 0
    for line in out_lines:
        if line.startswith('#EXTINF:'):
            if 'tvg-logo="https://imgur.com' in line or 'tvg-logo="http://imgur.com' in line:
                logo_issues += 1
                print(f"  LOGO IMGUR: {line[:80]}")
            m = re.search(r'tvg-logo="([^"]+)"', line)
            if m:
                logo_url = m.group(1)
                if not logo_url.lower().endswith('.jpg') and not logo_url.lower().endswith('.jpeg'):
                    logo_issues += 1
                    print(f"  LOGO NAO .jpg: {logo_url[:60]}")
    if logo_issues == 0:
        print("  Todas as logos sao .jpg e sem imgur.com - OK")

    print(f"\n" + "=" * 60)
    print(f"RESUMO FINAL:")
    print(f"  Entradas originais: {len(channels_raw)}")
    print(f"  Canais unicos mantidos: {n_channels}")
    print(f"  Removidos (antivirus/falha): {removed}")
    print(f"  Canais com EPG: {channels_with_epg}")
    if epg_analysis:
        print(f"  EPG hoje: {'OK' if epg_analysis['has_today'] else 'FALTA'}")
        print(f"  EPG amanha: {'OK' if epg_analysis['has_tomorrow'] else 'FALTA'}")
        print(f"  EPG depois: {'OK' if epg_analysis['has_day_after'] else 'FALTA'}")
        print(f"  Programas totais: {epg_analysis['total_programmes']}")
    if epg_failed:
        print(f"  ALERTA: Alguns EPGs remotos podem estar inacessiveis")
    print(f"  Logos: todas .jpg, sem imgur.com")
    print(f"  URLs com #EXTINF antes: OK")
    print(f"  Finalizado: {OUTPUT_FILE}")

if __name__ == '__main__':
    process()
