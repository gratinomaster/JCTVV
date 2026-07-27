#!/usr/bin/env python3
import urllib.request
import ssl

def test_url(url, timeout=10):
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        response = urllib.request.urlopen(req, timeout=timeout, context=ctx)
        return True, response.getcode()
    except Exception as e:
        return False, str(e)

# Test CNN International stream
cnn_url = "https://turnerlive.warnermediacdn.com/hls/live/586497/cnngo/cnni/VIDEO_0_3564000.m3u8"
print(f"Testando CNN International: {cnn_url}")
is_online, status = test_url(cnn_url, timeout=15)
print(f"  Resultado: {'✓ ONLINE' if is_online else '✗ OFFLINE'} ({status})")

# Test CNN logo
cnn_logo = "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/united-states/cnn-us.png"
print(f"\nTestando logo CNN: {cnn_logo}")
is_online, status = test_url(cnn_logo, timeout=10)
print(f"  Resultado: {'✓ ONLINE' if is_online else '✗ OFFLINE'} ({status})")

# Test all NEWS WORLD logos
logos = [
    ("ABC News Live", "https://keyframe-cdn.abcnews.com/streamprovider10.jpg"),
    ("DW English", "https://www.dw.com/image/0,,15914468_401,00.png"),
    ("France 24", "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/international/france-24-english-int.png"),
    ("Al Jazeera", "https://i.imgur.com/2wOe3bM.png"),
    ("TRT World", "https://i.imgur.com/55SK22l.png"),
    ("Arirang TV", "https://i.imgur.com/Asu5pE9.png"),
    ("BBC World News", "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/united-kingdom/bbc-world-news-uk.png"),
    ("CNN International", cnn_logo),
]

print("\n" + "="*60)
print("TESTANDO LOGOS DOS CANAIS NEWS WORLD:")
print("="*60)
for name, url in logos:
    is_online, status = test_url(url, timeout=8)
    print(f"  {name}: {'✓' if is_online else '✗'} ({status})")
    # Check for .svg
    if '.svg' in url.lower():
        print(f"    ⚠ AVISO: Logo é .svg!")
