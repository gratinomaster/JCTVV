#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Corrige lista5.m3u: EPG valido/atualizado, streams testados, logos .jpg,
anti-virus (reputacao de dominio), formato EXTINF correto, sem imgur."""
import os, re, gzip, io, ssl, sys, json
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

BASE = "/home/runner/work/JCTVV/JCTVV"
M3U_FILE = os.path.join(BASE, "lista5.m3u")
REPORT = os.path.join(BASE, "relatorio_lista5.txt")

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

EPG_URL = "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz"
EPG_BACKUP_URL = "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz"

BAD_DOMAINS = ["imgur.com", "bit.ly", "tinyurl.com", "is.gd", "goo.gl", "t.co", "adf.ly"]

CHANNELS = [
    {
        "name": "ABC News Live",
        "tvg_id": "ABC.News.Live.us2",
        "tvg_name": "ABC News Live",
        "group": "NEWS WORLD",
        "logo": "https://keyframe-cdn.abcnews.com/streamprovider10.jpg",
        "url": "https://abcnews-livestreams.akamaized.net/out/v1/6a597119dbd5428a82dc11a2f514a1a2/abcn-live-10-cmaf-manifest/abcn-live-10-index.m3u8",
    },
    {
        "name": "Fox News Channel",
        "tvg_id": "Fox.News.Channel.HD.us2",
        "tvg_name": "Fox News Channel",
        "group": "NEWS WORLD",
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/01d1a249-0905-483d-9a43-4f0bee1eae5f/b5809b25-d315-4076-8601-251257d5a58f/1280x720/match/390/219/image.jpg",
        "url": "https://247preview.foxnews.com/hls/live/2020027/fncv3preview/primary.m3u8",
    },
    {
        "name": "Fox Business",
        "tvg_id": "Fox.Business.HD.us2",
        "tvg_name": "Fox Business",
        "group": "NEWS WORLD",
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/c9b2e2eb-7b87-435c-9510-eab2650ff944/8b584585-acf2-4c37-aa07-aaf2d077bb20/1280x720/match/676/380/image.jpg",
        "url": "https://247preview.foxbusiness.com/hls/live/2020026/fbnv3preview/primary.m3u8",
    },
    {
        "name": "CBS News 24/7",
        "tvg_id": "CBS.News.National.Stream.us2",
        "tvg_name": "CBS News 24/7",
        "group": "NEWS WORLD",
        "logo": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
        "url": "https://cbsn-us.cbsnstream.cbsnews.com/out/v1/55a8648e8f134e82a470f83d562deeca/master.m3u8",
    },
]


def http_get(url, timeout=45, binary=True):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
        final = r.geturl()
    return r.status, data, final


def test_stream(url):
    try:
        status, data, _ = http_get(url)
        head = data[:300].decode("utf-8", "replace").lstrip()
        if status < 400 and head.startswith(("#EXTM3U", "#EXT-X")):
            return True
        return False
    except Exception as e:
        return False


def test_logo(url):
    if any(b in url.lower() for b in BAD_DOMAINS):
        return False
    path = url.split("?")[0]
    if not path.lower().endswith((".jpg", ".jpeg")):
        return False
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=25) as r:
            data = r.read(1024)
            ct = r.headers.get("Content-Type", "")
            status = r.status
        return status < 400 and data[:3] == b"\xff\xd8\xff" and "image/" in ct
    except Exception:
        return False


def antivirus_ok(url):
    u = url.lower()
    netloc = re.sub(r"^[a-z]+://", "", u).split("/")[0].split(":")[0].split("@")[-1]
    for b in BAD_DOMAINS:
        if b in u:
            return False
    if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", netloc):
        return False
    if not u.startswith("https://"):
        return False
    known = [
        "abcnews.com", "akamaized.net", "dssott.com", "foxnews.com",
        "foxbusiness.com", "cbsnews.com", "cbsnstream.cbsnews.com",
        "cbsivideo.com", "dai.google.com", "epgshare01.online",
    ]
    return any(k in u for k in known)


def epg_coverage():
    res = {}
    try:
        status, data, _ = http_get(EPG_URL, timeout=120)
        raw = data
        if raw[:2] == b"\x1f\x8b":
            raw = gzip.GzipFile(fileobj=io.BytesIO(raw)).read()
        root = ET.fromstring(raw)
        progs = root.findall("programme")
        days = {}
        for i in range(3):
            d = (datetime.now() + timedelta(days=i)).strftime("%Y%m%d")
            days[i] = d
        for c in CHANNELS:
            cnt = [0, 0, 0]
            for p in progs:
                if p.get("channel") == c["tvg_id"]:
                    s = p.get("start", "")
                    for i in range(3):
                        if s[:8] == days[i]:
                            cnt[i] += 1
            res[c["tvg_id"]] = {
                "hoje": cnt[0], "amanha": cnt[1], "depois": cnt[2],
                "ok": cnt[0] > 0 and cnt[1] > 0 and cnt[2] > 0,
            }
    except Exception as e:
        res = {"erro": str(e)[:100]}
    return res


def main():
    out = []
    log = []

    log.append("RELATORIO CORRECAO lista5.m3u")
    log.append("Data: %s" % datetime.now().strftime("%Y-%m-%d %H:%M"))
    log.append("=" * 55)

    # EPG
    log.append("\n[1] EPG")
    cov = epg_coverage()
    all_ok = True
    if "erro" in cov:
        all_ok = False
        log.append("  ERRO baixando EPG: %s" % cov["erro"])
    else:
        for cid, v in cov.items():
            log.append("  %s: hoje=%d amanha=%d depois=%d -> %s" % (
                cid, v["hoje"], v["amanha"], v["depois"], "OK" if v["ok"] else "FALHOU"))
            if not v["ok"]:
                all_ok = False
    log.append("  EPG usado: %s" % EPG_URL)
    log.append("  EPG cobre hoje/amanha/depois de todos os canais: %s" % ("SIM" if all_ok else "NAO"))

    # streams, logos, antivirus
    log.append("\n[2] Canais (stream + logo + antivirus)")
    passing = []
    for c in CHANNELS:
        s_ok = test_stream(c["url"])
        l_ok = test_logo(c["logo"])
        av_ok = antivirus_ok(c["url"])
        status = "OK" if (s_ok and l_ok and av_ok) else "REPROVADO"
        log.append("  %s | stream=%s logo=%s antivirus=%s -> %s" % (
            c["name"], "OK" if s_ok else "FAIL",
            "OK" if l_ok else "FAIL", "OK" if av_ok else "FAIL", status))
        if s_ok and l_ok and av_ok:
            passing.append(c)

    # build m3u
    log.append("\n[3] Gerando M3U")
    if not all_ok or not passing:
        log.append("  ABORTADO: EPG ou canais nao passaram nos testes")
        print("\n".join(log))
        return 1

    lines = ['#EXTM3U x-tvg-url="%s"' % EPG_URL]
    for c in passing:
        extinf = ('#EXTINF:-1 tvg-id="%s" tvg-name="%s" tvg-logo="%s" '
                  'group-title="%s",%s' % (
                      c["tvg_id"], c["tvg_name"], c["logo"], c["group"], c["name"]))
        lines.append(extinf)
        lines.append(c["url"])
        log.append("  + %s (tvg-id=%s)" % (c["name"], c["tvg_id"]))
    content = "\n".join(lines) + "\n"

    # [4] validacao final
    problems = []
    clines = content.splitlines()
    if not clines[0].startswith("#EXTM3U"):
        problems.append("linha 1 nao e #EXTM3U")
    elif "x-tvg-url=" not in clines[0]:
        problems.append("linha 1 sem x-tvg-url")
    for i, l in enumerate(clines):
        if l.startswith("#EXTINF:"):
            if "tvg-id=" not in l:
                problems.append("linha %d sem tvg-id" % (i + 1))
            lg = re.search(r'tvg-logo="([^"]*)"', l)
            if not lg or not lg.group(1):
                problems.append("linha %d sem tvg-logo" % (i + 1))
            elif not test_logo_syntax(lg.group(1)):
                problems.append("linha %d logo invalido: %s" % (i + 1, lg.group(1)[:60]))
        elif l.startswith(("http://", "https://")):
            if i == 0 or not clines[i - 1].startswith("#EXTINF:"):
                problems.append("linha %d: URL sem #EXTINF acima" % (i + 1))
    if not problems:
        log.append("  VALIDACAO: OK (todas as URLs tem #EXTINF acima; logos .jpg; sem imgur; tvg-id presente)")
    else:
        for p in problems:
            log.append("  PROBLEMA: " + p)

    with open(M3U_FILE, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    log.append("  Salvo: %s (%d bytes, %d canais)" % (M3U_FILE, len(content), len(passing)))
    log.append("=" * 55)

    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(log) + "\n")
    print("\n".join(log))
    return 0


def test_logo_syntax(url):
    if any(b in url.lower() for b in BAD_DOMAINS):
        return False
    return url.split("?")[0].lower().endswith((".jpg", ".jpeg"))


if __name__ == "__main__":
    sys.exit(main())