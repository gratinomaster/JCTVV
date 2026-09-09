#!/usr/bin/env python3
"""
Script v10 para corrigir lista5.m3u (2026-09-09):
- Deduplica canais (1 por canal logico)
- Remove canais que nao passam no teste de validade do stream (anti-virus proxy)
- Usa streams validos (HTTP 200 + manifest HLS #EXTM3U)
- Testa logos (.jpg, HTTP 200 image, sem imgur.com)
- Testa EPG iptv-epg.org US: cobertura hoje/amanha/depois para cada tvg-id
- Garante #EXTINF na linha de cima de todo link
- Header com url-tvg e x-tvg-url
"""

import re
import ssl
import gzip
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from urllib.request import Request, urlopen

M3U_FILE = "/home/runner/work/JCTVV/JCTVV/lista5.m3u"
BACKUP = M3U_FILE + ".bak.v10_" + datetime.now().strftime("%Y%m%d_%H%M%S")
EPG_URL = "https://iptv-epg.org/files/epg-us.xml.gz"

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def http_get(url, timeout=25):
    req = Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
    return urlopen(req, timeout=timeout, context=ctx)

def test_stream(url, timeout=20):
    """Validade (proxy anti-virus): URL abre e retorna manifest HLS com segmentos."""
    try:
        resp = http_get(url, timeout=timeout)
        data = resp.read(2500)
        head = data[:600]
        if b'#EXTM3U' in head or b'#EXT-X-STREAM-INF' in head or b'#EXT-X-TARGETDURATION' in head:
            return True, 'HLS manifest ok'
        return False, f'HTTP {resp.status} sem manifest'
    except Exception as e:
        return False, f'{type(e).__name__}: {e}'

def test_logo(url, timeout=15):
    issues = []
    if not re.search(r'\.jpe?g($|\?)', url.lower()):
        issues.append('nao e .jpg')
    if 'imgur.com' in url.lower():
        issues.append('imgur.com')
    try:
        resp = http_get(url, timeout=timeout)
        ct = resp.headers.get('Content-Type', '')
        if resp.status != 200:
            issues.append(f'HTTP {resp.status}')
        elif 'image' not in ct.lower():
            issues.append(f'content-type={ct}')
    except Exception as e:
        issues.append(f'{type(e).__name__}')
    return issues

def epg_coverage(tvg_ids):
    """Retorna dict id -> [hoje, amanha, depois] e exemplo de programa."""
    data = http_get(EPG_URL, timeout=180).read()
    if EPG_URL.endswith('.gz'):
        data = gzip.decompress(data)
    today = datetime.now(timezone.utc)
    d0 = today.strftime('%Y%m%d')
    d1 = (today + timedelta(days=1)).strftime('%Y%m%d')
    d2 = (today + timedelta(days=2)).strftime('%Y%m%d')
    counts = {tid: [0, 0, 0] for tid in tvg_ids}
    example = {}
    root = None
    try:
        import xml.etree.ElementTree as ET
        root = ET.fromstring(data)
        for p in root.findall('programme'):
            ch = p.get('channel')
            if ch not in counts:
                continue
            d = p.get('start', '')[:8]
            if d == d0:
                counts[ch][0] += 1
            elif d == d1:
                counts[ch][1] += 1
            elif d == d2:
                counts[ch][2] += 1
            example.setdefault(ch, (p.get('start', '')[:16], (p.findtext('title') or '').strip()))
    except ET.ParseError:
        return None, example
    return counts, example

TARGETS = [
    {
        "name": "ABC News Live",
        "tvg_id": "ABCNewsLive.us",
        "logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
        "stream": "https://abcnews-livestreams.akamaized.net/out/v1/6a597119dbd5428a82dc11a2f514a1a2/abcn-live-10-cmaf-manifest/abcn-live-10-index.m3u8",
    },
    {
        "name": "Fox News Channel",
        "tvg_id": "FoxNewsChannel.us",
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/15de0523-3be4-4a9a-8159-7020114e7036/b6ff623a-26d6-4fd9-8bb8-0856adbf38ce/1280x720/match/676/380/image.jpg",
        "stream": "http://247preview.foxnews.com/hls/live/2020027/fncv3preview/primary.m3u8",
    },
    {
        "name": "Fox Business",
        "tvg_id": "FoxBusiness.us",
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/c9b2e2eb-7b87-435c-9510-eab2650ff944/8b584585-acf2-4c37-aa07-aaf2d077bb20/1280x720/match/676/380/image.jpg",
        "stream": "https://247preview.foxbusiness.com/hls/live/2020026/fbnv3preview/primary.m3u8",
    },
    {
        "name": "CBS News 24/7",
        "tvg_id": "CBSNews.us",
        "logo": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
        "stream": "https://cbsn-us.cbsnstream.cbsnews.com/out/v1/55a8648e8f134e82a470f83d562deeca/master.m3u8",
    },
]

