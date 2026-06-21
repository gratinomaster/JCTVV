import re
import subprocess
import sys
from urllib.parse import urlparse

M3U_FILE = "lista5.m3u"

with open(M3U_FILE, "r") as f:
    lines = f.read().splitlines()

entries = []
i = 0
while i < len(lines):
    if lines[i].startswith("#EXTINF:"):
        if i + 1 < len(lines) and not lines[i+1].startswith("#"):
            entries.append((lines[i], lines[i+1]))
            i += 2
        else:
            i += 1
    else:
        i += 1

# Group by channel name (extract name from EXTINF)
groups = {}
for extinf, url in entries:
    name = extinf.rsplit(",", 1)[-1].strip() if "," in extinf else extinf
    if name not in groups:
        groups[name] = []
    groups[name].append((extinf, url))

print(f"Encontrados {len(entries)} entries em {len(groups)} grupos de canais")

def test_url(url, timeout=10):
    try:
        r = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", str(timeout), url],
            capture_output=True, text=True, timeout=timeout+5
        )
        code = r.stdout.strip()
        return code.startswith("2")
    except Exception as e:
        return False

working_groups = []
failed_groups = []

for name, group_entries in groups.items():
    test_url_str = group_entries[0][1]
    if test_url(test_url_str):
        working_groups.append(name)
        print(f"  [OK] {name}")
    else:
        failed_groups.append(name)
        print(f"  [FAIL] {name}")

# Rebuild M3U content keeping only working channels
seen_names = set()
new_lines = ["#EXTM3U"]
for extinf, url in entries:
    name = extinf.rsplit(",", 1)[-1].strip() if "," in extinf else extinf
    if name in working_groups and name not in seen_names:
        seen_names.add(name)
    if name in working_groups:
        new_lines.append(extinf)
        new_lines.append(url)

with open(M3U_FILE, "w") as f:
    f.write("\n".join(new_lines) + "\n")

print(f"\n--- Resumo ---")
print(f"Canais funcionando: {len(working_groups)}")
for n in working_groups:
    print(f"  [OK] {n}")
print(f"Canais removidos: {len(failed_groups)}")
for n in failed_groups:
    print(f"  [REMOVED] {n}")
print(f"Arquivo {M3U_FILE} atualizado com {len(new_lines)-1} linhas")
