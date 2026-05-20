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
        try:
            if self._cancel_requested:
                return
            title, size, thumb, available_formats, available_qualities, available_subtitles = get_video_info(
                self.url,
                cookiefile=self.cookie_file,
                browser_auth=self.browser_auth,
                allow_playlist=self.allow_playlist,
                quality=self.quality,
                container=self.container
            )
            if self._cancel_requested:
                return
            thumb_bytes = None
            if thumb:
                try:
                    thumb_bytes = get_bytes(
                        thumb,
                        timeout=10,
                        retries=2,
                        max_bytes=5 * 1024 * 1024,
                        allowed_content_types={"image/jpeg", "image/png", "image/webp"},
                    )
                except Exception:
                    _log.warning("Thumbnail fetch failed for %s", thumb)
                    thumb_bytes = None
            self.info_ready.emit(
                title,
                size,
                thumb_bytes,
                available_formats,
                available_qualities,
                available_subtitles
            )
        except CookieLockError as e:
            self.cookie_lock.emit(e.browser_name, str(e))
        except Exception as e:
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
