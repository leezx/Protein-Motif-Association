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
from pip._vendor.packaging.specifiers import SpecifierSet
from pip._vendor.packaging.tags import Tag, parse_tag
from pip._vendor.packaging.utils import canonicalize_name, parse_wheel_filename
from pip._vendor.packaging.version import Version


def toolchain_probe_environment(python_root: Path, base: dict[str, str] | None = None) -> dict[str, str]:
    """Return a fail-closed environment for importing the external builder wheels."""
    return {**(os.environ if base is None else base), "PYTHONPATH": str(python_root),
            "PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1",
            "SETUPTOOLS_USE_DISTUTILS": "local"}


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


def validate_py3_none_any_wheel(wheel: Path, python_version: str) -> tuple[str, str, object]:
    """Validate filename, metadata tags, Requires-Python, and absence of native payload."""
    name, version, _build, filename_tags = parse_wheel_filename(wheel.name)
    expected_tag = Tag("py3", "none", "any")
    if filename_tags != {expected_tag}:
        raise RuntimeError(f"ARGOS_TOOLCHAIN_WHEEL_NOT_PURE_PY3:{wheel.name}")
    with zipfile.ZipFile(wheel) as archive:
        members = archive.namelist()
        root_dist_infos = {
            PurePosixPath(item).parts[0]
            for item in members
            if PurePosixPath(item).parts
            and PurePosixPath(item).parts[0].endswith(".dist-info")
        }
        expected_dist_info = f"{canonicalize_name(str(name)).replace('-', '_')}-{version}.dist-info"
        metadata_path = f"{expected_dist_info}/METADATA"
        wheel_path = f"{expected_dist_info}/WHEEL"
        if (root_dist_infos != {expected_dist_info} or members.count(metadata_path) != 1 or
                members.count(wheel_path) != 1):
            raise RuntimeError(f"ARGOS_TOOLCHAIN_WHEEL_METADATA_INVALID:{wheel.name}")
        metadata = Parser().parsestr(archive.read(metadata_path).decode("utf-8"))
        wheel_metadata = Parser().parsestr(archive.read(wheel_path).decode("utf-8"))
        declared_tags = set()
        for value in wheel_metadata.get_all("Tag", []):
            declared_tags.update(parse_tag(value))
        if declared_tags != filename_tags:
            raise RuntimeError(f"ARGOS_TOOLCHAIN_WHEEL_TAG_MISMATCH:{wheel.name}")
        if wheel_metadata.get("Root-Is-Purelib", "").lower() != "true":
            raise RuntimeError(f"ARGOS_TOOLCHAIN_WHEEL_NOT_PURELIB:{wheel.name}")
        requires_python = metadata.get("Requires-Python")
        if requires_python and not SpecifierSet(requires_python).contains(Version(python_version), prereleases=True):
            raise RuntimeError(f"ARGOS_TOOLCHAIN_REQUIRES_PYTHON_MISMATCH:{wheel.name}:{requires_python}")
        native_suffixes = (".pyd", ".dll", ".dylib", ".o", ".a", ".obj", ".lib")
        for member in members:
            if member.endswith("/"):
                continue
            lower_name = member.lower()
            is_shared_object = lower_name.endswith(".so") or ".so." in lower_name
            if (is_shared_object or lower_name.endswith(native_suffixes) or
                    archive.read(member).startswith(bytes((0x7f,)) + b"ELF")):
                raise RuntimeError(f"ARGOS_TOOLCHAIN_PURE_WHEEL_HAS_NATIVE_PAYLOAD:{wheel.name}:{member}")
    normalized_name = re.sub(r"[-_.]+", "-", metadata.get("Name", "")).lower()
    if normalized_name != re.sub(r"[-_.]+", "-", str(name)).lower() or Version(metadata.get("Version", "0")) != version:
        raise RuntimeError(f"ARGOS_TOOLCHAIN_WHEEL_FILENAME_METADATA_MISMATCH:{wheel.name}")
    return normalized_name, str(version), metadata


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
        package, version, metadata = validate_py3_none_any_wheel(wheel, "3.11.17")
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
    probe_env = toolchain_probe_environment(python_root)
    probe_script = Path(__file__).with_name("probe_hint_argos_toolchain.py")
    probe = subprocess.run([str(python), str(probe_script), str(python_root)], env=probe_env,
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
