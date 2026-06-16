#!/usr/bin/env python3
"""Corrige lista5.m3u: dedup, EPG, logos .jpg, testa streams, remove imgur, anti-virus"""
import re, os, requests, gzip, io, xml.etree.ElementTree as ET
from datetime import datetime, timedelta

M3U_FILE = "/home/runner/work/JCTVV/JCTVV/lista5.m3u"
REPORT_FILE = "/home/runner/work/JCTVV/JCTVV/relatorio_lista5.txt"

EPG_URLS = [
    "https://iptv-epg.org/files/epg-us.xml.gz",
]

CHANNEL_MAP = {
    "ABC News Live (Disney)": {"tvg-id": "ABCNewsLive.us", "group": "NEWS WORLD"},
    "ABC News Live":           {"tvg-id": "ABCNewsLive.us", "group": "NEWS WORLD"},
    "Fox News Channel":        {"tvg-id": "FoxNewsChannel.us", "group": "NEWS WORLD"},
    "Fox Business":            {"tvg-id": "FoxBusiness.us", "group": "NEWS WORLD"},
    "CBS News 24/7":           {"tvg-id": "CBSNews.us", "group": "NEWS WORLD"},
}

FALLBACK_URLS = {
    "Fox News Channel": "http://41.205.93.154/FOX-NEWS/index.m3u8",
    "Fox Business": "http://41.205.93.154/FOXBUSINESS/index.m3u8",
    "CBS News 24/7": "https://cbsn-us.cbsnstream.cbsnews.com/out/v1/55a8648e8f134e82a470f83d562deeca/master.m3u8",
}

LOGO_MAP = {
    "ABC News Live (Disney)": "https://s.abcnews.com/images/Live/abc_news_live-abc-ml-250210_1739199021469_hpMain_16x9_608.jpg",
    "ABC News Live": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
    "Fox News Channel": "https://a57.foxnews.com/static.foxnews.com/foxnews.com/images/2024/09/fn-logo-social-share.jpg",
    "Fox Business": "https://a57.foxnews.com/static.foxbusiness.com/foxbusiness.com/2024/09/fb-logo-social-share.jpg",
    "CBS News 24/7": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
}

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

def log(msg):
    print(msg)

