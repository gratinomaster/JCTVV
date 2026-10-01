#!/usr/bin/env python3
"""Passo 5 - motor anti-virus local para streams HLS.

Sem chave VirusTotal no ambiente, roda um scanner deterministico:
  1. assinatura EICAR em qualquer byte baixado
  2. magic bytes de malware/executavel (PE, ELF, RAR, ZIP, script, Mach-O)
  3. injecao no manifesto HLS (<script>, javascript:, data:, .exe/.dll/...)
  4. integridade do segmento (MPEG-TS 188/bytes ou fMP4)
  5. heuristicas de URL (punycode, IP crua, credencial embutida, CRLF, esquema)

Se VIRUSTOTAL_API_KEY existir no ambiente, consulta a API real.
"""
import json
import os
import re
import subprocess
import sys
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

EICAR = rb"X5O!P%@AP[4\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"

MAGIC = [
    (b"MZ", "PE/executavel Windows"),
    (b"\x7fELF", "ELF/executavel Linux"),
    (b"Rar!\x1a\x07", "RAR"),
    (b"PK\x03\x04", "ZIP"),
    (b"\xca\xfe\xba\xbe", "Mach-O"),
    (b"#!", "script shebang"),
    (b"<?php", "script PHP"),
    (b"<script", "HTML/JS"),
    (b"GIF89a", "GIF"), (b"GIF87a", "GIF"),
    (b"BM", "bitmap Windows"),
]

MANIFEST_INJ = re.compile(
    r"<script|javascript:|data:text/html|vbscript:|\.(exe|dll|bat|cmd|ps1|"
    r"scr|vbs|js|jar|msi|hta|cpl)([?\"'\s]|$)", re.I)

URL_BAD = re.compile(
    r"^[^a-z]+://|xn--|[\r\n]|\s|%0d%0a|user:pass@", re.I)

TS_OK = re.compile(rb"^.{188}G", re.S)


def curl(args, timeout=25):
    try:
        p = subprocess.run(["curl", "-sL", "-A", UA, "--max-time", str(timeout),
                            *args], capture_output=True, timeout=timeout + 10)
        return p.stdout
    except Exception:
        return b""


def join(parent, child):
    full = urllib.parse.urljoin(parent, child)
    pq = urllib.parse.urlsplit(parent).query
    if pq:
        sp = urllib.parse.urlsplit(full)
        if not sp.query:
            full = urllib.parse.urlunsplit(
                (sp.scheme, sp.netloc, sp.path, pq, sp.fragment))
    return full


def vt_check(url):
    key = os.environ.get("VIRUSTOTAL_API_KEY") or os.environ.get("VT_API_KEY")
    if not key:
        return None
    import base64
    uid = base64.urlsafe_b64encode(url.encode()).decode().rstrip("=")
    try:
        p = subprocess.run(["curl", "-s", "--max-time", "30", "-H",
                            f"x-apikey: {key}",
                            f"https://www.virustotal.com/api/v3/urls/{uid}"],
                           capture_output=True, timeout=40)
        d = json.loads(p.stdout)
        st = d.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
        mal = st.get("malicious", 0)
        sus = st.get("suspicious", 0)
        return {"malicious": mal, "suspicious": sus,
                "verdict": "MALICIOSO" if (mal or sus) else "SEGURO"}
    except Exception as e:
        return {"erro": str(e)[:60]}


def is_media(txt):
    """True se for media playlist (tem #EXTINF de segmento)."""
    return "#EXTINF:" in txt


def first_media_line(txt):
    """Primeira URI de segmento (apos um #EXTINF)."""
    lines = [l.strip() for l in txt.splitlines() if l.strip()]
    seen_inf = False
    for l in lines:
        if l.startswith("#EXTINF:"):
            seen_inf = True
            continue
        if not l.startswith("#") and seen_inf:
            return l
    return None


def first_variant(txt):
    lines = [l.strip() for l in txt.splitlines() if l.strip()]
    for i, l in enumerate(lines):
        if l.startswith("#EXT-X-STREAM-INF"):
            for j in range(i + 1, len(lines)):
                if not lines[j].startswith("#"):
                    return lines[j]
    return None


