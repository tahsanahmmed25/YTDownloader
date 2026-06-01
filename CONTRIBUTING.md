# Contributing to YTDownloaderPro

First off, thank you for considering contributing to YTDownloaderPro! It's people like you who make this a great utility for everyone.

By contributing to this repository, you agree to license your work under the **Custom License** terms.

---

## Table of Contents
1. [Code of Conduct](#code-of-conduct)
2. [How Can I Contribute?](#how-can-i-contribute)
   - [Reporting Bugs](#reporting-bugs)
   - [Suggesting Features](#suggesting-features)
   - [Pull Requests](#pull-requests)
3. [Local Development Setup](#local-development-setup)
   - [Dependencies](#dependencies)
   - [Running the App](#running-the-app)
   - [Running Tests](#running-tests)
4. [Coding Style & Standards](#coding-style--standards)
5. [Building Releases Locally](#building-releases-locally)

---

## Code of Conduct

We aim to foster an open, welcoming, and inclusive community. Please ensure that all interactions in issues, pull requests, and discussions are polite, respectful, and professional.

---

## How Can I Contribute?

### Reporting Bugs
* Check the existing issues to ensure the bug hasn't already been reported.
* If it's a new issue, open a new **Bug Report** using the template.
* Include a clear description, reproduction steps, expected behavior, and log output (redacting any private details or credentials).

### Suggesting Features
* If you have an idea for a feature, open a **Feature Request** using the template.
* Explain the use case, why this feature would be valuable to users, and mockups/ideas if applicable.

### Pull Requests
1. Fork the repository and create your branch from `main`.
2. Keep your commits atomic, well-described, and clean.
3. Make sure all tests pass before submitting.
4. Open the Pull Request and fill out the PR template thoroughly.

---

## Local Development Setup

### Dependencies
* **Python 3.11 or 3.12** is recommended.
* On Linux, you will need build and runtime dependencies for Qt:
  ```bash
  sudo apt-get update
  sudo apt-get install -y libfuse2 libxcb-cursor0 libxcb-xinerama0 libxkbcommon-x11-0 libgl1
  ```

### Running the App
1. Clone your fork:
   ```bash
   git clone https://github.com/tahsanahmmed25/YTDownloaderPro.git
   cd YTDownloaderPro
   ```
2. Set up a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Linux
   # .venv\Scripts\activate   # Windows
   ```
3. Install dependencies:
   ```bash
   pip install --upgrade pip
   pip install -r requirements-dev.lock
   ```
4. Run the application:
   ```bash
   python app.py
   ```

### Running Tests
Automated tests are powered by `pytest`. Run them with:
```bash
python -m pytest
```
Please ensure all 34 tests pass before opening a PR. If you write new functions or change existing logic, write corresponding unit tests under the `tests/` directory.

---

## Coding Style & Standards

* **PEP 8 Compliance**: Follow standard Python coding conventions.
* **Keep Code Clean**: Do not leave commented-out debug code. Keep functions focused and modular.
* **Documentation**: Maintain existing comments and docstrings. Document new public methods.
* **Security & Privacy**: 
  * Do not expose credentials or keys in tests/logs.
  * Subprocesses should be run securely (use argument lists, avoid `shell=True`).
  * Private data/files should use Owner-only permissions (`0o600`).

---

## Building Releases Locally

If you want to verify that your changes do not break packaging:

### Linux (AppImage)
```bash
export APPIMAGETOOL_SHA256="b90f4a8b18967545fda78a445b27680a1642f1ef9488ced28b65398f2be7add2"
./build_release.sh
```

### Windows (Inno Setup)
Make sure you have [Inno Setup 6](https://jrsoftware.org/isinfo.php) installed on your Windows machine, then run:
```powershell
$env:YTDL_FFMPEG_WIN_ZIP_SHA256 = "<verified_sha256>"
.\build_release.ps1
```
