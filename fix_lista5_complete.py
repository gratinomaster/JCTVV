#!/usr/bin/env python3
import io, os, re, shutil, gzip, json
import xml.etree.ElementTree as ET
import requests
from datetime import datetime, timedelta
from collections import OrderedDict

BASE = "/home/runner/work/JCTVV/JCTVV"
M3U_FILE = os.path.join(BASE, "lista5.m3u")
M3U_BAK = os.path.join(BASE, "lista5.m3u.bak.pre_correcao")
REPORT_FILE = os.path.join(BASE, "relatorio_lista5.txt")

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

CHANNELS = OrderedDict([
    ("ABC News Live", OrderedDict([
        ("tvg-id", "ABCNewsLive.us"),
        ("tvg-name", "ABC News Live"),
        ("tvg-logo", "https://keyframe-cdn.abcnews.com/streamprovider11.jpg"),
        ("group-title", "NEWS WORLD"),
        ("tvg-chno", "2"),
        ("stream", "https://abcnews-livestreams.akamaized.net/out/v1/6a597119dbd5428a82dc11a2f514a1a2/abcn-live-10-cmaf-manifest/abcn-live-10-index.m3u8"),
    ])),
    ("Fox News Channel", OrderedDict([
        ("tvg-id", "FoxNewsChannel.us"),
        ("tvg-name", "Fox News Channel"),
        ("tvg-logo", "https://raw.githubusercontent.com/gratinomaster/JCTV/main/fox_news.jpg"),
        ("group-title", "NEWS WORLD"),
        ("tvg-chno", "3"),
        ("stream", "https://247.foxnews.com/hls/live/2003586/FNCHLSv3/master.m3u8"),
    ])),
    ("Fox Business", OrderedDict([
        ("tvg-id", "FoxBusiness.us"),
        ("tvg-name", "Fox Business"),
        ("tvg-logo", "https://raw.githubusercontent.com/gratinomaster/JCTV/main/fox_business.jpg"),
        ("group-title", "NEWS WORLD"),
        ("tvg-chno", "4"),
        ("stream", "https://247.foxbusiness.com/hls/live/2003756/FBNHLSv3/master.m3u8"),
    ])),
    ("CBS News 24/7", OrderedDict([
        ("tvg-id", "CBSNews.us"),
        ("tvg-name", "CBS News 24/7"),
        ("tvg-logo", "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg"),
        ("group-title", "NEWS WORLD"),
        ("tvg-chno", "5"),
        ("stream", "https://dai.google.com/linear/hls/pa/event/Sid4xiTQTkCT1SLu6rjUSQ/stream/9fa3bc64-7c04-4c58-bf13-4b04029d1e13:DLS/master.m3u8"),
    ])),
])

VALID_IDS = {ch["tvg-id"] for ch in CHANNELS.values()}

REMOTE_EPG_URLS = [
    "https://iptv-epg.org/files/epg-us.xml.gz",
    "https://epg.pw/xmltv/epg_US.xml.gz",
]

LOCAL_EPG_PATHS = [
    os.path.join(BASE, "lista5_epg.xml.gz"),
    os.path.join(BASE, "lista5_epg.xml"),
]

def log(msg):
    print(msg)

