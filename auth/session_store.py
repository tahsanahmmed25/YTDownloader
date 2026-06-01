import os
from urllib.parse import quote, unquote, urlparse, urlunparse

from app_config import app_data_dir, local_tmp_dir
from core.security import atomic_write_text, ensure_private_dir, set_private_file_permissions


SERVICE_NAME = "YTDownloaderPro"
SESSION_ACCOUNT = "youtube-session-cookies"
PROXY_ACCOUNT = "proxy-password"


def _keyring():
    try:
        import keyring
        return keyring
    except Exception:
        return None


def save_secret(account, value):
    kr = _keyring()
    if not kr or value is None:
        return False
    try:
        kr.set_password(SERVICE_NAME, account, value)
        return True
    except Exception:
        return False


def load_secret(account):
    kr = _keyring()
    if not kr:
        return ""
    try:
        return kr.get_password(SERVICE_NAME, account) or ""
    except Exception:
        return ""


def delete_secret(account):
    kr = _keyring()
    if not kr:
        return False
    try:
        kr.delete_password(SERVICE_NAME, account)
        return True
    except Exception:
        return False


def managed_cookie_cache_path():
    return os.path.join(app_data_dir(), "yt_session_cookies.txt")


def read_cookie_text(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def write_secure_cookie_file(text, path=None):
    path = path or managed_cookie_cache_path()
    ensure_private_dir(os.path.dirname(path))
    atomic_write_text(path, text or "", mode=0o600)
    set_private_file_permissions(path)
    return path


def save_session_cookie_text(text):
    saved_to_keyring = save_secret(SESSION_ACCOUNT, text or "")
    # yt-dlp needs a Netscape cookies.txt path. Keep the compatibility cache
    # private and recreate it from keyring where possible.
    path = write_secure_cookie_file(text or "", managed_cookie_cache_path())
    return path, saved_to_keyring


def materialize_session_cookie_file():
    text = load_secret(SESSION_ACCOUNT)
    if text:
        return write_secure_cookie_file(text, managed_cookie_cache_path())
    path = managed_cookie_cache_path()
    if os.path.isfile(path):
        set_private_file_permissions(path)
        return path
    return ""


def clear_session_storage():
    delete_secret(SESSION_ACCOUNT)
    for path in (managed_cookie_cache_path(),):
        try:
            if os.path.isfile(path):
                os.remove(path)
        except OSError:
            pass


def materialize_runtime_cookie_copy(source_path):
    if not source_path or not os.path.isfile(source_path):
        return ""
    target = os.path.join(local_tmp_dir(), f"yt-runtime-cookies-{os.getpid()}.txt")
    with open(source_path, "r", encoding="utf-8", errors="replace") as f:
        return write_secure_cookie_file(f.read(), target)


def split_proxy_secret(proxy_url):
    parsed = urlparse(proxy_url or "")
    if not parsed.scheme or not parsed.netloc or "@" not in parsed.netloc:
        return proxy_url or "", ""
    userinfo, host = parsed.netloc.rsplit("@", 1)
    if ":" not in userinfo:
        return proxy_url, ""
    username, password = userinfo.split(":", 1)
    password = unquote(password)
    sanitized_netloc = f"{username}@{host}"
    sanitized = urlunparse((parsed.scheme, sanitized_netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
    return sanitized, password


def restore_proxy_secret(proxy_url):
    parsed = urlparse(proxy_url or "")
    if not parsed.scheme or not parsed.netloc or "@" not in parsed.netloc:
        return proxy_url or ""
    userinfo, host = parsed.netloc.rsplit("@", 1)
    if ":" in userinfo:
        return proxy_url or ""
    password = load_secret(PROXY_ACCOUNT)
    if not password:
        return proxy_url or ""
    restored_netloc = f"{userinfo}:{quote(password, safe='')}@{host}"
    return urlunparse((parsed.scheme, restored_netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))


def save_proxy_url(proxy_url):
    sanitized, password = split_proxy_secret(proxy_url)
    if password:
        save_secret(PROXY_ACCOUNT, password)
    elif not sanitized:
        delete_secret(PROXY_ACCOUNT)
    return sanitized
