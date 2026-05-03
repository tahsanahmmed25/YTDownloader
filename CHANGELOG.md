# Changelog

All notable changes to YTDownloader will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Planned
- Keyboard shortcuts (Ctrl+V, Ctrl+Q, Enter)
- Delete downloaded files from library
- Tray notifications on download completion
- Remember last quality/format preference
- Estimated time remaining during download
- CLI interface for scripting

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
- Library with search/filter by title
- Download history with thumbnails
- Multi-file queue management system
- Toast notifications for user feedback
- Dark mode toggle
- Download folder selection
- Quality/format selection
- Local library management
- Settings persistence

---

## Version Support

| Version | Status | Notes |
|---|---|---|
| **2.1.7** | ✅ Active | Current stable — Windows + Linux |
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
