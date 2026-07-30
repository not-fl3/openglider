#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != "Linux" ]]; then
    echo "This script must be run on Linux."
    exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if command -v uv >/dev/null 2>&1; then
    if [[ "${CI:-}" == "true" ]]; then
        uv pip install --system -e ".[gui]"
        uv pip install --system pyinstaller
        PYTHON_FOR_PYINSTALLER=(python3)
    elif [[ -n "${VIRTUAL_ENV:-}" ]]; then
        uv pip install -e ".[gui]"
        uv pip install pyinstaller
        PYTHON_FOR_PYINSTALLER=(python3)
    else
        if [[ ! -d ".venv" ]]; then
            uv venv .venv
        fi
        uv pip install --python .venv/bin/python -e ".[gui]"
        uv pip install --python .venv/bin/python pyinstaller
        PYTHON_FOR_PYINSTALLER=(.venv/bin/python)
    fi
else
    python3 -m pip install --upgrade pip
    python3 -m pip install -e ".[gui]"
    python3 -m pip install pyinstaller
    PYTHON_FOR_PYINSTALLER=(python3)
fi

"${PYTHON_FOR_PYINSTALLER[@]}" -m PyInstaller \
    --noconfirm \
    --clean \
    --onefile \
    --windowed \
    --name OpenGlider \
    --collect-all openglider \
    --collect-all debugpy \
    --collect-all qtawesome \
    --collect-all pyqtgraph \
    --hidden-import PySide6 \
    scripts/launch_gui.py

ARCH_RAW="$(uname -m)"
case "$ARCH_RAW" in
    x86_64|amd64)
        APPIMAGE_ARCH="x86_64"
        ;;
    aarch64|arm64)
        APPIMAGE_ARCH="aarch64"
        ;;
    *)
        echo "Unsupported architecture for AppImage: $ARCH_RAW"
        exit 1
        ;;
esac

APPDIR="$ROOT_DIR/dist/AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin"
mkdir -p "$APPDIR/usr/share/applications"
mkdir -p "$APPDIR/usr/share/icons/hicolor/256x256/apps"

cp "$ROOT_DIR/dist/OpenGlider" "$APPDIR/usr/bin/OpenGlider"
cp "$ROOT_DIR/openglider/gui/openglider.png" "$APPDIR/usr/share/icons/hicolor/256x256/apps/openglider.png"

cat > "$APPDIR/openglider.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=OpenGlider
Comment=OpenGlider
Exec=OpenGlider
Icon=openglider
Categories=Science;Engineering;
Terminal=false
EOF

cp "$APPDIR/openglider.desktop" "$APPDIR/usr/share/applications/openglider.desktop"

cat > "$APPDIR/AppRun" <<'EOF'
#!/usr/bin/env bash
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$HERE/usr/bin/OpenGlider" "$@"
EOF
chmod +x "$APPDIR/AppRun"

ln -sf usr/share/icons/hicolor/256x256/apps/openglider.png "$APPDIR/openglider.png"

TOOLS_DIR="$ROOT_DIR/.tools"
mkdir -p "$TOOLS_DIR"
APPIMAGETOOL="$TOOLS_DIR/appimagetool-${APPIMAGE_ARCH}.AppImage"

export ARCH="$APPIMAGE_ARCH"
if command -v appimagetool >/dev/null 2>&1; then
    appimagetool "$APPDIR"
else
    if [[ ! -f "$APPIMAGETOOL" ]]; then
        curl -L \
            "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-${APPIMAGE_ARCH}.AppImage" \
            -o "$APPIMAGETOOL"
        chmod +x "$APPIMAGETOOL"
    fi

    "$APPIMAGETOOL" --appimage-extract-and-run "$APPDIR"
fi

OUTPUT_NAME="OpenGlider-linux-${APPIMAGE_ARCH}.AppImage"
mv "$ROOT_DIR/OpenGlider-${APPIMAGE_ARCH}.AppImage" "$ROOT_DIR/dist/$OUTPUT_NAME"

echo "Linux AppImage created at: $ROOT_DIR/dist/$OUTPUT_NAME"
