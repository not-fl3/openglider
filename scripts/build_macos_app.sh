#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "This script must be run on macOS."
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
    --windowed \
    --name OpenGlider \
    --osx-bundle-identifier org.openglider.app \
    --collect-submodules openglider \
    --collect-data openglider \
    --collect-data qtawesome \
    --collect-data pyqtgraph \
    --hidden-import qtawesome \
    --hidden-import pyqtgraph \
    --hidden-import PySide6 \
    scripts/launch_gui.py

ARCH="$(uname -m)"
case "$ARCH" in
    arm64)
        ARTIFACT_NAME="OpenGlider-macos-app-arm64.tar.gz"
        ;;
    x86_64)
        ARTIFACT_NAME="OpenGlider-macos-app-x64.tar.gz"
        ;;
    *)
        echo "Unsupported macOS architecture: $ARCH"
        exit 1
        ;;
esac

tar -C "$ROOT_DIR/dist" -czf "$ROOT_DIR/dist/$ARTIFACT_NAME" OpenGlider.app

echo "macOS app bundle created at: $ROOT_DIR/dist/OpenGlider.app"
echo "macOS artifact archive created at: $ROOT_DIR/dist/$ARTIFACT_NAME"
