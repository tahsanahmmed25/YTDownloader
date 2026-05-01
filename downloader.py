import os
import re
import time
import sys
import shutil
import zipfile
import importlib
import subprocess
import threading
import traceback
import requests
from urllib.parse import urlparse, parse_qs

from app_config import app_data_dir, local_tmp_dir
from logging_utils import get_logger
from net_utils import request_with_retry

_YTDLP_CHECKED = False
_YTDLP_MODULE = None
_YTDLP_VERSION_FILE = "yt_dlp_version.txt"
_YTDLP_LAST_CHECK_FILE = "yt_dlp_last_check.txt"
_YTDLP_CHECK_INTERVAL = 24 * 60 * 60
_FORMAT_CACHE = {}
_FORMAT_CACHE_LOCK = threading.Lock()

_log = get_logger()
_YTDLP_LOCK = threading.Lock()


class DownloadPaused(Exception):
    pass


class DownloadCancelled(Exception):
    pass


class NotReadyError(Exception):
    """Raised when a required binary (yt-dlp.exe) is not yet available."""
    pass


class CookieLockError(Exception):
    def __init__(self, browser_name, details=""):
        self.browser_name = browser_name
        self.details = details
        super().__init__(f"Cookies for {browser_name} are locked. {details}")


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

    tmpdir = local_tmp_dir()
    wheel_path = os.path.join(tmpdir, "yt_dlp.whl")
    try:
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
    finally:
        # Always remove the temp wheel file, even if extraction fails
        try:
            if os.path.exists(wheel_path):
                os.remove(wheel_path)
        except Exception:
            pass
    try:
        with open(os.path.join(deps_dir, _YTDLP_LAST_CHECK_FILE), "w", encoding="utf-8") as f:
            f.write(str(time.time()))
    except Exception:
        pass


def _get_yt_dlp():
    global _YTDLP_CHECKED, _YTDLP_MODULE
    if _YTDLP_MODULE:
        return _YTDLP_MODULE
    # Prefer an already-installed/bundled yt-dlp first.
    try:
        _YTDLP_MODULE = importlib.import_module("yt_dlp")
        return _YTDLP_MODULE
    except Exception:
        pass

    if not _YTDLP_CHECKED:
        _ensure_ytdlp_updated()
        _YTDLP_CHECKED = True

    _YTDLP_MODULE = importlib.import_module("yt_dlp")
    return _YTDLP_MODULE


def update_ytdlp(force=True):
    _ensure_ytdlp_updated(force=force)

def init_ytdlp_background():
    def _run():
        try:
            update_ytdlp(force=False)
        except Exception as e:
            _log.warning("Background yt-dlp update check failed: %s", e)
    t = threading.Thread(target=_run, daemon=True)
    t.start()


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
    """Find a binary by name on the current platform.
    Searches (in order): system PATH, bin_dir(), PyInstaller MEIPASS, exe dir, cwd.
    Pass the base name without extension (e.g. 'yt-dlp', 'ffmpeg') —
    this function adds the platform-correct suffix automatically.
    """
    from app_config import bin_dir, bin_name
    platform_name = bin_name(name)   # adds .exe on Windows, nothing on Linux

    # 1. System PATH
    which = shutil.which(platform_name)
    if not which and name != platform_name:
        which = shutil.which(name)   # also try without suffix just in case
    if which and os.path.exists(which):
        return which

    candidates = []
    # 2. Auto-download bin_dir (yt-dlp/ffmpeg downloaded by manager modules)
    candidates.append(os.path.join(bin_dir(), platform_name))
    # 3. PyInstaller bundle
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", "")
        if meipass:
            candidates.append(os.path.join(meipass, platform_name))
        candidates.append(os.path.join(os.path.dirname(sys.executable), platform_name))
    # 4. Current working directory
    candidates.append(os.path.join(os.getcwd(), platform_name))

    for path in candidates:
        if path and os.path.exists(path):
            return path
    return None


def get_video_info(url,
                   timeout=10,
                   cookiefile=None,
                   browser_auth=None,
                   allow_playlist=False,
                   quality=None,
                   container="auto"):
    if not is_valid_youtube_url(url):
        raise ValueError("Invalid URL")

    playlist_mode = allow_playlist and _is_playlist_url(url)
    url = normalize_youtube_url(url, keep_playlist=playlist_mode)

    base_opts = build_base_options(
        timeout=timeout,
        noplaylist=not playlist_mode,
        skip_download=True,
        logger=_SilentLogger()
    )

    if playlist_mode:
        base_opts["extract_flat"] = "in_playlist"

    info = _extract_best_video_info(url, base_opts, cookiefile, browser_auth)

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
    with _FORMAT_CACHE_LOCK:
        cached = _FORMAT_CACHE.get(cache_key)
    if cached:
        available_formats, available_qualities = cached
    else:
        available_formats, available_qualities = _available_format_quality(info)
        with _FORMAT_CACHE_LOCK:
            _FORMAT_CACHE[cache_key] = (available_formats, available_qualities)
    available_subtitles = _available_subtitles(info)
    return title, size_mb, thumbnail, available_formats, available_qualities, available_subtitles


