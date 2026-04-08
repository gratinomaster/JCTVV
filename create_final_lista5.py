#!/usr/bin/env python3
from datetime import datetime, timedelta

JPG_LOGOS = {
    "ABC News": "https://i.imgur.com/abc_news_logo.jpg",
    "Fox News": "https://i.imgur.com/fox_news_logo.jpg", 
    "Fox Business": "https://i.imgur.com/fox_business_logo.jpg",
    "CBS News": "https://i.imgur.com/cbs_news_logo.jpg",
}

CLEAN_LOGOS = {
    "ABC News": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4d/ABC_News_App_Icon.png/200px-ABC_News_App_Icon.png",
    "Fox News": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4d/Fox_News_Channel_Logo_2017.png/200px-Fox_News_Channel_Logo_2017.png",
    "Fox Business": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b9/Fox_Business_Logo.svg/200px-Fox_Business_Logo.svg.png",
    "CBS News": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/00/CBS_Logo_-_2023.svg/200px-CBS_Logo_-_2023.svg.png",
}

FINAL_CHANNELS = [
    {
        "name": "ABC News Live",
        "url": "https://linear-abcnews-ftc-na-central-1.media.dssott.com/dvt2=exp=1775688663~url=%2Flas1%2Fva01%2Fdisneyplus%2Fchannel%2F79449312-79dd-473d-873c-515ebf4b5e5f-1773291359692%2F~psid=e2591d3c-fe22-487d-a5c2-7a4045e40ce6~did=030f8ca2-d610-4a22-a0f3-2a85f60c498f~country=US~kid=k02~hmac=72a7cf7a657ece3acbd72e025015138c80d3bff9516ac1b8bdb259365b7c3faa/las1/va01/disneyplus/channel/79449312-79dd-473d-873c-515ebf4b5e5f-1773291359692/ctr-all-hdri-sliding.m3u8?r=1080&v=1&hash=fe52cce12f9cafe1e088577253e8191f7e3bf7f4",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/14/American_Broadcasting_Company_Logo.svg/200px-American_Broadcasting_Company_Logo.svg.png",
        "type": "ABCNewsLive",
        "epg_channel": "ABCNewsLive.us"
    },
    {
        "name": "ABC News Network",
        "url": "https://abcnews-livestreams.akamaized.net/out/v1/6a597119dbd5428a82dc11a2f514a1a2/abcn-live-10-cmaf-manifest/abcn-live-10-index.m3u8",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/14/American_Broadcasting_Company_Logo.svg/200px-American_Broadcasting_Company_Logo.svg.png",
        "type": "ABCNewsLive",
        "epg_channel": "ABCNewsLive.us"
    },
    {
        "name": "Fox News",
        "url": "https://247.foxnews.com/hls/live/2003586/FNCHLSv3/master.m3u8?hdnea=exp=1775605864~acl=/*~hmac=635b013ca9d8bdfa8986c73c798b61f1e64911dfc5bfb1f1abfc50981bc7a5b2",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0c/Fox_News_Channel_Logo.svg/200px-Fox_News_Channel_Logo.svg.png",
        "type": "FoxNews",
        "epg_channel": "FoxNewsChannel.us"
    },
    {
        "name": "Fox Business",
        "url": "https://247.foxbusiness.com/hls/live/2003756/FBNHLSv3/master.m3u8?hdnea=exp=1775605864~acl=/*~hmac=635b013ca9d8bdfa8986c73c798b61f1e64911dfc5bfb1f1abfc50981bc7a5b2",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b9/Fox_Business_Logo.svg/200px-Fox_Business_Logo.svg.png",
        "type": "FoxBusiness",
        "epg_channel": "FoxBusinessNetwork.us"
    },
    {
        "name": "CBS News 24/7",
        "url": "https://dai.google.com/linear/hls/pa/event/Sid4xiTQTkCT1SLu6rjUSQ/stream/493ece8c-a04d-463f-890d-d55c944ab4c1:TUL/master.m3u8",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/00/CBS_Logo_-_2023.svg/200px-CBS_Logo_-_2023.svg.png",
        "type": "CBSNews",
        "epg_channel": "CBSNewsNetwork.us"
    },
]

