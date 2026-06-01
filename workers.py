import hashlib
import os
import shutil
from datetime import datetime, UTC

from PySide6.QtCore import QObject, Signal
from requests import HTTPError

from downloader import (
    download_video,
    get_video_info,
    get_playlist_entries,
    DownloadPaused,
    DownloadCancelled,
    CookieLockError,
    NotReadyError,
)
from history_manager import save_history
from app_config import THUMB_DIR, ensure_dir, local_tmp_dir
from core.security import assert_https_url, safe_extract_zip
from logging_utils import get_logger
from net_utils import request_with_retry, get_bytes
from updates.manager import TRUSTED_UPDATE_HOSTS, validate_update_url, verify_update_file

_log = get_logger()

class UpdateWorker(QObject):
    update_available = Signal(object)
    update_required = Signal(object)
    no_update = Signal()
    error = Signal(str)
    finished = Signal()

    def __init__(self, manifest_url, current_version, extract_update_info, compare_versions):
        super().__init__()
        self.manifest_url = manifest_url
        self.current_version = current_version
        self._extract_update_info = extract_update_info
        self._compare_versions = compare_versions
        self._cancel_requested = False

    def request_cancel(self):
        self._cancel_requested = True

    def run(self):
        try:
            if not self.manifest_url:
                self.no_update.emit()
                return
            if self._cancel_requested:
                return
            validate_update_url(self.manifest_url)
            resp = request_with_retry("GET", self.manifest_url, timeout=10)
            if self._cancel_requested:
                return
            data = resp.json()
            info = self._extract_update_info(data, self.manifest_url)
            latest = info.get("latest_version") or ""
            if not latest:
                self.error.emit("Update manifest is missing latest version.")
                return

            cmp_latest = self._compare_versions(latest, self.current_version)
            if cmp_latest <= 0:
                self.no_update.emit()
                return

            min_required = info.get("min_required_version") or latest
            if self._compare_versions(min_required, self.current_version) > 0:
                self.update_required.emit(info)
            else:
                self.update_available.emit(info)
        except Exception as e:
            if isinstance(e, HTTPError):
                code = getattr(getattr(e, "response", None), "status_code", None)
                if code == 404:
                    _log.info("Update check endpoint returned 404; release metadata is not accessible.")
                else:
                    _log.warning("Update check failed for %s (HTTP %s)", self.manifest_url, code)
            else:
                _log.exception("Update check failed for %s", self.manifest_url)
            self.error.emit(str(e))
        finally:
            self.finished.emit()


