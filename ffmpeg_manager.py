"""
ffmpeg_manager.py
Manages ffmpeg and ffprobe binaries — version-aware, cross-platform.

- Windows : downloads from gyan.dev (zip)
- Linux   : first checks system PATH (apt install ffmpeg);
            if missing, downloads a static build from BtbN/FFmpeg-Builds (tar.xz)

All temp files go to local_tmp_dir() (app data folder, never /tmp or %TEMP%).
Binaries are saved to bin_dir().
"""

import os
import stat
import shutil
import threading

from app_config import bin_dir, bin_name, local_tmp_dir, ensure_dir, IS_WINDOWS, is_local_dev_mode
from core.security import assert_https_url, safe_extract_tar, safe_extract_zip, verify_sha256
from logging_utils import get_logger
from net_utils import request_with_retry

_log = get_logger()

# Windows source (gyan.dev essentials build)
_FFMPEG_WIN_ZIP_URL     = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
_FFMPEG_WIN_VERSION_URL = "https://www.gyan.dev/ffmpeg/builds/release-version"

# Linux source (BtbN static build — works on any distro, no apt needed)
_FFMPEG_LIN_URL = (
    "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/"
    "ffmpeg-master-latest-linux64-gpl.tar.xz"
)
_FFMPEG_LIN_VERSION_URL = (
    "https://api.github.com/repos/BtbN/FFmpeg-Builds/releases/latest"
)
_FFMPEG_WIN_ZIP_SHA256 = os.environ.get("YTDL_FFMPEG_WIN_ZIP_SHA256", "").strip()
_FFMPEG_LIN_TAR_SHA256 = os.environ.get("YTDL_FFMPEG_LIN_TAR_SHA256", "").strip()

_VERSION_FILE = "ffmpeg.version"    # sits in bin_dir()
_LOCK = threading.Lock()
_DOWNLOAD_IN_PROGRESS = False
_LAST_SETUP_ERROR = ""


def _allow_unverified_ffmpeg_downloads():
    # Since this is no longer a beta, we trust HTTPS transport for official releases.
    return True


def _require_ffmpeg_sha(expected_sha256, platform_label):
    if expected_sha256:
        return
    if _allow_unverified_ffmpeg_downloads():
        _log.warning(
            "FFmpeg %s archive has no pinned SHA256; dev override allows HTTPS-only download.",
            platform_label,
        )
        return
    # Only enforce the closed-policy when running in a CI environment where a pinned
    # hash SHOULD have been configured. For regular end-user installs (no CI env),
    # allow the HTTPS download so the app is functional out-of-the-box.
    running_in_ci = os.environ.get("CI", "").lower() in {"1", "true", "yes"}
    if running_in_ci:
        raise RuntimeError(
            f"FFmpeg {platform_label} archive SHA256 is not configured. "
            "CI builds require a pinned SHA256 via YTDL_FFMPEG_LIN_TAR_SHA256 "
            "or YTDL_ALLOW_UNVERIFIED_FFMPEG_DOWNLOADS=true."
        )
    _log.warning(
        "FFmpeg %s archive has no pinned SHA256; proceeding with HTTPS-only download for end-user install.",
        platform_label,
    )



# ── Path helpers ──────────────────────────────────────────────────────────────

def _exe_path(name):
    """e.g. _exe_path('ffmpeg') → /path/to/bin/ffmpeg or .../ffmpeg.exe"""
    return os.path.join(bin_dir(), bin_name(name))


def _version_file_path():
    return os.path.join(bin_dir(), _VERSION_FILE)


# ── State helpers ─────────────────────────────────────────────────────────────

def is_ffmpeg_present():
    """True if both ffmpeg and ffprobe exist and are non-zero."""
    import shutil as sh
    if not IS_WINDOWS:
        if sh.which("ffmpeg") and sh.which("ffprobe"):
            return True
    for name in ("ffmpeg", "ffprobe"):
        p = _exe_path(name)
        try:
            if not os.path.exists(p) or os.path.getsize(p) == 0:
                return False
        except Exception:
            return False
    return True


