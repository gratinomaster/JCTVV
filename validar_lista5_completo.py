#!/usr/bin/env python3
"""
Validacao completa e independente da lista5.m3u (usa o arquivo final, como um player):
  1. estrutura M3U (url-tvg, #EXTINF acima de cada link, sem duplicatas, sem imgur, https)
  2. EPG de cada url-tvg: HTTP 200, XMLTV valido e programacao de hoje/amanha/depois
  3. logos: .jpg, JPEG real, sem imgur
  4. streams: manifest -> variante -> segmento com bytes de midia
  5. triagem anti-virus: blocklists + heuristicas + magic bytes

Uso: python3 validar_lista5_completo.py
"""
import gzip
import io
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict, Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, urljoin

import requests

BASE = os.path.dirname(os.path.abspath(__file__))
LISTA = os.path.join(BASE, "lista5.m3u")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}

BLOCKLISTS = [
    ("URLhaus mirror", "https://malware-filter.gitlab.io/malware-filter/urlhaus-filter-online.txt"),
    ("phishing.army", "https://phishing.army/download/phishing_army_blocklist_extended.txt"),
    ("ipsum malware IPs", "https://raw.githubusercontent.com/stamparm/ipsum/master/levels/3.txt"),
    ("Feodo Tracker", "https://feodotracker.abuse.ch/downloads/ipblocklist.txt"),
    ("StevenBlack hosts", "https://raw.githubusercontent.com/StevenBlack/hosts/master/hosts"),
]
RISKY_TLDS = {"tk", "ml", "ga", "cf", "gq", "xyz", "top", "click", "link", "work", "rest",
              "zip", "mov", "country", "kim", "loan", "download", "racing", "party",
              "science", "stream", "bid", "trade", "date", "faith", "win", "review"}
SHORTENERS = {"bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "is.gd", "buff.ly",
              "t.ly", "cutt.ly", "rb.gy", "rebrand.ly", "trib.al"}
EXEC_EXT = (".exe", ".msi", ".bat", ".cmd", ".scr", ".pif", ".com", ".vbs", ".js", ".jar",
            ".ps1", ".apk", ".dll", ".hta", ".reg", ".lnk", ".iso", ".img")
MAGIC = {b"MZ": "PE/EXE", b"\x7fELF": "ELF", b"%PDF": "PDF", b"PK\x03\x04": "ZIP",
         b"Rar!": "RAR", b"\xd0\xcf\x11\xe0": "MS-OLE", b"7z\xbc\xaf": "7Z",
         b"\xca\xfe\xba\xbe": "MACHO-FAT", b"\xfe\xed\xfa": "MACHO"}

# ids numericos (epg.pw) equivalentes aos ids canonicos (iptv-epg.org) da lista5
ALIASES = {
    "ABCNewsLive.us": ["465150", "408627", "3474"],
    "CBSNews.us": ["464941"],
    "FoxBusiness.us": ["464766", "408654"],
}

fails, warns = [], []


def fail(msg):
    fails.append(msg)
    print(f"  [FALHA] {msg}")


def warn(msg):
    warns.append(msg)
    print(f"  [AVISO] {msg}")


def ok(msg):
    print(f"  [OK   ] {msg}")


def parse_m3u(path):
    """Retorna (header_epg_urls, [(attrs, name, url)])."""
    lines = [l.strip() for l in open(path, encoding="utf-8").read().splitlines() if l.strip()]
    epg_urls = []
    chans = []
    pending = None
    for i, l in enumerate(lines):
        if l.startswith("#EXTM3U"):
            m = re.search(r'url-tvg="([^"]*)"', l)
            if m:
                epg_urls += m.group(1).split()
            continue
        if l.startswith("#EXTINF"):
            attrs = dict(re.findall(r'([a-zA-Z0-9-]+)="([^"]*)"', l))
            name = l.split(",", 1)[1] if "," in l else ""
            pending = (attrs, name)
            continue
        if l.startswith("#"):
            continue
        chans.append((pending or ({}, ""), l))
        pending = None
    return epg_urls, chans, lines


