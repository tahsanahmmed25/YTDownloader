import hashlib
import os
from datetime import datetime, UTC

from PySide6.QtCore import QObject, Signal

from downloader import download_video, get_video_info, DownloadPaused, DownloadCancelled
from history_manager import save_history
from app_config import THUMB_DIR, ensure_dir
from logging_utils import get_logger
from net_utils import request_with_retry, get_bytes


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
        try:
            resp = request_with_retry("GET", self.url, stream=True, timeout=20)
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            with open(self.dest_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if self._cancel_requested:
                        try:
                            resp.close()
                        except Exception:
                            pass
                        return
                    if not chunk:
                        continue
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        self.progress.emit(int(downloaded * 100 / total))
            if self.expected_sha256:
                sha = hashlib.sha256()
                with open(self.dest_path, "rb") as f:
                    for chunk in iter(lambda: f.read(1024 * 1024), b""):
                        sha.update(chunk)
                actual = sha.hexdigest().lower()
                if actual != self.expected_sha256:
                    try:
                        os.remove(self.dest_path)
                    except Exception:
                        pass
                    self.error.emit("Update hash mismatch. Download blocked.")
                    return
            self.completed.emit(self.dest_path)
        except Exception as e:
            _log.exception("Update download failed for %s", self.url)
            self.error.emit(str(e))
        finally:
            self.finished.emit()


class FetchWorker(QObject):
    info_ready = Signal(str, object, object, object, object, object)
    error = Signal(str)
    finished = Signal()

    def __init__(self, url, cookie_file, allow_playlist=False, quality=None, container="auto"):
        super().__init__()
        self.url = url
        self.cookie_file = cookie_file
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
                allow_playlist=self.allow_playlist,
                quality=self.quality,
                container=self.container
            )
            if self._cancel_requested:
                return
            thumb_bytes = None
            if thumb:
                try:
                    thumb_bytes = get_bytes(thumb, timeout=10, retries=2)
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
        except Exception as e:
            _log.exception("Fetch info failed for %s", self.url)
            self.error.emit(str(e))
        finally:
            self.finished.emit()


class DownloadWorker(QObject):
    progress = Signal(float, object, object, object)
    error = Signal(str)
    completed = Signal(list)
    paused = Signal()
    finished = Signal()

    def __init__(self,
                 url,
                 quality,
                 cookie_file,
                 download_dir,
                 download_playlist=False,
                 container="mp4",
                 subtitles=False,
                 subtitles_langs=None,
                 embed_subtitles=True,
                 rate_limit=None):
        super().__init__()
        self.url = url
        self.quality = quality
        self.cookie_file = cookie_file
        self.download_dir = download_dir
        self.download_playlist = download_playlist
        self.container = container
        self.subtitles = subtitles
        self.subtitles_langs = subtitles_langs
        self.embed_subtitles = embed_subtitles
        self.rate_limit = rate_limit
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
            content = get_bytes(thumb_url, timeout=10, retries=2)
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
                self.progress.emit(percent, speed, downloaded, total)

            results = download_video(
                self.url,
                self.quality,
                progress_cb,
                cookiefile=self.cookie_file,
                download_playlist=self.download_playlist,
                download_dir=self.download_dir,
                container=self.container,
                subtitles=self.subtitles,
                subtitles_langs=self.subtitles_langs,
                embed_subtitles=self.embed_subtitles,
                rate_limit=self.rate_limit,
                pause_check=lambda: self._pause_requested,
                cancel_check=lambda: self._cancel_requested
            ) or []

            if self._cancel_requested:
                return

            saved_items = []
            for item in results:
                thumb_path = self._save_thumbnail(
                    item.get("thumbnail"),
                    item.get("id")
                )
                history_item = {
                    "title": item.get("title") or "Unknown",
                    "url": item.get("url") or self.url,
                    "filepath": item.get("filepath") or "",
                    "thumb_path": thumb_path,
                    "added_at": datetime.now(UTC).isoformat()
                }
                save_history(history_item)
                saved_items.append(history_item)

            if not results:
                history_item = {
                    "title": self.url,
                    "url": self.url,
                    "filepath": "",
                    "thumb_path": "",
                    "added_at": datetime.now(UTC).isoformat()
                }
                save_history(history_item)
                saved_items.append(history_item)

            self.completed.emit(saved_items)
        except Exception as e:
            msg = str(e)
            if isinstance(e, DownloadPaused) or "DOWNLOAD_PAUSED" in msg:
                self.paused.emit()
                return
            if isinstance(e, DownloadCancelled) or "DOWNLOAD_CANCELLED" in msg:
                return
            _log.exception("Download failed for %s", self.url)
            self.error.emit(msg)
        finally:
            self.finished.emit()