def get_playlist_entries(url, cookiefile=None, browser_auth=None, timeout=15, max_items=0):
    if not is_valid_youtube_url(url):
        raise ValueError("Invalid URL")
    if not _is_playlist_url(url):
        raise ValueError("Invalid playlist URL")

    url = normalize_youtube_url(url, keep_playlist=True)
    ytdlp = _get_yt_dlp()

    base_opts = build_base_options(
        timeout=timeout,
        noplaylist=False,
        skip_download=True,
        logger=_SilentLogger()
    )
    base_opts["extract_flat"] = "in_playlist"

    info = None
    last_err = None
    auth_attempts = _iter_auth_attempts(
        cookiefile,
        browser_auth,
        allow_fallback=True,
        prefer_no_auth=True
    )
    for client in _client_fallbacks():
        for mode, value in auth_attempts:
            opts = dict(base_opts)
            if mode == "cookiefile":
                apply_restricted_mode_options(opts, cookiefile=value)
            elif mode == "browser":
                apply_restricted_mode_options(opts, browser_auth=value)
            else:
                apply_normal_mode_options(opts)
            apply_client_fallback(opts, client)
            _log.info("Playlist extract attempt: client=%s auth=%s", client or "default", mode)
            try:
                with _YTDLP_LOCK:
                    with ytdlp.YoutubeDL(opts) as ydl:
                        info = ydl.extract_info(url, download=False)
                break
            except Exception as e:
                last_err = e
                info = None
                continue
        if info is not None:
            break

    if info is None:
        if last_err:
            raise last_err
        raise RuntimeError("Failed to read playlist")

    if info.get("_type") != "playlist":
        raise ValueError("URL is not a playlist")

    entries = []
    raw_entries = info.get("entries") or []
    try:
        max_items = int(max_items or 0)
    except Exception:
        max_items = 0
    if max_items < 0:
        max_items = 0

    for entry in raw_entries:
        if not entry:
            continue
        if isinstance(entry, dict):
            vid = (entry.get("id") or "").strip()
            title = (entry.get("title") or "").strip() or "Unknown"
            raw_url = (entry.get("url") or entry.get("webpage_url") or "").strip()
            if raw_url and raw_url.startswith("http"):
                video_url = raw_url
            elif vid:
                video_url = f"https://www.youtube.com/watch?v={vid}"
            else:
                continue
            video_url = normalize_youtube_url(video_url, keep_playlist=False)
            entries.append({
                "id": vid,
                "title": title,
                "url": video_url,
                "thumbnail": entry.get("thumbnail")
            })
        elif isinstance(entry, str):
            vid = entry.strip()
            if not vid:
                continue
            entries.append({
                "id": vid,
                "title": "Unknown",
                "url": f"https://www.youtube.com/watch?v={vid}",
                "thumbnail": None
            })
        if max_items and len(entries) >= max_items:
            break

    return {
        "title": info.get("title") or "Playlist",
        "count": len(entries),
        "entries": entries
    }


def _available_subtitles(info):
    langs = set()
    subs = info.get("subtitles") or {}
    auto = info.get("automatic_captions") or {}
    if isinstance(subs, dict):
        langs.update([k for k in subs.keys() if k])
    if isinstance(auto, dict):
        langs.update([k for k in auto.keys() if k])
    return sorted(langs)


def _video_stream_formats(info):
    formats = info.get("formats") or []
    video = []
    for f in formats:
        vcodec = str(f.get("vcodec") or "none").lower()
        if vcodec == "none":
            continue
        ext = str(f.get("ext") or "").lower()
        note = str(f.get("format_note") or "").lower()
        proto = str(f.get("protocol") or "").lower()
        # Skip storyboard/image-like entries that do not represent actual video streams.
        if "storyboard" in note or ext == "mhtml" or "mhtml" in proto:
            continue
        video.append(f)
    return video


def _audio_stream_formats(info):
    formats = info.get("formats") or []
    audio = []
    for f in formats:
        vcodec = str(f.get("vcodec") or "none").lower()
        acodec = str(f.get("acodec") or "none").lower()
        if vcodec == "none" and acodec != "none":
            audio.append(f)
    return audio


def _info_score(info):
    videos = _video_stream_formats(info)
    if not videos:
        return (0, 0, 0)
    max_h = max((f.get("height") or 0 for f in videos), default=0)
    sized = sum(1 for f in videos if (f.get("filesize") or f.get("filesize_approx")))
    return (len(videos), max_h, sized)


def _extract_best_video_info(url, base_opts, cookiefile=None, browser_auth=None):
    started_at = time.time()
    max_probe_seconds = 45  # increased to give auth attempts enough time
    ytdlp = _get_yt_dlp()
    best_info = None
    best_score = (-1, -1, -1)
    last_err = None
    lock_err = None

    auth_attempts = _iter_auth_attempts(
        cookiefile,
        browser_auth,
        allow_fallback=True,
        prefer_no_auth=True   # try no-auth first so public videos always work;
                              # cookies are the second attempt for restricted videos
    )
    for client in _client_fallbacks():
        if (time.time() - started_at) >= max_probe_seconds:
            break
        for mode, value in auth_attempts:
            if (time.time() - started_at) >= max_probe_seconds:
                break
            opts = dict(base_opts)
            if mode == "cookiefile":
                apply_restricted_mode_options(opts, cookiefile=value)
                auth_label = "cookiefile"
            elif mode == "browser":
                apply_restricted_mode_options(opts, browser_auth=value)
                auth_label = f"browser:{value}"
            else:
                apply_normal_mode_options(opts)
                auth_label = "none"

            apply_client_fallback(opts, client)
            _log.info(
                "Info extract attempt: client=%s auth=%s%s",
                client or "default",
                auth_label,
                f" file={value}" if mode == "cookiefile" else ""
            )
            try:
                with _YTDLP_LOCK:
                    with ytdlp.YoutubeDL(opts) as ydl:
                        info = ydl.extract_info(url, download=False)
                        # Capture any cookie-related warnings emitted by yt-dlp internals
                        _check_ydl_cookie_warnings(ydl, base_opts)
            except Exception as e:
                import traceback
                tb = traceback.format_exc()
                err_str = str(e).lower()

                # ── Missing browser profile: skip this browser, try the next ──
                # e.g. "could not find opera cookies database in /home/.../.config/opera"
                if mode == "browser" and (
                    "could not find" in err_str and "cookies database" in err_str
                ):
                    _log.warning(
                        "Browser '%s' not found or not logged in — skipping. (%s)",
                        value, str(e).split("\n")[0]
                    )
                    continue  # try next browser — do NOT mark as last_err

                # ── Locked cookie DB ──
                if "PermissionError" in tb or "[Errno 13]" in tb or "Could not copy" in tb:
                    if mode == "browser":
                        _log.warning("Cookie database locked for %s", value)
                        lock_err = CookieLockError(value, str(e))
                        continue

                last_err = e
                continue
            score = _info_score(info)
            if best_info is None or score > best_score:
                best_info = info
                best_score = score
                if best_score[0] >= 2 and best_score[1] >= 720:
                    _log.info("Info extraction succeeded via client=%s auth=%s", client or "default", auth_label)
                    return best_info

    if best_info is not None:
        _log.info("Info extraction fallback selected.")
        return best_info

    if lock_err:
        raise lock_err

    # Check captured cookie warnings from the logger
    cookie_warn = _get_cookie_warning(base_opts)

    if last_err:
        if cookie_warn:
            raise RuntimeError(
                f"Cookie decryption failed: {cookie_warn}. "
                f"Original error: {last_err}"
            )
        raise last_err
    raise RuntimeError("Failed to extract video info")


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
    video_formats = _video_stream_formats(info)
    audio_formats = _audio_stream_formats(info)

    if video_formats:
        def _size_of(fmt):
            return fmt.get("filesize") or fmt.get("filesize_approx") or 0

        best_video = max(
            video_formats,
            key=lambda f: (
                f.get("height") or 0,
                _size_of(f),
                f.get("tbr") or 0
            )
        )
        v_size = _size_of(best_video)
        if v_size:
            best_audio_size = 0
            if audio_formats:
                best_audio = max(
                    audio_formats,
                    key=lambda f: (_size_of(f), f.get("abr") or 0, f.get("tbr") or 0)
                )
                best_audio_size = _size_of(best_audio)
            combined = v_size + best_audio_size
            if combined > 0:
                return round(combined / (1024 * 1024), 2)

    best_size = None
    for f in formats:
        f_size = f.get("filesize") or f.get("filesize_approx")
        if f_size and (best_size is None or f_size > best_size):
            best_size = f_size
    if best_size:
        size_mb = round(best_size / (1024 * 1024), 2)
        max_h = max((f.get("height") or 0 for f in video_formats), default=0)
        # Some manifests expose tiny placeholder sizes for high-res streams.
        if not (max_h >= 720 and size_mb < 5):
            return size_mb

    duration = info.get("duration")
    tbr = info.get("tbr")
    if (not tbr) and video_formats:
        best_video_tbr = max((f.get("tbr") or 0 for f in video_formats), default=0)
        best_audio_tbr = max((f.get("tbr") or 0 for f in audio_formats), default=0)
        tbr = best_video_tbr + best_audio_tbr
    if duration and tbr:
        try:
            size_bytes = float(duration) * float(tbr) * 1000 / 8
            return round(size_bytes / (1024 * 1024), 2)
        except Exception:
            return None

    return None