def get_segment(url):
    """Segue master -> variant -> segmento. Devolve (seg_url, profundidade)."""
    txt = curl([url]).decode("utf-8", "replace")
    if not txt.startswith("#EXTM3U"):
        return None, "nao-manifesto"
    if is_media(txt):
        seg = first_media_line(txt)
        return (join(url, seg) if seg else None), "media"
    var = first_variant(txt)
    if not var:
        seg = first_media_line(txt)
        return (join(url, seg) if seg else None), "media"
    vurl = join(url, var)
    vtxt = curl([vurl]).decode("utf-8", "replace")
    seg = first_media_line(vtxt)
    return (join(vurl, seg) if seg else vurl), "master->media"


def scan(url):
    achados = []
    # 5) heuristicas de URL
    if not url.lower().startswith("https://"):
        achados.append(f"esquema nao-https: {url[:24]}")
    if URL_BAD.search(url):
        achados.append("URL suspeita (punycode/credencial/CRLF)")
    host = urllib.parse.urlsplit(url).hostname or ""
    if re.match(r"^\d+\.\d+\.\d+\.\d+$", host):
        achados.append(f"host IP cru: {host}")

    # manifesto
    man = curl([url])
    if not man:
        achados.append("manifesto vazio")
        return {"url": url, "achados": achados, "ok": not achados}
    if EICAR in man:
        achados.append("!! assinatura EICAR no manifesto")
    for sig, nome in MAGIC:
        if man[:8].startswith(sig) and nome not in ("GIF", "bitmap Windows",
                                                    "HTML/JS"):
            achados.append(f"magic {nome} no manifesto")
            break

    rec_seg = 0
    if man.startswith(b"#EXTM3U"):
        m = MANIFEST_INJ.search(man.decode("utf-8", "replace"))
        if m:
            achados.append(f"injecao no manifesto: {m.group(0)[:30]}")
        seg, prof = get_segment(url)
        if not seg:
            achados.append("nao encontrou segmento")
        else:
            data = curl(["-r", "0-1500000", seg], timeout=30)
            rec_seg = len(data)
            if EICAR in data:
                achados.append("!! assinatura EICAR no segmento")
            for sig, nome in MAGIC:
                if data[:8].startswith(sig):
                    achados.append(f"!! magic {nome} no segmento")
                    break
            ts = len(data) >= 376 and data[0:1] == b"G" and data[188:189] == b"G"
            mp4 = b"ftyp" in data[:64] or b"moof" in data[:8192]
            aac = data[:2] in (b"\xff\xf1", b"\xff\xf9", b"\xff\xfb")
            if not (ts or mp4 or aac):
                achados.append(f"segmento nao e TS/fMP4/AAC ({rec_seg}b)")
    else:
        achados.append("resposta nao e manifesto HLS")

    vt = vt_check(url)
    return {"url": url, "achados": achados, "ok": not achados,
            "seg_bytes": rec_seg, "virustotal": vt}


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "lista5.m3u"
    urls, seen = [], set()
    for ln in open(src, encoding="utf-8", errors="replace"):
        s = ln.strip()
        if s and not s.startswith("#") and s not in seen:
            seen.add(s)
            urls.append(s)
    print(f"URLs unicas a escanear: {len(urls)}")
    if not os.environ.get("VIRUSTOTAL_API_KEY") and not os.environ.get("VT_API_KEY"):
        print("AVISO: sem VIRUSTOTAL_API_KEY -> usando motor local\n")
    with ThreadPoolExecutor(max_workers=5) as ex:
        res = list(ex.map(scan, urls))
    ruins = 0
    for r in res:
        st = "LIMPO" if r["ok"] else "INFECTADO"
        if not r["ok"]:
            ruins += 1
        print(f"[{st}] {r['url'][:88]}")
        for a in r["achados"]:
            print(f"         -> {a}")
        if r.get("virustotal"):
            print(f"         -> VirusTotal: {r['virustotal']}")
    print(f"\nANTIVIRUS: {len(res)-ruins}/{len(res)} URLs limpas, {ruins} rejeitadas")
    json.dump(res, open("l5_av_results.json", "w"), indent=1)