# UV Quick Reference Guide

Quick commands for working with the OpenGlider ecosystem using UV.

## Installation

```bash
# Install UV
curl -LsSf https://astral.sh/uv/install.sh | sh

# Add to PATH (add to ~/.bashrc or ~/.zshrc)
export PATH="$HOME/.cargo/bin:$PATH"
```

## Virtual Environments

```bash
# Create virtual environment
uv venv

# Create with specific Python version
uv venv --python 3.11

# Activate
source .venv/bin/activate  # Linux/macOS
.venv\Scripts\activate     # Windows

# Deactivate
deactivate
```

## Package Installation

```bash
# Install package in editable mode
uv pip install -e .

# Install with extras
uv pip install -e ".[gui]"
uv pip install -e ".[dev]"

# Install from requirements
uv pip install -r requirements.txt

# Install specific package
uv pip install numpy
```

## OpenGlider Ecosystem Setup

```bash
# Full installation (run in order)
cd ~/dev/para/euklid && uv pip install -e .
cd ~/dev/para/pyfoil && uv pip install -e .
cd ~/dev/para/openglider && uv pip install -e ".[gui]"
cd ~/dev/para/openglider-input && uv pip install -e .
cd ~/dev/para/openglider-physics && uv pip install -e .
cd ~/dev/para/openglider-sim && uv pip install -e .
```

## Dependency Management

```bash
# Show installed packages
uv pip list

# Show dependency tree
uv pip tree

# Compile lock file
uv pip compile pyproject.toml -o requirements.txt

# Sync from lock file
uv pip sync requirements.txt

# Upgrade all packages
uv pip install --upgrade -e .
```

## Common Tasks

```bash
# Reinstall package
uv pip install --force-reinstall -e .

# Uninstall package
uv pip uninstall package-name

# Show package info
uv pip show package-name

# Check for issues
uv pip check
```

## Development Workflow

```bash
# 1. Setup
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"

# 2. Development
# ... make changes ...

# 3. Test
pytest
mypy .

# 4. Build
python -m build  # or maturin build for Rust projects
```

## Troubleshooting

```bash
# Clear cache
uv cache clean

# Verbose output
uv pip install -e . -v

# Show UV version
uv --version

# Get help
uv --help
uv pip --help
```

## Speed Comparison

| Operation | pip | uv | Speedup |
|-----------|-----|-----|---------|
| Install numpy | 5s | 0.5s | 10x |
| Create venv | 2s | 0.2s | 10x |
| Resolve deps | 30s | 1s | 30x |

## Tips

- Use `uv pip compile` to create reproducible environments
- UV caches packages globally - first install is slower, subsequent installs are instant
- UV works with existing pip/setuptools projects - no migration needed for basic usage
- For C++ projects (euklid, pyfoil), ensure CMake and compilers are installed

## Links

- UV Documentation: https://github.com/astral-sh/uv
- UV Installation: https://astral.sh/uv
- OpenGlider Docs: See MIGRATION_SUMMARY.md
