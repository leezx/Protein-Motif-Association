#!/usr/bin/env python3
"""Validate the immutable files and pip dependency closure in an offline HINT bundle."""
import hashlib
import json
import os
import re
import sys
import zipfile
from email.parser import Parser

from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import parse_wheel_filename
from packaging.version import Version

RGT_SDIST_SHA256 = "2169e71f2018340d101146bab09bb933a384611c5f7b76f4be5999fa835cac7e"


def wheel_targets_hint(wheel_tags):
    """Check wheel tags against the declared CPython 3.11 Linux x86_64 target.

    Do not use sys_tags(): this validator runs from pmafp, whose Python ABI may
    differ from the isolated HINT target being built.
    """
    platform_tags = {"any", "manylinux1_x86_64",
                     "manylinux2010_x86_64", "manylinux2014_x86_64"}
    platform_tags.update(f"manylinux_2_{minor}_x86_64" for minor in range(5, 24))
    for tag in wheel_tags:
        python_ok = tag.interpreter in ("py3", "cp311")
        abi_ok = tag.abi in ("none", "abi3", "cp311")
        if python_ok and abi_ok and tag.platform in platform_tags:
            return True
    return False


def wheel_requires_hint_python(requires_python, target_version):
    return not requires_python or SpecifierSet(requires_python).contains(
        Version(target_version), prereleases=True
    )


def hint_marker_environment(python_full_version):
    return {
        "implementation_name": "cpython",
        "implementation_version": python_full_version,
        "os_name": "posix",
        "platform_machine": "x86_64",
        "platform_python_implementation": "CPython",
        "platform_release": "",
        "platform_system": "Linux",
        "platform_version": "",
        "python_full_version": python_full_version,
        "python_version": ".".join(python_full_version.split(".")[:2]),
        "sys_platform": "linux",
        "extra": "",
    }


def marker_environment_supported(raw_requirement):
    return not re.search(r"\b(?:platform_release|platform_version)\b", raw_requirement)


