# Rust Migration Guide for C++ Extensions

This document outlines the strategy for migrating C++ extensions to Rust in the OpenGlider ecosystem.

## Current C++ Extensions

### 1. euklid (Vector Operations Library)

**Current Implementation:**
- C++ library with pybind11 bindings
- CMake build system
- Provides 2D/3D vector operations
- Core dependency for other projects

**Location:** `/home/simon/dev/para/euklid`

**Key Components:**
- Vector2, Vector3 classes
- Geometric operations
- Performance-critical math operations

**Migration Priority:** HIGH (foundational library)

### 2. pyfoil (Airfoil Analysis)

**Current Implementation:**
- C++ library with pybind11 bindings
- Includes xfoil (Fortran code wrapped in C++)
- CMake build system
- Airfoil generation, modification, and analysis

**Location:** `/home/simon/dev/para/pyfoil`

**Key Components:**
- xfoil integration
- Airfoil generators
- Aerodynamic calculations

**Migration Priority:** MEDIUM (complex, includes Fortran code)

## Why Migrate to Rust?

1. **Memory Safety**: Rust eliminates entire classes of bugs (null pointers, buffer overflows)
2. **Modern Tooling**: Cargo provides excellent dependency management and build system
3. **Performance**: Comparable to C++, often better due to zero-cost abstractions
4. **Python Integration**: PyO3 and maturin make Python bindings seamless
5. **Maintainability**: Better error messages, clearer code, easier to refactor
6. **Cross-platform**: Easier cross-compilation and distribution

## Migration Strategy

### Phase 1: Setup and Tooling

1. Install Rust toolchain:
```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
```

2. Install maturin (Rust-Python build tool):
```bash
pip install maturin
# or
uv pip install maturin
```

3. Install PyO3 development tools:
```bash
cargo install cargo-expand  # For debugging macros
```

### Phase 2: Migrate euklid

**Step 1: Create Rust Project Structure**

```bash
cd /home/simon/dev/para/euklid
mkdir rust-euklid
cd rust-euklid
maturin init --bindings pyo3
```

**Step 2: Update pyproject.toml**

```toml
[build-system]
requires = ["maturin>=1.0,<2.0"]
build-backend = "maturin"

[project]
name = "euklid"
version = "0.3.0"
description = "Common vector operations [2D/3D] - Rust implementation"
requires-python = ">=3.8"
# ... rest of metadata

[tool.maturin]
features = ["pyo3/extension-module"]
python-source = "python"
module-name = "euklid._core"
```

**Step 3: Implement Core Types**

Example Rust implementation:

```rust
use pyo3::prelude::*;

#[pyclass]
#[derive(Clone, Copy, Debug)]
pub struct Vector2 {
    #[pyo3(get, set)]
    pub x: f64,
    #[pyo3(get, set)]
    pub y: f64,
}

#[pymethods]
impl Vector2 {
    #[new]
    fn new(x: f64, y: f64) -> Self {
        Vector2 { x, y }
    }
    
    fn __add__(&self, other: &Vector2) -> Vector2 {
        Vector2 {
            x: self.x + other.x,
            y: self.y + other.y,
        }
    }
    
    fn __mul__(&self, scalar: f64) -> Vector2 {
        Vector2 {
            x: self.x * scalar,
            y: self.y * scalar,
        }
    }
    
    fn norm(&self) -> f64 {
        (self.x * self.x + self.y * self.y).sqrt()
    }
    
    fn normalize(&self) -> Vector2 {
        let n = self.norm();
        Vector2 {
            x: self.x / n,
            y: self.y / n,
        }
    }
}

#[pymodule]
fn euklid(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<Vector2>()?;
    Ok(())
}
```

**Step 4: Build and Test**

```bash
# Development build
maturin develop

# Release build
maturin build --release

# Run tests
pytest tests/
```

### Phase 3: Migrate pyfoil

**Challenges:**
- xfoil is Fortran code
- Complex aerodynamic calculations
- Large existing codebase

**Options:**

1. **Wrap existing xfoil**: Keep Fortran/C++ xfoil, create Rust wrapper
2. **Pure Rust rewrite**: Reimplement xfoil algorithms in Rust (long-term)
3. **Hybrid approach**: Rust for new code, FFI to existing xfoil

**Recommended Approach:**

```toml
[build-system]
requires = ["maturin>=1.0,<2.0"]
build-backend = "maturin"

[dependencies]
pyo3 = { version = "0.20", features = ["extension-module"] }
numpy = "0.20"  # For array operations
```

