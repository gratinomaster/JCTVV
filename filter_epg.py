import gzip, re, urllib.request

MANUAL_MAP = {
    "DW News English": "DW.English.HD.il",
    "BBC News": "65d92a8c8b24c80008e285c0",
    "CNN International": "CNN.International.fr",
    "France 24 English": "France.24.fr",
    "CBS News 24/7": "CBS.News.us",
    "Bloomberg TV": "BLOOMBERG TV",
    "Al Jazeera English": "Al.Jazeera.English.es",
    "Sky News": "55b285cd2665de274553d66f",
    "Newsmax": "Newsmax.us",
    "Euronews English": "Euronews.fr",
    "Africa 24 English": "Africa.24.fr",
    "TRT World": "TRT.WORLD.tr",
    "CGTN": "CGTN",
    "NDTV 24x7": "NDTV.24x7.in",
    "CGTN Francais": "CGTN",
    "DW Espanol": "DW.pt",
    "Bloomberg Asia": "BLOOMBERG TV",
    "CNA": "Channel.News.Asia.id",
    "Al Jazeera Arabic": "AL.JAZEERA.ARABIC.tr",
    "NHK World-Japan": "NHK.World.TV.pt",
    "France 24 Français": "France.24.fr",
}

# Fetch M3U
req = urllib.request.urlopen('https://github.com/gratinomaster/JCTV/raw/refs/heads/main/NEWSWORLDNOVOS.m3u')
m3u = req.read().decode()

# Extract M3U channel display names
m3u_names = {}
for line in m3u.split('\n'):
    if line.startswith('#EXTINF:'):
        parts = line.rsplit(',', 1)
        if len(parts) > 1:
            name = parts[1].strip()
            if name:
                m3u_names[name] = True

# Read original EPG XML
with gzip.open('EPGFULL.xml.gz', 'rt', encoding='utf-8') as f:
    xml = f.read()

# Match M3U channels to EPG IDs
matched_ids = set()
for m3u_name in m3u_names:
    matched = False
    for pattern, epg_id in MANUAL_MAP.items():
        if pattern.lower() in m3u_name.lower():
            matched_ids.add(epg_id)
            print(f"MATCH: '{m3u_name}' -> '{epg_id}'")
            matched = True
            break
    if not matched:
        print(f"NO MATCH: '{m3u_name}'")

print(f"\nTotal matched channels: {len(matched_ids)}")
print(f"Matched IDs: {sorted(matched_ids)}")

# Extract channel blocks for matched IDs
channel_pattern = re.compile(r'<channel id="([^"]+)">(.*?)</channel>', re.DOTALL)
channels_xml = ''
for m in channel_pattern.finditer(xml):
    if m.group(1) in matched_ids:
        channels_xml += m.group(0) + '\n'

# Extract programme blocks for matched channels
programme_pattern = re.compile(r'<programme[^>]*channel="([^"]+)"[^>]*>.*?</programme>', re.DOTALL)
programmes_xml = ''
for m in programme_pattern.finditer(xml):
    if m.group(1) in matched_ids:
        programmes_xml += m.group(0) + '\n'

# Get XML header (everything before the first <channel> or <programme>)
header_end = xml.find('<channel ')
if header_end == -1:
    header_end = xml.find('<programme ')
header = xml[:header_end]

# Build filtered XML
filtered_xml = header + '\n' + channels_xml + programmes_xml + '</tv>'

# Write gzipped output (overwrite)
with gzip.open('EPGFULL.xml.gz', 'wt', encoding='utf-8') as f:
    f.write(filtered_xml)

ch_count = filtered_xml.count('<channel ')
pr_count = filtered_xml.count('<programme ')
print(f"\nOutput: {ch_count} channels, {pr_count} programmes")
print(f"Size: {len(filtered_xml)} bytes uncompressed")
