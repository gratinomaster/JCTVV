#!/usr/bin/env python3
"""
Script completo para corrigir lista5.m3u:
1. Deduplicar canais (manter melhor stream)
2. Adicionar tvg-id, tvg-name, tvg-logo (.jpg)
3. Adicionar x-tvg-url no header
4. Remover canais com URLs expiradas/inacessíveis
5. Testar EPG para hoje, amanhã, depois-de-amanhã
6. Remover imgur.com logos
7. Garantir # na linha antes de cada URL
"""

import re
import os
import sys
import gzip
import hashlib
import subprocess
import urllib.request
import urllib.error
import ssl
from datetime import datetime, timedelta
from io import BytesIO
from collections import OrderedDict

# Configuração
M3U_FILE = "lista5.m3u"
BACKUP_SUFFIX = datetime.now().strftime("%Y%m%d_%H%M%S")
OUTPUT_FILE = M3U_FILE

# Fontes EPG para testar (em ordem de prioridade)
EPG_SOURCES = [
    "https://iptv-epg.org/files/epg-us.xml.gz",
    "https://epg.pw/xmltv/epg_US.xml.gz",
    "https://github.com/iptv-org/epg/raw/master/guide/us.xml.gz",
]

# Mapeamento de canais conhecidos
CHANNEL_MAP = {
    "ABC News Live": {
        "tvg_id": "ABCWBMA.us",
        "tvg_name": "ABC News Live",
        "logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
        "group": "NEWS WORLD",
        "epg_id": "ABCWBMA.us",
    },
    "Fox Business": {
        "tvg_id": "FoxBusiness.us",
        "tvg_name": "Fox Business",
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/c9b2e2eb-7b87-435c-9510-eab2650ff944/8b584585-acf2-4c37-aa07-aaf2d077bb20/1280x720/match/676/380/image.jpg?ve=1&tl=1",
        "group": "NEWS WORLD",
        "epg_id": "FoxBusiness.us",
    },
    "Fox News Channel": {
        "tvg_id": "FoxNewsChannel.us",
        "tvg_name": "Fox News Channel",
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/15de0523-3be4-4a9a-8159-7020114e7036/b6ff623a-26d6-4fd9-8bb8-0856adbf38ce/1280x720/match/676/380/image.jpg?ve=1&tl=1",
        "group": "NEWS WORLD",
        "epg_id": "FoxNewsChannel.us",
    },
    "CBS News 24/7": {
        "tvg_id": "CBSNews.us",
        "tvg_name": "CBS News",
        "logo": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
        "group": "NEWS WORLD",
        "epg_id": "CBSNews.us",
    },
}

# Logo verification - all logos must be .jpg and accessible
LOGO_VERIFICATION = {
    "ABC News Live": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
    "Fox Business": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/c9b2e2eb-7b87-435c-9510-eab2650ff944/8b584585-acf2-4c37-aa07-aaf2d077bb20/1280x720/match/676/380/image.jpg?ve=1&tl=1",
    "Fox News Channel": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/15de0523-3be4-4a9a-8159-7020114e7036/b6ff623a-26d6-4fd9-8bb8-0856adbf38ce/1280x720/match/676/380/image.jpg?ve=1&tl=1",
    "CBS News 24/7": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
}


def parse_m3u(filepath):
    """Parse M3U file into list of channel entries"""
    channels = []
    current_channel = None

    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        if line.startswith('#EXTM3U'):
            i += 1
            continue

        if line.startswith('#EXTINF:'):
            current_channel = {
                'extinf': line,
                'url': '',
                'name': '',
                'group': '',
                'logo': '',
                'tvg_id': '',
                'tvg_name': '',
            }

            # Parse EXTINF
            name_match = re.search(r',(.+)$', line)
            if name_match:
                current_channel['name'] = name_match.group(1).strip()

            group_match = re.search(r'group-title="([^"]*)"', line)
            if group_match:
                current_channel['group'] = group_match.group(1)

            logo_match = re.search(r'tvg-logo="([^"]*)"', line)
            if logo_match:
                current_channel['logo'] = logo_match.group(1)

            tvg_id_match = re.search(r'tvg-id="([^"]*)"', line)
            if tvg_id_match:
                current_channel['tvg_id'] = tvg_id_match.group(1)

            tvg_name_match = re.search(r'tvg-name="([^"]*)"', line)
            if tvg_name_match:
                current_channel['tvg_name'] = tvg_name_match.group(1)

            i += 1
            if i < len(lines):
                url_line = lines[i].strip()
                if url_line and not url_line.startswith('#'):
                    current_channel['url'] = url_line
                    channels.append(current_channel)
            i += 1
            continue

        i += 1

    return channels