def _available_format_quality(info):
    video_formats = _video_stream_formats(info)
    if not video_formats:
        # Fallback for extractor variants that omit codec fields but still expose resolution.
        formats = info.get("formats") or []
        video_formats = [f for f in formats if (f.get("height") or f.get("resolution"))]
    exts = {str(f.get("ext") or "").lower() for f in video_formats if f.get("ext")}
    format_labels = []
    if "mp4" in exts:
        format_labels.append("MP4")
    if "webm" in exts:
        format_labels.append("WEBM")
    if video_formats:
        format_labels.append("MKV")

    heights = []
    for f in video_formats:
        h = f.get("height")
        if h:
            heights.append(h)
            continue
        res = str(f.get("resolution") or "")
        if "x" in res:
            try:
                heights.append(int(res.split("x", 1)[1]))
            except Exception:
                pass
        note = str(f.get("format_note") or "").lower()
        fmt_id = str(f.get("format_id") or "")
        if "2160" in note or "4k" in note or "uhd" in note:
            heights.append(2160)
        elif "1440" in note or "2k" in note or "qhd" in note:
            heights.append(1440)
        elif "1080" in note:
            heights.append(1080)
        elif "720" in note or "hd720" in note:
            heights.append(720)
        elif fmt_id in ("22", "136"):
            heights.append(720)
        elif fmt_id in ("137", "248", "299"):
            heights.append(1080)
    max_h = max(heights) if heights else 0
    unique_heights = sorted(list(set(heights)), reverse=True)
    quality_labels = []
    for h in unique_heights:
        if h >= 2160: quality_labels.append(f"{h}p (4K)")
        elif h >= 1440: quality_labels.append(f"{h}p (2K)")
        elif h >= 720: quality_labels.append(f"{h}p (HD)")
        else: quality_labels.append(f"{h}p")

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
    with _YTDLP_LOCK:
        with RenamingYDL(ydl_opts) as ydl:
            ydl.download([url])


def _parse_progress_int(value):
    try:
        return int(float(value))
    except Exception:
        return None


