import subprocess
import re

INPUT = "lista5.m3u"
OUTPUT = "lista5.m3u"

def parse_m3u(path):
    groups = []
    with open(path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()
    current = None
    for line in lines:
        if line.startswith("#EXTM3U"):
            continue
        elif line.startswith("#EXTINF:"):
            if current:
                groups.append(current)
            current = {"extinf": line, "urls": []}
        elif line.startswith("http://") or line.startswith("https://"):
            if current:
                current["urls"].append(line)
        else:
            if current:
                current.setdefault("extra", []).append(line)
    if current:
        groups.append(current)
    return groups

def fetch(url):
    try:
        r = subprocess.run(
            ["curl", "-s", "--connect-timeout", "8", "--max-time", "15", "-L", url],
            capture_output=True, text=True, timeout=25,
        )
        return r.stdout
    except Exception:
        return ""

def is_valid_m3u8(body):
    if not body:
        return False
    if "#EXTM3U" in body[:2000]:
        return True
    if re.search(r"#EXT-X-(STREAM-INF|MEDIA|TARGETDURATION|INF)", body):
        return True
    return False

def main():
    groups = parse_m3u(INPUT)
    total = len(groups)
    print(f"Total de canais: {total}")

    kept = []
    removed = []
    for i, g in enumerate(groups, 1):
        name = g["extinf"].split(",")[-1][:60]
        url = g["urls"][0] if g["urls"] else ""
        body = fetch(url) if url else ""
        ok = is_valid_m3u8(body)
        status = "OK " if ok else "FALHA"
        print(f"[{i}/{total}] {status} - {name}")
        if ok:
            kept.append(g)
        else:
            removed.append((name, url, body[:200].replace("\n", " ")))

    print(f"\nFuncionando: {len(kept)} | Removidos: {len(removed)}")

    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for g in kept:
            f.write(g["extinf"] + "\n")
            for u in g["urls"]:
                f.write(u + "\n")
            for e in g.get("extra", []):
                f.write(e + "\n")

    print(f"Arquivo sobrescrito: {OUTPUT}")

if __name__ == "__main__":
    main()