def classify_channel(name):
    """Classify a channel into known categories"""
    name_lower = name.lower()

    if 'abc' in name_lower and 'news' in name_lower:
        return 'ABC News Live'
    elif 'fox business' in name_lower or 'foxbusiness' in name_lower:
        return 'Fox Business'
    elif 'fox news' in name_lower or 'foxnews' in name_lower:
        return 'Fox News Channel'
    elif 'cbs' in name_lower and 'news' in name_lower:
        return 'CBS News 24/7'

    return name


def deduplicate_channels(channels):
    """Deduplicate channels, keeping the best stream for each"""
    classified = OrderedDict()

    for ch in channels:
        category = classify_channel(ch['name'])
        if category not in classified:
            classified[category] = []
        classified[category].append(ch)

    result = []
    for category, ch_list in classified.items():
        # Sort by URL quality (prefer master.m3u8, then highest bitrate indicators)
        def url_quality(url):
            score = 0
            if 'master.m3u8' in url:
                score += 100
            if 'cmaf-cenc-ctr-1700K' in url or '1700' in url:
                score += 50
            if 'cmaf-cenc-ctr-2400K' in url or '2400' in url:
                score += 60
            if '1280x720' in url:
                score += 30
            if 'audio-aac' in url:
                score -= 10
            if 'index_3.m3u8' in url or 'index_4_0.m3u8' in url:
                score -= 20
            if '128_complete' in url:
                score -= 30
            # Prefer shorter URLs (likely cleaner)
            score -= len(url) // 100
            return score

        ch_list.sort(key=lambda x: url_quality(x['url']), reverse=True)
        best = ch_list[0]

        # Update with proper metadata
        if category in CHANNEL_MAP:
            meta = CHANNEL_MAP[category]
            best['tvg_id'] = meta['tvg_id']
            best['tvg_name'] = meta['tvg_name']
            best['logo'] = meta['logo']
            best['group'] = meta['group']
            best['name'] = meta['tvg_name']

        result.append(best)

    return result


def fix_logo(logo_url):
    """Ensure logo is valid, remove imgur"""
    if not logo_url:
        return logo_url

    # Remove imgur links
    if 'imgur.com' in logo_url:
        return ''

    return logo_url


def fix_extinf_line(ch):
    """Rebuild EXTINF line with proper attributes"""
    name = ch['name']
    group = ch['group'] or 'NEWS WORLD'
    logo = fix_logo(ch['logo'])
    tvg_id = ch['tvg_id']
    tvg_name = ch['tvg_name'] or name

    # Build the EXTINF line: #EXTINF:-1 attr1 attr2 ...,Name
    attrs = ['#EXTINF:-1']

    if tvg_id:
        attrs.append(f'tvg-id="{tvg_id}"')
    if tvg_name:
        attrs.append(f'tvg-name="{tvg_name}"')
    if logo:
        attrs.append(f'tvg-logo="{logo}"')
    if group:
        attrs.append(f'group-title="{group}"')

    return ' '.join(attrs) + ',' + name


def check_url_accessible(url, timeout=10):
    """Check if a URL is accessible via HEAD request"""
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        req = urllib.request.Request(url, method='HEAD')
        req.add_header('User-Agent', 'Mozilla/5.0')
        response = urllib.request.urlopen(req, timeout=timeout, context=ctx)
        return response.status == 200
    except Exception as e:
        # Try GET as fallback
        try:
            req = urllib.request.Request(url)
            req.add_header('User-Agent', 'Mozilla/5.0')
            response = urllib.request.urlopen(req, timeout=timeout, context=ctx)
            return response.status == 200
        except:
            return False


