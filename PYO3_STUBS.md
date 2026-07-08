# PyO3 Stub Generation

This project uses PyO3's `experimental-inspect` feature to automatically generate `.pyi` type stub files for the Rust extension module.

## How It Works

1. **PyO3 Configuration**: The `Cargo.toml` includes the `experimental-inspect` feature which enables runtime introspection of PyO3 classes and functions.

2. **Build System**: The project uses `setuptools-rust` to build the PyO3 extension during installation.

3. **Stub Generation**: After building, the `.pyi` stub files are automatically generated using the introspection data.

## Building and Generating Stubs

### Development Installation

To build the extension and generate stubs in editable mode:

```bash
pip install -e .
```

This will:
1. Compile the Rust extension using `setuptools-rust`
2. Generate `.pyi` stub files from the introspection data
3. Install the package in development mode

### Manual Stub Generation

If you need to regenerate stubs after modifying the Rust code:

```bash
python scripts/generate_pyi_stubs.py
```

### Via Make (if available)

```bash
make stubs
```

## Generated Files

The stub files are generated in the following locations:

- `openglider/rs.pyi` - Main module stub
- `openglider/rs/__init__.pyi` - Submodule initialization stub
- `openglider/rs/vector.pyi` - Vector types and operations
- `openglider/rs/spline.pyi` - Spline curve types
- `openglider/rs/plane.pyi` - Plane geometry types
- `openglider/rs/mesh.pyi` - Mesh operations

## Type Checking

With the stubs in place, you can now use full type checking with mypy:

```bash
mypy openglider
```

## Cargo Configuration

Key configuration in `Cargo.toml`:

```toml
[dependencies]
pyo3 = { version = "0.29", features = ["experimental-inspect"] }
```

The `experimental-inspect` feature provides runtime introspection capabilities that power stub generation.

## Build Configuration

Key configuration in `pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=69", "setuptools-rust>=1.12", "wheel"]
build-backend = "setuptools.build_meta"

[tool.setuptools-rust]
[[tool.setuptools-rust.ext-modules]]
target = "openglider.rs"
path = "Cargo.toml"
binding = "PyO3"
```

## Troubleshooting

### Stubs not generated
- Ensure the extension built successfully: `python -c "import openglider.rs; print(openglider.rs.version())"`
- Run the stub generation script manually: `python scripts/generate_pyi_stubs.py`

### Import errors
- Rebuild the extension: `pip install -e . --force-reinstall --no-cache-dir`
- Check that all dependencies are installed: `pip install setuptools-rust pyo3`

### Type checking issues
- Ensure `py.typed` marker exists in `openglider/py.typed`
- Check that mypy configuration in `pyproject.toml` is correct
- Verify stubs are in the correct locations

## Future Improvements

- Use `pyo3-inspect` CLI tool once it's stable
- Automate stub generation in CI/CD
- Generate more detailed stubs with type information
- Consider using `stubgen` from mypy for comparison
