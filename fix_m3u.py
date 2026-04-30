#!/usr/bin/env python3
"""Fix ESTADOS UNIDOS RESERVA.m3u - Corrected version"""
import xml.etree.ElementTree as ET
import re

tree = ET.parse('/tmp/guide.xml')
root = tree.getroot()
epg_channels = {}
for ch in root.findall('channel'):
    cid = ch.get('id')
    names = [dn.text for dn in ch.findall('display-name')]
    icon = ch.find('icon')
    icon_src = icon.get('src') if icon is not None else ''
    epg_channels[cid] = {'names': names, 'icon': icon_src}

TVPASS_TO_EPG = {
    'CNN': 'I202.58646.schedulesdirect.org', 'FoxNewsChannel': 'I360.60179.schedulesdirect.org',
    'MSNBC': 'I356.58639.schedulesdirect.org', 'CNBC': 'I355.58780.schedulesdirect.org',
    'BloombergTV': 'I353.14755.schedulesdirect.org', 'HLN': 'I204.64549.schedulesdirect.org',
    'FoxBusiness': 'I359.58718.schedulesdirect.org', 'NewsmaxTV': 'I349.87925.schedulesdirect.org',
    'CSPAN': 'I350.10161.schedulesdirect.org', 'CSPAN2': 'I351.10162.schedulesdirect.org',
    'AEEast': 'I265.51529.schedulesdirect.org', 'AMCEast': 'I254.58574.schedulesdirect.org',
    'AmericanHeroesChannel': 'I287.78808.schedulesdirect.org', 'AnimalPlanetEast': 'I282.57394.schedulesdirect.org',
    'BBCAmericaEast': 'I264.64492.schedulesdirect.org', 'BBCWorldNewsNorthAmerica': 'I1007.68053.schedulesdirect.org',
    'BETEast': 'I329.63236.schedulesdirect.org', 'BETHerEast': 'I330.14897.schedulesdirect.org',
    'BravoEast': 'I237.58625.schedulesdirect.org', 'CartoonNetworkEast': 'I296.12131.schedulesdirect.org',
    'CinemaxEast': 'I515.10120.schedulesdirect.org', 'CMTEast': 'I327.59440.schedulesdirect.org',
    'ComedyCentralEast': 'I249.62420.schedulesdirect.org', 'CrimePlusInvestigation': 'I284.57390.schedulesdirect.org',
    'DestinationAmerica': 'I286.60468.schedulesdirect.org', 'DiscoveryChannelEast': 'I278.56905.schedulesdirect.org',
    'DiscoveryFamily': 'I294.67749.schedulesdirect.org', 'DiscoveryLife': 'I261.16125.schedulesdirect.org',
    'DisneyChannelEast': 'I290.59684.schedulesdirect.org', 'DisneyJuniorEast': 'I289.74885.schedulesdirect.org',
    'DisneyXDEast': 'I292.60006.schedulesdirect.org', 'EEast': 'I236.61812.schedulesdirect.org',
    'FoodNetworkEast': 'I232.68065.schedulesdirect.org', 'FreeformEast': 'I311.59615.schedulesdirect.org',
    'FuseEast': 'I339.59116.schedulesdirect.org', 'FXMovieChannel': 'I258.70253.schedulesdirect.org',
    'FXEast': 'I248.58574.schedulesdirect.org', 'FXXEast': 'I259.66379.schedulesdirect.org',
    'FYIEast': 'I266.58988.schedulesdirect.org', 'game-show-network-east': 'I233.14909.schedulesdirect.org',
    'GolfChannel': 'I218.61854.schedulesdirect.org', 'HallmarkChannelEast': 'I312.66268.schedulesdirect.org',
    'HallmarkDrama': 'I564.105723.schedulesdirect.org', 'HallmarkMoviesMysteriesEast': 'I565.46710.schedulesdirect.org',
    'HBOEast': 'I501.19548.schedulesdirect.org', 'HBO2East': 'I547.58533.schedulesdirect.org',
    'HBOComedyEast': 'I506.59839.schedulesdirect.org', 'HBOFamilyEast': 'I506.59839.schedulesdirect.org',
    'HBOSignatureEast': 'I506.59839.schedulesdirect.org', 'HBOZoneEast': 'I506.59839.schedulesdirect.org',
    'HGTVEast': 'I229.49788.schedulesdirect.org', 'HistoryEast': 'I269.57708.schedulesdirect.org',
    'IFCEast': 'I333.59444.schedulesdirect.org', 'InvestigationDiscoveryEast': 'I285.65342.schedulesdirect.org',
    'IONTVEast': 'I305.76894.schedulesdirect.org', 'LifetimeMoviesEast': 'I253.55887.schedulesdirect.org',
    'LifetimeEast': 'I252.60150.schedulesdirect.org', 'LogoEast': 'I272.46762.schedulesdirect.org',
    'MoreMaxEast': 'I517.59373.schedulesdirect.org', 'Motortrend': 'I281.31046.schedulesdirect.org',
    'MovieMaxEast': 'I535.36225.schedulesdirect.org', 'MTVEast': 'I331.10986.schedulesdirect.org',
    'mtv-2-east': 'I332.16361.schedulesdirect.org', 'NationalGeographicEast': 'I276.49438.schedulesdirect.org',
    'NationalGeographicWildEast': 'I283.67331.schedulesdirect.org', 'NickJrEast': 'I301.82649.schedulesdirect.org',
    'NickelodeonEast': 'I299.59432.schedulesdirect.org', 'NicktoonsEast': 'I302.30420.schedulesdirect.org',
    'OWNEast': 'I279.70388.schedulesdirect.org', 'OutdoorChannel': 'I606.14776.schedulesdirect.org',
    'OxygenEast': 'I251.70522.schedulesdirect.org', 'Reelz': 'I238.68385.schedulesdirect.org',
    'Science': 'I284.57390.schedulesdirect.org', 'ShowtimeEast': 'I545.21868.schedulesdirect.org',
    'Showtime2East': 'I547.58533.schedulesdirect.org', 'StarzEast': 'I525.34941.schedulesdirect.org',
    'SundanceTVEast': 'I239.71280.schedulesdirect.org', 'SyfyEast': 'I244.58623.schedulesdirect.org',
    'TBSEast': 'I247.58515.schedulesdirect.org', 'TeenNickEast': 'I682.72294.schedulesdirect.org',
    'TelemundoEast': 'I402.68049.schedulesdirect.org', 'CookingChannel': 'I232.68065.schedulesdirect.org',
    'TennisChannel': 'I217.60316.schedulesdirect.org', 'TheWeatherChannel': 'I362.11187.schedulesdirect.org',
    'TLCEast': 'I697.107373.schedulesdirect.org', 'TheMovieChannelEast': 'I534.91029.schedulesdirect.org',
    'TNTEast': 'I245.42642.schedulesdirect.org', 'TravelChannelEast': 'I277.11180.schedulesdirect.org',
    'truTVEast': 'I246.64490.schedulesdirect.org', 'TCMEast': 'I256.64312.schedulesdirect.org',
    'tv-land-eastern': 'I304.73541.schedulesdirect.org', 'TVOne': 'I328.61960.schedulesdirect.org',
    'UniversalKidsEast': 'I292.60006.schedulesdirect.org', 'UnivisionEast': 'I402.68049.schedulesdirect.org',
    'USANetworkEast': 'I242.58452.schedulesdirect.org', 'VH1East': 'I335.11218.schedulesdirect.org',
    'VICETV': 'I271.65732.schedulesdirect.org', 'WeTVEast': 'I260.16409.schedulesdirect.org',
    'paramount-network-us': 'I241.59186.schedulesdirect.org',
    'ESPN': 'I206.10179.schedulesdirect.org', 'espn-deportes': 'I466.71914.schedulesdirect.org',
    'ESPNews': 'I207.16485.schedulesdirect.org', 'ESPNU': 'I208.45654.schedulesdirect.org',
    'ESPN2': 'I209.12444.schedulesdirect.org', 'BTN': 'I610.58321.schedulesdirect.org',
    'ACCNetwork': 'I612.111905.schedulesdirect.org', 'SECN': 'I611.89535.schedulesdirect.org',
    'CBSSportsNetworkUSA': 'I221.59250.schedulesdirect.org', 'FoxSports1': 'I219.82547.schedulesdirect.org',
    'FoxSports2': 'I618.59305.schedulesdirect.org', 'NBATV': 'I216.45526.schedulesdirect.org',
    'NFLNetwork': 'I212.45399.schedulesdirect.org', 'NFLRedZone': 'I211.65025.schedulesdirect.org',
    'NHLNetwork': 'I215.58570.schedulesdirect.org', 'MLBNetwork': 'I213.62081.schedulesdirect.org',
    'tsn1': 'I400.11182.schedulesdirect.org', 'tsn2': 'I401.18990.schedulesdirect.org',
    'tsn3': 'I402.90118.schedulesdirect.org', 'tsn4': 'I403.90122.schedulesdirect.org',
    'tsn5': 'I404.90124.schedulesdirect.org',
    'sportsnet-one': 'I409.68858.schedulesdirect.org', 'sportsnet-360': 'I410.49952.schedulesdirect.org',
    'sportsnet-east': 'I406.18798.schedulesdirect.org', 'sportsnet-ontario': 'I405.62111.schedulesdirect.org',
    'sportsnet-pacific': 'I407.18801.schedulesdirect.org', 'sportsnet-west': 'I408.18800.schedulesdirect.org',
    'sportsnet-pittsburgh': 'I428.49882.gracenote.com',
    'marquee-sports-network': 'I202.116034.gracenote.com',
    'msg-madison-square-gardens': 'I433.34999.gracenote.com', 'msg-plus': 'I433.34999.gracenote.com',
    'monumental-sports-network': 'I424.32537.gracenote.com',
    'new-england-sports-network': 'I434.35038.gracenote.com', 'nbc-sports-boston': 'I434.35038.gracenote.com',
    'nbc-sports-bay-area': 'I437.35035.gracenote.com', 'nbc-sports-california': 'I437.35036.gracenote.com',
    'nbc-sports-philadelphia': 'I437.35037.gracenote.com',
    'sny-sportsnet-new-york-comcast': 'I202.116035.gracenote.com',
    'yes-network': 'I1702.46275.gracenote.com', 'altitude-sports-denver': 'I413.65596.gracenote.com',
    'chicago-sports-network': 'I25.183131.gracenote.com', 'midatlantic-sports-network': 'I433.35039.gracenote.com',
    'space-city-home-network': 'I433.35040.gracenote.com',
    'Boomerang': 'I298.21883.schedulesdirect.org',
    'fanduel-sports-network-florida': 'I1720.50728.gracenote.com',
    'fanduel-sports-network-detroit-hd': 'I1748.50728.gracenote.com',
    'fanduel-sports-network-great-lakes': 'I1748.50728.gracenote.com',
    'fanduel-sports-network-north': 'I1748.50728.gracenote.com',
    'fanduel-sports-network-ohio-cleveland': 'I1748.50728.gracenote.com',
    'fanduel-sports-network-oklahoma': 'I1753.35295.gracenote.com',
    'fanduel-sports-network-san-diego': 'I1774.59625.gracenote.com',
    'fanduel-sports-network-socal': 'I1774.59625.gracenote.com',
    'fanduel-sports-network-south-carolinas': 'I1724.75970.gracenote.com',
    'fanduel-sports-network-south-tennessee-usa': 'I1724.75970.gracenote.com',
    'fanduel-sports-network-west': 'I1772.59627.gracenote.com',
    'fanduel-sports-network-wisconsin': 'I1748.50728.gracenote.com',
    'fanduel-sports-indiana': 'I1748.50728.gracenote.com',
    'fanduel-sports-southeast-georgia': 'I1724.75970.gracenote.com',
    'fanduel-sports-southeast-north-carolina': 'I1724.75970.gracenote.com',
    'fanduel-sports-southeast-south-carolina': 'I1724.75970.gracenote.com',
    'fanduel-sports-southeast-tennessee-nashville': 'I1724.75970.gracenote.com',
    'fanduel-sports-tennessee-east': 'I1724.75970.gracenote.com',
    'fanduel-sports-sun': 'I1720.50728.gracenote.com',
    'spectrum-sportsnet-la': 'I560.74074.schedulesdirect.org',
    'spectrum-sportsnet': 'I560.74075.schedulesdirect.org',
    'metv-toons': 'I431.121328.gracenote.com', 'metv-wjlp-new-jerseynew-york': 'I430.25399.gracenote.com',
    'meganoticias': 'I729.60855.schedulesdirect.org',
}

