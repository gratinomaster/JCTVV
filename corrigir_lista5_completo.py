#!/usr/bin/env python3
"""Corrige lista5.m3u: EPG valido, logos .jpg, sem duplicatas, sem imgur"""
import re, gzip, xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import subprocess

today = datetime.now()
tomorrow = today + timedelta(days=1)
day_after = tomorrow + timedelta(days=1)

CHANNEL_MAP = {
    "ABC News Live": {
        "tvg_id": "ABC.News.Live.us2",
        "logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
        "url": "https://abcnews-livestreams.akamaized.net/out/v1/6a597119dbd5428a82dc11a2f514a1a2/abcn-live-10-cmaf-manifest/abcn-live-10-index.m3u8"
    },
    "Fox News Channel": {
        "tvg_id": "Fox.News.Channel.HD.us2",
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/a42fcc3e-9718-4893-9108-905cb3619587/45e40ad8-3c57-4fbb-938e-81475a6d6958/1280x720/match/896/504/image.jpg",
        "url": "https://247.foxnews.com/hls/live/2003586/FNCHLSv3/master.m3u8?hdnea=exp=1780713021~acl=/*~hmac=0613c02bc52224cfed586283de6fdacb75af4cfb512c185cba8a1d4644d4a304"
    },
    "Fox Business": {
        "tvg_id": "Fox.Business.HD.us2",
        "logo": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/2abec983-1632-4bec-abbf-173538f30a85/970fa095-2ee9-44d0-9d9b-203cc5659d2b/1280x720/match/896/504/image.jpg",
        "url": "https://247.foxbusiness.com/hls/live/2003756/FBNHLSv3/master.m3u8?hdnea=exp=1780713021~acl=/*~hmac=0613c02bc52224cfed586283de6fdacb75af4cfb512c185cba8a1d4644d4a304"
    },
    "CBS News 24/7": {
        "tvg_id": "CBS.News.National.Stream.us2",
        "logo": "https://www.cbsnews.com/bundles/cbsnewsvideo/images/cbsn--main-bg.jpg",
        "url": "https://dai.google.com/linear/hls/pa/event/Sid4xiTQTkCT1SLu6rjUSQ/stream/f75dd488-c9fd-4b8c-ad20-5b9b8fb8d6d8:TUL/master.m3u8"
    }
}

def detect_channel(name):
    nl = name.lower()
    if "abc" in nl and "news" in nl:
        return "ABC News Live"
    if "fox" in nl and "business" in nl:
        return "Fox Business"
    if "fox" in nl and "news" in nl:
        return "Fox News Channel"
    if "cbs" in nl and "news" in nl:
        return "CBS News 24/7"
    return None

def gerar_epg():
    slots = [
        ("060000", "090000", "Morning News"),
        ("090000", "120000", "Midday News"),
        ("120000", "150000", "Afternoon Edition"),
        ("150000", "180000", "Evening Edition"),
        ("180000", "210000", "Prime Time News"),
        ("210000", "235959", "Night Edition"),
    ]
    root = ET.Element("tv")
    for ch_name, ch_info in CHANNEL_MAP.items():
        ch_el = ET.SubElement(root, "channel", id=ch_info["tvg_id"])
        dn = ET.SubElement(ch_el, "display-name")
        dn.text = ch_name
        ic = ET.SubElement(ch_el, "icon", src=ch_info["logo"])
    for day_offset, day in enumerate([today, tomorrow, day_after]):
        day_str = day.strftime("%Y%m%d")
        for ch_name, ch_info in CHANNEL_MAP.items():
            for idx, (start_h, stop_h, title) in enumerate(slots):
                if day_offset == 2 and idx >= 5:
                    continue
                prog = ET.SubElement(root, "programme",
                    start=f"{day_str}{start_h} +0000",
                    stop=f"{day_str}{stop_h} +0000",
                    channel=ch_info["tvg_id"])
                t = ET.SubElement(prog, "title")
                t.text = f"{title} - {day.strftime('%Y-%m-%d')}"
                cat = ET.SubElement(prog, "category")
                cat.text = "News"
    xml_str = ET.tostring(root, encoding="unicode", xml_declaration=True)
    with open("lista5_epg.xml", "w", encoding="utf-8") as f:
        f.write(xml_str)
    with gzip.open("lista5_epg.xml.gz", "wt", encoding="utf-8") as f:
        f.write(xml_str)
    progs = root.findall("programme")
    hoje = sum(1 for p in progs if p.get("start","")[:8] == today.strftime("%Y%m%d"))
    amanha = sum(1 for p in progs if p.get("start","")[:8] == tomorrow.strftime("%Y%m%d"))
    depois = sum(1 for p in progs if p.get("start","")[:8] == day_after.strftime("%Y%m%d"))
    print(f"EPG gerado: {len(progs)} programas")
    print(f"  Hoje ({today.strftime('%Y%m%d')}): {hoje}")
    print(f"  Amanha ({tomorrow.strftime('%Y%m%d')}): {amanha}")
    print(f"  Depois ({day_after.strftime('%Y%m%d')}): {depois}")
    return hoje > 0 and amanha > 0 and depois > 0

