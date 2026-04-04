#!/usr/bin/env python3
import re

def process_lista5():
    with open("lista5.m3u", "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.split('\n')
    output_lines = []
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        if line.startswith("#EXTINF:"):
            extinf_line = line
            
            if '.png' in extinf_line:
                extinf_line = re.sub(r'\.png(\?|$)', r'.jpg\1', extinf_line)
            if '.webp' in extinf_line:
                extinf_line = re.sub(r'\.webp(\?|$)', r'.jpg\1', extinf_line)
            if '.svg' in extinf_line:
                extinf_line = re.sub(r'\.svg(\?|$)', r'.jpg\1', extinf_line)
            if '.jpeg' in extinf_line:
                extinf_line = re.sub(r'\.jpeg(\?|$)', r'.jpg\1', extinf_line)
                
            output_lines.append(extinf_line)
            
            i += 1
            
            while i < len(lines) and (lines[i].startswith("#EXTVLCOPT") or lines[i].startswith("#KODIPROP") or lines[i].startswith("#https://") or lines[i].startswith("#http://")):
                output_lines.append(lines[i])
                i += 1
            
            if i < len(lines) and lines[i].startswith("http"):
                output_lines.append(lines[i])
                i += 1
            elif i < len(lines) and lines[i].startswith("#http"):
                output_lines.append(lines[i])
                i += 1
        else:
            output_lines.append(line)
            i += 1
    
    with open("lista5.m3u", "w", encoding="utf-8") as f:
        f.write('\n'.join(output_lines))
    
    print("Arquivo processado com sucesso!")

if __name__ == "__main__":
    process_lista5()
