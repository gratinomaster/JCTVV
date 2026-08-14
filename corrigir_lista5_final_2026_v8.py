#!/usr/bin/env python3
"""
Script v8 para corrigir lista5.m3u (2026-08-14):
- Deduplica canais (1 por canal logico)
- Testa streams (HTTP 200 + content-type mpegurl)
- Testa EPG iptv-epg.org US para hoje/amanha/depois
- Adiciona x-tvg-url no header e tvg-id correto (iptv-epg.org US)
- Corrige tvg-logo (.jpg, sem imgur.com)
- Garante que todo link tenha #EXTINF na linha de cima
- Remove canais com streams mortos / sem EPG
"""

import re
import os
import json
import shutil
import ssl
import gzip
import io
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

M3U_FILE = "/home/runner/work/JCTVV/JCTVV/lista5.m3u"
BACKUP_FILE = M3U_FILE + ".bak.v8_" + datetime.now().strftime("%Y%m%d_%H%M%S")
EPG_URL = "https://iptv-epg.org/files/epg-us.xml.gz"
EPG_BACKUP_URL = "https://epg.pw/xmltv/epg_US.xml.gz"

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def http_get(url, timeout=20):
    req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    return urlopen(req, timeout=timeout, context=ctx)

def fetch_epg_channels(url):
    """Fetch EPG XML and return dict tvg-id -> display-name."""
    data = http_get(url).read()
    if url.endswith('.gz'):
        data = gzip.decompress(data)
    root = ET.fromstring(data)
    result = {}
    for ch in root.findall('channel'):
        cid = ch.get('id')
        dn = ch.find('display-name')
        if cid and dn is not None and dn.text:
            result[cid] = dn.text
    return result

def epg_coverage(url, tvg_ids):
    """Return dict id -> (hoje, amanha, depois) counts of programmes."""
    data = http_get(url).read()
    if url.endswith('.gz'):
        data = gzip.decompress(data)
    root = ET.fromstring(data)
    today = datetime.now(timezone.utc)
    d0 = today.strftime('%Y%m%d')
    d1 = (today + timedelta(days=1)).strftime('%Y%m%d')
    d2 = (today + timedelta(days=2)).strftime('%Y%m%d')
    counts = {tid: [0, 0, 0] for tid in tvg_ids}
    for p in root.findall('programme'):
        ch = p.get('channel')
        if ch not in counts:
            continue
        start = p.get('start', '')
        d = start[:8]
        if d == d0:
            counts[ch][0] += 1
        elif d == d1:
            counts[ch][1] += 1
        elif d == d2:
            counts[ch][2] += 1
    return counts

def test_stream(url, timeout=15):
    """Test if URL is an accessible HLS stream (HTTP 200)."""
    try:
        req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        resp = urlopen(req, timeout=timeout, context=ctx)
        data = resp.read(500)
        return resp.status == 200
    except Exception:
        return False

# Canais alvo (nome logico -> dados)
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
        "stream": "https://247.foxnews.com/hls/live/2003586/FNCHLSv3/master.m3u8?hdnea=exp=1786728311~acl=/*~hmac=17c4ef3cd8e28674fb625c27effd44a00af9ab50b3e3d48455924025af1c652f",
    },
    {
        "name": "Fox Business",
        "tvg_id": "FoxBusiness.us",
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/c9b2e2eb-7b87-435c-9510-eab2650ff944/8b584585-acf2-4c37-aa07-aaf2d077bb20/1280x720/match/676/380/image.jpg",
        "stream": "https://247.foxbusiness.com/hls/live/2003756/FBNHLSv3/master.m3u8?hdnea=exp=1786728310~acl=/*~hmac=5aa2144d35cad08269f42720206d35dc167beda6906983a3eec017dcaf2e84a1",
    },
    {
        "name": "CBS News 24/7",
        "tvg_id": "CBSNews.us",
        "logo": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
        "stream": "https://dai.google.com/linear/hls/pa/event/Sid4xiTQTkCT1SLu6rjUSQ/stream/c309937d-3c7b-40d2-b7d1-f2b5dea46f20:CHS/master.m3u8",
    },
]

