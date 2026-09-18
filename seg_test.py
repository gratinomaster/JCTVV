#!/usr/bin/env python3
"""Final segment-level verification for the URLs that passed variant test."""
import subprocess

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"

urls = {
    "ABC dssott (ctr-all-hdri-sliding)": "https://linear-abcnews-akc-na-east-1.media.dssott.com/dvt2=exp=1789840108~url=%2Fclt1%2Fva02%2Fdisneyplus%2Fchannel%2F79449312-79dd-473d-873c-515ebf4b5e5f-1781081210579%2F~psid=441d7251-c40e-4736-a771-0d8c6ec1b66b~did=d720d615-cd19-4a2d-ad5b-9e087bf8efcd~country=US~kid=k02~hmac=3d6572843347faa43d07f261d315601c5dc20fb50f5a815dcb70f262ecb15816/clt1/va02/disneyplus/channel/79449312-79dd-473d-873c-515ebf4b5e5f-1781081210579/ctr-all-hdri-sliding.m3u8?r=1080&v=1&hash=c00ca54a5fd625c2ce1a442c983e81561832da94",
    "ABC akamaized (index)": "https://abcnews-livestreams.akamaized.net/out/v1/6a597119dbd5428a82dc11a2f514a1a2/abcn-live-10-cmaf-manifest/abcn-live-10-index.m3u8",
    "CBS master.m3u8": "https://dai.google.com/linear/hls/pa/event/Sid4xiTQTkCT1SLu6rjUSQ/stream/58e749d3-de16-4c7a-99fd-6f5bc0954ada:CHS/master.m3u8",
}

import re, urllib.parse
def curl(url, t=25):
    try:
        return subprocess.run(["curl","-sL","--max-time",str(t),"-A",UA,url],capture_output=True,text=True,timeout=t+10).stdout
    except Exception as e:
        return ""

for label, master_url in urls.items():
    print("="*60)
    print(label)
    m = curl(master_url)
    if "#EXTM3U" not in m[:300]:
        print("  master FALHA", m[:80].replace("\n"," | "))
        continue
    print("  master OK", len(m), "bytes")
    # first variant
    vurl = None
    for l in m.splitlines():
        l=l.strip()
        if l and not l.startswith("#"):
            vurl = urllib.parse.urljoin(master_url, l) if not l.startswith("http") else l
            break
    v = curl(vurl)
    segs = [l.strip() for l in v.splitlines() if l.strip() and not l.startswith("#")]
    print("  variante OK", len(v), "bytes,", len(segs), "segmentos")
    if segs:
        s = segs[0]
        surl = urllib.parse.urljoin(vurl, s) if not s.startswith("http") else s
        seg = curl(surl, 20)
        print("  segmento[0]:", len(seg), "bytes ->", "PLAYABLE" if len(seg) > 5000 else "DUVIDOSO")