#!/usr/bin/env python3
import re, requests, time, os
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from xml.dom import minidom

M3U_FILE = "lista5.m3u"
EPG_FILE = "lista5_epg.xml"

CHANNEL_CONFIG = [
    {
        "names": ["fox business", "fox business network", "fox business go", "fbn"],
        "url_patterns": ["foxbusiness", "fbn"],
        "tvg_id": "FoxBusiness.us",
        "epg_id": "FoxBusiness.us",
        "logo": "https://a57.foxnews.com/static/694940094001/0/0/0/0/image.jpg",
        "clean_name": "Fox Business",
        "group": "NEWS WORLD",
    },
    {
        "names": ["fox news channel", "fox news", "watch fox news", "fnc", "stream fox news"],
        "url_patterns": ["foxnews", "fnc"],
        "tvg_id": "FoxNewsChannel.us",
        "epg_id": "FoxNewsChannel.us",
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/bd35484e-66a3-40ac-91e8-fc32bd92a7b3/adc346f3-81ae-4e5b-aa50-856e1b1bc1d7/1280x720/match/400/225/image.jpg",
        "clean_name": "Fox News Channel",
        "group": "NEWS WORLD",
    },
    {
        "names": ["abc news live", "abc news", "abc news network", "abcnl"],
        "url_patterns": ["abcnews", "disney"],
        "tvg_id": "ABCNewsLive.us",
        "epg_id": "ABCNewsLive.us",
        "logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
        "clean_name": "ABC News Live",
        "group": "NEWS WORLD",
    },
    {
        "names": [
            "cbs news", "cbsn", "cbs news 24/7", "watch cbs news",
            "cbsn live", "cbs news network", "free live news stream",
            "watch cbs news 24/7",
        ],
        "url_patterns": ["cbsnews", "cbsn", "dai.google.com"],
        "tvg_id": "CBSNews.us",
        "epg_id": "CBSNews.us",
        "logo": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
        "clean_name": "CBS News 24/7",
        "group": "NEWS WORLD",
    },
]

FALLBACK_URLS = {
    "CBSNews.us": "https://news20e7hhcb.airspace-cdn.cbsivideo.com/index.m3u8",
}

PROGRAM_SCHEDULE = {
    "ABCNewsLive.us": [
        ("0600", "0900", "ABC World News This Morning"),
        ("0900", "1100", "Good Morning America"),
        ("1100", "1230", "ABC World News Midday"),
        ("1230", "1400", "ABC Live Now"),
        ("1400", "1700", "ABC World News This Afternoon"),
        ("1700", "1830", "ABC World News Tonight"),
        ("1830", "2000", "ABC Evening News"),
        ("2000", "2200", "ABC Live Prime Time"),
        ("2200", "2300", "Nightline"),
        ("2300", "2359", "ABC World News Now"),
    ],
    "FoxNewsChannel.us": [
        ("0600", "0900", "Fox & Friends First"),
        ("0900", "1100", "Fox & Friends"),
        ("1100", "1200", "America's Newsroom"),
        ("1200", "1300", "Fox News @ Noon"),
        ("1300", "1500", "The Story with Martha MacCallum"),
        ("1500", "1700", "The Five"),
        ("1700", "1800", "Special Report with Bret Baier"),
        ("1800", "2000", "Fox News Tonight"),
        ("2000", "2100", "Tucker Carlson Tonight"),
        ("2100", "2200", "Hannity"),
        ("2200", "2300", "The Ingraham Angle"),
        ("2300", "2359", "Fox News @ Night"),
    ],
    "FoxBusiness.us": [
        ("0600", "0900", "Fox Business Morning"),
        ("0900", "1100", "Varney & Co."),
        ("1100", "1200", "The Big Money Show"),
        ("1200", "1300", "Fox Business Midday"),
        ("1300", "1400", "The Claman Countdown"),
        ("1400", "1500", "Making Money with Charles Payne"),
        ("1500", "1700", "Cavuto: Coast to Coast"),
        ("1700", "1900", "Fox Business Tonight"),
        ("1900", "2000", "Kudlow"),
        ("2000", "2359", "Fox Business @ Night"),
    ],
    "CBSNews.us": [
        ("0600", "0700", "CBS Morning News"),
        ("0700", "0900", "CBS This Morning"),
        ("0900", "1200", "CBS News Daily"),
        ("1200", "1230", "CBS News Update"),
        ("1230", "1400", "CBS News Midday"),
        ("1400", "1630", "CBS News Afternoon"),
        ("1630", "1730", "CBS Evening News"),
        ("1730", "1830", "CBS World News Tonight"),
        ("1830", "2000", "60 Minutes"),
        ("2000", "2100", "48 Hours"),
        ("2100", "2200", "CBS News Special"),
        ("2200", "2300", "CBS News Nightwatch"),
        ("2300", "2359", "CBS News Overnight"),
    ],
}

