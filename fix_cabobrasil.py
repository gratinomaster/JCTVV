#!/usr/bin/env python3
import re
import os
import gzip
import shutil
from datetime import datetime
from urllib.parse import urlparse
import requests
from pathlib import Path

# Disable SSL warnings
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class M3UFixer:
    def __init__(self, m3u_path, epg_path=None):
        self.m3u_path = m3u_path
        self.backup_path = f"{m3u_path}.bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.epg_path = epg_path
        self.epg_data = None
        self.load_epg()
        
    def backup(self):
        shutil.copy2(self.m3u_path, self.backup_path)
        print(f"Backup created: {self.backup_path}")
        
    def load_epg(self):
        if self.epg_path and os.path.exists(self.epg_path):
            try:
                if self.epg_path.endswith('.gz'):
                    with gzip.open(self.epg_path, 'rt', encoding='utf-8', errors='ignore') as f:
                        self.epg_data = f.read()
                else:
                    with open(self.epg_path, 'r', encoding='utf-8', errors='ignore') as f:
                        self.epg_data = f.read()
                print(f"Loaded EPG: {self.epg_path}")
            except Exception as e:
                print(f"Error loading EPG: {e}")
    
    def parse_m3u(self):
        with open(self.m3u_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        return content
    
    def get_epg_channels(self):
        if not self.epg_data:
            return []
        channels = re.findall(r'<channel id="([^"]+)"', self.epg_data)
        return channels
    
    def has_programming_today(self, channel_id):
        if not self.epg_data:
            return False
        today = datetime.now().strftime('%Y%m%d')
        # Look for programmes for this channel starting today
        pattern = f'channel="{re.escape(channel_id)}"[^>]*start="{today}'
        return bool(re.search(pattern, self.epg_data))
    
    def test_url(self, url, timeout=5):
        try:
            headers = {'User-Agent': 'VLC/3.0.18 LibVLC/3.0.18'}
            # Try HEAD first
            response = requests.head(url, headers=headers, timeout=timeout, verify=False, allow_redirects=True)
            if response.status_code >= 400:
                # Try GET
                response = requests.get(url, headers=headers, timeout=timeout, verify=False, allow_redirects=True, stream=True)
                response.close()
            # Check for suspicious content
            if response.status_code >= 200 and response.status_code < 400:
                return True, response.status_code
            return False, response.status_code
        except Exception as e:
            return False, str(e)
    
    def test_image_url(self, url, timeout=5):
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.head(url, headers=headers, timeout=timeout, verify=False, allow_redirects=True)
            if response.status_code >= 400:
                response = requests.get(url, headers=headers, timeout=timeout, verify=False, allow_redirects=True, stream=True)
                response.close()
            content_type = response.headers.get('content-type', '')
            if '.svg' in url.lower() or 'svg' in content_type:
                return False, 'SVG not allowed'
            if response.status_code >= 200 and response.status_code < 400:
                return True, content_type
            return False, response.status_code
        except Exception as e:
            return False, str(e)

def main():
    fixer = M3UFixer('/home/runner/work/JCTVV/JCTVV/CABOBRASIL.m3u', 
                     '/home/runner/work/JCTVV/JCTVV/EPGFULL.xml.gz')
    fixer.backup()
    
    content = fixer.parse_m3u()
    
    # Find all channel entries
    lines = content.split('\n')
    result_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.strip().startswith('#EXTM3U'):
            result_lines.append(line)
            i += 1
            continue
        if line.strip().startswith('#EXTINF'):
            extinf = line
            # Get next non-empty line as URL
            j = i + 1
            while j < len(lines) and lines[j].strip() == '':
                j += 1
            if j < len(lines) and lines[j].strip().startswith('http'):
                url = lines[j].strip()
                # Test URL
                ok, status = fixer.test_url(url)
                if not ok:
                    print(f"Removing offline/bad channel: {extinf[:80]}... ({status})")
                    i = j + 1
                    continue
                # Check logo
                logo_match = re.search(r'tvg-logo="([^"]*)"', extinf)
                if not logo_match or not logo_match.group(1) or logo_match.group(1).strip() == '':
                    print(f"Channel without logo: {extinf[:60]}...")
                elif logo_match.group(1).lower().endswith('.svg'):
                    print(f"SVG logo found (will replace): {extinf[:60]}...")
                    # Try to replace with placeholder or skip - but need to keep channel
                else:
                    # Test image
                    logo_ok, logo_status = fixer.test_image_url(logo_match.group(1))
                    if not logo_ok:
                        print(f"Bad logo for: {extinf[:60]}... ({logo_status})")
                result_lines.append(extinf)
                result_lines.append(url)
                i = j + 1
                continue
            else:
                # EXTINF without URL - remove it
                print(f"Removing EXTINF without URL: {extinf[:80]}...")
                i += 1
                continue
        i += 1
    
    # Write back
    new_content = '\n'.join(result_lines)
    if not new_content.endswith('\n'):
        new_content += '\n'
    with open(fixer.m3u_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print(f"Updated {fixer.m3u_path}")

if __name__ == '__main__':
    main()
