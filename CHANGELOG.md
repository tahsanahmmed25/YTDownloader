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

## [1.0.0] - 2026-03-17

### Added
- Pause and resume functionality for interrupted downloads
- Download queue with persistence across app restarts
- Concurrent downloads (1-5 configurable)
- System tray integration with show/quit options
- Disk space validation before downloads (200MB safety buffer)
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
|---------|--------|-------|
| 2.0.1+ | Active | Current stable release |
| 1.0.0 | Upgrade recommended | Earlier public release |
| 0.9.0 | EOL | No longer supported |

---

## How to Update

YTDownloader automatically checks for updates on startup. When an update is available:

1. **Optional Update**: Will show notification, user can choose to update
2. **Required Update**: Will prompt user to update before using the app
3. **Auto-Download**: If enabled in Options, downloads silently in background

Users can also manually check for updates via Options → "Check Now" button.

---

## Reporting Bugs

Found a bug? Please help us improve by reporting it:

1. Check [existing issues](https://github.com/tahsanahmmed25/YTDownloader/issues)
2. Open a [new issue](https://github.com/tahsanahmmed25/YTDownloader/issues/new)
3. Include:
   - Windows version
   - Error message (from logs)
   - Steps to reproduce
   - Video URL (if applicable)

---

## Development

To run development version:
```bash
git clone https://github.com/tahsanahmmed25/YTDownloader.git
cd YTDownloader
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
python app.py
```
