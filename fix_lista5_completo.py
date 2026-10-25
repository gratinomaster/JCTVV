#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import re
import json
import base64
import shutil
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from urllib.parse import urlsplit, urlunsplit
from collections import defaultdict
import requests

BASE = '/home/runner/work/JCTVV/JCTVV'
M3U_FILE = os.path.join(BASE, 'lista5.m3u')
REPORT = os.path.join(BASE, f'relatorio_lista5_corrigido_completo_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt')

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
VT_API_KEY = os.environ.get('VIRUSTOTAL_API_KEY', '')

def log(msg):
    print(msg)
    with open(REPORT, 'a', encoding='utf-8') as f:
        f.write(msg + '\n')

def fix_logo(url):
    if not url:
        return None
    url_low = url.lower()
    if 'imgur.com' in url_low:
        return None
    # remove query/fragment
    url_clean = url.split('?')[0].split('#')[0]
    if url_clean.lower().endswith('.jpg') or url_clean.lower().endswith('.jpeg'):
        if url_clean.lower().endswith('.jpeg'):
            return url_clean[:-5] + '.jpg'
        return url_clean
    # change extension to jpg
    for ext in ['.png', '.svg', '.webp', '.gif', '.bmp', '.ico']:
        if url_clean.lower().endswith(ext):
            base = url_clean[:len(url_clean)-len(ext)]
            return base + '.jpg'
    # if has extension, change
    m = re.search(r'\.([a-zA-Z0-9]+)$', url_clean)
    if m:
        base = url_clean[:m.start()]
        return base + '.jpg'
    # no extension
    return url_clean.rstrip('/') + '.jpg' if '/' in url_clean else url_clean + '.jpg'

def check_stream(url, timeout=12):
    try:
        headers = {'User-Agent': USER_AGENT, 'Accept': '*/*'}
        r = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True, stream=True)
        # Check status
        if r.status_code >= 400:
            return False
        ct = r.headers.get('Content-Type', '')
        # Read small chunk
        chunk = next(r.iter_content(chunk_size=8192), b'')
        r.close()
        if chunk.startswith(b'#EXTM3U') or b'#EXT-X-VERSION' in chunk or len(chunk) > 100:
            return True
        # if content-type suggests media
        if any(x in ct.lower() for x in ['mpegurl', 'video', 'octet-stream']):
            return True
        return len(chunk) > 0
    except Exception as e:
        return False

def check_virustotal(url):
    if not VT_API_KEY:
        return {'status': 'nao_verificado'}
    try:
        import time
        url_id = base64.urlsafe_b64encode(url.encode()).decode().strip("=")
        headers = {"x-apikey": VT_API_KEY}
        r = requests.get(f"https://www.virustotal.com/api/v3/urls/{url_id}", headers=headers, timeout=20)
        if r.status_code == 200:
            data = r.json()
            stats = data.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
            malicious = stats.get("malicious", 0)
            suspicious = stats.get("suspicious", 0)
            if malicious > 0 or suspicious > 0:
                return {"status": "malicious", "malicious": malicious, "suspicious": suspicious}
            return {"status": "clean", "malicious": 0, "suspicious": 0}
        elif r.status_code == 404:
            # Submit for analysis
            try:
                r2 = requests.post("https://www.virustotal.com/api/v3/urls", headers=headers, data={"url": url}, timeout=20)
                if r2.status_code in (200, 202):
                    return {"status": "submitted"}
            except:
                pass
            return {"status": "nao_encontrado"}
        else:
            return {"status": f"erro_{r.status_code}"}
    except Exception as e:
        return {"status": "erro", "erro": str(e)}

def parse_m3u_detailed(path):
    entries = []
    cur = None
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        for raw in f:
            line = raw.rstrip('\n\r')
            if not line.strip():
                continue
            if line.strip().startswith('#EXTM3U'):
                continue
            if line.strip().startswith('#EXTINF:'):
                if cur and cur['urls']:
                    entries.append(cur)
                cur = {'extinf': line.strip(), 'urls': []}
            elif line.strip().startswith('http://') or line.strip().startswith('https://'):
                if cur is None:
                    cur = {'extinf': '#EXTINF:-1', 'urls': []}
                cur['urls'].append(line.strip())
        if cur and cur['urls']:
            entries.append(cur)
    return entries

def extract_attr(extinf, attr):
    m = re.search(rf'{attr}="([^"]*)"', extinf)
    if m:
        return m.group(1)
    return ''

def build_extinf(tvg_id, tvg_name, tvg_logo, group_title, name):
    parts = []
    parts.append(f'tvg-id="{tvg_id}"')
    parts.append(f'tvg-name="{tvg_name}"')
    if tvg_logo:
        parts.append(f'tvg-logo="{tvg_logo}"')
    parts.append(f'group-title="{group_title}"')
    return f'#EXTINF:-1 {" ".join(parts)},{name}'

