#!/usr/bin/env bash
# build_release.sh — Linux build script for YTDownloader
# Produces: dist/YTDownloader.AppImage
# Run from the project root: ./build_release.sh

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [[ "${YTDL_LOCAL_DEV_MODE:-false}" == "true" ]]; then
    export PATH="$SCRIPT_DIR/tools/bin:$PATH"
fi
# ── Colours ──────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { echo -e "${GREEN}[build]${NC} $*"; }
warn()  { echo -e "${YELLOW}[warn]${NC}  $*"; }
error() { echo -e "${RED}[error]${NC} $*"; exit 1; }

# ── Python ───────────────────────────────────────────────────────────────────
if [[ -f ".venv/bin/python" ]]; then
    PYTHON="$SCRIPT_DIR/.venv/bin/python"
    info "Using local .venv Python: $PYTHON"
elif [[ -f "venv/bin/python" ]]; then
    PYTHON="$SCRIPT_DIR/venv/bin/python"
    info "Using venv Python: $PYTHON"
elif command -v python3 &>/dev/null; then
    PYTHON="$(command -v python3)"
    info "Using system Python: $PYTHON"
else
    error "Python 3 not found. Install it or create a venv."
fi

pip_install() { "$PYTHON" -m pip install --quiet "$@"; }

info "Installing pinned build dependencies..."
pip_install -r requirements-dev.lock

info "Running tests..."
"$PYTHON" -m pytest

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
if [[ "${YTDL_LOCAL_DEV_MODE:-false}" == "true" ]]; then
    APPIMAGETOOL="$SCRIPT_DIR/tools/bin/appimagetool-x86_64.AppImage"
else
    APPIMAGETOOL="$SCRIPT_DIR/appimagetool-x86_64.AppImage"
fi

if [[ ! -f "$APPIMAGETOOL" ]]; then
    info "Downloading appimagetool..."
    : "${APPIMAGETOOL_SHA256:?Set APPIMAGETOOL_SHA256 before building verified AppImages.}"
    curl --fail --location --proto '=https' --tlsv1.2 -o "$APPIMAGETOOL" \
        "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"
fi
: "${APPIMAGETOOL_SHA256:?Set APPIMAGETOOL_SHA256 before building verified AppImages.}"
echo "${APPIMAGETOOL_SHA256}  ${APPIMAGETOOL}" | sha256sum -c -
chmod +x "$APPIMAGETOOL"

# ── Build AppImage ────────────────────────────────────────────────────────────
OUTPUT="$SCRIPT_DIR/dist_installer/YTDownloader-linux-x86_64.AppImage"
mkdir -p "$SCRIPT_DIR/dist_installer"

info "Building AppImage → $OUTPUT ..."
ARCH=x86_64 "$APPIMAGETOOL" "$APPDIR" "$OUTPUT"
sha256sum "$OUTPUT" | tee "$SCRIPT_DIR/dist_installer/SHA256SUMS-linux.txt"

info "✅  Done! AppImage: $OUTPUT"
info "    Size: $(du -sh "$OUTPUT" | cut -f1)"
