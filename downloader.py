import os
import sys
import shutil
import tempfile
import zipfile
import importlib
import time
import requests
from urllib.parse import urlparse, parse_qs

from app_config import app_data_dir
from logging_utils import get_logger
from net_utils import request_with_retry

_YTDLP_CHECKED = False
_YTDLP_MODULE = None
_YTDLP_VERSION_FILE = "yt_dlp_version.txt"
_YTDLP_LAST_CHECK_FILE = "yt_dlp_last_check.txt"
_YTDLP_CHECK_INTERVAL = 24 * 60 * 60
_FORMAT_CACHE = {}

_log = get_logger()


class DownloadPaused(Exception):
    pass


class DownloadCancelled(Exception):
    pass


def _get_deps_dir():
    return os.path.join(app_data_dir(), "deps")


def _local_ytdlp_present(deps_dir):
    try:
        for name in os.listdir(deps_dir):
            if name.startswith("yt_dlp"):
                return True
    except Exception:
        return False
    return False


def _should_check_update(deps_dir):
    last_check_path = os.path.join(deps_dir, _YTDLP_LAST_CHECK_FILE)
    if not os.path.exists(last_check_path):
        return True
    try:
        with open(last_check_path, "r", encoding="utf-8") as f:
            ts = float(f.read().strip() or "0")
        if ts <= 0:
            return True
        return (time.time() - ts) >= _YTDLP_CHECK_INTERVAL
    except Exception:
        return True


def _ensure_ytdlp_updated(force=False):
    deps_dir = _get_deps_dir()
    try:
        os.makedirs(deps_dir, exist_ok=True)
    except Exception:
        _log.warning("Failed to create deps dir: %s", deps_dir)
        return

    if deps_dir not in sys.path:
        sys.path.insert(0, deps_dir)

    version_path = os.path.join(deps_dir, _YTDLP_VERSION_FILE)
    local_version = None
    if os.path.exists(version_path):
        try:
            with open(version_path, "r", encoding="utf-8") as f:
                local_version = f.read().strip()
        except Exception:
            local_version = None

    if not force:
        if not _should_check_update(deps_dir) and _local_ytdlp_present(deps_dir):
            return

    try:
        resp = request_with_retry("GET", "https://pypi.org/pypi/yt-dlp/json", timeout=10)
        data = resp.json()
        latest = data.get("info", {}).get("version")
    except Exception as exc:
        _log.warning("yt-dlp update check failed: %s", exc)
        return

    if not latest or latest == local_version:
        try:
            with open(os.path.join(deps_dir, _YTDLP_LAST_CHECK_FILE), "w", encoding="utf-8") as f:
                f.write(str(time.time()))
        except Exception:
            pass
        return

    wheel_url = None
    for item in data.get("releases", {}).get(latest, []):
        name = item.get("filename") or ""
        if name.endswith("py3-none-any.whl"):
            wheel_url = item.get("url")
            break

    if not wheel_url:
        return

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            wheel_path = os.path.join(tmpdir, "yt_dlp.whl")
            r = request_with_retry("GET", wheel_url, timeout=20)
            with open(wheel_path, "wb") as f:
                f.write(r.content)

            for name in os.listdir(deps_dir):
                if name.startswith("yt_dlp") or name.startswith("yt_dlp-"):
                    path = os.path.join(deps_dir, name)
                    try:
                        if os.path.isdir(path):
                            shutil.rmtree(path, ignore_errors=True)
                        else:
                            os.remove(path)
                    except Exception:
                        _log.warning("Failed to remove old yt-dlp: %s", path)

            with zipfile.ZipFile(wheel_path, "r") as zf:
                zf.extractall(deps_dir)

        with open(version_path, "w", encoding="utf-8") as f:
            f.write(latest)
    except Exception as exc:
        _log.warning("yt-dlp update failed: %s", exc)
        return
    try:
        with open(os.path.join(deps_dir, _YTDLP_LAST_CHECK_FILE), "w", encoding="utf-8") as f:
            f.write(str(time.time()))
    except Exception:
        pass


def _get_yt_dlp():
    global _YTDLP_CHECKED, _YTDLP_MODULE
    if _YTDLP_MODULE:
        return _YTDLP_MODULE
    if not _YTDLP_CHECKED:
        _ensure_ytdlp_updated()
        _YTDLP_CHECKED = True
    _YTDLP_MODULE = importlib.import_module("yt_dlp")
    return _YTDLP_MODULE


