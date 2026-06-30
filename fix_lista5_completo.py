#!/usr/bin/env python3
import os, re, shutil, requests, gzip, io, xml.etree.ElementTree as ET
from collections import OrderedDict
from datetime import datetime, timedelta

BASE = "/home/runner/work/JCTVV/JCTVV"
M3U_FILE = f"{BASE}/lista5.m3u"
M3U_BAK = f"{BASE}/lista5.m3u.bak"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

EPG_URLS = [
    "https://raw.githubusercontent.com/gratinomaster/JCTVV/main/lista5_epg.xml",
    "https://raw.githubusercontent.com/gratinomaster/JCTVV/main/EPGFULL.xml.gz",
]

CANALS = OrderedDict([
    ("ABC News Live", {
        "tvg-id": "ABCNewsLive.us",
        "tvg-name": "ABC News Live",
        "tvg-logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
        "group-title": "NEWS WORLD",
        "stream": "https://abcnews-livestreams.akamaized.net/out/v1/6a597119dbd5428a82dc11a2f514a1a2/abcn-live-10-cmaf-manifest/abcn-live-10-index.m3u8",
    }),
    ("Fox News Channel", {
        "tvg-id": "FoxNewsChannel.us",
        "tvg-name": "Fox News Channel",
        "tvg-logo": "https://a57.foxnews.com/static/694940094001/15de0523-3be4-4a9a-8159-7020114e7036/b6ff623a-26d6-4fd9-8bb8-0856adbf38ce/1280x720/match/676/380/image.jpg",
        "group-title": "NEWS WORLD",
        "stream": "https://247.foxnews.com/hls/live/2003586/FNCHLSv3/master.m3u8",
    }),
    ("Fox Business", {
        "tvg-id": "FoxBusiness.us",
        "tvg-name": "Fox Business",
        "tvg-logo": "https://a57.foxnews.com/static/694940094001/c9b2e2eb-7b87-435c-9510-eab2650ff944/8b584585-acf2-4c37-aa07-aaf2d077bb20/1280x720/match/676/380/image.jpg",
        "group-title": "NEWS WORLD",
        "stream": "https://247.foxbusiness.com/hls/live/2003756/FBNHLSv3/master.m3u8",
    }),
    ("CBS News 24/7", {
        "tvg-id": "CBSNews.us",
        "tvg-name": "CBS News 24/7",
        "tvg-logo": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
        "group-title": "NEWS WORLD",
        "stream": "https://dai.google.com/linear/hls/pa/event/Sid4xiTQTkCT1SLu6rjUSQ/stream/65541e9d-bb06-4bdd-9b25-0fe191cb5308:TUL/master.m3u8",
    }),
])

def log(msg):
    print(msg)

def test_url(url):
    try:
        r = requests.get(url, timeout=15, headers={'User-Agent': USER_AGENT}, allow_redirects=True)
        if r.status_code == 200 and url.endswith('.m3u8'):
            return r.content.startswith(b'#EXTM3U') or len(r.content) > 100
        return r.status_code == 200
    except:
        return False

def fix_logo(url):
    if not url or 'imgur.com' in url.lower():
        return None
    url = url.split('?')[0].split('#')[0]
    if url.lower().endswith(('.jpg', '.jpeg')):
        return url
    m = re.match(r'(.*)\.\w+', url)
    if m:
        return m.group(1) + '.jpg'
    return url + '/logo.jpg'