def _download_with_exe(url, ydl_opts, progress_callback=None, pause_check=None, cancel_check=None, legacy=False, minimal=False, oauth2_cb=None):
    exe_path = _find_local_binary("yt-dlp")
    if not exe_path:
        raise RuntimeError("yt-dlp.exe not found")

    cmd = [exe_path, "--newline", "--no-color", "--continue"]

    if ydl_opts.get("no_warnings"):
        cmd.append("--no-warnings")

    def _add_opt(flag, key):
        value = ydl_opts.get(key)
        if value is None:
            return
        cmd.extend([flag, str(value)])

    if not minimal:
        _add_opt("--retries", "retries")
        _add_opt("--fragment-retries", "fragment_retries")
        _add_opt("--file-access-retries", "file_access_retries")
        _add_opt("--concurrent-fragments", "concurrent_fragment_downloads")
        _add_opt("--sleep-interval", "sleep_interval")
        _add_opt("--max-sleep-interval", "max_sleep_interval")
        _add_opt("--socket-timeout", "socket_timeout")

    if ydl_opts.get("ratelimit"):
        cmd.extend(["--limit-rate", str(int(ydl_opts["ratelimit"]))])

    if ydl_opts.get("noplaylist"):
        cmd.append("--no-playlist")
    if "playliststart" in ydl_opts:
        cmd.extend(["--playlist-start", str(ydl_opts["playliststart"])])
    if "playlistend" in ydl_opts:
        cmd.extend(["--playlist-end", str(ydl_opts["playlistend"])])
    if ydl_opts.get("ignoreerrors"):
        cmd.append("--ignore-errors")

    fmt = ydl_opts.get("format")
    if fmt:
        cmd.extend(["-f", fmt])

    outtmpl = ydl_opts.get("outtmpl")
    if outtmpl:
        cmd.extend(["-o", outtmpl])

    merge_fmt = ydl_opts.get("merge_output_format")
    if merge_fmt:
        cmd.extend(["--merge-output-format", merge_fmt])

    ffmpeg_loc = ydl_opts.get("ffmpeg_location")
    if ffmpeg_loc:
        cmd.extend(["--ffmpeg-location", ffmpeg_loc])

    cookiefile = ydl_opts.get("cookiefile")
    if cookiefile:
        cmd.extend(["--cookies", cookiefile])

    browser_auth = ydl_opts.get("cookiesfrombrowser")
    if browser_auth:
        browser_arg = _normalize_browser_auth_for_cli(browser_auth)
        if browser_arg:
            cmd.extend(["--cookies-from-browser", str(browser_arg)])

    proxy = ydl_opts.get("proxy")
    if proxy:
        cmd.extend(["--proxy", str(proxy)])

    # Note: --auth-type oauth2 has been removed; it conflicts with cookie-based
    # authentication and is not needed for standard cookie/browser-auth flows.

    if not minimal:
        extractor_args = ydl_opts.get("extractor_args") or {}
        yt_args = extractor_args.get("youtube") if isinstance(extractor_args, dict) else None
        if isinstance(yt_args, dict):
            client = yt_args.get("player_client")
            if client:
                if isinstance(client, (list, tuple)):
                    client_val = ",".join([str(c) for c in client if c])
                else:
                    client_val = str(client)
                if client_val:
                    cmd.extend(["--extractor-args", f"youtube:player_client={client_val}"])

        http_headers = ydl_opts.get("http_headers") or {}
        user_agent = http_headers.get("User-Agent") or http_headers.get("user-agent")
        if user_agent:
            cmd.extend(["--user-agent", user_agent])
        for name, value in http_headers.items():
            if name.lower() == "user-agent":
                continue
            cmd.extend(["--add-header", f"{name}:{value}"])

    if ydl_opts.get("writesubtitles") or ydl_opts.get("writeautomaticsub"):
        cmd.append("--write-subs")
        if ydl_opts.get("writeautomaticsub"):
            cmd.append("--write-auto-subs")
        if ydl_opts.get("embedsubtitles"):
            cmd.append("--embed-subs")
        subfmt = ydl_opts.get("subtitlesformat")
        if subfmt:
            cmd.extend(["--sub-format", str(subfmt)])
        sublangs = ydl_opts.get("subtitleslangs")
        if sublangs:
            if isinstance(sublangs, (list, tuple)):
                sublangs = ",".join([s for s in sublangs if s])
            cmd.extend(["--sub-langs", str(sublangs)])

    if not legacy:
        cmd.extend([
            "--progress",
            "--progress-template",
            "download:DL:%(progress.downloaded_bytes)s:%(progress.total_bytes)s:%(progress.speed)s:%(progress.total_bytes_estimate)s:%(progress._percent_str)s"
        ])
        cmd.extend([
            "--print",
            "after_move:YTRESULT:%(id)s\t%(title)s\t%(webpage_url)s\t%(thumbnail)s\t%(filepath)s"
        ])
    cmd.append(url)

    def _terminate_process(proc):
        try:
            proc.terminate()
        except Exception:
            pass
        try:
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    results = []
    last_error = ""
    start_ts = time.time()
    popen_kwargs = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.STDOUT,
        "stdin": subprocess.DEVNULL,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "bufsize": 1
    }
    if os.name == 'nt':
        # Add CREATE_NO_WINDOW flag for Windows to suppress console window
        popen_kwargs["creationflags"] = 0x08000000 # subprocess.CREATE_NO_WINDOW

    proc = subprocess.Popen(cmd, **popen_kwargs)
    try:
        while True:
            raw_line = proc.stdout.readline()
            if not raw_line and proc.poll() is not None:
                break
            
            if cancel_check and cancel_check():
                _terminate_process(proc)
                raise DownloadCancelled("DOWNLOAD_CANCELLED")
            if pause_check and pause_check():
                _terminate_process(proc)
                raise DownloadPaused("DOWNLOAD_PAUSED")

            line = (raw_line or "").strip()
            if not line:
                continue
            
            # Log a sample if we haven't seen any DL: lines yet (for debugging)
            # if "download" in line.lower(): _log.debug("RAW_DOWNLOAD_LINE: %s", line)

            if "DL:" in line:
                # Handle cases where DL: might be preceded by [download] 
                payload = line.split("DL:", 1)[1]
                parts = payload.split(":", 5)
                downloaded = _parse_progress_int(parts[0]) if len(parts) > 0 else None
                total = _parse_progress_int(parts[1]) if len(parts) > 1 else None
                speed = _parse_progress_int(parts[2]) if len(parts) > 2 else None
                total_est = _parse_progress_int(parts[3]) if len(parts) > 3 else None
                percent_str = parts[4].strip() if len(parts) > 4 else ""

                if percent_str:
                    import re
                    clean_pct = re.sub(r"[^\d\.]", "", percent_str)
                    if clean_pct:
                        try:
                            percent = min(float(clean_pct), 100.0)
                        except Exception:
                            percent = 0
                    else:
                        percent = 0
                else:
                    if total and downloaded is not None and total > 0:
                        percent = min(downloaded / total * 100, 100)
                    elif total_est and downloaded is not None and total_est > 0:
                        percent = min(downloaded / total_est * 100, 100)
                    else:
                        percent = 0

                if not total:
                    total = total_est

                speed_text = f"{round(speed / 1024, 2)} KB/s" if speed else None
                if progress_callback:
                    try:
                        progress_callback(percent, speed_text, downloaded, total)
                    except Exception:
                        _log.exception("Progress callback failed (exe path)")
                continue

            # Fallback for standard yt-dlp progress output if DL: is missing
            if "[download]" in line and "%" in line:
                import re
                # Match " 10.5% of 100.00MiB at  1.00MiB/s ETA 00:01"
                # Patterns: 10.5% of 100.00MiB, 10.5% of ~100.00MiB
                m = re.search(r"(\d+\.?\d*)\s*%\s+of\s+~?\s*([\d\.]+\s*\w+)\s+at\s+([^\s]+)", line)
                if m:
                    try:
                        percent = float(m.group(1))
                        size_str = m.group(2).strip()
                        speed_text = m.group(3).strip()
                        
                        # Fix speed_text if it has color codes or weird prefixes like ~
                        speed_text = re.sub(r"\x1b\[[0-9;]*m", "", speed_text)
                        if speed_text.startswith("~"): speed_text = speed_text[1:]

                        # Try to parse total size for better UI display
                        total_bytes = None
                        if size_str:
                            try:
                                # Clean size_str: "100.00MiB" -> "100.00", "MiB"
                                num_part = re.search(r"[\d\.]+", size_str)
                                unit_part = re.search(r"[a-zA-Z]+", size_str)
                                if num_part and unit_part:
                                    num = float(num_part.group(0))
                                    unit = unit_part.group(0).lower()
                                    if "ki" in unit: total_bytes = num * 1024
                                    elif "mi" in unit: total_bytes = num * 1024 * 1024
                                    elif "gi" in unit: total_bytes = num * 1024 * 1024 * 1024
                                    elif "k" in unit: total_bytes = num * 1000
                                    elif "m" in unit: total_bytes = num * 1000 * 1000
                                    elif "g" in unit: total_bytes = num * 1000 * 1000 * 1000
                            except Exception: pass

                        downloaded_bytes = None
                        if total_bytes:
                            downloaded_bytes = total_bytes * (percent / 100.0)

                        if progress_callback:
                            progress_callback(percent, speed_text, downloaded_bytes, total_bytes)
                    except Exception:
                        pass
                continue

            if "has already been downloaded" in line:
                if progress_callback:
                    try:
                        progress_callback(100.0, "Done", None, None)
                    except Exception:
                        pass
                continue

            if "google.com/device" in line and "code" in line:
                # E.g., "To give yt-dlp access to your account, go to https://www.google.com/device and enter code XYZ-123"
                if oauth2_cb:
                    try:
                        oauth2_cb(line)
                    except Exception:
                        pass
                continue

            if "YTRESULT:" in line:
                payload = line.split("YTRESULT:", 1)[1]
                parts = payload.split("\t")
                while len(parts) < 5:
                    parts.append("")
                results.append({
                    "id": parts[0] or None,
                    "title": parts[1] or os.path.basename(parts[4] or ""),
                    "url": parts[2] or url,
                    "thumbnail": parts[3] or None,
                    "filepath": parts[4] or ""
                })
                continue

            if "ERROR" in line or "Error" in line:
                import re
                last_error = re.sub(r"\x1b\[[0-9;]*m", "", line).strip()
                # Remove "ERROR: " or "Error: " prefix if present
                if ":" in last_error and (last_error.lower().startswith("error")):
                    last_error = last_error.split(":", 1)[1].strip()
    finally:
        try:
            if proc.stdout:
                proc.stdout.close()
        except Exception:
            pass

    returncode = proc.wait()

    if not results:
        download_dir = ydl_opts.get("_download_dir")
        outtmpl = ydl_opts.get("outtmpl") or ""
        if not download_dir:
            download_dir = os.path.dirname(outtmpl)
            if "%(" in download_dir:
                download_dir = download_dir.split("%(", 1)[0].rstrip("\\/") or download_dir
        if not download_dir:
            download_dir = os.getcwd()
        try:
            candidates = []
            for root, _, files in os.walk(download_dir):
                for name in files:
                    if name.endswith(".part") or name.endswith(".ytdl"):
                        continue
                    path = os.path.join(root, name)
                    try:
                        mtime = os.path.getmtime(path)
                    except Exception:
                        continue
                    if mtime >= start_ts - 2:
                        candidates.append((mtime, path))
            candidates.sort(reverse=True)
            for _, path in candidates:
                base = os.path.basename(path)
                title = os.path.splitext(base)[0]
                results.append({
                    "id": None,
                    "title": title,
                    "url": url,
                    "thumbnail": None,
                    "filepath": path
                })
        except Exception:
            _log.exception("Fallback result scan failed for %s", download_dir)

    if returncode != 0:
        # ── Exit code 2: format or option error ──
        # Covers both "unknown option" (needs legacy retry) and format-related
        # failures ("requested format not available").  Let the outer
        # download_video loop handle format fallback by raising.
        if (not legacy) and returncode == 2:
            err_lower = (last_error or "").lower()
            if not last_error or "unknown option" in err_lower:
                _log.warning("yt-dlp exit code 2 (unknown option); retrying with legacy flags.")
                return _download_with_exe(
                    url,
                    ydl_opts,
                    progress_callback=progress_callback,
                    pause_check=pause_check,
                    cancel_check=cancel_check,
                    legacy=True,
                    minimal=minimal,
                    oauth2_cb=oauth2_cb
                )
            # Format-related exit code 2: let it propagate as a RuntimeError
            # so the outer loop can fall back to a safer format string.
            _log.warning(
                "yt-dlp exit code 2 (format/quality issue): %s",
                last_error
            )

        if not results:
            if ydl_opts.get("cookiesfrombrowser") and _is_cookie_error(last_error):
                raw_browser = ydl_opts.get("cookiesfrombrowser")
                browser_name = str(raw_browser[0] if isinstance(raw_browser, (list, tuple)) else raw_browser).lower()
                _log.warning("Cookie lock detected in downloader for %s", browser_name)
                raise CookieLockError(browser_name, last_error or "Database locked")
            raise RuntimeError(last_error or f"yt-dlp exited with code {returncode}")
        else:
            _log.warning("yt-dlp exited with code %s but results were obtained. Ignoring error: %s", returncode, last_error)

    return results


