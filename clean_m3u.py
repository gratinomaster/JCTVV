#!/usr/bin/env python3

with open('ESTADOS UNIDOS RESERVA.m3u', 'r', encoding='utf-8') as f:
    lines = f.readlines()

result = []
i = 0
while i < len(lines):
    line = lines[i].strip()
    
    if line.startswith('#EXTINF'):
        extinf_line = line
        next_line = lines[i + 1].strip() if i + 1 < len(lines) else ''
        
        if next_line.startswith('http://') or next_line.startswith('https://'):
            result.append(extinf_line + '\n')
            result.append(next_line + '\n')
            i += 2
        else:
            i += 1
    elif line.startswith('#EXTM3U'):
        result.append(line + '\n')
        i += 1
    else:
        i += 1

with open('ESTADOS UNIDOS RESERVA.m3u', 'w', encoding='utf-8') as f:
    f.writelines(result)

print(f"Arquivo limpo. Linhas restantes: {len(result)}")