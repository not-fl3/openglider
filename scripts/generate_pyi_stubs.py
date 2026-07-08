#!/usr/bin/env python3
"""Generate PyO3 stubs from the compiled extension using pyo3-introspection."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PACKAGE_ROOT = PROJECT_ROOT / "openglider"
MODULE_NAME = "rs"
SUBMODULE_STUB_ROOT = PACKAGE_ROOT / MODULE_NAME
ROOT_STUB_PATH = PACKAGE_ROOT / f"{MODULE_NAME}.pyi"


def _find_extension_binary() -> Path:
    extensions = []
    for pattern in ("rs*.so", "rs*.pyd", "rs*.dylib"):
        extensions.extend(sorted(PACKAGE_ROOT.glob(pattern)))
    if not extensions:
        raise FileNotFoundError(
            "Could not find the compiled openglider.rs extension. Build the extension first."
        )
    return extensions[0]


def _run_introspection(binary_path: Path, output_dir: Path) -> None:
    subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--bin",
            "pyo3_stub_gen",
            "--",
            str(binary_path),
            MODULE_NAME,
            str(output_dir),
        ],
        cwd=PROJECT_ROOT,
        check=True,
    )


def _install_generated_files(output_dir: Path) -> None:
    root_stub = output_dir / "__init__.pyi"
    if not root_stub.exists():
        raise FileNotFoundError(f"Expected generated root stub at {root_stub}")

    SUBMODULE_STUB_ROOT.mkdir(parents=True, exist_ok=True)
    for stub_file in SUBMODULE_STUB_ROOT.glob("*.pyi"):
        stub_file.unlink()

    shutil.copy2(root_stub, ROOT_STUB_PATH)
    for stub_file in output_dir.glob("*.pyi"):
        if stub_file.name == "__init__.pyi":
            continue
        shutil.copy2(stub_file, SUBMODULE_STUB_ROOT / stub_file.name)


def generate_pyi_stubs() -> None:
    binary_path = _find_extension_binary()
    with tempfile.TemporaryDirectory(prefix="openglider-pyo3-stubs-") as tmp_dir:
        output_dir = Path(tmp_dir)
        _run_introspection(binary_path, output_dir)
        _install_generated_files(output_dir)


if __name__ == "__main__":
    generate_pyi_stubs()
