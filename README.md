<div align="center">

# YTDownloader

**A clean, fast YouTube downloader with a desktop UI — for Windows and Linux.**

[![Build](https://github.com/tahsanahmmed25/YTDownloader/actions/workflows/build.yml/badge.svg)](https://github.com/tahsanahmmed25/YTDownloader/actions/workflows/build.yml)
[![Release](https://img.shields.io/github/v/release/tahsanahmmed25/YTDownloader?label=latest)](https://github.com/tahsanahmmed25/YTDownloader/releases/latest)
[![License](https://img.shields.io/github/license/tahsanahmmed25/YTDownloader)](LICENSE)

</div>

---

## 📥 Download

Go to the **[Releases page](https://github.com/tahsanahmmed25/YTDownloader/releases/latest)** and grab the file for your OS:

| Platform | File | Notes |
|---|---|---|
| 🐧 **Linux** (Zorin OS, Ubuntu, Mint…) | `YTDownloader-linux-x86_64.AppImage` | Just download & run — no installation needed |
| 🪟 **Windows 10/11** | `YTDownloader-Setup.exe` | Run the installer, choose your install drive |

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
4. On first launch the app will automatically download **yt-dlp** and **FFmpeg** if they aren't already installed on your system.

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
4. On first launch the app automatically downloads **yt-dlp** and **FFmpeg** in the background.

---

## ✨ Features

- **Paste a YouTube URL** → instantly shows title, thumbnail, estimated size, and available qualities
- **Video qualities:** Auto (Best), 720p, 1080p, 2K, 4K
- **Formats:** MP4, MKV, WEBM, or Auto
- **Playlist downloads** with queue management, pause/resume, and per-item progress
- **Subtitles:** download and optionally embed into the video file
- **Download history** with thumbnails, re-download, and search
- **Auto-update for yt-dlp** — checked regularly, updated silently in the background
- **Auto-update for FFmpeg** — managed silently in the background
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

> **Why this works everywhere:** You log in using your own browser — no embedded Chromium, no sandbox restrictions, no GPU driver conflicts. Works 100% on Linux, Windows, and all AppImage environments.

### Option 2 — Connect your local browser
Select your browser (Chrome, Firefox, Brave, etc.) and click **Connect Browser**. The app reads your existing local session directly.

> **Linux tip:** Firefox is the most reliable choice on Linux. Chrome/Edge cookies use the GNOME system keyring which can sometimes block automated extraction.

### Option 3 — Manual Cookies File
1. Install a cookies export extension in your browser (e.g. *Get cookies.txt LOCALLY*).
2. Log in to YouTube, then export cookies in Netscape format as `cookies.txt`.
3. In the Cookies tab, click **Set Cookies File** and select the file.
4. Keep the file private — refresh it if it expires.

> **Privacy:** Cookies never leave your computer. The app reads them locally to pass authentication to yt-dlp. Never share your cookies with anyone.

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

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the app
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
pip install pyinstaller PySide6 PySide6-WebEngine requests browser-cookie3 yt-dlp
python -m PyInstaller --clean -y YTDownloader_linux.spec
# Then package the dist/ folder into an AppImage
```

**Windows (Inno Setup installer) — locally:**
```powershell
pip install pyinstaller PySide6 PySide6-WebEngine requests browser-cookie3 yt-dlp
python -m PyInstaller --clean -y YTDownloader.spec
# Then run YTDownloader.iss with Inno Setup
```

---


## 📋 Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history.

---

## 📄 License

See [LICENSE](LICENSE).