def fail(message):
    raise ValueError(message)


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def main():
    bundle = os.path.abspath(sys.argv[1])
    issues = []

    def check(condition, message):
        if not condition:
            issues.append(message)

    manifest_path = os.path.join(bundle, "bundle-manifest.json")
    conda_path = os.path.join(bundle, "conda-explicit-linux-64.lock")
    pip_path = os.path.join(bundle, "pip-requirements.lock")
    artifacts_path = os.path.join(bundle, "artifacts.sha256")
    try:
        with open(manifest_path, encoding="utf-8") as handle:
            manifest = json.load(handle)
        check(manifest.get("schema_version") == 1, "BUNDLE_SCHEMA_INVALID")
        check(manifest.get("target_platform") == "linux-64", "BUNDLE_PLATFORM_INVALID")
        check(manifest.get("python_abi") == "cp311", "BUNDLE_PYTHON_ABI_INVALID")
        try:
            check(tuple(map(int, manifest["glibc_max"].split("."))) <= (2, 23), "BUNDLE_GLIBC_TOO_NEW")
        except (KeyError, ValueError):
            check(False, "BUNDLE_GLIBC_INVALID")
        check(bool(manifest.get("builder")), "BUNDLE_BUILDER_MISSING")
        check(manifest.get("rgt_sdist_sha256") == RGT_SDIST_SHA256, "RGT_SDIST_PROVENANCE_MISMATCH")
        for key, path in (("conda_lock_sha256", conda_path), ("pip_lock_sha256", pip_path), ("artifacts_sha256", artifacts_path)):
            check(manifest.get(key) == sha256(path), f"{key.upper()}_MISMATCH")
        check(bool(manifest.get("conda_version")), "CONDA_BUILDER_VERSION_MISSING")
        check(bool(manifest.get("pip_version")), "PIP_BUILDER_VERSION_MISSING")
        report_relative = manifest.get("rgt_build_report", "")
        if not report_relative or os.path.isabs(report_relative) or ".." in report_relative.split("/"):
            check(False, "RGT_BUILD_REPORT_PATH_INVALID")
        else:
            report_path = os.path.join(bundle, report_relative)
            check(manifest.get("rgt_build_report_sha256") == sha256(report_path), "RGT_BUILD_REPORT_HASH_MISMATCH")
            with open(report_path, encoding="utf-8") as report_handle:
                report = json.load(report_handle)
            check(report.get("rgt_sdist_sha256") == RGT_SDIST_SHA256, "RGT_BUILD_SDIST_MISMATCH")
            check(report.get("builder") == manifest.get("builder"), "RGT_BUILD_IDENTITY_MISMATCH")
            check(report.get("python_abi") == "cp311", "RGT_BUILD_ABI_MISMATCH")
            check(report.get("rgt_wheel") == manifest.get("rgt_wheel"), "RGT_BUILD_WHEEL_NAME_MISMATCH")
            check(report.get("rgt_wheel_sha256") == manifest.get("rgt_wheel_sha256"), "RGT_BUILD_WHEEL_HASH_MISMATCH")
            try:
                check(tuple(map(int, report["glibc_symbol_max"].split("."))) <= (2, 23), "RGT_WHEEL_GLIBC_TOO_NEW")
            except (KeyError, ValueError):
                check(False, "RGT_WHEEL_GLIBC_REPORT_INVALID")
            check(bool(report.get("auditwheel_policy")), "RGT_WHEEL_AUDITWHEEL_REPORT_MISSING")
            check("native_dependencies" in report, "RGT_WHEEL_NATIVE_DEPENDENCIES_MISSING")
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        issues.append(f"BUNDLE_MANIFEST_INVALID: {exc}")
        print("\n".join(issues), file=sys.stderr)
        return 1

    artifacts = {}
    try:
        with open(artifacts_path, encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip() or line.lstrip().startswith("#"):
                    continue
                fields = line.rstrip("\n").split(None, 1)
                if len(fields) != 2 or not re.fullmatch(r"[a-fA-F0-9]{64}", fields[0]):
                    issues.append(f"ARTIFACT_ROW_INVALID:{line_number}")
                    continue
                digest, relative = fields
                if os.path.isabs(relative) or ".." in relative.split("/"):
                    issues.append(f"ARTIFACT_PATH_INVALID:{relative}")
                    continue
                artifacts[relative] = digest.lower()
                path = os.path.join(bundle, relative)
                if not os.path.isfile(path):
                    issues.append(f"MISSING_OR_INVALID_ARTIFACT:{relative}")
                elif sha256(path) != digest.lower():
                    issues.append(f"ARTIFACT_HASH_MISMATCH:{relative}")
    except OSError as exc:
        issues.append(f"ARTIFACT_INVENTORY_INVALID:{exc}")
    report_relative = manifest.get("rgt_build_report", "")
    if artifacts.get(report_relative) != manifest.get("rgt_build_report_sha256", "").lower():
        issues.append("RGT_BUILD_REPORT_NOT_IN_ARTIFACT_INVENTORY")

    repodata_by_subdir = {}
    for subdir in ("linux-64", "noarch"):
        relative = f"conda/{subdir}/repodata.json"
        if relative not in artifacts:
            issues.append(f"REPODATA_NOT_IN_ARTIFACT_INVENTORY:{relative}")
        path = os.path.join(bundle, relative)
        try:
            with open(path, encoding="utf-8") as handle:
                parsed_repodata = json.load(handle)
            if not isinstance(parsed_repodata, dict):
                issues.append(f"REPODATA_ROOT_INVALID:{relative}")
                repodata_by_subdir[subdir] = {}
            elif not isinstance(parsed_repodata.get("packages"), dict):
                issues.append(f"REPODATA_PACKAGES_INVALID:{relative}")
                repodata_by_subdir[subdir] = parsed_repodata
            else:
                repodata_by_subdir[subdir] = parsed_repodata
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            issues.append(f"REPODATA_INVALID:{relative}:{exc}")

    conda_packages = {}
    repodata_dist_keys = {}
    try:
        with open(conda_path, encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip() or line.lstrip().startswith("#"):
                    continue
                fields = line.rstrip("\n").split("\t")
                if len(fields) != 6:
                    issues.append(f"CONDA_LOCK_ROW_INVALID:{line_number}")
                    continue
                subdir, name, version, build, filename, digest = fields
                key = normalized(name)
                if key in conda_packages:
                    issues.append(f"CONDA_LOCK_DUPLICATE:{name}")
                conda_packages[key] = (version, build)
                relative = f"conda/{subdir}/{filename}"
                if subdir not in ("linux-64", "noarch") or "/" in filename or ".." in filename:
                    issues.append(f"CONDA_LOCK_PATH_INVALID:{relative}")
                if not filename.endswith(".tar.bz2"):
                    issues.append(f"CONDA_PACKAGE_FORMAT_UNSUPPORTED:{filename}")
                if artifacts.get(relative) != digest.lower():
                    issues.append(f"CONDA_ARTIFACT_NOT_IN_INVENTORY:{relative}")
                path = os.path.join(bundle, relative)
                if not os.path.isfile(path):
                    issues.append(f"MISSING_CONDA_ARTIFACT:{name}={version}={build}")
                elif sha256(path) != digest.lower():
                    issues.append(f"CONDA_ARTIFACT_HASH_MISMATCH:{relative}")
                package_record = repodata_by_subdir.get(subdir, {}).get("packages", {}).get(filename)
                if package_record is None:
                    issues.append(f"CONDA_LOCK_NOT_IN_REPODATA:{relative}")
                else:
                    for field, expected_value in (("name", name), ("version", version), ("build", build), ("sha256", digest.lower())):
                        observed = package_record.get(field)
                        if observed is None or str(observed).lower() != str(expected_value).lower():
                            issues.append(f"CONDA_REPODATA_{field.upper()}_MISMATCH:{relative}")
                    dist_key = (subdir, key, version, build)
                    prior = repodata_dist_keys.get(dist_key)
                    if prior is not None and prior != filename:
                        issues.append(f"CONDA_REPODATA_DUPLICATE_DIST:{subdir}/{name}/{version}/{build}")
                    repodata_dist_keys[dist_key] = filename
    except OSError as exc:
        issues.append(f"CONDA_LOCK_INVALID:{exc}")
    for name, expected in (("python", None), ("numpy", "1.26.4"), ("setuptools", "80.9.0")):
        value = conda_packages.get(name)
        if value is None or (expected is not None and value[0] != expected):
            issues.append(f"CONDA_PIN_MISSING_OR_WRONG:{name}:{expected or '3.11.x'}")
    if "python" in conda_packages and not conda_packages["python"][0].startswith("3.11."):
        issues.append("CONDA_PIN_MISSING_OR_WRONG:python:3.11.x")

    pip_packages = {}
    try:
        with open(pip_path, encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([A-Za-z0-9_.+-]+) --hash=sha256:([a-fA-F0-9]{64})", line)
                if not match:
                    issues.append(f"PIP_LOCK_ROW_INVALID:{line_number}")
                    continue
                name, version, digest = match.groups()
                key = normalized(name)
                if key in pip_packages:
                    issues.append(f"PIP_LOCK_DUPLICATE:{name}")
                pip_packages[key] = (version, digest.lower())
                if key in conda_packages:
                    issues.append(f"PACKAGE_MANAGER_DUPLICATE:{key}")
    except OSError as exc:
        issues.append(f"PIP_LOCK_INVALID:{exc}")
    if pip_packages.get("rgt", (None,))[0] != "1.0.2":
        issues.append("PIP_PIN_MISSING_OR_WRONG:rgt:1.0.2")
    rgt_wheel = manifest.get("rgt_wheel")
    rgt_hash = manifest.get("rgt_wheel_sha256")
    if pip_packages.get("rgt", (None, None))[1] != rgt_hash:
        issues.append("RGT_WHEEL_HASH_MISMATCH")

    wheelhouse = os.path.join(bundle, "wheels")
    wheel_meta = {}
    try:
        for filename in os.listdir(wheelhouse):
            if not filename.endswith(".whl"):
                issues.append(f"NON_WHEEL_IN_WHEELHOUSE:{filename}")
                continue
            try:
                wheel_name, wheel_version, _build, tags = parse_wheel_filename(filename)
                if not wheel_targets_hint(tags):
                    issues.append(f"INCOMPATIBLE_WHEEL:{filename}")
                    continue
                key = normalized(wheel_name)
                if key in wheel_meta:
                    issues.append(f"DUPLICATE_WHEEL:{key}")
                    continue
                with zipfile.ZipFile(os.path.join(wheelhouse, filename)) as archive:
                    metadata_paths = [p for p in archive.namelist() if p.endswith(".dist-info/METADATA")]
                    if len(metadata_paths) != 1:
                        issues.append(f"WHEEL_METADATA_INVALID:{filename}")
                        continue
                    metadata = Parser().parsestr(archive.read(metadata_paths[0]).decode("utf-8"))
                if normalized(metadata.get("Name", "")) != key or Version(metadata.get("Version", "0")) != wheel_version:
                    issues.append(f"WHEEL_IDENTITY_MISMATCH:{filename}")
                    continue
                target_python = conda_packages.get("python", ("3.11.0", ""))[0]
                requires_python = metadata.get("Requires-Python")
                if not wheel_requires_hint_python(requires_python, target_python):
                    issues.append(f"WHEEL_REQUIRES_PYTHON_MISMATCH:{filename}:{requires_python}:{target_python}")
                wheel_meta[key] = (filename, metadata)
                if key == "rgt" and filename != rgt_wheel:
                    issues.append("RGT_WHEEL_NAME_MISMATCH")
                locked = pip_packages.get(key)
                relative = f"wheels/{filename}"
                if locked is None:
                    issues.append(f"UNLOCKED_WHEEL:{filename}")
                elif locked[0] != str(wheel_version) or locked[1] != sha256(os.path.join(wheelhouse, filename)):
                    issues.append(f"WHEEL_LOCK_MISMATCH:{filename}")
                if artifacts.get(relative) != sha256(os.path.join(wheelhouse, filename)):
                    issues.append(f"WHEEL_ARTIFACT_NOT_IN_INVENTORY:{filename}")
            except (ValueError, OSError, zipfile.BadZipFile) as exc:
                issues.append(f"WHEEL_INVALID:{filename}:{exc}")
    except OSError as exc:
        issues.append(f"WHEELHOUSE_INVALID:{exc}")
    if set(wheel_meta) != set(pip_packages):
        issues.append("WHEELHOUSE_AND_PIP_LOCK_SET_MISMATCH")

    installed = {name: version for name, (version, _build) in conda_packages.items()}
    installed.update({name: value[0] for name, value in pip_packages.items()})
    python_full_version = conda_packages.get("python", ("3.11.0", ""))[0]
    python_major_minor = ".".join(python_full_version.split(".")[:2])
    target_marker_environment = hint_marker_environment(python_full_version)
    for key, (_filename, metadata) in wheel_meta.items():
        for raw_requirement in metadata.get_all("Requires-Dist", []):
            try:
                requirement = Requirement(raw_requirement)
                if requirement.marker and not marker_environment_supported(raw_requirement):
                    issues.append(f"UNSUPPORTED_TARGET_MARKER_ENVIRONMENT:{key}:{raw_requirement}")
                    continue
                if requirement.marker and not requirement.marker.evaluate(target_marker_environment):
                    continue
                dependency = normalized(requirement.name)
                if dependency not in installed:
                    issues.append(f"UNRESOLVED_WHEEL_DEPENDENCY:{key}:{raw_requirement}")
                elif not requirement.specifier.contains(Version(installed[dependency]), prereleases=True):
                    issues.append(f"WHEEL_DEPENDENCY_VERSION_MISMATCH:{key}:{raw_requirement}:{installed[dependency]}")
            except (ValueError, TypeError) as exc:
                issues.append(f"WHEEL_DEPENDENCY_INVALID:{key}:{raw_requirement}:{exc}")

    if issues:
        print("\n".join(issues), file=sys.stderr)
        return 1
    print("HINT_BUNDLE_FILES_AND_PIP_CLOSURE_OK")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (AssertionError, KeyError, OSError, ValueError) as exc:
        print(f"HINT_BUNDLE_VALIDATION_ERROR:{exc}", file=sys.stderr)
        sys.exit(1)