def update_ytdlp():
    _ensure_ytdlp_updated(force=True)


def _default_download_dir():
    home = os.path.expanduser("~")
    if home:
        return os.path.join(home, "Downloads")
    return os.path.join(os.getcwd(), "downloads")


def _ensure_download_dir(path):
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        _log.warning("Failed to create download dir: %s", path)


def _find_local_binary(name):
    candidates = []
    which = shutil.which(name)
    if which and os.path.exists(which):
        return which
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", "")
        if meipass:
            candidates.append(os.path.join(meipass, name))
        candidates.append(os.path.join(os.path.dirname(sys.executable), name))
    candidates.append(os.path.join(os.getcwd(), name))

    for path in candidates:
        if path and os.path.exists(path):
            return path
    return None


def get_video_info(url,
                   timeout=10,
                   cookiefile=None,
                   allow_playlist=False,
                   quality=None,
                   container="auto"):
    if not is_valid_youtube_url(url):
        raise ValueError("Invalid URL")

    playlist_mode = allow_playlist and _is_playlist_url(url)
    url = normalize_youtube_url(url, keep_playlist=playlist_mode)

    base_opts = {
        "quiet": True,
        "noplaylist": not playlist_mode,
        "skip_download": True,
        "socket_timeout": timeout,
        "ignore_no_formats_error": True,
        "remote_components": ["ejs:github"],
        "http_headers": {
            "User-Agent":
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        },
        "extractor_args": {
            "youtube": {
                "player_client": ["web", "web_safari"]
            }
        }
    }

    if playlist_mode:
        base_opts["extract_flat"] = "in_playlist"

    js_runtimes = _js_runtimes()
    if js_runtimes:
        base_opts["js_runtimes"] = js_runtimes

    info = None
    last_err = None
    format_candidates = None
    if quality:
        format_candidates = _build_format_candidates(quality, container)

    if format_candidates:
        for fmt, _ in format_candidates:
            try:
                opts = dict(base_opts)
                opts["format"] = fmt
                info = _extract_info_with_cookies(url, opts, cookiefile)
                break
            except Exception as e:
                last_err = e
                continue
    else:
        try:
            opts = dict(base_opts)
            opts["format"] = "best"
            info = _extract_info_with_cookies(url, opts, cookiefile)
        except Exception as e:
            last_err = e

    if info is None and last_err:
        raise last_err

    if info.get("_type") == "playlist":
        title = info.get("title") or "Playlist"
        count = info.get("playlist_count")
        if count is None:
            entries = info.get("entries") or []
            try:
                count = len(entries)
            except Exception:
                count = None
        if count:
            title = f"Playlist: {title} ({count} videos)"
        else:
            title = f"Playlist: {title}"

        thumbnail = info.get("thumbnail")
        if not thumbnail:
            entries = info.get("entries") or []
            if isinstance(entries, list) and entries:
                thumbnail = entries[0].get("thumbnail")

        return title, "Unknown", thumbnail, [], [], []

    title = info.get("title", "Unknown")

    size_mb = _estimate_size_mb(info)
    if size_mb is None:
        size_mb = "Unknown"

    thumbnail = info.get("thumbnail")

    cache_key = info.get("id") or normalize_youtube_url(url, keep_playlist=playlist_mode)
    cached = _FORMAT_CACHE.get(cache_key)
    if cached:
        available_formats, available_qualities = cached
    else:
        available_formats, available_qualities = _available_format_quality(info)
        _FORMAT_CACHE[cache_key] = (available_formats, available_qualities)
    available_subtitles = _available_subtitles(info)
    return title, size_mb, thumbnail, available_formats, available_qualities, available_subtitles


def _available_subtitles(info):
    langs = set()
    subs = info.get("subtitles") or {}
    auto = info.get("automatic_captions") or {}
    if isinstance(subs, dict):
        langs.update([k for k in subs.keys() if k])
    if isinstance(auto, dict):
        langs.update([k for k in auto.keys() if k])
    return sorted(langs)


