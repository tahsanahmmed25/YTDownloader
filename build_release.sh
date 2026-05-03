#!/usr/bin/env bash
# build_release.sh — Linux build script for YTDownloader
# Produces: dist/YTDownloader.AppImage
# Run from the project root: ./build_release.sh

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── Colours ──────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { echo -e "${GREEN}[build]${NC} $*"; }
warn()  { echo -e "${YELLOW}[warn]${NC}  $*"; }
error() { echo -e "${RED}[error]${NC} $*"; exit 1; }

# ── Python ───────────────────────────────────────────────────────────────────
if [[ -f "venv/bin/python" ]]; then
    PYTHON="$SCRIPT_DIR/venv/bin/python"
    info "Using venv Python: $PYTHON"
elif command -v python3 &>/dev/null; then
    PYTHON="$(command -v python3)"
    info "Using system Python: $PYTHON"
else
    error "Python 3 not found. Install it or create a venv."
fi

pip_install() { "$PYTHON" -m pip install --quiet "$@"; }

info "Installing/checking build dependencies..."
pip_install pyinstaller
pip_install PySide6 requests browser-cookie3 yt-dlp

# ── PyInstaller ───────────────────────────────────────────────────────────────
info "Running PyInstaller..."
"$PYTHON" -m PyInstaller --clean -y YTDownloader_linux.spec

DIST_DIR="$SCRIPT_DIR/dist/YTDownloader"
[[ -d "$DIST_DIR" ]] || error "PyInstaller output not found at $DIST_DIR"

# ── AppImage structure ────────────────────────────────────────────────────────
APPDIR="$SCRIPT_DIR/dist/YTDownloader.AppDir"
info "Building AppDir at $APPDIR ..."
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin"
mkdir -p "$APPDIR/usr/lib"

# Copy PyInstaller bundle
cp -r "$DIST_DIR"/. "$APPDIR/usr/bin/"

# Desktop entry (required by AppImage spec)
cat > "$APPDIR/YTDownloader.desktop" <<'EOF'
[Desktop Entry]
Name=YTDownloader
Exec=YTDownloader
Icon=YTDownloader
Type=Application
Categories=AudioVideo;Network;
Comment=Simple YouTube Downloader by Tahsan
EOF

# Icon
if [[ -f "$SCRIPT_DIR/icons/download.png" ]]; then
    cp "$SCRIPT_DIR/icons/download.png" "$APPDIR/YTDownloader.png"
else
    warn "icons/download.png not found; AppImage will have no icon."
fi

# AppRun launcher script
cat > "$APPDIR/AppRun" <<'APPRUN'
#!/bin/bash
HERE="$(dirname "$(readlink -f "${0}")")"
export PATH="$HERE/usr/bin:$PATH"
export LD_LIBRARY_PATH="$HERE/usr/lib:${LD_LIBRARY_PATH:-}"
exec "$HERE/usr/bin/YTDownloader" "$@"
APPRUN
chmod +x "$APPDIR/AppRun"

# ── appimagetool ─────────────────────────────────────────────────────────────
APPIMAGETOOL="$SCRIPT_DIR/appimagetool-x86_64.AppImage"
if [[ ! -f "$APPIMAGETOOL" ]]; then
    info "Downloading appimagetool..."
    curl -L -o "$APPIMAGETOOL" \
        "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"
    chmod +x "$APPIMAGETOOL"
fi

# ── Build AppImage ────────────────────────────────────────────────────────────
OUTPUT="$SCRIPT_DIR/dist_installer/YTDownloader-linux-x86_64.AppImage"
mkdir -p "$SCRIPT_DIR/dist_installer"

info "Building AppImage → $OUTPUT ..."
ARCH=x86_64 "$APPIMAGETOOL" "$APPDIR" "$OUTPUT"

info "✅  Done! AppImage: $OUTPUT"
info "    Size: $(du -sh "$OUTPUT" | cut -f1)"
