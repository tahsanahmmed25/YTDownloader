# Deployment Guide for YTDownloaderPro

This project is hardened for unsigned releases, but it should not be treated as production-ready. Paid code signing is not a blocker for public unsigned builds; users must instead get clear unsigned-app warnings, SHA256 checksums, transparent release notes, and no-warranty language.

## Table of Contents
1. [Pre-Release Checklist](#pre-release-checklist)
2. [Building Release](#building-release)
3. [GitHub Setup](#github-setup)
4. [Distributing via GitHub Releases](#distributing-via-github-releases)
5. [Update System](#update-system)
6. [Maintenance & Versioning](#maintenance--versioning)

---

## Pre-Release Checklist

### Version Management
```bash
# Update version in these files:
1. app_config.py          → APP_VERSION = "3.0.0"
2. YTDownloaderPro.iss    → AppVersion=3.0.0
3. CHANGELOG.md           → release entry for 3.0.0
4. README.md              → current stable release text
```

### Code Quality
```bash
# Install pinned build/test dependencies
python -m pip install -r requirements-dev.lock

# Run syntax checks and tests
python -m py_compile $(git ls-files '*.py')
python -m pytest
python -m pip_audit -r requirements.txt -r requirements-dev.txt
```

### Testing
- [ ] Test on clean Windows 10/11
- [ ] Verify installer works (install/uninstall)
- [ ] Test core features (download, pause, resume)
- [ ] Check queue persistence
- [ ] Verify update check works and rejects missing/bad SHA256 metadata
- [ ] Test with/without cookies
- [ ] Test browser-lock handling and explicit force-close confirmation
- [ ] Test concurrent downloads
- [ ] Verify logs redact cookies, proxy credentials, tokens, and sensitive paths

### Required CI/Repository Variables

Set these before release builds:

```text
APPIMAGETOOL_SHA256=<sha256 of the exact appimagetool-x86_64.AppImage used by CI>
YTDL_FFMPEG_WIN_ZIP_SHA256=<sha256 of ffmpeg-release-essentials.zip>
YTDL_FFMPEG_LIN_TAR_SHA256=<sha256 of ffmpeg-master-latest-linux64-gpl.tar.xz, if managed Linux FFmpeg is enabled>
```

If these are missing, CI or runtime managed downloads should fail closed rather than consuming unverifiable external binaries. `YTDL_ALLOW_UNVERIFIED_FFMPEG_DOWNLOADS=true` is for local development only.

### Documentation
```markdown
- [ ] Update README.md with new features
- [ ] Create CHANGELOG.md entry
- [ ] Update FAQ section
- [ ] Add screenshots (if UI changed)
```

---

## Building Release

### Step 1: Clean Previous Builds
```powershell
Remove-Item .\build -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item .\dist -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item .\dist_installer -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item .\obf -Recurse -Force -ErrorAction SilentlyContinue
```

### Step 2: Build Executable
```powershell
# Install pinned build/test dependencies into the project environment
.\venv\Scripts\python.exe -m pip install -r requirements-dev.lock

# Run in PowerShell from the repo root
.\build_release.ps1

# Or without obfuscation (faster):
.\build_release.ps1 -NoObfuscate
```

This will:
1. Select `.\venv\Scripts\python.exe` when present, otherwise use the active Python
2. Install only pinned direct dependencies from the lock files
3. Run tests before release artifacts are built
4. Build executable with PyInstaller
5. Generate SHA256 checksums for release artifacts
6. Create Windows installer with Inno Setup

### Step 3: Verify Build
```bash
# Check if installer was created
ls dist_installer/*.exe

# Smoke-test the packaged EXE before distributing
$proc = Start-Process .\dist\YTDownloaderPro\YTDownloaderPro.exe -PassThru
Start-Sleep -Seconds 8
if (-not (Get-Process -Id $proc.Id -ErrorAction SilentlyContinue)) { throw "YTDownloaderPro exited early." }
Stop-Process -Id $proc.Id

# Confirm the GUI appears and stays open during the check

# Test installer locally (don't run in production dir)
# Use a VM or separate test directory
```

---

## GitHub Setup

### 1. Create GitHub Repository
```bash
# Initialize git (if not already)
git init
git add .
git commit -m "Initial commit: YTDownloaderPro v3.0.0"

# Add remote (replace with your username)
git remote add origin https://github.com/tahsanahmmed25/YTDownloaderPro.git
git branch -M main
git push -u origin main
```

### 2. Add License
Create `LICENSE` file (Custom License to protect code from commercial/redistribution use):
```markdown
Copyright (c) 2026 Tahsan Ahmmed
All rights reserved.
...
```

### 3. Create Release Notes Template
Create `CHANGELOG.md`:
```markdown
# Changelog

## [1.0.0] - 2026-03-12
### Added
- Pause/resume downloads
- Queue persistence
- Concurrent downloads (up to 5)
- System tray integration
- Speed limiting
- Disk space validation

### Fixed
- Issue with large playlist downloads
- Memory leak in concurrent mode

### Changed
- Improved UI responsiveness
- Better error messages

## [0.9.0] - 2026-03-01
### Initial Release
```

---

## Distributing via GitHub Releases

### Step 1: Create Release on GitHub
```bash
# Method A: Via GitHub Web UI
1. Go to: github.com/tahsanahmmed25/YTDownloaderPro
2. Click "Releases" tab
3. Click "Create a new release"
4. Fill details (see below)

# Method B: Via GitHub CLI
gh release create v3.0.0 \
  ./dist_installer/YTDownloaderPro-Setup.exe \
  --title "YTDownloaderPro v3.0.0" \
  --prerelease \
  --notes "Unsigned release. Verify SHA256 before running. See CHANGELOG.md for details."
```

### Step 2: Release Details Template

**Tag:** `v3.0.0`

**Title:** `YTDownloaderPro v3.0.0 - Unsigned Release`

**Description:**
```markdown
## YTDownloaderPro v3.0.0

This is an unsigned release of a personal project. Your system may show security warnings because the app is not signed with a paid certificate. Please verify the SHA256 checksum before running.

No warranty is provided. Use at your own risk.

### ✨ Features
- Modern UI with dark mode
- Pause & resume downloads
- Multiple concurrent downloads
- Download queue persistence
- System tray integration
- Speed limiting

### 📥 Installation
1. Download the installer or AppImage for your OS.
2. Verify SHA256 against the matching checksum file.
3. Run the installer/AppImage.

### 🔧 System Requirements
- Windows 10 or later
- 50 MB disk space
- Internet connection

### 📝 What's New
See [CHANGELOG.md](https://github.com/tahsanahmmed25/YTDownloaderPro/blob/main/CHANGELOG.md)

### 🐛 Found a Bug?
Report it: [Open Issue](https://github.com/tahsanahmmed25/YTDownloaderPro/issues)

### 🔐 Verification
SHA256: `<paste hash here>`

`installer_sha256: <paste 64-char platform installer hash here>`

To verify installer integrity:
\`\`\`powershell
Get-FileHash YTDownloaderPro-Setup.exe -Algorithm SHA256
\`\`\`
```

### Step 3: Upload Installer

**Files to upload:**
1. `YTDownloaderPro-Setup.exe` - Windows installer
2. `YTDownloaderPro-linux-x86_64.AppImage` - Linux AppImage
3. `SHA256SUMS-windows.txt` and `SHA256SUMS-linux.txt` - Security verification

### Step 4: Generate SHA256 Checksum
```powershell
# In PowerShell
Get-FileHash .\dist_installer\YTDownloaderPro-Setup.exe -Algorithm SHA256 | Format-List

# Copy output to release notes for security verification
```

---

## Update System

Your app already has update checking! Verify it works:

### 1. Update Manifest Format (GitHub Releases)
Your app expects JSON with:
```json
{
  "tag_name": "v3.0.0",
  "name": "v3.0.0",
  "prerelease": true,
  "assets": [
    {
      "name": "YTDownloaderPro-Setup.exe",
      "browser_download_url": "https://github.com/..."
    }
  ],
  "body": "Release notes here...\nmin_required_version: 1.0.0\ninstaller_sha256: abc123def456..."
}
```

### 2. Add to Release Notes
```markdown
## Installation & Updates

### Requirements
- Minimum required version: 1.0.0

### Installer SHA256
\`installer_sha256: 8a3c5f9b2d1e4a6c9f3b2e5d8a1c4f7b9e2d5a8c1f4b7e9d2c5a8b1e4f7a0c\`

### Update Instructions
The app automatically checks for updates on startup. When available, users can:
1. Accept update → Downloads & installs automatically
2. Skip update → Can check manually later
```

---

## Maintenance & Versioning

### Semantic Versioning (MAJOR.MINOR.PATCH)

```
3.0.0
├─ MAJOR (3) - Breaking changes (increment if user action needed)
├─ MINOR (0) - New features (backward compatible)
└─ PATCH (0) - Bug fixes (backward compatible)

Examples:
- v3.0.0 → v3.0.1: Bug fix
- v3.0.0 → v3.1.0: New feature
- v3.0.0 → v4.0.0: Major rewrite (breaking changes)
```

### Release Workflow

```
1. Code changes → Test locally
2. Update version numbers in all files
3. Update CHANGELOG.md
4. Commit & push: git push origin main
5. Create GitHub Release with installer
6. Users auto-update via built-in updater
```

### Continuous Improvements

**Low-effort, high-value additions:**
- [ ] Keyboard shortcuts (Ctrl+V, Ctrl+Q)
- [ ] Delete file from Downloads
- [ ] Tray notifications
- [ ] Remember last quality preference
- [ ] Estimated time remaining

---

## Advanced: Auto-Build with GitHub Actions (Optional)

Create `.github/workflows/build.yml`:
```yaml
name: Build Release
on:
  push:
    tags:
      - 'v*'

jobs:
  build:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.12'
      - run: python -m venv venv
      - run: .\venv\Scripts\python.exe -m pip install -r requirements-dev.lock
      - run: .\build_release.ps1 -NoObfuscate
      - uses: ncipollo/release-action@v1
        with:
          artifacts: "dist_installer/YTDownloaderPro-Setup.exe"
          token: ${{ secrets.GITHUB_TOKEN }}
```

This automatically builds & releases when you push a git tag like `git push origin v3.0.0`.

---

## Quick Reference: Release Checklist

```powershell
# 1. Update version
# Edit: app_config.py, YTDownloaderPro.iss, CHANGELOG.md, README.md

# 2. Update changelog
# Edit: CHANGELOG.md

# 3. Install deps into the project environment
.\venv\Scripts\python.exe -m pip install -r requirements-dev.lock

# 4. Build
.\build_release.ps1

# 5. Smoke test the built EXE
$proc = Start-Process .\dist\YTDownloaderPro\YTDownloaderPro.exe -PassThru
Start-Sleep -Seconds 8
if (-not (Get-Process -Id $proc.Id -ErrorAction SilentlyContinue)) { throw "YTDownloaderPro exited early." }
Stop-Process -Id $proc.Id

# 6. Confirm the GUI appears and stays open during the check

# 7. Git commit
git add .
git commit -m "Release v3.0.0"
git tag v3.0.0
git push origin main --tags

# 8. Create GitHub Release
# - Go to GitHub.com
# - Create Release from tag
# - Upload installer
# - Add release notes with unsigned release warning, SHA256 checksum, and no-warranty text

# 9. Users get auto-update notification
# Done! 🎉
```

---

## Resources

- **GitHub**: https://github.com (free hosting)
- **Semantic Versioning**: https://semver.org
- **Inno Setup Docs**: https://jrsoftware.org/isinfo.php
- **PyInstaller**: https://pyinstaller.org
- **Best Practices**: https://keepachangelog.com

---

**Unsigned release rule:** release only after tests, checksums, AppImage smoke checks, and release notes pass. Do not call the app production-ready.
