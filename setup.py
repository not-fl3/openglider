# type: ignore
"""Setup script with PyO3 stub generation."""

from pathlib import Path
import subprocess
import sys

from setuptools import setup


def generate_stubs_after_build():
    """Generate .pyi stub files after building the PyO3 extension."""
    script_path = Path(__file__).parent / "scripts" / "generate_pyi_stubs.py"
    subprocess.run([sys.executable, str(script_path)], check=True)



SRC_CPP = "src_cpp"

CPP_FILES = [
    "solver.cpp",
    "xfoil.cpp",
    "pybind.cpp",
]

HEADER_FILES = [
    "solver.hpp",
    "xfoil_params.h",
    "xfoil.h",
    "version.hpp",
]

XFOIL_EXTENSION = Pybind11Extension(
    "xfoil",
    [f"{SRC_CPP}/{file_name}" for file_name in CPP_FILES],
    include_dirs=[SRC_CPP],
    libraries=["fmt"],
    cxx_std=17,
    depends=[f"{SRC_CPP}/{file_name}" for file_name in HEADER_FILES],
)

if __name__ == "__main__":
    setup()
    # Generate stubs after installation
    generate_stubs_after_build()
