"""
ui/session_manager.py — YouTube Session Manager

Handles persistence and validation of YouTube authentication cookies.
Entirely I/O focused; no Qt dependency, safe to call from any thread.

Critical design contract
------------------------
A "valid session" means the cookies file ACTUALLY CONTAINS real YouTube
authentication cookies (SID, SAPISID, __Secure-1PSID, etc.).

Merely having a file with the Netscape header but no auth cookies is
treated the same as having no session at all — we NEVER pass such a file
to yt-dlp, because yt-dlp with an empty/tracking-only cookie file causes
YouTube to reject even public video requests.
"""

import os
import sys
import time
import logging

from app_config import app_data_dir

_log = logging.getLogger(__name__)

# File name for the managed session cookie store
_COOKIES_FILENAME = "yt_session_cookies.txt"

# Sessions older than 30 days are treated as stale
_SESSION_MAX_AGE_DAYS = 30

# Cookies that prove the user is actually logged in to YouTube.
# YouTube always sets at least SID + SAPISID for authenticated sessions.
# Tracking / analytics cookies are present without login and must NOT be
# treated as authentication.
_YOUTUBE_AUTH_COOKIE_NAMES = frozenset({
    "SID",
    "HSID",
    "SSID",
    "SAPISID",
    "APISID",
    "__Secure-1PSID",
    "__Secure-3PSID",
    "__Secure-1PAPISID",
    "__Secure-3PAPISID",
    "LOGIN_INFO",
})

# Minimum number of auth cookies we require before considering a session valid
_MIN_AUTH_COOKIES = 1


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_session_cookies_path() -> str:
    """Canonical path for the managed session cookies file."""
    return os.path.join(app_data_dir(), _COOKIES_FILENAME)


def load_session() -> str:
    """
    Return the cookies path if a valid authenticated session exists, else ''.
    Validity requires the file to contain real YouTube auth cookies.
    """
    path = get_session_cookies_path()
    if is_session_valid(path):
        _log.info("Session restored from %s", path)
        return path
    if os.path.isfile(path):
        _log.warning(
            "Session file exists at %s but contains no valid auth cookies — ignoring",
            path
        )
    return ""


def is_session_valid(path: str) -> bool:
    """
    True only if:
      1. File exists and is not too old
      2. File contains at least one real YouTube authentication cookie
    """
    if not path or not os.path.isfile(path):
        return False
    try:
        mtime = os.path.getmtime(path)
        age_days = (time.time() - mtime) / 86400
        if age_days > _SESSION_MAX_AGE_DAYS:
            _log.info("Session file is %d days old — treating as expired", int(age_days))
            return False
    except OSError:
        return False

    return _file_has_auth_cookies(path)


