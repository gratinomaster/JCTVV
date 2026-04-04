#!/bin/bash
# Extract all channel IDs from EPG
curl -s "https://raw.githubusercontent.com/globetvapp/epg/main/Venezuela/venezuela1.xml" | grep -oP 'channel id="[^"]*"' | sed 's/channel id="//;s/"$//' | sort -u > /tmp/epg_channels.txt
echo "Total unique channels in EPG:"
wc -l < /tmp/epg_channels.txt