class UpdateDownloadWorker(QObject):
    progress = Signal(int)
    completed = Signal(str)
    error = Signal(str)
    finished = Signal()

    def __init__(self, url, dest_path, expected_sha256=""):
        super().__init__()
        self.url = url
        self.dest_path = dest_path
        self.expected_sha256 = (expected_sha256 or "").lower()
        self._cancel_requested = False

    def request_cancel(self):
        self._cancel_requested = True

    def run(self):
        tmp_path = self.dest_path + ".tmp"
        try:
            assert_https_url(self.url, allowed_hosts=TRUSTED_UPDATE_HOSTS)
            if not self.expected_sha256:
                raise RuntimeError("Update hash is missing. Download blocked.")
            resp = request_with_retry("GET", self.url, stream=True, timeout=20)
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            with open(tmp_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if self._cancel_requested:
                        try:
                            resp.close()
                        except Exception:
                            pass
                        raise RuntimeError("Update download cancelled.")
                    if not chunk:
                        continue
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        self.progress.emit(int(downloaded * 100 / total))
            verify_update_file(tmp_path, self.expected_sha256)
            os.replace(tmp_path, self.dest_path)
            self.completed.emit(self.dest_path)
        except Exception as e:
            _log.exception("Update download failed for %s", self.url)
            self.error.emit(str(e))
        finally:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
            self.finished.emit()


class FetchWorker(QObject):
    info_ready = Signal(str, object, object, object, object, object)
    error = Signal(str)
    cookie_lock = Signal(str, str)
    finished = Signal()

    def __init__(self, url, cookie_file, browser_auth=None, allow_playlist=False, quality=None, container="auto"):
        super().__init__()
        self.url = url
        self.cookie_file = cookie_file
        self.browser_auth = browser_auth
        self.allow_playlist = allow_playlist
        self.quality = quality
        self.container = container
        self._cancel_requested = False

    def request_cancel(self):
        self._cancel_requested = True

    def run(self):
        import time
        from downloader import (
            _get_yt_dlp, _cookiefile_path, _iter_auth_attempts, _client_fallbacks,
            apply_restricted_mode_options, apply_normal_mode_options, apply_client_fallback,
            _prepare_runtime_cookiefile, _restore_runtime_cookiefile, _cleanup_runtime_cookiefile,
            _check_ydl_cookie_warnings, CookieLockError, _info_score, _estimate_size_mb,
            _available_format_quality, _available_subtitles, _is_playlist_url, normalize_youtube_url,
            build_base_options, _FORMAT_CACHE, _FORMAT_CACHE_LOCK
        )


        print(f"[Analyze] Worker started for URL: {self.url}")
        try:
            if self._cancel_requested:
                print("[Analyze] Cancel requested before starting")
                return

            playlist_mode = self.allow_playlist and _is_playlist_url(self.url)
            url = normalize_youtube_url(self.url, keep_playlist=playlist_mode)

            base_opts = build_base_options(
                timeout=10,
                noplaylist=not playlist_mode,
                skip_download=True,
                logger=None
            )

            if playlist_mode:
                base_opts["extract_flat"] = "in_playlist"

            print(f"[Analyze] yt-dlp extraction started")
            
            started_at = time.time()
            max_probe_seconds = 45
            ytdlp = _get_yt_dlp()
            best_info = None
            best_score = (-1, -1, -1)
            last_err = None
            lock_err = None

            has_auth = bool(_cookiefile_path(self.cookie_file, require_auth=True) or self.browser_auth)
            auth_attempts = _iter_auth_attempts(
                self.cookie_file,
                self.browser_auth,
                allow_fallback=True,
                prefer_no_auth=not has_auth
            )
            for mode, value in auth_attempts:
                if self._cancel_requested:
                    print("[Analyze] Cancel requested during auth loop")
                    return
                if (time.time() - started_at) >= max_probe_seconds:
                    break
                for client in _client_fallbacks(authenticated=(mode != "none")):
                    if self._cancel_requested:
                        print("[Analyze] Cancel requested during client loop")
                        return
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
                        "Info extract attempt (lock-free): client=%s auth=%s",
                        client or "default",
                        auth_label,
                    )
                    runtime_cookie = None
                    try:
                        runtime_cookie = _prepare_runtime_cookiefile(opts)
                        with ytdlp.YoutubeDL(opts) as ydl:
                            info = ydl.extract_info(url, download=False)
                            _check_ydl_cookie_warnings(ydl, base_opts)
                        
                        score = _info_score(info)
                        if best_info is None or score > best_score:
                            best_info = info
                            best_score = score
                        if best_score[0] >= 3 and best_score[1] >= 720:
                            break
                    except Exception as e:
                        import traceback
                        tb = traceback.format_exc()
                        err_str = str(e).lower()
                        if mode == "browser" and ("could not find" in err_str and "cookies database" in err_str):
                            continue
                        if "PermissionError" in tb or "[Errno 13]" in tb or "Could not copy" in tb:
                            if mode == "browser":
                                lock_err = CookieLockError(value, str(e))
                                continue
                        last_err = e
                    finally:
                        _restore_runtime_cookiefile(opts)
                        _cleanup_runtime_cookiefile(runtime_cookie)
                else:
                    continue
                break

            if best_info is None:
                if lock_err:
                    raise lock_err
                if last_err:
                    raise last_err
                raise RuntimeError("Failed to extract video info")

            info = best_info
            
            if self._cancel_requested:
                print("[Analyze] Cancel requested after extraction")
                return

            print(f"[Analyze] yt-dlp extraction finished, info keys: {list(info.keys())[:5]}")

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

                available_formats = []
                available_qualities = []
                available_subtitles = []
                size_mb = "Unknown"
            else:
                title = info.get("title", "Unknown")
                size_mb = _estimate_size_mb(info)
                if size_mb is None:
                    size_mb = "Unknown"
                thumbnail = info.get("thumbnail")

                cache_key = info.get("id") or normalize_youtube_url(self.url, keep_playlist=playlist_mode)
                with _FORMAT_CACHE_LOCK:
                    cached = _FORMAT_CACHE.get(cache_key)
                if cached:
                    available_formats, available_qualities = cached
                else:
                    available_formats, available_qualities = _available_format_quality(info)
                    with _FORMAT_CACHE_LOCK:
                        _FORMAT_CACHE[cache_key] = (available_formats, available_qualities)
                available_subtitles = _available_subtitles(info)

            thumb_bytes = None
            if thumbnail:
                try:
                    thumb_bytes = get_bytes(
                        thumbnail,
                        timeout=10,
                        retries=2,
                        max_bytes=5 * 1024 * 1024,
                        allowed_content_types={"image/jpeg", "image/png", "image/webp"},
                    )
                except Exception:
                    _log.warning("Thumbnail fetch failed for %s", thumbnail)
                    thumb_bytes = None

            if self._cancel_requested:
                print("[Analyze] Cancel requested before emitting result")
                return

            print(f"[Analyze] result signal emitting")
            self.info_ready.emit(
                title,
                size_mb,
                thumb_bytes,
                available_formats,
                available_qualities,
                available_subtitles
            )
            print(f"[Analyze] result emitted")

        except CookieLockError as e:
            print(f"[Analyze] cookie lock exception: {e}")
            self.cookie_lock.emit(e.browser_name, str(e))
        except Exception as e:
            print(f"[Analyze] error signal emitting: {e}")
            _log.exception("Fetch info failed for %s", self.url)
            self.error.emit(str(e))
        finally:
            self.finished.emit()