def load_blocks():
    out = {}
    for name, url in BLOCKLISTS:
        try:
            r = requests.get(url, timeout=120, headers=UA)
            if r.status_code != 200:
                warn(f"blacklist '{name}' indisponivel (HTTP {r.status_code})")
                continue
            hosts = set()
            for line in r.text.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                line = line.split()[0]
                if line.startswith("http"):
                    line = (urlparse(line).hostname or "").lower()
                if line:
                    hosts.add(line.lower())
            out[name] = hosts
            print(f"  [AV   ] blacklist '{name}': {len(hosts)} hosts")
        except Exception as e:
            warn(f"blacklist '{name}' falhou: {type(e).__name__}")
    return out


def av_url(url, blocks):
    reasons = []
    p = urlparse(url)
    host = (p.hostname or "").lower()
    if not host:
        return ["URL invalido"]
    if p.scheme != "https":
        reasons.append(f"esquema '{p.scheme}' (sem TLS)")
    if "imgur" in host:
        reasons.append("imgur.com")
    if p.path.lower().endswith(EXEC_EXT):
        reasons.append("extensao executavel")
    if p.port and p.port not in (80, 443):
        reasons.append(f"porta {p.port}")
    if host.rsplit(".", 1)[-1] in RISKY_TLDS:
        reasons.append(f"TLD '.{host.rsplit('.', 1)[-1]}'")
    if host in SHORTENERS:
        reasons.append("encurtador")
    if p.username or p.password:
        reasons.append("credenciais na URL")
    if host.replace(".", "").isdigit():
        reasons.append("IP cru")
    for n, hosts in blocks.items():
        if host in hosts:
            reasons.append(f"blacklist '{n}'")
    return reasons


def av_bytes(data, allow):
    bad = []
    for sig, name in MAGIC.items():
        if data.startswith(sig):
            bad.append(name)
    if b"<script" in data[:4000].lower():
        bad.append("HTML com <script>")
    return [b for b in bad if b not in allow]


def check_logo(url, blocks):
    p = urlparse(url)
    r = {"url": url}
    reasons = av_url(url, blocks)
    if not p.path.lower().endswith((".jpg", ".jpeg")):
        reasons.append("extensao nao .jpg")
    try:
        resp = requests.get(url, timeout=45, headers=UA, allow_redirects=True)
        r["status"] = resp.status_code
        r["bytes"] = len(resp.content)
        r["ctype"] = resp.headers.get("content-type", "")
        if resp.status_code != 200:
            reasons.append(f"HTTP {resp.status_code}")
        if resp.content[:3] != b"\xff\xd8\xff":
            reasons.append("nao e JPEG real")
        if "image/jpeg" not in r["ctype"].lower():
            reasons.append(f"content-type {r['ctype']}")
        reasons += av_bytes(resp.content, allow=())
    except Exception as e:
        reasons.append(f"{type(e).__name__}: {e}")
    r["ok"] = not reasons
    r["reasons"] = reasons
    return r


def check_stream(url, blocks):
    reasons = av_url(url, blocks)
    res = {"url": url}
    s = requests.Session()
    s.headers.update(UA)
    try:
        r = s.get(url, timeout=30, allow_redirects=True)
        res["status"] = r.status_code
        if r.status_code != 200:
            reasons.append(f"HTTP {r.status_code}")
            return {**res, "ok": False, "reasons": reasons}
        if "#EXTM3U" not in r.text[:400]:
            reasons.append("nao e manifesto HLS")
            return {**res, "ok": False, "reasons": reasons}
        lines = r.text.splitlines()
        variants = []
        for i, ln in enumerate(lines):
            if ln.startswith("#EXT-X-STREAM-INF"):
                bw = re.search(r"BANDWIDTH=(\d+)", ln)
                reso = re.search(r"RESOLUTION=(\S+)", ln)
                for j in range(i + 1, len(lines)):
                    nx = lines[j].strip()
                    if nx and not nx.startswith("#"):
                        variants.append((int(bw.group(1)) if bw else 0,
                                         reso.group(1) if reso else "?",
                                         urljoin(r.url, nx)))
                        break
        variants.sort(key=lambda x: -x[0])
        res["variants"] = len(variants)
        if not variants:
            reasons.append("sem variantes")
            return {**res, "ok": False, "reasons": reasons}
        bw, reso, vurl = variants[0]
        rv = s.get(vurl, timeout=30)
        if rv.status_code != 200:
            reasons.append(f"variante HTTP {rv.status_code}")
            return {**res, "ok": False, "reasons": reasons}
        segs = [urljoin(rv.url, l.strip()) for l in rv.text.splitlines()
                if l.strip() and not l.startswith("#")][:3]
        good = 0
        sizes = []
        for sg in segs:
            rs = s.get(sg, timeout=30)
            if rs.status_code == 200 and len(rs.content) > 2000:
                good += 1
                sizes.append(len(rs.content))
                reasons += av_bytes(rs.content, allow=())
        res.update(segments=f"{good}/{len(segs)}", resolution=reso, bitrate=bw, sizes=sizes)
        if good == 0:
            reasons.append("nenhum segmento com bytes de midia")
    except Exception as e:
        reasons.append(f"{type(e).__name__}: {e}")
    res["ok"] = not reasons
    res["reasons"] = reasons
    return res


