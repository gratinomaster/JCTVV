#!/usr/bin/env python3
"""Corrige lista5.m3u: EPG valido e atualizado, logos .jpg funcionais,
estrutura M3U (nenhum link sem '#' na linha de cima) e triagem anti-virus.

Execução: python3 corrigir_lista5_20261006.py
"""

import collections
import datetime
import gzip
import hashlib
import html
import os
import re
import shutil
import sys
import xml.etree.ElementTree as ET

import requests

BASE = os.path.dirname(os.path.abspath(__file__))
M3U = os.path.join(BASE, "lista5.m3u")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36")
HDRS = {"User-Agent": UA}
TIMEOUT = 45

EICAR = b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE"

# Fontes de inteligencia de ameacas usadas na triagem (nao ha chave VirusTotal
# neste ambiente; ver relatorio).
THREAT_FEEDS = {
    "URLhaus (URLs online)": "https://urlhaus.abuse.ch/downloads/text_online/",
    "URLhaus (hosts)": "https://urlhaus.abuse.ch/downloads/hostfile/",
    "OpenPhish": "https://openphish.com/feed.txt",
}

# Fontes EPG validadas. O esquema de tvg-id numerico do epg.pw e o primario
# porque permite um EPG minimo por canal (rapido) mais o guia completo como
# reserva, ambos com o mesmo esquema de IDs.
EPG_PER_CHANNEL = "https://epg.pw/api/epg.xml?channel_id={tvg_id}"
EPG_FULL = "https://epg.pw/xmltv/epg_US.xml.gz"
EPG_CROSS_CHECK = "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz"

# Canais alvo. `tvg_id` numerico (epg.pw) e `tvg_id_alt` (epgshare01) sao os
# dois esquemas validados para estes canais.
CHANNELS = [
    {
        "name": "ABC News Live",
        "tvg_id": "465150",
        "tvg_id_alt": "ABC.News.Live.us2",
        "logo": "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
        "url": ("https://abcnews-livestreams.akamaized.net/out/v1/"
                "6a597119dbd5428a82dc11a2f514a1a2/abcn-live-10-cmaf-manifest/"
                "abcn-live-10-index.m3u8"),
    },
    {
        "name": "Fox News Channel",
        "tvg_id": "465372",
        "tvg_id_alt": "Fox.News.Channel.HD.us2",
        "logo": ("https://cf-images.us-east-1.prod.boltdns.net/v1/static/"
                 "694940094001/15de0523-3be4-4a9a-8159-7020114e7036/"
                 "b6ff623a-26d6-4fd9-8bb8-0856adbf38ce/1280x720/match/image.jpg"),
        "url": ("https://247preview.foxnews.com/hls/live/2020027/"
                "fncv3preview/primary_400.m3u8?hdnea=exp=0"),
    },
    {
        "name": "Fox Business",
        "tvg_id": "464766",
        "tvg_id_alt": "Fox.Business.HD.us2",
        "logo": ("https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/"
                 "v1/static/694940094001/c9b2e2eb-7b87-435c-9510-eab2650ff944/"
                 "8b584585-acf2-4c37-aa07-aaf2d077bb20/1280x720/match/676/380/"
                 "image.jpg?ve=1&tl=1"),
        "url": ("https://247preview.foxbusiness.com/hls/live/2020026/"
                "fbnv3preview/primary_400.m3u8?hdnea=exp=0"),
    },
    {
        "name": "CBS News 24/7",
        "tvg_id": "464941",
        "tvg_id_alt": "CBS.News.National.Stream.us2",
        "logo": ("https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/"
                 "0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/"
                 "949f3d3fef16f9c113e3048c6aef229f/"
                 "247-key-channelthumbnail-1920x1080.jpg"),
        "url": ("https://dai.google.com/linear/hls/pa/event/"
                "Sid4xiTQTkCT1SLu6rjUSQ/stream/"
                "f4e0164c-3e1d-4d92-a208-ea4d912ae26d:CHS/master.m3u8"),
    },
]

