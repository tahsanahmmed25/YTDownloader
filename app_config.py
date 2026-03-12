import os
import re
import sys


APP_NAME = "YTDownloader"
APP_ORG = "Tahsan"
APP_VERSION = "1.0.0"
DEFAULT_UPDATE_MANIFEST_URL = "https://api.github.com/repos/tahsanahmmed25/tahsan-code/releases/latest"
LEGACY_UPDATE_MANIFEST_URL = "https://api.github.com/repos/tahsanahmmed25/tahsan-s-code/releases/latest"
UPDATE_INSTALLER_NAME = "YTDownloader-Setup.exe"


def app_data_dir():
    base = os.getenv("LOCALAPPDATA") or os.path.expanduser("~") or os.getcwd()
    path = os.path.join(base, APP_NAME)
    os.makedirs(path, exist_ok=True)
    return path


def ensure_dir(path):
    if not path:
        return
    os.makedirs(path, exist_ok=True)


THUMB_DIR = os.path.join(app_data_dir(), "thumbs")
LOG_DIR = os.path.join(app_data_dir(), "logs")


def app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.getcwd()


def get_icon_path():
    base_dirs = []
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", "")
        if meipass:
            base_dirs.append(meipass)
        base_dirs.append(os.path.dirname(sys.executable))
    base_dirs.append(os.getcwd())

    for base in base_dirs:
        for name in ("download.ico", "download.png"):
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
        for asset in assets:
            name = (asset.get("name") or "").lower()
            if name.endswith(".exe"):
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
