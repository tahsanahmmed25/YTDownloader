<div align="center">

# YTDownloader

**A clean, fast YouTube downloader with a desktop UI — for Windows and Linux.**

**Private Beta:** This is a personal project by Tahsan, currently shared as a private beta. Builds are unsigned, may trigger OS/browser warnings, and should only be installed by testers who trust the private repository source.

[![Build](https://github.com/tahsanahmmed25/YTDownloader/actions/workflows/build.yml/badge.svg)](https://github.com/tahsanahmmed25/YTDownloader/actions/workflows/build.yml)
[![Release](https://img.shields.io/github/v/release/tahsanahmmed25/YTDownloader?label=latest)](https://github.com/tahsanahmmed25/YTDownloader/releases/latest)
[![License](https://img.shields.io/github/license/tahsanahmmed25/YTDownloader)](LICENSE)

</div>

---

## 📥 Private Beta Download

Go to the private **[Releases page](https://github.com/tahsanahmmed25/YTDownloader/releases/latest)** and grab the file for your OS:

| Platform | File | Notes |
|---|---|---|
| 🐧 **Linux** (Zorin OS, Ubuntu, Mint…) | `YTDownloader-linux-x86_64.AppImage` | Just download & run — no installation needed |
| 🪟 **Windows 10/11** | `YTDownloader-Setup.exe` | Run the installer, choose your install drive |

> **Unsigned beta warning:** Windows SmartScreen and some Linux desktop environments may warn that this app is from an unknown publisher. That is expected for this private beta because the builds are not code-signed yet.

> **Security note:** Verify release checksums when they are published. The in-app updater blocks installer downloads unless release metadata contains a valid `installer_sha256` value for the selected platform.

---

## Production Hardening Status

This project has production-hardening in place and is prepared for private beta testing, but it is not yet fully production-grade. Current safeguards include pinned direct dependencies, automated tests, SQLite-backed queue/history storage, safer archive extraction, private cookie files, keyring-backed session/proxy secrets when available, redacted logs, and checksum-gated update installs.

Known remaining work before a strict production release includes code signing for Windows/AppImage releases, signed update manifests, complete hash pinning for all third-party binary mirrors, a fully generated transitive lock file or hash-locked install workflow, and broader GUI/e2e coverage.

---

## 🐧 Linux — Quick Start (Zorin OS / Ubuntu)

1. Download `YTDownloader-linux-x86_64.AppImage` from the Releases page.
2. Open a terminal and make it executable:
   ```bash
   chmod +x YTDownloader-linux-x86_64.AppImage
   ```
3. Run it:
   ```bash
   ./YTDownloader-linux-x86_64.AppImage
   ```
   Or right-click the file in your file manager → **Run as Program**.
4. On first launch the app will use system **yt-dlp**/**FFmpeg** when available and may download managed copies when needed.

> **Tip — install yt-dlp and FFmpeg system-wide (optional but faster):**
> ```bash
> sudo apt install yt-dlp ffmpeg
> ```
> If these are already installed, the app uses them directly and skips the download.

> **Tip — Zorin OS desktop shortcut:** Right-click the AppImage → *Properties* → *Permissions* → enable "Allow executing as program". You can then double-click it like any normal app.

---

## 🪟 Windows — Quick Start

1. Download `YTDownloader-Setup.exe` from the Releases page.
2. Run the installer.
   - You can choose **any drive** as the install location (D:, E:, etc.) — the app stores everything there.
   - Windows SmartScreen may warn "Unknown publisher". Click **More info → Run anyway**. This warning appears because the app isn't code-signed yet.
3. Launch **YTDownloader** from the Start Menu or Desktop shortcut.
4. On first launch the app prepares **yt-dlp** and **FFmpeg** in the background when they are not already bundled or available.

---

## ✨ Features

- **Paste a YouTube URL** → instantly shows title, thumbnail, estimated size, and available qualities
- **Video qualities:** Auto (Best), 720p, 1080p, 2K, 4K
- **Formats:** MP4, MKV, WEBM, or Auto
- **Playlist downloads** with queue management, pause/resume, and per-item progress
- **Subtitles:** download and optionally embed into the video file
- **Download history** with thumbnails, re-download, and search
- **Auto-update for yt-dlp** — checked regularly with SHA256 verification for managed binary downloads
- **Auto-update for FFmpeg** — managed with HTTPS source validation and optional pinned SHA256 environment checks
- **Light and dark themes**
- **Two access modes:**
  - `Normal Mode` — for public videos (no cookies needed)
  - `Restricted Mode` — for age-gated or members-only videos (uses your YouTube session)

---

## 🗂️ Where files are stored

| Item | Windows | Linux |
|---|---|---|
| App binaries | Your chosen install folder | Read-only AppImage |
| yt-dlp / FFmpeg | Next to the app `.exe` | `~/.local/share/YTDownloader/bin/` |
| History & cache | `{install folder}\.data\YTDownloader\` | `~/.local/share/YTDownloader/.data/` |
| Downloaded videos | Your chosen download folder (default: `~/Downloads`) | Same |

---

## 🔒 Restricted Mode (Cookie-based auth)

Some videos require a YouTube login (age-restricted, members-only, private). To download these, go to **Preferences → Cookies** and choose one of three methods:

### Option 1 — Login to YouTube (Most Reliable 🌟)
1. Click **Open YouTube Login** — your default system browser opens to the Google sign-in page.
2. Log in to your Google/YouTube account normally.
3. Return to YTDownloader and click **I'm Logged In ✓**.
4. The app automatically extracts your session cookies in the background. The status shows **✅ Logged in** when complete.

Your session is saved and automatically restored next time you open the app. Click **Logout** to clear it.

> **Why this approach is used:** You log in using your own browser — no embedded Chromium and no password collection. Browser cookie extraction can still fail if the browser profile is locked or the OS keyring blocks access.

When a browser locks its cookie database, the app may ask whether it should force-close that browser. This behavior is intentional, but it now requires explicit confirmation and warns that all matching browser windows/processes will be closed.

### Option 2 — Connect your local browser
Select your browser (Chrome, Firefox, Brave, etc.) and click **Connect Browser**. The app reads your existing local session directly.

> **Linux tip:** Firefox is the most reliable choice on Linux. Chrome/Edge cookies use the GNOME system keyring which can sometimes block automated extraction.

### Option 3 — Manual Cookies File
1. Install a cookies export extension in your browser (e.g. *Get cookies.txt LOCALLY*).
2. Log in to YouTube, then export cookies in Netscape format as `cookies.txt`.
3. In the Cookies tab, click **Set Cookies File** and select the file.
4. Keep the file private — refresh it if it expires.

> **Privacy:** Cookies never leave your computer. The app reads them locally to pass authentication to yt-dlp. Never share your cookies with anyone.

Managed session cookies are stored in the OS keyring when available and materialized to a private `cookies.txt` cache only because yt-dlp requires a file path. Proxy passwords are also kept out of QSettings where keyring support is available.

---

## Developer Setup

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.lock
python -m pytest
```

The lock files currently pin direct dependencies. Treat dependency updates as release work: update deliberately, run the test suite, rebuild installers, regenerate checksums, and review vulnerability-scan output.

---

## Release Policy

- CI must pass tests before release artifacts are built.
- Release installers must publish SHA256 checksum files.
- In-app update metadata must include `installer_sha256: <64 hex chars>` in the GitHub release body or manifest.
- Custom update URLs are disabled by default. Set `YTDL_ALLOW_CUSTOM_UPDATE_URL=true` only for development/staging.
- Windows and Linux release channels should be promoted Dev → Staging → Production with a rollback tag kept available.

---

## ⚙️ System Requirements

| | Linux | Windows |
|---|---|---|
| OS | Any 64-bit distro (Zorin, Ubuntu 20.04+, Mint…) | Windows 10/11 (64-bit) |
| CPU | x86_64 | x86_64 |
| RAM | 512 MB | 512 MB |
| Disk | 500 MB free | 500 MB free |
| Internet | Required | Required |

---

## 🛠️ Troubleshooting

**"yt-dlp is still setting up…"**
> The app downloads yt-dlp automatically on first launch. Wait a few seconds and try again.

**"This file is unknown and dangerous" (Windows SmartScreen)**
> This is a false positive — the app isn't code-signed yet. Click **More info → Run anyway** to proceed. The app is safe.

**Video won't download / quality not available**
> Try a lower quality or use **Auto**. The app automatically picks the best available quality at or below your selected resolution.

**FFmpeg merge failed**
> Go to **Preferences** and click **Install FFmpeg**. Or on Linux: `sudo apt install ffmpeg`.

**Download failed with "Sign in required" or "Video unavailable"**
> Enable **Restricted Mode** in the Cookies tab. Use **Option 2 (Internal Login)** for the most reliable result on all platforms.

**"Failed to decrypt browser cookies" (Linux with Chrome/Edge)**
> Chrome/Edge cookies on Linux use the GNOME system keyring, which can block automated extraction. Switch to **Firefox** in the browser selector, or use the **Internal Login** option instead.

**Linux: AppImage won't open**
> Make sure FUSE is installed: `sudo apt install libfuse2`

**Linux: double-clicking does nothing**
> In your file manager, right-click the AppImage → Properties → Permissions → enable "Allow executing as program".

---

## 👩‍💻 Development Setup

```bash
# 1. Clone the repo
git clone https://github.com/tahsanahmmed25/YTDownloader.git
cd YTDownloader

# 2. Create a virtual environment
python3 -m venv venv
source venv/bin/activate          # Linux
# venv\Scripts\activate           # Windows

# 3. Install pinned development/build dependencies
pip install -r requirements-dev.lock

# 4. Run tests, then the app
python -m pytest
python app.py
```

### Building a release

**Automated (GitHub Actions — recommended):**
```bash
git tag v2.0.5
git push origin v2.0.5
# GitHub builds both Windows + Linux automatically and publishes a release
```

**Linux (AppImage) — locally:**
```bash
export APPIMAGETOOL_SHA256=<verified appimagetool sha256>
./build_release.sh
```

**Windows (Inno Setup installer) — locally:**
```powershell
$env:YTDL_FFMPEG_WIN_ZIP_SHA256 = "<verified ffmpeg zip sha256>"
.\build_release.ps1
```

---


## 📋 Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history.

---

## 📄 License

See [LICENSE](LICENSE).
