#!/bin/bash
INPUT="lista5.m3u"
TIMEOUT=8
CONNECT_TIMEOUT=5

# Backup
cp "$INPUT" "$INPUT.bak.$(date +%Y%m%d_%H%M%S)"

# Extract unique channels (name -> first EXTINF + URL pair)
declare -A seen_names
declare -a extinf_lines
declare -a url_lines

while IFS= read -r line; do
    if [[ "$line" == "#EXTINF:"* ]]; then
        extinf_line="$line"
        channel_name=$(echo "$extinf_line" | sed 's/.*,\(.*\)/\1/')
    elif [[ "$line" == http* ]]; then
        url_line="$line"
        if [[ -z "${seen_names[$channel_name]}" ]]; then
            seen_names[$channel_name]=1
            extinf_lines+=("$extinf_line")
            url_lines+=("$url_line")
        fi
    fi
done < "$INPUT"

TOTAL=${#url_lines[@]}
echo "Total de canais unicos: $TOTAL"
echo "=========================================="

# Write header
> "$INPUT.tmp"
echo "#EXTM3U" >> "$INPUT.tmp"

OK=0
FAIL=0

for i in $(seq 0 $((TOTAL - 1))); do
    extinf="${extinf_lines[$i]}"
    url="${url_lines[$i]}"
    name=$(echo "$extinf" | sed 's/.*,\(.*\)/\1/')
    idx=$((i + 1))

    status=$(curl -s -o /dev/null -w "%{http_code}" -L --max-time "$TIMEOUT" --connect-timeout "$CONNECT_TIMEOUT" "$url" 2>/dev/null)

    if [[ "$status" -ge 200 && "$status" -lt 400 ]]; then
        echo "$extinf" >> "$INPUT.tmp"
        echo "$url" >> "$INPUT.tmp"
        echo "[$idx/$TOTAL] OK   ($status) $name"
        OK=$((OK + 1))
    else
        echo "[$idx/$TOTAL] FAIL ($status) $name"
        FAIL=$((FAIL + 1))
    fi
done

mv "$INPUT.tmp" "$INPUT"
echo ""
echo "=== RESULTADO ==="
echo "Total: $TOTAL | OK: $OK | FAIL: $FAIL"
echo "Lista atualizada em $INPUT"
