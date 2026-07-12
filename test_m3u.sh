#!/bin/bash

input="lista5.m3u"
output="lista5_new.m3u"

# Parse M3U properly: each group is EXTINF line + URL line(s) until next EXTINF or EOF
declare -a extinf_lines=()
declare -a url_lines=()

current_extinf=""
current_urls=()

while IFS= read -r line || [ -n "$line" ]; do
    if [[ $line == \#EXTM3U* ]]; then
        continue
    elif [[ $line == \#EXTINF:* ]]; then
        if [ -n "$current_extinf" ]; then
            extinf_lines+=("$current_extinf")
            url_lines+=("${current_urls[*]}")
        fi
        current_extinf="$line"
        current_urls=()
    elif [[ $line == https://* ]] || [[ $line == http://* ]]; then
        current_urls+=("$line")
    fi
done < "$input"
# Last group
if [ -n "$current_extinf" ]; then
    extinf_lines+=("$current_extinf")
    url_lines+=("${current_urls[*]}")
fi

echo "Total groups: ${#extinf_lines[@]}"

# For each group, test only the FIRST URL (the master/playlist) and mark group as good/bad
declare -a good_groups=()

for idx in "${!extinf_lines[@]}"; do
    extinf="${extinf_lines[$idx]}"
    IFS=' ' read -ra urls <<< "${url_lines[$idx]}"
    first_url="${urls[0]}"
    
    # Extract name from EXTINF (after last comma)
    name="${extinf##*,}"
    
    echo -n "[$((idx+1))/${#extinf_lines[@]}] $name ... "
    
    # Test first URL
    http_code=$(curl -o /dev/null -s -w "%{http_code}" --connect-timeout 5 --max-time 10 -L "$first_url" 2>/dev/null)
    
    if [ "$http_code" = "200" ] || [ "$http_code" = "206" ]; then
        echo "OK ($http_code)"
        good_groups+=($idx)
    else
        echo "FAIL ($http_code) - REMOVING"
    fi
done

echo ""
echo "Working groups: ${#good_groups[@]} of ${#extinf_lines[@]}"
echo ""

# Write new M3U
{
    echo "#EXTM3U"
    for idx in "${good_groups[@]}"; do
        echo "${extinf_lines[$idx]}"
        IFS=' ' read -ra urls <<< "${url_lines[$idx]}"
        for url in "${urls[@]}"; do
            echo "$url"
        done
    done
} > "$output"

echo "Written to $output"

# Compare
echo "Original: $(wc -l < $input) lines"
echo "New:      $(wc -l < $output) lines"
