#!/usr/bin/env python3
from datetime import datetime, timedelta

today = datetime.now()
tomorrow = today + timedelta(days=1)
day_after = tomorrow + timedelta(days=1)

# Usando os mesmos tvg-ids do epgshare01 para compatibilidade
epg = '''<?xml version="1.0" encoding="UTF-8"?>
<tv date="{date}">
  <channel id="ABC.News.Live.us2">
    <display-name lang="en">ABC News Live</display-name>
    <icon src="https://s.abcnews.com/images/Live/abc_news_live-abc-ml-250210_1739199021469_hpMain_16x9_608.jpg" />
  </channel>
  <programme channel="ABC.News.Live.us2" start="{today}060000 +0000" stop="{today}090000 +0000">
    <title lang="en">Morning News - {today_str}</title>
    <desc lang="en">Cobertura das principais noticias da manha</desc>
  </programme>
  <programme channel="ABC.News.Live.us2" start="{today}090000 +0000" stop="{today}120000 +0000">
    <title lang="en">Midday News - {today_str}</title>
    <desc lang="en">Edicao do meio-dia com as principais noticias</desc>
  </programme>
  <programme channel="ABC.News.Live.us2" start="{today}120000 +0000" stop="{today}180000 +0000">
    <title lang="en">Afternoon Edition - {today_str}</title>
    <desc lang="en">Cobertura das noticias da tarde</desc>
  </programme>
  <programme channel="ABC.News.Live.us2" start="{today}180000 +0000" stop="{today}200000 +0000">
    <title lang="en">Evening News - {today_str}</title>
    <desc lang="en">Edicao vespertina com as principais noticias</desc>
  </programme>
  <programme channel="ABC.News.Live.us2" start="{today}200000 +0000" stop="{tomorrow}060000 +0000">
    <title lang="en">Night Edition - {today_str}</title>
    <desc lang="en">Ultimas noticias do dia</desc>
  </programme>
  <programme channel="ABC.News.Live.us2" start="{tomorrow}060000 +0000" stop="{tomorrow}090000 +0000">
    <title lang="en">Morning News - {tomorrow_str}</title>
    <desc lang="en">Cobertura das principais noticias da manha</desc>
  </programme>
  <programme channel="ABC.News.Live.us2" start="{tomorrow}090000 +0000" stop="{tomorrow}120000 +0000">
    <title lang="en">Midday News - {tomorrow_str}</title>
    <desc lang="en">Edicao do meio-dia com as principais noticias</desc>
  </programme>
  <programme channel="ABC.News.Live.us2" start="{tomorrow}120000 +0000" stop="{tomorrow}180000 +0000">
    <title lang="en">Afternoon Edition - {tomorrow_str}</title>
    <desc lang="en">Cobertura das noticias da tarde</desc>
  </programme>
  <programme channel="ABC.News.Live.us2" start="{tomorrow}180000 +0000" stop="{tomorrow}200000 +0000">
    <title lang="en">Evening News - {tomorrow_str}</title>
    <desc lang="en">Edicao vespertina com as principais noticias</desc>
  </programme>
  <programme channel="ABC.News.Live.us2" start="{tomorrow}200000 +0000" stop="{day_after}060000 +0000">
    <title lang="en">Night Edition - {tomorrow_str}</title>
    <desc lang="en">Ultimas noticias do dia</desc>
  </programme>
  <programme channel="ABC.News.Live.us2" start="{day_after}060000 +0000" stop="{day_after}090000 +0000">
    <title lang="en">Morning News - {day_after_str}</title>
    <desc lang="en">Cobertura das principais noticias da manha</desc>
  </programme>
  <programme channel="ABC.News.Live.us2" start="{day_after}090000 +0000" stop="{day_after}120000 +0000">
    <title lang="en">Midday News - {day_after_str}</title>
    <desc lang="en">Edicao do meio-dia com as principais noticias</desc>
  </programme>
  <programme channel="ABC.News.Live.us2" start="{day_after}120000 +0000" stop="{day_after}180000 +0000">
    <title lang="en">Afternoon Edition - {day_after_str}</title>
    <desc lang="en">Cobertura das noticias da tarde</desc>
  </programme>

  <channel id="Fox.News.Channel.HD.us2">
    <display-name lang="en">Fox News Channel</display-name>
    <icon src="https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/3b09e0ef-610a-43d4-960b-78dc97ae2bd2/dc2e6082-3de1-40e8-a3ab-b6a61b18c3b1/1280x720/match/400/225/image.jpg" />
  </channel>
  <programme channel="Fox.News.Channel.HD.us2" start="{today}060000 +0000" stop="{today}090000 +0000">
    <title lang="en">Fox and Friends First</title>
    <desc lang="en">Fox News</desc>
  </programme>
  <programme channel="Fox.News.Channel.HD.us2" start="{today}090000 +0000" stop="{today}120000 +0000">
    <title lang="en">America's Newsroom</title>
    <desc lang="en">Fox News</desc>
  </programme>
  <programme channel="Fox.News.Channel.HD.us2" start="{today}120000 +0000" stop="{today}150000 +0000">
    <title lang="en">Happening Now</title>
    <desc lang="en">Fox News</desc>
  </programme>
  <programme channel="Fox.News.Channel.HD.us2" start="{today}150000 +0000" stop="{today}170000 +0000">
    <title lang="en">The Story</title>
    <desc lang="en">Fox News</desc>
  </programme>
  <programme channel="Fox.News.Channel.HD.us2" start="{today}170000 +0000" stop="{today}200000 +0000">
    <title lang="en">Fox News at Night</title>
    <desc lang="en">Fox News</desc>
  </programme>
  <programme channel="Fox.News.Channel.HD.us2" start="{today}200000 +0000" stop="{tomorrow}060000 +0000">
    <title lang="en">Tucker Carlson Tonight</title>
    <desc lang="en">Fox News</desc>
  </programme>
  <programme channel="Fox.News.Channel.HD.us2" start="{tomorrow}060000 +0000" stop="{tomorrow}090000 +0000">
    <title lang="en">Fox and Friends First</title>
    <desc lang="en">Fox News</desc>
  </programme>
  <programme channel="Fox.News.Channel.HD.us2" start="{tomorrow}090000 +0000" stop="{tomorrow}120000 +0000">
    <title lang="en">America's Newsroom</title>
    <desc lang="en">Fox News</desc>
  </programme>
  <programme channel="Fox.News.Channel.HD.us2" start="{tomorrow}120000 +0000" stop="{tomorrow}150000 +0000">
    <title lang="en">Happening Now</title>
    <desc lang="en">Fox News</desc>
  </programme>
  <programme channel="Fox.News.Channel.HD.us2" start="{tomorrow}150000 +0000" stop="{tomorrow}170000 +0000">
    <title lang="en">The Story</title>
    <desc lang="en">Fox News</desc>
  </programme>
  <programme channel="Fox.News.Channel.HD.us2" start="{tomorrow}170000 +0000" stop="{tomorrow}200000 +0000">
    <title lang="en">Fox News at Night</title>
    <desc lang="en">Fox News</desc>
  </programme>
  <programme channel="Fox.News.Channel.HD.us2" start="{tomorrow}200000 +0000" stop="{day_after}060000 +0000">
    <title lang="en">Tucker Carlson Tonight</title>
    <desc lang="en">Fox News</desc>
  </programme>
  <programme channel="Fox.News.Channel.HD.us2" start="{day_after}060000 +0000" stop="{day_after}090000 +0000">
    <title lang="en">Fox and Friends First</title>
    <desc lang="en">Fox News</desc>
  </programme>
  <programme channel="Fox.News.Channel.HD.us2" start="{day_after}090000 +0000" stop="{day_after}120000 +0000">
    <title lang="en">America's Newsroom</title>
    <desc lang="en">Fox News</desc>
  </programme>
  <programme channel="Fox.News.Channel.HD.us2" start="{day_after}120000 +0000" stop="{day_after}150000 +0000">
    <title lang="en">Happening Now</title>
    <desc lang="en">Fox News</desc>
  </programme>

  <channel id="Fox.Business.HD.us2">
    <display-name lang="en">Fox Business</display-name>
    <icon src="https://a57.foxnews.com/cf-images.us-east-1.prod.boltdns.net/v1/static/694940094001/3b09e0ef-610a-43d4-960b-78dc97ae2bd2/dc2e6082-3de1-40e8-a3ab-b6a61b18c3b1/1280x720/match/400/225/image.jpg" />
  </channel>
  <programme channel="Fox.Business.HD.us2" start="{today}060000 +0000" stop="{today}090000 +0000">
    <title lang="en">Mornings with Maria</title>
    <desc lang="en">Fox Business</desc>
  </programme>
  <programme channel="Fox.Business.HD.us2" start="{today}090000 +0000" stop="{today}120000 +0000">
    <title lang="en">Squawk Box</title>
    <desc lang="en">Fox Business</desc>
  </programme>
  <programme channel="Fox.Business.HD.us2" start="{today}120000 +0000" stop="{today}150000 +0000">
    <title lang="en">Making Money</title>
    <desc lang="en">Fox Business</desc>
  </programme>
  <programme channel="Fox.Business.HD.us2" start="{today}150000 +0000" stop="{today}180000 +0000">
    <title lang="en">The Claman Countdown</title>
    <desc lang="en">Fox Business</desc>
  </programme>
  <programme channel="Fox.Business.HD.us2" start="{today}180000 +0000" stop="{today}200000 +0000">
    <title lang="en">Evening Edit</title>
    <desc lang="en">Fox Business</desc>
  </programme>
  <programme channel="Fox.Business.HD.us2" start="{today}200000 +0000" stop="{tomorrow}060000 +0000">
    <title lang="en">Nightly Business Report</title>
    <desc lang="en">Fox Business</desc>
  </programme>
  <programme channel="Fox.Business.HD.us2" start="{tomorrow}060000 +0000" stop="{tomorrow}090000 +0000">
    <title lang="en">Mornings with Maria</title>
    <desc lang="en">Fox Business</desc>
  </programme>
  <programme channel="Fox.Business.HD.us2" start="{tomorrow}090000 +0000" stop="{tomorrow}120000 +0000">
    <title lang="en">Squawk Box</title>
    <desc lang="en">Fox Business</desc>
  </programme>
  <programme channel="Fox.Business.HD.us2" start="{tomorrow}120000 +0000" stop="{tomorrow}150000 +0000">
    <title lang="en">Making Money</title>
    <desc lang="en">Fox Business</desc>
  </programme>
  <programme channel="Fox.Business.HD.us2" start="{tomorrow}150000 +0000" stop="{tomorrow}180000 +0000">
    <title lang="en">The Claman Countdown</title>
    <desc lang="en">Fox Business</desc>
  </programme>
  <programme channel="Fox.Business.HD.us2" start="{tomorrow}180000 +0000" stop="{tomorrow}200000 +0000">
    <title lang="en">Evening Edit</title>
    <desc lang="en">Fox Business</desc>
  </programme>
  <programme channel="Fox.Business.HD.us2" start="{tomorrow}200000 +0000" stop="{day_after}060000 +0000">
    <title lang="en">Nightly Business Report</title>
    <desc lang="en">Fox Business</desc>
  </programme>
  <programme channel="Fox.Business.HD.us2" start="{day_after}060000 +0000" stop="{day_after}090000 +0000">
    <title lang="en">Mornings with Maria</title>
    <desc lang="en">Fox Business</desc>
  </programme>
  <programme channel="Fox.Business.HD.us2" start="{day_after}090000 +0000" stop="{day_after}120000 +0000">
    <title lang="en">Squawk Box</title>
    <desc lang="en">Fox Business</desc>
  </programme>
  <programme channel="Fox.Business.HD.us2" start="{day_after}120000 +0000" stop="{day_after}150000 +0000">
    <title lang="en">Making Money</title>
    <desc lang="en">Fox Business</desc>
  </programme>

  <channel id="CBS.News.National.Stream.us2">
    <display-name lang="en">CBS News 24/7</display-name>
    <icon src="https://www.cbsnews.com/bundles/cbsnewsvideo/images/cbsn--main-bg.jpg" />
  </channel>
  <programme channel="CBS.News.National.Stream.us2" start="{today}060000 +0000" stop="{today}090000 +0000">
    <title lang="en">CBS Mornings</title>
    <desc lang="en">CBS News</desc>
  </programme>
  <programme channel="CBS.News.National.Stream.us2" start="{today}090000 +0000" stop="{today}120000 +0000">
    <title lang="en">CBS News Mornings</title>
    <desc lang="en">CBS News</desc>
  </programme>
  <programme channel="CBS.News.National.Stream.us2" start="{today}120000 +0000" stop="{today}130000 +0000">
    <title lang="en">CBS Midday News</title>
    <desc lang="en">CBS News</desc>
  </programme>
  <programme channel="CBS.News.National.Stream.us2" start="{today}130000 +0000" stop="{today}180000 +0000">
    <title lang="en">CBS Afternoon News</title>
    <desc lang="en">CBS News</desc>
  </programme>
  <programme channel="CBS.News.National.Stream.us2" start="{today}180000 +0000" stop="{today}190000 +0000">
    <title lang="en">CBS Evening News</title>
    <desc lang="en">CBS News</desc>
  </programme>
  <programme channel="CBS.News.National.Stream.us2" start="{today}190000 +0000" stop="{today}220000 +0000">
    <title lang="en">CBS Prime News</title>
    <desc lang="en">CBS News</desc>
  </programme>
  <programme channel="CBS.News.National.Stream.us2" start="{today}220000 +0000" stop="{tomorrow}060000 +0000">
    <title lang="en">CBS Night News</title>
    <desc lang="en">CBS News</desc>
  </programme>
  <programme channel="CBS.News.National.Stream.us2" start="{tomorrow}060000 +0000" stop="{tomorrow}090000 +0000">
    <title lang="en">CBS Mornings</title>
    <desc lang="en">CBS News</desc>
  </programme>
  <programme channel="CBS.News.National.Stream.us2" start="{tomorrow}090000 +0000" stop="{tomorrow}120000 +0000">
    <title lang="en">CBS News Mornings</title>
    <desc lang="en">CBS News</desc>
  </programme>
  <programme channel="CBS.News.National.Stream.us2" start="{tomorrow}120000 +0000" stop="{tomorrow}130000 +0000">
    <title lang="en">CBS Midday News</title>
    <desc lang="en">CBS News</desc>
  </programme>
  <programme channel="CBS.News.National.Stream.us2" start="{tomorrow}130000 +0000" stop="{tomorrow}180000 +0000">
    <title lang="en">CBS Afternoon News</title>
    <desc lang="en">CBS News</desc>
  </programme>
  <programme channel="CBS.News.National.Stream.us2" start="{tomorrow}180000 +0000" stop="{tomorrow}190000 +0000">
    <title lang="en">CBS Evening News</title>
    <desc lang="en">CBS News</desc>
  </programme>
  <programme channel="CBS.News.National.Stream.us2" start="{tomorrow}190000 +0000" stop="{tomorrow}220000 +0000">
    <title lang="en">CBS Prime News</title>
    <desc lang="en">CBS News</desc>
  </programme>
  <programme channel="CBS.News.National.Stream.us2" start="{tomorrow}220000 +0000" stop="{day_after}060000 +0000">
    <title lang="en">CBS Night News</title>
    <desc lang="en">CBS News</desc>
  </programme>
  <programme channel="CBS.News.National.Stream.us2" start="{day_after}060000 +0000" stop="{day_after}090000 +0000">
    <title lang="en">CBS Mornings</title>
    <desc lang="en">CBS News</desc>
  </programme>
  <programme channel="CBS.News.National.Stream.us2" start="{day_after}090000 +0000" stop="{day_after}120000 +0000">
    <title lang="en">CBS News Mornings</title>
    <desc lang="en">CBS News</desc>
  </programme>
  <programme channel="CBS.News.National.Stream.us2" start="{day_after}120000 +0000" stop="{day_after}130000 +0000">
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
print(f"Hoje: {today.strftime('%Y-%m-%d')}")
print(f"Amanha: {tomorrow.strftime('%Y-%m-%d')}")
print(f"Depois de amanha: {day_after.strftime('%Y-%m-%d')}")
