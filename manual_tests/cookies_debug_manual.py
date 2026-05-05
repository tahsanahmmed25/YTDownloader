import logging
import traceback


def main():
    logging.basicConfig(level=logging.DEBUG)
    from downloader import get_video_info, update_ytdlp

    print("yt-dlp initializing...")
    update_ytdlp()
    print("get_video_info running...")
    title, size, thumb, formats, qualities, subs = get_video_info(
        "https://www.youtube.com/watch?v=3ptlSZqS",
        browser_auth="chrome"
    )
    print(f"Success! Title: {title}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Exception: {e}")
        traceback.print_exc()
