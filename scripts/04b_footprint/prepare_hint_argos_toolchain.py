#!/usr/bin/env python3
"""Download and safely unpack the hash-pinned pure-Python builder wheels outside Conda prefixes."""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from urllib.parse import urlsplit, urlunsplit
import zipfile
from email.parser import Parser
from pathlib import Path, PurePosixPath


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def sanitize_text(value: str) -> str:
    def clean(match):
        parsed = urlsplit(match.group(0))
        host = parsed.hostname or ""
        if parsed.port:
            host += f":{parsed.port}"
        return urlunsplit((parsed.scheme, host, parsed.path, "", ""))
    return re.sub(r"https?://[^\s\"'<>]+", clean, value)


def parse_lock(path: Path) -> dict[str, tuple[str, str]]:
    expected = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([A-Za-z0-9_.-]+) --hash=sha256:([a-fA-F0-9]{64})", line)
        if not match:
            raise ValueError(f"BUILDER_TOOL_LOCK_ROW_INVALID:{number}")
        name = re.sub(r"[-_.]+", "-", match.group(1)).lower()
        if name in expected:
            raise ValueError(f"BUILDER_TOOL_LOCK_DUPLICATE:{name}")
        expected[name] = (match.group(2), match.group(3).lower())
    if not expected:
        raise ValueError("BUILDER_TOOL_LOCK_EMPTY")
    return expected


