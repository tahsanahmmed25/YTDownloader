"""
ui/session_manager.py — YouTube Session Manager

Handles persistence and validation of YouTube authentication cookies.
Entirely I/O focused; no Qt dependency, safe to call from any thread.

Critical design contract
------------------------
A "valid session" means the cookies file ACTUALLY CONTAINS real YouTube
and Google authentication cookies (SID, SAPISID, __Secure-1PSID, etc.).

Merely having a file with the Netscape header but no auth cookies is
treated the same as having no session at all — we NEVER pass such a file
to yt-dlp, because yt-dlp with an empty/tracking-only cookie file causes
YouTube to reject even public video requests.
"""

import os
import sys
import time
from collections import defaultdict

from auth.session_store import (
    clear_session_storage,
    managed_cookie_cache_path,
    materialize_session_cookie_file,
    save_session_cookie_text,
)
from logging_utils import get_logger

_log = get_logger()

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

# YouTube age/membership checks can depend on both YouTube and Google account
# cookies. A YouTube-only cookie file may look logged in but still fail
# age-restricted videos with "Sign in to confirm your age".
_YOUTUBE_COOKIE_DOMAINS = (".youtube.com", "youtube.com")
_GOOGLE_COOKIE_DOMAINS = (".google.com", "google.com")
_COOKIE_LOAD_DOMAINS = (".youtube.com", ".google.com")

# Minimum number of auth cookies we require before considering a session valid.
_MIN_AUTH_COOKIES = 2

_AUTO_BROWSER_ORDER = ["chrome", "firefox", "edge", "brave", "opera", "chromium"]
if sys.platform.startswith("linux"):
    # Firefox does not require the Linux keyring for cookie decryption, which
    # makes it the most reliable first attempt on Zorin/Ubuntu-like desktops.
    _AUTO_BROWSER_ORDER = ["firefox", "chrome", "edge", "brave", "opera", "chromium"]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_session_cookies_path() -> str:
    """Canonical path for the managed session cookies file."""
    return managed_cookie_cache_path()


def get_browser_auto_order() -> list:
    """Return the browser order used by auto cookie extraction."""
    return list(_AUTO_BROWSER_ORDER)


