#!/usr/bin/env python3
import re
import gzip
import xml.etree.ElementTree as ET
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
import os
import subprocess
import sys

INPUT = "lista5.m3u"
OUTPUT = "lista5.m3u"
BACKUP = "lista5.m3u.bak"

LOCAL_EPG_ATUALIZADO = "lista5_epg_atualizado.xml.gz"
LOCAL_EPG_FULL = "EPGFULL.xml.gz"

EPG_URLS = 'x-tvg-url="https://raw.githubusercontent.com/gratinomaster/JCTV/main/lista5_epg_atualizado.xml.gz|https://raw.githubusercontent.com/gratinomaster/JCTV/main/EPGFULL.xml.gz" url-tvg="https://raw.githubusercontent.com/gratinomaster/JCTV/main/lista5_epg_atualizado.xml.gz https://raw.githubusercontent.com/gratinomaster/JCTV/main/EPGFULL.xml.gz"'

CHANNEL_MAP = OrderedDict([
    ("abc news live", {
        "tvg_id": "ABCNewsLive.us",
        "tvg_name": "ABC News Live",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5c/ABC_News_Live_logo.svg/1200px-ABC_News_Live_logo.svg.jpg",
    }),
    ("good morning america", {
        "tvg_id": "ABCNewsLive.us",
        "tvg_name": "ABC News Live",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5c/ABC_News_Live_logo.svg/1200px-ABC_News_Live_logo.svg.jpg",
    }),
    ("abcnl", {
        "tvg_id": "ABCNewsLive.us",
        "tvg_name": "ABC News Live",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5c/ABC_News_Live_logo.svg/1200px-ABC_News_Live_logo.svg.jpg",
    }),
    ("abc news", {
        "tvg_id": "ABCNewsLive.us",
        "tvg_name": "ABC News Live",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5c/ABC_News_Live_logo.svg/1200px-ABC_News_Live_logo.svg.jpg",
    }),
    ("fox business", {
        "tvg_id": "FoxBusinessNetwork.us",
        "tvg_name": "Fox Business Network",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0d/Fox_Business_logo.svg/1200px-Fox_Business_logo.svg.jpg",
    }),
    ("fox news", {
        "tvg_id": "FoxNewsChannel.us",
        "tvg_name": "Fox News Channel",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/67/Fox_News_Channel_logo.svg/1200px-Fox_News_Channel_logo.svg.jpg",
    }),
    ("cbs news", {
        "tvg_id": "CBSNewsNetwork.us",
        "tvg_name": "CBS News 24/7",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/9e/CBS_News_logo_2024.svg/1200px-CBS_News_logo_2024.svg.jpg",
    }),
])

def parse_m3u(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.read().splitlines()
    
    header = "#EXTM3U"
    current_extinf = None
    entries = []
    
    for line in lines:
        s = line.strip()
        if s.startswith("#EXTM3U"):
            header = s
        elif s.startswith("#EXTINF:"):
            current_extinf = s
        elif s and not s.startswith("#") and current_extinf:
            entries.append((current_extinf, s))
            current_extinf = None
    
    return header, entries

def extract_attrs(extinf):
    content = re.sub(r'^#EXTINF:-1\s*', '', extinf.strip())
    attrs = {}
    for m in re.finditer(r'([\w-]+)="([^"]*)"', content):
        attrs[m.group(1)] = m.group(2)
    name_m = re.search(r',(.+)$', content)
    attrs["name"] = name_m.group(1).strip() if name_m else content.strip()
    return attrs

def build_extinf(attrs):
    name = attrs.pop("name", "")
    parts = ["#EXTINF:-1"]
    for key, val in attrs.items():
        if val:
            parts.append(f'{key}="{val}"')
    parts.append(f",{name}")
    result = " ".join(parts)
    result = result.replace('" ,', '",')
    return result

def get_channel_info(name):
    nl = name.lower()
    for kw, info in CHANNEL_MAP.items():
        if kw in nl:
            return info
    return None

def test_url(url, timeout=10):
    try:
        r = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
             "--max-time", str(timeout), "-L", url],
            capture_output=True, text=True, timeout=timeout + 5
        )
        code = r.stdout.strip()
        if code and code[0] in ("2", "3"):
            return True, f"HTTP {code}"
        if code == "403":
            return True, f"HTTP 403 (pode funcionar no player)"
        return False, f"HTTP {code or 'sem resposta'}"
    except subprocess.TimeoutExpired:
        return False, "Timeout"
    except Exception as e:
        return False, str(e)

