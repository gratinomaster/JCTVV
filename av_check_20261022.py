#!/usr/bin/env python3
"""Anti-virus/heuristica para URLs da lista5 (sem API key do VirusTotal).

Fontes: abuse.ch URLhaus (hostfile + CSV, com descompressao zip) e
heuristicas locais (IP cru, porta incomum, TLD de risco, encurtador,
imgur, spoof de marca, executavel).
"""
import csv, io, ipaddress, os, re, shutil, sys, zipfile
from urllib.parse import urlparse

import tldextract

HOSTFILE = "/tmp/opencode/urlhaus_hostfile.txt"
CSVFILE = "/tmp/opencode/urlhaus_csv.txt"
HOST_URL = "https://urlhaus.abuse.ch/downloads/hostfile/"
CSV_URL = "https://urlhaus.abuse.ch/downloads/csv/"
OPENPHISH_FILE = "/tmp/opencode/openphish_feed.txt"
OPENPHISH_URL = "https://openphish.com/feed.txt"
STATUS = []


def _curl(url, path):
    import subprocess
    subprocess.run(["curl", "-sSL", "-o", path, "--max-time", "300", url], check=True)


def ensure_downloaded():
    """Baixa as feeds. URLhaus pode estar indisponivel (410) sem Auth-Key:
    nesse caso seguimos so com OpenPhish + heuristicas locais."""
    for path, url in ((HOSTFILE, HOST_URL), (CSVFILE, CSV_URL)):
        if not os.path.exists(path) or os.path.getsize(path) == 0:
            print(f"baixando {url} ...")
            try:
                _curl(url, path)
            except Exception as e:
                STATUS.append(f"URLhaus indisponivel ({type(e).__name__})")
    if not os.path.exists(OPENPHISH_FILE) or os.path.getsize(OPENPHISH_FILE) == 0:
        print(f"baixando {OPENPHISH_URL} ...")
        try:
            _curl(OPENPHISH_URL, OPENPHISH_FILE)
        except Exception as e:
            STATUS.append(f"OpenPhish indisponivel ({type(e).__name__})")
    csvpath = CSVFILE
    with open(CSVFILE, "rb") as f:
        if f.read(2) == b"PK":
            out = CSVFILE.replace(".txt", "_unzip.txt")
            with zipfile.ZipFile(CSVFILE) as z:
                with z.open(z.namelist()[0]) as src, open(out, "wb") as dst:
                    shutil.copyfileobj(src, dst)
            csvpath = out
    return csvpath


def openphish_urls():
    urls, hosts = set(), set()
    if not os.path.exists(OPENPHISH_FILE):
        return urls, hosts
    with open(OPENPHISH_FILE, encoding="utf-8", errors="ignore") as f:
        for line in f:
            u = line.strip()
            if not u or u.startswith("#"):
                continue
            urls.add(u.lower())
            h = urlparse(u).hostname
            if h:
                hosts.add(h.lower())
    return urls, hosts


def _is_html(path):
    try:
        with open(path, "rb") as f:
            head = f.read(200).lstrip()
    except OSError:
        return False
    return head.startswith(b"<")


def load_hosts(path=HOSTFILE):
    hosts = set()
    if not os.path.exists(path) or _is_html(path):
        if os.path.exists(path):
            STATUS.append(f"URLhaus hostfile indisponivel (HTTP nao-dados: {path})")
        return hosts
    for line in open(path, encoding="utf-8", errors="ignore"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[0] in ("0.0.0.0", "127.0.0.1"):
            hosts.add(parts[1].lower())
        elif len(parts) == 1 and "." in parts[0]:
            hosts.add(parts[0].lower())
    return hosts


def load_urls(path):
    urls = set()
    if not os.path.exists(path) or _is_html(path):
        if os.path.exists(path):
            STATUS.append(f"URLhaus csv indisponivel (HTTP nao-dados: {path})")
        return urls
    with open(path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            if line.startswith("#"):
                continue
            try:
                parts = next(csv.reader(io.StringIO(line)))
            except Exception:
                continue
            if len(parts) >= 4:
                urls.add(parts[2].strip().lower())
    return urls


RISKY_TLD = {"tk", "ml", "ga", "cf", "gq", "top", "xyz", "zip", "mov",
             "country", "win", "bid", "trade", "work", "click", "link"}
SHORTENERS = {"bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "is.gd",
              "cutt.ly", "rb.gy", "tiny.cc", "buff.ly", "t.me", "vm.tn"}
OFFICIAL = ("abcnews.com", "cbsnews.com", "cbsnewsstatic.com", "cbsistatic.com", "foxnews.com",
            "foxbusiness.com", "dssott.com", "akamaized.net", "epg.pw",
            "epgshare01.online", "abuse.ch",
            # canais oficiais hospedados em FAST partners (Live NOW from FOX/CGTN)
            "amagi.tv")


def check(url, hosts, bad_urls):
    reasons = []
    p = urlparse(url)
    host = (p.hostname or "").lower()
    if p.scheme not in ("http", "https"):
        reasons.append(f"esquema_invalido={p.scheme}")
    if "imgur.com" in host:
        reasons.append("imgur_proibido")
    if url.lower() in bad_urls:
        reasons.append("urlhaus_url_maliciosa")
    if host in hosts:
        reasons.append("urlhaus_host_malicioso")
    for h in hosts:
        if host.endswith("." + h):
            reasons.append(f"urlhaus_subdominio_de={h}")
            break
    try:
        ipaddress.ip_address(host)
        reasons.append("host_ip_cru")
    except ValueError:
        pass
    if p.port and p.port not in (80, 443):
        reasons.append(f"porta_incomum={p.port}")
    ext = tldextract.extract(host)
    if ext.suffix and ext.suffix.split(".")[-1] in RISKY_TLD:
        reasons.append(f"tld_risco={ext.suffix}")
    if host in SHORTENERS:
        reasons.append("encurtador")
    for b in ("foxnews", "foxbusiness", "cbsnews", "abcnews", "cbsnstream"):
        if b in host and not any(host.endswith("." + d) or host == d for d in OFFICIAL):
            reasons.append(f"dominio_nao_oficial_da_marca={host}")
            break
    if re.search(r"\.(exe|apk|scr|bat|cmd|js|vbs|ps1|zip|rar)(\?|$)", p.path, re.I):
        reasons.append("arquivo_executavel_suspeito")
    return reasons


def main():
    csvpath = ensure_downloaded()
    hosts = load_hosts()
    bad_urls = load_urls(csvpath)
    ph_urls, ph_hosts = openphish_urls()
    bad_urls |= ph_urls
    hosts |= ph_hosts
    print(f"URLhaus: {len(hosts)} hosts, {len(bad_urls)} URLs maliciosas carregadas")
    print(f"OpenPhish: {len(ph_urls)} URLs / {len(ph_hosts)} hosts")
    for s in STATUS:
        print(f"AVISO: {s}")
    if not hosts and not bad_urls:
        print("AVISO: nenhuma base maliciosa disponivel (checagem so por heuristicas)")
    urls = [l.strip() for l in open(sys.argv[1]) if l.strip()]
    bad = 0
    for u in urls:
        r = check(u, hosts, bad_urls)
        if r:
            bad += 1
            print(f"REPROVADA: {u}\n    -> {', '.join(r)}")
        else:
            print(f"APROVADA : {u}")
    print(f"\nTotal {len(urls)} | Aprovadas {len(urls) - bad} | Reprovadas {bad}")
    return bad


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
