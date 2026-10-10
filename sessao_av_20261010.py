#!/usr/bin/env python3
"""Sessao 2026-10-10: anti-virus (URLhaus + heuristicas locais) para as URLs finais.

Cobrem: streams aprovados, logos .jpg e fontes de EPG.
Inclui controles negativos (imgur + URLhaus) para provar que o detector funciona.
"""
import importlib.util
import json
import sys

BASE = "/home/runner/work/JCTVV/JCTVV/"
spec = importlib.util.spec_from_file_location("av", BASE + "av_check_20261008.py")
av = importlib.util.module_from_spec(spec)
spec.loader.exec_module(av)

STREAMS = [u for u, v in json.load(open(BASE + "sessao_streams_20261010.json")).items() if v["ok"]]

LOGOS = [
    "https://keyframe-cdn.abcnews.com/streamprovider11.jpg",
    "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
    "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/15de0523-3be4-4a9a-8159-7020114e7036/b6ff623a-26d6-4fd9-8bb8-0856adbf38ce/1280x720/match/676/380/image.jpg",
    "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/c9b2e2eb-7b87-435c-9510-eab2650ff944/8b584585-acf2-4c37-aa07-aaf2d077bb20/1280x720/match/676/380/image.jpg",
]

EPGS = [
    "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz",
    "https://epg.pw/xmltv/epg_US.xml.gz",
]

CONTROLES = [
    "https://imgur.com/a/xyz123",
    "http://110.136.5.74:44981/i",
    "https://bit.ly/3abcd",
]


def main():
    csvpath = av.ensure_downloaded()
    hosts = av.load_hosts()
    bad_urls = av.load_urls(csvpath)
    print(f"URLhaus: {len(hosts)} hosts / {len(bad_urls)} URLs maliciosas")

    todas = STREAMS + LOGOS + EPGS
    reprovadas = []
    for u in todas:
        r = av.check(u, hosts, bad_urls)
        print(f"{'REPROVADA' if r else 'APROVADA '} {u[:90]}" + (f"  -> {', '.join(r)}" if r else ""))
        if r:
            reprovadas.append((u, r))

    print("\n--- controles negativos (tem que reprovar) ---")
    ctrl_ok = True
    for u in CONTROLES:
        r = av.check(u, hosts, bad_urls)
        status = "OK (reprovado)" if r else "FALHA (passou!)"
        if not r:
            ctrl_ok = False
        print(f"  {status}: {u} -> {r}")

    print(f"\nTotal {len(todas)} | aprovadas {len(todas)-len(reprovadas)} | reprovadas {len(reprovadas)}")
    print(f"controles negativos: {'OK' if ctrl_ok else 'FALHOU'}")
    return 1 if (reprovadas or not ctrl_ok) else 0


if __name__ == "__main__":
    sys.exit(main())
