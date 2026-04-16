# YTDownloader

YTDownloader is a Windows YouTube downloader with a desktop UI, queue management, history, subtitles, update checks, and two clear access modes:
- `Normal Mode` for public videos with no cookies
- `Restricted Mode` for user-consented browser auth on videos that require an account

Current stable release: `v2.0.1`

## Highlights
- Fast analyze with title, estimated size, thumbnail, and available qualities
- Playlist downloads with queueing, pause/resume, and per-item progress
- Subtitles download and optional subtitle embedding
- Local history library with thumbnails and actions
- Auto-update checks with installer-based updates
- First-run `yt-dlp.exe` bootstrap in the app folder
- Background FFmpeg essentials install for merge workflows
- More reliable packaged Windows build and installer flow
- Light and dark themes

## Installation
1. Download `YTDownloader-Setup.exe` from the GitHub Releases page.
2. Run the installer and complete setup.
3. Launch the app and start in `Normal Mode`.
4. Enable `Restricted Mode` only if a video actually requires login or age/account access.

## System Requirements
- Windows 10 or newer
- Internet connection
- Optional: a supported local browser profile for `Restricted Mode`

## Privacy
- Cookies are not used unless the user explicitly enables `Restricted Mode`.
- Browser auth stays local to the machine.
- Do not share exported cookies with anyone.

## Development
1. Create and activate a virtual environment.
2. Install dependencies with `pip install -r requirements.txt`.
3. Run the app with `python app.py`.
4. Build a Windows release with `.\build_release.ps1`.

## Troubleshooting
- If the packaged app exits immediately, rebuild from the project `venv` with `.\build_release.ps1`.
- If a video requires login, connect a supported browser profile in `Restricted Mode`.
- If subtitle embedding or muxing fails, install FFmpeg essentials from `Preferences`.
- If update checks fail, verify the GitHub release endpoint in `Preferences`.

## License
See [LICENSE](LICENSE).