def check_epg(url, wanted_ids, blocks, alias_ids=None, local=False):
    """wanted_ids: {tvg-id: nome}. alias_ids: {tvg-id: [ids numericos]}. Retorna cobertura."""
    res = {"url": url}
    reasons = av_url(url, blocks) if not local else []
    try:
        if local:
            r = None
            with open(url, "rb") as f:
                data = f.read()
            res["status"] = 200
        else:
            r = requests.get(url, timeout=900, headers=UA)
            res["status"] = r.status_code
            res["lm"] = r.headers.get("last-modified")
            if r.status_code != 200:
                reasons.append(f"HTTP {r.status_code}")
                return {**res, "ok": False, "reasons": reasons, "cov": {}}
            data = r.content
        if data[:2] == b"\x1f\x8b":
            try:
                data = gzip.decompress(data)
            except Exception:
                reasons.append("gzip invalido")
        root = ET.fromstring(data)
        chans = {c.get("id"): (c.find("display-name").text
                               if c.find("display-name") is not None else "")
                 for c in root.findall("channel")}
        res["channels"] = len(chans)
        res["programmes"] = len(root.findall("programme"))
        today = datetime.now(timezone.utc).date()
        days = [today + timedelta(days=i) for i in range(3)]
        pcd = defaultdict(Counter)
        for p in root.findall("programme"):
            s = (p.get("start") or "")[:8]
            if len(s) != 8:
                continue
            try:
                d = datetime.strptime(s, "%Y%m%d").date()
            except ValueError:
                continue
            pcd[p.get("channel")][d] += 1
        cov = {}
        for cid, nm in wanted_ids.items():
            if cid not in chans:
                cov[cid] = (nm, None, [0, 0, 0])
                continue
            c = pcd.get(cid, Counter())
            cov[cid] = (nm, chans[cid], [c.get(d, 0) for d in days])
        res["cov"] = cov
        res["alias_cov"] = {}
        for cid, al in (alias_ids or {}).items():
            for a in al:
                if a in chans:
                    c = pcd.get(a, Counter())
                    res["alias_cov"][a] = (chans[a], [c.get(d, 0) for d in days])
    except Exception as e:
        reasons.append(f"{type(e).__name__}: {e}")
        res["cov"] = {}
    res["ok"] = not reasons
    res["reasons"] = reasons
    return res