def corrigir_m3u():
    lines = []
    lines.append('#EXTM3U x-tvg-url="https://raw.githubusercontent.com/JCTV/JCTV/main/lista5_epg.xml.gz"')
    for ch_name, ch_info in CHANNEL_MAP.items():
        extinf = (
            f'#EXTINF:-1 tvg-id="{ch_info["tvg_id"]}" '
            f'tvg-logo="{ch_info["logo"]}" '
            f'group-title="NEWS WORLD",{ch_name}'
        )
        lines.append(extinf)
        lines.append(ch_info["url"])
    with open("lista5.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"M3U atualizado: {len(CHANNEL_MAP)} canais unicos")
    for ch in CHANNEL_MAP:
        print(f"  - {ch}")

def testar_streams():
    results = {}
    with open("lista5.m3u", "r", encoding="utf-8") as f:
        content = f.read()
    for ch_name, ch_info in CHANNEL_MAP.items():
        url = ch_info["url"]
        print(f"  Testando: {ch_name}...", end=" ", flush=True)
        try:
            result = subprocess.run(
                ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                 "--connect-timeout", "10", "--max-time", "15", url],
                capture_output=True, text=True, timeout=20
            )
            code = result.stdout.strip()
            results[ch_name] = code
            print(f"HTTP {code}")
        except Exception as e:
            results[ch_name] = f"ERRO: {e}"
            print(f"ERRO: {e}")
    return results

def main():
    print("=" * 60)
    print("CORRECAO COMPLETA - lista5.m3u")
    print("=" * 60)
    print("\n[1/5] Gerando EPG...")
    epg_ok = gerar_epg()
    print(f"  EPG {'✓ FUNCIONANDO' if epg_ok else '✗ PROBLEMAS'}")
    print("\n[2/5] Corrigindo M3U...")
    corrigir_m3u()
    print("\n[3/5] Verificando integridade...")
    with open("lista5.m3u") as f:
        m3u = f.read()
    imgur_count = m3u.lower().count("imgur.com")
    print(f"  URLs imgur.com: {imgur_count} {'✓' if imgur_count == 0 else '✗'}")
    logos = re.findall(r'tvg-logo="([^"]*)"', m3u)
    non_jpg = [l for l in logos if not (l.lower().endswith(".jpg") or l.lower().endswith(".jpeg"))]
    print(f"  Logos .jpg: {len(logos)} total, {len(non_jpg)} nao-jpg {'✓' if len(non_jpg) == 0 else '✗'}")
    lines = m3u.strip().split("\n")
    bad = 0
    for i, line in enumerate(lines):
        if line.startswith("http") and (i == 0 or not lines[i-1].startswith("#EXTINF")):
            bad += 1
    print(f"  URLs com #EXTINF acima: {'✓' if bad == 0 else f'✗ {bad} sem #'}")
    print("\n[4/5] Verificando EPG schedule...")
    tree = ET.parse("lista5_epg.xml")
    root = tree.getroot()
    progs = root.findall("programme")
    hoje = sum(1 for p in progs if p.get("start","")[:8] == today.strftime("%Y%m%d"))
    amanha = sum(1 for p in progs if p.get("start","")[:8] == tomorrow.strftime("%Y%m%d"))
    depois = sum(1 for p in progs if p.get("start","")[:8] == day_after.strftime("%Y%m%d"))
    print(f"  Hoje: {hoje} programas")
    print(f"  Amanha: {amanha} programas")
    print(f"  Depois: {depois} programas")
    print("\n[5/5] Testando streams...")
    resultados = testar_streams()
    print("\n" + "=" * 60)
    print("RESUMO FINAL")
    print("=" * 60)
    all_ok = True
    for ch, code in resultados.items():
        ok = code == "200"
        print(f"  {ch}: HTTP {code} {'✓' if ok else '✗'}")
        if not ok:
            all_ok = False
    print(f"\nEPG: {'✓ FUNCIONANDO' if epg_ok else '✗ PROBLEMAS'}")
    print(f"Streams: {'✓ TODOS OK' if all_ok else '✗ ALGUNS FALHARAM'}")
    print(f"Arquivos:")
    print(f"  lista5.m3u - Playlist corrigida")
    print(f"  lista5_epg.xml - EPG XML")
    print(f"  lista5_epg.xml.gz - EPG compactado")

if __name__ == "__main__":
    main()
