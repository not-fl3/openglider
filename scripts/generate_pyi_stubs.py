#!/usr/bin/env python3
"""Generate PyO3 stubs from the compiled extension using pyo3-introspection."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PACKAGE_ROOT = PROJECT_ROOT / "openglider"
MODULE_NAME = "openglider.rs"
FALLBACK_MODULE_NAME = "rs"
SUBMODULE_NAME = "rs"
SUBMODULE_STUB_ROOT = PACKAGE_ROOT / SUBMODULE_NAME
ROOT_STUB_PATH = SUBMODULE_STUB_ROOT / "__init__.pyi"


def _build_debug_extension() -> None:
    subprocess.run(["cargo", "build", "--quiet", "--lib", "--features", "inspect"], cwd=PROJECT_ROOT, check=True)


def _find_extension_binaries() -> list[Path]:
    _build_debug_extension()

    search_roots = [
        PROJECT_ROOT / "target" / "debug",
        PROJECT_ROOT / "build",
        PACKAGE_ROOT,
    ]

    # Keep unique paths and prefer newest build output when multiple candidates exist.
    search_patterns = (
        "rs*.pyd",
        "rs*.so",
        "rs*.dylib",
        "rs*.dll",
        "librs*.so",
        "librs*.dylib",
        "librs*.dll",
    )

    extensions: list[Path] = []
    for search_root in search_roots:
        if not search_root.exists():
            continue
        root_matches: list[Path] = []
        for pattern in search_patterns:
            root_matches.extend(search_root.rglob(pattern))
        extensions.extend(sorted(set(root_matches), key=lambda p: p.stat().st_mtime, reverse=True))

    explicit_binary = os.environ.get("OPENGLIDER_RS_BINARY")
    if explicit_binary:
        explicit_path = Path(explicit_binary)
        if explicit_path.exists():
            # Keep explicit binary as a fallback candidate, but do not force it first.
            # Editable/wheel artifacts often lack the `inspect` feature required by pyo3-introspection.
            extensions.append(explicit_path)

    unique_extensions: list[Path] = []
    seen: set[Path] = set()
    for extension_path in extensions:
        if extension_path in seen:
            continue
        seen.add(extension_path)
        unique_extensions.append(extension_path)

    if not unique_extensions:
        raise FileNotFoundError(
            "Could not find the compiled openglider.rs extension in source or debug build directories. "
            "Build the extension first."
        )
    return unique_extensions


def _run_introspection(binary_path: Path, output_dir: Path) -> None:
    module_names = [FALLBACK_MODULE_NAME, MODULE_NAME]
    last_error: subprocess.CalledProcessError | None = None

    for module_name in module_names:
        try:
            subprocess.run(
                [
                    "cargo",
                    "run",
                    "--quiet",
                    "--features",
                    "inspect",
                    "--bin",
                    "pyo3_stub_gen",
                    "--",
                    str(binary_path),
                    module_name,
                    str(output_dir),
                ],
                cwd=PROJECT_ROOT,
                check=True,
            )
            return
        except subprocess.CalledProcessError as exc:
            last_error = exc

    if last_error is not None:
        raise last_error


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

    _ensure_root_exports_submodules()


def _ensure_root_exports_submodules() -> None:
    existing_text = ROOT_STUB_PATH.read_text(encoding="utf-8")
    submodules = sorted(
        stub_path.stem
        for stub_path in SUBMODULE_STUB_ROOT.glob("*.pyi")
        if stub_path.name != "__init__.pyi"
    )

    if not submodules:
        return

    export_lines = [f"from . import {name} as {name}" for name in submodules]
    missing_lines = [line for line in export_lines if line not in existing_text]

    if not missing_lines:
        return

    new_text = "\n".join(missing_lines) + "\n" + existing_text
    ROOT_STUB_PATH.write_text(new_text, encoding="utf-8")


def generate_pyi_stubs() -> None:
    candidate_binaries = _find_extension_binaries()
    errors: list[str] = []

    with tempfile.TemporaryDirectory(prefix="openglider-pyo3-stubs-") as tmp_dir:
        output_dir = Path(tmp_dir)

        for binary_path in candidate_binaries:
            try:
                _run_introspection(binary_path, output_dir)
                _install_generated_files(output_dir)
                return
            except subprocess.CalledProcessError as exc:
                errors.append(f"{binary_path}: {exc}")

    details = "\n".join(errors) if errors else "No candidate binaries were tried."
    raise RuntimeError(
        "Failed to generate stubs from any Rust extension candidate. "
        "This usually means the selected binary was built without the `inspect` feature.\n"
        f"Tried:\n{details}"
    )


if __name__ == "__main__":
    generate_pyi_stubs()
