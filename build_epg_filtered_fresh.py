#!/usr/bin/env python3
"""Build EPGFULL.xml.gz containing ONLY the channels present in the M3U
(NEWSWORLDNOVOS.m3u fetched from GitHub), overwriting the existing file.
"""
import gzip
import re
import os
import sys
import glob
import urllib.request
import xml.etree.ElementTree as ET
from collections import OrderedDict
from datetime import datetime, timezone, timedelta

M3U_URL = "https://github.com/gratinomaster/JCTV/raw/refs/heads/main/NEWSWORLDNOVOS.m3u"
M3U_FILE = "NEWSWORLDNOVOS.m3u"
OUTPUT = "EPGFULL.xml.gz"
WORKDIR = os.path.dirname(os.path.abspath(__file__))

SOURCES = [
    "https://iptv-epg.org/files/epg-ar.xml.gz",
    "https://iptv-epg.org/files/epg-br.xml.gz",
    "https://iptv-epg.org/files/epg-cl.xml.gz",
    "https://iptv-epg.org/files/epg-fr.xml.gz",
    "https://iptv-epg.org/files/epg-il.xml.gz",
    "https://iptv-epg.org/files/epg-mx.xml.gz",
    "https://iptv-epg.org/files/epg-pt.xml.gz",
    "https://iptv-epg.org/files/epg-us.xml.gz",
    "https://iptv-epg.org/files/epg-ve.xml.gz",
]

LOCAL_SOURCES = [
    os.path.join(WORKDIR, "epgshare_US2.xml.gz"),
    os.path.join(WORKDIR, "epgpw.xml.gz"),
    os.path.join(WORKDIR, "iptvepg.xml.gz"),
    os.path.join(WORKDIR, "EPGFULL.xml.gz"),
]

EXTRA_MAPPINGS = {
    "tviiptv": "TVI.HD.pt", "tvirealityiptv": "TVI.Reality.HD.pt",
    "tvihdpt": "TVI.HD.pt", "tvirealityhdpt": "TVI.Reality.HD.pt",
    "telefe": "Telefe.ar", "telefear": "Telefe.ar",
    "canaltelefeargentinaar": "Canal.Telefé.(Argentina).ar",
    "canaltelefe": "Canal.Telefé.(Argentina).ar",
    "cbseastwcbsus": "CBS.Streaming.SD.East.feed.us2",
    "cbseastus": "CBS.Streaming.SD.East.feed.us2",
    "cbsus": "CBS.Streaming.SD.East.feed.us2",
    "bigbrotherpluto": "BigBrother.us",
    "bigbrother247plutotv": "BigBrother.us",
    "telemundoeastus": "Telemundo.mx",
    "telemundous": "NoticiasTelemundoAHORA.us",
    "tmcfr": "TMC.fr", "tmc": "TMC.fr",
    "redevidabr": "Rede.Vida.br", "redevida": "Rede.Vida.br",
    "aljazeeraenglish": "AlJazeera.Arabic.net",
    "france24espanol": "France24enEspanol.ar",
    "tviusa": "TVI.HD.pt", "tvirealityusa": "TVI.Reality.HD.pt",
    "tvchilecl": "TVChile.cl",
    "teleformulamx": "TeleFormula.mx",
    "aljazeeraus": "AlJazeera.Arabic.net",
    "cgtnespanolus": "CGTNSpanish.cn",
    "cgtncctvnewsus": "CGTNSpanish.cn",
}


def norm(s):
    return re.sub(r'[^a-z0-9]', '', s.lower())


def normalize_id(s):
    return re.sub(r'[^a-z0-9]', '', s.lower())