def _estimate_size_mb(info):
    requested = info.get("requested_formats")
    if isinstance(requested, list) and requested:
        total = 0
        for fmt in requested:
            f_size = fmt.get("filesize") or fmt.get("filesize_approx")
            if f_size:
                total += f_size
        if total:
            return round(total / (1024 * 1024), 2)

    filesize = info.get("filesize") or info.get("filesize_approx")
    if filesize:
        return round(filesize / (1024 * 1024), 2)

    formats = info.get("formats") or []
    best_size = None
    for f in formats:
        f_size = f.get("filesize") or f.get("filesize_approx")
        if f_size and (best_size is None or f_size > best_size):
            best_size = f_size
    if best_size:
        return round(best_size / (1024 * 1024), 2)

    duration = info.get("duration")
    tbr = info.get("tbr")
    if duration and tbr:
        try:
            size_bytes = float(duration) * float(tbr) * 1000 / 8
            return round(size_bytes / (1024 * 1024), 2)
        except Exception:
            return None

    return None


def _available_format_quality(info):
    formats = info.get("formats") or []
    exts = {f.get("ext") for f in formats if f.get("ext")}
    format_labels = []
    if any(ext in ("mp4", "m4a") for ext in exts):
        format_labels.append("MP4")
    if "webm" in exts:
        format_labels.append("WEBM")
    if exts:
        format_labels.append("MKV")

    heights = [f.get("height") for f in formats if f.get("height")]
    max_h = max(heights) if heights else 0
    quality_labels = []
    if max_h >= 720:
        quality_labels.append("720p")
    if max_h >= 1080:
        quality_labels.append("1080p")
    if max_h >= 1440:
        quality_labels.append("2K")
    if max_h >= 2160:
        quality_labels.append("4K")

    return format_labels, quality_labels


def normalize_youtube_url(url, keep_playlist=False):
    try:
        parsed = urlparse(url.strip())
        host = (parsed.netloc or "").lower()
        qs = parse_qs(parsed.query)
        list_id = qs.get("list", [""])[0]

        if host in ("youtu.be", "www.youtu.be"):
            vid = parsed.path.strip("/")
            if vid:
                if keep_playlist and list_id:
                    return f"https://www.youtube.com/watch?v={vid}&list={list_id}"
                return f"https://www.youtube.com/watch?v={vid}"

        if "youtube.com" in host:
            if parsed.path.startswith("/playlist"):
                if keep_playlist and list_id:
                    return f"https://www.youtube.com/playlist?list={list_id}"
                return url
            if parsed.path.startswith("/watch"):
                vid = qs.get("v", [""])[0]
                if vid:
                    if keep_playlist and list_id:
                        return f"https://www.youtube.com/watch?v={vid}&list={list_id}"
                    return f"https://www.youtube.com/watch?v={vid}"
            if parsed.path.startswith("/shorts/"):
                vid = parsed.path.split("/shorts/")[1].split("/")[0]
                if vid:
                    if keep_playlist and list_id:
                        return f"https://www.youtube.com/watch?v={vid}&list={list_id}"
                    return f"https://www.youtube.com/watch?v={vid}"
    except Exception:
        return url

    return url


def is_valid_youtube_url(url):
    try:
        parsed = urlparse(url.strip())
        if parsed.scheme not in ("http", "https"):
            return False
        host = (parsed.netloc or "").lower()
        if host.startswith("www."):
            host = host[4:]
        allowed = {
            "youtube.com",
            "m.youtube.com",
            "music.youtube.com",
            "youtu.be"
        }
        if host not in allowed:
            return False
        if host == "youtu.be":
            return bool(parsed.path.strip("/"))
        if parsed.path.startswith("/watch"):
            qs = parse_qs(parsed.query)
            return bool(qs.get("v", [""])[0])
        if parsed.path.startswith("/playlist"):
            qs = parse_qs(parsed.query)
            return bool(qs.get("list", [""])[0])
        if parsed.path.startswith("/shorts/"):
            return True
        return False
    except Exception:
        return False


def is_playlist_url(url):
    return _is_playlist_url(url)


def _is_playlist_url(url):
    try:
        parsed = urlparse(url.strip())
        host = (parsed.netloc or "").lower()
        qs = parse_qs(parsed.query)
        list_id = qs.get("list", [""])[0]
        if list_id:
            return True
        if "youtube.com" in host and parsed.path.startswith("/playlist"):
            return True
    except Exception:
        return False
    return False