class _SilentLogger:
    def __init__(self):
        self.warnings = []
        self.errors = []

    def debug(self, msg):
        pass

    def warning(self, msg):
        self.warnings.append(str(msg))

    def error(self, msg):
        self.errors.append(str(msg))


# Patterns that indicate a cookie decryption or access failure
_COOKIE_FAIL_MARKERS = (
    "failed to decrypt cookie",
    "secretstorage",
    "could not decrypt",
    "cannot decrypt",
    "dbus",
    "secretservice",
    "no module named 'secretstorage'",
    "no module named secretstorage",
)


def _get_cookie_warning(base_opts):
    """Return the first cookie-related warning captured by the _SilentLogger, or None."""
    logger = base_opts.get("logger")
    if not (logger and hasattr(logger, "warnings")):
        return None
    for w in logger.warnings:
        w_lower = w.lower()
        if any(marker in w_lower for marker in _COOKIE_FAIL_MARKERS):
            return w
    for w in getattr(logger, "errors", []):
        w_lower = w.lower()
        if any(marker in w_lower for marker in _COOKIE_FAIL_MARKERS):
            return w
    return None


def _check_ydl_cookie_warnings(ydl, base_opts):
    """Pull any cookie warnings out of a live yt-dlp YoutubeDL instance
    and store them in our _SilentLogger so they can be inspected later."""
    logger = base_opts.get("logger")
    if not (logger and hasattr(logger, "warnings")):
        return
    # yt-dlp stores its own _warning_list on some versions
    for w in getattr(ydl, "_warning_list", []) or []:
        w_str = str(w)
        if any(marker in w_str.lower() for marker in _COOKIE_FAIL_MARKERS):
            logger.warnings.append(w_str)


