"""
ytdlp_exe_manager.py
Manages the yt-dlp binary: checks for updates from GitHub Releases
and downloads it to bin_dir() on first run or when outdated.

- Windows : downloads yt-dlp.exe
- Linux   : downloads yt-dlp (no extension), makes it executable
             First checks the system PATH (e.g. installed via apt).
All temp files go to local_tmp_dir() (project data folder, never /tmp or %TEMP%).
"""

import os
import sys
import time
import stat
import hashlib
import threading

from app_config import app_dir, bin_dir, bin_name, local_tmp_dir, ensure_dir, IS_WINDOWS
from logging_utils import get_logger
from net_utils import request_with_retry

_log = get_logger()

_GITHUB_RELEASES_API = "https://api.github.com/repos/yt-dlp/yt-dlp-nightly-builds/releases/latest"
_VERSION_FILE    = "yt-dlp.version"       # sits in bin_dir()
_LAST_CHECK_FILE = "yt-dlp.lastcheck"     # timestamp of last GitHub API call
_CHECK_INTERVAL  = 4 * 60 * 60            # check at most once per 4 hours (nightly builds drop frequently)

# Platform-correct asset names in the nightly GitHub release
# Nightly uses 'yt-dlp_linux' not 'yt-dlp' for the Linux binary
_ASSET_NAME      = "yt-dlp.exe" if IS_WINDOWS else "yt-dlp_linux"
_SHA_LINE_KEY    = "yt-dlp.exe" if IS_WINDOWS else "yt-dlp_linux"

_EXE_NAME = bin_name("yt-dlp")
_LOCK = threading.Lock()
_DOWNLOAD_IN_PROGRESS = False


def get_exe_path():
    """Return the expected path of the yt-dlp binary in bin_dir()."""
    return os.path.join(bin_dir(), _EXE_NAME)


def is_exe_present():
    """True if the yt-dlp binary exists, is non-zero, and is executable."""
    import shutil
    # Prefer system-installed version on Linux (apt install yt-dlp)
    if not IS_WINDOWS:
        system = shutil.which("yt-dlp")
        if system and os.path.exists(system):
            return True
    p = get_exe_path()
    try:
        return os.path.exists(p) and os.path.getsize(p) > 0
    except Exception:
        return False


def _version_path():
    return os.path.join(bin_dir(), _VERSION_FILE)


def _lastcheck_path():
    return os.path.join(bin_dir(), _LAST_CHECK_FILE)


