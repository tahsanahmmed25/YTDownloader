<div align="center">

# YTDownloaderPro

**A clean, fast YouTube downloader with a desktop UI — for Windows and Linux.**

**Official Source Notice:** This is the official repository for YTDownloaderPro. To protect your system from fake, rebranded, or malicious copies, always check the source URL and download only from: [https://github.com/tahsanahmmed25/YTDownloaderPro](https://github.com/tahsanahmmed25/YTDownloaderPro).

[![Build](https://github.com/tahsanahmmed25/YTDownloaderPro/actions/workflows/build.yml/badge.svg)](https://github.com/tahsanahmmed25/YTDownloaderPro/actions/workflows/build.yml)
[![Release](https://img.shields.io/github/v/release/tahsanahmmed25/YTDownloaderPro?label=latest)](https://github.com/tahsanahmmed25/YTDownloaderPro/releases/latest)
[![License](https://img.shields.io/badge/license-Custom-blue)](LICENSE)

</div>

---

## Download

Go to the **[Releases page](https://github.com/tahsanahmmed25/YTDownloaderPro/releases/latest)** and grab the file for your OS:

| Platform | File | Notes |
|---|---|---|
| 🐧 **Linux** (Zorin OS, Ubuntu, Mint…) | `YTDownloaderPro-linux-x86_64.AppImage` | Just download & run — no installation needed |
| 🪟 **Windows 10/11** | `YTDownloaderPro-Setup.exe` | Run the installer, choose your install drive |

> **Unsigned warning:** Windows SmartScreen and some Linux desktop environments may warn that this app is from an unknown publisher. That is expected because the app is not signed with a paid certificate.

> **Security note:** Verify the SHA256 checksum before running the app. The in-app updater blocks installer downloads unless release metadata contains a valid `installer_sha256` value for the selected platform.

```bash
sha256sum YTDownloaderPro-linux-x86_64.AppImage
cat SHA256SUMS-linux.txt
```

```powershell
Get-FileHash .\YTDownloaderPro-Setup.exe -Algorithm SHA256
Get-Content .\SHA256SUMS-windows.txt
```

No warranty is provided. Use at your own risk.

---

## Readiness Status

This project has hardening in place, but it is not production-ready. Current safeguards include pinned direct dependencies, automated tests, SQLite-backed queue/history storage, safer archive extraction, private cookie files, keyring-backed session/proxy secrets when available, redacted logs, and checksum-gated update installs.

Paid code signing is not required for this unsigned release. Trust is handled through SHA256 checksums, transparent release notes, strict update hash checks, and optional GPG signing when practical. Remaining work before a strict production release includes signed update manifests, stronger third-party binary hash pinning, a fully generated transitive lock file or hash-locked install workflow, and broader GUI/e2e coverage.

---

## 🐧 Linux — Quick Start (Zorin OS / Ubuntu)

1. Download `YTDownloaderPro-linux-x86_64.AppImage` from the Releases page.
2. Open a terminal and make it executable:
   ```bash
   chmod +x YTDownloaderPro-linux-x86_64.AppImage
   ```
3. Run it:
   ```bash
   ./YTDownloaderPro-linux-x86_64.AppImage
   ```
   Or right-click the file in your file manager → **Run as Program**.
4. On first launch the app will use system **yt-dlp**/**FFmpeg** when available. 

> **Tip — install yt-dlp and FFmpeg system-wide (optional but faster):**
> ```bash
> sudo apt install yt-dlp ffmpeg
> ```
> If these are already installed, the app uses them directly and skips the download.

> **Tip — Zorin OS desktop shortcut:** Right-click the AppImage → *Properties* → *Permissions* → enable "Allow executing as program". You can then double-click it like any normal app.

---

## 🪟 Windows — Quick Start

1. Download `YTDownloaderPro-Setup.exe` from the Releases page.
2. Run the installer.
   - You can choose **any drive** as the install location (D:, E:, etc.) — the app stores everything there.
   - Windows SmartScreen may warn "Unknown publisher". Click **More info → Run anyway**. This warning appears because the app isn't code-signed yet.
3. Launch **YTDownloaderPro** from the Start Menu or Desktop shortcut.
4. On first launch the app prepares **yt-dlp** and **FFmpeg** in the background when they are not already bundled or available.

---

## ✨ Features

- **Homepage:** paste a YouTube URL, analyze metadata, choose quality/format, and start downloads
- **Video qualities:** Auto (Best), 720p, 1080p, 2K, 4K
- **Formats:** MP4, MKV, WEBM, or Auto
- **Playlist downloads** with queue management, pause/resume, and per-item progress
- **Subtitles:** download and optionally embed into the video file
- **Downloads page** for active, queued, paused, and completed downloads
- **History** with thumbnails, re-download, and search
- **Auto-update for yt-dlp** — checked regularly with SHA256 verification for managed binary downloads
- **FFmpeg support** — uses system FFmpeg when available; managed FFmpeg downloads use HTTPS
- **Light and dark themes**
- **Two access modes:**
  - `Normal Mode` — for public videos (no cookies needed)
  - `Restricted Mode` — for age-gated or members-only videos (uses your YouTube session)

---

## 🗂️ Where files are stored

| Item | Windows | Linux |
|---|---|---|
| App binaries | Your chosen install folder | Read-only AppImage |
| yt-dlp / FFmpeg | Next to the app `.exe` | `~/.local/share/YTDownloaderPro/bin/` |
| History & cache | `{install folder}\.data\YTDownloaderPro\` | `~/.local/share/YTDownloaderPro/.data/` |
| Downloaded videos | Your chosen download folder (default: `~/Downloads`) | Same |

---

## 🔒 Restricted Mode (Cookie-based auth)

Some videos require a YouTube login (age-restricted, members-only, private). To download these, go to **Preferences → Cookies** and choose one of three methods:

### Option 1 — Login to YouTube (Most Reliable 🌟)
1. Click **Open YouTube Login** — your default system browser opens to the Google sign-in page.
2. Log in to your Google/YouTube account normally.
3. Return to YTDownloaderPro and click **I'm Logged In ✓**.
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
- Pre-release version tags containing `-beta`, `-alpha`, or `-rc` must be published as prereleases.
- Release installers must publish SHA256 checksum files.
- In-app update metadata must include `installer_sha256: <64 hex chars>` in the GitHub release body or manifest.
- Custom update URLs are disabled by default. Set `YTDL_ALLOW_CUSTOM_UPDATE_URL=true` only for development/staging.
- Optional GPG signatures may be published alongside SHA256 files when practical.
- Windows and Linux release channels should be promoted Dev -> Staging -> Public with a rollback tag kept available.

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
> This warning is expected for unsigned builds. Verify the SHA256 checksum, then run the installer only if you trust the release source.

**Video won't download / quality not available**
> Try a lower quality or use **Auto**. The app automatically picks the best available quality at or below your selected resolution.

**FFmpeg merge failed**
> Go to **Preferences** and click **Install FFmpeg** if the release has a trusted FFmpeg SHA256 configured. On Linux, the simplest fix is usually: `sudo apt install ffmpeg`.

**Download failed with "Sign in required" or "Video unavailable"**
> Enable **Restricted Mode** in the Cookies tab. Use **Option 2 (Internal Login)** for the most reliable result on all platforms.

**"Failed to decrypt browser cookies" (Linux with Chrome/Edge)**
> Chrome/Edge cookies on Linux use the GNOME system keyring, which can block automated extraction. Switch to **Firefox** in the browser selector, or use the **Internal Login** option instead.

**Linux: AppImage won't open**
> Make sure FUSE is installed: `sudo apt install libfuse2`

**Linux: missing desktop/runtime libraries**
> Install the common AppImage/PySide runtime libraries: `sudo apt install libfuse2 libxcb-cursor0 libxcb-xinerama0 libxkbcommon-x11-0 libgl1`.

**Linux: double-clicking does nothing**
> In your file manager, right-click the AppImage → Properties → Permissions → enable "Allow executing as program".

---

## 👩‍💻 Development Setup

```bash
# 1. Clone the repo
git clone https://github.com/tahsanahmmed25/YTDownloaderPro.git
cd YTDownloaderPro

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
git tag v3.0.0
git push origin v3.0.0
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

## 🤝 How to Contribute

We welcome contributions of all sizes! To get started:

1. Read our **[Contributing Guidelines](CONTRIBUTING.md)** for developer setup, testing, and coding standards.
2. Check the existing **[Issues](https://github.com/tahsanahmmed25/YTDownloaderPro/issues)** or open a new one to discuss your ideas.
3. Submit a Pull Request targeting the `main` branch.

All contributors must respect code quality, write unit tests for new features, and ensure the entire test suite passes before submitting PRs.

## 📄 License

This project is licensed under the **Custom License — Personal use only. See LICENSE file.**
