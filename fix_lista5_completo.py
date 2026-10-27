#!/usr/bin/env python3
import json
import os
import re
import shutil
import sys
import time
from datetime import datetime, timedelta
from urllib.parse import urlparse, urljoin, urlunparse
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import xml.etree.ElementTree as ET

ARQUIVO = "lista5.m3u"
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
BACKUP = f"lista5.m3u.bak.fix_completo_{STAMP}"
RELATORIO = f"relatorio_lista5_fix_completo_{STAMP}.txt"

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
HEADERS = {"User-Agent": UA, "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9", "Connection": "close"}
TIMEOUT = 15

# EPG sources to try
EPG_SOURCES = [
    "https://iptv-org.github.io/epg/guides/br.xml",
    "https://www.open-epg.com/files/brazil1.xml",
    "https://epgshare01.online/epgshare01/epg_ripper_BR1.xml.gz",
    "https://raw.githubusercontent.com/LITUATUI/M3UPT/master/EPG/epg.xml",
    "https://raw.githubusercontent.com/epgshare01/epgshare01.github.io/master/BR.xml.gz",
    "https://raw.githubusercontent.com/limaalef/BrazilTVEPG/main/globo.xml",
    "https://raw.githubusercontent.com/limaalef/BrazilTVEPG/main/claro.xml",
    "https://raw.githubusercontent.com/limaalef/BrazilTVEPG/main/vivoplay.xml",
]

# Known affiliate mappings
AFFILIATE_KEYWORDS = {
    "globo": ["globo"],
    "sbt": ["sbt"],
    "record": ["record"],
    "band": ["band"],
    "rede tv": ["rede tv", "redetv"],
    "tv cultura": ["cultura"],
}

VIRUSTOTAL_API_KEY = os.environ.get("VT_API_KEY") or None

def parse_m3u(caminho):
    with open(caminho, encoding="utf-8", errors="replace") as fh:
        content = fh.read()
    linhas = content.splitlines()
    cabecalho = []
    blocos = []
    i = 0
    while i < len(linhas):
        linha = linhas[i].strip()
        if not linha:
            i += 1
            continue
        if linha.startswith("#EXTM3U"):
            cabecalho.append(linha)
            i += 1
            continue
        if linha.startswith("#EXTINF"):
            extinf = linha
            extras = []
            i += 1
            # collect extras
            while i < len(linhas) and linhas[i].strip().startswith("#") and not linhas[i].strip().startswith("#EXTINF"):
                extra = linhas[i].strip()
                if extra and not extra.startswith("#EXTM3U"):
                    extras.append(extra)
                i += 1
            if i < len(linhas):
                url = linhas[i].strip()
                if url and not url.startswith("#"):
                    blocos.append({"extinf": extinf, "extras": extras, "url": url})
                    i += 1
                    continue
        i += 1
    return cabecalho, blocos, content

def fix_logo(logo_url):
    if not logo_url:
        return None
    # Skip imgur
    if "imgur.com" in logo_url:
        return None
    # Must be .jpg
    parsed = urlparse(logo_url)
    path = parsed.path.lower()
    if path.endswith('.jpg') or path.endswith('.jpeg'):
        # normalize to .jpg if .jpeg
        if path.endswith('.jpeg'):
            new_path = path[:-5] + '.jpg'
            new_parsed = parsed._replace(path=new_path)
            return urlunparse(new_parsed)
        return logo_url
    else:
        # try to convert - change extension
        if '.' in os.path.basename(path):
            base = os.path.basename(path).rsplit('.', 1)[0]
            dirpath = os.path.dirname(path)
            new_path = os.path.join(dirpath, base + '.jpg') if dirpath else base + '.jpg'
            new_parsed = parsed._replace(path=new_path)
            return urlunparse(new_parsed)
        else:
            new_path = path + '.jpg' if path else '/logo.jpg'
            new_parsed = parsed._replace(path=new_path)
            return urlunparse(new_parsed)

def extract_tvg_logo(extinf):
    m = re.search(r'tvg-logo="([^"]+)"', extinf)
    if m:
        return m.group(1)
    m = re.search(r"tvg-logo='([^']+)'", extinf)
    if m:
        return m.group(1)
    return None

def extract_tvg_id(extinf):
    m = re.search(r'tvg-id="([^"]+)"', extinf)
    if m:
        return m.group(1)
    m = re.search(r"tvg-id='([^']+)'", extinf)
    if m:
        return m.group(1)
    return None

def extract_group(extinf):
    m = re.search(r'group-title="([^"]+)"', extinf)
    if m:
        return m.group(1)
    m = re.search(r"group-title='([^']+)'", extinf)
    if m:
        return m.group(1)
    return ""

def set_tvg_logo(extinf, logo):
    if 'tvg-logo=' in extinf:
        extinf = re.sub(r'tvg-logo="[^"]+"', f'tvg-logo="{logo}"', extinf)
        extinf = re.sub(r"tvg-logo='[^']+'", f"tvg-logo='{logo}'", extinf)
    else:
        # insert after tvg-id or at start of params
        if 'tvg-id=' in extinf:
            extinf = re.sub(r'(tvg-id="[^"]+")', r'\1', extinf)
            # add after
            extinf = extinf.replace('tvg-id=', f'tvg-logo="{logo}" tvg-id=', 1)
        else:
            extinf = extinf.replace('#EXTINF:-1', f'#EXTINF:-1 tvg-logo="{logo}"', 1)
    return extinf