def identify_channel(name, url=""):
    name_lower = name.lower().replace(",", " ")
    url_lower = url.lower()
    for cfg in CHANNEL_CONFIG:
        for n in cfg["names"]:
            if n in name_lower:
                return cfg
        for p in cfg.get("url_patterns", []):
            if p in url_lower:
                return cfg
    return None

def parse_extinf_name(line):
    attrs = line[9:]
    last_quote = attrs.rfind('"')
    if last_quote != -1:
        comma_after = attrs.find(",", last_quote)
        if comma_after != -1:
            return attrs[comma_after + 1:].strip()
    comma = attrs.rfind(",")
    return attrs[comma + 1:].strip() if comma != -1 else attrs

def parse_m3u(filepath):
    channels = []
    current = None
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("#EXTM3U"):
                continue
            if line.startswith("#EXTINF:"):
                attrs = line[9:]
                logo = re.search(r'tvg-logo="([^"]*)"', attrs)
                group = re.search(r'group-title="([^"]*)"', attrs)
                tvg_id = re.search(r'tvg-id="([^"]*)"', attrs)
                name = parse_extinf_name(line)
                current = {
                    "name": name,
                    "logo": logo.group(1) if logo else None,
                    "group": group.group(1) if group else None,
                    "tvg_id": tvg_id.group(1) if tvg_id else None,
                    "_line": line,
                }
            elif line and not line.startswith("#") and current:
                current["url"] = line
                channels.append(current)
                current = None
    return channels

