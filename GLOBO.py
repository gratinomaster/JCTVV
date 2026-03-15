import requests
import re
import json

OUTPUT = "globo_playlist.m3u"

headers = {
    "User-Agent": "Mozilla/5.0"
}

urls = [
    "https://globoplay.globo.com/v/4613774/",
    "https://globoplay.globo.com/ao-vivo/7689934/",
    "https://globoplay.globo.com/ao-vivo/7690141/",
    "https://g1.globo.com/sp/campinas-regiao/ao-vivo/eptv-1-campinas-ao-vivo.ghtml"
]


def extract_video_id(html):

    patterns = [
        r'"videoId":"(\d+)"',
        r'data-video-id="(\d+)"',
        r'"id":"(\d+)"'
    ]

    for p in patterns:
        match = re.search(p, html)
        if match:
            return match.group(1)

    return None


def get_stream(video_id):

    api = f"https://playback.video.globo.com/v2/video-session"

    payload = {
        "player_type": "desktop",
        "video_id": video_id,
        "quality": "max"
    }

    r = requests.post(api, json=payload, headers=headers)

    data = r.json()

    try:
        m3u8 = data["sources"][0]["url"]
        thumb = data["sources"][0]["thumbUri"]
        return m3u8, thumb
    except:
        return None, None


def process_url(url):

    print("Processando:", url)

    html = requests.get(url, headers=headers).text

    video_id = extract_video_id(html)

    if not video_id:
        print("Video ID não encontrado")
        return None

    m3u8, thumb = get_stream(video_id)

    if not m3u8:
        print("Stream não encontrado")
        return None

    title_match = re.search("<title>(.*?)</title>", html)

    title = title_match.group(1) if title_match else "Globo"

    return {
        "title": title,
        "stream": m3u8,
        "thumb": thumb
    }


def generate_playlist(data):

    with open(OUTPUT, "w", encoding="utf-8") as f:

        f.write("#EXTM3U\n")

        for item in data:

            f.write(
                f'#EXTINF:-1 tvg-logo="{item["thumb"]}" group-title="Globo",{item["title"]}\n'
            )

            f.write(item["stream"] + "\n")


results = []

for u in urls:

    data = process_url(u)

    if data:
        results.append(data)

generate_playlist(results)

print("Playlist criada:", OUTPUT)
