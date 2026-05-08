import pytest

import ffmpeg_manager
from updates.manager import custom_update_urls_enabled, validate_update_url


def test_ffmpeg_download_requires_pinned_sha_by_default(monkeypatch):
    monkeypatch.delenv("YTDL_LOCAL_DEV_MODE", raising=False)
    monkeypatch.delenv("YTDL_ALLOW_UNVERIFIED_FFMPEG_DOWNLOADS", raising=False)

    with pytest.raises(RuntimeError, match="SHA256 is not configured"):
        ffmpeg_manager._require_ffmpeg_sha("", "Linux")


def test_ffmpeg_download_allows_dev_override(monkeypatch):
    monkeypatch.delenv("YTDL_LOCAL_DEV_MODE", raising=False)
    monkeypatch.setenv("YTDL_ALLOW_UNVERIFIED_FFMPEG_DOWNLOADS", "true")

    ffmpeg_manager._require_ffmpeg_sha("", "Linux")


def test_ffmpeg_download_accepts_configured_sha(monkeypatch):
    monkeypatch.delenv("YTDL_ALLOW_UNVERIFIED_FFMPEG_DOWNLOADS", raising=False)

    ffmpeg_manager._require_ffmpeg_sha("a" * 64, "Linux")


def test_linux_ffmpeg_download_fails_before_network_without_sha(monkeypatch):
    monkeypatch.delenv("YTDL_LOCAL_DEV_MODE", raising=False)
    monkeypatch.delenv("YTDL_ALLOW_UNVERIFIED_FFMPEG_DOWNLOADS", raising=False)
    monkeypatch.setattr(ffmpeg_manager, "_FFMPEG_LIN_TAR_SHA256", "")
    monkeypatch.setattr(
        ffmpeg_manager,
        "request_with_retry",
        lambda *args, **kwargs: pytest.fail("network request should not start without a pinned SHA256"),
    )

    with pytest.raises(RuntimeError, match="SHA256 is not configured"):
        ffmpeg_manager._download_linux(None)


def test_custom_update_urls_disabled_by_default(monkeypatch):
    monkeypatch.delenv("YTDL_ALLOW_CUSTOM_UPDATE_URL", raising=False)

    assert custom_update_urls_enabled() is False
    with pytest.raises(ValueError, match="not trusted"):
        validate_update_url("https://updates.example.test/manifest.json")


def test_custom_update_urls_require_explicit_opt_in(monkeypatch):
    monkeypatch.setenv("YTDL_ALLOW_CUSTOM_UPDATE_URL", "true")

    validate_update_url("https://updates.example.test/manifest.json")
