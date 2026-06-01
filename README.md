<h1 align="center">YT Downloader Pro</h1>

<p align="center"><b>A clean, fast YouTube downloader for Windows, Linux, and macOS.</b></p>

<p align="center">
  ⚠️ Always download from the official source: <a href="https://github.com/tahsanahmmed25/YTDownloaderPro">github.com/tahsanahmmed25/YTDownloaderPro</a>
</p>

<p align="center">
  <a href="https://github.com/tahsanahmmed25/YTDownloaderPro/releases/latest"><img src="https://img.shields.io/github/v/release/tahsanahmmed25/YTDownloaderPro?label=latest" alt="Latest Release"></a>
  <a href="https://github.com/tahsanahmmed25/YTDownloaderPro/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-Custom-red" alt="License"></a>
  <a href="https://github.com/tahsanahmmed25/YTDownloaderPro/actions/workflows/build.yml"><img src="https://github.com/tahsanahmmed25/YTDownloaderPro/actions/workflows/build.yml/badge.svg" alt="Build Status"></a>
</p>

---

## Download

Get the latest version from the **[Releases page](https://github.com/tahsanahmmed25/YTDownloaderPro/releases/latest)**:

| Platform | File | Notes |
| -------- | ---- | ----- |
| 🐧 Linux (Ubuntu, Fedora, Zorin…) | `YTDownloaderPro-linux-x86_64.AppImage`<br>`YTDownloaderPro-linux-amd64.deb`<br>`YTDownloaderPro-linux-x86_64.rpm`<br>`YTDownloaderPro-linux-x86_64.tar.gz` | **AppImage:** Run directly (no install)<br>**DEB:** Ubuntu/Debian/Mint installer<br>**RPM:** Fedora/RHEL/openSUSE installer<br>**TAR.GZ:** Portable binary |
| 🪟 Windows 10/11 | `YTDownloaderPro-Setup.exe`<br>`YTDownloaderPro-windows-x64.msi`<br>`YTDownloaderPro-windows-x64.zip` | **Setup.exe:** Installer with shortcuts<br>**MSI:** Enterprise/silent install<br>**ZIP:** Portable standalone folder |
| 🍎 macOS 12+ | `YTDownloaderPro-macOS.dmg`<br>`YTDownloaderPro-macOS.app.tar.gz` | **DMG:** Open DMG, drag to Applications<br>**TAR.GZ:** Portable standalone app bundle |

> Windows SmartScreen or Linux may warn "unknown publisher" — this is expected for unsigned builds. Verify the SHA256 checksum from the release page before running.

---

## Features

- Paste a YouTube URL, pick quality and format, download
- **Qualities:** 144p up to 4K — or Auto (Best)
- **Formats:** MP4, MKV, WebM, MP3, AAC and more
- **Subtitles:** download and embed into video files
- **Playlist support** with queue management and per-item progress
- **Downloads page** — active, queued, paused, and completed
- **History** with thumbnails and search
- **4 themes:** Teal Clarity, Indigo Focus, Amber Warmth, Slate Mono
- **Light and dark mode**
- **Restricted Mode** — for age-restricted or members-only videos using your YouTube session

---

## 🐧 Linux Quick Start

```bash
# 1. Download the AppImage from the Releases page
# 2. Make it executable
chmod +x YTDownloaderPro-linux-x86_64.AppImage
# 3. Run it
./YTDownloaderPro-linux-x86_64.AppImage
```

Or right-click in your file manager → Properties → Permissions → Allow executing as program.

**Optional — install system yt-dlp and FFmpeg for faster startup:**
```bash
sudo apt install yt-dlp ffmpeg
```

**If AppImage won't open:**
```bash
sudo apt install libfuse2 libxcb-cursor0 libxcb-xinerama0 libxkbcommon-x11-0 libgl1
```

---

## 🪟 Windows Quick Start

1. Download `YTDownloaderPro-Setup.exe` from the Releases page
2. Run the installer — you can install to any drive
3. If Windows SmartScreen warns "Unknown publisher", click **More info → Run anyway**
4. Launch from the Start Menu or Desktop shortcut

---

## 🍎 macOS Quick Start

1. Download `YTDownloaderPro-macOS.dmg` from the Releases page
2. Double-click the DMG and drag **YTDownloaderPro** into your **Applications** folder
3. Open it from your Applications folder
4. If macOS warns about an unsigned developer, right-click the app icon and select **Open**, or run:
   ```bash
   xattr -cr /Applications/YTDownloaderPro.app
   ```

---

## 🔒 Restricted Mode

For age-restricted or members-only videos, go to **Restricted Mode** in the sidebar and choose:

- **Login to YouTube** ⭐ — opens your browser, you log in normally, app extracts cookies automatically
- **Connect your browser** — reads your existing local browser session (Firefox is most reliable on Linux)
- **Manual cookies file** — export cookies.txt from your browser using a cookies extension

Your cookies never leave your computer.

---

## ⚙️ System Requirements

| | Linux | Windows | macOS |
| - | ----- | ------- | ----- |
| OS | Any 64-bit distro (Ubuntu 20.04+) | Windows 10/11 64-bit | macOS 12+ |
| CPU | x86_64 | x86_64 | Apple Silicon / Intel |
| RAM | 512 MB | 512 MB | 512 MB |
| Disk | 500 MB | 500 MB | 500 MB |

---

## 🛠️ Troubleshooting

**"yt-dlp is still setting up…"** — Wait a few seconds on first launch, it downloads automatically.

**Download failed / quality not available** — Try a lower quality or use Auto.

**"Sign in required"** — Enable Restricted Mode and use the Login to YouTube option.

**FFmpeg merge failed (Linux)** — Run `sudo apt install ffmpeg`.

**"Failed to decrypt browser cookies" on Linux** — Switch to Firefox or use the Login to YouTube option.

**macOS: "damaged" or "cannot be opened because developer cannot be verified"** — Right-click the app in Applications and click **Open**, or run: `xattr -cr /Applications/YTDownloaderPro.app`

---

## Developer Setup

```bash
git clone https://github.com/tahsanahmmed25/YTDownloaderPro.git
cd YTDownloaderPro
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-dev.lock
python -m pytest
python app.py
```

---

## 📄 License

Custom License — personal use only. Modification and commercial use are strictly prohibited. See [LICENSE](LICENSE).

**© 2026 Tahsan Ahmmed**