def _unique_path(path):
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    index = 1
    while True:
        candidate = f"{base} ({index}){ext}"
        if not os.path.exists(candidate):
            return candidate
        index += 1


def _make_renaming_ydl(yt_dlp_mod):
    class _RenamingYDL(yt_dlp_mod.YoutubeDL):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._unique_outtmpl_cache = {}

        def prepare_filename(self, info_dict, *args, **kwargs):
            base = super().prepare_filename(info_dict, *args, **kwargs)
            cached = self._unique_outtmpl_cache.get(base)
            if cached:
                return cached
            unique = _unique_path(base)
            self._unique_outtmpl_cache[base] = unique
            return unique

    return _RenamingYDL


def _download_with_opts(url, ydl_opts):
    ytdlp = _get_yt_dlp()
    RenamingYDL = _make_renaming_ydl(ytdlp)
    with RenamingYDL(ydl_opts) as ydl:
        ydl.download([url])


class _SilentLogger:
    def debug(self, msg):
        pass

    def warning(self, msg):
        pass

    def error(self, msg):
        pass


def _cookiefile_path(cookiefile=None):
    if cookiefile and os.path.exists(cookiefile):
        return cookiefile
    path = os.path.join(os.getcwd(), "cookies.txt")
    return path if os.path.exists(path) else None


def _js_runtimes():
    runtimes = {}
    node_path = shutil.which("node")
    deno_path = shutil.which("deno")
    if node_path:
        runtimes["node"] = {"path": node_path}
    if deno_path:
        runtimes["deno"] = {"path": deno_path}
    else:
        local_deno = os.path.join(os.getcwd(), "deno.exe")
        if os.path.exists(local_deno):
            runtimes["deno"] = {"path": local_deno}
        else:
            local_appdata = os.getenv("LOCALAPPDATA")
            if local_appdata:
                fallback = os.path.join(
                    local_appdata,
                    "Microsoft",
                    "WinGet",
                    "Packages",
                    "DenoLand.Deno_Microsoft.Winget.Source_8wekyb3d8bbwe",
                    "deno.exe"
                )
                if os.path.exists(fallback):
                    runtimes["deno"] = {"path": fallback}
    return runtimes or None


def _is_cookie_error(msg):
    cookie_markers = (
        "Could not copy Chrome cookie database",
        "CookieLoadError",
        "failed to load cookies",
        "Failed to decrypt with DPAPI",
        "could not find firefox cookies database",
        "Could not copy Edge cookie database",
    )
    return any(m in msg for m in cookie_markers)


def _extract_info_with_cookies(url, base_opts, cookiefile=None):
    ytdlp = _get_yt_dlp()
    cookiefile = _cookiefile_path(cookiefile)
    if cookiefile:
        ydl_opts = dict(base_opts)
        ydl_opts["cookiefile"] = cookiefile
        with ytdlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=False)

    cookie_sources = [
        ("chrome",),
        ("edge",),
        ("firefox",)
    ]

    last_err = None

    for cookies in cookie_sources + [None]:
        ydl_opts = dict(base_opts)
        if cookies:
            ydl_opts["cookiesfrombrowser"] = cookies
        try:
            with ytdlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=False)
        except Exception as e:
            last_err = e
            continue

    if last_err:
        raise last_err


def _build_format_candidates(quality, container):
    height_map = {
        "720p": 720,
        "1080p": 1080,
        "2K": 1440,
        "4K": 2160
    }

    if quality == "Auto (Best)":
        base_video = "bestvideo*"
        base_best = "best"
        generic = f"{base_video}+bestaudio/{base_best}"
    else:
        h = height_map.get(quality)
        if h:
            base_video = f"bestvideo*[height<={h}]"
            base_best = f"best[height<={h}]"
            generic = f"{base_video}+bestaudio/{base_best}/bestvideo*+bestaudio/best"
        else:
            base_video = "bestvideo*"
            base_best = "best"
            generic = f"{base_video}+bestaudio/{base_best}"

    mp4_pref = f"{base_video}[ext=mp4]+bestaudio[ext=m4a]/{base_best}[ext=mp4]"
    webm_pref = f"{base_video}[ext=webm]+bestaudio[ext=webm]/{base_best}[ext=webm]"

    container = (container or "auto").lower()

    if container == "auto":
        return [
            (mp4_pref, "mp4"),
            (generic, "mkv")
        ]
    if container == "mp4":
        return [(mp4_pref, "mp4")]
    if container == "webm":
        return [(webm_pref, "webm")]
    if container == "mkv":
        return [(generic, "mkv")]
    return [(generic, "mkv")]