class PlaylistWorker(QObject):
    completed = Signal(object)
    error = Signal(str)
    cookie_lock = Signal(str, str)
    finished = Signal()

    def __init__(self, url, cookie_file, browser_auth=None, max_items=0):
        super().__init__()
        self.url = url
        self.cookie_file = cookie_file
        self.browser_auth = browser_auth
        self.max_items = max_items
        self._cancel_requested = False

    def request_cancel(self):
        self._cancel_requested = True

    def run(self):
        try:
            if self._cancel_requested:
                return
            info = get_playlist_entries(
                self.url,
                cookiefile=self.cookie_file,
                browser_auth=self.browser_auth,
                max_items=self.max_items
            )
            if self._cancel_requested:
                return
            self.completed.emit(info)
        except CookieLockError as e:
            self.cookie_lock.emit(e.browser_name, str(e))
        except Exception as e:
            _log.exception("Playlist fetch failed for %s", self.url)
            self.error.emit(str(e))
        finally:
            self.finished.emit()


class DownloadWorker(QObject):
    progress = Signal(str, float, object, object, object)
    oauth2_prompt = Signal(str, str)
    error = Signal(str, str)
    cookie_lock = Signal(str, str, str) # task_id, browser_name, message
    completed = Signal(str, list)
    paused = Signal(str)
    finished = Signal()

    def __init__(self,
                 task_id,
                 url,
                 quality,
                 cookie_file,
                 browser_auth,
                 download_dir,
                 download_playlist=False,
                 playlist_start=1,
                 playlist_end=0,
                 playlist_batch_size=0,
                 skip_unavailable=True,
                 container="mp4",
                 subtitles=False,
                 subtitles_langs=None,
                 embed_subtitles=True,
                 rate_limit=None,
                 proxy=None):
        super().__init__()
        self.task_id = task_id
        self.url = url
        self.quality = quality
        self.cookie_file = cookie_file
        self.browser_auth = browser_auth
        self.download_dir = download_dir
        self.download_playlist = download_playlist
        self.playlist_start = playlist_start
        self.playlist_end = playlist_end
        self.playlist_batch_size = playlist_batch_size
        self.skip_unavailable = skip_unavailable
        self.container = container
        self.subtitles = subtitles
        self.subtitles_langs = subtitles_langs
        self.embed_subtitles = embed_subtitles
        self.rate_limit = rate_limit
        self.proxy = proxy
        self._pause_requested = False
        self._cancel_requested = False

    def request_pause(self):
        self._pause_requested = True

    def request_cancel(self):
        self._cancel_requested = True

    def _save_thumbnail(self, thumb_url, video_id=None):
        if not thumb_url:
            return ""
        ensure_dir(THUMB_DIR)
        name = video_id or hashlib.md5(thumb_url.encode("utf-8", errors="ignore")).hexdigest()
        thumb_path = os.path.join(THUMB_DIR, f"{name}.jpg")
        try:
            content = get_bytes(
                thumb_url,
                timeout=10,
                retries=2,
                max_bytes=5 * 1024 * 1024,
                allowed_content_types={"image/jpeg", "image/png", "image/webp"},
            )
            with open(thumb_path, "wb") as f:
                f.write(content)
            return thumb_path
        except Exception:
            _log.warning("Thumbnail save failed for %s", thumb_url)
            return ""

    def run(self):
        try:
            def progress_cb(percent, speed=None, downloaded=None, total=None):
                if self._cancel_requested:
                    raise DownloadCancelled("DOWNLOAD_CANCELLED")
                try:
                    self.progress.emit(self.task_id, percent, speed, downloaded, total)
                except Exception:
                    _log.exception("Progress emit failed for %s", self.url)

            def oauth2_cb(msg):
                try:
                    self.oauth2_prompt.emit(self.task_id, msg)
                except Exception:
                    pass

            results = download_video(
                self.url,
                self.quality,
                progress_cb,
                cookiefile=self.cookie_file,
                browser_auth=self.browser_auth,
                download_playlist=self.download_playlist,
                playlist_start=self.playlist_start,
                playlist_end=self.playlist_end,
                playlist_batch_size=self.playlist_batch_size,
                skip_unavailable=self.skip_unavailable,
                download_dir=self.download_dir,
                container=self.container,
                subtitles=self.subtitles,
                subtitles_langs=self.subtitles_langs,
                embed_subtitles=self.embed_subtitles,
                rate_limit=self.rate_limit,
                proxy=self.proxy,
                pause_check=lambda: self._pause_requested,
                cancel_check=lambda: self._cancel_requested,
                oauth2_cb=oauth2_cb
            ) or []

            if self._cancel_requested:
                return

            saved_items = []
            for item in results:
                thumb_path = self._save_thumbnail(
                    item.get("thumbnail"),
                    item.get("id")
                )
                filepath = (item.get("filepath") or "").strip()
                if not filepath:
                    continue
                history_item = {
                    "title": item.get("title") or "Unknown",
                    "url": item.get("url") or self.url,
                    "filepath": filepath,
                    "thumb_path": thumb_path,
                    "added_at": datetime.now(UTC).isoformat()
                }
                save_history(history_item)
                saved_items.append(history_item)

            self.completed.emit(self.task_id, saved_items)
        except BaseException as e:
            if isinstance(e, CookieLockError):
                self.cookie_lock.emit(self.task_id, e.browser_name, str(e))
                return
            if isinstance(e, NotReadyError):
                self.error.emit(self.task_id, str(e))
                return
            msg = str(e)
            if isinstance(e, DownloadPaused) or "DOWNLOAD_PAUSED" in msg:
                self.paused.emit(self.task_id)
                return
            if isinstance(e, DownloadCancelled) or "DOWNLOAD_CANCELLED" in msg:
                return
            import traceback
            tb = traceback.format_exc()
            _log.exception("Download failed for %s", self.url)
            self.error.emit(self.task_id, tb)
        finally:
            self.finished.emit()


