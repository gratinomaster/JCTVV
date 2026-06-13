#!/usr/bin/env python3
"""
Verificação completa do lista5.m3u corrigido
"""
import re, gzip, ssl, sys, os
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from urllib.request import Request, urlopen

M3U_PATH = "lista5.m3u"

EPG_URL = "https://iptv-epg.org/files/epg-us.xml.gz"
EPG_URL2 = "https://epg.pw/xmltv/epg_US.xml.gz"

CHANNEL_NAMES = {
    "ABCNewsLive.us": "ABC News Live",
    "CBSNews.us": "CBS News 24/7",
}


def download_epg(url):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        req = Request(url)
        req.add_header('User-Agent', 'Mozilla/5.0')
        resp = urlopen(req, timeout=60, context=ctx)
        data = resp.read()
        if url.endswith('.gz'):
            data = gzip.decompress(data)
        return data.decode('utf-8', errors='replace')
    except Exception as e:
        return None


def check_url(url):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        req = Request(url, method='HEAD')
        req.add_header('User-Agent', 'Mozilla/5.0')
        resp = urlopen(req, timeout=10, context=ctx)
        return resp.status in (200, 301, 302, 307, 308)
    except:
        try:
            req = Request(url)
            req.add_header('User-Agent', 'Mozilla/5.0')
            resp = urlopen(req, timeout=10, context=ctx)
            resp.read(1024)
            return True
        except:
            return False


def test_epg_channel(epg_content, tvg_id):
    result = {"hoje": 0, "amanha": 0, "depois_amanha": 0, "programas_hoje": [], "programas_amanha": [], "programas_da": []}
    try:
        root = ET.fromstring(epg_content)
        hoje = datetime.now().strftime("%Y%m%d")
        amanha = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
        da = (datetime.now() + timedelta(days=2)).strftime("%Y%m%d")
        for prog in root.findall("programme"):
            ch = prog.get("channel", "")
            if ch == tvg_id:
                s = prog.get("start", "")
                start_date = s[:8] if len(s) >= 8 else ""
                title = prog.findtext("title", "N/A")
                if start_date == hoje:
                    result["hoje"] += 1
                    if len(result["programas_hoje"]) < 5:
                        result["programas_hoje"].append((s[8:12] if len(s) >= 12 else "", title))
                elif start_date == amanha:
                    result["amanha"] += 1
                    if len(result["programas_amanha"]) < 5:
                        result["programas_amanha"].append((s[8:12] if len(s) >= 12 else "", title))
                elif start_date == da:
                    result["depois_amanha"] += 1
                    if len(result["programas_da"]) < 5:
                        result["programas_da"].append((s[8:12] if len(s) >= 12 else "", title))
    except:
        pass
    return result


