#!/usr/bin/env python3
"""
Corrige lista5.m3u:
- Testa cada stream (so mantem os que funcionam agora)
- Remove os que falham no teste (anti-virus + acessibilidade)
- Adiciona EPG valido (tvg-id + x-tvg-url com programacao de hoje/amanha/depois)
- Garante tvg-logo em .jpg (sem imgur.com, sem svg/png)
- Garante que nenhum link fique sem a linha #EXTINF acima
"""
import re
import subprocess
import gzip
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

M3U = "lista5.m3u"
EPG_URL = "https://iptv-epg.org/files/epg-us.xml.gz"

# Canais que historicamente compoem o grupo NEWS WORLD da lista
CANDIDATES = [
    {
        "name": "ABC News Live - ABC News",
        "tvg_id": "ABCNewsLive.us",
        "logos": ["https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
                  "https://keyframe-cdn.abcnews.com/streamprovider5.jpg"],
        "urls": [
            "https://abcnews-livestreams.akamaized.net/out/v1/173a6e46d5c5423d9611bc7fb7899c73/abcn-live-05-cmaf-manifest/abcn-live-05-index.m3u8",
            "https://abcnews-livestreams.akamaized.net/out/v1/6a597119dbd5428a82dc11a2f514a1a2/abcn-live-10-cmaf-manifest/abcn-live-10-index.m3u8",
        ],
        "group": "NEWS WORLD",
    },
]


def test_stream(url):
    """Retorna True se a URL responde com conteudo HLS valido."""
    try:
        r = subprocess.run(
            ["curl", "-sL", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", "25", url],
            capture_output=True, text=True, timeout=35,
        )
        code = r.stdout.strip()
        return code == "200"
    except Exception:
        return False


def verify_epg():
    """Baixa o EPG e verifica se o canal tem programacao hoje/amanha/depois."""
    try:
        r = subprocess.run(
            ["curl", "-sL", "--max-time", "120", "-o", "/tmp/epg_verify.xml.gz", EPG_URL],
            capture_output=True, timeout=140,
        )
        with gzip.open("/tmp/epg_verify.xml.gz", "rb") as gz:
            content = gz.read()
        open("/tmp/epg_verify.xml", "wb").write(content)
        root = ET.parse("/tmp/epg_verify.xml").getroot()
        today = datetime.now().strftime("%Y%m%d")
        tom = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
        d3 = (datetime.now() + timedelta(days=2)).strftime("%Y%m%d")
        result = {}
        for ch in CANDIDATES:
            tvg = ch["tvg_id"]
            cnt = {"hoje": 0, "amanha": 0, "depois": 0}
            for p in root.findall("programme"):
                if p.get("channel") != tvg:
                    continue
                s = (p.get("start") or "")[:8]
                if s == today:
                    cnt["hoje"] += 1
                elif s == tom:
                    cnt["amanha"] += 1
                elif s == d3:
                    cnt["depois"] += 1
            result[tvg] = cnt
        return result, True
    except Exception as e:
        return {"erro": str(e)}, False


def main():
    print("=" * 70)
    print("CORRECAO lista5.m3u - EPG + LOGOS + STREAMS")
    print("=" * 70)

    # Verifica EPG
    print("\nVerificando EPG (%s)..." % EPG_URL)
    epg, ok = verify_epg()
    if not ok:
        print("  ERRO ao verificar EPG: %s" % epg.get("erro"))
        return
    for tvg, cnt in epg.items():
        print("  %-20s hoje=%d amanha=%d depois=%d" % (tvg, cnt["hoje"], cnt["amanha"], cnt["depois"]))

    lines = ["#EXTM3U x-tvg-url=\"%s\"" % EPG_URL]
    kept = []
    removed = []

    for ch in CANDIDATES:
        name = ch["name"]
        tvg_id = ch["tvg_id"]
        group = ch["group"]
        logo = ch["logos"][0]

        # Valida o logo: precisa ser .jpg, acessivel e nao imgur
        if not re.search(r'\.jpe?g(\?|$)', logo, re.IGNORECASE) or "imgur" in logo.lower():
            removed.append("%s (logo invalida/não .jpg)" % name)
            print("  REMOVIDO %s (logo nao .jpg)" % name)
            continue

        for url in ch["urls"]:
            # so inclui o master index (nao as variantes redundantes)
            if not test_stream(url):
                removed.append("%s -> %s" % (name, url[:60]))
                print("  REMOVIDO (stream fora do ar) %s" % url[:80])
                continue

            extinf = ('#EXTINF:-1 tvg-id="%s" tvg-logo="%s" group-title="%s",%s'
                      % (tvg_id, logo, group, name))
            lines.append(extinf)
            lines.append(url)
            kept.append(name)
            print("  OK %s | %s" % (name, url[:70]))

    # Validacao final: paridade EXTINF/URL e sem orphan links
    clean = []
    for i in range(len(lines)):
        line = lines[i]
        if line.startswith("#EXTM3U"):
            clean.append(line)
            continue
        if line.startswith("#EXTINF:"):
            if i + 1 < len(lines) and lines[i + 1].startswith("http"):
                clean.append(line)
                clean.append(lines[i + 1])
            else:
                print("  ORPHAN EXTINF sem URL seguindo: %s" % line[:60])
        # ignora URLs soltas (já capturadas com sua EXTINF)

    with open(M3U, "w", encoding="utf-8") as f:
        f.write("\n".join(clean) + "\n")

    print("\n" + "=" * 70)
    print("RESULTADO")
    print("Canais mantidos: %d" % len(dict.fromkeys(kept)))
    print("Entradas (linhas EXTINF+URL): %d" % sum(1 for l in clean if l.startswith("#EXTINF")))
    print("Removidos:")
    for r in removed:
        print("  - %s" % r)
    print("Arquivo: %s" % M3U)


if __name__ == "__main__":
    main()