def download_m3u():
    print("=" * 60)
    print("STEP 1: Downloading fresh M3U from GitHub")
    print("=" * 60)
    req = urllib.request.Request(M3U_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        content = resp.read().decode("utf-8", errors="replace")
    with open(M3U_FILE, "w", encoding="utf-8") as f:
        f.write(content)
    tvg_ids = set()
    tvg_names = {}
    for line in content.splitlines():
        for m in re.finditer(r'tvg-id="([^"]*)"', line):
            t = m.group(1).strip()
            if t and t != "0" and t != "(no tvg-id)":
                tvg_ids.add(t)
        mn = re.search(r'tvg-name="([^"]*)"', line)
        if mn:
            tid = re.search(r'tvg-id="([^"]*)"', line)
            if tid:
                tvg_names[tid.group(1)] = mn.group(1).lower().strip()
    print(f"  Saved {M3U_FILE} with {len(tvg_ids)} unique tvg-ids")
    return tvg_ids, tvg_names


def resolve_ch_id(ch_id, m3u_ids, id_mapping, name_to_tvgid):
    if ch_id in m3u_ids:
        return ch_id
    n = normalize_id(ch_id)
    if n in id_mapping:
        return id_mapping[n]
    if n in EXTRA_MAPPINGS and EXTRA_MAPPINGS[n] in m3u_ids:
        return EXTRA_MAPPINGS[n]
    return None


def parse_epg_file(path, m3u_ids, id_mapping, name_to_tvgid, matched, chans, progs, seen_progs, now, lo, hi):
    kind = "local" if not path.startswith("http") else "remote"
    ch_count = 0
    prog_count = 0
    openf = gzip.open if path.endswith(".gz") else open
    f = openf(path, "rb")
    for event, elem in ET.iterparse(f, events=("end",)):
        if elem.tag == "channel":
            cid = elem.get("id", "")
            real = resolve_ch_id(cid, m3u_ids, id_mapping, name_to_tvgid)
            if real and real not in matched:
                ser = ET.tostring(elem, encoding="unicode")
                new = ET.fromstring(ser)
                new.set("id", real)
                chans[real] = new
                matched.add(real)
                ch_count += 1
            elem.clear()
        elif elem.tag == "programme":
            ch = elem.get("channel", "")
            real = resolve_ch_id(ch, m3u_ids, id_mapping, name_to_tvgid)
            if real and real in matched:
                start = elem.get("start", "")
                try:
                    dt = datetime.strptime(start[:14], "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
                    if not (lo <= dt <= hi):
                        elem.clear()
                        continue
                except Exception:
                    pass
                stop = elem.get("stop", "")
                pkey = f"{real}|{start}|{stop}"
                if pkey not in seen_progs:
                    seen_progs.add(pkey)
                    ser = ET.tostring(elem, encoding="unicode")
                    p = ET.fromstring(ser)
                    p.set("channel", real)
                    progs.append(p)
                    prog_count += 1
            elem.clear()
    f.close()
    return ch_count, prog_count


def main():
    tvg_ids, tvg_names = download_m3u()
    id_mapping = {normalize_id(t): t for t in tvg_ids}
    name_to_tvgid = {norm(n): tid for tid, n in tvg_names.items() if n}

    now = datetime.now(timezone.utc)
    lo = now - timedelta(days=1)
    hi = now + timedelta(days=2, hours=6)

    matched = set()
    chans = OrderedDict()
    progs = []
    seen_progs = set()

    print()
    print("=" * 60)
    print("STEP 2: Parsing EPG sources and filtering to M3U channels")
    print("=" * 60)

    sources = SOURCES + LOCAL_SOURCES
    for src in sources:
        label = src.split("/")[-1]
        if src.startswith("http"):
            cached = os.path.join("/tmp/opencode", label)
            tmp = os.path.join("/tmp", f"tmp_{label}")
            if os.path.exists(cached) and os.path.getsize(cached) > 1000:
                path = cached
                print(f"\n  Using cached {label}...", flush=True)
            else:
                print(f"\n  Downloading {label}...", flush=True)
                try:
                    req = urllib.request.Request(src, headers={"User-Agent": "Mozilla/5.0"})
                    with urllib.request.urlopen(req, timeout=180) as resp:
                        data = resp.read()
                    with open(tmp, "wb") as f:
                        f.write(data)
                    path = tmp
                except Exception as e:
                    print(f"    FAILED: {e}")
                    continue
        else:
            path = src
            if not os.path.exists(path):
                continue
        print(f"  Parsing {label}...", flush=True)
        ch_count, prog_count = parse_epg_file(
            path, tvg_ids, id_mapping, name_to_tvgid,
            matched, chans, progs, seen_progs, now, lo, hi)
        print(f"    matched {ch_count} new channels, {prog_count} programmes "
              f"| total {len(matched)}/{len(tvg_ids)} channels")
        if len(matched) >= len(tvg_ids):
            print("  All channels matched!")
            break

    print()
    print("=" * 60)
    print("STEP 3: Writing output (overwrite)")
    print("=" * 60)

    missing = sorted(tvg_ids - set(chans.keys()))
    print(f"  Channels with EPG: {len(chans)}, missing from sources: {len(missing)}")
    if missing:
        print(f"  Missing: {missing}")

    lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    lines.append('<tv generator-info-name="JCTVV EPG Builder">')
    for cid in sorted(chans.keys()):
        lines.append(ET.tostring(chans[cid], encoding="unicode"))
    progs.sort(key=lambda p: p.get("start", ""))
    for p in progs:
        lines.append(ET.tostring(p, encoding="unicode"))
    lines.append("</tv>")
    xml_str = "\n".join(lines)

    out_path = os.path.join(WORKDIR, OUTPUT)
    with gzip.open(out_path, "wt", encoding="utf-8") as f:
        f.write(xml_str)
    print(f"  Written {OUTPUT} ({os.path.getsize(out_path):,} bytes compressed, "
          f"{len(xml_str):,} uncompressed)")

    print()
    print("=" * 60)
    print("STEP 4: Testing EPG (today/tomorrow)")
    print("=" * 60)
    root = ET.fromstring(xml_str)
    canais = root.findall("channel")
    programas = root.findall("programme")
    hoje = datetime.now().strftime("%Y%m%d")
    amanha = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
    prog_hoje = 0
    prog_amanha = 0
    canais_hoje = set()
    canais_amanha = set()
    for prog in programas:
        start = prog.get("start", "")
        ch = prog.get("channel", "")
        if start[:8] == hoje:
            prog_hoje += 1
            canais_hoje.add(ch)
        elif start[:8] == amanha:
            prog_amanha += 1
            canais_amanha.add(ch)
    print(f"  Channels: {len(canais)}")
    print(f"  Programmes: {len(programas)}")
    print(f"  Today ({hoje}): {prog_hoje} programmes in {len(canais_hoje)} channels")
    print(f"  Tomorrow ({amanha}): {prog_amanha} programmes in {len(canais_amanha)} channels")

    sample = 0
    for ch_id in sorted(canais_hoje):
        if sample >= 6:
            break
        titles = [p.findtext("title") or "?" for p in programas
                  if p.get("channel") == ch_id and p.get("start", "")[:8] == hoje][:2]
        print(f"    {ch_id}: {', '.join(titles)}")
        sample += 1

    if len(canais) > 0 and prog_hoje > 0 and prog_amanha > 0:
        print()
        print("  RESULT: EPG OK - has programmes for today and tomorrow!")
        sys.exit(0)
    else:
        print()
        print("  RESULT: EPG WARNING - missing today/tomorrow programmes")
        sys.exit(1)


if __name__ == "__main__":
    main()