def main():
    errors = []
    passed = 0
    failed = 0

    def test(name, condition, detail=""):
        nonlocal passed, failed
        if condition:
            print(f"  ✓ {name}")
            passed += 1
        else:
            print(f"  ✗ {name}: {detail}")
            failed += 1
            errors.append(f"  ✗ {name}: {detail}")

    print("=" * 70)
    print("VERIFICAÇÃO COMPLETA DO lista5.m3u")
    print("=" * 70)

    # 1. File exists and is readable
    print("\n[1] Estrutura do arquivo")
    with open(M3U_PATH, 'r', encoding='utf-8') as f:
        content = f.read()
    lines = content.strip().split('\n')

    test("Arquivo existe", os.path.exists(M3U_PATH))
    test("Header #EXTM3U", lines[0].startswith('#EXTM3U'))
    test("Tem url-tvg no header", 'url-tvg="' in lines[0])

    # Extract EPG URLs from header
    epg_urls = re.findall(r'https?://[^"]+', lines[0])
    test(f"EPG sources: {len(epg_urls)}", len(epg_urls) > 0)

    # 2. Parse channels
    print("\n[2] Canais")
    entries = []
    i = 1
    while i < len(lines):
        l = lines[i].strip()
        if l.startswith('#EXTINF:'):
            url = lines[i+1].strip() if i+1 < len(lines) else ""
            tvg_id = re.search(r'tvg-id="([^"]*)"', l)
            tvg_logo = re.search(r'tvg-logo="([^"]*)"', l)
            group = re.search(r'group-title="([^"]*)"', l)
            name = re.search(r',(.+)$', l)
            entries.append({
                "tvg_id": tvg_id.group(1) if tvg_id else "",
                "logo": tvg_logo.group(1) if tvg_logo else "",
                "group": group.group(1) if group else "",
                "name": name.group(1) if name else "",
                "url": url,
            })
            i += 2
        else:
            i += 1

    test(f"Total de canais: {len(entries)}", len(entries) > 0)
    test("Nenhum canal duplicado (URL)", len(set(e["url"] for e in entries)) == len(entries))
    test("Nenhum canal duplicado (nome)", len(set(e["name"] for e in entries)) == len(entries))

    # 3. Check each channel
    print("\n[3] Atributos por canal")
    for e in entries:
        print(f"\n  Canal: {e['name']}")
        test("  tvg-id presente", bool(e["tvg_id"]), f"tvg-id={e['tvg_id']}")
        test("  tvg-logo presente", bool(e["logo"]))
        test("  Logo .jpg", e["logo"].split('?')[0].lower().endswith('.jpg'), f"Logo={e['logo'][:50]}")
        test("  group-title presente", bool(e["group"]))
        test("  URL presente", bool(e["url"]), "URL vazia")
        test("  Não é imgur.com", "imgur.com" not in e["logo"] and "imgur.com" not in e["url"], "Usa imgur.com")

    # 4. URL accessibility
    print("\n[4] Teste de URLs")
    for e in entries:
        accessible = check_url(e["url"])
        test(f"  {e['name'][:40]}: URL acessível", accessible, f"URL={e['url'][:60]}")

    # 5. EPG programming
    print("\n[5] Programação EPG")
    print("  Baixando EPG...")
    epg = download_epg(EPG_URL)
    if not epg:
        epg = download_epg(EPG_URL2)

    if epg:
        print(f"  EPG baixado: {len(epg)} bytes")
        for e in entries:
            tvg_id = e["tvg_id"]
            r = test_epg_channel(epg, tvg_id)
            hoje_ok = r["hoje"] > 0
            amanha_ok = r["amanha"] > 0
            da_ok = r["depois_amanha"] > 0

            desc = f"hoje={r['hoje']}, amanhã={r['amanha']}, +2={r['depois_amanha']}"
            test(f"  {e['name']}: EPG completo (hoje+amanhã+depois)", hoje_ok and amanha_ok and da_ok, desc)

            if r["programas_hoje"]:
                print(f"    Hoje: {r['programas_hoje'][0][0]}h - {r['programas_hoje'][0][1][:50]}")
            if r["programas_amanha"]:
                print(f"    Amanhã: {r['programas_amanha'][0][0]}h - {r['programas_amanha'][0][1][:50]}")
            if r["programas_da"]:
                print(f"    +2: {r['programas_da'][0][0]}h - {r['programas_da'][0][1][:50]}")
    else:
        print("  ✗ Não foi possível baixar EPG")

    # Summary
    print("\n" + "=" * 70)
    print("RESULTADO FINAL")
    print("=" * 70)
    total = passed + failed
    print(f"  Testes: {total}")
    print(f"  ✓ Passaram: {passed}")
    print(f"  ✗ Falharam: {failed}")

    if failed == 0:
        print("\n  ✅ lista5.m3u está CORRETO!")
    else:
        print(f"\n  ❌ {failed} teste(s) falharam:")
        for e in errors:
            print(f"    {e}")

    return failed


if __name__ == "__main__":
    sys.exit(main())
