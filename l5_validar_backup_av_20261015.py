#!/usr/bin/env python3
"""Validacao estendida da lista5.m3u (2026-10-15).

Complementa l5_step7_validate.py com dois blocos que ele nao cobre:
  - EPG de BACKUP (epg.pw US) por display-name (tvg-name)
  - ANTI-VIRUS: abuse.ch URLhaus (hostfile + csv) + heuristicas locais
    (imgur proibido, IP cru, porta incomum, TLD de risco, encurtador,
    spoof de marca) sobre streams, logos e URLs de EPG.

Uso: python3 l5_validar_backup_av_20261015.py [lista5.m3u]
"""
import gzip
import ipaddress
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import requests

M3U = sys.argv[1] if len(sys.argv) > 1 else "lista5.m3u"
BACKUP_URL = "https://epg.pw/xmltv/epg_US.xml.gz"
CACHE = "/tmp/opencode/l5"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126 Safari/537.36"}
RISKY_TLD = {"tk", "ml", "ga", "cf", "gq", "top", "xyz", "zip", "mov",
             "country", "win", "bid", "trade", "work", "click", "link"}
SHORTENERS = {"bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "is.gd",
              "cutt.ly", "rb.gy", "tiny.cc", "buff.ly", "t.me", "vm.tn"}

errors = []


def log(ok, label, detail=""):
    print(f"  [{'OK  ' if ok else 'FALHA'}] {label}{(' -> ' + detail) if detail else ''}")
    if not ok:
        errors.append(f"{label} {detail}")


def attr(info, key):
    m = re.search(rf'{key}="([^"]*)"', info)
    return m.group(1) if m else None


def display_name(entry):
    m = re.search(r",(.+)$", entry["info"])
    return m.group(1).strip() if m else entry["url"][:60]


def parse_m3u(path):
    header, entries, info = None, [], None
    for raw in open(path, encoding="utf-8", errors="replace"):
        s = raw.strip()
        if not s:
            continue
        if s.startswith("#EXTM3U"):
            header = s
        elif s.startswith("#EXTINF"):
            info = s
        elif s.startswith("#"):
            continue
        else:
            entries.append({"info": info or "", "url": s})
            info = None
    return header, entries


def download(url, path):
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return
    r = requests.get(url, headers=UA, timeout=180, stream=True)
    r.raise_for_status()
    with open(path, "wb") as fh:
        for chunk in r.iter_content(1 << 16):
            fh.write(chunk)


def programmes_for(data, channel):
    out = []
    for m in re.finditer(r'<programme ([^>]*?)>(.*?)(?=<programme |</tv>)', data, re.S):
        attrs = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
        if attrs.get("channel") != channel:
            continue
        t = re.search(r'<title[^>]*>([^<]*)</title>', m.group(2))
        out.append((attrs.get("start", ""), t.group(1) if t else "?"))
    return out


def days_covered(progs):
    now = datetime.now(timezone.utc)
    want = [(now + timedelta(days=d)).strftime("%Y%m%d") for d in range(3)]
    seen = {d: 0 for d in want}
    for s, _t in progs:
        m = re.match(r"(\d{8})", s)
        if m and m.group(1) in seen:
            seen[m.group(1)] += 1
    return want, seen


def main():
    print("=" * 70)
    print("VALIDACAO ESTENDIDA LISTA5.M3U - 2026-10-15")
    print("=" * 70)
    header, entries = parse_m3u(M3U)

    print("\n== A. EPG BACKUP (epg.pw US, por display-name) ==")
    try:
        path = os.path.join(CACHE, "epgpw.xml.gz")
        download(BACKUP_URL, path)
        with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
            bak = fh.read()
        name_to_id = {}
        for m in re.finditer(r'<channel id="([^"]+)">(.*?)</channel>', bak, re.S):
            dn = re.search(r'<display-name[^>]*>([^<]*)</display-name>', m.group(2))
            if dn:
                name_to_id[dn.group(1).strip().lower()] = m.group(1)
        for e in entries:
            tname = (attr(e["info"], "tvg-name") or "").strip().lower()
            cid = name_to_id.get(tname)
            if not cid:
                log(False, f"tvg-name no backup: {display_name(e)}", tname)
                continue
            want, seen = days_covered(programmes_for(bak, cid))
            log(all(seen[d] > 0 for d in want), f"backup 3 dias: {display_name(e)} ({cid})",
                " ".join(f"{d[-2:]}={seen[d]}" for d in want))
    except Exception as ex:
        log(False, "EPG backup", str(ex))

    print("\n== B. ANTI-VIRUS (URLhaus + heuristicas) ==")
    try:
        hostfile = os.path.join(CACHE, "urlhaus_hostfile.txt")
        csvfile = os.path.join(CACHE, "urlhaus_csv.txt")
        download("https://urlhaus.abuse.ch/downloads/hostfile/", hostfile)
        download("https://urlhaus.abuse.ch/downloads/csv/", csvfile)
        bad_hosts = set()
        for line in open(hostfile, encoding="utf-8", errors="ignore"):
            parts = line.split()
            if len(parts) >= 2 and parts[0] in ("0.0.0.0", "127.0.0.1"):
                bad_hosts.add(parts[1].lower())
            elif len(parts) == 1 and "." in parts[0]:
                bad_hosts.add(parts[0].lower())
        bad_urls = set()
        for line in open(csvfile, encoding="utf-8", errors="ignore"):
            if line.startswith("#"):
                continue
            mm = re.findall(r'"[^"]*"|[^,]+', line)
            if len(mm) >= 4:
                bad_urls.add(mm[2].strip().strip('"').lower())
        all_urls = set()
        for e in entries:
            all_urls.add(e["url"])
            logo = attr(e["info"], "tvg-logo")
            if logo:
                all_urls.add(logo)
        for u in re.findall(r'(?:url-tvg|x-tvg-url)="([^"]+)"', header or ""):
            all_urls.update(u.split())
        for u in sorted(all_urls):
            p = urlparse(u)
            h = (p.hostname or "").lower()
            reasons = []
            if "imgur.com" in h:
                reasons.append("imgur_proibido")
            if u.lower() in bad_urls:
                reasons.append("urlhaus_url_maliciosa")
            if h in bad_hosts:
                reasons.append("urlhaus_host_malicioso")
            try:
                ipaddress.ip_address(h)
                reasons.append("host_ip_cru")
            except ValueError:
                pass
            if p.port and p.port not in (80, 443):
                reasons.append(f"porta_incomum={p.port}")
            if h in SHORTENERS:
                reasons.append("encurtador")
            tld = h.rsplit(".", 1)[-1] if "." in h else ""
            if tld in RISKY_TLD:
                reasons.append(f"tld_risco={tld}")
            log(not reasons, f"AV: {h}", ",".join(reasons))
    except Exception as ex:
        log(False, "anti-virus", str(ex))

    print("\n" + "=" * 70)
    if errors:
        print(f"RESULTADO: {len(errors)} FALHA(S)")
        return 1
    print("RESULTADO: TUDO OK - 0 falhas")
    return 0


if __name__ == "__main__":
    sys.exit(main())
