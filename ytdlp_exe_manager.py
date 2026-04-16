"""
ytdlp_exe_manager.py
Manages the yt-dlp.exe binary: checks for updates from GitHub Releases
and downloads it to the app directory on first run or when outdated.
Downloads go to the project/app folder, never to C: system directories.
"""

import os
import sys
import hashlib
import threading

from app_config import app_dir, ensure_dir
from logging_utils import get_logger
from net_utils import request_with_retry

_log = get_logger()

_GITHUB_RELEASES_API = "https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest"
_VERSION_FILE = "yt-dlp.version"      # sits next to yt-dlp.exe in app_dir()
_EXE_NAME = "yt-dlp.exe"
_LOCK = threading.Lock()
_DOWNLOAD_IN_PROGRESS = False


def get_exe_path():
    """Return the expected path of yt-dlp.exe in the app folder."""
    return os.path.join(app_dir(), _EXE_NAME)


def is_exe_present():
    """True if yt-dlp.exe exists and is non-zero size."""
    p = get_exe_path()
    try:
        return os.path.exists(p) and os.path.getsize(p) > 0
    except Exception:
        return False


def _get_local_version():
    path = os.path.join(app_dir(), _VERSION_FILE)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


def _save_local_version(version):
    path = os.path.join(app_dir(), _VERSION_FILE)
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(version)
    except Exception:
        pass


def _fetch_latest_release():
    """
    Returns (tag_name, download_url, sha256_or_None) for the Windows exe asset.
    """
    resp = request_with_retry(
        "GET",
        _GITHUB_RELEASES_API,
        timeout=15,
        headers={"Accept": "application/vnd.github+json"}
    )
    data = resp.json()
    tag = data.get("tag_name", "")
    assets = data.get("assets", [])

    exe_url = None
    sha_url = None
    for asset in assets:
        name = asset.get("name", "")
        if name == "yt-dlp.exe":
            exe_url = asset.get("browser_download_url")
        if name == "SHA2-256SUMS":
            sha_url = asset.get("browser_download_url")

    sha256 = None
    if sha_url and exe_url:
        try:
            sha_resp = request_with_retry("GET", sha_url, timeout=10)
            for line in sha_resp.text.splitlines():
                if "yt-dlp.exe" in line:
                    parts = line.split()
                    if parts:
                        sha256 = parts[0].lower()
                    break
        except Exception:
            pass

    return tag, exe_url, sha256


def _download_exe(url, dest_path, sha256=None, progress_cb=None):
    """Download yt-dlp.exe to dest_path, optionally verifying sha256."""
    tmp_path = dest_path + ".tmp"
    try:
        resp = request_with_retry("GET", url, timeout=60, stream=True)
        total = int(resp.headers.get("Content-Length", 0))
        downloaded = 0

        with open(tmp_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                if not chunk:
                    continue
                f.write(chunk)
                downloaded += len(chunk)
                if progress_cb and total:
                    pct = min(int(downloaded * 100 / total), 99)
                    progress_cb(pct)

        if sha256:
            digest = hashlib.sha256()
            with open(tmp_path, "rb") as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b""):
                    digest.update(chunk)
            actual = digest.hexdigest().lower()
            if actual != sha256:
                _log.error("yt-dlp.exe hash mismatch (expected %s, got %s)", sha256, actual)
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
                raise RuntimeError("yt-dlp.exe download hash mismatch — file discarded.")

        # Atomic replace
        if os.path.exists(dest_path):
            try:
                os.remove(dest_path)
            except Exception:
                pass
        os.rename(tmp_path, dest_path)
        if progress_cb:
            progress_cb(100)

    except Exception:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass
        raise


def ensure_ytdlp_exe(force=False, progress_cb=None):
    """
    Ensures yt-dlp.exe is present and up-to-date in the app folder.
    Called on first run and periodically.

    progress_cb(int 0-100) — optional UI callback.
    Returns True if exe is ready, False if download failed.
    """
    global _DOWNLOAD_IN_PROGRESS

    with _LOCK:
        if _DOWNLOAD_IN_PROGRESS:
            _log.info("yt-dlp.exe download already in progress.")
            return False
        _DOWNLOAD_IN_PROGRESS = True

    try:
        dest = get_exe_path()
        ensure_dir(os.path.dirname(dest))

        local_version = _get_local_version()
        already_present = is_exe_present()

        if already_present and not force:
            # Check if we should update (re-use the existing version check)
            try:
                tag, exe_url, sha256 = _fetch_latest_release()
                if tag and tag == local_version:
                    _log.info("yt-dlp.exe is already up to date (%s).", tag)
                    return True
                _log.info("Updating yt-dlp.exe: %s → %s", local_version or "?", tag)
            except Exception as e:
                _log.warning("Could not check yt-dlp.exe version: %s", e)
                return True   # Already present, just can't check version — that's fine
        else:
            _log.info("yt-dlp.exe missing. Fetching from GitHub...")
            try:
                tag, exe_url, sha256 = _fetch_latest_release()
            except Exception as e:
                _log.error("Failed to fetch yt-dlp.exe release info: %s", e)
                return False

        if not exe_url:
            _log.error("No yt-dlp.exe download URL found in GitHub release.")
            return False

        _log.info("Downloading yt-dlp.exe v%s from %s", tag, exe_url)
        _download_exe(exe_url, dest, sha256=sha256, progress_cb=progress_cb)
        _save_local_version(tag)
        _log.info("yt-dlp.exe v%s installed to %s", tag, dest)
        return True

    except Exception as e:
        _log.error("yt-dlp.exe setup failed: %s", e)
        return False
    finally:
        with _LOCK:
            _DOWNLOAD_IN_PROGRESS = False


def ensure_ytdlp_exe_background(on_done=None, on_error=None, progress_cb=None):
    """
    Run ensure_ytdlp_exe() in a daemon background thread.
    on_done()        — called on success (from thread, not UI thread)
    on_error(str)    — called on failure
    progress_cb(int) — progress 0-100
    """
    def _run():
        try:
            ok = ensure_ytdlp_exe(progress_cb=progress_cb)
            if ok and on_done:
                on_done()
            elif not ok and on_error:
                on_error("yt-dlp.exe could not be downloaded. Check your internet connection.")
        except Exception as e:
            if on_error:
                on_error(str(e))

    t = threading.Thread(target=_run, daemon=True, name="ytdlp-exe-updater")
    t.start()
    return t
