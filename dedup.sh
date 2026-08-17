#!/bin/bash

INPUT_FILE="lista5.m3u"

declare -A seen_channels
output=""

while IFS= read -r line; do
    if [[ "$line" == \#EXTM3U ]]; then
        output+="$line"$'\n'
        continue
    fi
    
    if [[ "$line" == \#EXTINF:* ]]; then
        extinf="$line"
    elif [[ -n "$extinf" && "$line" != \#EXTM3U && -n "$line" ]]; then
        channel_name=$(echo "$extinf" | grep -oP 'group-title="[^"]*",.*$' | sed 's/^.*",//')
        
        if [[ -z "${seen_channels[$channel_name]+x}" ]]; then
            seen_channels["$channel_name"]=1
            output+="$extinf"$'\n'
            output+="$line"$'\n'
        fi
        
        extinf=""
    fi
done < "$INPUT_FILE"

echo -n "$output" > "$INPUT_FILE"

echo "Deduplicação concluída. Canais únicos mantidos: ${#seen_channels[@]}"