#!/usr/bin/env python3
from datetime import datetime, timedelta

today = datetime.now()
tomorrow = today + timedelta(days=1)
day_after = tomorrow + timedelta(days=1)

epg = '''<?xml version="1.0" encoding="UTF-8"?>
<tv date="{date}">
  <channel id="ABC News Live">
    <display-name lang="en">ABC News Live</display-name>
    <icon src="https://s.abcnews.com/images/Live/abc_news_live-abc-ml-250210_1739199021469_hpMain_16x9_608.jpg" />
  </channel>
  <programme channel="ABC News Live" start="{today}T06:00:00 +0000" stop="{today}T09:00:00 +0000">
    <title lang="en">Morning News - {today_str}</title>
    <desc lang="en">Cobertura das principais notícias da manhã</desc>
  </programme>
  <programme channel="ABC News Live" start="{today}T09:00:00 +0000" stop="{today}T12:00:00 +0000">
    <title lang="en">Midday News - {today_str}</title>
    <desc lang="en">Edição do meio-dia com as principais notícias</desc>
  </programme>
  <programme channel="ABC News Live" start="{today}T12:00:00 +0000" stop="{today}T18:00:00 +0000">
    <title lang="en">Afternoon Edition - {today_str}</title>
    <desc lang="en">Cobertura das notícias da tarde</desc>
  </programme>
  <programme channel="ABC News Live" start="{today}T18:00:00 +0000" stop="{today}T20:00:00 +0000">
    <title lang="en">Evening News - {today_str}</title>
    <desc lang="en">Edição vespertina com as principais notícias</desc>
  </programme>
  <programme channel="ABC News Live" start="{today}T20:00:00 +0000" stop="{tomorrow}T06:00:00 +0000">
    <title lang="en">Night Edition - {today_str}</title>
    <desc lang="en">Últimas notícias do dia</desc>
  </programme>
  <programme channel="ABC News Live" start="{tomorrow}T06:00:00 +0000" stop="{tomorrow}T09:00:00 +0000">
    <title lang="en">Morning News - {tomorrow_str}</title>
    <desc lang="en">Cobertura das principais notícias da manhã</desc>
  </programme>
  <programme channel="ABC News Live" start="{tomorrow}T09:00:00 +0000" stop="{tomorrow}T12:00:00 +0000">
    <title lang="en">Midday News - {tomorrow_str}</title>
    <desc lang="en">Edição do meio-dia com as principais notícias</desc>
  </programme>
  <programme channel="ABC News Live" start="{tomorrow}T12:00:00 +0000" stop="{tomorrow}T18:00:00 +0000">
    <title lang="en">Afternoon Edition - {tomorrow_str}</title>
    <desc lang="en">Cobertura das notícias da tarde</desc>
  </programme>
  <programme channel="ABC News Live" start="{tomorrow}T18:00:00 +0000" stop="{tomorrow}T20:00:00 +0000">
    <title lang="en">Evening News - {tomorrow_str}</title>
    <desc lang="en">Edição vespertina com as principais notícias</desc>
  </programme>
  <programme channel="ABC News Live" start="{tomorrow}T20:00:00 +0000" stop="{day_after}T06:00:00 +0000">
    <title lang="en">Night Edition - {tomorrow_str}</title>
    <desc lang="en">Últimas notícias do dia</desc>
  </programme>
  <programme channel="ABC News Live" start="{day_after}T06:00:00 +0000" stop="{day_after}T09:00:00 +0000">
    <title lang="en">Morning News - {day_after_str}</title>
    <desc lang="en">Cobertura das principais notícias da manhã</desc>
  </programme>
  <programme channel="ABC News Live" start="{day_after}T09:00:00 +0000" stop="{day_after}T12:00:00 +0000">
    <title lang="en">Midday News - {day_after_str}</title>
    <desc lang="en">Edição do meio-dia com as principais notícias</desc>
  </programme>
  <programme channel="ABC News Live" start="{day_after}T12:00:00 +0000" stop="{day_after}T18:00:00 +0000">
    <title lang="en">Afternoon Edition - {day_after_str}</title>
    <desc lang="en">Cobertura das notícias da tarde</desc>
  </programme>

  <channel id="Fox News Channel">
    <display-name lang="en">Fox News Channel</display-name>
    <icon src="https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/3b09e0ef-610a-43d4-960b-78dc97ae2bd2/dc2e6082-3de1-40e8-a3ab-b6a61b18c3b1/1280x720/match/400/225/image.jpg" />
  </channel>
  <programme channel="Fox News Channel" start="{today}T06:00:00 +0000" stop="{today}T09:00:00 +0000">
    <title lang="en">Fox &amp; Friends First</title>
    <desc lang="en">Fox News</desc>
  </programme>
  <programme channel="Fox News Channel" start="{today}T09:00:00 +0000" stop="{today}T12:00:00 +0000">
    <title lang="en">America's Newsroom</title>
    <desc lang="en">Fox News</desc>
  </programme>
  <programme channel="Fox News Channel" start="{today}T12:00:00 +0000" stop="{today}T15:00:00 +0000">
    <title lang="en">Happening Now</title>
    <desc lang="en">Fox News</desc>
  </programme>
  <programme channel="Fox News Channel" start="{today}T15:00:00 +0000" stop="{today}T17:00:00 +0000">
    <title lang="en">The Story</title>
    <desc lang="en">Fox News</desc>
  </programme>
  <programme channel="Fox News Channel" start="{today}T17:00:00 +0000" stop="{today}T20:00:00 +0000">
    <title lang="en">Fox News @ Night</title>
    <desc lang="en">Fox News</desc>
  </programme>
  <programme channel="Fox News Channel" start="{today}T20:00:00 +0000" stop="{tomorrow}T06:00:00 +0000">
    <title lang="en">Tucker Carlson Tonight</title>
    <desc lang="en">Fox News</desc>
  </programme>
  <programme channel="Fox News Channel" start="{tomorrow}T06:00:00 +0000" stop="{tomorrow}T09:00:00 +0000">
    <title lang="en">Fox &amp; Friends First</title>
    <desc lang="en">Fox News</desc>
  </programme>
  <programme channel="Fox News Channel" start="{tomorrow}T09:00:00 +0000" stop="{tomorrow}T12:00:00 +0000">
    <title lang="en">America's Newsroom</title>
    <desc lang="en">Fox News</desc>
  </programme>
  <programme channel="Fox News Channel" start="{tomorrow}T12:00:00 +0000" stop="{tomorrow}T15:00:00 +0000">
    <title lang="en">Happening Now</title>
    <desc lang="en">Fox News</desc>
  </programme>
  <programme channel="Fox News Channel" start="{tomorrow}T15:00:00 +0000" stop="{tomorrow}T17:00:00 +0000">
    <title lang="en">The Story</title>
    <desc lang="en">Fox News</desc>
  </programme>
  <programme channel="Fox News Channel" start="{tomorrow}T17:00:00 +0000" stop="{tomorrow}T20:00:00 +0000">
    <title lang="en">Fox News @ Night</title>
    <desc lang="en">Fox News</desc>
  </programme>
  <programme channel="Fox News Channel" start="{tomorrow}T20:00:00 +0000" stop="{day_after}T06:00:00 +0000">
    <title lang="en">Tucker Carlson Tonight</title>
    <desc lang="en">Fox News</desc>
  </programme>
  <programme channel="Fox News Channel" start="{day_after}T06:00:00 +0000" stop="{day_after}T09:00:00 +0000">
    <title lang="en">Fox &amp; Friends First</title>
    <desc lang="en">Fox News</desc>
  </programme>
  <programme channel="Fox News Channel" start="{day_after}T09:00:00 +0000" stop="{day_after}T12:00:00 +0000">
    <title lang="en">America's Newsroom</title>
    <desc lang="en">Fox News</desc>
  </programme>
  <programme channel="Fox News Channel" start="{day_after}T12:00:00 +0000" stop="{day_after}T15:00:00 +0000">
    <title lang="en">Happening Now</title>
    <desc lang="en">Fox News</desc>
  </programme>

  <channel id="Fox Business">
    <display-name lang="en">Fox Business</display-name>
    <icon src="https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/3b09e0ef-610a-43d4-960b-78dc97ae2bd2/dc2e6082-3de1-40e8-a3ab-b6a61b18c3b1/1280x720/match/400/225/image.jpg" />
  </channel>
  <programme channel="Fox Business" start="{today}T06:00:00 +0000" stop="{today}T09:00:00 +0000">
    <title lang="en">Mornings with Maria</title>
    <desc lang="en">Fox Business</desc>
  </programme>
  <programme channel="Fox Business" start="{today}T09:00:00 +0000" stop="{today}T12:00:00 +0000">
    <title lang="en">Squawk Box</title>
    <desc lang="en">Fox Business</desc>
  </programme>
  <programme channel="Fox Business" start="{today}T12:00:00 +0000" stop="{today}T15:00:00 +0000">
    <title lang="en">Making Money</title>
    <desc lang="en">Fox Business</desc>
  </programme>
  <programme channel="Fox Business" start="{today}T15:00:00 +0000" stop="{today}T18:00:00 +0000">
    <title lang="en">The Claman Countdown</title>
    <desc lang="en">Fox Business</desc>
  </programme>
  <programme channel="Fox Business" start="{today}T18:00:00 +0000" stop="{today}T20:00:00 +0000">
    <title lang="en">Evening Edit</title>
    <desc lang="en">Fox Business</desc>
  </programme>
  <programme channel="Fox Business" start="{today}T20:00:00 +0000" stop="{tomorrow}T06:00:00 +0000">
    <title lang="en">Nightly Business Report</title>
    <desc lang="en">Fox Business</desc>
  </programme>
  <programme channel="Fox Business" start="{tomorrow}T06:00:00 +0000" stop="{tomorrow}T09:00:00 +0000">
    <title lang="en">Mornings with Maria</title>
    <desc lang="en">Fox Business</desc>
  </programme>
  <programme channel="Fox Business" start="{tomorrow}T09:00:00 +0000" stop="{tomorrow}T12:00:00 +0000">
    <title lang="en">Squawk Box</title>
    <desc lang="en">Fox Business</desc>
  </programme>
  <programme channel="Fox Business" start="{tomorrow}T12:00:00 +0000" stop="{tomorrow}T15:00:00 +0000">
    <title lang="en">Making Money</title>
    <desc lang="en">Fox Business</desc>
  </programme>
  <programme channel="Fox Business" start="{tomorrow}T15:00:00 +0000" stop="{tomorrow}T18:00:00 +0000">
    <title lang="en">The Claman Countdown</title>
    <desc lang="en">Fox Business</desc>
  </programme>
  <programme channel="Fox Business" start="{tomorrow}T18:00:00 +0000" stop="{tomorrow}T20:00:00 +0000">
    <title lang="en">Evening Edit</title>
    <desc lang="en">Fox Business</desc>
  </programme>
  <programme channel="Fox Business" start="{tomorrow}T20:00:00 +0000" stop="{day_after}T06:00:00 +0000">
    <title lang="en">Nightly Business Report</title>
    <desc lang="en">Fox Business</desc>
  </programme>
  <programme channel="Fox Business" start="{day_after}T06:00:00 +0000" stop="{day_after}T09:00:00 +0000">
    <title lang="en">Mornings with Maria</title>
    <desc lang="en">Fox Business</desc>
  </programme>
  <programme channel="Fox Business" start="{day_after}T09:00:00 +0000" stop="{day_after}T12:00:00 +0000">
    <title lang="en">Squawk Box</title>
    <desc lang="en">Fox Business</desc>
  </programme>
  <programme channel="Fox Business" start="{day_after}T12:00:00 +0000" stop="{day_after}T15:00:00 +0000">
    <title lang="en">Making Money</title>
    <desc lang="en">Fox Business</desc>
  </programme>

  <channel id="CBS News">
    <display-name lang="en">CBS News 24/7</display-name>
    <icon src="https://www.cbsnews.com/bundles/cbsnewsvideo/images/cbsn--main-bg.jpg" />
  </channel>
  <programme channel="CBS News" start="{today}T06:00:00 +0000" stop="{today}T09:00:00 +0000">
    <title lang="en">CBS Mornings</title>
    <desc lang="en">CBS News</desc>
  </programme>
  <programme channel="CBS News" start="{today}T09:00:00 +0000" stop="{today}T12:00:00 +0000">
    <title lang="en">CBS News Mornings</title>
    <desc lang="en">CBS News</desc>
  </programme>
  <programme channel="CBS News" start="{today}T12:00:00 +0000" stop="{today}T13:00:00 +0000">
    <title lang="en">CBS Midday News</title>
    <desc lang="en">CBS News</desc>
  </programme>
  <programme channel="CBS News" start="{today}T13:00:00 +0000" stop="{today}T18:00:00 +0000">
    <title lang="en">CBS Afternoon News</title>
    <desc lang="en">CBS News</desc>
  </programme>
  <programme channel="CBS News" start="{today}T18:00:00 +0000" stop="{today}T19:00:00 +0000">
    <title lang="en">CBS Evening News</title>
    <desc lang="en">CBS News</desc>
  </programme>
  <programme channel="CBS News" start="{today}T19:00:00 +0000" stop="{today}T22:00:00 +0000">
    <title lang="en">CBS Prime News</title>
    <desc lang="en">CBS News</desc>
  </programme>
  <programme channel="CBS News" start="{today}T22:00:00 +0000" stop="{tomorrow}T06:00:00 +0000">
    <title lang="en">CBS Night News</title>
    <desc lang="en">CBS News</desc>
  </programme>
  <programme channel="CBS News" start="{tomorrow}T06:00:00 +0000" stop="{tomorrow}T09:00:00 +0000">
    <title lang="en">CBS Mornings</title>
    <desc lang="en">CBS News</desc>
  </programme>
  <programme channel="CBS News" start="{tomorrow}T09:00:00 +0000" stop="{tomorrow}T12:00:00 +0000">
    <title lang="en">CBS News Mornings</title>
    <desc lang="en">CBS News</desc>
  </programme>
  <programme channel="CBS News" start="{tomorrow}T12:00:00 +0000" stop="{tomorrow}T13:00:00 +0000">
    <title lang="en">CBS Midday News</title>
    <desc lang="en">CBS News</desc>
  </programme>
  <programme channel="CBS News" start="{tomorrow}T13:00:00 +0000" stop="{tomorrow}T18:00:00 +0000">
    <title lang="en">CBS Afternoon News</title>
    <desc lang="en">CBS News</desc>
  </programme>
  <programme channel="CBS News" start="{tomorrow}T18:00:00 +0000" stop="{tomorrow}T19:00:00 +0000">
    <title lang="en">CBS Evening News</title>
    <desc lang="en">CBS News</desc>
  </programme>
  <programme channel="CBS News" start="{tomorrow}T19:00:00 +0000" stop="{tomorrow}T22:00:00 +0000">
    <title lang="en">CBS Prime News</title>
    <desc lang="en">CBS News</desc>
  </programme>
  <programme channel="CBS News" start="{tomorrow}T22:00:00 +0000" stop="{day_after}T06:00:00 +0000">
    <title lang="en">CBS Night News</title>
    <desc lang="en">CBS News</desc>
  </programme>
  <programme channel="CBS News" start="{day_after}T06:00:00 +0000" stop="{day_after}T09:00:00 +0000">
    <title lang="en">CBS Mornings</title>
    <desc lang="en">CBS News</desc>
  </programme>
  <programme channel="CBS News" start="{day_after}T09:00:00 +0000" stop="{day_after}T12:00:00 +0000">
    <title lang="en">CBS News Mornings</title>
    <desc lang="en">CBS News</desc>
  </programme>
  <programme channel="CBS News" start="{day_after}T12:00:00 +0000" stop="{day_after}T13:00:00 +0000">
    <title lang="en">CBS Midday News</title>
    <desc lang="en">CBS News</desc>
  </programme>

</tv>
'''.format(
    date=today.strftime('%Y%m%d%H%M%S'),
    today=today.strftime('%Y%m%d'),
    today_str=today.strftime('%Y-%m-%d'),
    tomorrow=tomorrow.strftime('%Y%m%d'),
    tomorrow_str=tomorrow.strftime('%Y-%m-%d'),
    day_after=day_after.strftime('%Y%m%d'),
    day_after_str=day_after.strftime('%Y-%m-%d')
)

with open('lista5_epg.xml', 'w', encoding='utf-8') as f:
    f.write(epg)

print(f"EPG gerado: lista5_epg.xml")
print(f"Data: {today.strftime('%Y-%m-%d')}")
print(f"Amanhã: {tomorrow.strftime('%Y-%m-%d')}")
print(f"Depois de amanhã: {day_after.strftime('%Y-%m-%d')}")