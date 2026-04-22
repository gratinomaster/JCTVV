import re
import asyncio
import logging
import sys

logging.basicConfig(level=logging.CRITICAL, format="", handlers=[logging.StreamHandler(sys.stdout)])
for logger_name in ["crawl4ai", "playwright", "asyncio"]:
    logging.getLogger(logger_name).setLevel(logging.CRITICAL)

from crawl4ai import AsyncWebCrawler
from crawl4ai.async_configs import BrowserConfig, CrawlerRunConfig

VIDEO_URLS = [
    "https://www.foxnews.com/video/5614615980001",
    "https://www.foxnews.com/video/5614626175001",
]

async def find_m3u8_stream(url: str) -> str | None:
    browser_config = BrowserConfig(
        headless=True,
        verbose=False,
        extra_args=["--disable-gpu", "--no-sandbox"],
    )
    run_config = CrawlerRunConfig(
        delay_before_return_html=10,
        capture_network_requests=True,
    )
    
    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(url=url, config=run_config)
        
        if result and result.network_requests:
            for req in result.network_requests:
                req_url = req.get("url", "")
                req_url_lower = req_url.lower()
                if "playlist.m3u8" in req_url_lower or req_url_lower.endswith(".m3u8"):
                    if "token=" in req_url:
                        return req_url
                
        if result and result.html:
            matches = re.findall(r'https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*token=[^\s"\'<>]*', result.html)
            if matches:
                return matches[0]
                
    return None

async def main():
    for url in VIDEO_URLS:
        print(f"Buscando stream em: {url}")
        m3u8_url = await find_m3u8_stream(url)
        if m3u8_url:
            print(f"  -> Encontrado: {m3u8_url}")
        else:
            print(f"  -> Stream não encontrado")

if __name__ == "__main__":
    asyncio.run(main())