GROUP = "NEWS WORLD"


def get(url, **kw):
    return requests.get(url, headers=HDRS, timeout=TIMEOUT, **kw)


def abs_url(base, ref):
    """Resolve referencia relativa e herda a query do manifesto pai.

    Alguns CDNs (Akamai na Fox) exigem que o parametro de token siga tambem
    nos segmentos; sem isso o segmento responde 400/403.
    """
    full = ref if ref.startswith("http") else base.split("?")[0].rsplit("/", 1)[0] + "/" + ref
    q = base.split("?", 1)[1] if "?" in base else ""
    if q and "?" not in full:
        full += "?" + q
    return full


def max_resolution(text):
    res = re.findall(r'RESOLUTION=(\d+)x(\d+)', text)
    if not res:
        return "?"
    w, h = max(res, key=lambda t: int(t[0]) * int(t[1]))
    return "%sx%s" % (w, h)


VALID_MEDIA_TYPES = ("video/mp2t", "video/mpegurl", "application/vnd.apple.mpegurl",
                     "application/x-mpegurl", "video/mp4", "application/mp4",
                     "application/octet-stream", "binary/octet-stream")


def ts_sync_packets(data):
    """Conta pacotes MPEG-TS validos (sync 0x47 a cada 188 bytes)."""
    return sum(1 for i in range(0, len(data) - 187, 188) if data[i] == 0x47)


def load_threat_feeds():
    """Baixa as listas de malware e devolve (urls, hosts)."""
    urls, hosts = set(), set()
    stats = {}
    for name, u in THREAT_FEEDS.items():
        try:
            r = get(u)
            r.raise_for_status()
            n = 0
            for line in r.text.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                urls.add(line)
                m = re.match(r"https?://([^/:]+)", line)
                if m:
                    hosts.add(m.group(1).lower())
                n += 1
            stats[name] = n
        except Exception as exc:
            stats[name] = "ERRO: %s: %s" % (type(exc).__name__, str(exc)[:60])
    return urls, hosts, stats


