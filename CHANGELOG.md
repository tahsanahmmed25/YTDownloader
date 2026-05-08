# Changelog

All notable changes to YTDownloader will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Planned
- Keyboard shortcuts (Ctrl+V, Ctrl+Q, Enter)
- Delete downloaded files from Downloads
- Tray notifications on download completion
- Remember last quality/format preference
- Estimated time remaining during download
- CLI interface for scripting

---

## [2.1.9-beta.2] - 2026-05-08

### Added
- Added safer download task states for queued, starting, active, cancelling, paused, finalizing, completed, and failed work.
- Added automated lifecycle tests for reset during active downloads, reset spam, cancel-then-new-download behavior, app close during active tasks, concurrent download limits, fake yt-dlp progress, fake yt-dlp errors, hangs, and cancellation.

### Changed
- Renamed the main download setup area to **Homepage** and the saved/active download area to **Downloads** in visible UI copy.
- Paused new download starts while cancellation cleanup is still waiting on old download threads.
- Marked beta/alpha/rc tags as prereleases in the GitHub release workflow and added a headless AppImage smoke test.
- Updated public unsigned beta documentation with checksum verification, unsigned-app warnings, no-warranty language, and Linux AppImage troubleshooting.

### Security
- FFmpeg managed downloads now fail closed unless a trusted SHA256 is configured or an explicit development override is set.
- Update checks for private/unavailable GitHub release endpoints now pause quietly on 404 instead of telling users to make the repo public.
- Expanded log redaction tests for cookie values, auth headers, proxy passwords, and local user paths.

---

## [2.1.9-beta.1] - 2026-05-05

### Added
- Prepared the app for beta release with beta documentation, unsigned-build warnings, support/security docs, release checklist, and local/manual test separation.
- Added pytest coverage for URL validation, session/cookie validation, storage migration, update manifests, import smoke checks, and security helpers.
- Added SQLite-backed history and queue storage wrappers with WAL mode, transactions, and JSON migration support.

### Changed
- Hardened release/build scripts and CI so tests run before packaging and release artifacts include SHA256 checksum files.
- Tightened managed download/update paths with safer URL validation, archive extraction, checksum verification hooks, and redacted logging.
- Updated local Linux release builds to use the project `.venv` without requiring development-mode app paths.

### Security
- Added private file/directory helpers, atomic write helpers, safe archive extraction, and keyring-backed session/proxy secret storage where available.
- Restricted production update URLs to trusted GitHub release hosts unless `YTDL_ALLOW_CUSTOM_UPDATE_URL=true` is explicitly set.

### Known Limitations
- Builds are unsigned and may trigger Windows SmartScreen or Linux desktop security warnings.
- Update manifests are checksum-gated but not signed yet.
- Private GitHub release update checks can return `404` without authenticated GitHub API access.
- AppImage build tooling was verified by a locally computed SHA256 for this beta build; a separately pinned upstream checksum policy is still needed.

---

## [2.1.8] - 2026-05-04

### Fixed
- Fixed Restricted Mode so browser connection only succeeds after extracting a complete YouTube + Google login session.
- Fixed restricted video analysis/download retries to prefer the normal authenticated YouTube client before mobile fallbacks.
- Protected saved cookie sessions from being rewritten by failed yt-dlp probes.
- Fixed Linux/Zorin first-run downloads so split video/audio streams are not requested until FFmpeg is ready, preventing separated files.

### Changed
- Bumped app and Windows installer metadata to `2.1.8`.

---

## [2.1.7] - 2026-05-03

### Fixed
- Fixed GitHub release publishing when Actions artifact storage quota is full by uploading release assets directly from the platform build jobs.
- Fixed the Linux AppImage desktop category metadata used in CI and local Linux release builds.

### Changed
- Bumped app and Windows installer metadata to `2.1.7`.

---

## [2.1.6] - 2026-05-03

### Fixed
- Fixed Restricted Mode retry after locked browser cookies by calling the correct Analyze flow.
- Fixed Auto browser authentication so fallback browsers are tried separately instead of collapsing to the first browser.
- Fixed stalled/cancelled downloads so the `yt-dlp` subprocess can be interrupted even when no output is being produced.
- Fixed close-to-tray behavior so the stalled-download watchdog keeps running while active downloads continue in the tray.
- Restored persisted queued and paused downloads on startup instead of clearing the saved queue.
- Moved history storage to the app data directory, with migration from legacy project-folder JSON/SQLite history files.
- Fixed manual FFmpeg installation to use the cross-platform FFmpeg manager and Linux `bin/` location.
- Fixed Linux updater downloads so AppImage updates are saved with the correct name, made executable, and opened with the desktop handler.
- Fixed CLI mode so it no longer imports PySide6 before checking CLI arguments.

### Changed
- Bumped app and Windows installer metadata to `2.1.6`.
- Kept yt-dlp nightly binary checks on a shorter background interval for faster YouTube compatibility updates.

---

## [2.0.2] - 2026-04-29