def get_epg_id(url):
    if 'tvpass.org/live/' in url:
        slug = url.split('tvpass.org/live/')[1].split('/')[0]
        return TVPASS_TO_EPG.get(slug, '')
    return ''

def get_epg_icon(epg_id):
    if epg_id and epg_id in epg_channels:
        return epg_channels[epg_id].get('icon', '')
    return ''

def logo_from_id(epg_id):
    if not epg_id:
        return ''
    m = re.search(r'[./](\d{4,})\.', epg_id)
    if m:
        return f'https://schedulesdirect-api20141201-logos.s3.dualstack.us-east-1.amazonaws.com/stationLogos/s{m.group(1)}_dark_360w_270h.png'
    m = re.search(r'[./](\d+)\.', epg_id)
    if m:
        return f'https://zpmc.tmsimg.com/h3/NowShowing/{m.group(1)}/s{m.group(1)}_ll_h15_ab.png'
    return ''

def get_channel_name(extinf):
    """Extract channel name from EXTINF line - finds FIRST comma OUTSIDE quotes"""
    in_quotes = False
    for i, c in enumerate(extinf):
        if c == '"':
            in_quotes = not in_quotes
        elif c == ',' and not in_quotes:
            return extinf[i + 1:].strip()
    return 'Unknown'