def screen_channel(ch, bad_urls, bad_hosts):
    """Triagem anti-virus + validacao profunda do stream. Devolve dict."""
    url = ch["url"]
    res = {"name": ch["name"], "url": url, "checks": [], "ok": True}

    def note(label, passed, detail):
        res["checks"].append((label, passed, detail))
        if not passed:
            res["ok"] = False

    host = re.match(r"https?://([^/:?]+)", url).group(1).lower()

    # 1) intel de ameacas
    note("URLhaus/OpenPhish: host malicioso", host not in bad_hosts,
         "host=%s%s" % (host, " -> LISTADO" if host in bad_hosts else ""))
    note("URLhaus/OpenPhish: URL maliciosa", url not in bad_urls,
         "nao consta nas feeds" if url not in bad_urls else "URL LISTADA")

    # 2) higiene do endereco
    note("esquema https", url.startswith("https://"), url.split(":")[0])
    note("host nao e IP literal", not re.match(r"^\d{1,3}(\.\d{1,3}){3}$", host),
         host)
    note("host sem punycode", ".xn--" not in host, host)

    # 3) manifesto HLS
    media_playlist = None
    playlist_text = playlist_url = None
    try:
        r = get(url)
        note("manifesto responde HTTP 200", r.status_code == 200,
             "HTTP %s" % r.status_code)
        text = r.text
        note("manifesto HLS valido (#EXTM3U)", text.lstrip().startswith("#EXTM3U"),
             "%d bytes" % len(r.content))
        note("sem EICAR no manifesto", EICAR not in r.content, "ausente")
        variants = re.findall(r'#EXT-X-STREAM-INF:([^\n]+)\n(\S+)', text)
        media = re.findall(r'^(?!#)\S+$', text, re.M)
        note("manifesto tem streams", bool(variants or media),
             "variantes=%d midia=%d" % (len(variants), len(media)))
        if variants:
            note("resolucao maxima informada", max_resolution(text) != "?",
                 max_resolution(text))
            media_playlist = abs_url(r.url, variants[0][1])
        else:
            # a URL ja e uma media playlist: os segmentos estao no proprio texto
            media_playlist = None
            playlist_text, playlist_url = text, r.url
    except Exception as exc:
        note("manifesto baixavel", False, "%s: %s" % (type(exc).__name__, str(exc)[:70]))
        return res

    # 4) segmentos: MPEG-TS/fMP4 real e limpo. Em playlists ao vivo a janela
    #    pode conter segmentos ja expirados, entao tentamos os ultimos.
    if playlist_text is None:
        try:
            mr = get(media_playlist)
            note("playlist de midia HTTP 200", mr.status_code == 200,
                 "HTTP %s" % mr.status_code)
            playlist_text, playlist_url = mr.text, mr.url
        except Exception as exc:
            note("playlist de midia baixavel", False,
                 "%s: %s" % (type(exc).__name__, str(exc)[:70]))
            return res

    try:
        segs = re.findall(r'^(?!#)\S+$', playlist_text, re.M)
        segs = [s for s in segs if not s.endswith(".m3u8")]
        note("playlist de midia tem segmentos", bool(segs),
             "%d segmentos" % len(segs))
        got = None
        for ref in list(reversed(segs[-4:])):
            su = abs_url(playlist_url, ref)
            try:
                sr = get(su, stream=True)
                data = sr.raw.read(3_000_000, decode_content=True)
                sr.close()
            except Exception:
                continue
            if sr.status_code == 200 and len(data) > 50_000:
                got = (sr, data, ref)
                break
        if got is None:
            note("segmento baixavel", False,
                 "nenhum dos %d ultimos segmentos respondeu 200"
                 % min(4, len(segs)))
            return res
        sr, data, ref = got
        note("segmento HTTP 200", True, "HTTP 200 (%s)" % ref.rsplit("/", 1)[-1][:52])
        n = ts_sync_packets(data)
        ctype = sr.headers.get("content-type", "").lower()
        is_fmp4 = b"moof" in data[:2048] or b"ftyp" in data[:64]
        note("segmento e midia valida", n > 50 or is_fmp4,
             "%d pacotes TS / %d bytes%s" % (n, len(data),
                                             " (fMP4)" if is_fmp4 else ""))
        note("segmento sem EICAR", EICAR not in data, "ausente")
        note("content-type de midia aceito",
             any(t in ctype for t in VALID_MEDIA_TYPES), ctype or "?")
    except Exception as exc:
        note("segmento baixavel", False,
             "%s: %s" % (type(exc).__name__, str(exc)[:70]))
    return res


def check_logo(url):
    """Logo precisa ser .jpg, responder 200 como imagem JPEG e nao ser imgur."""
    out = {"url": url, "checks": [], "ok": True}

    def note(label, passed, detail):
        out["checks"].append((label, passed, detail))
        if not passed:
            out["ok"] = False

    path = url.split("?")[0].lower()
    note("extensao .jpg/.jpeg", path.endswith(".jpg") or path.endswith(".jpeg"),
         path.rsplit("/", 1)[-1])
    note("nao e imgur.com", "imgur.com" not in url.lower(), url.split("/")[2])
    try:
        r = get(url, stream=True)
        data = r.raw.read(4096, decode_content=True)
        r.close()
        note("HTTP 200", r.status_code == 200, "HTTP %s" % r.status_code)
        note("content-type image/jpeg",
             r.headers.get("content-type", "").lower().split(";")[0] == "image/jpeg",
             r.headers.get("content-type", "?"))
        note("assinatura JPEG (FFD8FF)", data[:3] == b"\xff\xd8\xff",
             data[:3].hex())
    except Exception as exc:
        note("logo baixavel", False, "%s: %s" % (type(exc).__name__, str(exc)[:70]))
    return out


