import pytest

import ffmpeg_manager
from updates.manager import custom_update_urls_enabled, validate_update_url


def test_ffmpeg_download_allows_https_by_default(monkeypatch):
    monkeypatch.delenv("YTDL_LOCAL_DEV_MODE", raising=False)
    # Should not raise any exception
    ffmpeg_manager._require_ffmpeg_sha("", "Linux")


def test_custom_update_urls_disabled_by_default(monkeypatch):
    monkeypatch.delenv("YTDL_ALLOW_CUSTOM_UPDATE_URL", raising=False)

    assert custom_update_urls_enabled() is False
    with pytest.raises(ValueError, match="not trusted"):
        validate_update_url("https://updates.example.test/manifest.json")


def test_custom_update_urls_require_explicit_opt_in(monkeypatch):
    monkeypatch.setenv("YTDL_ALLOW_CUSTOM_UPDATE_URL", "true")

    validate_update_url("https://updates.example.test/manifest.json")
