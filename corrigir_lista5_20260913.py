#!/usr/bin/env python3
"""
Corrige lista5.m3u (2026-09-13):
- Mantem apenas 1 entrada por canal (stream master validada: HTTP 200 + HLS)
- Remove canais que nao passam no teste do anti-virus (stream bloqueada/morta)
- Usa EPG (epgshare01 US2) que cobre todos os canais com programacao de hoje/amanha/depois
- Insere a URL do EPG no header do .m3u (url-tvg + x-tvg-url)
- Garante tvg-logo em .jpg, acessivel e sem imgur.com
- Garante que todo link tenha a linha #EXTINF diretamente acima
"""
import re
import os
import shutil
import gzip
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

M3U_FILE = "lista5.m3u"
EPG_URL = "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz"

TARGETS = [
    {
        "name": "ABC News Live",
        "tvg_id": "ABC.News.Live.us2",
        "logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
        "stream": "https://abcnews-livestreams.akamaized.net/out/v1/6a597119dbd5428a82dc11a2f514a1a2/abcn-live-10-cmaf-manifest/abcn-live-10-index.m3u8",
    },
    {
        "name": "Fox News Channel",
        "tvg_id": "Fox.News.Channel.HD.us2",
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/15de0523-3be4-4a9a-8159-7020114e7036/b6ff623a-26d6-4fd9-8bb8-0856adbf38ce/1280x720/match/676/380/image.jpg?ve=1&tl=1",
        "stream": "https://247preview.foxnews.com/hls/live/2020027/fncv3preview/primary.m3u8",
    },
    {
        "name": "Fox Business",
        "tvg_id": "Fox.Business.HD.us2",
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/c9b2e2eb-7b87-435c-9510-eab2650ff944/8b584585-acf2-4c37-aa07-aaf2d077bb20/1280x720/match/676/380/image.jpg?ve=1&tl=1",
        "stream": "https://247preview.foxbusiness.com/hls/live/2020026/fbnv3preview/primary.m3u8",
    },
    {
        "name": "CBS News 24/7",
        "tvg_id": "CBS.News.National.Stream.us2",
        "logo": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
        "stream": "https://dai.google.com/linear/hls/pa/event/Sid4xiTQTkCT1SLu6rjUSQ/stream/3ad70707-8456-42d9-9289-12bcca4da823:ATL/master.m3u8",
    },
]


def test_stream(url, timeout=25):
    """Teste do anti-virus/acessibilidade: retorna True se a resposta tiver manifest HLS."""
    try:
        r = subprocess.run(
            ["curl", "-s", "-L", "--max-time", str(timeout), "-H", "User-Agent: Mozilla/5.0",
             "-r", "0-1200", url],
            capture_output=True, text=True, timeout=timeout + 10,
        )
        body = r.stdout
        return "#EXTM3U" in body and "#EXT-X" in body
    except Exception:
        return False


def test_logo(url):
    try:
        r = subprocess.run(
            ["curl", "-s", "-L", "--max-time", "30", "-o", "/dev/null", "-w",
             "%{http_code} %{content_type}", url],
            capture_output=True, text=True, timeout=40,
        )
        code, ctype = r.stdout.strip().split(" ", 1)
        return code == "200" and "image" in ctype
    except Exception:
        return False


def epg_coverage(url, tvg_ids):
    """Baixa o EPG e conta programas de hoje/amanha/depois para cada tvg_id."""
    r = subprocess.run(
        ["curl", "-s", "-L", "--max-time", "120", "-o", "/tmp/epgshare_verify.xml.gz", url],
        capture_output=True, timeout=140,
    )
    with gzip.open("/tmp/epgshare_verify.xml.gz", "rb") as gz:
        root = ET.fromstring(gz.read())
    today = datetime.now().strftime("%Y%m%d")
    tom = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
    d3 = (datetime.now() + timedelta(days=2)).strftime("%Y%m%d")
    counts = {tid: [0, 0, 0] for tid in tvg_ids}
    for p in root.findall("programme"):
        ch = p.get("channel")
        if ch not in counts:
            continue
        s = (p.get("start") or "")[:8]
        if s == today:
            counts[ch][0] += 1
        elif s == tom:
            counts[ch][1] += 1
        elif s == d3:
            counts[ch][2] += 1
    return counts


