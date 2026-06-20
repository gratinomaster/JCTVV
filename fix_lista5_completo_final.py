#!/usr/bin/env python3
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import gzip
import os

# ─── CONFIG ───────────────────────────────────────────────────────
NOW = datetime.now()
TODAY_MIDNIGHT = NOW.replace(hour=0, minute=0, second=0, microsecond=0)

# Channel definitions: (tvg-id, tvg-name, tvg-logo.jpg)
CHANNELS = [
    ("ABCNewsLive.us", "ABC News Live",
     "https://keyframe-cdn.abcnews.com/streamprovider11.jpg"),
    ("FoxNewsChannel.us", "Fox News Channel",
     "https://a57.foxnews.com/static/foxnews/fox-news-logo.jpg"),
    ("FoxBusiness.us", "Fox Business",
     "https://a57.foxnews.com/static/foxnews/fox-business-logo.jpg"),
    ("CBSNews.us", "CBS News 24/7",
     "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg"),
]

PROGRAMS = {
    "ABCNewsLive.us": [
        ("06", "09", "Good Morning America"),
        ("09", "12", "World News This Morning"),
        ("12", "13", "ABC World News Midday"),
        ("13", "17", "ABC News Live"),
        ("17", "18", "World News Tonight"),
        ("18", "22", "ABC News Prime"),
        ("22", "06", "Nightline"),
    ],
    "FoxNewsChannel.us": [
        ("06", "09", "Fox & Friends First"),
        ("09", "12", "America's Newsroom"),
        ("12", "13", "Happening Now"),
        ("13", "16", "The Story with Martha MacCallum"),
        ("16", "17", "Your World with Neil Cavuto"),
        ("17", "18", "The Five"),
        ("18", "20", "Fox News Tonight"),
        ("20", "21", "Tucker Carlson Tonight"),
        ("21", "22", "Hannity"),
        ("22", "23", "The Ingraham Angle"),
        ("23", "06", "Fox News @ Night"),
    ],
    "FoxBusiness.us": [
        ("06", "09", "Mornings with Maria"),
        ("09", "12", "Varney & Co."),
        ("12", "14", "Cavuto: Coast to Coast"),
        ("14", "17", "Making Money with Charles Payne"),
        ("17", "19", "The Evening Edit"),
        ("19", "20", "Kudlow"),
        ("20", "22", "The Claman Countdown"),
        ("22", "23", "Fox Business @ Night"),
        ("23", "06", "Fox Business Overnight"),
    ],
    "CBSNews.us": [
        ("06", "07", "CBS Morning News"),
        ("07", "09", "CBS This Morning"),
        ("09", "12", "CBS News NOW"),
        ("12", "12", "CBS News Midday"),
        ("12", "17", "CBS News Afternoon"),
        ("17", "18", "CBS Evening News"),
        ("18", "22", "CBS News Prime"),
        ("22", "23", "CBS News Nightwatch"),
        ("23", "06", "CBS News Overnight"),
    ],
}

# ─── GENERATE EPG ─────────────────────────────────────────────────
def generate_epg():
    root = ET.Element('tv')
    root.set('date', NOW.strftime('%Y%m%d%H%M%S'))

    for ch_id, ch_name, ch_logo in CHANNELS:
        ch = ET.SubElement(root, 'channel')
        ch.set('id', ch_id)
        disp = ET.SubElement(ch, 'display-name')
        disp.set('lang', 'en')
        disp.text = ch_name
        icon = ET.SubElement(ch, 'icon')
        icon.set('src', ch_logo)

    for day_offset in range(3):
        midnight = TODAY_MIDNIGHT + timedelta(days=day_offset)
        for ch_id, _, _ in CHANNELS:
            programs = PROGRAMS.get(ch_id, PROGRAMS["ABCNewsLive.us"])
            for start_h, end_h, title in programs:
                sh = int(start_h)
                eh = int(end_h)
                start_dt = midnight + timedelta(hours=sh)
                if eh <= sh:
                    end_dt = midnight + timedelta(days=1, hours=eh)
                else:
                    end_dt = midnight + timedelta(hours=eh)

                prog = ET.SubElement(root, 'programme')
                prog.set('channel', ch_id)
                prog.set('start', start_dt.strftime('%Y%m%dT%H%M00 +0000'))
                prog.set('stop', end_dt.strftime('%Y%m%dT%H%M00 +0000'))
                title_elem = ET.SubElement(prog, 'title')
                title_elem.set('lang', 'en')
                title_elem.text = title
                desc = ET.SubElement(prog, 'desc')
                desc.set('lang', 'en')
                desc.text = f"Live news coverage from {ch_name}"

    return root

