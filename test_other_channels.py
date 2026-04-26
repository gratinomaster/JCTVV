#!/usr/bin/env python3
import requests

streams = [
    ("Fox Business", "https://247.foxbusiness.com/hls/live/2003756/FBNHLSv3/master.m3u8?hdnea=exp=1776012240~acl=/*~hmac=effcc7473696adf98133071f5ed8126df348e7f2a1c38c2c9132265a8fb533ca"),
    ("Fox News", "https://247.foxnews.com/hls/live/2003586/FNCHLSv3/master.m3u8?hdnea=exp=1776012241~acl=/*~hmac=c9a0ed4c573c539e777f47f48b6cc6e2dec93bdd36b3d9da4a901b8e6105eb56"),
    ("CBS News", "https://dai.google.com/linear/hls/pa/event/Sid4xiTQTkCT1SLu6rjUSQ/stream/fb23b674-1517-4a63-a8bf-c29f7e166af9:TUL/master.m3u8"),
]

for name, url in streams:
    try:
        base = url.split('?')[0]
        r = requests.head(base, timeout=10, allow_redirects=True)
        print(f"{name}: {r.status_code}")
    except Exception as e:
        print(f"{name}: ERRO - {e}")