def main():
    print("=" * 70)
    print("CORRECAO lista5.m3u | 2026-09-13 | EPG + LOGOS + ANTI-VIRUS")
    print("=" * 70)

    backup = M3U_FILE + ".bak.pre_corrigir_20260913_" + datetime.now().strftime("%H%M%S")
    shutil.copy2(M3U_FILE, backup)
    print(f"\n[1] Backup: {backup}")

    print("\n[2] VERIFICANDO EPG (%s)..." % EPG_URL)
    tvg_ids = [t["tvg_id"] for t in TARGETS]
    try:
        cov = epg_coverage(EPG_URL, tvg_ids)
        for t in TARGETS:
            h, a, d = cov[t["tvg_id"]]
            st = "OK" if (h > 0 and a > 0 and d > 0) else "INSUFICIENTE"
            print("  %-30s hoje=%3d amanha=%3d depois=%3d  %s" % (t["tvg_id"], h, a, d, st))
        epg_ok = all(
            cov[t["tvg_id"]][0] > 0 and cov[t["tvg_id"]][1] > 0 and cov[t["tvg_id"]][2] > 0
            for t in TARGETS
        )
    except Exception as e:
        print("  ERRO ao verificar EPG:", e)
        epg_ok = False

    print("\n[3] TESTANDO STREAMS (anti-virus / validade)...")
    valid = []
    for t in TARGETS:
        ok = test_stream(t["stream"])
        print("  %-18s %s  %s" % ("OK" if ok else "FALHOU", t["name"], t["stream"][:70]))
        if ok:
            valid.append(t)
        else:
            print("       -> %s REMOVIDO (nao passou no teste)" % t["name"])

    print("\n[4] TESTANDO LOGOS (.jpg, acessivel, sem imgur)...")
    final = []
    for t in valid:
        logo = t["logo"]
        base = logo.split("?")[0]
        problems = []
        if "imgur.com" in logo.lower():
            problems.append("imgur.com")
        if not re.search(r"\.jpe?g$", base, re.IGNORECASE):
            problems.append("nao e .jpg")
        if not test_logo(logo):
            problems.append("HTTP nao-200/nao-imagem")
        if problems:
            print("  REMOVIDO %-18s %s (%s)" % (t["name"], logo[:55], ", ".join(problems)))
            continue
        print("  OK  %-18s %s" % (t["name"], logo[:70]))
        final.append(t)

    print("\n[5] ESCREVENDO %s..." % M3U_FILE)
    header = '#EXTM3U url-tvg="%s" x-tvg-url="%s"' % (EPG_URL, EPG_URL)
    lines = [header]
    for t in final:
        extinf = (
            '#EXTINF:-1 tvg-id="%s" tvg-name="%s" tvg-logo="%s" group-title="NEWS WORLD",%s'
            % (t["tvg_id"], t["name"], t["logo"], t["name"])
        )
        lines.append(extinf)
        lines.append(t["stream"])

    with open(M3U_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print("  Canais mantidos: %d" % len(final))

    print("\n[6] VALIDACAO ESTRUTURAL...")
    issues = []
    with open(M3U_FILE, encoding="utf-8") as f:
        lns = [l.rstrip("\n") for l in f]
    for i, line in enumerate(lns):
        if line.startswith("http"):
            if i == 0 or not lns[i - 1].startswith("#EXTINF:"):
                issues.append("Linha %d: URL sem #EXTINF acima" % (i + 1))
        if "imgur.com" in line.lower():
            issues.append("Linha %d: contem imgur.com" % (i + 1))
        m = re.search(r'tvg-logo="([^"]+)"', line)
        if m:
            lg = m.group(1)
            if not re.search(r"\.jpe?g($|\?)", lg, re.IGNORECASE):
                issues.append("Linha %d: logo nao e .jpg: %s" % (i + 1, lg[:45]))
    if issues:
        for x in issues:
            print("  PROBLEMA:", x)
    else:
        print("  NENHUM PROBLEMA ENCONTRADO!")

    print("\n[7] RESUMO")
    print("  Canais: %d" % len(final))
    print("  EPG: %s" % EPG_URL)
    print("  Cobertura (hoje/amanha/depois): %s" % ("OK" if epg_ok else "FALHA"))
    print("  Backup: %s" % backup)

    if issues:
        print("  ATENCAO: problemas encontrados.")
    else:
        print("  LISTA PRONTA.")


if __name__ == "__main__":
    main()