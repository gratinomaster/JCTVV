import re
import asyncio
import logging
import sys

logging.basicConfig(level=logging.CRITICAL, format="", handlers=[logging.StreamHandler(sys.stdout)])
for logger_name in ["crawl4ai", "playwright", "asyncio"]:
    logging.getLogger(logger_name).setLevel(logging.CRITICAL)

from crawl4ai import AsyncWebCrawler
from crawl4ai.async_configs import BrowserConfig, CrawlerRunConfig

SITES = [
    "https://cbn.globo.com/ao-vivo/video/cbn-sp/",
    "https://g1.globo.com/sp/ribeirao-preto-franca/ao-vivo/eptv1.ghtml",
    "https://g1.globo.com/sp/campinas-regiao/ao-vivo/veja-o-eptv-2-campinas-ao-vivo.ghtml",
    "https://g1.globo.com/sp/piracicaba-regiao/ao-vivo/eptv-2-piracicaba-ao-vivo.ghtml",
    "https://g1.globo.com/sp/ribeirao-preto-franca/ao-vivo/eptv-2-ribeirao-e-franca-ao-vivo.ghtml",
]


def extract_title(html: str) -> str:
    """Extrai título da página"""
    og_title = re.search(r'<meta property="og:title" content="([^"]+)"', html)
    if og_title:
        return og_title.group(1).strip()

    title = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE)
    if title:
        return title.group(1).strip()

    return "Canal ao vivo"


def extract_thumbnail(html: str) -> str:
    """Extrai thumbnail da página"""
    og_img = re.search(r'<meta property="og:image" content="([^"]+)"', html)
    if og_img:
        return og_img.group(1)

    twitter_img = re.search(r'<meta name="twitter:image" content="([^"]+)"', html)
    if twitter_img:
        return twitter_img.group(1)

    return ""


async def find_stream_and_metadata(url: str):
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

        m3u8_url = None
        title = "Live Stream"
        thumbnail = ""

        if result and result.html:
            html = result.html

            title = extract_title(html)
            thumbnail = extract_thumbnail(html)

            matches = re.findall(r'https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*', html)
            if matches:
                m3u8_url = matches[0]

        if not m3u8_url and result and result.network_requests:
            for req in result.network_requests:
                req_url = req.get("url", "")
                req_url_lower = req_url.lower()

                if "playlist.m3u8" in req_url_lower or req_url_lower.endswith(".m3u8"):
                    m3u8_url = req_url
                    break

        return m3u8_url, title, thumbnail


async def main():
    playlist = ["#EXTM3U"]

    for url in SITES:
        print(f"Buscando stream em: {url}")

        m3u8_url, title, thumb = await find_stream_and_metadata(url)

        if m3u8_url:
            print(f"  -> Encontrado: {m3u8_url[:80]}...")
            print(f"  -> Título: {title}")

            playlist.append(f'#EXTINF:-1 tvg-logo="{thumb}" group-title="NEWS WORLD",{title}')
            playlist.append(m3u8_url)

        else:
            print("  -> Stream não encontrado")

    with open("lista3.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(playlist))

    print("\nArquivo lista3.m3u gerado com sucesso!")


if __name__ == "__main__":
    asyncio.run(main())
