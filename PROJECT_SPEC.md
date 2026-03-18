# PROJECT_SPEC

## Overview

Build a Windows desktop app called `Simple YouTube Downloader by Tahsan`.

The product is a polished YouTube video and playlist downloader with a modern PySide6 desktop UI, `yt-dlp` download engine, `ffmpeg` merge support, persistent history, cookie-based restricted video support, installer packaging, and GitHub-based update readiness.

The app should feel modern, soft, premium, and calm. Stability is more important than cleverness.

## Technology Stack

Use:

- Python
- PySide6 for GUI
- `yt-dlp` for extraction and download
- `ffmpeg` for merge operations
- PyInstaller for executable packaging
- Inno Setup for installer creation

## Working Style

- Build a stable modular architecture, not one giant file.
- Split code into reusable modules such as app entry, downloader logic, workers, UI pages, dialogs, widgets, config, logging, and history.
- Keep code maintainable and readable.
- Use worker threads correctly so the UI does not freeze.
- Avoid manipulating Qt widgets from background threads.
- Test after every major change.
- Prefer stability over cleverness.
- Do not make destructive changes without asking.

## App Identity

- App title: `Simple YouTube Downloader by Tahsan`
- Sidebar brand label: `YTDownloader`
- Version: `1.0.0` until changed intentionally
- Platform target: Windows desktop
- Icon assets:
  - `icons/download.ico`
  - `icons/download.png`

## Main Product Behavior

- The app downloads YouTube videos and playlists.
- Default save folder should be the user's Windows `Downloads` folder.
- The user must be able to change the download folder inside the app.
- The app must support `cookies.txt` for restricted or sign-in-required videos.
- The app should auto-detect `cookies.txt` in the app folder if present.
- The app should show a clear indicator for cookie status.
- If cookies are missing and a video likely needs them, show a helpful user-facing reminder.
- If a file already exists, download again with an automatic renamed filename instead of failing.

## UI Structure

Use a left sidebar and a main content area.

Sidebar pages:

- Downloader
- Library
- History
- Options
- Cookies
- About

Layout goals:

- Light theme by default
- Optional dark mode, but soft and premium rather than harsh black
- Resizable window
- Clean spacing
- Soft cards
- High-quality shadows
- Smooth transitions
- Hover states on clickable buttons except where intentionally avoided
- Modern, readable, eye-resting look

## Downloader Page

### Top Controls

Top controls should include:

- playlist toggle
- Paste button
- URL input
- Analyze button

Behavior:

- Analyze button text should animate between:
  - `Analyze`
  - `Analyzing...`
  - back to `Analyze`
- URL text should remain visible from the beginning, not shifted into the middle.
- Show a thin loading indicator during analyze.

### Video Info Area

After analyze, show:

- title
- estimated size
- thumbnail preview
- show thumbnail toggle
- cookie status row
- reset button

Before analyze:

- configuration should be hidden or disabled
- download button should be disabled

### Configuration

After analyze, populate:

- Format dropdown
- Quality dropdown
- subtitle options

Rules:

- Show only actually available formats for the current video
- Show only actually available qualities for the current video
- Always include Auto options
- Subtitle language should be a dropdown, not a text box
- `Embed subtitles` should not be enabled by default

For normal videos:

- `Auto` format should prefer MP4 if available
- If best MP4 is not available, use the next best compatible option

For playlists:

- Force Format to `Auto`
- Force Quality to `Auto (Best)`
- Make it clear that playlist mode uses automatic settings only

### Download Button

- Download button should remain disabled until analyze succeeds
- When downloads exist in pipeline, button text should change to `Downloading...`
- When no active, queued, or paused tasks remain, button text should return to `Start Download`

### Reset Behavior

- Reset should fully clear downloader-page state
- If reset is clicked during downloads, it must cancel the entire pipeline, not just the active item

## Download Rules

### Single Video Downloads

- Support best available download
- Prefer high quality
- Use cookies if needed
- Show progress, speed, and downloaded size

### Playlist Downloads

Playlist behavior must be explicit and stable:

- Process playlist videos one by one
- Keep `1` active downloading item
- Keep up to `4` queued items visible
- Show each visible playlist video as its own row
- Active item should appear at the top
- Queued items should appear below it

If more items exist than visible rows:

- queue continues internally
- UI should scroll when needed

Playlist reset behavior:

- Reset must cancel:
  - active item
  - queued items
  - paused items
  - playlist session state

## Active Download Row Behavior

Each row in active downloads should show:

- title
- progress bar
- speed
- downloaded MB
- action buttons

Per-item actions:

- Pause
- Resume when paused
- Cancel for that specific item
- Open Folder when completed

If a title is too long:

- avoid breaking layout
- use a marquee-style or equivalent readable overflow treatment

When a row completes:

- it should smoothly slide and fade out
- it should then move into completed history records

When a row fails:

- show a clear failed state
- continue playlist flow where appropriate

## Library and History Rules

### Library

Library is for non-completed pipeline items only:

- active downloads
- queued downloads
- paused downloads
- failed downloads

It should not be blank-looking; it needs a real wrapper/card layout similar in quality to other pages.

### History

History is for completed downloads only.

History behavior:

- newest items first
- searchable
- item card shows:
  - thumbnail
  - title
  - saved file name
  - Open Folder
  - Remove
  - Delete File

Also support:

- clear history only, without deleting files
- delete file + history entry together

## Cookies Support

Cookies page should include:

- Set Cookies File
- Clear Cookies File
- How To Add Cookies
- cookie loaded / not loaded indicator

Rules:

- Never expose cookie contents
- Never encourage sharing cookies
- If cookies are missing or expired, explain clearly
- For cookie-related failures, show user-friendly messages instead of raw technical errors where possible

## Notifications and Tray Behavior

Use modern toast notifications.

Rules:

- Avoid aggressive red styling unless truly necessary
- If the user closes the window while downloads are active:
  - minimize to tray instead of fully closing
- If the user closes app with no active downloads:
  - close normally
- If the user chooses `Quit` from the tray:
  - stop all downloads
  - cancel the full pipeline
  - close app completely
- Avoid redundant completion notifications when app is already visible and active

## Options Page

Options must include:

- download folder selector
- max concurrent downloads
- speed limit
- install essentials (`ffmpeg`)
- update settings
- dark mode toggle

Rules:

- max concurrent downloads can go up to `10`
- update manifest URL can exist as an advanced setting
- explanatory text should stay short and readable
- layout must visually match the rest of the app
- typography must remain crisp and normal, not blurry or stroked-looking

## Update System

- Add update check support using GitHub releases
- Repo should remain private until intentionally made public
- Support optional update checking
- Support optional auto-download updates
- Do not auto-publish releases

## Error Handling and Stability

- Add logging
- Avoid silent failures
- Add retry logic where reasonable for network operations
- Detect and surface:
  - network failures
  - cookie/sign-in failures
  - ffmpeg missing
  - invalid links
  - unavailable videos
- Avoid crashes from late worker-thread completions
- Avoid queue deadlocks
- Playlist handling must remain stable even with very large playlists
- If YouTube rate-limits or blocks access, fail gracefully and continue where possible

## Testing Requirements

After major features, run:

- compile checks
- import checks
- startup smoke tests

Before packaging, verify:

- UI opens
- analyze works
- single download works
- playlist queue works
- cookies load correctly
- history works
- installer builds

Always report:

- what passed
- what failed
- what still needs manual UI validation

## Packaging

- Build a Windows installer, not just a loose executable
- Output installer into `dist_installer`
- Keep build artifacts out of Git where appropriate
- Push source changes to the configured GitHub repo
- Keep the GitHub repo private unless intentionally changed

## Design Direction

The design should feel:

- light-mode-first
- premium
- calm
- modern
- eye-resting

Dark mode should be:

- softer
- elegant
- not overly black

Use smooth micro-animations for:

- button text changes
- analyze state
- download state
- toast appearance
- completed row removal

## Asset / Input Checklist

To rebuild this app from scratch efficiently, provide:

- app name
- icon files
- target platform
- preferred tech stack
- GitHub repo URL
- exact wording for About / Terms / Privacy if needed
- any special UI preferences beyond this document

## Success Definition

The app is considered successful when:

- single video downloads work reliably
- playlist downloads are stable and understandable
- cookies workflow is clear and useful
- Library cleanly reflects active queue state
- History cleanly reflects completed downloads
- tray behavior is sensible
- packaging works
- the UI feels polished and intentional