Example structure:
```
pyfoil/
├── Cargo.toml
├── pyproject.toml
├── src/
│   ├── lib.rs          # Main Rust module
│   ├── xfoil_ffi.rs    # FFI to existing xfoil
│   ├── generators.rs   # Airfoil generators in Rust
│   └── analysis.rs     # Analysis tools
├── xfoil/              # Existing C++/Fortran code
└── python/
    └── pyfoil/         # Python wrapper code
```

## Migration Checklist

### For euklid:

- [ ] Set up Rust project with maturin
- [ ] Implement Vector2 class
- [ ] Implement Vector3 class
- [ ] Port geometric operations
- [ ] Add comprehensive tests
- [ ] Benchmark against C++ version
- [ ] Update documentation
- [ ] Create migration guide for users
- [ ] Publish to PyPI

### For pyfoil:

- [ ] Analyze xfoil dependencies
- [ ] Set up Rust project with maturin
- [ ] Create FFI bindings to xfoil
- [ ] Port airfoil generators to Rust
- [ ] Port analysis tools to Rust
- [ ] Add comprehensive tests
- [ ] Benchmark performance
- [ ] Update documentation
- [ ] Gradual rollout strategy

## Building with Maturin

### Development

```bash
# Build and install in current virtualenv
maturin develop

# With release optimizations
maturin develop --release

# With specific Python version
maturin develop --python python3.11
```

### Distribution

```bash
# Build wheel for current platform
maturin build --release

# Build for multiple Python versions
maturin build --release --interpreter python3.8 python3.9 python3.10 python3.11 python3.12

# Build for distribution
maturin build --release --strip
```

### Publishing

```bash
# Publish to PyPI
maturin publish

# Test on TestPyPI first
maturin publish --repository testpypi
```

## Performance Considerations

### Optimization Flags

In `Cargo.toml`:

```toml
[profile.release]
opt-level = 3
lto = true
codegen-units = 1
strip = true
```

### Benchmarking

```rust
use criterion::{black_box, criterion_group, criterion_main, Criterion};

fn benchmark_vector_ops(c: &mut Criterion) {
    c.bench_function("vector2_add", |b| {
        let v1 = Vector2::new(1.0, 2.0);
        let v2 = Vector2::new(3.0, 4.0);
        b.iter(|| black_box(&v1).__add__(black_box(&v2)))
    });
}

criterion_group!(benches, benchmark_vector_ops);
criterion_main!(benches);
```

## Testing Strategy

### Unit Tests (Rust)

```rust
#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_vector2_add() {
        let v1 = Vector2::new(1.0, 2.0);
        let v2 = Vector2::new(3.0, 4.0);
        let result = v1.__add__(&v2);
        assert_eq!(result.x, 4.0);
        assert_eq!(result.y, 6.0);
    }
}
```

### Integration Tests (Python)

```python
import pytest
from euklid import Vector2

def test_vector2_operations():
    v1 = Vector2(1.0, 2.0)
    v2 = Vector2(3.0, 4.0)
    
    result = v1 + v2
    assert result.x == 4.0
    assert result.y == 6.0
    
    scaled = v1 * 2.0
    assert scaled.x == 2.0
    assert scaled.y == 4.0
```

## Resources

- **PyO3 Documentation**: https://pyo3.rs/
- **Maturin Guide**: https://www.maturin.rs/
- **Rust Book**: https://doc.rust-lang.org/book/
- **PyO3 Examples**: https://github.com/PyO3/pyo3/tree/main/examples

## Timeline Estimate

### euklid Migration
- Setup: 1-2 days
- Core implementation: 1-2 weeks
- Testing & optimization: 1 week
- Documentation: 2-3 days
- **Total: 3-4 weeks**

### pyfoil Migration
- Analysis & planning: 1 week
- FFI setup: 1 week
- Core migration: 4-6 weeks
- Testing & optimization: 2 weeks
- Documentation: 1 week
- **Total: 9-11 weeks**

## Backward Compatibility

During migration, maintain both versions:

```python
# In __init__.py
try:
    from ._rust import Vector2, Vector3  # Rust implementation
except ImportError:
    from ._cpp import Vector2, Vector3   # C++ fallback
```

This allows gradual migration and testing.

## Next Steps

1. Install Rust toolchain
2. Experiment with maturin on a small test project
3. Start euklid migration (high priority, foundational)
4. Gather feedback and refine approach
5. Begin pyfoil migration once euklid is stable