def log_report(msg):
    with open(REPORT_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

def backup_file():
    if os.path.exists(M3U_FILE):
        with open(M3U_FILE, "r", encoding="utf-8") as f:
            content = f.read()
        with open(M3U_BAK, "w", encoding="utf-8") as f:
            f.write(content)
        log(f"  Backup salvo: {M3U_BAK}")
        return content
    return ""

def download_epg(url):
    log(f"  Baixando: {url}")
    try:
        r = requests.get(url, timeout=120, allow_redirects=True,
            headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"})
        if r.status_code != 200:
            log(f"    Status {r.status_code}")
            return None
        if len(r.content) < 1000:
            log(f"    Conteudo muito pequeno ({len(r.content)} bytes)")
            return None
        log(f"    OK: {len(r.content)} bytes")
        return r.content
    except Exception as e:
        log(f"    Erro: {e}")
        return None

def load_local_epg(path):
    if not os.path.exists(path):
        return None
    log(f"  Carregando local: {path}")
    try:
        with open(path, "rb") as f:
            raw = f.read()
        if raw[:2] == b'\x1f\x8b':
            text = gzip.GzipFile(fileobj=io.BytesIO(raw)).read()
        else:
            text = raw
        root = ET.fromstring(text)
        ch_map = {}
        for c in root.findall("channel"):
            cid = c.get("id", "")
            dn = c.find("display-name")
            ch_map[cid] = dn.text if dn is not None else cid
        programmes = root.findall("programme")
        log(f"    {len(ch_map)} canais, {len(programmes)} programas")
        return ch_map, programmes
    except Exception as e:
        log(f"    Erro parse: {e}")
        return None

def parse_epg(raw_data):
    if raw_data is None:
        return {}, []
    try:
        if raw_data[:2] == b'\x1f\x8b':
            text = gzip.GzipFile(fileobj=io.BytesIO(raw_data)).read()
        else:
            text = raw_data
        root = ET.fromstring(text)
        ch_map = {}
        for c in root.findall("channel"):
            cid = c.get("id", "")
            dn = c.find("display-name")
            ch_map[cid] = dn.text if dn is not None else cid
        programmes = root.findall("programme")
        return ch_map, programmes
    except Exception as e:
        log(f"    Erro parse: {e}")
        return {}, []

def filter_programmes(programmes, valid_ids):
    seen = set()
    result = []
    for p in programmes:
        ch = p.get("channel", "")
        if ch in valid_ids:
            key = f"{ch}|{p.get('start')}|{p.get('stop')}"
            if key not in seen:
                seen.add(key)
                result.append(p)
    return result

def test_coverage(programmes, label=""):
    hoje = datetime.now().strftime("%Y%m%d")
    amanha = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
    depois = (datetime.now() + timedelta(days=2)).strftime("%Y%m%d")
    c_hoje = sum(1 for p in programmes if p.get("start", "")[:8] == hoje)
    c_amanha = sum(1 for p in programmes if p.get("start", "")[:8] == amanha)
    c_depois = sum(1 for p in programmes if p.get("start", "")[:8] == depois)
    log(f"  {label}Hoje={c_hoje} Amanha={c_amanha} Depois={c_depois}")
    return c_hoje, c_amanha, c_depois

def check_url(url, timeout=15):
    try:
        r = requests.get(url, timeout=timeout,
            headers={"User-Agent": USER_AGENT}, allow_redirects=True)
        if r.status_code < 400:
            ct = r.headers.get("Content-Type", "")
            if not ct or any(t in ct for t in ["text", "application", "video", "audio"]):
                return True
            if r.content.startswith(b"#EXTM3U") or len(r.content) > 100:
                return True
        return False
    except:
        return False

def fix_logo_url(url):
    if not url:
        return None
    if "imgur.com" in url.lower():
        return None
    url_clean = url.split("?")[0].split("#")[0]
    if url_clean.lower().endswith((".jpg", ".jpeg")):
        return url_clean
    for bad_ext in [".png", ".svg", ".webp", ".gif", ".bmp"]:
        if url_clean.lower().endswith(bad_ext):
            base = url_clean[:url_clean.rindex(".")]
            return base + ".jpg"
    if "." in url_clean.split("/")[-1]:
        base = url_clean[:url_clean.rindex(".")]
        return base + ".jpg"
    return url_clean.rstrip("/") + "/logo.jpg"

def main():
    log("=" * 70)
    log("CORRECAO FINAL lista5.m3u - EPG + LOGOS + STREAMS")
    log("=" * 70)
    log_report("=" * 70)
    log_report(f"CORRECAO lista5.m3u - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    log_report("=" * 70 + "\n")

    hoje = datetime.now().strftime("%Y%m%d")
    amanha = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
    depois = (datetime.now() + timedelta(days=2)).strftime("%Y%m%d")

    log("\n[1] Backup do arquivo original...")
    backup_file()

    log("\n[2] Carregando EPGs...")
    all_channels = {}
    all_programmes = []

    for path in LOCAL_EPG_PATHS:
        result = load_local_epg(path)
        if result:
            chs, progs = result
            all_channels.update(chs)
            filtered = filter_programmes(progs, VALID_IDS)
            existing = {(p.get("channel",""), p.get("start",""), p.get("stop","")) for p in all_programmes}
            for p in filtered:
                key = (p.get("channel",""), p.get("start",""), p.get("stop",""))
                if key not in existing:
                    existing.add(key)
                    all_programmes.append(p)

    for url in REMOTE_EPG_URLS:
        data = download_epg(url)
        if data is None:
            continue
        chs, progs = parse_epg(data)
        all_channels.update(chs)
        filtered = filter_programmes(progs, VALID_IDS)
        existing = {(p.get("channel",""), p.get("start",""), p.get("stop","")) for p in all_programmes}
        for p in filtered:
            key = (p.get("channel",""), p.get("start",""), p.get("stop",""))
            if key not in existing:
                existing.add(key)
                all_programmes.append(p)
        log(f"  Remote: +{len(all_programmes)} total para nossos IDs")

    log(f"\n  Total: {len(all_programmes)} programas para {len(VALID_IDS)} canais")

    log("\n[3] Verificando cobertura EPG...")
    c_hoje, c_amanha, c_depois = test_coverage(all_programmes)
    for ch_name, ch_info in CHANNELS.items():
        cid = ch_info["tvg-id"]
        ch_progs = [p for p in all_programmes if p.get("channel") == cid]
        ch_hoje = sum(1 for p in ch_progs if p.get("start", "")[:8] == hoje)
        ch_amanha = sum(1 for p in ch_progs if p.get("start", "")[:8] == amanha)
        ch_depois = sum(1 for p in ch_progs if p.get("start", "")[:8] == depois)
        status = "OK" if (ch_hoje > 0 and ch_amanha > 0 and ch_depois > 0) else "PARCIAL"
        log(f"  {ch_name} (ID:{cid}): Hoje={ch_hoje} Amanha={ch_amanha} Depois={ch_depois} -> {status}")

    log("\n[4] Salvando EPG combinado...")
    tv_attrs = {"generator-info-name": "JCTV News EPG", "date": datetime.now().strftime("%Y%m%d%H%M%S")}
    root = ET.Element("tv", attrib=tv_attrs)
    for cid in VALID_IDS:
        ch = ET.SubElement(root, "channel", attrib={"id": cid})
        dn = ET.SubElement(ch, "display-name")
        dn.text = all_channels.get(cid, cid)
    for p in all_programmes:
        root.append(p)
    tree = ET.ElementTree(root)

    epg_xml = os.path.join(BASE, "lista5_epg.xml")
    tree.write(epg_xml, encoding="utf-8", xml_declaration=True)
    log(f"  XML: {epg_xml} ({len(all_programmes)} programas)")

    buf = io.BytesIO()
    tree.write(buf, encoding="utf-8", xml_declaration=True)
    epg_gz = os.path.join(BASE, "lista5_epg.xml.gz")
    with gzip.open(epg_gz, "wb") as f:
        f.write(buf.getvalue())
    log(f"  GZ: {epg_gz} ({buf.tell()} bytes)")

    log("\n[5] Testando streams...")
    stream_results = {}
    for ch_name, ch_info in CHANNELS.items():
        url = ch_info["stream"]
        ok = check_url(url)
        log(f"  Testando {ch_name}... {'OK' if ok else 'FALHOU'}")
        stream_results[ch_name] = ok
        log_report(f"Stream {ch_name}: {'OK' if ok else 'OFFLINE'}")

    log("\n[6] Gerando M3U corrigido...")
    epg_url_str = " ".join(REMOTE_EPG_URLS)
    m3u_lines = [f'#EXTM3U url-tvg="{epg_url_str}"']

    for ch_name, ch_info in CHANNELS.items():
        logo = fix_logo_url(ch_info["tvg-logo"])
        if not logo:
            logo = ch_info["tvg-logo"]

        attrs = f'tvg-id="{ch_info["tvg-id"]}"'
        attrs += f' tvg-name="{ch_info["tvg-name"]}"'
        attrs += f' tvg-logo="{logo}"'
        if ch_info.get("tvg-chno"):
            attrs += f' tvg-chno="{ch_info["tvg-chno"]}"'
        attrs += f' group-title="{ch_info["group-title"]}"'

        m3u_lines.append(f'#EXTINF:-1 {attrs},{ch_name}')
        m3u_lines.append(ch_info["stream"])
        log(f"  + {ch_name}")

    m3u_content = "\n".join(m3u_lines) + "\n"
    with open(M3U_FILE, "w", encoding="utf-8") as f:
        f.write(m3u_content)
    log(f"\n  M3U salvo: {M3U_FILE} ({len(m3u_content)} bytes, {len(CHANNELS)} canais)")

    log("\n[7] Verificacao final...")
    lines = m3u_content.strip().split("\n")
    issues = []
    for i, line in enumerate(lines):
        if line.startswith("#EXTINF:"):
            if "tvg-id=" not in line:
                issues.append(f"  Linha {i+1}: sem tvg-id")
            logo_match = re.search(r'tvg-logo="([^"]+)"', line)
            if logo_match:
                logo = logo_match.group(1)
                if not logo.lower().endswith((".jpg", ".jpeg")):
                    issues.append(f"  Linha {i+1}: logo nao .jpg: {logo}")
                if "imgur.com" in logo.lower():
                    issues.append(f"  Linha {i+1}: contem imgur.com: {logo}")
            else:
                issues.append(f"  Linha {i+1}: sem tvg-logo")
            if "group-title=" not in line:
                issues.append(f"  Linha {i+1}: sem group-title")
        elif line.startswith("http"):
            if i == 0 or not lines[i-1].startswith("#EXTINF:"):
                issues.append(f"  Linha {i+1}: URL sem #EXTINF acima")

    log(f"  Canais: {len(CHANNELS)}")
    if issues:
        log("  PROBLEMAS ENCONTRADOS:")
        for issue in issues:
            log(f"    {issue}")
    else:
        log("  NENHUM PROBLEMA ENCONTRADO!")

    log("\n" + "=" * 70)
    log("RELATORIO FINAL")
    log("=" * 70)
    log(f"  Arquivo: {M3U_FILE}")
    log(f"  Canais: {len(CHANNELS)}")
    log(f"  Programas EPG: {len(all_programmes)}")
    log(f"  Cobertura: Hoje={c_hoje} | Amanha={c_amanha} | Depois={c_depois}")
    log(f"  EPG Completo: {'SIM' if c_hoje > 0 and c_amanha > 0 and c_depois > 0 else 'PARCIAL'}")
    report_streams = ", ".join([f"{n}={'OK' if s else 'OFF'}" for n, s in stream_results.items()])
    log(f"  Streams: {report_streams}")

    log_report(f"\nCanais: {len(CHANNELS)}")
    log_report(f"Programas EPG: {len(all_programmes)}")
    log_report(f"Cobertura: Hoje={c_hoje} Amanha={c_amanha} Depois={c_depois}")
    log_report(f"EPG Completo: {'SIM' if c_hoje > 0 and c_amanha > 0 and c_depois > 0 else 'PARCIAL'}")
    log_report(f"Streams: {report_streams}")
    for ch_name, ch_info in CHANNELS.items():
        log_report(f"\n  {ch_name}:")
        log_report(f"    tvg-id: {ch_info['tvg-id']}")
        log_report(f"    logo: {ch_info['tvg-logo']}")
        log_report(f"    stream: {'OK' if stream_results[ch_name] else 'OFFLINE'}")
        cid = ch_info["tvg-id"]
        ch_progs = [p for p in all_programmes if p.get("channel") == cid]
        log_report(f"    EPG: {len(ch_progs)} programas (Hoje={sum(1 for p in ch_progs if p.get('start','')[:8]==hoje)}, Amanha={sum(1 for p in ch_progs if p.get('start','')[:8]==amanha)}, Depois={sum(1 for p in ch_progs if p.get('start','')[:8]==depois)})")
    log_report("=" * 70)

    log("\nConcluido!")

if __name__ == "__main__":
    main()