def generate_epg():
    today = datetime.now()
    dates = [today, today + timedelta(days=1), today + timedelta(days=2)]
    
    programs = {
        "ABCNewsLive": [
            ("0600", "0900", "ABC World News This Morning"),
            ("0900", "1100", "Good Morning America"),
            ("1100", "1230", "ABC World News Midday"),
            ("1230", "1400", "ABC Live Now"),
            ("1400", "1600", "The View"),
            ("1600", "1730", "ABC World News This Afternoon"),
            ("1730", "1830", "ABC World News Tonight"),
            ("1830", "1900", "ABC World News Prime"),
            ("1900", "2000", "ABC Evening News"),
            ("2000", "2200", "ABC Live Prime Time"),
            ("2200", "2300", "Nightline"),
            ("2300", "0600", "ABC World News Now"),
        ],
        "FoxNews": [
            ("0600", "0900", "Fox & Friends First"),
            ("0900", "1100", "Fox & Friends"),
            ("1100", "1200", "America's Newsroom"),
            ("1200", "1300", "Fox News @ Noon"),
            ("1300", "1500", "The Story"),
            ("1500", "1700", "The Five"),
            ("1700", "1800", "Fox News Tonight"),
            ("1800", "1900", "Fox News Sunday"),
            ("1900", "2000", "Tucker Carlson Tonight"),
            ("2000", "2100", "Hannity"),
            ("2100", "2200", "The Ingraham Angle"),
            ("2200", "2300", "Fox News @ Night"),
            ("2300", "0600", "Fox News Overnight"),
        ],
        "FoxBusiness": [
            ("0600", "0900", "Fox Business Morning"),
            ("0900", "1100", "Varney & Co."),
            ("1100", "1200", "The Big Money Show"),
            ("1200", "1300", "Fox Business Midday"),
            ("1300", "1400", "The Claman Countdown"),
            ("1400", "1500", "Making Money"),
            ("1500", "1700", "The Five"),
            ("1700", "1800", "Cavuto: Coast to Coast"),
            ("1800", "1900", "Fox Business Tonight"),
            ("1900", "2000", "Kudlow"),
            ("2000", "2100", "The Big Money Show"),
            ("2100", "2200", "Fox Business @ Night"),
            ("2200", "0600", "Fox Business Overnight"),
        ],
        "CBSNews": [
            ("0600", "0700", "CBS Morning News"),
            ("0700", "0900", "CBS This Morning"),
            ("0900", "1000", "CBS News Daily"),
            ("1000", "1200", "CBS This Morning"),
            ("1200", "1230", "CBS News Midday"),
            ("1230", "1330", "CBS News Update"),
            ("1330", "1400", "The Price Is Right"),
            ("1400", "1430", "CBS News Update"),
            ("1430", "1530", "The Young and the Restless"),
            ("1530", "1630", "CBS News Afternoon"),
            ("1630", "1730", "CBS Evening News"),
            ("1730", "1830", "CBS News Evening"),
            ("1830", "1900", "CBS World News Tonight"),
            ("1900", "2000", "60 Minutes"),
            ("2000", "2100", "CBS News Special"),
            ("2100", "2200", "CBS News Special"),
            ("2200", "2300", "CBS News Nightwatch"),
            ("2300", "0600", "CBS News Overnight"),
        ],
    }
    
    channel_ids = {
        "ABCNewsLive": "ABCNewsLive.us",
        "FoxNews": "FoxNewsChannel.us",
        "FoxBusiness": "FoxBusinessNetwork.us",
        "CBSNews": "CBSNewsNetwork.us",
    }
    
    xml = ['<?xml version="1.0" encoding="UTF-8"?>\n<tv>']
    
    for ch_type, prog_list in programs.items():
        ch_id = channel_ids[ch_type]
        
        for date in dates:
            date_str = date.strftime("%Y%m%d")
            for start, stop, title in prog_list:
                xml.append(f'  <programme channel="{ch_id}" start="{date_str}{start}00 +0000" stop="{date_str}{stop}00 +0000">')
                xml.append(f'    <title lang="en">{title}</title>')
                xml.append(f'    <desc lang="en">Live news coverage</desc>')
                xml.append(f'  </programme>')
    
    xml.append('</tv>')
    return '\n'.join(xml)

def main():
    print("Creating final lista5.m3u...")
    
    output = ["#EXTM3U"]
    
    for ch in FINAL_CHANNELS:
        output.append(f"#EXTINF:-1 tvg-logo=\"{ch['logo']}\" group-title=\"NEWS WORLD\",{ch['name']}")
        output.append(ch['url'])
    
    with open('lista5.m3u', 'w', encoding='utf-8') as f:
        f.write('\n'.join(output))
    
    print(f"Saved lista5.m3u with {len(FINAL_CHANNELS)} channels")
    
    epg = generate_epg()
    with open('lista5_epg_news.xml', 'w', encoding='utf-8') as f:
        f.write(epg)
    
    print(f"Saved lista5_epg_news.xml")
    
    today = datetime.now().strftime("%Y%m%d")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
    dayafter = (datetime.now() + timedelta(days=2)).strftime("%Y%m%d")
    
    print(f"\nEPG validation:")
    print(f"  Today ({today}): {epg.count(today)} programme entries")
    print(f"  Tomorrow ({tomorrow}): {epg.count(tomorrow)} programme entries")
    print(f"  Day After ({dayafter}): {epg.count(dayafter)} programme entries")
    
    print("\nChannel summary:")
    for ch in FINAL_CHANNELS:
        print(f"  - {ch['name']}: {ch['epg_channel']}")

if __name__ == "__main__":
    main()
