#!/usr/bin/env python3
"""Test stream URLs with proper GET requests"""
import requests

URLS = [
    ("ABC News Master", "https://linear-abcnews-ftc-na-west-1.media.dssott.com/dvt2=exp=1778024653~url=%2Flas1%2Fva01%2Fdisneyplus%2Fchannel%2F79449312-79dd-473d-873c-515ebf4b5e5f-1776861675071%2F~psid=bc389f1e-0e5e-4731-b9de-8f50cd074912~did=634f520e-2d96-4eaa-b37e-81a6d638a563~country=US~kid=k02~hmac=f06151aa3c784f46ff09e467c6783babc13f136c2da0879452bf551a52012f94/las1/va01/disneyplus/channel/79449312-79dd-473d-873c-515ebf4b5e5f-1776861675071/ctr-all-hdri-sliding.m3u8?r=1080&v=1&hash=ab84398225d4a583cf5479db7842af5fa60665cc"),
    ("ABC Akamai", "https://abcnews-livestreams.akamaized.net/out/v1/6a597119dbd5428a82dc11a2f514a1a2/abcn-live-10-cmaf-manifest/abcn-live-10-index.m3u8"),
    ("Fox Business", "https://247.foxbusiness.com/hls/live/2003756/FBNHLSv3/master.m3u8?hdnea=exp=1777941852~acl=/*~hmac=69b602dc84bda5220f56849399b00635fa6407bcdb68a90484858cee97783973"),
    ("Fox News", "https://247.foxnews.com/hls/live/2003586/FNCHLSv3/master.m3u8?hdnea=exp=1777941852~acl=/*~hmac=69b602dc84bda5220f56849399b00635fa6407bcdb68a90484858cee97783973"),
    ("CBS News", "https://dai.google.com/linear/hls/pa/event/Sid4xiTQTkCT1SLu6rjUSQ/stream/d2b621a2-baf4-427b-9fd6-c2d3d54c5465:CBF2/master.m3u8"),
]

for name, url in URLS:
    print(f"\nTesting {name}...")
    try:
        resp = requests.get(url, timeout=10, stream=True, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://www.google.com/'
        })
        content = resp.text[:500]
        print(f"  Status: {resp.status_code}")
        print(f"  Is M3U8: {'#EXTM3U' in content}")
        print(f"  Content preview: {content[:200]}")
        resp.close()
    except Exception as e:
        print(f"  ERROR: {e}")