def save_cookies_from_browser(browser_name: str) -> str:
    """
    Extract YouTube cookies from *browser_name* using browser-cookie3,
    validate that real auth cookies are present, write to the managed
    cookies file, and return the path.

    Raises RuntimeError with a user-friendly message on any failure.
    """
    import browser_cookie3

    _YOUTUBE_DOMAINS = (
        ".youtube.com", "youtube.com",
        ".google.com", "google.com",
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
    # On Linux, Firefox does NOT need the system keyring to decrypt cookies,
    # making it far more reliable than Chrome/Edge/Brave in non-desktop environments.
    # Reorder so Firefox is tried first on Linux.
    if sys.platform.startswith("linux"):
        auto_order = ["firefox", "chrome", "edge", "brave", "opera", "chromium"]
    names_to_try = auto_order if browser_name == "auto" else [browser_name.lower()]

    best_collected: dict = {}          # (domain, name) → cookie
    best_auth_count: int = 0
    last_err = None

    for name in names_to_try:
        loader = _BROWSER_LOADERS.get(name)
        if loader is None:
            continue
        try:
            jar = loader(domain_name=".youtube.com")
            collected: dict = {}
            for cookie in jar:
                if any(cookie.domain.endswith(d) for d in _YOUTUBE_DOMAINS):
                    collected[(cookie.domain, cookie.name)] = cookie

            auth_count = sum(
                1 for (_, cname) in collected
                if cname in _YOUTUBE_AUTH_COOKIE_NAMES
            )
            _log.info(
                "Browser '%s': found %d YouTube cookies, %d auth cookies",
                name, len(collected), auth_count
            )

            if auth_count > best_auth_count:
                best_auth_count = auth_count
                best_collected = collected

            if auth_count >= _MIN_AUTH_COOKIES:
                break   # found a good browser — stop searching

        except Exception as exc:
            err_lower = str(exc).lower()
            if "could not find" in err_lower or "no such file" in err_lower:
                _log.debug("Browser '%s' not installed or no profile: %s", name, exc)
            else:
                _log.warning("Browser '%s' extraction error: %s", name, exc)
            last_err = exc

    if best_auth_count < _MIN_AUTH_COOKIES:
        # Check if the failure was due to a decryption error (Linux keyring issue)
        _is_linux = sys.platform.startswith("linux")
        _decryption_keywords = ("decrypt", "dbus", "secretstorage", "secretservice", "keyring")
        _decrypt_failed = last_err and any(k in str(last_err).lower() for k in _decryption_keywords)

        if _is_linux and _decrypt_failed:
            raise RuntimeError(
                "Your browser (likely Chrome or Edge) uses the system keyring to encrypt "
                "cookies, and this app cannot access it on Linux without the keyring service running.\n\n"
                "\u2022 Recommended fix: Use Firefox instead\n"
                "  Firefox stores cookies without keyring encryption and works reliably.\n"
                "  Steps: Open Firefox \u2192 Log in to YouTube \u2192 Come back and click \u2018I\u2019m Logged In\u2019.\n\n"
                "\u2022 Alternative: In the Cookies tab, select \u2018Firefox\u2019 from the Browser drop-down,\n"
                "  then click \u2018Connect Browser\u2019."
            )
        detail = f"\n\nTechnical detail: {last_err}" if last_err else ""
        raise RuntimeError(
            "No YouTube login cookies were found in any browser.\n\n"
            "Please make sure you are fully logged in to YouTube in your "
            "browser (Firefox is most reliable on Linux) and try again.\n\n"
            "If you recently logged in, close and reopen your browser once "
            f"to ensure cookies are saved to disk.{detail}"
        )

    return _write_cookies_file(best_collected)


def get_auth_cookie_names_in_file(path: str) -> set:
    """Return the set of auth cookie names present in *path*."""
    found = set()
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) >= 7:
                    cookie_name = parts[5]
                    if cookie_name in _YOUTUBE_AUTH_COOKIE_NAMES:
                        found.add(cookie_name)
    except OSError:
        pass
    return found


def clear_session() -> None:
    """Delete the managed cookies file."""
    path = get_session_cookies_path()
    try:
        if os.path.isfile(path):
            os.remove(path)
            _log.info("Session cookies deleted: %s", path)
    except OSError as exc:
        _log.warning("Failed to delete session file: %s", exc)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _file_has_auth_cookies(path: str) -> bool:
    """Return True if the file contains at least one YouTube auth cookie."""
    auth_names = get_auth_cookie_names_in_file(path)
    if auth_names:
        _log.info("Cookie file %s contains auth cookies: %s", path, auth_names)
        return True
    _log.warning("Cookie file %s has NO YouTube auth cookies", path)
    return False


def _write_cookies_file(cookies: dict) -> str:
    """Write *cookies* dict to the managed Netscape cookies.txt and return path."""
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
        _log.info("Wrote %d cookies to %s", len(cookies), out_path)
    except Exception as exc:
        raise RuntimeError(f"Failed to write cookies file: {exc}") from exc
    return out_path