def get_attr(extinf, attr):
    """Extract attribute value from EXTINF line"""
    m = re.search(rf'{attr}="([^"]*)"', extinf)
    return m.group(1) if m else ''

with open('/home/runner/work/JCTV/JCTV/ESTADOS UNIDOS RESERVA.m3u', 'r') as f:
    content = f.read()

entries = []
current_extinf = None
current_url = None
for line in content.strip().split('\n'):
    line = line.strip()
    if line.startswith('#EXTM3U'):
        continue
    elif line.startswith('#EXTINF'):
        if current_extinf and current_url:
            entries.append((current_extinf, current_url))
        current_extinf = line
        current_url = None
    elif line and not line.startswith('#'):
        current_url = line
if current_extinf and current_url:
    entries.append((current_extinf, current_url))

print(f"Parsed: {len(entries)} entries")

DEAD = ['turnerlive.warnermediacdn.com', 'mdc.ott.alticeusa.net']
seen = set()
fixed = []
removed = 0

for extinf, url in entries:
    if not url or url.strip() == '':
        removed += 1; continue
    if any(p in url for p in DEAD):
        removed += 1; continue
    if url in seen:
        removed += 1; continue
    seen.add(url)

    channel_name = get_channel_name(extinf)
    tvg_name = get_attr(extinf, 'tvg-name') or channel_name
    epg_id = get_epg_id(url)
    icon = get_epg_icon(epg_id) or logo_from_id(epg_id)
    icon = icon.replace('"', '')

    new_extinf = f'#EXTINF:-1 tvg-id="{epg_id}" tvg-name="{tvg_name}" tvg-logo="{icon}",{channel_name}'
    fixed.append((new_extinf, url))