def download_epg(url, timeout=30):
    """Download EPG XML, handling gzip"""
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'Mozilla/5.0')
        response = urllib.request.urlopen(req, timeout=timeout, context=ctx)
        data = response.read()

        if url.endswith('.gz'):
            data = gzip.decompress(data)

        return data.decode('utf-8', errors='replace')
    except Exception as e:
        print(f"  Erro ao baixar EPG de {url}: {e}")
        return None


def test_epg_for_channel(epg_xml, channel_tvg_id):
    """Test if EPG has programming for today, tomorrow, and day after"""
    if not epg_xml:
        return False, "EPG não disponível"

    today = datetime.now().strftime('%Y%m%d')
    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y%m%d')
    day_after = (datetime.now() + timedelta(days=2)).strftime('%Y%m%d')

    # Check if channel exists in EPG
    channel_pattern = re.compile(rf'channel id="{re.escape(channel_tvg_id)}"', re.IGNORECASE)
    if not channel_pattern.search(epg_xml):
        return False, f"Canal {channel_tvg_id} não encontrado no EPG"

    # Check for programmes today
    today_count = len(re.findall(
        rf'start="{today}\d{{6}} .*".*channel="{re.escape(channel_tvg_id)}"',
        epg_xml
    ))
    tomorrow_count = len(re.findall(
        rf'start="{tomorrow}\d{{6}} .*".*channel="{re.escape(channel_tvg_id)}"',
        epg_xml
    ))
    day_after_count = len(re.findall(
        rf'start="{day_after}\d{{6}} .*".*channel="{re.escape(channel_tvg_id)}"',
        epg_xml
    ))

    has_today = today_count > 0
    has_tomorrow = tomorrow_count > 0
    has_day_after = day_after_count > 0

    if has_today and has_tomorrow and has_day_after:
        return True, f"OK - Hoje: {today_count}, Amanhã: {tomorrow_count}, Depois: {day_after_count}"
    else:
        missing = []
        if not has_today:
            missing.append("hoje")
        if not has_tomorrow:
            missing.append("amanhã")
        if not has_day_after:
            missing.append("depois-de-amanhã")
        return False, f"Falta programação para: {', '.join(missing)}"


def test_virustotal(url, api_key=None):
    """Test URL against VirusTotal"""
    import base64

    # Compute URL ID for VT API v3
    url_id = base64.urlsafe_b64encode(url.encode()).decode().strip("=")

    if api_key:
        # Use API key
        try:
            req = urllib.request.Request(
                f"https://www.virustotal.com/api/v3/urls/{url_id}"
            )
            req.add_header('x-apikey', api_key)
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            response = urllib.request.urlopen(req, timeout=15, context=ctx)
            data = __import__('json').loads(response.read())
            stats = data.get('data', {}).get('attributes', {}).get('last_analysis_stats', {})
            malicious = stats.get('malicious', 0)
            suspicious = stats.get('suspicious', 0)
            if malicious > 0:
                return 'MALICIOUS', f"Malicioso: {malicious}"
            elif suspicious > 0:
                return 'SUSPICIOUS', f"Suspeito: {suspicious}"
            else:
                return 'CLEAN', "Limpo"
        except urllib.error.HTTPError as e:
            if e.code == 404:
                # URL not found, submit for analysis
                try:
                    post_data = __import__('json').dumps({"url": url}).encode()
                    req = urllib.request.Request(
                        "https://www.virustotal.com/api/v3/urls",
                        data=post_data,
                        method='POST'
                    )
                    req.add_header('x-apikey', api_key)
                    req.add_header('Content-Type', 'application/json')
                    response = urllib.request.urlopen(req, timeout=15, context=ctx)
                    return 'SUBMITTED', "Enviado para análise"
                except:
                    return 'UNKNOWN', "Erro ao enviar"
            return 'UNKNOWN', f"Erro HTTP {e.code}"
        except Exception as e:
            return 'UNKNOWN', str(e)
    else:
        # Public API (limited)
        try:
            post_data = __import__('json').dumps({"url": url}).encode()
            req = urllib.request.Request(
                "https://www.virustotal.com/api/v3/urls",
                data=post_data,
                method='POST'
            )
            req.add_header('Content-Type', 'application/json')
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            response = urllib.request.urlopen(req, timeout=15, context=ctx)
            data = __import__('json').loads(response.read())
            analysis_link = data.get('data', {}).get('links', {}).get('self', '')
            if analysis_link:
                # Wait and poll
                import time
                time.sleep(3)
                req2 = urllib.request.Request(analysis_link)
                response2 = urllib.request.urlopen(req2, timeout=15, context=ctx)
                data2 = __import__('json').loads(response2.read())
                stats = data2.get('data', {}).get('attributes', {}).get('last_analysis_stats', {})
                malicious = stats.get('malicious', 0)
                suspicious = stats.get('suspicious', 0)
                if malicious > 0:
                    return 'MALICIOUS', f"Malicioso: {malicious}"
                elif suspicious > 0:
                    return 'SUSPICIOUS', f"Suspeito: {suspicious}"
                else:
                    return 'CLEAN', "Limpo"
            return 'UNKNOWN', "Sem resultado"
        except Exception as e:
            return 'UNKNOWN', str(e)


