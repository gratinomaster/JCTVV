#!/bin/bash

INPUT="lista5.m3u"
OUTPUT="lista5_clean.m3u"
TIMEOUT=10

# Parse M3U and deduplicate by channel name
declare -A seen_channels
declare -a keep_extinf=()
declare -a keep_urls=()

current_extinf=""
current_url=""

while IFS= read -r line; do
    if [[ "$line" == "#EXTINF:"* ]]; then
        current_extinf="$line"
        # Extract channel name (after last comma)
        channel_name="${line##*,}"
        # Trim whitespace
        channel_name=$(echo "$channel_name" | xargs)
    elif [[ "$line" == http* ]]; then
        current_url="$line"
        if [[ -n "$current_extinf" ]] && [[ -n "$current_url" ]]; then
            # Create a key based on channel name
            key="$channel_name"
            if [[ -z "${seen_channels[$key]}" ]]; then
                seen_channels[$key]=1
                keep_extinf+=("$current_extinf")
                keep_urls+=("$current_url")
                echo "MANTENDO: $channel_name"
            else
                echo "DUPLICATA REMOVIDA: $channel_name"
            fi
        fi
        current_extinf=""
        current_url=""
    fi
done < "$INPUT"

# Write deduplicated list
echo "#EXTM3U" > "$OUTPUT"
for i in "${!keep_extinf[@]}"; do
    echo "${keep_extinf[$i]}" >> "$OUTPUT"
    echo "${keep_urls[$i]}" >> "$OUTPUT"
done

echo ""
echo "Original: $(wc -l < "$INPUT") linhas"
echo "Limpa:    $(wc -l < "$OUTPUT") linhas"
echo "Canais mantidos: ${#keep_extinf[@]}"
