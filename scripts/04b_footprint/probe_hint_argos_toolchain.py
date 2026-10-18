#!/usr/bin/env python3
"""Fail-closed origin probe for the hash-locked external builder wheels."""
import importlib
import importlib.metadata
import os
import pathlib
import sys


EXPECTED = {
    "pip": "25.2", "packaging": "25.0", "setuptools": "80.9.0",
    "wheel": "0.45.1", "auditwheel": "6.0.0", "pyelftools": "0.31",
}


def require_origin(name: str, path: pathlib.Path, root: pathlib.Path) -> None:
    path = path.resolve()
    if root not in path.parents:
        raise RuntimeError(f"ARGOS_TOOLCHAIN_MODULE_ORIGIN_MISMATCH:{name}:{path}")


def probe(root: pathlib.Path) -> None:
    root = root.resolve()
    if os.environ.get("SETUPTOOLS_USE_DISTUTILS") != "local":
        raise RuntimeError("ARGOS_TOOLCHAIN_DISTUTILS_POLICY_MISMATCH")

    # Import setuptools before pip. pip's startup hook disables the distutils
    # finder, which otherwise makes setuptools fall back to pmafp's stdlib copy.
    hack = importlib.import_module("_distutils_hack")
    require_origin("_distutils_hack", pathlib.Path(hack.__file__), root)
    hack.add_shim()
    setuptools = importlib.import_module("setuptools")
    distutils_core = importlib.import_module("distutils.core")
    distutils_path = pathlib.Path(distutils_core.__file__).resolve()
    if root not in distutils_path.parents or "_distutils" not in distutils_path.parts:
        raise RuntimeError(f"ARGOS_TOOLCHAIN_DISTUTILS_ORIGIN_MISMATCH:{distutils_path}")

    modules = {
        "setuptools": setuptools,
        "packaging": importlib.import_module("packaging"),
        "wheel": importlib.import_module("wheel"),
        "auditwheel": importlib.import_module("auditwheel"),
        "pyelftools": importlib.import_module("elftools"),
        "pip": importlib.import_module("pip"),
    }
    owned_prefixes = ("_distutils_hack", "distutils", "elftools", *modules.keys())
    for module_name, module in tuple(sys.modules.items()):
        if not any(module_name == prefix or module_name.startswith(prefix + ".")
                   for prefix in owned_prefixes):
            continue
        module_file = getattr(module, "__file__", None)
        if module_file:
            require_origin(module_name, pathlib.Path(module_file), root)
        else:
            for package_path in getattr(module, "__path__", ()):
                require_origin(module_name, pathlib.Path(package_path), root)

    for name, module in modules.items():
        module_path = pathlib.Path(module.__file__).resolve()
        distribution = importlib.metadata.distribution(name)
        metadata_files = [item for item in (distribution.files or [])
                          if item.name == "METADATA" and item.parts and
                          item.parts[0].endswith(".dist-info")]
        if len(metadata_files) != 1:
            raise RuntimeError(f"ARGOS_TOOLCHAIN_METADATA_MEMBER_INVALID:{name}:{len(metadata_files)}")
        metadata_path = pathlib.Path(distribution.locate_file(metadata_files[0])).resolve()
        print(name, distribution.version, module_path, metadata_path)
        require_origin(name, module_path, root)
        if distribution.version != EXPECTED[name]:
            raise RuntimeError(f"ARGOS_TOOLCHAIN_VERSION_MISMATCH:{name}:{distribution.version}")
        if root not in metadata_path.parents:
            raise RuntimeError(f"ARGOS_TOOLCHAIN_METADATA_ORIGIN_MISMATCH:{name}:{metadata_path}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("ARGOS_TOOLCHAIN_PROBE_USAGE")
    try:
        probe(pathlib.Path(sys.argv[1]))
    except Exception as exc:
        print(f"ARGOS_TOOLCHAIN_PROBE_FAIL:{type(exc).__name__}:{exc}", file=sys.stderr)
        raise SystemExit(1)
