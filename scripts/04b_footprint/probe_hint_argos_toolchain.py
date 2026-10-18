#!/usr/bin/env python3
"""Fail-closed origin probe for the hash-locked external builder wheels."""
import importlib
import importlib.metadata
import os
import pathlib
import sysconfig
import sys


EXPECTED = {
    "pip": "25.2", "packaging": "25.0", "setuptools": "80.9.0",
    "wheel": "0.45.1", "auditwheel": "6.0.0", "pyelftools": "0.31",
}


def require_origin(name: str, path: pathlib.Path, root: pathlib.Path) -> None:
    path = path.resolve()
    if root not in path.parents:
        raise RuntimeError(f"ARGOS_TOOLCHAIN_MODULE_ORIGIN_MISMATCH:{name}:{path}")


def require_distribution_origin(name: str, root: pathlib.Path) -> object:
    distribution = importlib.metadata.distribution(name)
    metadata_files = [item for item in (distribution.files or [])
                      if item.name == "METADATA" and item.parts and
                      item.parts[0].endswith(".dist-info")]
    if len(metadata_files) != 1:
        raise RuntimeError(f"ARGOS_TOOLCHAIN_METADATA_MEMBER_INVALID:{name}:{len(metadata_files)}")
    metadata_path = pathlib.Path(distribution.locate_file(metadata_files[0])).resolve()
    if root not in metadata_path.parents:
        raise RuntimeError(f"ARGOS_TOOLCHAIN_METADATA_ORIGIN_MISMATCH:{name}:{metadata_path}")
    if distribution.version != EXPECTED[name]:
        raise RuntimeError(f"ARGOS_TOOLCHAIN_VERSION_MISMATCH:{name}:{distribution.version}")
    return distribution


def require_no_host_site_packages(root: pathlib.Path) -> None:
    """Allow only standard/runtime, builder source, or external toolchain modules."""
    site_parts = {"site-packages", "dist-packages"}
    standard_roots = {
        pathlib.Path(value).resolve()
        for key, value in sysconfig.get_paths().items()
        if key in {"stdlib", "platstdlib"} and value
    }
    allowed_roots = {root.resolve(), pathlib.Path(__file__).resolve().parent, *standard_roots}
    workspace_value = os.environ.get("PMA_HINT_ALLOWED_WORKSPACE")
    if workspace_value:
        workspace = pathlib.Path(workspace_value)
        if not workspace.is_absolute() or workspace.resolve() == pathlib.Path("/"):
            raise RuntimeError("ARGOS_TOOLCHAIN_ALLOWED_WORKSPACE_INVALID")
        work_root = workspace.resolve()
        current_dir = pathlib.Path.cwd().resolve()
        if current_dir == work_root or work_root in current_dir.parents:
            allowed_roots.add(current_dir)
    for module_name, module in tuple(sys.modules.items()):
        paths = []
        module_file = getattr(module, "__file__", None)
        if module_file:
            paths.append(pathlib.Path(module_file))
        paths.extend(pathlib.Path(item) for item in getattr(module, "__path__", ()))
        for path in paths:
            resolved = path.resolve()
            if site_parts.intersection(resolved.parts) and root not in resolved.parents:
                raise RuntimeError(
                    f"ARGOS_TOOLCHAIN_HOST_SITE_PACKAGES_MODULE:{module_name}:{resolved}"
                )
            if not any(resolved == allowed or allowed in resolved.parents for allowed in allowed_roots):
                raise RuntimeError(
                    f"ARGOS_TOOLCHAIN_MODULE_ORIGIN_UNAPPROVED:{module_name}:{resolved}"
                )