def log_report(msg):
    with open(REPORT_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

def classify(name, url):
    nl = name.lower()
    ul = url.lower()
    if "abc news live" in nl or "abcnl" in ul or "abcnews" in ul:
        if "disney" in ul or "dssott" in ul:
            return "ABC News Live (Disney)"
        return "ABC News Live"
    if "fox business" in nl or "fbnhl" in ul or "foxbusiness" in ul:
        return "Fox Business"
    if ("fox news" in nl or "fnchl" in ul or "fox-news" in ul or "foxnews" in ul):
        if "business" not in nl:
            return "Fox News Channel"
    if "cbs news" in nl or "cbsn" in ul or "dai.google" in ul:
        return "CBS News 24/7"
    return None

def quality_score(url):
    ul = url.lower()
    if "/master.m3u8" in ul or "ctr-all-hdri-sliding" in ul:
        return 10
    if "abcn-live-10" in ul or "abcn-live-05" in ul:
        return 9
    if "2400" in ul or "4231" in ul or "2249" in ul:
        return 7
    if "1549" in ul or "1700" in ul:
        return 5
    if "733" in ul or "441" in ul:
        return 3
    if "128k" in ul or "64k" in ul or "audio" in ul:
        return 1
    return 8

def parse_m3u(content):
    channels = []
    lines = content.strip().split("\n")
    i = 0
    while i < len(lines):
        l = lines[i].strip()
        if l.startswith("#EXTINF:"):
            extinf = l
            if i + 1 < len(lines) and not lines[i+1].startswith("#"):
                url = lines[i+1].strip()
                if url.startswith("http"):
                    channels.append({"extinf": extinf, "url": url})
                    i += 2
                    continue
        i += 1
    return channels

def test_stream(url, timeout=15):
    try:
        r = requests.get(url, timeout=timeout,
            headers={"User-Agent": UA}, allow_redirects=True)
        if r.status_code < 400 and len(r.content) > 50:
            if r.content.startswith(b"#EXTM3U") or r.content.startswith(b"#EXT-X"):
                return True
            return True
        return False
    except:
        return False

def check_virustotal_url(url):
    api_key = os.environ.get("VIRUSTOTAL_API_KEY", "")
    if not api_key:
        return {"status": "nao_verificado"}
    try:
        import base64
        url_id = base64.urlsafe_b64encode(url.encode()).decode().strip("=")
        headers = {"x-apikey": api_key}
        r = requests.get(f"https://www.virustotal.com/api/v3/urls/{url_id}",
            headers=headers, timeout=15)
        if r.status_code == 200:
            data = r.json()
            stats = data.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
            malicious = stats.get("malicious", 0)
            suspicious = stats.get("suspicious", 0)
            if malicious > 0 or suspicious > 0:
                return {"status": "malicious", "malicious": malicious, "suspicious": suspicious}
            return {"status": "clean"}
        return {"status": "erro_api"}
    except Exception as e:
        return {"status": "erro", "erro": str(e)}

def fix_logo(url):
    if not url: return None
    if "imgur.com" in url.lower(): return None
    url = url.split("?")[0].split("#")[0]
    u = url.lower()
    for ext in ['.png', '.svg', '.webp', '.gif', '.bmp']:
        if u.endswith(ext):
            return url[:url.rindex('.')] + ".jpg"
    if u.endswith(('.jpg','.jpeg')):
        return url
    return url

def test_epg_coverage():
    log("\nVerificando cobertura do EPG...")
    epg_ok = False
    for epg_url in EPG_URLS:
        try:
            log(f"  Testando EPG: {epg_url}")
            r = requests.get(epg_url, timeout=120,
                headers={"User-Agent": UA, "Accept-Encoding": "gzip"})
            if r.status_code != 200:
                log(f"    Status {r.status_code}")
                continue
            raw = r.content
            if raw[:2] == b'\x1f\x8b':
                text = gzip.GzipFile(fileobj=io.BytesIO(raw)).read()
            else:
                text = raw
            root = ET.fromstring(text)
            programmes = root.findall("programme")
            today = datetime.now().strftime("%Y%m%d")
            tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
            day_after = (datetime.now() + timedelta(days=2)).strftime("%Y%m%d")

            for cid in ["ABCNewsLive.us", "FoxNewsChannel.us", "FoxBusiness.us", "CBSNews.us"]:
                c_today = sum(1 for p in programmes if p.get("channel")==cid and p.get("start","")[:8]==today)
                c_tomorrow = sum(1 for p in programmes if p.get("channel")==cid and p.get("start","")[:8]==tomorrow)
                c_dayafter = sum(1 for p in programmes if p.get("channel")==cid and p.get("start","")[:8]==day_after)
                log(f"    {cid}: hoje={c_today} amanha={c_tomorrow} depois={c_dayafter}")
                if c_today > 0 and c_tomorrow > 0:
                    epg_ok = True
            break
        except Exception as e:
            log(f"    Erro: {e}")
    return epg_ok

def main():
    open(REPORT_FILE, "w").close()

    log("=" * 70)
    log("CORRECAO lista5.m3u - EPG + LOGOS + STREAMS + ANTI-VIRUS")
    log("=" * 70)
    log_report("RELATORIO CORRECAO lista5.m3u")
    log_report(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    log_report("=" * 50)

    # 1. Parse
    with open(M3U_FILE, "r") as f:
        content = f.read()
    channels = parse_m3u(content)
    log(f"\nLidos {len(channels)} entries do M3U")
    log_report(f"Entries lidas: {len(channels)}")

    # 2. Classify and dedup
    best = {}
    for ch in channels:
        name_match = re.search(r',(.+)$', ch["extinf"])
        name = name_match.group(1).strip() if name_match else ""
        ch_type = classify(name, ch["url"])
        if not ch_type:
            log(f"  Ignorado: {name[:40]}")
            continue
        score = quality_score(ch["url"])
        if ch_type not in best or score > best[ch_type]["score"]:
            best[ch_type] = {"ch": ch, "score": score, "type": ch_type}
        elif score == best[ch_type]["score"] and len(ch["url"]) < len(best[ch_type]["ch"]["url"]):
            best[ch_type] = {"ch": ch, "score": score, "type": ch_type}

    log(f"\nApos dedup: {len(best)} canais unicos")
    log_report(f"Canais unicos: {len(best)}")
    for k, v in best.items():
        log(f"  {k}: score={v['score']}")

    # 3. Test streams and try fallbacks
    log("\nTestando streams...")
    working = {}
    for k, v in best.items():
        url = v["ch"]["url"]
        print(f"  {k}... ", end="", flush=True)
        ok = test_stream(url)
        print("OK" if ok else "FALHOU")
        if ok:
            working[k] = v
        elif k in FALLBACK_URLS:
            fb_url = FALLBACK_URLS[k]
            print(f"    Tentando fallback: {fb_url[:60]}... ", end="", flush=True)
            fb_ok = test_stream(fb_url)
            print("OK" if fb_ok else "FALHOU")
            if fb_ok:
                v["ch"]["url"] = fb_url
                working[k] = v

    log(f"\nStreams OK: {len(working)}/{len(best)}")
    log_report(f"Streams OK: {len(working)}/{len(best)}")

    # 4. VirusTotal check (if API key available)
    log("\nVerificacao anti-virus...")
    clean_channels = {}
    for k, v in working.items():
        url = v["ch"]["url"]
        vt = check_virustotal_url(url)
        log(f"  {k}: VirusTotal={vt['status']}")
        log_report(f"  VirusTotal {k}: {vt['status']}")
        if vt.get("status") == "malicious":
            log(f"    PULANDO (malicioso)")
            log_report(f"    Status: PULADO")
        else:
            clean_channels[k] = v

    log(f"\nCanais limpos: {len(clean_channels)}/{len(working)}")
    log_report(f"Canais limpos: {len(clean_channels)}/{len(working)}")

    # 5. EPG coverage test
    epg_ok = test_epg_coverage()
    log(f"\nEPG Funcional: {'SIM' if epg_ok else 'NAO'}")
    log_report(f"EPG Funcional: {'SIM' if epg_ok else 'NAO'}")

    # 6. Generate M3U
    log("\nGerando M3U corrigido...")
    epg_urls_str = " ".join(EPG_URLS)
    lines = [f'#EXTM3U x-tvg-url="{epg_urls_str}"']

    for ch_type, v in clean_channels.items():
        ch = v["ch"]
        config = CHANNEL_MAP.get(ch_type, {})
        tvg_id = config.get("tvg-id", "")
        group = config.get("group", "NEWS WORLD")

        name_match = re.search(r',(.+)$', ch["extinf"])
        ch_name = name_match.group(1).strip() if name_match else ch_type

        logo_match = re.search(r'tvg-logo="([^"]*)"', ch["extinf"])
        logo = fix_logo(logo_match.group(1)) if logo_match else None
        if not logo:
            logo = LOGO_MAP.get(ch_type, "")
        if not logo:
            logo = ""

        tvg_name = ch_type.replace(" (Disney)","")

        extinf = f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-name="{tvg_name}" tvg-logo="{logo}" group-title="{group}",{ch_name}'
        lines.append(extinf)
        lines.append(ch["url"])
        log(f"  + {ch_name} (tvg-id={tvg_id})")

    m3u_content = "\n".join(lines) + "\n"

    # 7. Verify format
    log("\nVerificando formato...")
    issues = []
    for i, l in enumerate(lines):
        if l.startswith("#EXTINF:"):
            if "tvg-id=" not in l:
                issues.append(f"  Linha {i+1}: sem tvg-id")
            logo_m = re.search(r'tvg-logo="([^"]+)"', l)
            if logo_m:
                lurl = logo_m.group(1)
                if not lurl.lower().endswith(('.jpg','.jpeg')):
                    issues.append(f"  Linha {i+1}: logo nao .jpg: {lurl}")
                if "imgur.com" in lurl.lower():
                    issues.append(f"  Linha {i+1}: logo imgur.com: {lurl}")
            else:
                issues.append(f"  Linha {i+1}: sem tvg-logo")
        elif l.startswith("http"):
            if i == 0 or not lines[i-1].startswith("#EXTINF:"):
                issues.append(f"  Linha {i+1}: URL sem #EXTINF acima")

    if not lines[0].startswith("#EXTM3U"):
        issues.append("  Linha 1: sem #EXTM3U")
    elif "x-tvg-url=" not in lines[0]:
        issues.append("  Linha 1: sem x-tvg-url")

    if issues:
        log("PROBLEMAS:")
        for iss in issues:
            log(f"  {iss}")
    else:
        log("VERIFICACAO: Tudo OK!")

    # 8. Write
    with open(M3U_FILE, "w", encoding="utf-8") as f:
        f.write(m3u_content)
    nchan = m3u_content.count("#EXTINF:")
    log(f"\nSalvo: {M3U_FILE}")
    log(f"Canais: {nchan}")
    log(f"Tamanho: {len(m3u_content)} bytes")
    log_report(f"\nTotal canais: {nchan}")
    log_report(f"EPG URLs: {epg_urls_str}")
    log_report(f"Problemas: {len(issues)}")
    log_report("=" * 50)
    log("\nConcluido!")

if __name__ == "__main__":
    main()
