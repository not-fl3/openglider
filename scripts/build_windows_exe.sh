#!/usr/bin/env bash
set -euo pipefail

if [[ "${OSTYPE:-}" != msys* && "${OSTYPE:-}" != cygwin* && "${OS:-}" != Windows_NT ]]; then
    echo "This script must be run on Windows (PowerShell, Git Bash, or WSL with Windows Python)."
    exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if command -v uv >/dev/null 2>&1; then
    uv pip install -e ".[gui]"
    uv pip install pyinstaller
    PYINSTALLER_CMD=(uv run pyinstaller)
else
    python -m pip install --upgrade pip
    python -m pip install -e ".[gui]"
    python -m pip install pyinstaller
    PYINSTALLER_CMD=(python -m PyInstaller)
fi

"${PYINSTALLER_CMD[@]}" \
    --noconfirm \
    --clean \
    --onefile \
    --windowed \
    --name OpenGlider \
    --collect-all openglider \
    --collect-all qtawesome \
    --collect-all pyqtgraph \
    --hidden-import PySide6 \
    scripts/launch_gui.py

echo "Windows executable created at: $ROOT_DIR/dist/OpenGlider.exe"