def isolate_import_path(root: pathlib.Path) -> None:
    """Allow only audited source, runtime, toolchain and external work paths."""
    root = root.resolve()
    # Fail if a startup hook has already loaded a host module; never repair a
    # contaminated process by removing its sys.modules entries.
    require_no_host_site_packages(root)
    site_parts = {"site-packages", "dist-packages"}
    explicit_paths = [pathlib.Path(item).resolve() for item in
                      os.environ.get("PYTHONPATH", "").split(os.pathsep) if item]
    if any(site_parts.intersection(path.parts) and root not in path.parents
           for path in explicit_paths):
        raise RuntimeError("ARGOS_TOOLCHAIN_UNAPPROVED_PYTHONPATH_SITE_PACKAGES")
    vendor = root / "setuptools" / "_vendor"
    if not vendor.is_dir():
        raise RuntimeError(f"ARGOS_TOOLCHAIN_SETUPTOOLS_VENDOR_MISSING:{vendor}")
    script_root = pathlib.Path(__file__).resolve().parent
    repo_root = script_root.parents[1]
    standard_roots = {
        pathlib.Path(value).resolve() for key, value in sysconfig.get_paths().items()
        if key in {"stdlib", "platstdlib"} and value
    }
    standard_zip = {path.parent / f"python{sys.version_info.major}{sys.version_info.minor}.zip"
                    for path in standard_roots}
    allowed_exact = {script_root, repo_root, *standard_zip}
    allowed_roots = {root, *standard_roots}
    workspace_value = os.environ.get("PMA_HINT_ALLOWED_WORKSPACE")
    if workspace_value:
        workspace = pathlib.Path(workspace_value)
        if not workspace.is_absolute() or workspace.resolve() == pathlib.Path("/"):
            raise RuntimeError("ARGOS_TOOLCHAIN_ALLOWED_WORKSPACE_INVALID")
        work_root = workspace.resolve()
        current_dir = pathlib.Path.cwd().resolve()
        if current_dir == work_root or work_root in current_dir.parents:
            allowed_exact.add(current_dir)
    filtered = []
    for item in sys.path:
        path = pathlib.Path(item or os.curdir).resolve()
        if site_parts.intersection(path.parts) and root not in path.parents:
            continue
        if path == vendor:
            continue
        if path not in allowed_exact and not any(
                path == allowed or allowed in path.parents for allowed in allowed_roots):
            raise RuntimeError(f"ARGOS_TOOLCHAIN_IMPORT_PATH_UNAPPROVED:{path}")
        filtered.append(item)
    sys.path[:] = filtered
    try:
        root_index = next(index for index, item in enumerate(sys.path)
                          if item and pathlib.Path(item).resolve() == root)
    except StopIteration as exc:
        raise RuntimeError("ARGOS_TOOLCHAIN_EXTERNAL_ROOT_NOT_ON_PATH") from exc
    # External top-level lock wins over vendored copies (notably packaging),
    # while setuptools' vendored jaraco is found before any unapproved path.
    sys.path.insert(root_index + 1, str(vendor))


def probe_startup(root: pathlib.Path) -> None:
    root = root.resolve()
    if os.environ.get("SETUPTOOLS_USE_DISTUTILS") != "local":
        raise RuntimeError("ARGOS_TOOLCHAIN_DISTUTILS_POLICY_MISMATCH")
    isolate_import_path(root)

    # Import setuptools before pip. Its distutils finder intentionally handles
    # pip imports by clearing local distutils and disabling itself, so avoid
    # even a find_spec("pip") call until after this origin check.
    hack = importlib.import_module("_distutils_hack")
    require_origin("_distutils_hack", pathlib.Path(hack.__file__), root)
    hack.add_shim()
    setuptools = importlib.import_module("setuptools")
    require_origin("setuptools", pathlib.Path(setuptools.__file__), root)
    require_distribution_origin("setuptools", root)
    pip_init = root / "pip" / "__init__.py"
    if not pip_init.is_file():
        raise RuntimeError("ARGOS_TOOLCHAIN_PIP_MODULE_MISSING")
    require_origin("pip", pip_init, root)
    require_distribution_origin("pip", root)
    distutils_core = importlib.import_module("distutils.core")
    distutils_path = pathlib.Path(distutils_core.__file__).resolve()
    if root not in distutils_path.parents or "_distutils" not in distutils_path.parts:
        raise RuntimeError(f"ARGOS_TOOLCHAIN_DISTUTILS_ORIGIN_MISMATCH:{distutils_path}")
    require_no_host_site_packages(root)


def probe(root: pathlib.Path) -> None:
    root = root.resolve()
    probe_startup(root)
    setuptools = importlib.import_module("setuptools")

    modules = {
        "setuptools": setuptools,
        "packaging": importlib.import_module("packaging"),
        "wheel": importlib.import_module("wheel"),
        "auditwheel": importlib.import_module("auditwheel"),
        "pyelftools": importlib.import_module("elftools"),
        "pip": importlib.import_module("pip"),
    }
    require_no_host_site_packages(root)

    for name, module in modules.items():
        module_path = pathlib.Path(module.__file__).resolve()
        distribution = require_distribution_origin(name, root)
        metadata_files = [item for item in (distribution.files or [])
                          if item.name == "METADATA" and item.parts and
                          item.parts[0].endswith(".dist-info")]
        metadata_path = pathlib.Path(distribution.locate_file(metadata_files[0])).resolve()
        print(name, distribution.version, module_path, metadata_path)
        require_origin(name, module_path, root)

    # This also checks transitive imports that were loaded while importing any
    # locked package, including modules outside the six named namespaces.
    require_no_host_site_packages(root)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("ARGOS_TOOLCHAIN_PROBE_USAGE")
    try:
        probe(pathlib.Path(sys.argv[1]))
    except Exception as exc:
        print(f"ARGOS_TOOLCHAIN_PROBE_FAIL:{type(exc).__name__}:{exc}", file=sys.stderr)
        raise SystemExit(1)
