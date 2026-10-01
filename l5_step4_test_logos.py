#!/usr/bin/env python3
"""Passo 4 - teste de logos: HTTP 200 + assinatura JPEG real (FFD8FF)."""
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

CANDIDATOS = {
    "ABC News (dssott)": "https://s.abcnews.com/images/Live/abc_news_live-abc-ml-250210_1739199021469_hpMain_16x9_608.jpg",
    "ABC News (akamai)": "https://keyframe-cdn.abcnews.com/streamprovider10.jpg",
    "FOX News": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/15de0523-3be4-4a9a-8159-7020114e7036/b6ff623a-26d6-4fd9-8bb8-0856adbf38ce/1280x720/match/676/380/image.jpg?ve=1&tl=1",
    "FOX Business": "https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/c9b2e2eb-7b87-435c-9510-eab2650ff944/8b584585-acf2-4c37-aa07-aaf2d077bb20/1280x720/match/676/380/image.jpg?ve=1&tl=1",
    "CBS News 24/7": "https://assets2.cbsnewsstatic.com/hub/i/r/2024/04/16/0fb75ad2-a909-44bb-87dc-86b9d51cbeb2/thumbnail/1280x720/949f3d3fef16f9c113e3048c6aef229f/247-key-channelthumbnail-1920x1080.jpg",
    "PLUTO CBS News (jpg?fm=jpg)": "https://images.pluto.tv/channels/5a6b92f6e22a617379789618/logo.png?fit=fill&fm=jpg&h=80&w=280",
    "PLUTO ABC News (jpg?fm=jpg)": "https://images.pluto.tv/channels/6508be683a0d700008c534e4/logo.png?fit=fill&fm=jpg&h=80&w=280",
    "epgshare01 dtil fox (jpg?fm=jpg)": "http://dtil.tmsimg.com/assets/s60179_ll_h15_ab.png?w=360&h=270&fm=jpg",
    "epgshare01 dtil abc (jpg?fm=jpg)": "http://dtil.tmsimg.com/assets/s113380_ll_h15_ab.png?w=360&h=270&fm=jpg",
    "epgshare01 dtil foxbiz (jpg?fm=jpg)": "http://dtil.tmsimg.com/assets/s58718_ll_h15_ac.png?w=360&h=270&fm=jpg",
    "plex cbs (jpg)": "https://metadata-static.plex.tv/d/gracenote/d3cf145e2a921140dfdecd6925c7a145.jpg",
}


def check(item):
    nome, url = item
    try:
        p = subprocess.run(
            ["curl", "-sL", "-A", UA, "--max-time", "20", "-r", "0-4095",
             "-w", "\n__META__%{http_code}|%{content_type}|%{size_download}",
             url],
            capture_output=True, timeout=30)
        out = p.stdout
        i = out.rfind(b"__META__")
        data, meta = out[:i], out[i + 8:].decode(errors="replace")
        code, ctype, size = (meta.split("|") + ["", "", ""])[:3]
        jpeg = data[:3] == b"\xff\xd8\xff"
        png = data[:8] == b"\x89PNG\r\n\x1a\n"
        return nome, {"code": code, "ctype": ctype, "size": size,
                      "jpeg": jpeg, "png": png, "bytes": len(data)}
    except Exception as e:
        return nome, {"erro": str(e)[:60]}


if __name__ == "__main__":
    with ThreadPoolExecutor(max_workers=8) as ex:
        res = dict(ex.map(check, CANDIDATOS.items()))
    for nome, r in res.items():
        tipo = "JPEG" if r.get("jpeg") else ("PNG" if r.get("png") else "??")
        print(f"{nome:<40} http={r.get('code'):<4} {tipo:<5} "
              f"{r.get('ctype','')[:38]:<40} {r.get('bytes',0)}b")
    json.dump(res, open("l5_logo_results.json", "w"), indent=1)