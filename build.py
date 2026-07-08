"""Build script for setuptools-rust to generate PyO3 stubs."""

import sys
import os
from pathlib import Path


def build(setup_kwargs):
    """Called by setuptools to build the extension.
    
    This hook generates .pyi stub files from the PyO3 module's introspection data.
    """
    
    # Add post-install hook to generate stubs
    from setuptools.command.install import install
    from setuptools.command.develop import develop
    from setuptools.command.build_ext import build_ext as _build_ext
    
    class GenerateStubs(_build_ext):
        """Custom build_ext that generates .pyi files."""
        
        def run(self):
            super().run()
            generate_pyi_stubs()
    
    class InstallWithStubs(install):
        """Custom install that generates .pyi files."""
        
        def run(self):
            super().run()
            generate_pyi_stubs()
    
    class DevelopWithStubs(develop):
        """Custom develop that generates .pyi files."""
        
        def run(self):
            super().run()
            generate_pyi_stubs()
    
    setup_kwargs.update({
        "cmdclass": {
            "build_ext": GenerateStubs,
            "install": InstallWithStubs,
            "develop": DevelopWithStubs,
        }
    })


def generate_pyi_stubs():
    """Generate .pyi stub files from PyO3 introspection data."""
    try:
        import importlib.util
        from pathlib import Path
        
        # Try to import the compiled module
        try:
            import openglider.rs as rs
        except ImportError:
            print("Could not import openglider.rs, skipping stub generation", file=sys.stderr)
            return
        
        stub_dir = Path(__file__).parent / "openglider" / "rs"
        stub_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate __init__.pyi
        generate_main_stub(rs, stub_dir.parent / "rs.pyi")
        
        # Generate submodule stubs
        for submodule_name in ["vector", "spline", "plane", "mesh"]:
            try:
                submodule = getattr(rs, submodule_name)
                stub_path = stub_dir / f"{submodule_name}.pyi"
                generate_module_stub(submodule, stub_path)
                print(f"Generated stub: {stub_path}")
            except AttributeError:
                pass
    except Exception as e:
        print(f"Warning: Could not generate stubs: {e}", file=sys.stderr)


def generate_main_stub(module, output_path):
    """Generate main module stub."""
    lines = [
        '"""Automatically generated stubs for openglider.rs."""',
        "",
        "from . import vector as vector",
        "from . import spline as spline",
        "from . import plane as plane", 
        "from . import mesh as mesh",
        "",
    ]
    
    # Add public functions
    for name in dir(module):
        if name.startswith("_") or name in ("vector", "spline", "plane", "mesh"):
            continue
        obj = getattr(module, name)
        if callable(obj) and not isinstance(obj, type):
            lines.append(f"def {name}(...) -> Any: ...")
    
    lines.extend(["", "__all__ = [", '    "vector",', '    "spline",', '    "plane",', '    "mesh",', "]"])
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines))
    print(f"Generated stub: {output_path}")


def generate_module_stub(module, output_path):
    """Generate stub for a module using basic introspection."""
    lines = [
        f'"""Automatically generated stubs for {module.__name__}."""',
        "",
        "from typing import Any, Iterator, Optional, Union, overload",
        "",
    ]
    
    # Extract classes and functions
    for name in dir(module):
        if name.startswith("_"):
            continue
        
        obj = getattr(module, name)
        
        if isinstance(obj, type):
            # Generate minimal class stub
            lines.append(f"class {name}:")
            doc = getattr(obj, "__doc__", None)
            if doc:
                lines.append(f'    """{doc}"""')
            
            # Add common methods
            for method in ["__init__", "__repr__", "__str__", "copy"]:
                if hasattr(obj, method):
                    lines.append(f"    def {method}(self, ...) -> Any: ...")
            
            # Add properties and methods
            for attr_name in dir(obj):
                if not attr_name.startswith("_"):
                    attr = getattr(obj, attr_name, None)
                    if callable(attr):
                        lines.append(f"    def {attr_name}(self, ...) -> Any: ...")
            
            lines.append("")
        elif callable(obj):
            # Generate function stub
            doc = getattr(obj, "__doc__", None)
            if doc:
                lines.append(f"def {name}(...) -> Any:")
                lines.append(f'    """{doc}"""')
                lines.append("    ...")
            else:
                lines.append(f"def {name}(...) -> Any: ...")
            lines.append("")
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines))


if __name__ == "__main__":
    generate_pyi_stubs()