def main():
    today = datetime.now(timezone.utc).date()
    print("=" * 78)
    print(f"VALIDACAO COMPLETA lista5.m3u - {datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S} UTC")
    print("=" * 78)

    epg_urls, chans, lines = parse_m3u(LISTA)
    print(f"\n[1] ESTRUTURA M3U  ({len(chans)} canais)")
    if not epg_urls:
        fail("cabecalho #EXTM3U sem url-tvg")
    else:
        ok(f"url-tvg com {len(epg_urls)} fonte(s)")
    for u in epg_urls:
        print(f"        {u}")
    urls = [c[1] for c in chans]
    if len(set(urls)) != len(urls):
        fail("URLs de stream duplicadas")
    else:
        ok("sem URLs duplicadas")
    for i, l in enumerate(lines):
        if not l.startswith("#") and not lines[i - 1].startswith("#EXTINF"):
            fail(f"link sem #EXTINF na linha de cima: {l[:70]}")
    ok("todo link tem #EXTINF imediatamente acima")
    if any("imgur" in l.lower() for l in lines):
        fail("contem imgur.com")
    else:
        ok("nenhum imgur.com")
    for (attrs, name), url in chans:
        for attr in ("tvg-id", "tvg-logo"):
            if attr not in attrs:
                fail(f"canal '{name}' sem {attr}")
        logo = attrs.get("tvg-logo", "")
        if logo and not urlparse(logo).path.lower().endswith((".jpg", ".jpeg")):
            fail(f"logo de '{name}' nao termina em .jpg: {logo[:70]}")
        if not url.lower().startswith("https://"):
            fail(f"stream de '{name}' nao usa https")
    ok("atributos tvg-id/tvg-logo presentes; logos .jpg; streams https")

    print("\n[2] ANTI-VIRUS - carregando blocklists")
    blocks = load_blocks()

    print("\n[3] LOGOS")
    logos = {}
    with ThreadPoolExecutor(max_workers=4) as ex:
        for (attrs, name), r in zip(chans, ex.map(lambda c: check_logo(c[0][0].get("tvg-logo", ""), blocks), chans)):
            logos[name] = r
            (ok if r["ok"] else fail)(f"{name}: {r.get('status')} {r.get('bytes')}B "
                                     f"{r.get('ctype')} {r['url'][:70]}"
                                     + ("" if r["ok"] else f" -> {r['reasons']}"))

    print("\n[4] STREAMS")
    streams = {}
    with ThreadPoolExecutor(max_workers=4) as ex:
        for (attrs, name), r in zip(chans, ex.map(lambda c: check_stream(c[1], blocks), chans)):
            streams[name] = r
            (ok if r["ok"] else fail)(f"{name}: HTTP {r.get('status')} "
                                     f"variantes={r.get('variants')} segmentos={r.get('segments')} "
                                     f"{r.get('resolution')} {r.get('bitrate')}bps "
                                     f"{r['url'][:60]}"
                                     + ("" if r["ok"] else f" -> {r['reasons']}"))

    print("\n[5] EPG por fonte (url-tvg) - cobertura hoje/amanha/depois de amanha")
    wanted = {attrs.get("tvg-id"): name for (attrs, name), _ in chans}
    aliases = {attrs.get("tvg-id"): ALIASES.get(attrs.get("tvg-id"), [])
               for (attrs, name), _ in chans}
    for u in epg_urls:
        r = check_epg(u, wanted, blocks, aliases)
        if not r["ok"]:
            warn(f"fonte indisponivel: {u} -> {r['reasons']}")
            continue
        print(f"\n  FONTE {u}")
        print(f"    HTTP {r['status']} | last-modified={r['lm']} | "
              f"{r['channels']} canais | {r['programmes']} programas")
        for cid, (nm, disp, cov) in r["cov"].items():
            if disp is None:
                alias_hit = [f"{a}{r['alias_cov'][a][1]}" for a in aliases.get(cid, [])
                             if a in r.get("alias_cov", {})]
                if alias_hit:
                    ok(f"{nm}: id={cid} ausente, mas alias epg.pw com cobertura {alias_hit}")
                else:
                    warn(f"{nm}: id={cid} ausente nesta fonte")
            elif all(cov):
                ok(f"{nm}: id={cid} '{disp}' hoje/amanha/depois={cov}")
            else:
                fail(f"{nm}: id={cid} '{disp}' cobertura incompleta {cov}")
        for a, (disp, cov) in r.get("alias_cov", {}).items():
            if all(cov):
                ok(f"alias {a} '{disp}' hoje/amanha/depois={cov}")
            else:
                warn(f"alias {a} '{disp}' cobertura parcial {cov}")

    local_epg = os.path.join(BASE, "lista5_epg.xml.gz")
    if os.path.exists(local_epg):
        r = check_epg(local_epg, wanted, blocks, aliases, local=True)
        print(f"\n  FONTE LOCAL (sera publicada em lista5_epg.xml.gz)")
        print(f"    {r['channels']} canais | {r['programmes']} programas")
        for cid, (nm, disp, cov) in r["cov"].items():
            (ok if disp and all(cov) else fail)(
                f"{nm}: id={cid} '{disp}' hoje/amanha/depois={cov}")

    print("\n" + "=" * 78)
    print(f"RESULTADO: {len(fails)} falha(s), {len(warns)} aviso(s)")
    for f in fails:
        print(f"  FALHA: {f}")
    for w in warns:
        print(f"  AVISO: {w}")
    print("=" * 78)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