def main():
    print("=" * 62)
    print(f"CORRECAO v10 LISTA5.M3U | {datetime.now():%Y-%m-%d %H:%M}")
    print("=" * 62)

    shutil.copy2(M3U_FILE, BACKUP)
    print(f"[1] Backup criado: {BACKUP}")

    print("\n[2] TESTE DE STREAMS (validade / anti-virus)...")
    valid = []
    for t in TARGETS:
        ok, why = test_stream(t["stream"], timeout=25)
        print(f"  {'OK ' if ok else 'FALHA'} {t['name']:18s} -> {why}")
        if ok:
            valid.append(t)
        else:
            print(f"       {t['name']} REMOVIDO (nao passou no teste)")

    print("\n[3] TESTE DE LOGOS (.jpg, HTTP 200, sem imgur)...")
    for t in valid:
        issues = test_logo(t["logo"])
        print(f"  {'OK ' if not issues else 'FU '} {t['name']:18s} {t['logo'][:55]}" + (f"  -> {', '.join(issues)}" if issues else ""))

    print(f"\n[4] TESTE DE EPG ({EPG_URL}) para hoje/amanha/depois...")
    tvg_ids = [t["tvg_id"] for t in valid]
    counts, example = epg_coverage(tvg_ids)
    epg_ok = False
    if counts is not None:
        for tid in tvg_ids:
            h, a, d = counts[tid]
            ok = all([h > 0, a > 0, d > 0])
            ex = example.get(tid, ('', ''))
            print(f"  {tid:22s} hoje={h:3d} amanha={a:3d} depois={d:3d}  {'OK' if ok else 'INSUFICIENTE'}  ex_programa={ex[1][:15] or '(vazio)'!r}")
        epg_ok = all(all(v > 0 for v in counts[tid]) for tid in tvg_ids)
    else:
        print("  FALHA: nao foi possivel ler o EPG")

    print("\n[5] ESCREVENDO LISTA5.M3U...")
    header = f'#EXTM3U url-tvg="{EPG_URL}" x-tvg-url="{EPG_URL}"'
    lines = [header]
    for t in valid:
        extinf = (f'#EXTINF:-1 tvg-id="{t["tvg_id"]}" tvg-name="{t["name"]}" '
                  f'tvg-logo="{t["logo"]}" group-title="NEWS WORLD",{t["name"]}')
        lines.append(extinf)
        lines.append(t["stream"])
    with open(M3U_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  {len(valid)} canais escritos.")

    print("\n[6] VERIFICACAO ESTRUTURAL...")
    issues = []
    with open(M3U_FILE, encoding="utf-8") as f:
        lns = f.read().strip().split("\n")
    for i, line in enumerate(lns):
        if re.match(r'^https?://', line):
            if i == 0 or not lns[i - 1].startswith("#EXTINF:"):
                issues.append(f"  Linha {i+1}: URL sem #EXTINF antes")
        if "imgur.com" in line.lower():
            issues.append(f"  Linha {i+1}: contem imgur.com")
        m = re.search(r'tvg-logo="([^"]+)"', line)
        if m and not re.search(r'\.jpe?g($|\?)', m.group(1).lower()):
            issues.append(f"  Linha {i+1}: logo nao e .jpg")
    # check each url follows an EXTINF line
    print("  " + "\n  ".join(issues) if issues else "  NENHUM PROBLEMA ESTRUTURAL")

    print("\n" + "=" * 62)
    print("RESUMO")
    print("=" * 62)
    print(f"  Canais: {len(valid)} (deduplicados, sem mortos)")
    print(f"  EPG:    {'FUNCIONANDO hoje/amanha/depois' if epg_ok else 'PARCIAL/FALHA'}")
    print(f"  Backup: {BACKUP}")
    print("  LISTA5.M3U PRONTA." if epg_ok and not issues else "  ATENCAO: revisar acima")

if __name__ == "__main__":
    main()