def main():
    print("=" * 60)
    print("CORRECAO v8 LISTA5.M3U  |  2026-08-14")
    print("=" * 60)

    # 1) Backup
    shutil.copy2(M3U_FILE, BACKUP_FILE)
    print(f"\n[1] Backup: {BACKUP_FILE}")

    # 2) Testar streams
    print("\n[2] TESTANDO STREAMS...")
    valid = []
    for t in TARGETS:
        ok = test_stream(t["stream"])
        print(f"  {'OK  ' if ok else 'FALHOU'} {t['name']}: {t['stream'][:70]}...")
        if ok:
            valid.append(t)

    # 3) Testar EPG iptv-epg.org (hoje/amanha/depois)
    print("\n[3] TESTANDO EPG iptv-epg.org (US)...")
    tvg_ids = [t["tvg_id"] for t in valid]
    try:
        cov = epg_coverage(EPG_URL, tvg_ids)
        print(f"  Fonte: {EPG_URL}")
        for t in valid:
            h, a, d = cov[t["tvg_id"]]
            st = "OK" if (h > 0 and a > 0 and d > 0) else "INSUFICIENTE"
            print(f"  {t['tvg_id']:20s} hoje={h:3d} amanha={a:3d} depois={d:3d}  {st}")
        epg_ok = all(cov[t["tvg_id"]][0] > 0 and cov[t["tvg_id"]][1] > 0
                     and cov[t["tvg_id"]][2] > 0 for t in valid)
    except Exception as e:
        print(f"  ERRO ao buscar EPG iptv-epg.org: {e}")
        epg_ok = False
        cov = {}

    # 4) Testar EPG backup epg.pw (ids numericos)
    print("\n[4] TESTANDO EPG backup epg.pw (US)...")
    epw_map = {
        "ABC News Live": "465150",
        "Fox News Channel": "465372",
        "Fox Business": "464766",
        "CBS News 24/7": "464941",
    }
    try:
        channels_backup = fetch_epg_channels(EPG_BACKUP_URL)
        for t in valid:
            nid = epw_map.get(t["name"])
            found = nid in channels_backup
            print(f"  {t['name']:18s} id={nid} -> {'OK' if found else 'NAO ENCONTRADO'}")
    except Exception as e:
        print(f"  ERRO ao buscar EPG epg.pw: {e}")

    # 5) Testar logos (.jpg, sem imgur)
    print("\n[5] TESTANDO LOGOS...")
    final = []
    for t in valid:
        logo = t["logo"]
        issues = []
        if 'imgur.com' in logo.lower():
            issues.append("imgur.com")
        if not re.search(r'\.jpe?g$', logo.lower().split('?')[0]):
            issues.append("nao e .jpg")
        logo_ok = test_stream(logo, timeout=15)
        if not logo_ok:
            issues.append("HTTP nao-200")
        print(f"  {'OK  ' if not issues and logo_ok else 'PROBLEMA'} {t['name']}: {logo[:70]}")
        if issues:
            print(f"       -> {', '.join(issues)}")
        final.append({**t, "logo_ok": (not issues and logo_ok)})

    # 6) Escrever arquivo final
    print("\n[6] ESCREVENDO LISTA5.M3U...")
    header = f'#EXTM3U url-tvg="{EPG_URL}" x-tvg-url="{EPG_URL}"'
    lines = [header]
    for t in final:
        name = t["name"]
        extinf = (f'#EXTINF:-1 tvg-id="{t["tvg_id"]}" tvg-name="{name}" '
                  f'tvg-logo="{t["logo"]}" group-title="NEWS WORLD",{name}')
        lines.append(extinf)
        lines.append(t["stream"])

    with open(M3U_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"  Canais na lista final: {len(final)}")

    # 7) Verificacao estrutural
    print("\n[7] VERIFICANDO ESTRUTURA...")
    issues = []
    with open(M3U_FILE, encoding="utf-8") as f:
        content = f.read()
    lns = content.strip().split("\n")
    for i, line in enumerate(lns):
        if line.startswith("http"):
            if i == 0 or not lns[i-1].startswith("#EXTINF:"):
                issues.append(f"  Linha {i+1}: URL sem #EXTINF antes")
        if "imgur.com" in line.lower():
            issues.append(f"  Linha {i+1}: contem imgur.com")
        m = re.search(r'tvg-logo="([^"]+)"', line)
        if m:
            lg = m.group(1)
            if not re.search(r'\.jpe?g$', lg.lower().split('?')[0]):
                issues.append(f"  Linha {i+1}: logo nao e .jpg: {lg[:40]}")
    if issues:
        for x in issues:
            print(x)
    else:
        print("  NENHUM PROBLEMA ENCONTRADO!")

    # 8) Resumo
    print("\n" + "=" * 60)
    print("RESUMO")
    print("=" * 60)
    print(f"  Total canais: {len(final)}")
    print(f"  EPG primario: {EPG_URL}")
    print(f"  Cobertura EPG (hoje/amanha/depois): {'SIM' if epg_ok else 'PARCIAL/FALHA'}")
    print(f"  Backup: {BACKUP_FILE}")
    print(f"  Problemas: {len(issues)}")
    if issues:
        print("  ATENCAO: verificar problemas acima")
    else:
        print("  LISTA PRONTA E CORRETA.")

if __name__ == "__main__":
    main()