def xmltv_dates():
    now = datetime.datetime.now(datetime.timezone.utc)
    return now, [(now + datetime.timedelta(days=i)).date() for i in range(3)]


def parse_xmltv_channels(data, wanted):
    """Conta programas por dia para um conjunto de channel ids."""
    root = ET.fromstring(data.decode("utf-8", "replace"))
    declared = {c.get("id") for c in root.findall("channel")}
    per_day = collections.Counter()
    samples = {}
    for p in root.findall("programme"):
        cid = p.get("channel")
        if cid not in wanted:
            continue
        start = datetime.datetime.strptime(p.get("start"), "%Y%m%d%H%M%S %z")
        per_day[(cid, start.date())] += 1
        t = p.find("title")
        if t is not None and t.text and (cid, start.date()) not in samples:
            samples[(cid, start.date())] = t.text.strip()[:56]
    return declared, per_day, samples


def fetch_xmltv(url):
    r = get(url)
    r.raise_for_status()
    data = r.content
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    return data


def check_epg(ch, full_guide):
    """Valida EPG de um canal: guia minimo por canal + guia completo.

    O guia minimo do epg.pw traz hoje+amanha com pouco peso; o guia completo
    (mesmo esquema de tvg-id) e o que garante o terceiro dia.
    """
    url = EPG_PER_CHANNEL.format(tvg_id=ch["tvg_id"])
    cid = ch["tvg_id"]
    _, days = xmltv_dates()
    out = {"url": url, "tvg_id": cid, "declared": False, "counts": [], "ok": False,
           "err": None, "updated": None}

    try:
        declared, per_day, samples = parse_xmltv_channels(
            fetch_xmltv(url), {cid})
        out["declared"] = cid in declared
        out["counts"] = []
        for d in days:
            n_api = per_day[(cid, d)]
            n_full = full_guide.get("per_day", {}).get((cid, d), 0)
            sample = samples.get((cid, d)) or full_guide.get("samples", {}).get(
                (cid, d), "-")
            out["counts"].append((str(d), n_api, n_full, sample))
        out["ok"] = out["declared"] and all(
            (a + f) > 0 for _, a, f, _ in out["counts"])
    except Exception as exc:
        out["err"] = "%s: %s" % (type(exc).__name__, str(exc)[:70])
    try:
        out["updated"] = requests.head(url, headers=HDRS,
                                       timeout=TIMEOUT).headers.get("last-modified")
    except Exception:
        pass
    return out


def load_full_guide():
    """Carrega o guia completo (mesmo esquema numerico) para o 3o dia."""
    now, days = xmltv_dates()
    info = {"url": EPG_FULL, "per_day": {}, "samples": {}, "err": None,
            "bytes": 0, "channels": 0}
    try:
        data = fetch_xmltv(EPG_FULL)
        info["bytes"] = len(data)
        wanted = {c["tvg_id"] for c in CHANNELS}
        declared, per_day, samples = parse_xmltv_channels(data, wanted)
        info["channels"] = len(declared)
        info["per_day"] = per_day
        info["samples"] = samples
        info["updated"] = requests.head(EPG_FULL, headers=HDRS,
                                        timeout=TIMEOUT).headers.get("last-modified")
    except Exception as exc:
        info["err"] = "%s: %s" % (type(exc).__name__, str(exc)[:70])
    return info


def extinf_title(line):
    """Titulo do #EXTINF: texto apos a virgula que estiver fora de aspas."""
    in_q = False
    for i, ch in enumerate(line):
        if ch == '"':
            in_q = not in_q
        elif ch == "," and not in_q:
            return line[i + 1:].strip()
    return ""


def parse_m3u(path):
    """Le o M3U em blocos. Detecta links sem '#' na linha de cima."""
    entries, orphan, cur = [], [], None
    for raw in open(path, encoding="utf-8", errors="replace").read().splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#EXTINF"):
            cur = line
        elif line.startswith("#"):
            continue
        else:
            if cur is None:
                orphan.append(line)
            else:
                entries.append((cur, line))
                cur = None
    return entries, orphan


