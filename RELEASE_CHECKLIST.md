# Release Checklist

## Dev

- [ ] Update `APP_VERSION`, installer metadata, and `CHANGELOG.md`.
- [ ] Install from pinned files: `python -m pip install -r requirements-dev.lock`.
- [ ] Run `python -m py_compile $(git ls-files '*.py')`.
- [ ] Run `python -m pytest`.
- [ ] Run dependency scan: `python -m pip_audit -r requirements.txt -r requirements-dev.txt`.
- [ ] Test Normal Mode and Restricted Mode.
- [ ] Test browser-lock confirmation and force-close behavior.

## Staging

- [ ] Build Windows and Linux artifacts in CI.
- [ ] Verify `APPIMAGETOOL_SHA256` and `YTDL_FFMPEG_WIN_ZIP_SHA256` repository variables are set.
- [ ] Verify release assets have matching `SHA256SUMS-*` files.
- [ ] Publish release notes with `installer_sha256: <sha256>` for the platform installer.
- [ ] Test update checks against staging metadata.

## Production

- [ ] Promote the staging tag or create a final signed tag.
- [ ] Confirm CI tests passed before artifacts were uploaded.
- [ ] Confirm artifacts launch on clean Windows and Linux machines.
- [ ] Keep the previous release available for rollback.
- [ ] Monitor privacy-safe logs and issue reports after release.

## Rollback

- [ ] Mark the bad release as pre-release or remove the affected installer asset.
- [ ] Publish a corrected release with a higher version.
- [ ] Keep old checksums and release notes for auditability.
