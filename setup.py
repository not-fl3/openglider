# type: ignore
from pybind11.setup_helpers import Pybind11Extension, build_ext
from setuptools import setup


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
    setup(ext_modules=[XFOIL_EXTENSION], cmdclass={"build_ext": build_ext})