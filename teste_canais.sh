#!/bin/bash
INPUT="lista5.m3u"
OUTPUT="lista5_clean.m3u"
TIMEOUT=10

echo "#EXTM3U" > "$OUTPUT"
COUNT=0
OK=0
FAIL=0

while IFS= read -r extinf && IFS= read -r url; do
    COUNT=$((COUNT + 1))
    name=$(echo "$extinf" | sed 's/.*,\(.*\)/\1/')
    
    # Test URL with curl - follow redirects, check HTTP status
    status=$(curl -s -o /dev/null -w "%{http_code}" -L --max-time "$TIMEOUT" --connect-timeout 5 "$url" 2>/dev/null)
    
    if [ "$status" -ge 200 ] && [ "$status" -lt 400 ]; then
        echo "$extinf" >> "$OUTPUT"
        echo "$url" >> "$OUTPUT"
        echo "[$COUNT] OK   ($status) $name"
        OK=$((OK + 1))
    else
        echo "[$COUNT] FAIL ($status) $name"
        FAIL=$((FAIL + 1))
    fi
done < <(tail -n +2 "$INPUT")

echo ""
echo "=== RESULTADO ==="
echo "Total: $COUNT | OK: $OK | FAIL: $FAIL"
