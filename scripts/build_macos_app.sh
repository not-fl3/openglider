#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "This script must be run on macOS."
    exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if command -v uv >/dev/null 2>&1; then
    uv pip install -e ".[gui]"
    uv pip install pyinstaller
    PYINSTALLER_CMD=(uv run pyinstaller)
else
    python3 -m pip install --upgrade pip
    python3 -m pip install -e ".[gui]"
    python3 -m pip install pyinstaller
    PYINSTALLER_CMD=(python3 -m PyInstaller)
fi

"${PYINSTALLER_CMD[@]}" \
    --noconfirm \
    --clean \
    --windowed \
    --name OpenGlider \
    --osx-bundle-identifier org.openglider.app \
    --collect-all openglider \
    --collect-all qtawesome \
    --collect-all pyqtgraph \
    --hidden-import PySide6 \
    scripts/launch_gui.py

echo "macOS app bundle created at: $ROOT_DIR/dist/OpenGlider.app"
