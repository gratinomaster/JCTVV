#!/usr/bin/env python3
import re
import requests
from datetime import datetime

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Try to find and add a relevant open TV channel
# Common ones: RecordTV, Globo (different feeds), SBT variations, etc.
m3u_path = '/home/runner/work/JCTVV/JCTVV/CABOBRASIL.m3u'
with open(m3u_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Check if we already have Record TV
if 'RecordTV' not in content and 'Record.br' not in content:
    # Try to add Record TV
    candidates = [
        {
            'extinf': '#EXTINF:-1 tvg-id="Record.br" tvg-name="RecordTV" tvg-logo="https://iptv-epg.org/images/OzF7kxJ7GDpi4gIS5jhY7rTNJ6XaXw8QqUxazuN_pboR6a3cWUD3DShshABx9-O3nDbygJZiI898whmS57M4ijfaTLpLlYbaehnMSBQWsi0wirU" group-title="TV ABERTA",RecordTV',
            'url': 'https://playplusspo-lh.akamaihd.net/i/pp_sp@350176/index_720_av-p.m3u8'  # Example, might not work
        }
    ]
    # Better approach - test some common URLs
    record_urls = [
        'https://cdn.jmvstream.com/w/LVW-10842/LVW10842_513N26MDBL/playlist.m3u8',
        'https://5cf4a2c2512a2.streamlock.net/rbatv/rbatv/playlist.m3u8',
    ]
    for url in record_urls:
        try:
            headers = {'User-Agent': 'VLC/3.0.18'}
            r = requests.head(url, headers=headers, timeout=5, verify=False, allow_redirects=True)
            if r.status_code < 400:
                # Add it
                content += f'\n{candidates[0]["extinf"]}\n{url}\n'
                print(f'Added RecordTV: {url}')
                break
        except:
            continue
    else:
        print('Could not find working RecordTV URL')

with open(m3u_path, 'w', encoding='utf-8') as f:
    f.write(content)
