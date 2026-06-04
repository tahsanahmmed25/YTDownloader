import io
import os
import tarfile
import zipfile

import pytest

from core.security import (
    redact_sensitive,
    safe_extract_tar,
    safe_extract_zip,
    sha256_file,
    verify_sha256,
)


def test_verify_sha256_accepts_matching_digest(tmp_path):
    path = tmp_path / "payload.bin"
    path.write_bytes(b"known-good")

    digest = sha256_file(path)

    assert verify_sha256(path, digest) is True


def test_verify_sha256_rejects_mismatch(tmp_path):
    path = tmp_path / "payload.bin"
    path.write_bytes(b"known-good")

    with pytest.raises(ValueError, match="SHA256 mismatch"):
        verify_sha256(path, "0" * 64)


def test_safe_extract_zip_rejects_path_traversal(tmp_path):
    archive = tmp_path / "bad.zip"
    dest = tmp_path / "dest"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("../escape.txt", "nope")

    with pytest.raises(ValueError, match="Unsafe archive member"):
        safe_extract_zip(archive, dest)

    assert not (tmp_path / "escape.txt").exists()


def test_safe_extract_tar_rejects_symlink(tmp_path):
    archive = tmp_path / "bad.tar"
    dest = tmp_path / "dest"
    with tarfile.open(archive, "w") as tf:
        info = tarfile.TarInfo("link")
        info.type = tarfile.SYMTYPE
        info.linkname = "/etc/passwd"
        tf.addfile(info)

    with pytest.raises(ValueError, match="Archive links"):
        safe_extract_tar(archive, dest)


def test_safe_extract_tar_allows_normal_file(tmp_path):
    archive = tmp_path / "ok.tar"
    dest = tmp_path / "dest"
    payload = b"hello"
    with tarfile.open(archive, "w") as tf:
        info = tarfile.TarInfo("folder/file.txt")
        info.size = len(payload)
        tf.addfile(info, io.BytesIO(payload))

    safe_extract_tar(archive, dest)

    assert (dest / "folder" / "file.txt").read_bytes() == payload


def test_redact_sensitive_hides_proxy_and_cookie_values():
    text = "proxy=http://user:secret@example.test:8080 --cookies /home/me/cookies.txt token=abc123"

    redacted = redact_sensitive(text)

    assert "secret" not in redacted
    assert "abc123" not in redacted
    assert "cookies.txt" not in redacted
    assert "[redacted]" in redacted


def test_redact_sensitive_hides_auth_headers_cookie_values_and_local_paths():
    text = (
        "Authorization: Bearer super-secret-token "
        "Cookie: SID=secret_sid; LOGIN_INFO=secret_login "
        "cookiefile=/home/testuser/private/cookies.txt "
        "proxy=https://user:proxy-pass@example.test:8443 "
        "profile=C:\\Users\\TestUser\\AppData\\Local\\Browser\\Cookies"
    )

    redacted = redact_sensitive(text)

    assert "super-secret-token" not in redacted
    assert "secret_sid" not in redacted
    assert "secret_login" not in redacted
    assert "proxy-pass" not in redacted
    assert "testuser" not in redacted.lower()
    assert "TestUser" not in redacted
    assert "cookies.txt" not in redacted
    assert "[redacted]" in redacted
    assert "[local-path]" in redacted