class AnalyzeWorker(QObject):
    result = Signal(dict)
    error = Signal(str)
    cookie_lock = Signal(str, str)
    finished = Signal()

    def __init__(self, url, cookie_file=None, browser_auth=None):
        super().__init__()
        self.url = url
        self.cookie_file = cookie_file
        self.browser_auth = browser_auth
        self._cancel_requested = False

    def request_cancel(self):
        self._cancel_requested = True

    def run(self):
        try:
            if self._cancel_requested:
                print("[Analyze] Cancel requested before starting")
                return
            print(f"[Analyze] Worker started for URL: {self.url}")
            import yt_dlp
            from downloader import apply_restricted_mode_options
            
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'skip_download': True,
            }
            if self.cookie_file:
                apply_restricted_mode_options(ydl_opts, cookiefile=self.cookie_file)
            elif self.browser_auth:
                apply_restricted_mode_options(ydl_opts, browser_auth=self.browser_auth)

            print(f"[Analyze] yt-dlp extraction started")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.url, download=False)
            
            print(f"[Analyze] yt-dlp extraction finished, info keys: {list(info.keys())[:5]}")

            # Extract ONLY what the UI needs — do NOT emit the full info dict
            safe_info = {
                "title":          info.get("title", "Unknown"),
                "uploader":       info.get("uploader", ""),
                "duration":       info.get("duration", 0),
                "thumbnail":      info.get("thumbnail", ""),
                "filesize_approx": info.get("filesize_approx", 0),
                "webpage_url":    info.get("webpage_url", self.url),
                "formats": [
                    {
                        "format_id":  f.get("format_id", ""),
                        "ext":        f.get("ext", ""),
                        "height":     f.get("height"),
                        "width":      f.get("width"),
                        "fps":        f.get("fps"),
                        "vcodec":     f.get("vcodec", ""),
                        "acodec":     f.get("acodec", ""),
                        "filesize":   f.get("filesize"),
                        "format_note": f.get("format_note", ""),
                        "protocol":    f.get("protocol", ""),
                        "resolution":  f.get("resolution", ""),
                    }
                    for f in info.get("formats", [])
                    if isinstance(f, dict)
                ],
                "subtitles":      {k: {} for k in info.get("subtitles", {}).keys()} if isinstance(info.get("subtitles"), dict) else {},
                "automatic_captions": {k: {} for k in info.get("automatic_captions", {}).keys()} if isinstance(info.get("automatic_captions"), dict) else {},
            }

            if self._cancel_requested:
                print("[Analyze] Cancel requested before emitting result")
                return

            print(f"[Analyze] result signal emitting")
            self.result.emit(safe_info)
            print(f"[Analyze] result emitted")

        except Exception as e:
            import traceback
            print(f"[Analyze] exception: {e}")
            print(traceback.format_exc())
            self.error.emit(str(e))
        finally:
            self.finished.emit()

