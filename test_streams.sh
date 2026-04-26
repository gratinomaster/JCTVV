#!/bin/bash

# Extract unique stream URLs from M3U file and test them
# Only test URLs (not the quality variants - those are sub-streams)

# URLs to test (first URL from each unique channel group)
URLS=(
"https://linear-abcnews-akc-na-east-1.media.dssott.com/dvt2=exp=1777314446~url=%2Fclt1%2Fva02%2Fdisneyplus%2Fchannel%2F79449312-79dd-473d-873c-515ebf4b5e5f-1776583682323%2F~psid=21a9e93f-a6be-4c28-a932-f7ec69d316bb~did=ca4cf4f3-cad0-4a67-9c04-d18f0128be43~country=US~kid=k02~hmac=39d3512a0f93ce0b388489b0985be50d6fbd727ee062c075054a786002eb72b5/clt1/va02/disneyplus/channel/79449312-79dd-473d-873c-515ebf4b5e5f-1776583682323/ctr-all-hdri-sliding.m3u8?r=1080&v=1&hash=0ce6d6ffe5eed1546b2d7ba51fca94a7850f62ea"
"https://abcnews-livestreams.akamaized.net/out/v1/6a597119dbd5428a82dc11a2f514a1a2/abcn-live-10-cmaf-manifest/abcn-live-10-index.m3u8"
"https://247.foxbusiness.com/hls/live/2003756/FBNHLSv3/master.m3u8?hdnea=exp=1777231645~acl=/*~hmac=fc50a7c76018519a8c957fbe1c290bf91cfee0a76111711fc5cad3b240f5428f"
"https://247.foxnews.com/hls/live/2003586/FNCHLSv3/master.m3u8?hdnea=exp=1777231646~acl=/*~hmac=75b197dc2ff36f7df5642ef003842a57d71a05fae14e23ebd7b0cd61a8c3a407"
"https://dai.google.com/linear/hls/pa/event/Sid4xiTQTkCT1SLu6rjUSQ/stream/43bff66e-f58a-4057-8095-ac672e40d839:CHS/master.m3u8"
)

NAMES=(
"ABC News Live"
"ABCN Live Video"
"Fox Business Go"
"Fox News Channel"
"CBS News 24/7"
)

echo "Testing streams..."
echo "========================================"

for i in "${!URLS[@]}"; do
    URL="${URLS[$i]}"
    NAME="${NAMES[$i]}"
    
    echo -n "Testing $NAME... "
    
    # Check HTTP response code
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 30 "$URL")
    
    if [ "$HTTP_CODE" = "200" ]; then
        echo "OK (HTTP $HTTP_CODE)"
    else
        echo "FAILED (HTTP $HTTP_CODE)"
    fi
done

echo "========================================"