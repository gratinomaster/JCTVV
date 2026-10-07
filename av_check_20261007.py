#!/usr/bin/env python3
"""Anti-virus/heuristica para URLs da lista5 (sem API key do VirusTotal)."""
import csv, io, ipaddress, re, sys, tldextract
from urllib.parse import urlparse

HOSTFILE = "/tmp/opencode/urlhaus_hostfile.txt"
CSVFILE  = "/tmp/opencode/urlhaus_csv.txt"
HOST_URL = "https://urlhaus.abuse.ch/downloads/hostfile/"
CSV_URL  = "https://urlhaus.abuse.ch/downloads/csv/"

def ensure_downloaded():
    import os, subprocess
    for path, url in ((HOSTFILE, HOST_URL), (CSVFILE, CSV_URL)):
        if not os.path.exists(path) or os.path.getsize(path) == 0:
            print(f"baixando {url} ...")
            subprocess.run(["curl", "-sSL", "-o", path, "--max-time", "120", url], check=True)

def load_hosts():
    hosts = set()
    for line in open(HOSTFILE, encoding="utf-8", errors="ignore"):
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("#") or "abuse.ch" in line and "URLhaus" in line:
            continue
        if line.startswith("#"): continue
        # formato: 0.0.0.0 host  (hostfile estilo hosts)
        parts = line.split()
        if len(parts) >= 2 and (parts[0] in ("0.0.0.0", "127.0.0.1")):
            hosts.add(parts[1].lower())
        elif len(parts) == 1 and "." in parts[0]:
            hosts.add(parts[0].lower())
    return hosts

def load_urls():
    urls = set()
    with open(CSVFILE, encoding="utf-8", errors="ignore") as f:
        for line in f:
            if line.startswith("#"): continue
            parts = next(csv.reader(io.StringIO(line)))
            if len(parts) >= 4:
                urls.add(parts[2].strip().lower())
    return urls

RISKY_TLD = {"tk","ml","ga","cf","gq","top","xyz","zip","mov","country","win","bid","trade","work","click","link"}
SHORTENERS = {"bit.ly","tinyurl.com","t.co","goo.gl","ow.ly","is.gd","cutt.ly","rb.gy","tiny.cc","buff.ly","t.me","vm.tn","is.gd"}
ALLOWED_OFFICIAL = {"abcnews.com","s.abcnews.com","keyframe-cdn.abcnews.com","cbsnews.com","assets2.cbsnewsstatic.com",
 "sportshub.cbsistatic.com","cbsistatic.com","foxnews.com","a57.foxnews.com","foxbusiness.com","dssott.com",
 "media.dssott.com","akamaized.net","cbsnstream.cbsnews.com","epg.pw","epgshare01.online","github.com","githubusercontent.com"}

def check(url, hosts, bad_urls):
    reasons = []
    p = urlparse(url)
    host = (p.hostname or "").lower()
    if p.scheme not in ("http", "https"):
        reasons.append(f"esquema_invalido={p.scheme}")
    if "imgur.com" in host:
        reasons.append("imgur_proibido")
    # lista URLhaus (url completa)
    if url.lower() in bad_urls:
        reasons.append("urlhaus_url_maliciosa")
    # lista URLhaus (host)
    if host in hosts:
        reasons.append("urlhaus_host_malicioso")
    # subdominio de host malicioso
    for h in hosts:
        if host.endswith("." + h):
            reasons.append(f"urlhaus_subdominio_de={h}")
            break
    # host em IP cru
    try:
        ipaddress.ip_address(host)
        reasons.append("host_ip_cru")
    except ValueError:
        pass
    # porta incomum
    if p.port and p.port not in (80, 443):
        reasons.append(f"porta_incomum={p.port}")
    # TLD de risco
    ext = tldextract.extract(host)
    if ext.suffix and ext.suffix.split(".")[-1] in RISKY_TLD:
        reasons.append(f"tld_risco={ext.suffix}")
    # encurtador
    if host in SHORTENERS:
        reasons.append("encurtador")
    # host parecendo marca mas nao oficial (homografia/spoof)
    brands = ["foxnews", "foxbusiness", "cbsnews", "abcnews", "cbsnstream"]
    for b in brands:
        if b in host and host not in ALLOWED_OFFICIAL and not any(host.endswith("."+d) or host==d for d in ALLOWED_OFFICIAL):
            ok = any(host.endswith("." + d) for d in ("foxnews.com","foxbusiness.com","cbsnews.com","cbsistatic.com","abcnews.com","dssott.com","akamaized.net","cbsnstream.cbsnews.com"))
            if not ok:
                reasons.append(f"dominio_nao_oficial_da_marca={host}")
            break
    # path suspeito
    if re.search(r"\.(exe|apk|scr|bat|cmd|js|vbs|ps1|zip|rar)(\?|$)", p.path, re.I):
        reasons.append("arquivo_executavel_suspeito")
    return reasons

def main():
    ensure_downloaded()
    hosts = load_hosts(); bad_urls = load_urls()
    print(f"URLhaus: {len(hosts)} hosts maliciosos, {len(bad_urls)} URLs maliciosas carregadas")
    urls = [l.strip() for l in open(sys.argv[1]) if l.strip()]
    bad = 0
    for u in urls:
        r = check(u, hosts, bad_urls)
        if r:
            bad += 1
            print(f"REPROVADA: {u}\n    -> {', '.join(r)}")
        else:
            print(f"APROVADA : {u}")
    print(f"\nTotal {len(urls)} | Aprovadas {len(urls)-bad} | Reprovadas {bad}")
    return bad

if __name__ == "__main__":
    sys.exit(1 if main() else 0)
