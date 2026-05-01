import sys
import logging
import traceback

logging.basicConfig(level=logging.DEBUG)

try:
    from downloader import get_video_info, _YTDLP_LOCK, _YTDLP_MODULE, init_ytdlp_background, update_ytdlp
    print("yt-dlp initializing...")
    update_ytdlp()
    print("get_video_info running...")
    title, size, thumb, formats, qualities, subs = get_video_info(
        "https://www.youtube.com/watch?v=yIEjB5oEeeU",
        browser_auth="chrome"
    )
    print(f"Success! Title: {title}")
except Exception as e:
    print(f"Exception Output: {e}")
