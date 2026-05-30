#!/usr/bin/env python3
"""Filter EPGFULL.xml.gz to only include channels present in the M3U playlist."""

import gzip
import re
import xml.etree.ElementTree as ET
from collections import OrderedDict

M3U_FILE = "/home/runner/work/JCTV/JCTV/NEWSWORLDNOVOS.m3u"
INPUT_EPG = "/home/runner/work/JCTV/JCTV/EPGFULL.xml.gz"
OUTPUT_EPG = "/home/runner/work/JCTV/JCTV/EPGFULL.xml.gz"

def get_tvg_ids(m3u_path):
    with open(m3u_path, 'r') as f:
        content = f.read()
    return set(re.findall(r'tvg-id="([^"]+)"', content))

def filter_epg(input_path, output_path, valid_ids):
    # Read the full XML
    with gzip.open(input_path, 'rt', encoding='utf-8') as f:
        xml_content = f.read()
    
    # Instead of XML parsing (which can be fragile), let's use regex/string processing
    # But first try to parse properly
    tree = ET.ElementTree(ET.fromstring(xml_content))
    root = tree.getroot()
    
    # Build new XML
    new_root = ET.Element('tv')
    
    channels_found = 0
    programmes_found = 0
    
    for child in root:
        if child.tag == 'channel':
            ch_id = child.get('id')
            if ch_id in valid_ids:
                new_root.append(child)
                channels_found += 1
        elif child.tag == 'programme':
            prog_ch = child.get('channel')
            if prog_ch in valid_ids:
                new_root.append(child)
                programmes_found += 1
    
    print(f"Channels kept: {channels_found}")
    print(f"Programmes kept: {programmes_found}")
    
    # Serialize with proper formatting
    ET.indent(new_root, space="  ")
    xml_bytes = ET.tostring(new_root, encoding='utf-8', xml_declaration=True)
    
    with gzip.open(output_path, 'wt', encoding='utf-8') as f:
        f.write(xml_bytes.decode('utf-8'))
    
    print(f"Written to {output_path}")

if __name__ == '__main__':
    valid_ids = get_tvg_ids(M3U_FILE)
    print(f"Valid tvg-ids from M3U: {len(valid_ids)}")
    filter_epg(INPUT_EPG, OUTPUT_EPG, valid_ids)
