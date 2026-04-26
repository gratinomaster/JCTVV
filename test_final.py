#!/usr/bin/env python3
import requests

streams = [
    "https://abcnews-livestreams.akamaized.net/out/v1/6a597119dbd5428a82dc11a2f514a1a2/abcn-live-10-cmaf-manifest/abcn-live-10-index.m3u8",
    "https://linear-abcnews-akc-na-central-1.media.dssott.com/dvt2=exp=1777307045~url=%2Flas1%2Fva01%2Fdisneyplus%2Fchannel%2F79449312-79dd-473d-873c-515ebf4b5e5f-1776861675071%2F~psid=aed17fa7-fa25-4454-85b2-c9ea5bb5e7db~did=cb2150e2-9870-472c-a57d-d7a537fa8b2e~country=US~kid=k02~hmac=b13f3fb44230b594a62c96b98bdc2ee5063140f9faf64f4fe7e3428a9796c453/las1/va01/disneyplus/channel/79449312-79dd-473d-873c-515ebf4b5e5f-1776861675071/ctr-all-hdri-sliding.m3u8",
]

for url in streams:
    try:
        base = url.split('?')[0]
        r = requests.head(base, timeout=10, allow_redirects=True)
        print(f"{base[:50]}... -> {r.status_code}")
    except Exception as e:
        print(f"ERRO: {e}")