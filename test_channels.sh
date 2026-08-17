#!/bin/bash

INPUT_FILE="lista5.m3u"
TEMP_FILE="lista5_tested.m3u"
LOG_FILE="test_results.log"

> "$LOG_FILE"
> "$TEMP_FILE"

echo "#EXTM3U" >> "$TEMP_FILE"

current_extinf=""
while IFS= read -r line; do
    if [[ "$line" == \#EXTINF:* ]]; then
        current_extinf="$line"
    elif [[ -n "$current_extinf" && "$line" != \#EXTM3U && -n "$line" ]]; then
        url="$line"
        
        http_code=$(curl -s -o /dev/null -w "%{http_code}" -m 10 --max-time 15 "$url" 2>/dev/null)
        
        if [[ "$http_code" == "200" ]]; then
            echo "OK  [$http_code] $url" >> "$LOG_FILE"
            echo "$current_extinf" >> "$TEMP_FILE"
            echo "$url" >> "$TEMP_FILE"
        else
            echo "FAIL[$http_code] $url" >> "$LOG_FILE"
        fi
        
        current_extinf=""
    fi
done < "$INPUT_FILE"

mv "$TEMP_FILE" "$INPUT_FILE"
echo "Teste concluído. Resultados em $LOG_FILE"