# ─── GENERATE M3U ─────────────────────────────────────────────────
def generate_m3u():
    lines = []
    epg_urls = [
        "lista5_epg_atualizado.xml.gz",
        "https://epg.pw/xmltv/epg_US.xml.gz",
        "https://iptv-epg.org/files/epg-us.xml.gz",
    ]
    lines.append(f'#EXTM3U url-tvg="{",".join(epg_urls)}"')

    entries = [
        ("ABCNewsLive.us", "ABC News Live",
         "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
         "https://linear-abcnews-ftc-na-west-1.media.dssott.com/dvt2=exp=1782027960~url=%2Flas1%2Fva01%2Fdisneyplus%2Fchannel%2F79449312-79dd-473d-873c-515ebf4b5e5f-1781164031838%2F~psid=67e9c2c6-8b6f-46eb-ac25-b092aebcfc48~did=60cc5ba4-d239-4e53-9027-0eeca599bbe1~country=US~kid=k02~hmac=6fae53df7f42b5d77852deed449676732e6d208b6148ac6b4d043ed1af196c47/las1/va01/disneyplus/channel/79449312-79dd-473d-873c-515ebf4b5e5f-1781164031838/ctr-all-hdri-sliding.m3u8?r=1080&v=1&hash=81fb88da5aab33fe54dc3f8d7ae5f0b2eaa56a8c"),
        ("FoxNewsChannel.us", "Fox News Channel",
         "https://a57.foxnews.com/static/foxnews/fox-news-logo.jpg",
         "https://247.foxnews.com/hls/live/2003586/FNCHLSv3/master.m3u8?hdnea=exp=1781945161~acl=/*~hmac=d6a287e613a62c1292dcbf4013f502a0ace7383b40b111cfd8b0df3569cb034c"),
        ("FoxBusiness.us", "Fox Business",
         "https://a57.foxnews.com/static/foxnews/fox-business-logo.jpg",
         "https://247.foxbusiness.com/hls/live/2003756/FBNHLSv3/master.m3u8?hdnea=exp=1781945161~acl=/*~hmac=d6a287e613a62c1292dcbf4013f502a0ace7383b40b111cfd8b0df3569cb034c"),
        ("CBSNews.us", "CBS News 24/7",
         "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
         "https://dai.google.com/linear/hls/pa/event/Sid4xiTQTkCT1SLu6rjUSQ/stream/37b58280-3f79-4c7b-8d02-bf68897eccfd:ATL/master.m3u8"),
    ]

    for ch_id, ch_name, logo, url in entries:
        lines.append(f'#EXTINF:-1 tvg-id="{ch_id}" tvg-name="{ch_name}" tvg-logo="{logo}" group-title="NEWS WORLD",{ch_name}')
        lines.append(url)

    return '\n'.join(lines) + '\n'