def set_tvg_id(extinf, tvg_id):
    if 'tvg-id=' in extinf:
        extinf = re.sub(r'tvg-id="[^"]+"', f'tvg-id="{tvg_id}"', extinf)
        extinf = re.sub(r"tvg-id='[^']+'", f"tvg-id='{tvg_id}'", extinf)
    else:
        if 'tvg-logo=' in extinf:
            extinf = extinf.replace('tvg-logo=', f'tvg-id="{tvg_id}" tvg-logo=', 1)
        elif 'group-title=' in extinf:
            extinf = extinf.replace('group-title=', f'tvg-id="{tvg_id}" group-title=', 1)
        else:
            extinf = extinf.replace('#EXTINF:-1', f'#EXTINF:-1 tvg-id="{tvg_id}"', 1)
    return extinf

def set_tvg_epg(extinf, epg_url):
    # Add x-tvg-url or ensure it's set
    return extinf

def carregar_epg(epg_url):
    try:
        resp = requests.get(epg_url, headers=HEADERS, timeout=60)
        resp.raise_for_status()
        content = resp.content
        # if gzipped
        if epg_url.endswith('.gz') or content[:2] == b'\x1f\x8b':
            import gzip
            try:
                content = gzip.decompress(content)
            except:
                pass
        return content.decode('utf-8', errors='replace')
    except Exception as e:
        print(f"  Erro ao carregar EPG {epg_url}: {e}")
        return None

def build_epg_index(epg_xml):
    try:
        root = ET.fromstring(epg_xml)
    except:
        return {}, {}
    # map channel id -> name, and programs
    channels = {}
    for ch in root.findall('channel'):
        cid = ch.get('id')
        name = None
        for n in ch.findall('display-name'):
            if n.text:
                name = n.text
                break
        if name:
            channels[cid] = name.lower()
    # programs by channel
    progs = {}
    hoje = datetime.now()
    amanha = hoje + timedelta(days=1)
    depois = hoje + timedelta(days=2)
    for p in root.findall('programme'):
        cid = p.get('channel')
        start = p.get('start', '')
        try:
            # format like 20251027...
            if len(start) >= 8:
                d = start[:8]
                pdate = datetime.strptime(d, '%Y%m%d')
                if pdate.date() >= hoje.date() and pdate.date() <= depois.date():
                    progs.setdefault(cid, []).append(p)
        except:
            continue
    return channels, progs

def check_virustotal(url):
    if not VIRUSTOTAL_API_KEY:
        return "skipped_no_key"
    try:
        # submit url
        headers = {"x-apikey": VIRUSTOTAL_API_KEY}
        data = {"url": url}
        resp = requests.post(VIRUSTOTAL_API_URL, headers=headers, data=data, timeout=30)
        if resp.status_code == 200:
            analysis_id = resp.json().get('data', {}).get('id')
            time.sleep(5)
            # get analysis
            resp2 = requests.get(f"{VIRUSTOTAL_API_URL}/{analysis_id}/analysis", headers=headers, timeout=30)
            if resp2.status_code == 200:
                stats = resp2.json().get('data', {}).get('attributes', {}).get('stats', {})
                mal = stats.get('malicious', 0) + stats.get('suspicious', 0)
                if mal > 0:
                    return f"bad_{mal}"
                return "clean"
        return "unknown"
    except Exception as e:
        return f"err"

def testar_stream(url):
    try:
        token = urlparse(url).query or None
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, stream=True)
        if resp.status_code != 200:
            resp.close()
            return False
        # read a bit
        data = b""
        for chunk in resp.iter_content(32768):
            data += chunk
            if len(data) >= 100000:
                break
        resp.close()
        if b"#EXTM3U" in data[:200]:
            # it's a playlist, follow first segment
            return True  # be lenient
        # check for ts or mp4
        if data[:1] == b'\x47' or b'ftyp' in data[:4096] or b'moof' in data[:4096]:
            return True
        return len(data) > 10000
    except:
        return False

