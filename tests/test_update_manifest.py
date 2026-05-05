import pytest

from updates.manager import UpdateManifest, extract_update_info, validate_manifest, verify_update_file


SHA = "a" * 64


def test_extracts_github_release_asset_and_hash_from_body():
    data = {
        "tag_name": "v2.1.9",
        "assets": [
            {
                "name": "YTDownloader-linux-x86_64.AppImage",
                "browser_download_url": "https://github.com/tahsanahmmed25/YTDownloader/releases/download/v2.1.9/YTDownloader-linux-x86_64.AppImage",
            }
        ],
        "body": f"installer_sha256: {SHA}\nmin_required_version: 2.1.0\n",
    }

    manifest = extract_update_info(
        data,
        "https://api.github.com/repos/tahsanahmmed25/YTDownloader/releases/latest",
        "YTDownloader-linux-x86_64.AppImage",
    )

    validated = validate_manifest(manifest, "YTDownloader-linux-x86_64.AppImage")
    assert validated.latest_version == "v2.1.9"
    assert validated.installer_sha256 == SHA
    assert validated.installer_asset_name == "YTDownloader-linux-x86_64.AppImage"


def test_validate_manifest_rejects_missing_hash():
    manifest = UpdateManifest(
        latest_version="2.1.9",
        manifest_url="https://api.github.com/repos/tahsanahmmed25/YTDownloader/releases/latest",
        installer_url="https://github.com/tahsanahmmed25/YTDownloader/releases/download/v2.1.9/YTDownloader-Setup.exe",
        installer_asset_name="YTDownloader-Setup.exe",
    )

    with pytest.raises(ValueError, match="SHA256 is required"):
        validate_manifest(manifest, "YTDownloader-Setup.exe")


def test_validate_manifest_rejects_untrusted_host_by_default():
    manifest = UpdateManifest(
        latest_version="2.1.9",
        manifest_url="https://example.com/update.json",
        installer_url="https://example.com/YTDownloader-Setup.exe",
        installer_sha256=SHA,
        installer_asset_name="YTDownloader-Setup.exe",
    )

    with pytest.raises(ValueError, match="not trusted"):
        validate_manifest(manifest, "YTDownloader-Setup.exe")


def test_validate_manifest_allows_custom_hosts_only_when_opted_in(monkeypatch):
    monkeypatch.setenv("YTDL_ALLOW_CUSTOM_UPDATE_URL", "true")
    manifest = UpdateManifest(
        latest_version="2.1.9",
        manifest_url="https://example.com/update.json",
        installer_url="https://downloads.example.com/YTDownloader-Setup.exe",
        installer_sha256=SHA,
        installer_asset_name="YTDownloader-Setup.exe",
    )

    assert validate_manifest(manifest, "YTDownloader-Setup.exe") == manifest


def test_verify_update_file_returns_digest(tmp_path):
    path = tmp_path / "installer.bin"
    path.write_bytes(b"installer")
    import hashlib

    digest = hashlib.sha256(b"installer").hexdigest()

    assert verify_update_file(path, digest) == digest