def _cookiefile_path(cookiefile=None):
    """Resolve *cookiefile* to an absolute path, validating it contains real cookies.

    Returns None (do not pass cookies) if:
    - path is empty / None
    - file does not exist on disk
    - file contains no actual cookie rows (e.g. header-only file)
    """
    if not cookiefile:
        return None
    if not os.path.exists(cookiefile):
        _log.warning("Cookie file specified but not found on disk: %s", cookiefile)
        return None
    # Validate the file actually has cookie rows (not just the Netscape header).
    # A real Netscape cookies.txt row has 7 tab-separated fields.
    has_rows = False
    try:
        with open(cookiefile, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                if len(stripped.split("\t")) >= 7:
                    has_rows = True
                    break
    except OSError:
        pass
    if not has_rows:
        _log.warning(
            "Cookie file %s exists but contains no valid cookie rows — skipping",
            cookiefile
        )
        return None
    try:
        size = os.path.getsize(cookiefile)
    except OSError:
        size = -1
    _log.info("Cookie file resolved: %s (%d bytes)", cookiefile, size)
    return cookiefile


def build_base_options(timeout=10, noplaylist=True, skip_download=True, logger=None):
    return {
        "quiet": True,
        "noplaylist": noplaylist,
        "skip_download": skip_download,
        "socket_timeout": timeout,
        "no_warnings": True,
        "logger": logger or _SilentLogger(),
        "retries": 8,
        "fragment_retries": 8,
        "file_access_retries": 3,
        "concurrent_fragment_downloads": 1,
        "sleep_interval": 1,
        "max_sleep_interval": 4,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        },
    }


def apply_normal_mode_options(opts):
    opts.pop("cookiefile", None)
    opts.pop("cookiesfrombrowser", None)
    opts.pop("use_oauth2", None)
    return opts


_KNOWN_BROWSER_AUTH = {
    "auto",
    "chrome",
    "edge",
    "firefox",
    "brave",
    "opera",
    "chromium",
}


def _normalize_browser_auth_for_api(value):
    if not value:
        return None
    if isinstance(value, (list, tuple)):
        items = [v for v in value if v]
        if not items:
            return None
        if all(isinstance(v, str) and v.strip().lower() in _KNOWN_BROWSER_AUTH for v in items) and len(items) > 1:
            return (str(items[0]).strip(),)
        parts = []
        for v in items:
            if isinstance(v, str):
                v = v.strip()
                if v.lower().startswith("browser:"):
                    v = v.split("browser:", 1)[1]
                parts.append(v)
            else:
                parts.append(str(v))
        parts = [p for p in parts if p]
        if not parts:
            return None
        return tuple(parts[:4])
    if isinstance(value, str):
        val = value.strip()
        if val.lower().startswith("browser:"):
            val = val.split("browser:", 1)[1]
        parts = [p for p in val.split(":") if p]
        if not parts:
            return None
        return tuple(parts[:4])
    return None


def _normalize_browser_auth_for_cli(value):
    if not value:
        return None
    if isinstance(value, (list, tuple)):
        items = [v for v in value if v]
        if not items:
            return None
        if all(isinstance(v, str) and v.strip().lower() in _KNOWN_BROWSER_AUTH for v in items) and len(items) > 1:
            return str(items[0]).strip()
        parts = []
        for v in items:
            if isinstance(v, str):
                v = v.strip()
                if v.lower().startswith("browser:"):
                    v = v.split("browser:", 1)[1]
                parts.append(v)
            else:
                parts.append(str(v))
        parts = [p for p in parts if p]
        return ":".join(parts) if parts else None
    if isinstance(value, str):
        val = value.strip()
        if val.lower().startswith("browser:"):
            val = val.split("browser:", 1)[1]
        return val or None
    return str(value)


def apply_restricted_mode_options(opts, cookiefile=None, browser_auth=None):
    cookie_path = _cookiefile_path(cookiefile)
    if cookie_path:
        opts["cookiefile"] = cookie_path
    if browser_auth:
        normalized = _normalize_browser_auth_for_api(browser_auth)
        if normalized:
            opts["cookiesfrombrowser"] = normalized
    return opts


def apply_client_fallback(opts, client):
    """Configure yt-dlp's YouTube player client.

    Pass None to use yt-dlp's own default client selection, which is the most
    up-to-date choice and handles Proof-of-Origin (PO) token negotiation
    internally.  Pass a specific client name (e.g. 'ios', 'android') to force
    a particular client that is known to work without PO tokens.
    """
    if client is None:
        # Remove any previous override — let yt-dlp choose its default.
        opts.pop("extractor_args", None)
    else:
        opts["extractor_args"] = {"youtube": {"player_client": client}}
    return opts


def _client_fallbacks():
    """Ordered list of YouTube player clients to try.

    None  = yt-dlp's own default (handles PO tokens, always tried first)
    ios   = iOS player API — no PO token required
    android = Android player API — no PO token required
    tv_embedded = TV embedded player — no PO token required

    The 'web' client is intentionally omitted: recent YouTube changes
    require PO tokens for web-client anonymous requests, causing
    'sign-in required' errors for public videos.
    """
    return [None, "ios", "android", "tv_embedded"]


def _iter_auth_attempts(cookiefile=None, browser_auth=None, allow_fallback=True, prefer_no_auth=False):
    attempts = []
    if allow_fallback and prefer_no_auth:
        attempts.append(("none", None))
    cookie_path = _cookiefile_path(cookiefile)
    if cookie_path:
        attempts.append(("cookiefile", cookie_path))
    if browser_auth:
        if isinstance(browser_auth, (list, tuple)):
            for entry in browser_auth:
                if entry:
                    attempts.append(("browser", entry))
        else:
            attempts.append(("browser", browser_auth))
    if allow_fallback and not prefer_no_auth:
        attempts.append(("none", None))
    seen = set()
    unique = []
    for mode, value in attempts:
        key = (mode, str(value))
        if key in seen:
            continue
        seen.add(key)
        unique.append((mode, value))
    return unique


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
        "could not find chrome cookies database",
        "CookieLoadError",
        "failed to load cookies",
        "Failed to decrypt with DPAPI",
        "could not find firefox cookies database",
        "Could not copy Edge cookie database",
        "Permission denied",
        "database is locked",
        "[Errno 13]",
    )
    return any(m.lower() in str(msg).lower() for m in cookie_markers)


