"""
ui/session_manager.py — YouTube Session Manager

Handles persistence and validation of YouTube authentication cookies.
Entirely I/O focused; no Qt dependency, safe to call from any thread.
"""

import os
import time
from app_config import app_data_dir

# Path where the app writes its own managed cookies file
_COOKIES_FILENAME = "yt_session_cookies.txt"
# A session older than 30 days is treated as stale
_SESSION_MAX_AGE_DAYS = 30


def get_session_cookies_path() -> str:
    """Canonical path for the managed session cookies file."""
    return os.path.join(app_data_dir(), _COOKIES_FILENAME)


def load_session() -> str:
    """Return the cookies path if a valid prior session exists, else ''."""
    path = get_session_cookies_path()
    if is_session_valid(path):
        return path
    return ""


def is_session_valid(path: str) -> bool:
    """True if *path* exists, is non-empty, and is not too old."""
    if not path or not os.path.isfile(path):
        return False
    try:
        size = os.path.getsize(path)
        if size < 10:
            return False
        mtime = os.path.getmtime(path)
        age_days = (time.time() - mtime) / 86400
        if age_days > _SESSION_MAX_AGE_DAYS:
            return False
    except OSError:
        return False
    return True


def save_cookies_from_browser(browser_name: str) -> str:
    """
    Extract YouTube/Google cookies from *browser_name* using browser-cookie3,
    write them to the managed cookies file in Netscape format, and return the
    path on success.  Raises RuntimeError on failure.

    *browser_name* is one of: chrome, firefox, edge, brave, opera, chromium,
    or 'auto' to try all of them in order.
    """
    import browser_cookie3  # already a project dependency

    _YOUTUBE_DOMAINS = (
        ".youtube.com", "youtube.com",
        ".google.com", "google.com",
        ".googleapis.com", ".ytimg.com",
        ".ggpht.com", ".googlevideo.com",
    )

    _BROWSER_LOADERS = {
        "chrome":   browser_cookie3.chrome,
        "firefox":  browser_cookie3.firefox,
        "edge":     browser_cookie3.edge,
        "brave":    browser_cookie3.brave,
        "opera":    browser_cookie3.opera,
        "chromium": browser_cookie3.chromium,
    }

    auto_order = ["chrome", "firefox", "edge", "brave", "opera", "chromium"]

    if browser_name == "auto":
        names_to_try = auto_order
    else:
        names_to_try = [browser_name.lower()]

    collected = {}   # (domain, name) -> cookie
    last_err = None

    for name in names_to_try:
        loader = _BROWSER_LOADERS.get(name)
        if loader is None:
            continue
        try:
            jar = loader(domain_name=".youtube.com")
            for cookie in jar:
                if any(cookie.domain.endswith(d) for d in _YOUTUBE_DOMAINS):
                    collected[(cookie.domain, cookie.name)] = cookie
        except Exception as exc:
            err_str = str(exc).lower()
            # Skip "not installed" / "no profile" gracefully
            if "could not find" in err_str or "no such file" in err_str:
                last_err = exc
                continue
            last_err = exc
            # For other errors (e.g. decryption failure), still continue
            continue

    if not collected:
        msg = (
            "No YouTube cookies were found in any browser.\n\n"
            "Please make sure you are logged in to YouTube in your browser "
            "and try again."
        )
        if last_err:
            msg += f"\n\nTechnical detail: {last_err}"
        raise RuntimeError(msg)

    return _write_cookies_file(collected)


def _write_cookies_file(cookies: dict) -> str:
    """Write *cookies* dict to the Netscape cookies.txt file and return the path."""
    out_path = get_session_cookies_path()
    try:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("# Netscape HTTP Cookie File\n")
            f.write("# Managed by YTDownloader. Do not edit.\n\n")
            for (domain, name), cookie in cookies.items():
                include_sub = "TRUE" if domain.startswith(".") else "FALSE"
                path_val = getattr(cookie, "path", "/") or "/"
                secure = "TRUE" if getattr(cookie, "secure", False) else "FALSE"
                expires = int(getattr(cookie, "expires", 0) or 0)
                value = getattr(cookie, "value", "") or ""
                f.write(
                    f"{domain}\t{include_sub}\t{path_val}\t"
                    f"{secure}\t{expires}\t{name}\t{value}\n"
                )
    except Exception as exc:
        raise RuntimeError(f"Failed to write cookies file: {exc}") from exc
    return out_path


def clear_session() -> None:
    """Delete the managed cookies file."""
    path = get_session_cookies_path()
    try:
        if os.path.isfile(path):
            os.remove(path)
    except OSError:
        pass