def generate_m3u(channels, epg_url):
    """Generate the fixed M3U file"""
    lines = []
    lines.append(f'#EXTM3U x-tvg-url="{epg_url}"')

    for ch in channels:
        extinf = fix_extinf_line(ch)
        lines.append(extinf)
        lines.append(ch['url'])

    return '\n'.join(lines) + '\n'


def main():
    print("=" * 60)
    print("CORREÇÃO COMPLETA DA lista5.m3u")
    print("=" * 60)

    # 1. Backup
    backup_file = f"{M3U_FILE}.bak.{BACKUP_SUFFIX}"
    if os.path.exists(M3U_FILE):
        with open(M3U_FILE, 'r') as f:
            content = f.read()
        with open(backup_file, 'w') as f:
            f.write(content)
        print(f"[1] Backup criado: {backup_file}")

    # 2. Parse
    print("\n[2] Parseando M3U...")
    channels = parse_m3u(M3U_FILE)
    print(f"    Total de entradas: {len(channels)}")

    # 3. Deduplicate
    print("\n[3] Deduplicando canais...")
    unique_channels = deduplicate_channels(channels)
    print(f"    Canais únicos: {len(unique_channels)}")
    for ch in unique_channels:
        print(f"    - {ch['name']} ({ch['tvg_id']})")

    # 4. Fix logos and verify
    print("\n[4] Verificando logos...")
    for ch in unique_channels:
        # Ensure logo is from verification list
        category = classify_channel(ch['name'])
        if category in LOGO_VERIFICATION:
            expected_logo = LOGO_VERIFICATION[category]
            if ch['logo'] != expected_logo:
                print(f"    Logo atualizado: {ch['name']}")
                ch['logo'] = expected_logo

        # Check if logo is .jpg (check path, not query params)
        if ch['logo']:
            logo_path = ch['logo'].split('?')[0]
            if not logo_path.endswith('.jpg') and not logo_path.endswith('.jpeg'):
                print(f"    AVISO: Logo não é .jpg: {ch['name']} ({ch['logo']})")

        # Check if logo contains imgur
        if 'imgur.com' in ch['logo']:
            print(f"    ERRO: Logo contém imgur: {ch['name']} - REMOVENDO")
            ch['logo'] = ''

        # Test logo accessibility
        if ch['logo']:
            print(f"    Testando logo {ch['name']}...", end=" ")
            accessible = check_url_accessible(ch['logo'], timeout=5)
            if accessible:
                print("OK")
            else:
                print("INACESSÍVEL")

    # Verify all logos end with .jpg
    for ch in unique_channels:
        if ch['logo']:
            logo_path = ch['logo'].split('?')[0]
            if not logo_path.endswith('.jpg') and not logo_path.endswith('.jpeg'):
                print(f"    AVISO: Logo não é .jpg: {ch['name']}")
                # For now, keep as-is since we can't convert images server-side
                # The user will need to find a .jpg version if needed

    # 5. Test stream URLs
    print("\n[5] Testando URLs dos canais...")
    accessible_channels = []
    for ch in unique_channels:
        url = ch['url']
        print(f"    Testando {ch['name']}...", end=" ")
        accessible = check_url_accessible(url, timeout=8)
        if accessible:
            print("ACESSÍVEL")
            accessible_channels.append(ch)
        else:
            print("INACESSÍVEL - removido")

    # 6. Test EPG sources
    print("\n[6] Testando fontes EPG...")
    working_epg = None
    epg_data = None

    for epg_url in EPG_SOURCES:
        print(f"\n    Testando: {epg_url}")
        data = download_epg(epg_url, timeout=30)
        if data:
            print(f"    Tamanho: {len(data)} bytes")
            # Test for each channel
            all_ok = True
            for ch in accessible_channels:
                tvg_id = ch['tvg_id']
                if tvg_id:
                    ok, msg = test_epg_for_channel(data, tvg_id)
                    status = "✓" if ok else "✗"
                    print(f"      {ch['name']}: {status} {msg}")
                    if not ok:
                        all_ok = False
            if all_ok:
                working_epg = epg_url
                epg_data = data
                print(f"    EPG FUNCIONAL: {epg_url}")
                break
        else:
            print(f"    FALHOU")

    if not working_epg:
        print("\n    AVISO: Nenhuma fonte EPG completa encontrada")
        print("    Usando melhor fonte disponível...")
        for epg_url in EPG_SOURCES:
            data = download_epg(epg_url, timeout=30)
            if data:
                working_epg = epg_url
                epg_data = data
                break

    # 7. VirusTotal test (optional, requires API key)
    print("\n[7] Teste VirusTotal...")
    vt_api_key = os.environ.get('VT_API_KEY', '')
    if vt_api_key:
        print("    API Key encontrada, testando...")
        safe_channels = []
        for ch in accessible_channels:
            status, msg = test_virustotal(ch['url'], vt_api_key)
            print(f"    {ch['name']}: {status} - {msg}")
            if status in ('CLEAN', 'SUBMITTED', 'UNKNOWN'):
                safe_channels.append(ch)
            else:
                print(f"      REMOVIDO: {ch['name']}")
            import time
            time.sleep(1.5)
        accessible_channels = safe_channels
    else:
        print("    Sem API Key - pulando teste VT")
        print("    Para testar, defina: export VT_API_KEY=sua_chave")

    # 8. Generate output
    print("\n[8] Gerando arquivo corrigido...")
    if working_epg:
        m3u_content = generate_m3u(accessible_channels, working_epg)
    else:
        m3u_content = generate_m3u(accessible_channels, "")

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(m3u_content)

    print(f"\n    Arquivo salvo: {OUTPUT_FILE}")
    print(f"    Canais finais: {len(accessible_channels)}")

    # 9. Summary
    print("\n" + "=" * 60)
    print("RESUMO")
    print("=" * 60)
    print(f"Entradas originais: {len(channels)}")
    print(f"Canais únicos: {len(unique_channels)}")
    print(f"Canais acessíveis: {len(accessible_channels)}")
    print(f"EPG: {working_epg or 'NENHUM'}")
    print(f"Backup: {backup_file}")

    # 10. Verify EPG
    if epg_data and working_epg:
        print("\n[9] Verificação final do EPG:")
        for ch in accessible_channels:
            tvg_id = ch['tvg_id']
            if tvg_id:
                ok, msg = test_epg_for_channel(epg_data, tvg_id)
                status = "✓" if ok else "✗"
                print(f"    {ch['name']}: {status} {msg}")

    print("\nConcluído!")


if __name__ == '__main__':
    main()