def load_session() -> str:
    """
    Return the cookies path if a valid authenticated session exists, else ''.
    Validity requires the file to contain real YouTube auth cookies.
    """
    path = materialize_session_cookie_file()
    if is_session_valid(path):
        _log.info("Managed YouTube session restored")
        return path
    if os.path.isfile(path):
        _log.warning(
            "Managed session file exists but contains no valid auth cookies — ignoring"
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

    _YOUTUBE_DOMAINS = _YOUTUBE_COOKIE_DOMAINS + _GOOGLE_COOKIE_DOMAINS

    _BROWSER_LOADERS = {
        "chrome":   browser_cookie3.chrome,
        "firefox":  browser_cookie3.firefox,
        "edge":     browser_cookie3.edge,
        "brave":    browser_cookie3.brave,
        "opera":    browser_cookie3.opera,
        "chromium": browser_cookie3.chromium,
    }

    names_to_try = get_browser_auto_order() if browser_name == "auto" else [browser_name.lower()]

    # On some Linux distros (e.g. Zorin OS), Firefox stores its profile under
    # ~/.config/mozilla/firefox instead of the standard ~/.mozilla/firefox.
    # browser_cookie3 only knows about the standard path, so we detect the
    # alternate location and pass it explicitly as cookie_file.
    _firefox_custom_profile = None
    if sys.platform.startswith("linux"):
        _std = os.path.expanduser("~/.mozilla/firefox")
        _alt = os.path.expanduser("~/.config/mozilla/firefox")
        _flt = os.path.expanduser("~/.var/app/org.mozilla.firefox/config/mozilla/firefox")
        if not os.path.isdir(_std):
            for _candidate in (_alt, _flt):
                if os.path.isdir(_candidate):
                    import glob as _glob, configparser as _cp
                    _ini_hits = _glob.glob(os.path.join(_candidate, "profiles.ini"))
                    if _ini_hits:
                        _cfg = _cp.ConfigParser()
                        _cfg.read(_ini_hits[0], encoding="utf-8")
                        for _sec in _cfg.sections():
                            if _cfg.get(_sec, "Default", fallback="") == "1" or _cfg.has_option(_sec, "Path"):
                                _rel = _cfg.get(_sec, "Path", fallback="")
                                if _rel:
                                    _full = os.path.join(_candidate, _rel)
                                    _cookie_db = os.path.join(_full, "cookies.sqlite")
                                    if os.path.isfile(_cookie_db):
                                        _firefox_custom_profile = _cookie_db
                                        _log.info("Firefox custom profile cookies found at: %s", _firefox_custom_profile)
                                        break
                    if _firefox_custom_profile:
                        break

    best_collected: dict = {}          # (domain, path, name) → cookie
    best_auth_count: int = 0
    best_has_required_auth = False
    last_err = None

    for name in names_to_try:
        loader = _BROWSER_LOADERS.get(name)
        if loader is None:
            continue
        try:
            collected: dict = {}
            for domain_name in _COOKIE_LOAD_DOMAINS:
                try:
                    # For Firefox on non-standard Linux paths, pass cookie_file explicitly
                    if name == "firefox" and _firefox_custom_profile and os.path.isfile(_firefox_custom_profile):
                        jar = loader(cookie_file=_firefox_custom_profile, domain_name=domain_name)
                    else:
                        jar = loader(domain_name=domain_name)
                except Exception:
                    if domain_name == _COOKIE_LOAD_DOMAINS[-1]:
                        raise
                    continue
                for cookie in jar:
                    domain = (getattr(cookie, "domain", "") or "").lower()
                    if any(domain.endswith(d) for d in _YOUTUBE_DOMAINS):
                        path_val = getattr(cookie, "path", "/") or "/"
                        collected[(cookie.domain, path_val, cookie.name)] = cookie

            auth_count = sum(
                1 for (*_, cname) in collected
                if cname in _YOUTUBE_AUTH_COOKIE_NAMES
            )
            has_required_auth = _cookies_have_required_auth(collected)
            _log.info(
                "Browser '%s': found %d YouTube/Google cookies, %d auth cookies, required_auth=%s",
                name, len(collected), auth_count, has_required_auth
            )

            if has_required_auth or auth_count > best_auth_count:
                best_auth_count = auth_count
                best_collected = collected
                best_has_required_auth = has_required_auth

            if has_required_auth:
                break   # found a good browser — stop searching

        except Exception as exc:
            err_lower = str(exc).lower()
            if "could not find" in err_lower or "no such file" in err_lower:
                _log.debug("Browser '%s' not installed or no profile: %s", name, exc)
            else:
                _log.warning("Browser '%s' extraction error: %s", name, exc)
            last_err = exc

    if not best_has_required_auth:
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
        if best_auth_count >= _MIN_AUTH_COOKIES:
            detail = (
                "\n\nSome account cookies were found, but the browser did not expose both "
                "YouTube and Google login cookies. Open YouTube in that browser, confirm "
                "you are signed in, then reconnect."
            ) + detail
        raise RuntimeError(
            "No complete YouTube login session was found in any browser.\n\n"
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


def get_auth_cookie_domain_groups_in_file(path: str) -> dict:
    """Return auth cookie names grouped by YouTube/Google domain family."""
    groups = defaultdict(set)
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) < 7:
                    continue
                domain = (parts[0] or "").lower()
                cookie_name = parts[5]
                if cookie_name not in _YOUTUBE_AUTH_COOKIE_NAMES:
                    continue
                if any(domain.endswith(d) for d in _YOUTUBE_COOKIE_DOMAINS):
                    groups["youtube"].add(cookie_name)
                elif any(domain.endswith(d) for d in _GOOGLE_COOKIE_DOMAINS):
                    groups["google"].add(cookie_name)
                else:
                    groups["other"].add(cookie_name)
    except OSError:
        pass
    return dict(groups)


def has_required_auth_cookies(path: str) -> bool:
    """True when a cookies file has enough account cookies for restricted videos."""
    groups = get_auth_cookie_domain_groups_in_file(path)
    youtube = groups.get("youtube") or set()
    google = groups.get("google") or set()
    total = sum(len(names) for names in groups.values())
    return bool(total >= _MIN_AUTH_COOKIES and youtube and google)


def clear_session() -> None:
    """Delete the managed cookies file."""
    clear_session_storage()
    _log.info("Session cookies deleted from managed storage")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _file_has_auth_cookies(path: str) -> bool:
    """Return True if the file contains the auth cookies restricted videos need."""
    groups = get_auth_cookie_domain_groups_in_file(path)
    auth_names = set()
    for names in groups.values():
        auth_names.update(names)
    if has_required_auth_cookies(path):
        _log.info("Cookie file contains required auth cookies: %s", auth_names)
        return True
    if auth_names:
        _log.warning(
            "Cookie file has auth cookies but is missing either YouTube or Google account cookies"
        )
    else:
        _log.warning("Cookie file has NO YouTube/Google auth cookies")
    return False


def _cookies_have_required_auth(cookies: dict) -> bool:
    groups = defaultdict(set)
    for key in cookies:
        if len(key) == 3:
            domain, _path, name = key
        else:
            domain, name = key
        domain = (domain or "").lower()
        if name not in _YOUTUBE_AUTH_COOKIE_NAMES:
            continue
        if any(domain.endswith(d) for d in _YOUTUBE_COOKIE_DOMAINS):
            groups["youtube"].add(name)
        elif any(domain.endswith(d) for d in _GOOGLE_COOKIE_DOMAINS):
            groups["google"].add(name)
    total = sum(len(names) for names in groups.values())
    return bool(total >= _MIN_AUTH_COOKIES and groups["youtube"] and groups["google"])


def _write_cookies_file(cookies: dict) -> str:
    """Write *cookies* dict to the managed Netscape cookies.txt and return path."""
    try:
        lines = [
            "# Netscape HTTP Cookie File",
            "# Managed by YTDownloader. Do not edit.",
            "",
        ]
        for key, cookie in cookies.items():
            if len(key) == 3:
                domain, _path_key, name = key
            else:
                domain, name = key
            include_sub = "TRUE" if domain.startswith(".") else "FALSE"
            path_val = getattr(cookie, "path", "/") or "/"
            secure = "TRUE" if getattr(cookie, "secure", False) else "FALSE"
            expires = int(getattr(cookie, "expires", 0) or 0)
            value = getattr(cookie, "value", "") or ""
            lines.append(
                f"{domain}\t{include_sub}\t{path_val}\t"
                f"{secure}\t{expires}\t{name}\t{value}"
            )
        out_path, keyring_saved = save_session_cookie_text("\n".join(lines) + "\n")
        _log.info("Wrote %d cookies to managed session storage (keyring=%s)", len(cookies), keyring_saved)
    except Exception as exc:
        raise RuntimeError(f"Failed to write cookies file: {exc}") from exc
    return out_path