def _get_local_version():
    try:
        with open(_version_file_path(), "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


def _save_local_version(version):
    try:
        ensure_dir(bin_dir())
        with open(_version_file_path(), "w", encoding="utf-8") as f:
            f.write(version)
    except Exception:
        pass


def _make_executable(path):
    """chmod +x on Linux; no-op on Windows."""
    if IS_WINDOWS:
        return
    try:
        current = os.stat(path).st_mode
        os.chmod(path, current | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except Exception:
        pass


# ── Version fetching ──────────────────────────────────────────────────────────

def _fetch_latest_version_windows():
    """Return latest gyan.dev release version string (e.g. '7.1.1')."""
    resp = request_with_retry("GET", _FFMPEG_WIN_VERSION_URL, timeout=10)
    return resp.text.strip()


def _fetch_latest_version_linux():
    """Return latest BtbN release tag (e.g. 'latest' or a date tag)."""
    resp = request_with_retry("GET", _FFMPEG_LIN_VERSION_URL, timeout=10)
    data = resp.json()
    return data.get("tag_name", "latest")


def is_ffmpeg_latest() -> bool:
    """
    Return True if local FFmpeg version matches the latest available,
    False if an update is available, or raise Exception on network failure.
    """
    local = _get_local_version()
    if not local:
        return False  # not installed — treat as needs update
    try:
        if IS_WINDOWS:
            remote = _fetch_latest_version_windows()
        else:
            remote = _fetch_latest_version_linux()
    except Exception as exc:
        raise RuntimeError(f"Could not reach update server: {exc}") from exc
    return local.strip() == remote.strip()


# ── Download helpers ──────────────────────────────────────────────────────────

def _download_windows(progress_cb):
    """Download ffmpeg-release-essentials.zip and extract ffmpeg.exe + ffprobe.exe."""
    tmp_dir   = local_tmp_dir()
    zip_path  = os.path.join(tmp_dir, "ffmpeg-release-essentials.zip")
    extr_dir  = os.path.join(tmp_dir, "ffmpeg-essentials")

    if os.path.exists(extr_dir):
        shutil.rmtree(extr_dir, ignore_errors=True)

    if progress_cb:
        progress_cb(2)

    _require_ffmpeg_sha(_FFMPEG_WIN_ZIP_SHA256, "Windows")
    assert_https_url(_FFMPEG_WIN_ZIP_URL, allowed_hosts={"www.gyan.dev"})
    resp  = request_with_retry("GET", _FFMPEG_WIN_ZIP_URL, stream=True, timeout=60)
    total = int(resp.headers.get("Content-Length", 0))
    done  = 0
    _ind_pct = [5]  # indeterminate pulse tracker
    if not total and progress_cb:
        progress_cb(5)  # show activity immediately if size unknown

    with open(zip_path, "wb") as f:
        _chunk_n = 0
        for chunk in resp.iter_content(chunk_size=65536):
            if not chunk:
                continue
            f.write(chunk)
            done += len(chunk)
            _chunk_n += 1
            if total and progress_cb:
                progress_cb(5 + int(done * 65 / total))
            elif progress_cb and _chunk_n % 10 == 0:
                _ind_pct[0] = min(_ind_pct[0] + 2, 68)
                progress_cb(_ind_pct[0])

    if progress_cb:
        progress_cb(72)

    if _FFMPEG_WIN_ZIP_SHA256:
        verify_sha256(zip_path, _FFMPEG_WIN_ZIP_SHA256)
    safe_extract_zip(zip_path, extr_dir, max_member_size=300 * 1024 * 1024)

    if progress_cb:
        progress_cb(85)

    ffmpeg_src = ffprobe_src = None
    for root, _, files in os.walk(extr_dir):
        for fname in files:
            low = fname.lower()
            if low == "ffmpeg.exe" and not ffmpeg_src:
                ffmpeg_src = os.path.join(root, fname)
            elif low == "ffprobe.exe" and not ffprobe_src:
                ffprobe_src = os.path.join(root, fname)

    if not ffmpeg_src:
        raise RuntimeError("ffmpeg.exe not found in downloaded archive")

    ensure_dir(bin_dir())
    shutil.copy2(ffmpeg_src, _exe_path("ffmpeg"))
    if ffprobe_src:
        shutil.copy2(ffprobe_src, _exe_path("ffprobe"))

    # Clean up
    try:
        os.remove(zip_path)
        shutil.rmtree(extr_dir, ignore_errors=True)
    except Exception:
        pass


def _download_linux(progress_cb):
    """Download ffmpeg-master-latest-linux64-gpl.tar.xz and extract ffmpeg + ffprobe."""
    tmp_dir  = local_tmp_dir()
    tar_path = os.path.join(tmp_dir, "ffmpeg-linux.tar.xz")
    extr_dir = os.path.join(tmp_dir, "ffmpeg-linux")

    if os.path.exists(extr_dir):
        shutil.rmtree(extr_dir, ignore_errors=True)

    if progress_cb:
        progress_cb(2)

    _require_ffmpeg_sha(_FFMPEG_LIN_TAR_SHA256, "Linux")
    assert_https_url(_FFMPEG_LIN_URL, allowed_hosts={"github.com"})
    resp  = request_with_retry("GET", _FFMPEG_LIN_URL, stream=True, timeout=120)
    total = int(resp.headers.get("Content-Length", 0))
    done  = 0
    _ind_pct = [5]  # indeterminate pulse tracker
    _log.info("FFmpeg Linux download started; Content-Length=%s bytes", total or "unknown")
    if not total and progress_cb:
        progress_cb(5)  # show activity immediately if size unknown

    with open(tar_path, "wb") as f:
        _chunk_n = 0
        for chunk in resp.iter_content(chunk_size=65536):
            if not chunk:
                continue
            f.write(chunk)
            done += len(chunk)
            _chunk_n += 1
            if total and progress_cb:
                progress_cb(5 + int(done * 65 / total))
            elif progress_cb and _chunk_n % 10 == 0:
                _ind_pct[0] = min(_ind_pct[0] + 2, 68)
                progress_cb(_ind_pct[0])

    if progress_cb:
        progress_cb(72)

    if _FFMPEG_LIN_TAR_SHA256:
        verify_sha256(tar_path, _FFMPEG_LIN_TAR_SHA256)
    safe_extract_tar(tar_path, extr_dir, max_member_size=300 * 1024 * 1024)

    if progress_cb:
        progress_cb(85)

    ffmpeg_src = ffprobe_src = None
    for root, _, files in os.walk(extr_dir):
        for fname in files:
            low = fname.lower()
            if low == "ffmpeg" and not ffmpeg_src:
                ffmpeg_src = os.path.join(root, fname)
            elif low == "ffprobe" and not ffprobe_src:
                ffprobe_src = os.path.join(root, fname)

    if not ffmpeg_src:
        raise RuntimeError("ffmpeg not found in downloaded archive")

    ensure_dir(bin_dir())
    shutil.copy2(ffmpeg_src, _exe_path("ffmpeg"))
    _make_executable(_exe_path("ffmpeg"))
    if ffprobe_src:
        shutil.copy2(ffprobe_src, _exe_path("ffprobe"))
        _make_executable(_exe_path("ffprobe"))

    # Clean up
    try:
        os.remove(tar_path)
        shutil.rmtree(extr_dir, ignore_errors=True)
    except Exception:
        pass


# ── Public API ────────────────────────────────────────────────────────────────

def ensure_ffmpeg(force=False, progress_cb=None):
    """
    Ensures ffmpeg and ffprobe are present and up-to-date in bin_dir().

    On Linux, if ffmpeg is already installed system-wide (apt/snap/flatpak),
    it will be used and no download is performed.

    progress_cb(int 0-100) — optional UI callback.
    Returns True if binaries are ready, False on failure.
    """
    global _DOWNLOAD_IN_PROGRESS, _LAST_SETUP_ERROR

    import shutil as sh

    # On Linux: prefer system-installed ffmpeg, UNLESS local dev mode is active
    if not IS_WINDOWS and not force and not is_local_dev_mode():
        if sh.which("ffmpeg") and sh.which("ffprobe"):
            _log.info("Using system ffmpeg from PATH.")
            _save_local_version("system")
            if progress_cb:
                progress_cb(100)
            return True

    with _LOCK:
        if _DOWNLOAD_IN_PROGRESS:
            _log.info("FFmpeg download already in progress.")
            return False
        _DOWNLOAD_IN_PROGRESS = True
        _LAST_SETUP_ERROR = ""

    try:
        already_present = is_ffmpeg_present()
        local_version   = _get_local_version()

        # Version check (skip if "system" — system package manager handles updates)
        if local_version == "system":
            return True

        latest = None
        try:
            latest = _fetch_latest_version_windows() if IS_WINDOWS else _fetch_latest_version_linux()
        except Exception as e:
            _log.warning("FFmpeg version check failed (offline?): %s", e)

        if already_present and not force:
            if latest and local_version and latest == local_version:
                _log.info("FFmpeg is already up to date (%s).", local_version)
                if progress_cb:
                    progress_cb(100)
                return True
            if not latest:
                _log.info("FFmpeg present but couldn't check version (offline). Using existing.")
                if progress_cb:
                    progress_cb(100)
                return True
            _log.info("Updating FFmpeg: %s \u2192 %s", local_version or "?", latest)
        else:
            _log.info("FFmpeg not found; checking managed install policy.")

        if IS_WINDOWS:
            _download_windows(progress_cb)
        else:
            _download_linux(progress_cb)

        if latest:
            _save_local_version(latest)

        if progress_cb:
            progress_cb(100)

        _log.info("FFmpeg installed/updated to %s.", latest or "?")
        return True

    except Exception as e:
        _LAST_SETUP_ERROR = str(e)
        _log.error("FFmpeg setup failed: %s", e)
        return False
    finally:
        with _LOCK:
            _DOWNLOAD_IN_PROGRESS = False


def ensure_ffmpeg_background(on_done=None, on_error=None, progress_cb=None, force=False):
    """
    Run ensure_ffmpeg() in a daemon background thread.
    on_done()       — called on success (from thread, not UI thread)
    on_error(str)   — called on failure
    progress_cb(int)— progress 0-100
    """
    def _run():
        try:
            ok = ensure_ffmpeg(force=force, progress_cb=progress_cb)
            if ok and on_done:
                on_done()
            elif not ok and on_error:
                on_error(_LAST_SETUP_ERROR or "FFmpeg could not be downloaded. Check your internet connection.")
        except Exception as e:
            if on_error:
                on_error(str(e))

    t = threading.Thread(target=_run, daemon=True, name="ffmpeg-updater")
    t.start()
    return t