def download_video(url,
                   quality,
                   progress_callback,
                   cookiefile=None,
                   download_playlist=False,
                   download_dir=None,
                   container="mp4",
                   subtitles=False,
                   subtitles_langs=None,
                   embed_subtitles=True,
                   rate_limit=None,
                   pause_check=None,
                   cancel_check=None):
    if not is_valid_youtube_url(url):
        raise ValueError("Invalid URL")

    download_dir = download_dir or _default_download_dir()
    _ensure_download_dir(download_dir)

    playlist_mode = download_playlist and _is_playlist_url(url)
    url = normalize_youtube_url(url, keep_playlist=playlist_mode)

    format_candidates = _build_format_candidates(quality, container)

    progress_state = {
        "by_key": {},
        "expected_total": None
    }

    def _seed_expected_total(info):
        if progress_state["expected_total"] is not None:
            return
        formats = info.get("requested_formats")
        if not isinstance(formats, list):
            return
        total = 0
        for fmt in formats:
            f_size = fmt.get("filesize") or fmt.get("filesize_approx")
            if f_size:
                total += f_size
        if total:
            progress_state["expected_total"] = total

    def _aggregate_totals():
        downloaded_sum = 0
        total_sum = 0
        for entry in progress_state["by_key"].values():
            if entry.get("downloaded") is not None:
                downloaded_sum += entry["downloaded"]
            if entry.get("total"):
                total_sum += entry["total"]
        expected = progress_state["expected_total"]
        if expected:
            total_sum = expected
        return downloaded_sum or None, total_sum or None

    def _make_progress_hook(last_finished):
        def hook(d):
            if cancel_check and cancel_check():
                raise DownloadCancelled("DOWNLOAD_CANCELLED")
            if pause_check and pause_check():
                raise DownloadPaused("DOWNLOAD_PAUSED")
            info = d.get("info_dict") or {}
            _seed_expected_total(info)

            key = d.get("filename") or info.get("format_id") or info.get("id") or "unknown"
            entry = progress_state["by_key"].setdefault(key, {"downloaded": 0, "total": None})

            if d["status"] == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate")
                downloaded = d.get("downloaded_bytes", 0)

                entry["downloaded"] = downloaded
                if total:
                    entry["total"] = total

                downloaded_sum, total_sum = _aggregate_totals()

                if total_sum:
                    percent = min(downloaded_sum / total_sum * 100, 100)
                else:
                    if total:
                        percent = downloaded / total * 100
                    else:
                        frag_index = d.get("fragment_index")
                        frag_count = d.get("fragment_count")
                        if frag_index and frag_count:
                            percent = (frag_index / frag_count) * 100
                        else:
                            percent = 0
                speed = d.get("speed")

                if speed:
                    speed_kb = round(speed / 1024, 2)
                    speed_text = f"{speed_kb} KB/s"
                else:
                    speed_text = None

                progress_callback(percent, speed_text, downloaded_sum, total_sum)

            elif d["status"] == "finished":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or entry.get("total")
                if total:
                    entry["total"] = total
                    entry["downloaded"] = total
                else:
                    entry["downloaded"] = entry.get("downloaded") or 0

                downloaded_sum, total_sum = _aggregate_totals()
                if total_sum and downloaded_sum is not None:
                    percent = min(downloaded_sum / total_sum * 100, 100)
                else:
                    percent = 100
                progress_callback(percent, None, downloaded_sum, total_sum)
                last_finished["filename"] = d.get("filename")
                last_finished["info"] = d.get("info_dict") or {}
        return hook

    def _make_post_hook(results, seen_keys):
        def hook(d):
            if d.get("status") != "finished":
                return
            info = d.get("info_dict") or {}
            filename = d.get("filename") or info.get("filepath") or info.get("_filename")
            if not filename:
                return
            key = info.get("id") or filename
            if key in seen_keys:
                return
            seen_keys.add(key)
            results.append({
                "id": info.get("id"),
                "title": info.get("title") or os.path.basename(filename),
                "url": info.get("webpage_url") or url,
                "thumbnail": info.get("thumbnail"),
                "filepath": filename
            })
        return hook

    outtmpl = os.path.join(download_dir, "%(title)s.%(ext)s")
    if playlist_mode:
        outtmpl = os.path.join(
            download_dir,
            "%(playlist_title)s",
            "%(playlist_index)02d - %(title)s.%(ext)s"
        )

    base_opts = {
        "outtmpl": outtmpl,
        "nopart": False,
        "continuedl": True,
        "overwrites": False,
        "quiet": True,
        "noprogress": False,
        "no_warnings": True,
        "logger": _SilentLogger(),
        "noplaylist": not playlist_mode,
        "retries": 10,
        "fragment_retries": 10,
        "concurrent_fragment_downloads": 5,
        "remote_components": ["ejs:github"],
        "http_headers": {
            "User-Agent":
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }
    }
    if rate_limit and rate_limit > 0:
        base_opts["ratelimit"] = int(rate_limit)

    if subtitles:
        base_opts["writesubtitles"] = True
        base_opts["writeautomaticsub"] = True
        base_opts["embedsubtitles"] = bool(embed_subtitles)
        base_opts["subtitlesformat"] = "best"
        if subtitles_langs:
            if isinstance(subtitles_langs, str):
                langs = [s.strip() for s in subtitles_langs.split(",") if s.strip()]
            else:
                langs = [s for s in subtitles_langs if s]
            if langs:
                base_opts["subtitleslangs"] = langs

    ffmpeg_path = _find_local_binary("ffmpeg.exe")
    if ffmpeg_path:
        base_opts["ffmpeg_location"] = ffmpeg_path

    js_runtimes = _js_runtimes()
    if js_runtimes:
        base_opts["js_runtimes"] = js_runtimes

    cookiefile = _cookiefile_path(cookiefile)
    if cookiefile:
        base_opts["cookiefile"] = cookiefile

    client_attempts = [
        (None, None),
        (["web"], None),
        (["web_safari"], None),
        (["web_embedded"], None),
        (["ios"], None),
        (["tv"], None),
        (["web_safari"], ("chrome",)),
        (["web_safari"], ("edge",)),
        (None, ("chrome",)),
        (None, ("edge",)),
        (None, ("firefox",)),
        (None, None),
    ]

    last_err = None
    last_non_cookie_err = None

    def _is_retryable_error(msg):
        msg = msg or ""
        lowered = msg.lower()
        if "requested format is not available" in msg:
            return True
        if "http error 403" in msg or "http error 429" in msg:
            return True
        if "downloaded file is empty" in lowered or "file is empty" in lowered:
            return True
        if "page needs to be reloaded" in lowered:
            return True
        return False

    for fmt, merge_fmt in format_candidates:
        for client, cookies in client_attempts:
            if cookiefile and cookies:
                continue
            results = []
            seen_keys = set()
            last_finished = {}
            ydl_opts = dict(base_opts)
            ydl_opts["format"] = fmt
            ydl_opts["merge_output_format"] = merge_fmt
            ydl_opts["progress_hooks"] = [_make_progress_hook(last_finished)]
            ydl_opts["postprocessor_hooks"] = [_make_post_hook(results, seen_keys)]
            if client:
                ydl_opts["extractor_args"] = {
                    "youtube": {
                        "player_client": client
                    }
                }
            if cookies:
                ydl_opts["cookiesfrombrowser"] = cookies
            try:
                _download_with_opts(url, ydl_opts)
                if not results and last_finished.get("filename"):
                    info = last_finished.get("info") or {}
                    filename = last_finished.get("filename")
                    results.append({
                        "id": info.get("id"),
                        "title": info.get("title") or os.path.basename(filename),
                        "url": info.get("webpage_url") or url,
                        "thumbnail": info.get("thumbnail"),
                        "filepath": filename
                    })
                return results
            except Exception as e:
                msg = str(e)
                if _is_cookie_error(msg):
                    continue
                last_err = e
                last_non_cookie_err = e
                if _is_retryable_error(msg):
                    continue
                raise

    if last_non_cookie_err:
        raise last_non_cookie_err
    if last_err:
        raise last_err
