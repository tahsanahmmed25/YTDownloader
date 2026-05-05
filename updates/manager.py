from dataclasses import dataclass
import os
import re
from urllib.parse import urlparse, unquote

from core.security import assert_https_url, sha256_file, verify_sha256


TRUSTED_UPDATE_HOSTS = {"api.github.com", "github.com", "objects.githubusercontent.com"}


@dataclass(frozen=True)
class UpdateManifest:
    latest_version: str = ""
    min_required_version: str = ""
    installer_url: str = ""
    installer_sha256: str = ""
    installer_asset_name: str = ""
    release_notes: str = ""
    manifest_url: str = ""

    def as_dict(self):
        return {
            "latest_version": self.latest_version,
            "min_required_version": self.min_required_version,
            "installer_url": self.installer_url,
            "installer_sha256": self.installer_sha256,
            "installer_asset_name": self.installer_asset_name,
            "release_notes": self.release_notes,
            "manifest_url": self.manifest_url,
        }


def _trusted_hosts_for_url(url):
    allow_custom = os.environ.get("YTDL_ALLOW_CUSTOM_UPDATE_URL", "").strip().lower() in {"1", "true", "yes"}
    if allow_custom:
        return None
    return TRUSTED_UPDATE_HOSTS


def custom_update_urls_enabled():
    return os.environ.get("YTDL_ALLOW_CUSTOM_UPDATE_URL", "").strip().lower() in {"1", "true", "yes"}


def validate_update_url(url):
    return assert_https_url(url, allowed_hosts=_trusted_hosts_for_url(url))


def _is_sha256(value):
    return bool(re.fullmatch(r"[0-9a-fA-F]{64}", value or ""))


def extract_update_info(data, manifest_url, installer_name):
    info = {
        "latest_version": "",
        "min_required_version": "",
        "installer_url": "",
        "installer_sha256": "",
        "release_notes": "",
        "manifest_url": manifest_url,
    }
    if not isinstance(data, dict):
        return UpdateManifest(**info)

    info["latest_version"] = data.get("latest_version") or data.get("version") or data.get("tag_name") or ""
    info["min_required_version"] = data.get("min_required_version") or data.get("min_required") or ""

    assets = data.get("assets") or []
    wanted = (installer_name or "").lower()
    if isinstance(assets, list):
        for asset in assets:
            name = (asset.get("name") or "").lower()
            if wanted and name == wanted:
                info["installer_url"] = asset.get("browser_download_url") or ""
                info["installer_asset_name"] = asset.get("name") or ""
                break
        if not info["installer_url"]:
            suffix = ".exe" if wanted.endswith(".exe") else ".appimage"
            for asset in assets:
                name = (asset.get("name") or "").lower()
                if name.endswith(suffix):
                    info["installer_url"] = asset.get("browser_download_url") or ""
                    info["installer_asset_name"] = asset.get("name") or ""
                    break

    info["installer_url"] = info["installer_url"] or data.get("installer_url") or data.get("download_url") or ""
    info["installer_sha256"] = data.get("installer_sha256") or data.get("sha256") or ""
    info["installer_asset_name"] = info.get("installer_asset_name") or data.get("installer_asset_name") or ""
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

    return UpdateManifest(**info)


def validate_manifest(manifest, installer_name=""):
    if isinstance(manifest, dict):
        manifest = UpdateManifest(**{k: manifest.get(k, "") for k in UpdateManifest().as_dict()})
    assert_https_url(manifest.manifest_url, allowed_hosts=_trusted_hosts_for_url(manifest.manifest_url))
    if manifest.installer_url:
        assert_https_url(manifest.installer_url, allowed_hosts=_trusted_hosts_for_url(manifest.installer_url))
    if installer_name and manifest.installer_url:
        asset_name = (manifest.installer_asset_name or "").lower()
        if asset_name:
            if asset_name != installer_name.lower():
                raise ValueError("Update asset name does not match this platform")
        else:
            # Direct manifests must point at the platform installer. GitHub
            # browser_download_url values can redirect to signed object URLs, so
            # GitHub API manifests should pass the asset name above instead.
            basename = unquote(os.path.basename(urlparse(manifest.installer_url).path or "")).lower()
            if basename != installer_name.lower():
                raise ValueError("Update asset name does not match this platform")
    if manifest.installer_url and not manifest.installer_sha256:
        raise ValueError("Installer SHA256 is required")
    if manifest.installer_sha256 and not _is_sha256(manifest.installer_sha256):
        raise ValueError("Installer SHA256 is invalid")
    if manifest.latest_version and not re.fullmatch(r"v?\d+(?:\.\d+){1,3}(?:[-+][A-Za-z0-9_.-]+)?", manifest.latest_version):
        raise ValueError("Latest version has an unexpected format")
    if manifest.min_required_version and not re.fullmatch(r"v?\d+(?:\.\d+){1,3}(?:[-+][A-Za-z0-9_.-]+)?", manifest.min_required_version):
        raise ValueError("Minimum required version has an unexpected format")
    return manifest


def verify_update_file(path, expected_sha256):
    verify_sha256(path, expected_sha256)
    return sha256_file(path)
