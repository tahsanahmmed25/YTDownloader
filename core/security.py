import hashlib
import json
import os
import re
import stat
import tarfile
import tempfile
import zipfile
from pathlib import Path
from urllib.parse import urlparse, urlunparse


SENSITIVE_REPLACEMENT = "[redacted]"
DEFAULT_DOWNLOAD_LIMIT_BYTES = 500 * 1024 * 1024

_SECRET_PATTERNS = (
    re.compile(r"(?i)(password|passwd|token|secret|key)=([^&\s]+)"),
    re.compile(r"(?i)(proxy|proxy_url)=([^\s,;]+)"),
    re.compile(r"(?i)(cookiefile|cookies|cookie_file)=([^\s,;]+)"),
    re.compile(r"(?i)(--cookies\s+)([^\s]+)"),
    re.compile(r"(?i)(Authorization:\s*)(Bearer\s+)?([^\s]+)"),
    re.compile(r"(?i)(SAPISID|SID|HSID|SSID|APISID|LOGIN_INFO|__Secure-[13]P?APISID|__Secure-[13]PSID)=([^\s;]+)"),
)

_LOCAL_PATH_PATTERNS = (
    re.compile(r"(?<![\w.-])/(?:home|Users)/[^/\s,;:)]+/[^\s,;)]*"),
    re.compile(r"(?i)(?<![\w.-])[A-Z]:\\Users\\[^\\\s,;:)]+\\[^\s,;)]*"),
)


def redact_url(value):
    if not value:
        return value
    try:
        parsed = urlparse(str(value))
        if not parsed.scheme or not parsed.netloc:
            return str(value)
        netloc = parsed.netloc
        if "@" in netloc:
            userinfo, host = netloc.rsplit("@", 1)
            username = userinfo.split(":", 1)[0]
            netloc = f"{username}:{SENSITIVE_REPLACEMENT}@{host}"
        query = ""
        if parsed.query:
            safe_parts = []
            for part in parsed.query.split("&"):
                key = part.split("=", 1)[0]
                if re.search(r"(?i)(token|secret|key|password|cookie|auth)", key):
                    safe_parts.append(f"{key}={SENSITIVE_REPLACEMENT}")
                else:
                    safe_parts.append(part)
            query = "&".join(safe_parts)
        return urlunparse((parsed.scheme, netloc, parsed.path, parsed.params, query, ""))
    except Exception:
        return str(value)


def redact_sensitive(value):
    if value is None:
        return value
    text = str(value)
    text = redact_url(text)
    for pattern in _SECRET_PATTERNS:
        def _replace(match):
            if len(match.groups()) >= 3 and "Authorization" in match.group(1):
                return f"{match.group(1)}{match.group(2) or ''}{SENSITIVE_REPLACEMENT}"
            return f"{match.group(1)}={SENSITIVE_REPLACEMENT}" if "=" in match.group(0) else f"{match.group(1)}{SENSITIVE_REPLACEMENT}"
        text = pattern.sub(_replace, text)
    for pattern in _LOCAL_PATH_PATTERNS:
        text = pattern.sub("[local-path]", text)
    return text


class RedactingFormatter:
    """Mixin for logging formatters that redacts secrets after interpolation."""

    def format(self, record):  # pragma: no cover - exercised through logging
        original = super().format(record)
        return redact_sensitive(original)


def ensure_private_dir(path):
    if not path:
        return
    os.makedirs(path, exist_ok=True)
    if os.name != "nt":
        try:
            os.chmod(path, 0o700)
        except OSError:
            pass


def set_private_file_permissions(path):
    if not path or os.name == "nt":
        return
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def atomic_write_text(path, text, mode=0o600):
    directory = os.path.dirname(os.path.abspath(path)) or "."
    ensure_private_dir(directory)
    fd, tmp_path = tempfile.mkstemp(prefix=".tmp-", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        if os.name != "nt":
            os.chmod(tmp_path, mode)
        os.replace(tmp_path, path)
        set_private_file_permissions(path)
    except Exception:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise


def atomic_write_json(path, data):
    atomic_write_text(path, json.dumps(data, indent=4, ensure_ascii=False))


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().lower()


def verify_sha256(path, expected_sha256):
    expected = (expected_sha256 or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise ValueError("Expected SHA256 is missing or invalid")
    actual = sha256_file(path)
    if actual != expected:
        raise ValueError(f"SHA256 mismatch for {path}: expected {expected}, got {actual}")
    return True


def assert_https_url(url, allowed_hosts=None):
    parsed = urlparse(url or "")
    if parsed.scheme.lower() != "https":
        raise ValueError("URL must use HTTPS")
    if not parsed.netloc:
        raise ValueError("URL host is missing")
    if allowed_hosts:
        host = parsed.hostname or ""
        if host.lower() not in {h.lower() for h in allowed_hosts}:
            raise ValueError(f"URL host is not trusted: {host}")
    return parsed


def _safe_destination(base_dir, member_name):
    base = Path(base_dir).resolve()
    dest = (base / member_name).resolve()
    if base != dest and base not in dest.parents:
        raise ValueError(f"Unsafe archive member path: {member_name}")
    return dest


def safe_extract_zip(zip_path, dest_dir, *, max_member_size=None):
    ensure_private_dir(dest_dir)
    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.infolist():
            _safe_destination(dest_dir, member.filename)
            file_type = (member.external_attr >> 16) & 0o170000
            if file_type == stat.S_IFLNK:
                raise ValueError(f"Archive links are not allowed: {member.filename}")
            if max_member_size and member.file_size > max_member_size:
                raise ValueError(f"Archive member too large: {member.filename}")
        zf.extractall(dest_dir)


def safe_extract_tar(tar_path, dest_dir, *, max_member_size=None):
    ensure_private_dir(dest_dir)
    with tarfile.open(tar_path, "r:*") as tf:
        for member in tf.getmembers():
            _safe_destination(dest_dir, member.name)
            if member.issym() or member.islnk():
                raise ValueError(f"Archive links are not allowed: {member.name}")
            if max_member_size and member.isfile() and member.size > max_member_size:
                raise ValueError(f"Archive member too large: {member.name}")
        tf.extractall(dest_dir)
