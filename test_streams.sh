#!/bin/bash

# Script para testar streams M3U e verificar quais estão funcionando

URLS=(
"https://linear-abcnews-akc-na-east-1.media.dssott.com/dvt2=exp=1777376569~url=%2Fclt1%2Fva02%2Fdisneyplus%2Fchannel%2F79449312-79dd-473d-873c-515ebf4b5e5f-1776583682323%2F~psid=bb4b1b48-cc84-4765-8da5-57bd8dfd746d~did=21f2504c-62ee-4b01-a1d7-f19fb3783b1a~country=US~kid=k02~hmac=ceef98cf129f9a0ab5fab97b3b7c1bc3f935350e6ca1b9943124b48a18ad5ca4/clt1/va02/disneyplus/channel/79449312-79dd-473d-873c-515ebf4b5e5f-1776583682323/ctr-all-hdri-sliding.m3u8?r=1080&v=1&hash=0ce6d6ffe5eed1546b2d7ba51fca94a7850f62ea"
"https://linear-abcnews-akc-na-east-1.media.dssott.com/dvt2=exp=1777376569~url=%2Fclt1%2Fva02%2Fdisneyplus%2Fchannel%2F79449312-79dd-473d-873c-515ebf4b5e5f-1776583682323%2F~psid=bb4b1b48-cc84-4765-8da5-57bd8dfd746d~did=21f2504c-62ee-4b01-a1d7-f19fb3783b1a~country=US~kid=k02~hmac=ceef98cf129f9a0ab5fab97b3b7c1bc3f935350e6ca1b9943124b48a18ad5ca4/clt1/va02/disneyplus/channel/79449312-79dd-473d-873c-515ebf4b5e5f-1776583682323/cmaf-cenc-ctr-1700K/1700_hdri_slide.m3u8"
"https://linear-abcnews-akc-na-east-1.media.dssott.com/dvt2=exp=1777376569~url=%2Fclt1%2Fva02%2Fdisneyplus%2Fchannel%2F79449312-79dd-473d-873c-515ebf4b5e5f-1776583682323%2F~psid=bb4b1b48-cc84-4765-8da5-57bd8dfd746d~did=21f2504c-62ee-4b01-a1d7-f19fb3783b1a~country=US~kid=k02~hmac=ceef98cf129f9a0ab5fab97b3b7c1bc3f935350e6ca1b9943124b48a18ad5ca4/clt1/va02/disneyplus/channel/79449312-79dd-473d-873c-515ebf4b5e5f-1776583682323/audio-aac-1-64K/64_slide.m3u8"
"https://linear-abcnews-akc-na-east-1.media.dssott.com/int/ps01/disney/40585aad-ff4a-4a54-9aa6-b67ecdb44570/unenc-all-69074290-b7d6-4d05-b712-d0da42050ae5-364485b5-a4f8-486d-bad7-20b21741936f.m3u8?r=720&fr=60&a=1&v=1&xp=1&hash=6782a5bc9b684fe4439e541a5d2bcea641f6374d"
"https://linear-abcnews-akc-na-east-1.media.dssott.com/int/ps01/disney/05ea2da4-fc45-47a9-a103-f6522f53e116/unenc-all-dca599bb-15f9-4dea-8953-4f3032c852df-104251a6-bbdd-4926-9208-0bb42ae40437.m3u8?r=720&fr=60&a=1&v=1&xp=1&hash=6782a5bc9b684fe4439e541a5d2bcea641f6374d"
"https://linear-abcnews-akc-na-east-1.media.dssott.com/int/ps01/disney/f35622f1-8fe6-4ea5-990f-346752bf4d4f/unenc-all-971d3d22-d877-4f3a-a793-5270a7eafc50-08a66a85-4ebc-4056-a9db-c48c01bfe6c4.m3u8?r=720&fr=60&a=1&v=1&xp=1&hash=6782a5bc9b684fe4439e541a5d2bcea641f6374d"
"https://linear-abcnews-akc-na-east-1.media.dssott.com/int/ps01/disney/d215ffaf-b343-4fe8-8786-2b42667a9716/unenc-all-ba230f9a-e352-46a4-991d-0f1873acee3a-e8d782aa-5b41-4409-9da9-31bb0854a2fb.m3u8?r=720&fr=60&a=1&v=1&xp=1&hash=6782a5bc9b684fe4439e541a5d2bcea641f6374d"
"https://linear-abcnews-akc-na-east-1.media.dssott.com/int/ps01/disney/05ea2da4-fc45-47a9-a103-f6522f53e116/r/451f8f8e-5f96-42a5-a240-23c90a187612/805b-MAIN/03/128_complete.m3u8"
"https://linear-abcnews-akc-na-east-1.media.dssott.com/int/ps01/disney/3bc70207-6ea8-4943-8821-8057ee401ea5/unenc-all-6e326a28-5364-4fa7-8701-edfdccacd9a8-48470756-82e8-41a7-a088-b587594f67ef.m3u8?r=720&fr=60&a=1&v=1&xp=1&hash=6782a5bc9b684fe4439e541a5d2bcea641f6374d"
"https://linear-abcnews-akc-na-east-1.media.dssott.com/int/ps01/disney/05ea2da4-fc45-47a9-a103-f6522f53e116/r/c4e8ba43-c62d-427a-8e61-6ffa85821788/805b-MAIN/03/1200_complete-62931ef9-a188-47b9-abf2-1cfa8a3d5467.m3u8"
"https://linear-abcnews-akc-na-east-1.media.dssott.com/int/ps01/disney/05ea2da4-fc45-47a9-a103-f6522f53e116/r/c4e8ba43-c62d-427a-8e61-6ffa85821788/805b-MAIN/03/1800_complete-62931ef9-a188-47b9-abf2-1cfa8a3d5467.m3u8"
"https://linear-abcnews-akc-na-east-1.media.dssott.com/int/ps01/disney/40585aad-ff4a-4a54-9aa6-b67ecdb44570/r/92449287-3799-4af3-8474-d806edac576b/aec3-MAIN/03/128_complete.m3u8"
"https://linear-abcnews-akc-na-east-1.media.dssott.com/int/ps01/disney/40585aad-ff4a-4a54-9aa6-b67ecdb44570/r/d8335f39-1804-4ffa-93d0-42d59ebe799a/aec3-MAIN/03/1200_complete-7e794572-dc81-4312-accf-7f5a8e969826.m3u8"
"https://abcnews-livestreams.akamaized.net/out/v1/6a597119dbd5428a82dc11a2f514a1a2/abcn-live-10-cmaf-manifest/abcn-live-10-index.m3u8"
"https://abcnews-livestreams.akamaized.net/out/v1/6a597119dbd5428a82dc11a2f514a1a2/abcn-live-10-cmaf-manifest/abcn-live-10-index_4_0.m3u8"
"https://abcnews-livestreams.akamaized.net/out/v1/6a597119dbd5428a82dc11a2f514a1a2/abcn-live-10-cmaf-manifest/abcn-live-10-index_3.m3u8"
"https://247.foxbusiness.com/hls/live/2003756/FBNHLSv3/master.m3u8?hdnea=exp=1777293769~acl=/*~hmac=b14f6e76c71b050e86737149bc6fc5a1287d6d7a1856149837012cb335918440"
"https://247.foxnews.com/hls/live/2003586/FNCHLSv3/master.m3u8?hdnea=exp=1777293769~acl=/*~hmac=b14f6e76c71b050e86737149bc6fc5a1287d6d7a1856149837012cb335918440"
"https://dai.google.com/linear/hls/pa/event/Sid4xiTQTkCT1SLu6rjUSQ/stream/9a5a43b1-d523-4a93-81ad-b55720591603:CHS/master.m3u8"
)

WORKING_URLS=()

for url in "${URLS[@]}"; do
    echo "Testing: $url"
    http_code=$(curl -s -o /dev/null -w "%{http_code}" -L --max-time 30 --connect-timeout 15 "$url" 2>/dev/null)
    
    if [[ "$http_code" == "200" || "$http_code" == "301" || "$http_code" == "302" ]]; then
        echo "  -> HTTP $http_code - WORKING"
        WORKING_URLS+=("$url")
    else
        echo "  -> HTTP $http_code - FAILED"
    fi
done

echo ""
echo "=== WORKING STREAMS ==="
for url in "${WORKING_URLS[@]}"; do
    echo "$url"
done