def safe_wheel_path(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or "\\" in name:
        raise ValueError(f"WHEEL_PATH_INVALID:{name}")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", required=True, type=Path)
    parser.add_argument("--lock", required=True, type=Path)
    parser.add_argument("--downloads", required=True, type=Path)
    parser.add_argument("--python-root", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    python = args.python.resolve()
    lock = args.lock.resolve()
    downloads = args.downloads.resolve()
    python_root = args.python_root.resolve()
    report = args.report.resolve()
    if python_root.exists() and any(python_root.iterdir()):
        raise ValueError("ARGOS_TOOLCHAIN_PYTHON_DIR_MUST_BE_EMPTY")
    if downloads.exists() and any(downloads.iterdir()):
        raise ValueError("ARGOS_TOOLCHAIN_DOWNLOAD_DIR_MUST_BE_EMPTY")
    downloads.mkdir(parents=True, exist_ok=True)
    python_root.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    expected = parse_lock(lock)
    command = [str(python), "-m", "pip", "download", "--require-hashes", "--no-deps",
               "--only-binary=:all:", "--dest", str(downloads), "-r", str(lock)]
    proc = subprocess.run(command, check=False, text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, env={**os.environ, "PYTHONNOUSERSITE": "1",
                                                         "PYTHONDONTWRITEBYTECODE": "1"})
    (report.parent / "toolchain-download.log").write_text(
        f"$ {sanitize_text(' '.join(command))}\n{sanitize_text(proc.stdout)}\n[exit={proc.returncode}]\n", encoding="utf-8")
    if proc.returncode:
        raise RuntimeError(f"ARGOS_TOOLCHAIN_DOWNLOAD_FAILED:{report.parent / 'toolchain-download.log'}")
    wheels = sorted(downloads.glob("*.whl"))
    if len(wheels) != len(expected):
        raise RuntimeError(f"ARGOS_TOOLCHAIN_WHEEL_COUNT_MISMATCH:{len(wheels)}:{len(expected)}")
    inventory = []
    for wheel in wheels:
        if not wheel.name.endswith("-py3-none-any.whl"):
            raise RuntimeError(f"ARGOS_TOOLCHAIN_WHEEL_NOT_PURE_PY3:{wheel.name}")
        if digest(wheel) not in {value[1] for value in expected.values()}:
            raise RuntimeError(f"ARGOS_TOOLCHAIN_WHEEL_HASH_UNEXPECTED:{wheel.name}")
        with zipfile.ZipFile(wheel) as archive:
            members = archive.namelist()
            for name in members:
                path = safe_wheel_path(name)
                if path.parts and path.parts[0].endswith(".data"):
                    if len(path.parts) > 1 and path.parts[1] in {"purelib", "platlib"}:
                        path = PurePosixPath(*path.parts[2:])
                    elif len(path.parts) > 1 and path.parts[1] == "scripts":
                        continue
                    else:
                        raise RuntimeError(f"ARGOS_TOOLCHAIN_WHEEL_DATA_UNSUPPORTED:{wheel.name}:{name}")
                if not path.parts:
                    raise RuntimeError(f"ARGOS_TOOLCHAIN_WHEEL_PATH_EMPTY:{wheel.name}:{name}")
            metadata_names = [name for name in members if name.endswith(".dist-info/METADATA")]
            if len(metadata_names) != 1:
                raise RuntimeError(f"ARGOS_TOOLCHAIN_METADATA_INVALID:{wheel.name}")
            metadata = Parser().parsestr(archive.read(metadata_names[0]).decode("utf-8"))
            package = re.sub(r"[-_.]+", "-", metadata.get("Name", "")).lower()
            version = metadata.get("Version", "")
            if package not in expected or expected[package][0] != version:
                raise RuntimeError(f"ARGOS_TOOLCHAIN_METADATA_IDENTITY_MISMATCH:{wheel.name}:{package}:{version}")
            if digest(wheel) != expected[package][1]:
                raise RuntimeError(f"ARGOS_TOOLCHAIN_LOCK_HASH_MISMATCH:{wheel.name}")
            for name in members:
                path = safe_wheel_path(name)
                if path.parts and path.parts[0].endswith(".data"):
                    if len(path.parts) > 1 and path.parts[1] in {"purelib", "platlib"}:
                        path = PurePosixPath(*path.parts[2:])
                    elif len(path.parts) > 1 and path.parts[1] == "scripts":
                        continue
                    else:
                        continue
                if name.endswith("/"):
                    continue
                destination = python_root.joinpath(*path.parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(name) as source, destination.open("xb") as out:
                    out.write(source.read())
            inventory.append({"name": package, "version": version, "wheel": wheel.name,
                              "sha256": digest(wheel), "requires_python": metadata.get("Requires-Python"),
                              "requires_dist": metadata.get_all("Requires-Dist", [])})
    if {item["name"] for item in inventory} != set(expected):
        raise RuntimeError("ARGOS_TOOLCHAIN_LOCK_CLOSURE_MISMATCH")
    sys.path.insert(0, str(python_root))
    from packaging.requirements import Requirement
    from packaging.utils import canonicalize_name
    from packaging.version import Version
    from packaging.markers import default_environment
    versions = {name: value[0] for name, value in expected.items()}
    environment = default_environment()
    environment.update({"python_version": "3.11", "python_full_version": "3.11.17",
                        "implementation_name": "cpython", "platform_python_implementation": "CPython",
                        "sys_platform": "linux", "platform_system": "Linux", "platform_machine": "x86_64"})
    for item in inventory:
        for raw in item["requires_dist"]:
            requirement = Requirement(raw)
            if requirement.marker is not None and not requirement.marker.evaluate(environment=environment):
                continue
            dependency = canonicalize_name(requirement.name)
            if dependency not in versions:
                raise RuntimeError(f"ARGOS_TOOLCHAIN_DEPENDENCY_NOT_LOCKED:{item['name']}:{dependency}")
            if requirement.specifier and not requirement.specifier.contains(Version(versions[dependency]), prereleases=True):
                raise RuntimeError(f"ARGOS_TOOLCHAIN_DEPENDENCY_VERSION_MISMATCH:{item['name']}:{dependency}:{versions[dependency]}")
    probe_env = {**os.environ, "PYTHONPATH": str(python_root), "PYTHONNOUSERSITE": "1",
                 "PYTHONDONTWRITEBYTECODE": "1"}
    probe_code = """import importlib.metadata as m, pathlib, sys
root = pathlib.Path(sys.argv[1]).resolve()
mods = {'pip': __import__('pip'), 'packaging': __import__('packaging'),
        'setuptools': __import__('setuptools'), 'wheel': __import__('wheel'),
        'auditwheel': __import__('auditwheel'), 'pyelftools': __import__('elftools')}
expected = {'pip':'25.2', 'packaging':'25.0', 'setuptools':'80.9.0',
            'wheel':'0.45.1', 'auditwheel':'6.0.0', 'pyelftools':'0.31'}
for name, module in mods.items():
    path = pathlib.Path(module.__file__).resolve()
    print(name, m.version(name), path)
    if m.version(name) != expected[name] or root not in path.parents:
        raise SystemExit(3)
"""
    probe = subprocess.run([str(python), "-c", probe_code, str(python_root)], env=probe_env,
                           check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (report.parent / "toolchain-import-probe.log").write_text(probe.stdout, encoding="utf-8")
    if probe.returncode:
        raise RuntimeError("ARGOS_TOOLCHAIN_IMPORT_PROBE_FAIL")
    probe = subprocess.run([str(python), "-c", "import sys; print(sys.version_info[:2])"],
                           check=True, text=True, stdout=subprocess.PIPE)
    if probe.stdout.strip() != "(3, 11)":
        raise RuntimeError(f"ARGOS_TOOLCHAIN_PYTHON_MISMATCH:{probe.stdout.strip()}")
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps({"python": str(python), "python_version": "3.11",
                                  "lock_sha256": digest(lock), "wheels": inventory,
                                  "python_root": str(python_root)}, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ARGOS_TOOLCHAIN_PREP_FAIL:{type(exc).__name__}:{exc}", file=sys.stderr)
        raise SystemExit(1)