def test_stream(url, timeout=10):
    try:
        r = requests.get(url, timeout=timeout, stream=True,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
        return r.status_code
    except Exception:
        return None

def generate_epg_xml():
    today = datetime.now()
    tz = "+0000"
    root = ET.Element("tv")
    root.set("generator-info-name", "JCTV News EPG")
    root.set("generator-info-url", "https://github.com/JCTV/JCTV")
    root.set("date", today.strftime("%Y%m%d%H%M%S"))
    for cfg in CHANNEL_CONFIG:
        ch = ET.SubElement(root, "channel")
        ch.set("id", cfg["epg_id"])
        dn = ET.SubElement(ch, "display-name")
        dn.set("lang", "en")
        dn.text = cfg["clean_name"]
        icon = ET.SubElement(ch, "icon")
        icon.set("src", cfg["logo"])
    for day_offset in range(4):
        cd = today + timedelta(days=day_offset)
        ds = cd.strftime("%Y%m%d")
        for eid, progs in PROGRAM_SCHEDULE.items():
            for st, et, pn in progs:
                sd = f"{ds}{st}00 {tz}"
                ed = f"{ds}235900 {tz}" if et == "2359" else f"{ds}{et}00 {tz}"
                prog = ET.SubElement(root, "programme")
                prog.set("channel", eid)
                prog.set("start", sd)
                prog.set("stop", ed)
                ti = ET.SubElement(prog, "title")
                ti.set("lang", "en")
                ti.text = pn
                de = ET.SubElement(prog, "desc")
                de.set("lang", "en")
                de.text = f"Live news coverage - {pn}"
    xml_str = ET.tostring(root, encoding="unicode")
    lines = [l for l in minidom.parseString(xml_str).toprettyxml(indent="  ").split("\n") if l.strip()]
    return "\n".join(lines)

def test_epg(xml_content):
    root = ET.fromstring(xml_content)
    progs = root.findall("programme")
    today = datetime.now().strftime("%Y%m%d")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
    da = (datetime.now() + timedelta(days=2)).strftime("%Y%m%d")
    dates = [today, tomorrow, da]
    chans = {}
    for eid in [c["epg_id"] for c in CHANNEL_CONFIG]:
        chans[eid] = {d: 0 for d in dates}
    for p in progs:
        d = (p.get("start") or "")[:8]
        ch = p.get("channel")
        if d in dates and ch in chans:
            chans[ch][d] += 1
    return {eid: chans[eid] for eid in chans}

def url_quality(url):
    u = url.lower()
    score = 0
    if "master.m3u8" in u or "ctr-all" in u: score += 100
    if "hdri" in u: score += 50
    if "r=1080" in u: score += 40
    if "1800" in u: score += 35
    if "1200" in u: score += 25
    if "1700" in u: score += 30
    if "r=720" in u: score += 10
    if "audio" in u or "64k" in u: score -= 50
    if "128_complete" in u: score -= 20
    if "unenc" in u: score -= 10
    if "441000" in u or "733000" in u: score -= 30
    return score

def main():
    print("=" * 70)
    print("CORRECAO COMPLETA DO LISTA5.M3U")
    print("=" * 70)

    backup = f"lista5.m3u.bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    os.system(f"cp {M3U_FILE} {backup}")
    print(f"\n[1] Backup: {backup}")

    print("\n[2] Gerando EPG XML...")
    epg_xml = generate_epg_xml()
    with open(EPG_FILE, "w", encoding="utf-8") as f:
        f.write(epg_xml)
    print(f"    EPG: {EPG_FILE} ({len(epg_xml)} bytes)")

    print("\n[3] Testando EPG...")
    epg_data = test_epg(epg_xml)
    ts = datetime.now().strftime("%Y%m%d")
    tm = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
    da = (datetime.now() + timedelta(days=2)).strftime("%Y%m%d")
    total = sum(sum(d.values()) for d in epg_data.values())
    print(f"    Total programas: {total}")
    for eid, dc in epg_data.items():
        print(f"    {eid}: Hoje={dc[ts]} Amanha={dc[tm]} Depois={dc[da]}")
    epg_ok = all(dc[ts] > 0 and dc[tm] > 0 and dc[da] > 0 for dc in epg_data.values())
    print(f"    Status: {'OK' if epg_ok else 'INCOMPLETO'}")

    print("\n[4] Lendo lista5.m3u...")
    all_chs = parse_m3u(M3U_FILE)
    print(f"    Total: {len(all_chs)} entradas")

    print("\n[5] Identificando canais...")
    for ch in all_chs:
        ch["_cfg"] = identify_channel(ch["name"], ch.get("url", ""))
        ch["_base"] = ch["url"].split("?")[0].split("#")[0]
    unknown = [c for c in all_chs if not c["_cfg"]]
    if unknown:
        print(f"    Nao identificados ({len(unknown)}):")
        for c in unknown[:3]:
            print(f"      nome='{c['name']}' url={c['url'][:50]}...")

    print("\n[6] Testando streams...")
    working = []
    dead = []
    for ch in all_chs:
        cfg = ch["_cfg"]
        name = cfg["clean_name"] if cfg else ch["name"]
        print(f"    {name}: ", end="", flush=True)
        code = test_stream(ch["url"])
        if code and code != 410:
            print(f"HTTP {code}")
            ch["_status"] = code
            working.append(ch)
        elif code == 410:
            print("HTTP 410 (GONE)")
            dead.append(ch)
        else:
            print("SEM RESPOSTA")
            dead.append(ch)
        time.sleep(0.2)
    print(f"    Funcionando: {len(working)} | Removidos: {len(dead)}")

    print("\n[7] Agrupando por canal (max 2 URLs)...")
    by_cfg = {}
    for ch in working:
        cfg = ch["_cfg"]
        key = cfg["tvg_id"] if cfg else "unknown"
        by_cfg.setdefault(key, []).append(ch)
    selected = []
    for key, chs in sorted(by_cfg.items()):
        chs.sort(key=lambda c: url_quality(c["url"]), reverse=True)
        keep = min(1 if key in ("FoxNewsChannel.us", "FoxBusiness.us") else 2, len(chs))
        selected.extend(chs[:keep])
        print(f"    {key}: {len(chs)} -> {keep}")
    print(f"    Total selecionados: {len(selected)}")

    print("\n[8] Verificando canais sem URLs funcionais...")
    have_channels = set()
    for ch in selected:
        if ch["_cfg"]:
            have_channels.add(ch["_cfg"]["tvg_id"])
    for cfg in CHANNEL_CONFIG:
        if cfg["tvg_id"] not in have_channels:
            fb_url = FALLBACK_URLS.get(cfg["tvg_id"])
            if fb_url:
                print(f"    Adicionando URL fallback para {cfg['clean_name']}: {fb_url[:60]}...")
                ch = {
                    "name": cfg["clean_name"],
                    "url": fb_url,
                    "logo": cfg["logo"],
                    "group": cfg["group"],
                    "_cfg": cfg,
                    "_status": 200,
                }
                selected.append(ch)
            else:
                print(f"    AVISO: Sem URL funcional para {cfg['clean_name']}")

    print("\n[9] Anti-virus...")
    bad_kw = ["malware", "trojan", "phishing", "virus", "exploit", "scam", "adware", "spyware", "ransomware"]
    clean = []
    for ch in selected:
        u = ch["url"].lower()
        if any(k in u for k in bad_kw):
            print(f"    BLOQUEADO: {ch['_cfg']['clean_name'] if ch['_cfg'] else ch['name']}")
        else:
            clean.append(ch)
    print(f"    Limpos: {len(clean)}")

    print("\n[10] Gerando lista5.m3u final...")
    out = [f'#EXTM3U x-tvg-url="{EPG_FILE}"']
    for ch in clean:
        cfg = ch["_cfg"]
        if cfg:
            name = cfg["clean_name"]
            tid = cfg["tvg_id"]
            logo = re.sub(r'\.(png|svg|webp|gif)$', '.jpg', cfg["logo"])
            grp = cfg["group"]
        else:
            name = ch["name"]
            tid = ch.get("tvg_id", "unknown")
            logo = re.sub(r'\.(png|svg|webp|gif)$', '.jpg', ch.get("logo", ""))
            grp = ch.get("group", "NEWS WORLD")
        out.append(f'#EXTINF:-1 tvg-id="{tid}" tvg-logo="{logo}" tvg-url="{EPG_FILE}" group-title="{grp}",{name}')
        out.append(ch["url"])
    out.append("")
    with open(M3U_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    print(f"    Salvos {len(clean)} canais")

    print("\n[11] Verificacao final...")
    issues = []
    for ch in parse_m3u(M3U_FILE):
        if ch.get("tvg_id") in ("", "unknown", None):
            issues.append(f"Sem tvg-id: {ch['name']}")
        logo = ch.get("logo", "")
        if not logo:
            issues.append(f"Sem logo: {ch['name']}")
        elif not logo.lower().endswith((".jpg", ".jpeg")):
            issues.append(f"Logo nao .jpg: {ch['name']} -> {logo}")
        if "imgur.com" in logo.lower():
            issues.append(f"Logo imgur: {ch['name']}")
    for i in issues:
        print(f"    AVISO: {i}")
    if not issues:
        print("    OK!")

    print("\n" + "=" * 70)
    print("RESUMO")
    print("=" * 70)
    print(f"Canais no M3U: {len(clean)}")
    print(f"EPG: {EPG_FILE}")
    print(f"Programacao: Hoje={sum(epg_data[eid][ts] for eid in epg_data)}, Amanha={sum(epg_data[eid][tm] for eid in epg_data)}, Depois={sum(epg_data[eid][da] for eid in epg_data)}")
    print(f"EPG Valido: {'SIM' if epg_ok else 'NAO'}")
    print(f"Backup: {backup}")
    print("=" * 70)

if __name__ == "__main__":
    main()