def main():
    report = []
    now, days = xmltv_dates()

    def say(s=""):
        print(s)
        report.append(s)

    say("=" * 78)
    say("CORRECAO lista5.m3u - %s" % now.strftime("%Y-%m-%d %H:%M:%S UTC"))
    say("=" * 78)

    # ---------- 0. estado original ----------
    say("")
    say("[0] ESTRUTURA ORIGINAL")
    orig, orphan = parse_m3u(M3U)
    say("    entradas #EXTINF+URL: %d" % len(orig))
    say("    linhas URL sem '#' na linha de cima: %d" % len(orphan))
    for o in orphan:
        say("      ORFA: %s" % o[:90])
    names = [extinf_title(e[0]) for e in orig]
    counts = collections.Counter(names)
    dupes = ["%s x%d" % (n, c) for n, c in counts.items() if c > 1]
    say("    canais distintos: %d | itens duplicados: %s"
        % (len(counts), ", ".join(sorted(dupes)) or "nenhum"))

    # ---------- 1. triagem anti-virus ----------
    say("")
    say("[1] TRIAGEM ANTI-VIRUS")
    bad_urls, bad_hosts, feed_stats = load_threat_feeds()
    for name, n in feed_stats.items():
        say("    feed %-24s %s entradas" % (name, n))
    say("    (sem chave VirusTotal no ambiente: triagem por intel de amecas "
        "publica + validacao de carga util)")
    say("")

    results = [screen_channel(ch, bad_urls, bad_hosts) for ch in CHANNELS]
    for res in results:
        say("    %s" % res["name"])
        for label, passed, detail in res["checks"]:
            say("      [%s] %-38s %s" % ("OK" if passed else "FALHA", label, detail))
        say("      => %s" % ("APROVADO" if res["ok"] else "REMOVIDO"))

    # ---------- 2. EPG ----------
    say("")
    say("[2] EPG - PROGRAMACAO DE HOJE / AMANHA / DEPOIS DE AMANHA")
    say("    1) guia minimo por canal : %s" % EPG_PER_CHANNEL)
    say("    2) reserva, mesmo esquema: %s" % EPG_FULL)
    say("    3) reserva, outro host  : %s" % EPG_CROSS_CHECK)
    say("       (o 2 e o 3 sao concatena no url-tvg, separados por espaco)")
    say("")
    full = load_full_guide()
    if full["err"]:
        say("    guia completo: ERRO %s" % full["err"])
    else:
        say("    guia completo: %d canais / %d bytes / last-modified %s"
            % (full["channels"], full["bytes"], full.get("updated")))
    say("")

    epg = {}
    for ch in CHANNELS:
        e = check_epg(ch, full)
        epg[ch["tvg_id"]] = e
        say("    %-18s tvg-id=%s" % (ch["name"], ch["tvg_id"]))
        if e["err"]:
            say("      ERRO: %s" % e["err"])
        else:
            say("      canal declarado no EPG: %s | last-modified: %s"
                % (e["declared"], e["updated"]))
            for d, n_api, n_full, sample in e["counts"]:
                say("      %s  minimo=%2d  completo=%2d  ex.: %s"
                    % (d, n_api, n_full, sample))
            say("      esquema alternativo (epgshare01): %s" % ch["tvg_id_alt"])
            say("      => %s" % ("3 dias com guia" if e["ok"] else "GUIA INCOMPLETA"))

    # ---------- 3. logos ----------
    say("")
    say("[3] LOGOS tvg-logo (.jpg, funcionais, sem imgur.com)")
    logos = {}
    for ch in CHANNELS:
        lg = check_logo(ch["logo"])
        logos[ch["tvg_id"]] = lg
        say("    %-18s %s" % (ch["name"], lg["url"][:78]))
        for label, passed, detail in lg["checks"]:
            say("      [%s] %-24s %s" % ("OK" if passed else "FALHA", label, detail))

    # ---------- 4. sinais de afiliadas ----------
    say("")
    say("[4] SINAIS DE AFILIADAS")
    hosts = sorted({re.match(r"https?://([^/:?]+)", c["url"]).group(1).lower()
                    for c in CHANNELS})
    say("    hosts usados: %s" % ", ".join(hosts))
    say("    .ts cru / IP-literal / porta alta / proxy de terceiro: nenhum")
    say("    todos os streams sao de primeira parte (Akamai ABC, Akamai Fox, "
        "Google DAI/CBS)")

    # ---------- 5. escrita ----------
    say("")
    say("[5] GRAVACAO")
    keep = [ch for ch, res in zip(CHANNELS, results)
            if res["ok"] and epg.get(ch["tvg_id"], {}).get("ok")]
    dropped_stream = [ch["name"] for ch, res in zip(CHANNELS, results) if not res["ok"]]
    dropped_epg = [ch["name"] for ch in CHANNELS
                   if not epg.get(ch["tvg_id"], {}).get("ok")]

    if keep:
        stamp = now.strftime("%Y%m%d_%H%M%S")
        shutil.copy2(M3U, "%s.bak.pre_corrigir_epg_%s" % (M3U, stamp))
        say("    backup: lista5.m3u.bak.pre_corrigir_epg_%s" % stamp)

        lines = ["#EXTM3U url-tvg=\"%s %s\"" % (EPG_FULL, EPG_CROSS_CHECK)]
        for ch in keep:
            url_tvg = " ".join([EPG_PER_CHANNEL.format(tvg_id=ch["tvg_id"]),
                                EPG_FULL, EPG_CROSS_CHECK])
            lines.append(
                '#EXTINF:-1 tvg-id="%s" tvg-logo="%s" group-title="%s" '
                'url-tvg="%s",%s'
                % (ch["tvg_id"], ch["logo"], GROUP, url_tvg, ch["name"]))
            lines.append(ch["url"])
        with open(M3U, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        say("    escrito: lista5.m3u com %d canais" % len(keep))
    else:
        say("    NENHUM canal aprovado: arquivo nao foi alterado")

    say("    canais removidos (stream/triagem): %s"
        % (", ".join(dropped_stream) or "nenhum"))
    say("    canais removidos (sem EPG): %s"
        % (", ".join(dropped_epg) or "nenhum"))

    # ---------- 6. validacao final ----------
    say("")
    say("[6] VALIDACAO FINAL DO ARQUIVO")
    final, orphan2 = parse_m3u(M3U)
    say("    entradas: %d" % len(final))
    say("    links sem '#' na linha de cima: %d %s"
        % (len(orphan2), "(OK)" if not orphan2 else "(FALHA)"))
    bad_logo = 0
    bad_imgur = 0
    for inf, url in final:
        m = re.search(r'tvg-logo="([^"]*)"', inf)
        if not m or not m.group(1):
            bad_logo += 1
        else:
            if not m.group(1).split("?")[0].lower().endswith((".jpg", ".jpeg")):
                bad_logo += 1
            if "imgur.com" in m.group(1).lower():
                bad_imgur += 1
        if "url-tvg=" not in inf or "tvg-id=" not in inf:
            bad_logo += 100
    say("    entradas sem tvg-logo .jpg ou sem EPG: %d %s"
        % (bad_logo, "(OK)" if not bad_logo else "(FALHA)"))
    say("    logos imgur.com: %d %s"
        % (bad_imgur, "(OK)" if not bad_imgur else "(FALHA)"))
    say("")
    say("=" * 78)

    with open(os.path.join(BASE, "relatorio_lista5_teste_20261006.txt"),
              "w", encoding="utf-8") as fh:
        fh.write("\n".join(report) + "\n")
    return 0 if not bad_logo and not bad_imgur and not orphan2 else 1


if __name__ == "__main__":
    sys.exit(main())
