# YTDownloader

Modern Windows YouTube downloader with a clean UI, a stable queue, and two clear modes:
Normal Mode for public videos (no cookies) and Restricted Mode for user-consented browser auth.

## Highlights
- Fast Analyze with title, estimated size, and thumbnail preview
- Normal Mode (no cookies) for public videos
- Restricted Mode (optional) to use browser auth for age/account-restricted videos
- Playlist downloads with queue and per-item progress
- Subtitles download and optional embedding
- Download queue with pause/resume/cancel
- History library with thumbnails and actions
- Speed limit and disk space checks
- Auto-update checker
- FFmpeg essentials auto-install
- Light and dark themes

## System Requirements
- Windows 10 or newer
- Internet connection
- Optional: a supported browser for Restricted Mode

## Installation (Users)
1. Download the installer from Releases.
2. Run the installer and follow prompts.
3. Open the app and start with Normal Mode. Use Restricted Mode only when needed.

## Normal vs Restricted Mode
Normal Mode:
- Uses no cookies
- Works for public videos

Restricted Mode:
- Uses your local browser auth only after explicit consent
- Intended for age-restricted or account-required videos you already have access to

## Development Setup
1. Create and activate a virtual environment.
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Run the app:
   - `python app.py`

## Project Structure
```
app.py
  └─ ui/main_window.py
       ├─ ui/pages.py
       ├─ ui/widgets.py
       ├─ ui/dialogs.py
       └─ workers.py
            └─ downloader.py
```

## Privacy and Safety
- Cookies are never used unless the user explicitly enables Restricted Mode.
- Browser auth is local to the user’s device.
- Do not share cookies files with anyone.

## Troubleshooting
- If a video requires login, enable Restricted Mode and connect a local browser profile.
- If subtitle embedding fails, install essentials (FFmpeg) from Preferences.
- If updates fail, verify the Update manifest URL in Preferences.

## License
See [LICENSE](LICENSE).