def _get_local_version():
    try:
        with open(_version_path(), "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


def _save_local_version(version):
    try:
        ensure_dir(bin_dir())
        with open(_version_path(), "w", encoding="utf-8") as f:
            f.write(version)
    except Exception:
        pass


def _should_check_update():
    """Return True if 24 hours have passed since the last GitHub API check."""
    try:
        with open(_lastcheck_path(), "r", encoding="utf-8") as f:
            ts = float(f.read().strip() or "0")
        return (time.time() - ts) >= _CHECK_INTERVAL
    except Exception:
        return True


def _save_last_check():
    try:
        ensure_dir(bin_dir())
        with open(_lastcheck_path(), "w", encoding="utf-8") as f:
            f.write(str(time.time()))
    except Exception:
        pass


def _fetch_latest_release():
    """Returns (tag_name, download_url, sha256_or_None) for the correct platform asset."""
    resp = request_with_retry("GET", _GITHUB_RELEASES_API, timeout=15)
    data = resp.json()
    tag = data.get("tag_name", "")
    assets = data.get("assets", [])

    exe_url = None
    sha_url = None
    for asset in assets:
        name = asset.get("name", "")
        if name == _ASSET_NAME:
            exe_url = asset.get("browser_download_url")
        if name == "SHA2-256SUMS":
            sha_url = asset.get("browser_download_url")

    sha256 = None
    if sha_url and exe_url:
        try:
            sha_resp = request_with_retry("GET", sha_url, timeout=10)
            for line in sha_resp.text.splitlines():
                if _SHA_LINE_KEY in line:
                    parts = line.split()
                    if parts:
                        sha256 = parts[0].lower()
                    break
        except Exception:
            pass

    return tag, exe_url, sha256


def _download_exe(url, dest_path, sha256=None, progress_cb=None, tmp_path=None):
    """Download the yt-dlp binary to dest_path, optionally verifying sha256.
    tmp_path: where to write the partial download (inside local_tmp_dir()).
    """
    if not tmp_path:
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
                _log.error("yt-dlp hash mismatch (expected %s, got %s)", sha256, actual)
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
                raise RuntimeError("yt-dlp download hash mismatch — file discarded.")

        ensure_dir(os.path.dirname(dest_path))
        os.replace(tmp_path, dest_path)

        # On Linux, make the binary executable
        if not IS_WINDOWS:
            current = os.stat(dest_path).st_mode
            os.chmod(dest_path, current | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

        if progress_cb:
            progress_cb(100)

    except Exception:
        try:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass
        raise


def ensure_ytdlp_exe(force=False, progress_cb=None):
    """
    Ensures the yt-dlp binary is present and up-to-date in bin_dir().
    Called on first run and at most once per 24 hours thereafter.
    All temp files go to local_tmp_dir() (app data folder).

    On Linux, if yt-dlp is already installed system-wide (via apt), the
    system version is used and no download is performed.

    progress_cb(int 0-100) — optional UI callback.
    Returns True if binary is ready, False if download failed.
    """
    global _DOWNLOAD_IN_PROGRESS

    import shutil

    # On Linux: if system yt-dlp is available, prefer it
    if not IS_WINDOWS and not force:
        system = shutil.which("yt-dlp")
        if system and os.path.exists(system):
            _log.info("Using system yt-dlp at %s", system)
            _save_local_version("system")
            return True

    with _LOCK:
        if _DOWNLOAD_IN_PROGRESS:
            _log.info("yt-dlp download already in progress.")
            return False
        _DOWNLOAD_IN_PROGRESS = True

    try:
        dest = get_exe_path()
        ensure_dir(bin_dir())

        local_version = _get_local_version()
        already_present = os.path.exists(dest) and os.path.getsize(dest) > 0

        if already_present and not force and local_version != "system":
            if not _should_check_update():
                _log.info("yt-dlp update check skipped (checked recently).")
                return True
            try:
                tag, exe_url, sha256 = _fetch_latest_release()
                _save_last_check()
                if tag and tag == local_version:
                    _log.info("yt-dlp is already up to date (%s).", tag)
                    return True
                _log.info("Updating yt-dlp: %s → %s", local_version or "?", tag)
            except Exception as e:
                _log.warning("Could not check yt-dlp version: %s", e)
                return True   # Already present, can't check — that's fine
        else:
            _log.info("yt-dlp missing. Fetching from GitHub...")
            try:
                tag, exe_url, sha256 = _fetch_latest_release()
                _save_last_check()
            except Exception as e:
                _log.error("Failed to fetch yt-dlp release info: %s", e)
                return False

        if not exe_url:
            _log.error("No yt-dlp download URL found in GitHub release.")
            return False

        tmp_dir = local_tmp_dir()
        tmp_path = os.path.join(tmp_dir, _EXE_NAME + ".tmp")

        _log.info("Downloading yt-dlp v%s from %s", tag, exe_url)
        _download_exe(exe_url, dest, sha256=sha256, progress_cb=progress_cb,
                      tmp_path=tmp_path)
        _save_local_version(tag)
        _log.info("yt-dlp v%s installed to %s", tag, dest)
        return True

    except Exception as e:
        _log.error("yt-dlp setup failed: %s", e)
        return False
    finally:
        with _LOCK:
            _DOWNLOAD_IN_PROGRESS = False


def ensure_ytdlp_exe_background(on_done=None, on_error=None, progress_cb=None, force=False):
    """
    Run ensure_ytdlp_exe() in a daemon background thread.
    on_done()       — called on success (from thread, not UI thread)
    on_error(str)   — called on failure
    progress_cb(int)— progress 0-100
    """
    def _run():
        try:
            ok = ensure_ytdlp_exe(force=force, progress_cb=progress_cb)
            if ok and on_done:
                on_done()
            elif not ok and on_error:
                on_error("yt-dlp could not be downloaded. Check your internet connection.")
        except Exception as e:
            if on_error:
                on_error(str(e))

    t = threading.Thread(target=_run, daemon=True, name="ytdlp-updater")
    t.start()
    return t
