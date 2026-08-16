#!/bin/bash

INPUT="lista5.m3u"
OUTPUT="lista5_filtered.m3u"
TIMEOUT=10

> "$OUTPUT"
echo "#EXTM3U" >> "$OUTPUT"

channel_name=""
extinf_line=""
url_line=""
keep_channel=false

while IFS= read -r line; do
    if [[ "$line" == "#EXTINF:"* ]]; then
        extinf_line="$line"
        channel_name=$(echo "$extinf_line" | sed 's/.*,\(.*\)/\1/')
    elif [[ "$line" == http* ]]; then
        url_line="$line"
        http_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time "$TIMEOUT" "$url_line" 2>/dev/null)
        if [[ "$http_code" -ge 200 && "$http_code" -lt 400 ]]; then
            echo "$extinf_line" >> "$OUTPUT"
            echo "$url_line" >> "$OUTPUT"
        else
            echo "FALHOU [$http_code]: $channel_name"
        fi
    fi
done < "$INPUT"

mv "$OUTPUT" "$INPUT"
echo "Concluído! Lista filtrada salva em $INPUT"