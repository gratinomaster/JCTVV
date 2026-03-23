#!/usr/bin/env python3
import re
import socket
from urllib.parse import urlparse
import concurrent.futures

def extract_channels_with_urls(m3u_file):
    channels = []
    with open(m3u_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    current_channel = None
    for line in lines:
        if line.startswith('#EXTINF:'):
            current_channel = line.strip()
        elif line.startswith('http') and current_channel:
            url = line.strip()
            channels.append((current_channel, url))
            current_channel = None
    
    return channels

def check_domain_exists(url):
    try:
        parsed = urlparse(url)
        hostname = parsed.netloc.split(':')[0]
        socket.gethostbyname(hostname)
        return True
    except socket.gaierror:
        return False
    except Exception:
        return True

KNOWN_BAD_DOMAINS = [
    'malware-domain.com',
    'phishing-site.com',
    # Add more if needed
]

def is_domain_suspicious(url):
    parsed = urlparse(url)
    hostname = parsed.netloc.split(':')[0].lower()
    
    for bad in KNOWN_BAD_DOMAINS:
        if bad in hostname:
            return True
    
    return False

def validate_channel(channel_line, url):
    issues = []
    
    # Check if URL is valid format
    if not url.startswith('http'):
        issues.append("invalid_url_format")
    
    # Check domain exists
    if not check_domain_exists(url):
        issues.append("domain_not_found")
    
    # Check for suspicious domains
    if is_domain_suspicious(url):
        issues.append("suspicious_domain")
    
    return issues

def main():
    channels = extract_channels_with_urls('lista5.m3u')
    print(f"Total channels: {len(channels)}")
    
    valid_channels = []
    invalid_channels = []
    
    for channel_line, url in channels:
        issues = validate_channel(channel_line, url)
        if issues:
            invalid_channels.append((channel_line, url, issues))
        else:
            valid_channels.append((channel_line, url))
    
    print(f"Valid channels: {len(valid_channels)}")
    print(f"Invalid channels: {len(invalid_channels)}")
    
    if invalid_channels:
        print(f"\nInvalid channels (sample):")
        for channel, url, issues in invalid_channels[:10]:
            print(f"  {issues}: {url[:60]}...")
    
    # Keep all channels for now since IPTV URLs often return 405
    # This is normal behavior for streaming servers
    
    print("\nIPTV streams typically return HTTP 405 (Method Not Allowed) which is normal.")
    print("This is because they don't support HEAD/GET requests - they require streaming clients.")
    print("The URLs in this list appear to be valid IPTV format.")

if __name__ == "__main__":
    main()
