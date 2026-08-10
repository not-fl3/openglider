# type: ignore
"""Setup script with Pybind11 and PyO3 extensions."""

from pathlib import Path
import subprocess
import sys

from setuptools import setup
from pybind11.setup_helpers import Pybind11Extension, build_ext
from setuptools_rust import build_rust


def generate_stubs_after_build():
    """Generate .pyi stub files after building extensions."""
    script_path = Path(__file__).parent / "scripts" / "generate_pyi_stubs.py"
    subprocess.run([sys.executable, str(script_path)], check=True)


def ensure_cpp_deps() -> None:
    """Fetch required C++ headers for extension builds."""
    script_path = Path(__file__).parent / "scripts" / "fetch_cpp_deps.py"
    subprocess.run([sys.executable, str(script_path)], check=True)


SRC_CPP = "openglider_xfoil"

ensure_cpp_deps()

CPP_FILES = [
    "solver.cpp",
    "xfoil.cpp",
    "pybind.cpp",
]

HEADER_FILES = [
    "solver.hpp",
    "xfoil_params.h",
    "xfoil.h"
]

extra_compile_args = []
if sys.platform == "win32":
    extra_compile_args.append("/utf-8")

xfoil_extension = Pybind11Extension(
    "openglider.xfoil",
    [f"{SRC_CPP}/{file_name}" for file_name in CPP_FILES],
    include_dirs=[SRC_CPP, f"{SRC_CPP}/fmt/include"],
    define_macros=[("FMT_HEADER_ONLY", "1")],
    extra_compile_args=extra_compile_args,
    cxx_std=17,
    depends=[f"{SRC_CPP}/{file_name}" for file_name in HEADER_FILES],
)

class BuildExtWithStubs(build_rust):
    def run(self):
        super().run()
        generate_stubs_after_build()


setup(
    ext_modules=[
        xfoil_extension,
    ],
    cmdclass={
        "build_rust": BuildExtWithStubs
    },
)