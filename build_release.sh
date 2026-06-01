#!/usr/bin/env bash
# build_release.sh — Linux build script for YTDownloaderPro
# Produces: dist/YTDownloaderPro.AppImage
# Run from the project root: ./build_release.sh

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [[ "${YTDL_LOCAL_DEV_MODE:-false}" == "true" ]]; then
    export PATH="$SCRIPT_DIR/tools/bin:$PATH"
fi
# ── Colours ──────────────────────────────────────────────────────────────────
bin_name() { echo -e "\033[0;32m[build]\033[0m $*"; }
info()  { echo -e "\033[0;32m[build]\033[0m $*"; }
warn()  { echo -e "\033[1;33m[warn]\033[0m  $*"; }
error() { echo -e "\033[0;31m[error]\033[0m $*"; exit 1; }

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
"$PYTHON" -m PyInstaller --clean -y YTDownloaderPro_linux.spec

DIST_DIR="$SCRIPT_DIR/dist/YTDownloaderPro"
[[ -d "$DIST_DIR" ]] || error "PyInstaller output not found at $DIST_DIR"

# ── AppImage structure ────────────────────────────────────────────────────────
APPDIR="$SCRIPT_DIR/dist/YTDownloaderPro.AppDir"
info "Building AppDir at $APPDIR ..."
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin"
mkdir -p "$APPDIR/usr/lib"

# Copy PyInstaller bundle
cp -r "$DIST_DIR"/. "$APPDIR/usr/bin/"

# Copy Qt plugins and libraries manually since PyInstaller might miss them on some setups
if [[ -d "$SCRIPT_DIR/.venv/lib/python3.12/site-packages/PySide6/Qt/plugins" ]]; then
    info "Copying PySide6 Qt plugins to AppDir..."
    mkdir -p "$APPDIR/usr/bin/_internal/PySide6/Qt"
    cp -r "$SCRIPT_DIR/.venv/lib/python3.12/site-packages/PySide6/Qt/plugins" "$APPDIR/usr/bin/_internal/PySide6/Qt/"
    info "Copying PySide6 Qt libraries to AppDir..."
    mkdir -p "$APPDIR/usr/bin/_internal/PySide6/Qt/lib"
    cp -rn "$SCRIPT_DIR/.venv/lib/python3.12/site-packages/PySide6/Qt/lib"/* "$APPDIR/usr/bin/_internal/PySide6/Qt/lib/"
elif [[ -d "$SCRIPT_DIR/venv/lib/python3.12/site-packages/PySide6/Qt/plugins" ]]; then
    info "Copying PySide6 Qt plugins to AppDir..."
    mkdir -p "$APPDIR/usr/bin/_internal/PySide6/Qt"
    cp -r "$SCRIPT_DIR/venv/lib/python3.12/site-packages/PySide6/Qt/plugins" "$APPDIR/usr/bin/_internal/PySide6/Qt/"
    info "Copying PySide6 Qt libraries to AppDir..."
    mkdir -p "$APPDIR/usr/bin/_internal/PySide6/Qt/lib"
    cp -rn "$SCRIPT_DIR/venv/lib/python3.12/site-packages/PySide6/Qt/lib"/* "$APPDIR/usr/bin/_internal/PySide6/Qt/lib/"
fi

# Desktop entry (required by AppImage spec)
cat > "$APPDIR/YTDownloaderPro.desktop" <<'EOF'
[Desktop Entry]
Name=YTDownloaderPro
Exec=YTDownloaderPro
Icon=YTDownloaderPro
Type=Application
Categories=AudioVideo;Network;
Comment=YTDownloaderPro - YouTube Video Downloader
EOF

# Icon
if [[ -f "$SCRIPT_DIR/icons/download.png" ]]; then
    cp "$SCRIPT_DIR/icons/download.png" "$APPDIR/YTDownloaderPro.png"
else
    warn "icons/download.png not found; AppImage will have no icon."
fi

# AppRun launcher script
cat > "$APPDIR/AppRun" <<'APPRUN'
#!/bin/bash
HERE="$(dirname "$(readlink -f "${0}")")"
export PATH="$HERE/usr/bin:$PATH"
export LD_LIBRARY_PATH="$HERE/usr/bin/_internal/PySide6/Qt/lib:$HERE/usr/lib:${LD_LIBRARY_PATH:-}"
export QT_PLUGIN_PATH="$HERE/usr/bin/_internal/PySide6/Qt/plugins"
exec "$HERE/usr/bin/YTDownloaderPro" "$@"
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
OUTPUT="$SCRIPT_DIR/dist_installer/YTDownloaderPro-linux-x86_64.AppImage"
mkdir -p "$SCRIPT_DIR/dist_installer"

info "Building AppImage → $OUTPUT ..."
ARCH=x86_64 "$APPIMAGETOOL" "$APPDIR" "$OUTPUT"
sha256sum "$OUTPUT" | tee "$SCRIPT_DIR/dist_installer/SHA256SUMS-linux.txt"

info "✅  Done! AppImage: $OUTPUT"
info "    Size: $(du -sh "$OUTPUT" | cut -f1)"
