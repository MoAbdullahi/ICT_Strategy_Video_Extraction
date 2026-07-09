import re
import sys

def extract_video_url(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Look for video URLs in the HTML
    # Facebook often stores video URLs in script tags or as data attributes
    # Common patterns: "browser_native_sd_url", "browser_native_hd_url", "video_url"
    
    video_urls = re.findall(r'"browser_native_hd_url":"([^"]+)"', content)
    if not video_urls:
        video_urls = re.findall(r'"browser_native_sd_url":"([^"]+)"', content)
    if not video_urls:
        video_urls = re.findall(r'"video_url":"([^"]+)"', content)
    
    if video_urls:
        # Unescape unicode characters if any
        url = video_urls[0].replace('\\/', '/')
        print(url)
    else:
        print("No video URL found.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        extract_video_url(sys.argv[1])
    else:
        print("Usage: python3 extract_fb_video.py <html_file_path>")