def fix_logo(logo, name):
    if not logo:
        return ""
    if "imgur.com" in logo.lower():
        return ""
    base = re.sub(r'\.[a-zA-Z]+(\?.*)?$', '', logo)
    ext_m = re.search(r'\.([a-zA-Z]+)(\?.*)?$', logo)
    ext = ext_m.group(1).lower() if ext_m else ""
    qs = ""
    if "?" in logo:
        qs = "?" + logo.split("?", 1)[1]
    if ext in ("jpg", "jpeg"):
        return logo
    return base + ".jpg" + qs

def test_vt_safety(url):
    issues = []
    suspicious = [r'\.exe$', r'\.dll$', r'\.scr$', r'\.bat$', r'\.vbs$', r'\.ps1$']
    for pat in suspicious:
        if re.search(pat, url, re.I):
            issues.append(f"Extensao suspeita: {pat}")
    return issues

def load_epg_channel_ids(path):
    if not os.path.exists(path):
        return {}
    try:
        if path.endswith('.gz'):
            with gzip.open(path, 'rt', encoding='utf-8') as f:
                content = f.read()
        else:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
        root = ET.fromstring(content)
        result = {}
        for ch in root.findall('.//channel'):
            cid = ch.get('id')
            dn = ch.find('display-name')
            result[cid] = dn.text if dn is not None else cid
        return result
    except:
        return {}

def verify_epg_schedule(path):
    if not os.path.exists(path):
        return {"status": "not_found"}
    try:
        if path.endswith('.gz'):
            with gzip.open(path, 'rt', encoding='utf-8') as f:
                content = f.read()
        else:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
        root = ET.fromstring(content)
        progs = root.findall('programme')
        now = datetime.now()
        today = now.strftime('%Y%m%d')
        tomorrow = (now + timedelta(days=1)).strftime('%Y%m%d')
        day_after = (now + timedelta(days=2)).strftime('%Y%m%d')
        t, tm, ta = 0, 0, 0
        per_ch = {}
        for p in progs:
            start = p.get('start', '')
            ch = p.get('channel', '')
            title_el = p.find('title')
            title = title_el.text if title_el is not None else ''
            d = start[:8]
            if d == today:
                t += 1
                if ch not in per_ch: per_ch[ch] = {}
                per_ch[ch]["today"] = per_ch[ch].get("today", 0) + 1
            elif d == tomorrow:
                tm += 1
            elif d == day_after:
                ta += 1
        return {
            "status": "ok",
            "total": len(progs),
            "hoje": t, "amanha": tm, "depois_amanha": ta,
            "per_channel": per_ch,
            "dates": {
                "today": t > 0,
                "tomorrow": tm > 0,
                "day_after": ta > 0
            }
        }
    except Exception as e:
        return {"status": f"erro: {e}"}