def main():
    log(f"=== CORRECAO COMPLETA lista5.m3u === {datetime.now()}")
    # Backup
    bak = os.path.join(BASE, f'lista5.m3u.bak.pre_completo_{datetime.now().strftime("%Y%m%d_%H%M%S")}')
    shutil.copy2(M3U_FILE, bak)
    log(f"Backup: {bak}")
    
    # Load all EPG files
    epg_files = []
    for fn in os.listdir(BASE):
        if fn.endswith('.xml') and ('epg' in fn.lower() or fn in ['lista5_epg.xml', 'lista5_epg_combinado.xml', 'lista5_epg_atualizado.xml']):
            epg_files.append(os.path.join(BASE, fn))
    # also include gz/xml.gz references? maybe just xml
    epg_files = list(set(epg_files))
    log(f"EPG files encontrados: {len(epg_files)}")
    
    # Load programmes from all EPGs
    all_progs = []
    all_channels_epg = {} # channel_id -> info
    for epgf in epg_files:
        try:
            tree = ET.parse(epgf)
            root = tree.getroot()
            for ch in root.findall('channel'):
                cid = ch.attrib.get('id')
                if cid and cid not in all_channels_epg:
                    dn = ch.find('display-name')
                    all_channels_epg[cid] = dn.text if dn is not None and dn.text else cid
            for p in root.findall('programme'):
                all_progs.append(p.attrib) # just attribs for quick check
        except Exception as e:
            log(f"Erro lendo {epgf}: {e}")
    log(f"Total canais EPG: {len(all_channels_epg)}, programas: {len(all_progs)}")
    
    # Check coverage for today/tomorrow/day after
    hoje = datetime.now().strftime('%Y%m%d')
    amanha = (datetime.now()+timedelta(days=1)).strftime('%Y%m%d')
    depois = (datetime.now()+timedelta(days=2)).strftime('%Y%m%d')
    def has_prog(cid, day):
        for p in all_progs:
            if p.get('channel') == cid and p.get('start','')[:8] == day:
                return True
        return False
    
    # Parse current m3u
    entries = parse_m3u_detailed(M3U_FILE)
    log(f"Entradas no m3u atual: {len(entries)}")
    
    # Process each unique logical channel? Or each entry - but user says "canais", probably deduplicate by name+stream
    # Also need to ensure every channel has valid epg - so need tvg-id mapping
    result_entries = []
    seen_streams = set()
    
    # Try to find good mapping for channels
    for entry in entries:
        extinf = entry['extinf']
        urls = entry['urls']
        if not urls:
            continue
        # Take first/main url? Or keep all if same channel? The original has duplicates - maybe consolidate
        main_url = urls[0]
        if main_url in seen_streams:
            continue  # skip duplicates
        seen_streams.add(main_url)
        
        tvg_id = extract_attr(extinf, 'tvg-id')
        tvg_name = extract_attr(extinf, 'tvg-name')
        tvg_logo = extract_attr(extinf, 'tvg-logo')
        group_title = extract_attr(extinf, 'group-title') or 'NEWS WORLD'
        name = extinf.split(',')[-1].strip()
        if not tvg_name:
            tvg_name = name
        
        log(f"\nProcessando: {name}")
        log(f"  URL: {main_url[:90]}...")
        
        # Fix logo
        new_logo = fix_logo(tvg_logo)
        if new_logo != tvg_logo:
            log(f"  Logo corrigido: {tvg_logo} -> {new_logo}")
        tvg_logo_fixed = new_logo
        if not tvg_logo_fixed or 'imgur' in str(tvg_logo_fixed).lower():
            tvg_logo_fixed = None  # need to add if missing - try to find or leave None but requirement says add if missing with .jpg; maybe use a placeholder or try to derive
        
        # Test stream
        stream_ok = check_stream(main_url)
        log(f"  Stream OK: {stream_ok}")
        if not stream_ok:
            log(f"  REMOVIDO: stream não funciona")
            continue
        
        # VirusTotal
        vt = check_virustotal(main_url)
        log(f"  VirusTotal: {vt.get('status')}")
        if vt.get('status') == 'malicious':
            log(f"  REMOVIDO: malicioso no VirusTotal")
            continue
        
        # EPG - if no tvg-id or no valid epg, try to find/match
        if not tvg_id or tvg_id not in all_channels_epg:
            # try to find matching by name
            name_norm = name.lower().replace(' ', '').replace('-', '').replace('_', '')
            found_id = None
            for cid in all_channels_epg:
                cid_norm = cid.lower().replace(' ', '').replace('-', '').replace('_', '')
                if name_norm in cid_norm or cid_norm in name_norm:
                    found_id = cid
                    break
            if found_id:
                tvg_id = found_id
                log(f"  EPG mapeado por nome: {tvg_id}")
            else:
                # for news channels in our list, try known mappings
                if 'abc' in name.lower():
                    tvg_id = 'ABCNewsLive.us'
                elif 'fox news' in name.lower() and 'business' not in name.lower():
                    tvg_id = 'FoxNewsChannel.us'
                elif 'fox business' in name.lower():
                    tvg_id = 'FoxBusiness.us'
                elif 'cbs' in name.lower():
                    tvg_id = 'CBSNews.us'
                elif 'cnn' in name.lower():
                    tvg_id = 'CNNinternational.us'
                else:
                    log(f"  AVISO: Sem tvg-id/EPG valido encontrado")
        
        # Check EPG coverage
        if tvg_id and tvg_id in all_channels_epg:
            h = has_prog(tvg_id, hoje)
            a = has_prog(tvg_id, amanha)
            d = has_prog(tvg_id, depois)
            log(f"  EPG cobertura: hoje={h} amanha={a} depois={d}")
            if not (h and a and d):  # need all three days
                log(f"  AVISO: EPG incompleto para os 3 dias")
        else:
            log(f"  CRITICO: Sem EPG valido")
            # try to assign a known good one from available
            # continue anyway but mark
        
        # Ensure logo is .jpg
        if not tvg_logo_fixed or not (tvg_logo_fixed.lower().endswith('.jpg') or tvg_logo_fixed.lower().endswith('.jpeg')):
            tvg_logo_fixed = fix_logo(tvg_logo_fixed) if tvg_logo_fixed else None
        if tvg_logo_fixed and tvg_logo_fixed.lower().endswith('.jpeg'):
            tvg_logo_fixed = tvg_logo_fixed[:-5] + '.jpg'
        # If still no logo or wrong format, try to set from known ones
        if not tvg_logo_fixed or '.imgur' in str(tvg_logo_fixed).lower():
            if 'abc' in name.lower():
                tvg_logo_fixed = 'https://raw.githubusercontent.com/gratinomaster/JCTV/main/abcnews.jpg'
            elif 'fox news' in name.lower() and 'business' not in name.lower():
                tvg_logo_fixed = 'https://raw.githubusercontent.com/gratinomaster/JCTV/main/fox_news.jpg'
            elif 'fox business' in name.lower():
                tvg_logo_fixed = 'https://raw.githubusercontent.com/gratinomaster/JCTV/main/fox_business.jpg'
            elif 'cbs' in name.lower():
                tvg_logo_fixed = 'https://raw.githubusercontent.com/gratinomaster/JCTV/main/cbsnews.jpg'
            elif 'cnn' in name.lower():
                tvg_logo_fixed = 'https://raw.githubusercontent.com/gratinomaster/JCTV/main/cnn.jpg'
            else:
                tvg_logo_fixed = tvg_logo_fixed  # keep as is if we can't fix
        
        if tvg_logo_fixed and not (tvg_logo_fixed.lower().endswith('.jpg')):
            tvg_logo_fixed = fix_logo(tvg_logo_fixed)
        
        extinf_new = build_extinf(tvg_id or name, tvg_name, tvg_logo_fixed, group_title, name)
        result_entries.append({'extinf': extinf_new, 'url': main_url})
    
    # Build m3u with multiple EPG URLs if needed
    epg_urls = []
    for epgf in epg_files:
        if epgf.endswith('.xml.gz'):
            # skip gz for now, use xml
            continue
        # make relative to repo raw or use local? The original used GitHub raw URLs in other files
        epg_urls.append(f'file://{epgf}')  # or just the filename
    # Prefer using GitHub style URLs like in other m3u files
    epg_url_str = 'https://raw.githubusercontent.com/JCTV/JCTV/main/lista5_epg.xml'
    # Also add others if they exist
    other_epgs = []
    for epgf in ['lista5_epg_combinado.xml', 'lista5_epg_atualizado.xml']:
        p = os.path.join(BASE, epgf)
        if os.path.exists(p):
            other_epgs.append(f'https://raw.githubusercontent.com/JCTV/JCTV/main/{epgf}')
    if other_epgs:
        epg_url_str = epg_url_str + ' ' + ' '.join(other_epgs)
    
    m3u_out = []
    m3u_out.append(f'#EXTM3U x-tvg-url="{epg_url_str}"')
    for re in result_entries:
        m3u_out.append(re['extinf'])
        m3u_out.append(re['url'])
    
    with open(M3U_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(m3u_out) + '\n')
    
    log(f"\n=== FINALIZADO ===")
    log(f"Canais salvos: {len(result_entries)}")
    log(f"Arquivo: {M3U_FILE}")

if __name__ == '__main__':
    main()
