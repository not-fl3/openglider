# UV Package Manager Migration Guide

This document describes the migration of the OpenGlider project ecosystem to use `uv` as the modern Python package manager.

## Overview

All projects have been migrated to use modern `pyproject.toml` files compatible with `uv`:

- ✅ **openglider** - Pure Python, using hatchling
- ✅ **openglider-input** - Pure Python, using hatchling  
- ✅ **openglider-physics** - Pure Python, using hatchling
- ✅ **openglider-sim** - Pure Python, using hatchling
- ✅ **pyfoil** - C++ extensions (CMake/pybind11), using setuptools
- ✅ **euklid** - C++ extensions (CMake/pybind11), using setuptools

## Installing UV

Install `uv` using one of these methods:

```bash
# Using curl (recommended)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Using pip
pip install uv

# Using cargo
cargo install uv
```

After installation, add to your PATH:
```bash
export PATH="$HOME/.cargo/bin:$PATH"
```

## Using UV

### Creating a Virtual Environment

```bash
# Create a new virtual environment
uv venv

# Activate it
source .venv/bin/activate  # Linux/macOS
# or
.venv\Scripts\activate  # Windows
```

### Installing Packages

```bash
# Install a package in development mode
cd /path/to/project
uv pip install -e .

# Install with optional dependencies
uv pip install -e ".[gui]"

# Install dev dependencies
uv pip install -e ".[dev]"
```

### Installing the Full OpenGlider Ecosystem

```bash
# Install in dependency order
cd /home/simon/dev/para/euklid
uv pip install -e .

cd /home/simon/dev/para/pyfoil
uv pip install -e .

cd /home/simon/dev/para/openglider
uv pip install -e ".[gui]"

cd /home/simon/dev/para/openglider-input
uv pip install -e .

cd /home/simon/dev/para/openglider-physics
uv pip install -e .

cd /home/simon/dev/para/openglider-sim
uv pip install -e .
```

### Syncing Dependencies

```bash
# Sync all dependencies from pyproject.toml
uv pip sync

# Compile dependencies to a lock file
uv pip compile pyproject.toml -o requirements.txt
```

## Project Structure

### Pure Python Projects (hatchling)

Projects using hatchling as the build backend:
- openglider
- openglider-input
- openglider-physics
- openglider-sim

These use a modern, simple build system with automatic package discovery.

### C++ Extension Projects (setuptools)

Projects with C++ extensions still use setuptools:
- **euklid** - Vector operations library
- **pyfoil** - Airfoil analysis (includes xfoil)

These projects require:
- CMake >= 3.15
- pybind11 >= 2.10.0
- C++ compiler (gcc/clang/msvc)

## Benefits of UV

1. **Speed**: 10-100x faster than pip
2. **Deterministic**: Reproducible installs with lock files
3. **Modern**: Built in Rust, designed for modern Python workflows
4. **Compatible**: Works with existing pip/setuptools projects
5. **Simple**: Single tool for virtual environments and package management

## Removed Files

The following legacy files can be removed after migration:
- `setup.cfg` (openglider) - replaced by pyproject.toml
- Old `setup.py` files (where applicable)

## Development Workflow

```bash
# 1. Create virtual environment
uv venv

# 2. Activate it
source .venv/bin/activate

# 3. Install project in editable mode
uv pip install -e ".[dev]"

# 4. Run tests
pytest

# 5. Type checking
mypy .
```

## Troubleshooting

### C++ Extension Build Failures

If euklid or pyfoil fail to build:

```bash
# Ensure CMake is installed
cmake --version

# Ensure pybind11 is available
uv pip install pybind11

# Build with verbose output
uv pip install -e . -v
```

### Dependency Conflicts

```bash
# Show dependency tree
uv pip tree

# Force reinstall
uv pip install --force-reinstall -e .
```

## Next Steps

See `RUST_MIGRATION.md` for information about migrating C++ extensions to Rust.
