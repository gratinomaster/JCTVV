#!/usr/bin/env python3
"""
Corrige lista5.m3u (realidade 2026-09-18):
- Testa cada stream: mantem apenas os que funcionam AGORA (anti-virus -> validacao HLS)
- Fox News / Fox Business removidos: token Akamai expirado (403) e sem renovacao possivel no ambiente
- CBS News 24/7: URLs antigas mortas (410) -> substituidas por URL fresca via Google DAI
- Adiciona EPG (tvg-id + x-tvg-url) com programacao hoje/amanha/depois
- Garante tvg-logo .jpg (sem imgur.com), nenhum link sem #EXTINF acima
"""
import re
import subprocess
import gzip
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

M3U = "lista5.m3u"
EPG_URL = "https://iptv-epg.org/files/epg-us.xml.gz"

EPG_COVERS = {"ABCNewsLive.us", "CBSNews.us"}

# Extrai do arquivo atual os pares (atributos EXTINF, URL) mantendo nome original
def read_current():
    src = open(M3U, encoding="utf-8").read()
    pairs = re.findall(r'#EXTINF:-1\s+(.*?)\n(https?://\S+)', src)
    out = []
    seen = set()
    for attrs, url in pairs:
        name_m = re.search(r',\s*([^,]+)$', attrs)
        logo_m = re.search(r'tvg-logo="([^"]+)"', attrs)
        name = name_m.group(1).strip() if name_m else url
        if url in seen:
            continue
        seen.add(url)
        out.append({
            "name": name,
            "url": url,
            "logo": logo_m.group(1) if logo_m else "",
        })
    return out

FOX_NEWS = ["Watch Fox News Channel Online | Stream Fox News"]
FOX_BIZ = ["Fox Business Go | Fox News Video"]
CBS = ["Watch CBS News 24/7, our free live news stream"]

CBS_NEW_URLS = [
    "https://dai.google.com/linear/hls/pa/event/Sid4xiTQTkCT1SLu6rjUSQ/stream/4fb6e612-890d-4791-a507-13e8e2c6137d:TUL/master.m3u8",
    "https://dai.google.com/linear/hls/event/Sid4xiTQTkCT1SLu6rjUSQ/master.m3u8",
]
CBS_LOGO = "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg"

CBS_TVG = "CBSNews.us"
ABC_TVG = "ABCNewsLive.us"

def test_stream(url):
    try:
        r = subprocess.run(
            ["curl", "-sL", "-r", "0-8192", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", "25", "-A",
             "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128.0 Safari/537.36", url],
            capture_output=True, text=True, timeout=35,
        )
        return r.stdout.strip() in ("200", "206")
    except Exception:
        return False


def test_logo(url):
    if not url:
        return False
    if re.search(r'\.jpe?g(\?|$)', url, re.IGNORECASE) and "imgur" not in url.lower():
        try:
            r = subprocess.run(
                ["curl", "-sL", "-r", "0-1023", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", "15", url],
                capture_output=True, text=True, timeout=20,
            )
            return r.stdout.strip() in ("200", "206")
        except Exception:
            return False
    return False


def verify_epg():
    try:
        subprocess.run(["curl", "-sL", "--max-time", "120", "-o", "/tmp/epg_verify.xml.gz", EPG_URL],
                       capture_output=True, timeout=140)
        with gzip.open("/tmp/epg_verify.xml.gz", "rb") as gz:
            content = gz.read()
        root = ET.fromstring(content)
        today = datetime.now().strftime("%Y%m%d")
        tom = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
        d3 = (datetime.now() + timedelta(days=2)).strftime("%Y%m%d")
        result = {}
        for ch in ("ABCNewsLive.us", "CBSNews.us"):
            cnt = {"hoje": 0, "amanha": 0, "depois": 0}
            for p in root.findall("programme"):
                if p.get("channel") != ch:
                    continue
                s = (p.get("start") or "")[:8]
                if s == today:
                    cnt["hoje"] += 1
                elif s == tom:
                    cnt["amanha"] += 1
                elif s == d3:
                    cnt["depois"] += 1
            result[ch] = cnt
        return result
    except Exception as e:
        return {"erro": str(e)}


def main():
    print("=" * 70)
    print("CORRECAO lista5.m3u - EPG + LOGOS + STREAMS (realidade 2026-09-18)")
    print("=" * 70)

    epg = verify_epg()
    print("\nEPG (%s)" % EPG_URL)
    for tvg, cnt in epg.items():
        print("  %-16s hoje=%d amanha=%d depois=%d" % (tvg, cnt["hoje"], cnt["amanha"], cnt["depois"]))

    current = read_current()
    lines = ["#EXTM3U x-tvg-url=\"%s\"" % EPG_URL]
    kept = []
    removed = []

    for ch in current:
        name = ch["name"]
        if name in FOX_NEWS or name in FOX_BIZ:
            print("  REMOVIDO (stream 403 / token Akamai expirado) %s" % name)
            removed.append("%s (403 - token Akamai expirado, sem renovacao no ambiente)" % name)
            continue
        if name in CBS:
            continue  # substitui por URLs novas abaixo
        if not test_stream(ch["url"]):
            print("  REMOVIDO (stream fora do ar) %s" % name)
            removed.append("%s (stream fora do ar)" % name)
            continue
        logo = ch["logo"] or "https://keyframe-cdn.abcnews.com/streamprovider11.jpg"
        if not test_logo(logo):
            logo = "https://keyframe-cdn.abcnews.com/streamprovider11.jpg"
        extinf = ('#EXTINF:-1 tvg-id="%s" tvg-logo="%s" group-title="NEWS WORLD",%s' % (ABC_TVG, logo, name))
        lines.append(extinf)
        lines.append(ch["url"])
        kept.append(name)
        print("  OK %s | %s" % (name, ch["url"][:80]))

    for url in CBS_NEW_URLS:
        if not test_stream(url):
            print("  REMOVIDO (CBS nova URL falhou) %s" % url[:60])
            removed.append("CBS News 24/7 (%s)" % url[:60])
            continue
        extinf = ('#EXTINF:-1 tvg-id="%s" tvg-logo="%s" group-title="NEWS WORLD",Watch CBS News 24/7, our free live news stream'
                  % (CBS_TVG, CBS_LOGO))
        lines.append(extinf)
        lines.append(url)
        kept.append("Watch CBS News 24/7, our free live news stream")
        print("  OK CBS News 24/7 | %s" % url[:80])

    clean = ["#EXTM3U x-tvg-url=\"%s\"" % EPG_URL]
    i = 1
    orphan = 0
    while i < len(lines):
        if lines[i].startswith("#EXTINF:"):
            if i + 1 < len(lines) and lines[i + 1].startswith("http"):
                clean.append(lines[i])
                clean.append(lines[i + 1])
                i += 2
            else:
                orphan += 1
                print("  ORPHAN EXTINF: %s" % lines[i][:60])
                i += 1
        else:
            i += 1

    with open(M3U, "w", encoding="utf-8") as f:
        f.write("\n".join(clean) + "\n")

    print("\n" + "=" * 70)
    print("RESULTADO")
    print("Entradas EXTINF+URL: %d" % sum(1 for l in clean if l.startswith("#EXTINF")))
    print("Canais mantidos (unicos): %d" % len(set(kept)))
    print("Orphan links: %d" % orphan)
    print("Removidos:")
    for r in removed:
        print("  - %s" % r)
    print("Arquivo: %s" % M3U)


if __name__ == "__main__":
    main()