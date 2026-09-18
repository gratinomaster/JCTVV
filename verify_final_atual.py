#!/usr/bin/env python3
"""Verificação final do lista5.m3u corrigido."""
import re, gzip, subprocess, io
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36"


def parse_m3u(path):
    with open(path, encoding="utf-8") as f:
        lines = [l.rstrip("\n") for l in f]
    header = lines[0]
    entries = []
    cur = None
    problems = []
    for i, line in enumerate(lines[1:], start=2):
        if not line.strip():
            continue
        if line.startswith("#EXTINF:"):
            m = re.match(r'#EXTINF:-?\d+\s+(.*?),(.*)$', line)
            attrs = m.group(1) if m else ""
            name = m.group(2).strip() if m else line
            tvg_id = re.search(r'tvg-id="([^"]*)"', attrs)
            logo = re.search(r'tvg-logo="([^"]*)"', attrs)
            grp = re.search(r'group-title="([^"]*)"', attrs)
            cur = {"name": name, "tvg_id": tvg_id.group(1) if tvg_id else "",
                   "logo": logo.group(1) if logo else "", "group": grp.group(1) if grp else "",
                   "url": None, "line": i}
            entries.append(cur)
        elif line.startswith("http"):
            if cur is None or cur["url"] is not None:
                problems.append(f"linha {i}: URL sem #EXTINF imediatamente acima ou EXTINF duplicado")
            else:
                cur["url"] = line
                if not re.match(r'^https?://', line):
                    problems.append(f"linha {i}: nao-e url http")
        else:
            # linha solta nao reconhecida
            if not line.startswith("#"):
                problems.append(f"linha {i}: linha solta sem #EXTINF acima")
    # URLs sem url
    for e in entries:
        if not e["url"]:
            problems.append(f"linha {e['line']}: #EXTINF sem URL abaixo")
    return header, entries, problems


def curl(url, t=25):
    try:
        r = subprocess.run(["curl", "-sL", "--max-time", str(t), "-A", UA, "-o", "/dev/null", "-w", "%{http_code} %{content_type} %{size_download}", url],
                           capture_output=True, text=True, timeout=t + 10)
        return r.stdout.strip()
    except Exception as e:
        return f"ERRO {e}"


def main():
    print("=" * 70)
    print("VERIFICACAO FINAL lista5.m3u")
    print("=" * 70)
    header, entries, problems = parse_m3u("lista5.m3u")
    print("\nHeader:", header)
    url_tvgs = re.findall(r'url-tvg="([^"]*)"', header)
    print("url-tvg no header:", url_tvgs)
    print("\nEstrutura:")
    for e in entries:
        print(f"  L{e['line']} {e['name']} | tvg-id={e['tvg_id']} | logo={'S' if e['logo'] else 'N'} | url={'S' if e['url'] else 'N'}")
    print("\nProblemas de estrutura:", problems if problems else "NENHUM (todas URLs com #EXTINF acima, sem linhas soltas)")

    # verificar logos
    print("\nLOGOS (.jpg?, sem imgur):")
    logo_ok = True
    for e in set(id(e) for e in entries):
        e = [x for x in entries if id(x) == e][0]
        logo = e["logo"]
        if not logo:
            continue
        ext = urlparse(logo).path.rsplit(".", 1)[-1].lower() if "." in urlparse(logo).path else "?"
        imgur = "imgur.com" in logo
        status = curl(logo)
        isjpg = ext not in ("jpg", "jpeg")
        if isjpg or imgur:
            logo_ok = False
        print(f"  [{ext}] {e['name']}: {status} imgur={'SIM!' if imgur else 'nao'}")

    # verificar streams
    print("\nSTREAMS:")
    stream_ok = True
    for e in entries:
        status = curl(e["url"])
        print(f"  {e['name']}: {status}")
        if not status.startswith("200"):
            stream_ok = False

    # verificar EPG: baixar e contar hoje/amanha/depois para os tvg-ids
    print("\nEPG (programas hoje/amanha/depois):")
    epg_ok = True
    ids = sorted(set(e["tvg_id"] for e in entries if e["tvg_id"]))
    if url_tvgs:
        epg_url = url_tvgs[0]
        raw = subprocess.run(["curl", "-sL", "--max-time", "180", "-A", UA, epg_url], capture_output=True, timeout=190)
        data = raw.stdout
        try:
            xml_data = gzip.decompress(data)
            root = ET.fromstring(xml_data)
            now = datetime.now(timezone.utc)
            dates = [(now + timedelta(days=d)).strftime("%Y%m%d") for d in [0, 1, 2]]
            progs = {}
            for p in root.findall("programme"):
                cid = p.get("channel", "")
                start = p.get("start", "")[:8]
                if cid in ids:
                    progs.setdefault(cid, {}).setdefault(start, 0)
                    progs[cid][start] += 1
            for cid in ids:
                counts = [progs.get(cid, {}).get(d, 0) for d in dates]
                today, tom, day2 = counts
                ok = today > 0 and tom > 0 and day2 > 0
                if not ok:
                    epg_ok = False
                print(f"  {cid}: hoje={today} amanha={tom} depois={day2} {'OK' if ok else 'SEM DADOS'}")
        except Exception as ex:
            epg_ok = False
            print("  ERRO ao processar EPG:", ex)
    else:
        epg_ok = False
        print("  SEM url-tvg no header!")

    print("\n" + "=" * 70)
    print("RESUMO")
    print("=" * 70)
    print(f"  Estrutura OK: {not problems}")
    print(f"  Logos OK (.jpg, sem imgur): {logo_ok}")
    print(f"  Streams OK: {stream_ok}")
    print(f"  EPG hoje/amanha/depois: {epg_ok}")
    total = "TODOS OS TESTES PASSARAM" if (not problems and logo_ok and stream_ok and epg_ok) else "HA FALHAS"
    print(f"\n  >>> {total}")


if __name__ == "__main__":
    main()