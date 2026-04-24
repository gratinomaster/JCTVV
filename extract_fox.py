import re
import asyncio
import logging
import sys
import json

logging.basicConfig(level=logging.CRITICAL, format="", handlers=[logging.StreamHandler(sys.stdout)])
for logger_name in ["crawl4ai", "playwright", "asyncio"]:
    logging.getLogger(logger_name).setLevel(logging.CRITICAL)

from crawl4ai import AsyncWebCrawler
from crawl4ai.async_configs import BrowserConfig, CrawlerRunConfig

VIDEO_URLS = [
    ("FoxNews", "https://www.foxnews.com/video/5614615980001", "foxnews"),
    ("FoxBusiness", "https://www.foxnews.com/video/5614626175001", "foxbusiness"),
]

async def find_m3u8_stream(url: str, domain: str) -> str | None:
    browser_config = BrowserConfig(
        headless=True,
        verbose=False,
        extra_args=["--disable-gpu", "--no-sandbox"],
    )
    run_config = CrawlerRunConfig(
        delay_before_return_html=8,
        capture_network_requests=True,
    )
    
    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(url=url, config=run_config)
        
        if result and result.network_requests:
            for req in result.network_requests:
                req_url = req.get("url", "")
                req_url_lower = req_url.lower()
                if domain in req_url_lower and ".m3u8" in req_url_lower and "master.m3u8" in req_url_lower:
                    if "chartbeat" not in req_url_lower and "ping" not in req_url_lower:
                        return req_url
                        
        if result and result.html:
            matches = re.findall(r'https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*', result.html)
            for m in matches:
                m_lower = m.lower()
                if domain in m_lower and "master.m3u8" in m_lower:
                    if "chartbeat" not in m_lower and "ping" not in m_lower:
                        return m
                
    return None

async def main():
    streams = {}
    for name, url, domain in VIDEO_URLS:
        print(f"Buscando stream em: {url}")
        m3u8_url = await find_m3u8_stream(url, domain)
        if m3u8_url:
            streams[name] = m3u8_url
            print(f"  -> Encontrado: {m3u8_url}")
        else:
            print(f"  -> Stream não encontrado")
    
    return streams

if __name__ == "__main__":
    streams = asyncio.run(main())
    print("\n=== RESULTADO ===")
    for name, url in streams.items():
        print(f"{name}: {url}")
    
    if "FoxNews" in streams:
        print("\n=== FX.m3u8 ===")
        print("#EXTM3U")
        print("#EXT-X-VERSION:3")
        print("#EXT-X-STREAM-INF:BANDWIDTH=3000000")
        print(streams["FoxNews"])
    
    if "FoxBusiness" in streams:
        print("\n=== FXB.m3u8 ===")
        print("#EXTM3U")
        print("#EXT-X-VERSION:3")
        print("#EXT-X-STREAM-INF:BANDWIDTH=3000000")
        print(streams["FoxBusiness"])