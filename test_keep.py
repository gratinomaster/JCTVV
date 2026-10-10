#!/usr/bin/env python3
import requests, re
from urllib.parse import urljoin, urlsplit, urlunsplit

H = {'User-Agent': 'Mozilla/5.0'}
url = 'https://linear-abcnews-akc-na-west-1.media.dssott.com/dvt2=exp=1791744455~url=%2Flas1%2Fva01%2Fdisneyplus%2Fchannel%2F79449312-79dd-473d-873c-515ebf4b5e5f-1781164031838%2F~psid=33d46668-64f3-433f-a2eb-952ab2472b01~did=c6c84256-61b2-4742-b869-c58222ac4eaf~country=US~kid=k02~hmac=3d878f3dc7ea69a893bd94f4b33e79635e1968d8321a84a99da903409391d03f/las1/va01/disneyplus/channel/79449312-79dd-473d-873c-515ebf4b5e5f-1781164031838/ctr-all-hdri-sliding.m3u8?r=1080&v=1&hash=81fb88da5aab33fe54dc3f8d7ae5f0b2eaa56a8c'
r = requests.get(url, headers=H, timeout=30)
print(r.status_code)
print(r.text[:300])
