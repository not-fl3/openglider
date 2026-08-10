#!/usr/bin/env python3
"""Fetch third-party C++ headers used by local/CI builds."""

from __future__ import annotations

import shutil
import tarfile
import tempfile
import urllib.request
from pathlib import Path


FMT_VERSION = "11.0.2"
FMT_ARCHIVE_URL = f"https://github.com/fmtlib/fmt/archive/refs/tags/{FMT_VERSION}.tar.gz"


def fetch_fmt_headers(repo_root: Path) -> None:
    header = repo_root / "openglider_xfoil" / "fmt" / "include" / "fmt" / "format.h"
    if header.exists():
        return

    target_root = repo_root / "openglider_xfoil"
    target_dir = target_root / "fmt"
    target_root.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        archive_path = tmp_path / "fmt.tar.gz"

        with urllib.request.urlopen(FMT_ARCHIVE_URL) as response:
            archive_path.write_bytes(response.read())

        with tarfile.open(archive_path, "r:gz") as tar:
            tar.extractall(path=tmp_path)

        extracted_root = tmp_path / f"fmt-{FMT_VERSION}"
        if not extracted_root.exists():
            raise RuntimeError("Failed to extract fmt headers")

        shutil.rmtree(target_dir, ignore_errors=True)
        shutil.move(str(extracted_root), str(target_dir))


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    fetch_fmt_headers(repo_root)


if __name__ == "__main__":
    main()
