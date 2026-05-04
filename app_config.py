import os
import re
import sys


APP_NAME = "YTDownloader"
APP_ORG = "Tahsan"
APP_VERSION = "2.1.8"
DEFAULT_UPDATE_MANIFEST_URL = "https://api.github.com/repos/tahsanahmmed25/YTDownloader/releases/latest"
LEGACY_UPDATE_MANIFEST_URL = "https://api.github.com/repos/tahsanahmmed25/tahsan-s-code/releases/latest"

# ── Platform flags ────────────────────────────────────────────────────────────
IS_WINDOWS = sys.platform == "win32"
IS_LINUX   = sys.platform.startswith("linux")
EXE_SUFFIX = ".exe" if IS_WINDOWS else ""
UPDATE_INSTALLER_NAME = "YTDownloader-Setup.exe" if IS_WINDOWS else "YTDownloader-linux-x86_64.AppImage"


def bin_name(name):
    """Return the platform-correct binary filename.

    Examples:
        bin_name("yt-dlp")  → "yt-dlp.exe" on Windows, "yt-dlp" on Linux
        bin_name("ffmpeg")  → "ffmpeg.exe" on Windows, "ffmpeg" on Linux
    """
    return name + EXE_SUFFIX


def app_dir():
    """Directory where the application executable lives (may be read-only on Linux AppImage)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.getcwd()


def user_data_dir():
    """Writable persistent data directory for this user.

    - Windows : same as app_dir() so everything stays in the install folder.
    - Linux   : ~/.local/share/YTDownloader  (XDG Base Directory standard).
    """
    if IS_WINDOWS:
        return app_dir()
    xdg_data = os.environ.get(
        "XDG_DATA_HOME",
        os.path.join(os.path.expanduser("~"), ".local", "share")
    )
    return os.path.join(xdg_data, APP_NAME)


def bin_dir():
    """Directory where auto-downloaded binaries (yt-dlp, ffmpeg) are stored.

    - Windows : same as app_dir() — next to the .exe (current behaviour).
    - Linux   : ~/.local/share/YTDownloader/bin/
                Kept separate so the AppImage (read-only) doesn't need to be writable.
    """
    if IS_WINDOWS:
        return app_dir()
    return os.path.join(user_data_dir(), "bin")


def app_data_dir():
    """Writable application data directory (history, thumbnails, logs, cache).

    - Windows : {install_dir}/.data/YTDownloader
    - Linux   : ~/.local/share/YTDownloader/.data
    """
    if IS_WINDOWS:
        path = os.path.join(app_dir(), ".data", APP_NAME)
    else:
        path = os.path.join(user_data_dir(), ".data")
    os.makedirs(path, exist_ok=True)
    return path


def ensure_dir(path):
    if not path:
        return
    os.makedirs(path, exist_ok=True)


THUMB_DIR = os.path.join(app_data_dir(), "thumbs")
LOG_DIR   = os.path.join(app_data_dir(), "logs")


def local_tmp_dir():
    """A writable temporary directory inside the app data tree (never the system /tmp or %TEMP%)."""
    path = os.path.join(app_data_dir(), ".tmp")
    os.makedirs(path, exist_ok=True)
    return path


def get_icon_path():
    base_dirs = []
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", "")
        if meipass:
            base_dirs.append(meipass)
        base_dirs.append(os.path.dirname(sys.executable))
    base_dirs.append(os.getcwd())

    # On Linux prefer .png; on Windows prefer .ico
    icon_names = ("download.png", "download.ico") if IS_LINUX else ("download.ico", "download.png")
    for base in base_dirs:
        for name in icon_names:
            path = os.path.join(base, "icons", name)
            if os.path.exists(path):
                return path
    return None


def normalize_version(value):
    if not value:
        return ()
    cleaned = str(value)
    out = []
    current = ""
    for ch in cleaned:
        if ch.isdigit():
            current += ch
        elif ch == ".":
            if current:
                out.append(int(current))
            current = ""
        else:
            continue
    if current:
        out.append(int(current))
    return tuple(out)


def compare_versions(left, right):
    a = list(normalize_version(left))
    b = list(normalize_version(right))
    length = max(len(a), len(b))
    a.extend([0] * (length - len(a)))
    b.extend([0] * (length - len(b)))
    if a == b:
        return 0
    return 1 if a > b else -1


def extract_update_info(data, manifest_url):
    info = {
        "latest_version": "",
        "min_required_version": "",
        "installer_url": "",
        "installer_sha256": "",
        "release_notes": "",
        "manifest_url": manifest_url
    }

    if not isinstance(data, dict):
        return info

    info["latest_version"] = (
        data.get("latest_version")
        or data.get("version")
        or data.get("tag_name")
        or ""
    )
    info["min_required_version"] = (
        data.get("min_required_version")
        or data.get("min_required")
        or ""
    )

    assets = data.get("assets") or []
    if isinstance(assets, list):
        # Pick the right installer for the current platform
        preferred_suffix = ".exe" if IS_WINDOWS else ".AppImage"
        for asset in assets:
            name = (asset.get("name") or "").lower()
            if name.endswith(preferred_suffix):
                info["installer_url"] = asset.get("browser_download_url") or ""
                break
        # Fallback: any .exe (old behaviour)
        if not info["installer_url"]:
            for asset in assets:
                name = (asset.get("name") or "").lower()
                if name.endswith(".exe") or name.endswith(".appimage"):
                    info["installer_url"] = asset.get("browser_download_url") or ""
                    break

    info["installer_url"] = (
        info["installer_url"]
        or data.get("installer_url")
        or data.get("download_url")
        or ""
    )
    info["installer_sha256"] = (
        data.get("installer_sha256")
        or data.get("sha256")
        or ""
    )
    notes = data.get("release_notes") or data.get("notes") or data.get("body") or ""
    info["release_notes"] = notes

    if notes:
        if not info["min_required_version"]:
            match = re.search(r"(?im)^\s*min_required_version\s*:\s*([^\r\n]+)\s*$", notes)
            if match:
                info["min_required_version"] = match.group(1).strip()
        if not info["installer_sha256"]:
            match = re.search(r"(?im)^\s*installer_sha256\s*:\s*([a-fA-F0-9]{64})\s*$", notes)
            if match:
                info["installer_sha256"] = match.group(1).strip()

    return info