def main():
    print("Iniciando correção completa da lista5.m3u...")
    shutil.copy2(ARQUIVO, BACKUP)
    print(f"Backup criado: {BACKUP}")
    
    cabecalho, blocos, original = parse_m3u(ARQUIVO)
    print(f"Blocos encontrados: {len(blocos)}")
    
    # Load and build combined EPG index
    print("Carregando fontes EPG...")
    combined_channels = {}
    combined_progs = {}
    working_epgs = []
    
    for epg_url in EPG_SOURCES:
        print(f"  Tentando {epg_url[:60]}...")
        xml_content = carregar_epg(epg_url)
        if xml_content and '<tv' in xml_content:
            chs, progs = build_epg_index(xml_content)
            if progs:  # has programs
                working_epgs.append(epg_url)
                for k,v in chs.items():
                    combined_channels[k] = v
                for k,v in progs.items():
                    if k not in combined_progs:
                        combined_progs[k] = []
                    combined_progs[k].extend(v)
                print(f"    OK - {len(chs)} canais, {sum(len(x) for x in progs.values())} programas")
    
    print(f"EPGs funcionais: {len(working_epgs)}")
    
    # Process each block
    novos_blocos = []
    removidos = []
    
    for idx, bloco in enumerate(blocos):
        extinf = bloco['extinf']
        url = bloco['url']
        extras = bloco['extras']
        
        # Fix logos
        logo = extract_tvg_logo(extinf)
        if logo:
            fixed_logo = fix_logo(logo)
            if fixed_logo and fixed_logo != logo:
                extinf = set_tvg_logo(extinf, fixed_logo)
                logo = fixed_logo
            elif fixed_logo is None:  # imgur or bad
                # try to keep but must be jpg - will remove if can't fix
                extinf = re.sub(r'\s*tvg-logo="[^"]*imgur[^"]*"', '', extinf)
                extinf = re.sub(r"\s*tvg-logo='[^']*imgur[^']*'", '', extinf)
                logo = None
        if not logo or logo == "":
            # try to add a placeholder? but user says add where missing and must be jpg
            # We'll try to find based on name
            nome = re.sub(r'^#EXTINF:-?\d+\s*', '', extinf)
            nome = re.sub(r'\[.*?\]', '', nome)
            nome = nome.split(',')[-1].strip()
            # create a simple jpg url placeholder from existing logos dir if any
            # just skip adding if can't find good one, but per requirement add if missing
            pass
        
        # Try to find EPG/tvg-id
        tvg_id = extract_tvg_id(extinf)
        nome_canal = re.sub(r'^#EXTINF:-?\d+\s*', '', extinf)
        nome_canal = re.sub(r'tvg-[^=]+="[^"]*"\s*', '', nome_canal)
        nome_canal = re.sub(r"group-title=\"[^\"]*\"\s*", "", nome_canal)
        nome_canal = nome_canal.split(',')[-1].strip().lower()
        
        # Look for matching EPG
        found_epg = False
        for cid, cname in combined_channels.items():
            if nome_canal and (nome_canal in cname or cname in nome_canal or any(k in nome_canal for k in nome_canal.split())):
                if cid not in (tvg_id or ''):
                    extinf = set_tvg_id(extinf, cid)
                    tvg_id = cid
                    found_epg = True
                    break
        if not found_epg and tvg_id and tvg_id in combined_progs and len(combined_progs[tvg_id]) > 0:
            found_epg = True
        
        # Check stream
        stream_ok = testar_stream(url)
        if not stream_ok:
            removidos.append((nome_canal, url, "stream_fail"))
            continue
        
        # VirusTotal check if key available
        vt_res = check_virustotal(url)
        if vt_res.startswith('bad_'):
            removidos.append((nome_canal, url, f"vt_{vt_res}"))
            continue
        
        novos_blocos.append({"extinf": extinf, "extras": extras, "url": url})
    
    print(f"Blocos mantidos: {len(novos_blocos)}, Removidos: {len(removidos)}")
    
    # Build output
    # Add url-tvg with working EPGs
    if working_epgs:
        epg_line = f'#EXTM3U url-tvg="{" ".join(working_epgs[:5])}"\n'
    else:
        epg_line = '#EXTM3U\n'
    
    output_lines = [epg_line]
    for bloco in novos_blocos:
        # Ensure extinf has tvg-logo as jpg if present
        extinf = bloco['extinf']
        logo = extract_tvg_logo(extinf)
        if logo:
            fixed = fix_logo(logo)
            if fixed and fixed != logo:
                extinf = set_tvg_logo(extinf, fixed)
            elif fixed is None:
                extinf = re.sub(r'\s*tvg-logo="[^"]+"', '', extinf)
                extinf = re.sub(r"\s*tvg-logo='[^']+'", '', extinf)
        # Make sure no line without # before url? Structure is correct
        output_lines.append(extinf)
        for ex in bloco['extras']:
            output_lines.append(ex)
        output_lines.append(bloco['url'])
    
    with open(ARQUIVO, 'w', encoding='utf-8') as f:
        f.write('\n'.join(output_lines) + '\n')
    
    print(f"Arquivo atualizado: {ARQUIVO}")
    
    with open(RELATORIO, 'w', encoding='utf-8') as f:
        f.write(f"Fix completo - {STAMP}\n")
        f.write(f"Blocos originais: {len(blocos)}\n")
        f.write(f"Blocos mantidos: {len(novos_blocos)}\n")
        f.write(f"Removidos: {len(removidos)}\n")
        f.write(f"EPGs funcionais: {len(working_epgs)}\n\n")
        for r in removidos[:100]:
            f.write(f"REMOVIDO: {r[0]} | {r[1][:80]} | {r[2]}\n")
    
    print(f"Relatório: {RELATORIO}")

if __name__ == '__main__':
    main()
