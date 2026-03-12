# YTDownloader

Modern YouTube downloader with a clean UI, cookies support, and update checks.

## Features
- Analyze YouTube links and fetch title, size estimate, and thumbnail
- Download best available quality or selected quality/container
- Optional subtitles download + embed
- Playlist downloads
- Library with thumbnails and quick open/remove
- Cookies support with safety warning
- Update checker and installer download

## Installation (Users)
1. Download the installer from Releases.
2. Run the installer and follow prompts.
3. Optional: add `cookies.txt` from your browser (Cookies tab).

## Development Setup
1. Create a virtual environment.
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Run the app:
   - `python app.py`

## Architecture
```
app.py
  └─ ui/main_window.py
       ├─ ui/pages.py
       ├─ ui/widgets.py
       ├─ ui/dialogs.py
       └─ workers.py
            └─ downloader.py
```

## Contributing
1. Create a feature branch.
2. Keep changes focused and well-scoped.
3. Run formatting/linting where applicable.
4. Submit a PR with a clear summary and test notes.