def main():
    log("=" * 70)
    log("CORRECAO FINAL lista5.m3u - EPG + LOGOS + STREAMS")
    log("=" * 70)

    if os.path.exists(M3U_FILE):
        shutil.copy2(M3U_FILE, M3U_BAK)
        log(f"Backup: {M3U_BAK}")

    log("\n[1] Testando streams...")
    for nome, info in CANALS.items():
        ok = test_url(info['stream'])
        log(f"  {nome}: {'OK' if ok else 'FALHOU (protegido/offline, mantido na lista)'}")

    log("\n[2] Gerando M3U corrigido...")
    epg_str = ' '.join(EPG_URLS)
    linhas = [f'#EXTM3U url-tvg="{epg_str}"']

    for nome, info in CANALS.items():
        logo = fix_logo(info['tvg-logo'])
        if not logo:
            logo = info['tvg-logo']

        attrs = f'tvg-id="{info["tvg-id"]}" tvg-name="{info["tvg-name"]}"'
        if logo:
            attrs += f' tvg-logo="{logo}"'
        attrs += f' group-title="{info["group-title"]}"'

        linhas.append(f'#EXTINF:-1 {attrs},{nome}')
        linhas.append(info['stream'])
        log(f"  + {nome} (id={info['tvg-id']})")

    conteudo = '\n'.join(linhas) + '\n'

    with open(M3U_FILE, 'w', encoding='utf-8') as f:
        f.write(conteudo)
    log(f"\n  Salvo: {M3U_FILE} ({len(conteudo)} bytes, {len(linhas)//2} canais)")

    log("\n[3] Verificacao final...")
    erros = 0
    for i, linha in enumerate(conteudo.strip().split('\n')):
        if linha.startswith('#EXTINF:'):
            if 'tvg-id=' not in linha:
                log(f"  ERRO L{i+1}: sem tvg-id"); erros += 1
            logo_m = re.search(r'tvg-logo="([^"]+)"', linha)
            if logo_m:
                l = logo_m.group(1)
                if 'imgur.com' in l.lower():
                    log(f"  ERRO L{i+1}: imgur.com"); erros += 1
                if not l.lower().endswith(('.jpg', '.jpeg')):
                    log(f"  ERRO L{i+1}: logo nao .jpg: {l}"); erros += 1
            else:
                log(f"  ERRO L{i+1}: sem tvg-logo"); erros += 1
        elif linha.startswith('http'):
            if i == 0 or not conteudo.strip().split('\n')[i-1].startswith('#EXTINF:'):
                log(f"  ERRO L{i+1}: URL sem #EXTINF acima"); erros += 1

    if 'url-tvg=' not in linhas[0]:
        log(f"  ERRO: #EXTM3U sem url-tvg"); erros += 1

    log(f"\n  Total: {len(linhas)//2} canais, {erros} erros")
    log("  VERIFICACAO: OK!" if erros == 0 else f"  VERIFICACAO: {erros} problema(s)")

    log("\n[4] Verificando cobertura EPG (hoje/amanha/depois)...")
    hoje = datetime.now().strftime('%Y%m%d')
    amanha = (datetime.now() + timedelta(days=1)).strftime('%Y%m%d')
    depois = (datetime.now() + timedelta(days=2)).strftime('%Y%m%d')

    for epg_url in EPG_URLS:
        try:
            r = requests.get(epg_url, timeout=30, headers={'User-Agent': USER_AGENT})
            if r.status_code != 200: continue
            data = r.content
            if epg_url.endswith('.gz'):
                data = gzip.GzipFile(fileobj=io.BytesIO(data)).read()
            root = ET.fromstring(data)
            programmes = root.findall('programme')
            log(f"  {epg_url.split('/')[-1]}: {len(programmes)} prog")
            for cid in ['ABCNewsLive.us', 'CBSNews.us', 'FoxBusiness.us', 'FoxNewsChannel.us']:
                progs = [p for p in programmes if p.get('channel') == cid]
                c_hoje = sum(1 for p in progs if p.get('start','')[:8] == hoje)
                c_amanha = sum(1 for p in progs if p.get('start','')[:8] == amanha)
                c_depois = sum(1 for p in progs if p.get('start','')[:8] == depois)
                st = 'OK' if (c_hoje>0 and c_amanha>0 and c_depois>0) else 'PARCIAL' if (c_hoje>0 or c_amanha>0) else 'SEM EPG'
                log(f"    {cid}: H={c_hoje} A={c_amanha} D={c_depois} {st}")
        except Exception as e:
            log(f"  Erro {epg_url.split('/')[-1][:30]}: {e}")

    log("\nConcluido!")

if __name__ == "__main__":
    main()