### Added
- **Linux / Zorin OS support** — runs natively on any 64-bit Linux distro
- **AppImage distribution** — single portable file for Linux, no installation needed
- **GitHub Actions CI/CD** — automatically builds Windows installer + Linux AppImage on every version tag; no Windows machine required to ship Windows builds
- `build_release.sh` — new Linux build script (PyInstaller → appimagetool → AppImage)
- `ffmpeg_manager.py` — downloads BtbN static FFmpeg build on Linux (tar.xz), makes executable automatically
- `ytdlp_exe_manager.py` — downloads `yt-dlp` binary (no .exe) on Linux, makes executable automatically
- Platform helpers in `app_config.py`: `IS_WINDOWS`, `bin_name()`, `user_data_dir()`, `bin_dir()`
- On Linux the app checks system PATH (`apt`-installed yt-dlp/ffmpeg) before auto-downloading its own copies
- `_kill_browser()` now uses `pkill` on Linux (was Windows-only `taskkill`)
- `NotReadyError` shows a friendly "yt-dlp is still setting up" toast instead of a raw traceback
- Installer now shows a **Choose Install Directory** page so users can install to any drive (D:, E:, etc.)

### Changed
- `pyinstaller_common.py`: Windows-only imports (`ctypes.wintypes`, `keyring.backends.Windows`) guarded by platform check; Linux build uses `keyring.backends.SecretService` instead
- `downloader.py`: `_find_local_binary()` now searches `bin_dir()` and uses platform-correct binary names (no hardcoded `.exe`)
- `build_release.ps1`: PyArmor obfuscation is **off by default** (eliminates antivirus false positives); pass `-Obfuscate` flag to enable
- Build script now automatically copies `yt-dlp.exe` + `ffmpeg.exe` into `dist\YTDownloader\` before Inno Setup runs

### Fixed
- Format selection changed from `height=N` (exact match) to `height<=N` — prevents silent failures when the exact requested resolution isn't available for a video
- Removed stale `{localappdata}\YTDownloader` from `[UninstallDelete]` in `.iss` — uninstall now works correctly on non-C: drive installs

---

## [2.0.1] - 2026-04-16

### Added
- Automatic first-run `yt-dlp.exe` download and background update checks
- Background FFmpeg essentials install workflow inside the app
- Release-build preflight checks for required runtime dependencies
- Shared PyInstaller spec configuration for normal and obfuscated builds

### Changed
- Windows release builds now prefer the project `venv` instead of whichever global Python is first on `PATH`
- FFmpeg and temporary download assets now use project-local temp paths instead of system temp folders
- Release documentation now uses a packaged-process smoke test that matches Windows GUI behavior

### Fixed
- Packaged Windows EXE no longer ships without `PySide6` because of interpreter mismatch during release builds
- Startup import ordering in `app_config.py` no longer causes packaged app launch failure
- SQLite history operations now close database connections reliably
- Format cache access is now guarded for concurrent use

---

## [1.0.0] - 2026-03-17

### Added
- Pause and resume functionality for interrupted downloads
- Download queue with persistence across app restarts
- Concurrent downloads (1–5 configurable)
- System tray integration with show/quit options
- Disk space validation before downloads (200 MB safety buffer)
- Download speed limiting (KB/s configurable, 0 = unlimited)
- Real-time download progress with speed and size display
- Downloads section with search/filter by title
- Download history with thumbnails
- Multi-file queue management system
- Toast notifications for user feedback
- Dark mode toggle
- Download folder selection
- Quality/format selection
- Local downloads management
- Settings persistence

---

## Version Support

| Version | Status | Notes |
|---|---|---|
| **2.1.9-beta.2** | Unsigned beta | Current beta — UI rename, task cancellation hardening, public-beta docs, and Linux AppImage checksum |
| 2.1.9-beta.1 | Unsigned beta | Earlier beta — hardening, tests, docs, and Linux AppImage checksum |
| 2.1.8 | Active stable | Restricted-video and Linux merge fixes |
| 2.1.7 | Upgrade recommended | Release workflow fix; affected by restricted-session and first-run FFmpeg issues |
| 2.1.6 | Upgrade recommended | Runtime fixes; GitHub release workflow failed before assets were published |
| 2.0.2 | Upgrade recommended | Earlier Windows + Linux release |
| 2.0.1 | Upgrade recommended | Windows only |
| 1.0.0 | Upgrade recommended | Earlier public release |
| 0.9.0 | ❌ EOL | No longer supported |

---

## How to Update

YTDownloader automatically checks for updates on startup. When an update is available:

1. **Optional Update** — shows a notification; you can choose to update later
2. **Required Update** — prompts you to update before using the app
3. **Silent background update** — yt-dlp and FFmpeg update themselves automatically once per day

You can also manually check for app updates via **Preferences → Check for Updates**.

---

## Reporting Bugs

Found a bug? Please help improve the app:

1. Check [existing issues](https://github.com/tahsanahmmed25/YTDownloader/issues)
2. Open a [new issue](https://github.com/tahsanahmmed25/YTDownloader/issues/new)
3. Include:
   - OS and version (e.g. "Zorin OS 17", "Windows 11")
   - Error message (from logs or the app's error toast)
   - Steps to reproduce
   - Video URL (if applicable)

---

## Development

```bash
git clone https://github.com/tahsanahmmed25/YTDownloader.git
cd YTDownloader
python3 -m venv venv
source venv/bin/activate          # Linux
# venv\Scripts\activate           # Windows
pip install PySide6 requests browser-cookie3 yt-dlp
python app.py
```
