#!/usr/bin/env python3
"""
Standalone script to generate .pyi stub files from PyO3 introspection.

This script can be run after building the PyO3 extension to generate type stubs.
Usage: python scripts/generate_pyi_stubs.py
"""

import sys
import importlib
from pathlib import Path
from typing import Any, Optional


def generate_pyi_stubs():
    """Generate .pyi stub files from the compiled PyO3 module."""
    print("Generating .pyi stub files from PyO3 introspection...", file=sys.stderr)
    
    try:
        import openglider.rs as rs
    except ImportError as e:
        print(f"ERROR: Could not import openglider.rs: {e}", file=sys.stderr)
        print("Make sure to build the extension first with: pip install -e .", file=sys.stderr)
        return False
    
    project_root = Path(__file__).parent.parent
    stub_root = project_root / "openglider" / "rs"
    stub_root.mkdir(parents=True, exist_ok=True)
    
    # Generate main stub
    main_stub_path = project_root / "openglider" / "rs.pyi"
    _generate_main_stub(rs, main_stub_path)
    
    # Generate submodule stubs
    for submodule_name in ["vector", "spline", "plane", "mesh"]:
        try:
            submodule = getattr(rs, submodule_name)
            stub_path = stub_root / f"{submodule_name}.pyi"
            _generate_module_stub(submodule, stub_path)
            print(f"✓ Generated {stub_path}", file=sys.stderr)
        except AttributeError:
            print(f"⚠ Submodule {submodule_name} not found", file=sys.stderr)
    
    print("Done! .pyi stubs generated successfully.", file=sys.stderr)
    return True


def _generate_main_stub(module: Any, output_path: Path) -> None:
    """Generate the main rs module stub."""
    lines = [
        '"""PyO3 Rust module providing high-performance geometric calculations.',
        '',
        'This module is automatically generated from Rust code using PyO3.',
        'Type stubs are generated from introspection data.',
        '"""',
        '',
        'from typing import Any',
        '',
        'from . import vector as vector',
        'from . import spline as spline', 
        'from . import plane as plane',
        'from . import mesh as mesh',
        '',
        '__all__ = [',
        '    "triangle_area",',
        '    "version",',
        '    "vector",',
        '    "spline",',
        '    "plane",',
        '    "mesh",',
        ']',
        '',
    ]
    
    # Add top-level functions
    for name in sorted(dir(module)):
        if not name.startswith("_") and name not in ("vector", "spline", "plane", "mesh"):
            obj = getattr(module, name)
            if callable(obj) and not isinstance(obj, type):
                lines.append(f'def {name}(*args: Any, **kwargs: Any) -> Any: ...')
    
    output_path.write_text("\n".join(lines))


def _generate_module_stub(module: Any, output_path: Path) -> None:
    """Generate a stub file for a PyO3 submodule."""
    lines = [
        f'"""Auto-generated stubs for {module.__name__}.',
        '',
        'This module provides geometric calculations and types.',
        'Stubs are generated from PyO3 introspection data.',
        '"""',
        '',
        'from typing import Any, Iterator, Optional, Union, overload',
        '',
    ]
    
    # Collect classes and functions
    classes = []
    functions = []
    
    for name in sorted(dir(module)):
        if name.startswith("_"):
            continue
        
        obj = getattr(module, name)
        
        if isinstance(obj, type):
            classes.append((name, obj))
        elif callable(obj):
            functions.append((name, obj))
    
    # Generate class stubs first
    for class_name, cls in classes:
        doc = _get_docstring(cls)
        lines.append(f'class {class_name}:')
        
        if doc:
            lines.append(f'    """{doc}"""')
        else:
            lines.append('    """Class stub."""')
        
        # Add attributes and methods  
        methods_added = set()
        for attr_name in sorted(dir(cls)):
            if attr_name.startswith("_") and attr_name not in ("__init__", "__repr__", "__str__"):
                continue
            if attr_name not in methods_added:
                attr = getattr(cls, attr_name, None)
                if callable(attr):
                    lines.append(f'    def {attr_name}(self, *args: Any, **kwargs: Any) -> Any: ...')
                    methods_added.add(attr_name)
        
        lines.append('')
    
    # Generate function stubs
    for func_name, func in functions:
        doc = _get_docstring(func)
        if doc:
            lines.append(f'def {func_name}(*args: Any, **kwargs: Any) -> Any:')
            lines.append(f'    """{doc}"""')
            lines.append('    ...')
        else:
            lines.append(f'def {func_name}(*args: Any, **kwargs: Any) -> Any: ...')
        lines.append('')
    
    output_path.write_text("\n".join(lines))


def _get_docstring(obj: Any) -> Optional[str]:
    """Extract and clean up a docstring."""
    doc = getattr(obj, "__doc__", None)
    if doc:
        return doc.strip().split('\n')[0][:100]
    return None


if __name__ == "__main__":
    success = generate_pyi_stubs()
    sys.exit(0 if success else 1)