def _requires_auth(msg):
    """Return True ONLY when the error definitively indicates authentication is needed.

    Deliberately narrow: generic errors like 'unavailable' or 'watch on youtube'
    can arise from rate-limiting, invalid player clients, geo-blocks, etc. — and
    must NOT trigger an automatic switch to cookie-auth for public videos.
    """
    lowered = (msg or "").lower()
    definitive_markers = (
        "please sign in",
        "requires sign-in",
        "requires login",
        "sign in to confirm your age",
        "confirm your age",
        "members only",
        "this video is private",
        "account is required",
    )
    return any(m in lowered for m in definitive_markers)


def _extract_info_with_cookies(url, base_opts, cookiefile=None):
    ytdlp = _get_yt_dlp()
    cookiefile = _cookiefile_path(cookiefile)
    last_err = None
    best_info = None
    best_score = (-1, -1, -1)

    attempts = []
    if cookiefile:
        attempts.append(("cookiefile", cookiefile))
    attempts.append(("none", None))

    for mode, value in attempts:
        ydl_opts = dict(base_opts)
        if mode == "cookiefile":
            ydl_opts["cookiefile"] = value
        try:
            with _YTDLP_LOCK:
                with ytdlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
            score = _info_score(info)
            if best_info is None or score > best_score:
                best_info = info
                best_score = score
            if best_score[0] >= 3 and best_score[1] >= 720:
                return best_info
        except Exception as e:
            last_err = e
            continue

    if best_info is not None:
        return best_info
    if last_err:
        raise last_err


def _build_format_candidates(quality, container):
    height_map = {
        "720p": 720,
        "1080p": 1080,
        "2K": 1440,
        "4K": 2160
    }

    h = height_map.get(quality)
    if h:
        video_cap = f"[height<={h}]"
        prog_cap = f"[height<={h}]"
    else:
        video_cap = ""
        prog_cap = ""

    split_best = f"bestvideo*{video_cap}+bestaudio"
    split_mp4 = f"bestvideo*[ext=mp4]{video_cap}+bestaudio[ext=m4a]"
    split_webm = f"bestvideo*[ext=webm]{video_cap}+bestaudio[ext=webm]"
    prog_mp4 = f"best[ext=mp4]{prog_cap}"
    prog_webm = f"best[ext=webm]{prog_cap}"
    prog_best = f"best{prog_cap}"
    any_split = f"bestvideo{video_cap}+bestaudio"
    any_best = "best"

    container = (container or "auto").lower()

    if container == "auto":
        return [
            (split_mp4, "mp4"),
            (split_best, "mkv"),
            (prog_mp4, None),
            (prog_best, None),
            (any_split, None),
            (any_best, None),
        ]
    if container == "mp4":
        return [
            (split_mp4, "mp4"),
            (prog_mp4, None),
            (split_best, "mkv"),
            (prog_best, None),
            (any_best, None),
        ]
    if container == "webm":
        return [
            (split_webm, "webm"),
            (prog_webm, None),
            (split_best, "mkv"),
            (prog_best, None),
            (any_best, None),
        ]
    if container == "mkv":
        return [
            (split_best, "mkv"),
            (prog_best, None),
            (any_best, None),
        ]
    return [
        (split_best, "mkv"),
        (prog_best, None),
        (any_best, None),
    ]


