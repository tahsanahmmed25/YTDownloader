import sys
import argparse
import os
import sys
import traceback
import threading

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtGui import QIcon

from app_config import get_icon_path
from logging_utils import setup_logging
from ui.main_window import Downloader


def _build_arg_parser():
    parser = argparse.ArgumentParser(description="YTDownloader")
    parser.add_argument("--cli", action="store_true", help="Run in CLI mode")
    parser.add_argument("--url", help="YouTube URL to download")
    parser.add_argument("--info", action="store_true", help="Fetch info only")
    parser.add_argument("--quality", default="Auto (Best)", help="Quality label")
    parser.add_argument("--format", dest="container", default="auto", help="Container: auto/mp4/mkv/webm")
    parser.add_argument("--playlist", action="store_true", help="Download playlist")
    parser.add_argument("--cookies", default="", help="Path to cookies.txt")
    parser.add_argument("--output-dir", default="", help="Download directory")
    parser.add_argument("--subtitles", action="store_true", help="Download subtitles")
    parser.add_argument("--embed-subs", action="store_true", help="Embed subtitles")
    parser.add_argument("--subs-lang", default="", help="Subtitle language code")
    parser.add_argument("--rate-limit", type=int, default=0, help="Rate limit KB/s (0=unlimited)")
    return parser


def _run_cli(args):
    from downloader import (
        download_video,
        get_video_info,
        is_valid_youtube_url,
        is_playlist_url,
    )
    from errors import humanize_error

    url = (args.url or "").strip()
    if not url:
        print("Missing --url")
        return 2
    if not is_valid_youtube_url(url):
        print("Error: Please provide a valid YouTube URL.")
        return 2
    if args.playlist and not is_playlist_url(url):
        print("Error: Playlist mode requires a valid playlist link.")
        return 2

    cookies = (args.cookies or "").strip() or None
    container = (args.container or "auto").lower()
    out_dir = (args.output_dir or "").strip() or None
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    if args.info:
        try:
            title, size, thumb, formats, qualities, subtitles = get_video_info(
                url,
                cookiefile=cookies,
                allow_playlist=args.playlist,
                quality=args.quality,
                container=container
            )
            print(f"Title: {title}")
            print(f"Estimated size: {size}")
            print(f"Formats: {', '.join(formats or [])}")
            print(f"Qualities: {', '.join(qualities or [])}")
            if subtitles:
                print(f"Subtitles: {', '.join(subtitles)}")
            return 0
        except Exception as exc:
            print(f"Error: {humanize_error(str(exc), cookies_loaded=bool(cookies))}")
            return 1

    def progress_cb(percent, speed=None, downloaded=None, total=None):
        line = f"{percent:6.2f}%"
        if downloaded is not None and total:
            line += f" | {downloaded / (1024*1024):.2f} MB / {total / (1024*1024):.2f} MB"
        if speed:
            line += f" | {speed}"
        print(line, end="\r", flush=True)

    rate_limit = args.rate_limit * 1024 if args.rate_limit else None

    try:
        download_video(
            url,
            args.quality,
            progress_cb,
            cookiefile=cookies,
            download_playlist=args.playlist,
            download_dir=out_dir,
            container=container,
            subtitles=args.subtitles,
            subtitles_langs=args.subs_lang,
            embed_subtitles=args.embed_subs,
            rate_limit=rate_limit
        )
        print()
        return 0
    except Exception as exc:
        print(f"\nError: {humanize_error(str(exc), cookies_loaded=bool(cookies))}")
        return 1


def main():
    logger = setup_logging()

    def _thread_excepthook(args):
        tb = "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback))
        try:
            logger.exception("Uncaught thread exception:\n%s", tb)
        except Exception:
            pass
        try:
            print(tb, file=sys.stderr)
        except Exception:
            pass

    threading.excepthook = _thread_excepthook

    if "--update-ytdlp" in sys.argv:
        from downloader import update_ytdlp
        update_ytdlp()
        sys.exit(0)

    parser = _build_arg_parser()
    args, _ = parser.parse_known_args()
    if args.cli or args.url or args.info:
        sys.exit(_run_cli(args))

    app = QApplication(sys.argv)

    def handle_exception(exc_type, exc_value, exc_traceback):
        tb = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        try:
            logger.exception("Uncaught exception:\n%s", tb)
        except Exception:
            pass
        try:
            QMessageBox.critical(None, "Unhandled Error", tb)
        except Exception:
            print(tb, file=sys.stderr)

    sys.excepthook = handle_exception

    icon_path = get_icon_path()
    if icon_path:
        app.setWindowIcon(QIcon(icon_path))

    window = Downloader()
    window.show()
    
    from downloader import init_ytdlp_background
    init_ytdlp_background()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
