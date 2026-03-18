# 🚀 Professional Deployment Guide for YTDownloader

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
1. app_config.py          → APP_VERSION = "1.0.0"
2. YTDownloader.iss       → AppVersion=1.0.0
3. YTDownloader.spec      → version='1.0.0'
4. YTDownloader_obf.spec  → version='1.0.0'
```

### Code Quality
```bash
# Run linter
pip install pylint
pylint ui/*.py downloader.py workers.py *.py --disable=too-many-lines,too-many-arguments

# Remove test files before build
rm -Force tmp_*.py, out.txt, links.txt, cookies.txt, history.json
```

### Testing
- [ ] Test on clean Windows 10/11
- [ ] Verify installer works (install/uninstall)
- [ ] Test core features (download, pause, resume)
- [ ] Check queue persistence
- [ ] Verify update check works
- [ ] Test with/without cookies
- [ ] Test concurrent downloads

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
# Run in PowerShell (as Administrator recommended)
.\build_release.ps1

# Or without obfuscation (faster):
.\build_release.ps1 -NoObfuscate
```

This will:
1. Install PyInstaller (if needed)
2. Optionally obfuscate code with PyArmor
3. Build executable with PyInstaller
4. Create Windows installer with Inno Setup

### Step 3: Verify Build
```bash
# Check if installer was created
ls dist_installer/*.exe

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
git commit -m "Initial commit: YTDownloader v1.0.0"

# Add remote (replace with your username)
git remote add origin https://github.com/tahsanahmmed25/YTDownloader.git
git branch -M main
git push -u origin main
```

### 2. Add License
Create `LICENSE` file (MIT recommended for free software):
```markdown
MIT License

Copyright (c) 2026 Tahsan

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction...
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
1. Go to: github.com/tahsanahmmed25/YTDownloader
2. Click "Releases" tab
3. Click "Create a new release"
4. Fill details (see below)

# Method B: Via GitHub CLI
gh release create v1.0.0 \
  ./dist_installer/YTDownloader-Setup.exe \
  --title "YTDownloader v1.0.0" \
  --notes "See CHANGELOG.md for details"
```

### Step 2: Release Details Template

**Tag:** `v1.0.0`

**Title:** `YTDownloader v1.0.0 - Release`

**Description:**
```markdown
## 🎉 YTDownloader v1.0.0

### ✨ Features
- Modern UI with dark mode
- Pause & resume downloads
- Multiple concurrent downloads
- Download queue persistence
- System tray integration
- Speed limiting

### 📥 Installation
1. Download `YTDownloader-Setup-1.0.0.exe`
2. Run installer
3. Follow prompts
4. Done! App starts automatically

### 🔧 System Requirements
- Windows 10 or later
- 50 MB disk space
- Internet connection

### 📝 What's New
See [CHANGELOG.md](https://github.com/tahsanahmmed25/YTDownloader/blob/main/CHANGELOG.md)

### 🐛 Found a Bug?
Report it: [Open Issue](https://github.com/tahsanahmmed25/YTDownloader/issues)

### 🔐 Verification
SHA256: `<paste hash here>`

To verify installer integrity:
\`\`\`powershell
Get-FileHash YTDownloader-Setup-1.0.0.exe -Algorithm SHA256
\`\`\`
```

### Step 3: Upload Installer

**Files to upload:**
1. `YTDownloader-Setup-1.0.0.exe` - Main installer
2. `YTDownloader-v1.0.0-portable.zip` (optional) - No installation needed
3. `SHA256-Checksums.txt` - Security verification

### Step 4: Generate SHA256 Checksum
```powershell
# In PowerShell
Get-FileHash .\dist_installer\YTDownloader-Setup.exe -Algorithm SHA256 | Format-List

# Copy output to release notes for security verification
```

---

## Update System

Your app already has update checking! Verify it works:

### 1. Update Manifest Format (GitHub Releases)
Your app expects JSON with:
```json
{
  "tag_name": "v1.0.1",
  "name": "v1.0.1",
  "prerelease": false,
  "assets": [
    {
      "name": "YTDownloader-Setup-1.0.1.exe",
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
1.0.0
├─ MAJOR (1) - Breaking changes (increment if user action needed)
├─ MINOR (0) - New features (backward compatible)
└─ PATCH (0) - Bug fixes (backward compatible)

Examples:
- v1.0.0 → v1.0.1: Bug fix
- v1.0.0 → v1.1.0: New feature
- v1.0.0 → v2.0.0: Major rewrite (breaking changes)
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
- [ ] Delete file from library
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
      - run: pip install -r requirements.txt pyinstaller
      - run: .\build_release.ps1 -NoObfuscate
      - uses: ncipollo/release-action@v1
        with:
          artifacts: "dist_installer/YTDownloader-Setup.exe"
          token: ${{ secrets.GITHUB_TOKEN }}
```

This automatically builds & releases when you push a git tag like `git push origin v1.0.0`.

---

## Quick Reference: Release Checklist

```powershell
# 1. Update version
# Edit: app_config.py, YTDownloader.iss, .spec files

# 2. Update changelog
# Edit: CHANGELOG.md

# 3. Test
.\build_release.ps1

# 4. Git commit
git add .
git commit -m "Release v1.0.0"
git tag v1.0.0
git push origin main --tags

# 5. Create GitHub Release
# - Go to GitHub.com
# - Create Release from tag
# - Upload installer
# - Add release notes

# 6. Users get auto-update notification
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

**Your app is ready for professional distribution!** 🚀