def download_video(url,
                   quality,
                   progress_callback,
                   cookiefile=None,
                   browser_auth=None,
                   download_playlist=False,
                   playlist_start=1,
                   playlist_end=0,
                   playlist_batch_size=0,
                   skip_unavailable=True,
                   download_dir=None,
                   container="mp4",
                   subtitles=False,
                   subtitles_langs=None,
                   embed_subtitles=True,
                   rate_limit=None,
                   proxy=None,
                   pause_check=None,
                   cancel_check=None,
                   oauth2_cb=None):
    if not is_valid_youtube_url(url):
        raise ValueError("Invalid URL")

    download_dir = download_dir or _default_download_dir()
    _ensure_download_dir(download_dir)

    playlist_mode = download_playlist and _is_playlist_url(url)
    url = normalize_youtube_url(url, keep_playlist=playlist_mode)
    ytdlp_exe = _find_local_binary("yt-dlp")
    _log.info(
        "download_video: url=%s quality=%s cookiefile=%s browser_auth=%s",
        url, quality, cookiefile or "(none)", browser_auth or "(none)"
    )
    if ytdlp_exe:
        _log.info("yt-dlp.exe detected at %s (cwd=%s); using subprocess download path.", ytdlp_exe, os.getcwd())
    else:
        _log.warning("yt-dlp.exe not found; subprocess download unavailable.")
        raise NotReadyError(
            "yt-dlp is still setting up. Please wait a moment and try again.\n"
            "If this keeps happening, restart the app."
        )

    try:
        playlist_start = int(playlist_start or 1)
    except Exception:
        playlist_start = 1
    if playlist_start < 1:
        playlist_start = 1
    try:
        playlist_end = int(playlist_end or 0)
    except Exception:
        playlist_end = 0
    try:
        playlist_batch_size = int(playlist_batch_size or 0)
    except Exception:
        playlist_batch_size = 0
    if playlist_batch_size < 0:
        playlist_batch_size = 0
    if playlist_mode and playlist_batch_size > 0:
        computed_end = playlist_start + playlist_batch_size - 1
        if playlist_end <= 0 or playlist_end > computed_end:
            playlist_end = computed_end

    # Include resolution in filename so different qualities produce different files.
    # yt-dlp substitutes %(height)s with the actual video height (e.g. 1080, 720).
    # For audio-only or unknown-resolution cases it falls back to just the title.
    outtmpl = os.path.join(download_dir, "%(title)s [%(height)sp].%(ext)s")
    if playlist_mode:
        outtmpl = os.path.join(
            download_dir,
            "%(playlist_title)s",
            "%(playlist_index)02d - %(title)s [%(height)sp].%(ext)s"
        )

    base_opts = build_base_options(
        timeout=8,
        noplaylist=not playlist_mode,
        skip_download=False,
        logger=_SilentLogger()
    )
    base_opts.update({
        "outtmpl": outtmpl,
        "nopart": False,
        "continuedl": True,
        "noprogress": False,
        "_download_dir": download_dir,
    })
    if playlist_mode:
        base_opts["playliststart"] = playlist_start
        if playlist_end and playlist_end >= playlist_start:
            base_opts["playlistend"] = playlist_end
        if skip_unavailable:
            base_opts["ignoreerrors"] = "only_download"
    if rate_limit and rate_limit > 0:
        base_opts["ratelimit"] = int(rate_limit)

    if proxy:
        base_opts["proxy"] = proxy

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

    ffmpeg_path = _find_local_binary("ffmpeg")
    if ffmpeg_path:
        base_opts["ffmpeg_location"] = ffmpeg_path

    cookiefile = _cookiefile_path(cookiefile)
    if browser_auth:
        if isinstance(browser_auth, (list, tuple)):
            cleaned = []
            for entry in browser_auth:
                if isinstance(entry, str) and entry.lower().startswith("browser:"):
                    entry = entry.split("browser:", 1)[1]
                if entry:
                    cleaned.append(entry)
            browser_auth = cleaned
        elif isinstance(browser_auth, str) and browser_auth.lower().startswith("browser:"):
            browser_auth = browser_auth.split("browser:", 1)[1]

    apply_normal_mode_options(base_opts)
    restricted_opts = None
    if cookiefile or browser_auth:
        restricted_opts = dict(base_opts)
        apply_restricted_mode_options(restricted_opts, cookiefile=cookiefile, browser_auth=browser_auth)
        # NOTE: do NOT set use_oauth2 here — OAuth2 is an entirely separate flow
        # and conflicts with cookie-based auth; it breaks downloads for public videos.

    container = (container or "auto").lower()
    merge_fmt = None
    if container in ("mp4", "webm", "mkv"):
        merge_fmt = container

    def _resolve_format_string(quality_val, container_val):
        q = str(quality_val).lower()
        if "auto" in q:
             if container_val == "mp4":
                 return "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
             elif container_val == "webm":
                 return "bestvideo[ext=webm]+bestaudio[ext=webm]/best[ext=webm]/best"
             return "bestvideo+bestaudio/best"

        # Extract height from labels like "1080p (HD)" or "720p"
        import re
        m = re.search(r"(\d+)", q)
        h = m.group(1) if m else "1080"

        # Use height<= (not height=) so we pick the best available quality
        # at or below the requested resolution instead of failing on exact match.
        if container_val == "mp4":
            return (
                f"bestvideo[height<={h}][ext=mp4]+bestaudio[ext=m4a]"
                f"/best[height<={h}][ext=mp4]"
                f"/bestvideo[height<={h}]+bestaudio"
                f"/best[height<={h}]"
                f"/best"
            )
        elif container_val == "webm":
            return (
                f"bestvideo[height<={h}][ext=webm]+bestaudio[ext=webm]"
                f"/best[height<={h}][ext=webm]"
                f"/bestvideo[height<={h}]+bestaudio"
                f"/best[height<={h}]"
                f"/best"
            )

        return (
            f"bestvideo[height<={h}]+bestaudio"
            f"/best[height<={h}]"
            f"/best"
        )

    fmt_requested = _resolve_format_string(quality, container)
    fmt_best = _resolve_format_string("auto", container)
    # Ultimate safe fallback — no container or height constraints at all.
    fmt_safe = "bestvideo+bestaudio/best"

    attempts = []
    if "auto" not in str(quality).lower():
        attempts.append((str(quality), fmt_requested))
    attempts.append(("best", fmt_best))
    # Only add the safe fallback if it's different from what we already have
    if fmt_safe != fmt_best:
        attempts.append(("safe", fmt_safe))

    last_err = None
    last_non_cookie_err = None
    auth_sets = [("normal", base_opts)]
    if restricted_opts is not None:
        auth_sets.append(("restricted", restricted_opts))

    _skip_to_restricted = False
    for auth_label, opts_template in auth_sets:
        if _skip_to_restricted and auth_label == "normal":
            continue
        for client in _client_fallbacks():
            if _skip_to_restricted:
                _skip_to_restricted = False  # consumed: proceed with restricted
            for label, fmt in attempts:
                ydl_opts = dict(opts_template)
                apply_client_fallback(ydl_opts, client)
                ydl_opts["format"] = fmt
                if merge_fmt:
                    ydl_opts["merge_output_format"] = merge_fmt
                minimal = auth_label == "normal"
                _log.info("Subprocess download attempt (%s/%s/%s): %s", auth_label, client or "default", label, fmt)
                try:
                    results = _download_with_exe(
                        url,
                        ydl_opts,
                        progress_callback=progress_callback,
                        pause_check=pause_check,
                        cancel_check=cancel_check,
                        minimal=minimal,
                        oauth2_cb=oauth2_cb
                    )
                    return results or []
                except Exception as e:
                    if isinstance(e, (DownloadPaused, DownloadCancelled, CookieLockError)):
                        raise
                    err_str = str(e)
                    is_cookie_err = _is_cookie_error(err_str)
                    if not is_cookie_err:
                        last_non_cookie_err = e
                    last_err = e

                    # ── Classify the error for better logging ──
                    if _requires_auth(err_str):
                        _log.warning(
                            "Auth error during %s attempt (%s/%s): %s — switching to restricted auth",
                            auth_label, client or "default", label, err_str
                        )
                        if auth_label == "normal" and restricted_opts is not None:
                            _skip_to_restricted = True
                            break  # break format loop → break client loop → skip to restricted
                    elif is_cookie_err:
                        _log.warning(
                            "Cookie error during %s/%s/%s: %s",
                            auth_label, client or "default", label, err_str
                        )
                        if auth_label == "restricted":
                            break  # try next client
                    else:
                        _log.warning(
                            "Download attempt %s/%s/%s failed: %s",
                            auth_label, client or "default", label, err_str
                        )
                    continue
            if _skip_to_restricted:
                break  # break client loop to move to restricted auth_set

    if last_non_cookie_err:
        raise last_non_cookie_err
    if last_err:
        raise last_err
    return []
