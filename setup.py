# type: ignore
"""Setup script with PyO3 stub generation."""

from setuptools import setup
from pathlib import Path


def generate_stubs_after_build():
    """Generate .pyi stub files after building the PyO3 extension."""
    try:
        from build import generate_pyi_stubs
        generate_pyi_stubs()
    except ImportError:
        pass



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