def main():
    print("=" * 70)
    print("CORRECAO COMPLETA lista5.m3u")
    print("=" * 70)

    if not os.path.exists(INPUT):
        print(f"ERRO: {INPUT} nao encontrado!")
        return 1

    print(f"\n[1/8] Fazendo backup...")
    if os.path.exists(INPUT):
        import shutil
        shutil.copy2(INPUT, BACKUP)
        print(f"  Backup: {BACKUP}")

    print(f"\n[2/8] Lendo {INPUT}...")
    header, entries = parse_m3u(INPUT)
    print(f"  Entradas: {len(entries)}")

    unique = OrderedDict()
    for extinf, url in entries:
        attrs = extract_attrs(extinf)
        name = attrs["name"]
        base_name = re.sub(r'\s*[-–|]\s*(?:\d+[kK]?\s*)?(?:\d+p\s*)?(?:\(.*\))?\s*$', '', name).strip()
        def qs(u):
            s = 0
            if 'hdri' in u.lower() or '1700' in u or '2400' in u: s += 20
            if 'master.m3u8' in u: s += 10
            if 'index.m3u8' in u: s += 5
            if '1200_complete' in u or '/1200_' in u: s += 15
            if '128_complete' in u: s += 3
            if '64' in u or '441000' in u: s -= 5
            return s
        if base_name not in unique:
            unique[base_name] = (extinf, url, name, attrs)
        else:
            _, old_url, _, _ = unique[base_name]
            if qs(url) > qs(old_url):
                unique[base_name] = (extinf, url, name, attrs)

    print(f"  Canais unicos: {len(unique)} ({len(entries) - len(unique)} duplicatas removidas)")

    print(f"\n[3/8] Testando URLs dos streams...")
    working = OrderedDict()
    failed = 0
    for dk, (extinf, url, name, attrs) in unique.items():
        vt_issues = test_vt_safety(url)
        if vt_issues:
            print(f"  REMOVIDO (antivirus): {name[:50]}")
            failed += 1
            continue
        print(f"  {name[:50]:<50} ", end="", flush=True)
        ok, msg = test_url(url)
        if ok:
            print(f"OK ({msg})")
            working[dk] = (extinf, url, name, attrs)
        else:
            print(f"REMOVED ({msg})")
            failed += 1

    print(f"\n[4/8] Carregando dados EPG...")
    epg_channels = load_epg_channel_ids(LOCAL_EPG_ATUALIZADO)
    print(f"  {LOCAL_EPG_ATUALIZADO}: {len(epg_channels)} canais")

    print(f"\n[5/8] Corrigindo atributos dos canais...")
    output_lines = []
    output_lines.append(f"#EXTM3U {EPG_URLS}")
    epg_count = 0
    for dk, (extinf, url, name, attrs) in working.items():
        ch_info = get_channel_info(name)
        if ch_info:
            attrs["tvg-id"] = ch_info["tvg_id"]
            attrs["tvg-name"] = ch_info["tvg_name"]
            attrs["tvg-logo"] = ch_info["logo"]
            epg_count += 1
        else:
            attrs.pop("tvg-id", None)
            attrs.pop("tvg-name", None)
            old_logo = attrs.get("tvg-logo", "")
            new_logo = fix_logo(old_logo, name)
            if new_logo:
                attrs["tvg-logo"] = new_logo
            elif old_logo:
                del attrs["tvg-logo"]

        if "group-title" not in attrs or not attrs["group-title"]:
            attrs["group-title"] = "NEWS WORLD"

        new_extinf = build_extinf(attrs.copy())
        output_lines.append(new_extinf)
        output_lines.append(url)

    print(f"  Canais com EPG: {epg_count}")
    print(f"  Canais sem EPG: {len(working) - epg_count}")

    print(f"\n[6/8] Salvando {OUTPUT}...")
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        f.write("\n".join(output_lines) + "\n")
    print(f"  {len(working)} canais salvos")

    print(f"\n[7/8] Verificacoes finais...")
    errors = 0
    with open(OUTPUT, 'r', encoding='utf-8') as f:
        out_lines = f.read().splitlines()
    
    for i, line in enumerate(out_lines):
        if line.startswith("http") or line.startswith("https://"):
            if i == 0 or not out_lines[i-1].startswith("#EXTINF:"):
                print(f"  ERRO linha {i+1}: URL sem #EXTINF antes")
                errors += 1
        if "#EXTINF:" in line:
            if 'tvg-logo="https://imgur.com' in line.lower():
                print(f"  ERRO linha {i+1}: Logo imgur.com encontrada")
                errors += 1
            m = re.search(r'tvg-logo="([^"]+)"', line)
            if m:
                logo = m.group(1)
                ext_m = re.search(r'\.([a-zA-Z]+)(\?.*)?$', logo)
                ext = ext_m.group(1).lower() if ext_m else ""
                if ext not in ("jpg", "jpeg"):
                    print(f"  ERRO linha {i+1}: Logo nao .jpg: {logo[:50]}")
                    errors += 1

    if errors == 0:
        print("  Todas as verificacoes passaram!")
    else:
        print(f"  {errors} erro(s) encontrado(s)")

    print(f"\n[8/8] Verificando programacao EPG...")
    for epg_path, epg_name in [(LOCAL_EPG_ATUALIZADO, "EPG Atualizado"),
                                 (LOCAL_EPG_FULL, "EPG Full")]:
        result = verify_epg_schedule(epg_path)
        if result["status"] == "ok":
            print(f"  {epg_name}: {result['total']} prog | Hoje: {result['hoje']} | Amanha: {result['amanha']} | Depois: {result['depois_amanha']}")
        else:
            print(f"  {epg_name}: {result['status']}")

    print(f"\n" + "=" * 70)
    print(f"RESUMO")
    print(f"=" * 70)
    print(f"  Entradas originais: {len(entries)}")
    print(f"  Canais unicos: {len(unique)}")
    print(f"  Removidos (falha/antivirus): {failed}")
    print(f"  Canais finais: {len(working)}")
    print(f"  Com EPG: {epg_count}")
    print(f"  Arquivo: {OUTPUT}")
    print(f"  EPG URLs: {EPG_URLS}")
    print()

    return 0

if __name__ == "__main__":
    sys.exit(main())
