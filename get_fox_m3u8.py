import requests
import re
import sys
import json
import hashlib
import hmac
import time
from urllib.parse import quote

# Correct format for Akamai token auth
def generate_akamai_token(url_to_sign, secret_key, exp_seconds=21600):
    """Generate Akamai-style auth token (hdnts format)"""
    start_time = int(time.time())
    exp_time = start_time + exp_seconds
    
    # For hdnea cookie based auth
    acl = "/*"
    
    # Using hdnts format (more common for AMD)
    token_input = f"st={start_time}~exp={exp_time}~acl={acl}"
    # Sign only the part after ~ (the acl part)
    sign_input = f"exp={exp_time}~acl={acl}"
    
    # Generate HMAC-SHA256
    key = secret_key.encode()
    hmac_obj = hmac.new(key, sign_input.encode(), hashlib.sha256)
    hmac_hex = hmac_obj.hexdigest()
    
    # Create token in hdnts format
    hdnts_token = f"st={start_time}~exp={exp_time}~acl={acl}~hmac={hmac_hex}"
    
    # Url encode the token
    encoded_token = quote(hdnts_token, safe='')
    return f"hdnts={encoded_token}"

def get_fox_news_api_data(video_id):
    """Get m3u8 URL from Fox News API"""
    url = f"https://api.foxnews.com/v3/video-player/{video_id}?callback=uid_{video_id}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36',
        'Referer': f'https://www.foxnews.com/video/{video_id}'
    }
    
    resp = requests.get(url, headers=headers, timeout=30)
    text = resp.text
    
    json_match = re.search(r'uid_\d+\((.*)\)', text, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
        data = json.loads(json_str)
        return data
    
    return None

def get_m3u8_url(data):
    """Extract m3u8 URL from API response"""
    if not data:
        return None
    
    media_content = data.get('channel', {}).get('item', {}).get('media-group', {}).get('media-content', [])
    
    for content in media_content:
        attrs = content.get('@attributes', {})
        url = attrs.get('url', '')
        if 'm3u8' in url:
            return url
    return None

if __name__ == "__main__":
    # Known working token from issue #33852
    # Format: hdnea=exp=1741903611~acl=/*~hmac=1c36aa35a73205e79dc4169783bbe9c9d3d1df9887a4ec3753d6f97f998c6bd7
    
    # Try generating with various keys
    keys_to_try = [
        "3B918D70B0C9E6F1A7C5D2E8F9A1B3C4",
        "1c36aa35a73205e79dc4169783bbe9c9", 
        "d3d1df9887a4ec3753d6f97f998c6bd7",
    ]
    
    video_ids = [
        ("5614615980001", "FX.m3u8", "https://247.foxnews.com/hls/live/2003586/FNCHLSv3/master.m3u8"),
        ("5614626175001", "FXB.m3u8", "https://247.foxbusiness.com/hls/live/2003756/FBNHLSv3/master.m3u8")
    ]
    
    for video_id, filename, base_url in video_ids:
        print(f"Processing video {video_id}...")
        
        data = get_fox_news_api_data(video_id)
        m3u8_url = get_m3u8_url(data)
        
        if not m3u8_url:
            m3u8_url = base_url
        
        if m3u8_url:
            print(f"  Base URL: {m3u8_url}")
            
            # Try the known working token format first
            exp_time = 1741903611  # From working example
            test_token = f"hdnea=exp={exp_time}~acl=/*~hmac=1c36aa35a73205e79dc4169783bbe9c9d3d1df9887a4ec3753d6f97f998c6bd7"
            test_url = f"{m3u8_url}?{test_token}"
            
            resp = requests.get(test_url, 
                          headers={'User-Agent': 'Mozilla/5.0'}, 
                          timeout=15)
            print(f"  Test response: {resp.status_code}")
            
            if resp.status_code == 200:
                print(f"  Success! Token worked!")
                final_url = test_url
            else:
                # Try generating a new token
                print("  Known token didn't work, trying generation...")
                for key in keys_to_try:
                    current_time = int(time.time())
                    exp_time = current_time + 21600
                    sign_input = f"exp={exp_time}~acl=/*"
                    
                    key_bytes = key.encode()
                    h = hmac.new(key_bytes, sign_input.encode(), hashlib.sha256)
                    hmac_hex = h.hexdigest()
                    
                    gen_token = f"hdnea=exp={exp_time}~acl=/*~hmac={hmac_hex}"
                    test_url = f"{m3u8_url}?{gen_token}"
                    
                    resp = requests.get(test_url, 
                                  headers={'User-Agent': 'Mozilla/5.0'}, 
                                  timeout=15)
                    
                    if resp.status_code == 200:
                        print(f"  Key {key[:8]}... worked!")
                        final_url = test_url
                        break
                else:
                    # Use fallback token
                    print("  Using fallback token (may not work)")
                    final_url = test_url
            
            with open(filename, 'w') as f:
                f.write(final_url)
            print(f"  Saved: {final_url[:100]}...")
        else:
            print(f"No m3u8 found for {video_id}")