fixed.append((
    '#EXTINF:-1 tvg-id="" tvg-name="NewsNation SD" tvg-logo="https://upload.wikimedia.org/wikipedia/commons/thumb/1/1a/NewsNation_logo.svg/320px-NewsNation_logo.svg.png",NewsNation SD',
    'https://tvpass.org/live/NewsNation/sd'
))
fixed.append((
    '#EXTINF:-1 tvg-id="" tvg-name="NewsNation HD" tvg-logo="https://upload.wikimedia.org/wikipedia/commons/thumb/1/1a/NewsNation_logo.svg/320px-NewsNation_logo.svg.png",NewsNation HD',
    'https://tvpass.org/live/NewsNation/hd'
))

print(f"Removed: {removed}, Kept: {len(fixed)}")

out = ['#EXTM3U x-tvg-url="https://raw.githubusercontent.com/acidjesuz/EPGTalk/master/guide.xml.gz"']
for extinf, url in fixed:
    out.append(extinf)
    out.append(url)

with open('/home/runner/work/JCTV/JCTV/ESTADOS UNIDOS RESERVA.m3u', 'w') as f:
    f.write('\n'.join(out) + '\n')

print(f"Written {len(fixed)} channels")

print("\n=== MegaNoticias ===")
for extinf, url in fixed:
    if 'meganoticias' in extinf.lower() or 'meganoticias' in url.lower():
        print(f"  {extinf}")
        print(f"  {url}")
        break

print("\n=== ABC channels (verify no corruption) ===")
for extinf, url in fixed:
    if 'ABC' in extinf or 'abc' in url:
        print(f"  {extinf[:120]}...")
        print(f"  {url}")