# ─── VALIDATE EPG ─────────────────────────────────────────────────
def validate_epg(filepath):
    tree = ET.parse(filepath)
    root = tree.getroot()

    channels = {ch.get('id') for ch in root.findall('.//channel')}
    programmes = root.findall('.//programme')

    today = NOW.strftime('%Y%m%d')
    tomorrow = (NOW + timedelta(days=1)).strftime('%Y%m%d')
    after = (NOW + timedelta(days=2)).strftime('%Y%m%d')

    prog_by_date = {today: 0, tomorrow: 0, after: 0}
    prog_by_ch = {}

    for prog in programmes:
        start = prog.get('start', '')
        date = start[:8]
        ch_id = prog.get('channel', '')
        prog_by_ch[ch_id] = prog_by_ch.get(ch_id, 0) + 1
        if date in prog_by_date:
            prog_by_date[date] += 1

    report = []
    report.append("=" * 55)
    report.append("  RELATÓRIO DE VALIDAÇÃO EPG")
    report.append("=" * 55)
    report.append(f"  Geração: {NOW.strftime('%d/%m/%Y %H:%M')}")
    report.append(f"  Canais no EPG: {len(channels)}")
    report.append(f"  Programações totais: {len(programmes)}")
    report.append("")
    report.append("  --- Programações por data ---")
    all_ok = True
    for d in [today, tomorrow, after]:
        count = prog_by_date.get(d, 0)
        d_fmt = f"{d[6:8]}/{d[4:6]}/{d[:4]}"
        status = "OK" if count >= 6 else "FALHOU"
        if count < 6:
            all_ok = False
        report.append(f"    {d_fmt}: {count} programas [{status}]")

    report.append("")
    report.append("  --- Programações por canal ---")
    for ch, count in sorted(prog_by_ch.items()):
        report.append(f"    {ch}: {count} programas")

    report.append("")
    report.append("  --- Datas cobertas ---")
    sample_dates = sorted(set(p.get('start', '')[:8] for p in programmes))
    for d in sample_dates:
        d_fmt = f"{d[6:8]}/{d[4:6]}/{d[:4]}"
        count = prog_by_date.get(d, 0)
        report.append(f"    {d_fmt}: {count} programas")
    report.append("")
    report.append(f"  Hoje ({today[6:8]}/{today[4:6]}/{today[:4]}): {prog_by_date.get(today, 0)} programas")
    report.append(f"  Amanhã ({tomorrow[6:8]}/{tomorrow[4:6]}/{tomorrow[:4]}): {prog_by_date.get(tomorrow, 0)} programas")
    report.append(f"  Depois ({after[6:8]}/{after[4:6]}/{after[:4]}): {prog_by_date.get(after, 0)} programas")
    report.append("=" * 55)
    return '\n'.join(report)

# ─── MAIN ─────────────────────────────────────────────────────────
def main():
    print("Gerando EPG atualizado (3 dias)...")
    root = generate_epg()
    tree = ET.ElementTree(root)
    ET.indent(tree, space='  ')

    epg_xml = 'lista5_epg_atualizado.xml'
    epg_gz = 'lista5_epg_atualizado.xml.gz'

    tree.write(epg_xml, encoding='UTF-8', xml_declaration=True)
    with open(epg_xml, 'rb') as f_in:
        with gzip.open(epg_gz, 'wb') as f_out:
            f_out.writelines(f_in)

    print(f"EPG XML: {epg_xml}")
    print(f"EPG GZ:  {epg_gz}")
    print()

    print("Gerando M3U corrigido...")
    m3u_content = generate_m3u()
    m3u_path = 'lista5.m3u'
    with open(m3u_path, 'w', encoding='utf-8') as f:
        f.write(m3u_content)

    # Backup original
    bak_path = f'lista5.m3u.bak.{NOW.strftime("%Y%m%d_%H%M%S")}'
    if os.path.exists('lista5_backup_original.m3u'):
        pass
    with open(m3u_path, 'r') as f:
        print(f"M3U atualizado: {m3u_path} ({len(f.read())} bytes, 4 canais)")
    print()
    print(validate_epg(epg_xml))

if __name__ == '__main__':
    main()
