#!/usr/bin/env python3
"""Build a CPython 3.11/Linux HINT bundle from a pinned Conda solve.

This program is intentionally limited to artifact construction. It never
creates an Argos environment. Bundle and evidence directories must both be
outside the repository. Run only after review in the configured Docker or
Argos-native Linux environment.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import shlex
import tarfile
import urllib.request
import zipfile
from urllib.parse import urlsplit, urlunsplit
from datetime import datetime, timezone
from email.parser import Parser
from pathlib import Path

from packaging.utils import canonicalize_name, parse_wheel_filename

RGT_SHA256 = "2169e71f2018340d101146bab09bb933a384611c5f7b76f4be5999fa835cac7e"
TARGET_SPECS = ("python=3.11", "numpy=1.26.4", "setuptools=80.9.0", "pip")
SYSTEM_RUNTIME_LIBS = {
    "ld-linux-x86-64.so.2", "libc.so.6", "libm.so.6", "libpthread.so.0",
    "librt.so.1", "libdl.so.2", "libutil.so.1", "libresolv.so.2", "libnsl.so.1",
    "libgcc_s.so.1", "linux-vdso.so.1",
}
RUN_LOG: Path | None = None


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def md5(path: Path) -> str:
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sanitize_url(value: str) -> str:
    parsed = urlsplit(value)
    host = parsed.hostname or ""
    if parsed.port:
        host += f":{parsed.port}"
    return urlunsplit((parsed.scheme, host, parsed.path, "", ""))


def sanitize_evidence(value):
    """Remove URL credentials and query strings before writing solver evidence."""
    if isinstance(value, dict):
        cleaned = {}
        for key, item in value.items():
            if key in {"url", "base_url", "channel", "channel_url"} and isinstance(item, str):
                cleaned[key] = sanitize_url(item)
            else:
                cleaned[key] = sanitize_evidence(item)
        return cleaned
    if isinstance(value, list):
        return [sanitize_evidence(item) for item in value]
    if isinstance(value, str) and value.startswith(("https://", "http://")):
        return sanitize_url(value)
    return value


def sanitize_text(value: str) -> str:
    return re.sub(r"https?://[^\s\"'<>]+", lambda match: sanitize_url(match.group(0)), value)


def run(argv: list[str], *, capture: bool = False, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(argv, check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            env=env)
    output = result.stdout or ""
    if RUN_LOG:
        with RUN_LOG.open("a", encoding="utf-8") as log:
            log.write(f"\n[{datetime.now(timezone.utc).isoformat()}] $ {sanitize_text(shlex.join(argv))}\n")
            log.write(sanitize_text(output))
            log.write(f"\n[exit={result.returncode}]\n")
    if result.returncode:
        raise subprocess.CalledProcessError(result.returncode, argv, output=output)
    if output and not capture:
        sys.stdout.write(output)
    return output


def conda_dry_run(conda: str, prefix: Path, options: list[str], specs: tuple[str, ...],
                  package_cache: Path | None = None) -> str:
    if prefix.exists():
        raise RuntimeError(f"CONDA_DRY_RUN_TARGET_ALREADY_EXISTS:{prefix}")
    command = [conda, "create", "--dry-run", "--json", "--yes", *options,
               "-p", str(prefix), *specs]
    env = os.environ.copy()
    if package_cache is not None:
        package_cache.mkdir(parents=True, exist_ok=True)
        env["CONDA_PKGS_DIRS"] = str(package_cache.resolve())
    output = run(command, capture=True, env=env)
    if prefix.exists():
        raise RuntimeError(f"CONDA_DRY_RUN_CREATED_PREFIX:{prefix}")
    return output


def require_builder() -> tuple[str, str]:
    if platform.system() != "Linux" or platform.machine() not in ("x86_64", "AMD64"):
        raise RuntimeError("BUILDER_PLATFORM_MUST_BE_LINUX_X86_64")
    if sys.version_info[:2] != (3, 11):
        raise RuntimeError(f"BUILDER_PYTHON_MUST_BE_3_11:{platform.python_version()}")
    libc, version = platform.libc_ver()
    if libc != "glibc" or tuple(map(int, version.split(".")[:2])) > (2, 23):
        raise RuntimeError(f"BUILDER_GLIBC_MUST_BE_LE_2_23:{libc}:{version}")
    mode = os.environ.get("PMA_HINT_BUILDER_MODE", "docker-image")
    if mode == "docker-image":
        image = os.environ.get("PMA_HINT_BUILDER_IMAGE", "")
        if not re.fullmatch(r"[^\s]+@sha256:[0-9a-f]{64}", image):
            raise RuntimeError("PMA_HINT_BUILDER_IMAGE_MUST_BE_DIGEST_PINNED")
        for path in (Path("/opt/conda/build-toolchain-explicit.txt"),
                     Path("/opt/conda/build-toolchain-pip.json")):
            if not path.is_file() or path.stat().st_size == 0:
                raise RuntimeError(f"PREPROVISIONED_TOOLCHAIN_LOCK_MISSING:{path}")
    elif mode == "argos-native":
        report = Path(os.environ.get("PMA_HINT_HOST_TOOLCHAIN_REPORT", ""))
        if not report.is_file() or report.stat().st_size == 0:
            raise RuntimeError("ARGOS_HOST_TOOLCHAIN_REPORT_MISSING")
        toolchain = Path(os.environ.get("PMA_HINT_EXTERNAL_TOOLCHAIN", ""))
        if not toolchain.is_dir():
            raise RuntimeError("ARGOS_EXTERNAL_TOOLCHAIN_MISSING")
        package_cache = Path(os.environ.get("CONDA_PKGS_DIRS", ""))
        if not package_cache.is_absolute():
            raise RuntimeError("ARGOS_CONDA_PACKAGE_CACHE_MUST_BE_EXPLICIT_EXTERNAL_PATH")
        try:
            expected = {"pip": "25.2", "packaging": "25.0", "setuptools": "80.9.0",
                        "wheel": "0.45.1", "auditwheel": "6.0.0", "pyelftools": "0.31"}
            import packaging, pip, setuptools, wheel, auditwheel, elftools
            modules = {"pip": pip, "packaging": packaging, "setuptools": setuptools,
                       "wheel": wheel, "auditwheel": auditwheel, "pyelftools": elftools}
            for name, module in modules.items():
                module_path = Path(module.__file__).resolve()
                if toolchain.resolve() not in module_path.parents:
                    raise RuntimeError(f"ARGOS_TOOLCHAIN_IMPORT_OUTSIDE_EXTERNAL_DIRECTORY:{name}:{module_path}")
                observed = importlib.metadata.version(name)
                if observed != expected[name]:
                    raise RuntimeError(f"ARGOS_TOOLCHAIN_VERSION_MISMATCH:{name}:{observed}:{expected[name]}")
        except ImportError as exc:
            raise RuntimeError(f"ARGOS_EXTERNAL_TOOLCHAIN_MODULE_MISSING:{exc.name}") from exc
    else:
        raise RuntimeError(f"BUILDER_MODE_UNSUPPORTED:{mode}")
    conda = shutil.which("conda")
    if not conda:
        raise RuntimeError("CONDA_EXECUTABLE_MISSING")
    expected_conda = os.environ.get("PMA_HINT_CONDA_EXECUTABLE")
    if mode == "argos-native":
        require_audited_conda(conda, expected_conda)
    executables = [("readelf", "READELF_MISSING_CANNOT_PROVE_CONDA_ABI"),
                   ("gcc", "GCC_MISSING_FOR_CONTROLLED_RGT_BUILD")]
    if mode == "docker-image":
        executables.append(("auditwheel", "AUDITWHEEL_MISSING_CANNOT_PROVE_WHEEL_ABI"))
    for executable, code in executables:
        if not shutil.which(executable):
            raise RuntimeError(code)
    return conda, version


def auditwheel_command(*args: str) -> list[str]:
    if os.environ.get("PMA_HINT_BUILDER_MODE", "docker-image") == "argos-native":
        return [sys.executable, "-m", "auditwheel", *args]
    return ["auditwheel", *args]


def validate_audited_conda(conda: str, expected: str) -> None:
    if not expected:
        raise RuntimeError("ARGOS_AUDITED_CONDA_EXECUTABLE_REQUIRED")
    if Path(conda).resolve() != Path(expected).resolve():
        raise RuntimeError("ARGOS_CONDA_PATH_DOES_NOT_MATCH_AUDITED_EXECUTABLE")


def require_audited_conda(conda: str, expected: str | None) -> None:
    validate_audited_conda(conda, expected or "")


def load_solver_plan(conda: str, work: Path, package_cache: Path | None = None) -> tuple[list[dict], str, str]:
    plan_path = work / "conda-solve.json"
    solve_prefix = work / "solve-prefix"
    channel = os.environ.get("PMA_HINT_ARGOS_CONDA_CHANNEL", "conda-forge")
    if os.environ.get("PMA_HINT_BUILDER_MODE") == "argos-native" and not channel.startswith("https://"):
        raise RuntimeError("ARGOS_CONDA_CHANNEL_MUST_BE_EXPLICIT_HTTPS_URL")
    if os.environ.get("PMA_HINT_BUILDER_MODE") == "argos-native":
        parsed_channel = urlsplit(channel)
        if not parsed_channel.netloc or parsed_channel.username or parsed_channel.password or parsed_channel.query or parsed_channel.fragment:
            raise RuntimeError("ARGOS_CONDA_CHANNEL_MUST_NOT_CONTAIN_CREDENTIALS_OR_QUERY")
    options = ["--no-default-packages", "--override-channels", "-c", channel]
    command = [conda, "create", "--dry-run", "--json", "--yes", *options,
               "-p", str(solve_prefix), *TARGET_SPECS]
    repodata_before = {}
    if os.environ.get("PMA_HINT_BUILDER_MODE") == "argos-native":
        for subdir in ("linux-64", "noarch"):
            repodata_before[subdir] = fetch_repodata_snapshot(channel, subdir, work, load_records=False)
    output = conda_dry_run(conda, solve_prefix, options, TARGET_SPECS, package_cache=package_cache)
    try:
        parsed = json.loads(output)
        links = parsed["actions"]["LINK"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise RuntimeError(f"CONDA_SOLVER_JSON_INVALID:{exc}") from exc
    if not links:
        raise RuntimeError("CONDA_SOLVER_LINK_EMPTY")
    if repodata_before:
        repodata_by_subdir = {}
        for subdir in ("linux-64", "noarch"):
            snapshot = fetch_repodata_snapshot(channel, subdir, work, load_records=True)
            if snapshot["sha256"] != repodata_before[subdir]["sha256"]:
                raise RuntimeError(f"ARGOS_UPSTREAM_REPODATA_CHANGED_DURING_SOLVE:{subdir}")
            repodata_by_subdir[subdir] = snapshot
        for item in links:
            subdir = item.get("subdir") or item.get("platform")
            url = item.get("url", "")
            if subdir not in ("linux-64", "noarch"):
                subdir = "noarch" if "/noarch/" in url else "linux-64" if "/linux-64/" in url else None
            filename = item.get("fn") or url.rsplit("/", 1)[-1]
            snapshot = repodata_by_subdir.get(subdir)
            source_record = (snapshot["packages"].get(filename) if snapshot else None)
            if source_record is None:
                raise RuntimeError(f"ARGOS_UPSTREAM_REPODATA_RECORD_MISSING:{subdir}:{filename}")
            for key, value in (("name", item.get("name")), ("version", item.get("version")),
                               ("build", item.get("build") or item.get("build_string")),
                               ("sha256", item.get("sha256"))):
                if source_record.get(key) != value:
                    raise RuntimeError(f"ARGOS_SOLVER_REPODATA_IDENTITY_MISMATCH:{filename}:{key}")
            for key in ("depends", "constrains"):
                link_value = item.get(key, [])
                source_value = source_record.get(key, [])
                if not isinstance(link_value, list) or not isinstance(source_value, list):
                    raise RuntimeError(f"ARGOS_SOLVER_REPODATA_METADATA_MISSING:{filename}:{key}")
                if sorted(link_value) != sorted(source_value):
                    raise RuntimeError(f"ARGOS_SOLVER_REPODATA_METADATA_MISMATCH:{filename}:{key}")
            item["pma_upstream_repodata_record"] = source_record
            item["pma_upstream_repodata"] = {"url": snapshot["url"], "sha256": snapshot["sha256"]}
    plan_path.write_text(json.dumps(sanitize_evidence(parsed), indent=2, sort_keys=True) + "\n",
                         encoding="utf-8")
    return links, " ".join(command), output


def fetch_repodata_snapshot(channel: str, subdir: str, work: Path, *, load_records: bool) -> dict:
    if subdir not in ("linux-64", "noarch"):
        raise RuntimeError(f"ARGOS_REPODATA_SUBDIR_UNSUPPORTED:{subdir}")
    url = f"{channel.rstrip('/')}/{subdir}/repodata.json"
    path = work / f"upstream-repodata-{subdir}.json.tmp"
    try:
        urllib.request.urlretrieve(url, path)
        digest = sha256(path)
        result = {"url": sanitize_url(url), "sha256": digest}
        if load_records:
            try:
                with path.open(encoding="utf-8") as stream:
                    repodata = json.load(stream)
            except (OSError, json.JSONDecodeError) as exc:
                raise RuntimeError(f"ARGOS_UPSTREAM_REPODATA_INVALID:{subdir}:{exc}") from exc
            packages = repodata.get("packages")
            if not isinstance(packages, dict):
                raise RuntimeError(f"ARGOS_UPSTREAM_REPODATA_PACKAGES_MISSING:{subdir}")
            result["packages"] = {name: record for name, record in packages.items()
                                   if name.endswith(".tar.bz2")}
        return result
    except (OSError, urllib.error.URLError) as exc:
        raise RuntimeError(f"ARGOS_UPSTREAM_REPODATA_FETCH_FAILED:{subdir}:{sanitize_text(str(exc))}") from exc
    finally:
        path.unlink(missing_ok=True)


def copy_conda_closure(links: list[dict], bundle: Path) -> list[dict]:
    records = []
    for item in links:
        url = item.get("url") or item.get("base_url", "").rstrip("/") + "/" + item.get("fn", "")
        filename = item.get("fn") or url.rsplit("/", 1)[-1]
        subdir = item.get("subdir") or item.get("platform")
        if subdir not in ("linux-64", "noarch"):
            subdir = "noarch" if "/noarch/" in url else "linux-64" if "/linux-64/" in url else None
        digest = item.get("sha256")
        if subdir not in ("linux-64", "noarch") or not filename.endswith(".tar.bz2"):
            raise RuntimeError(f"UNSUPPORTED_CONDA_ARTIFACT:{subdir}:{filename}")
        if not re.fullmatch(r"[0-9a-fA-F]{64}", str(digest or "")):
            raise RuntimeError(f"CONDA_SHA256_MISSING:{filename}")
        if not url.startswith("https://"):
            raise RuntimeError(f"CONDA_SOURCE_URL_INVALID:{filename}")
        destination = bundle / "conda" / subdir / filename
        destination.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(url, destination)
        if sha256(destination) != digest.lower():
            raise RuntimeError(f"CONDA_SHA256_MISMATCH:{filename}")
        with tarfile.open(destination, "r:bz2") as archive:
            index = json.load(archive.extractfile("info/index.json"))
        record = {"subdir": subdir, "name": index["name"], "version": index["version"],
                  "build": index["build"], "filename": filename, "sha256": digest.lower()}
        plan_build = item.get("build") or item.get("build_string")
        if (record["name"], record["version"], record["build"]) != (
                item.get("name"), item.get("version"), plan_build):
            raise RuntimeError(f"CONDA_PACKAGE_IDENTITY_MISMATCH:{filename}")
        record["md5"] = md5(destination)
        record["size"] = destination.stat().st_size
        record["source_url"] = sanitize_url(url)
        record["index_record"] = index
        if "pma_upstream_repodata_record" in item:
            record["source_record"] = item["pma_upstream_repodata_record"]
            record["source_repodata"] = item["pma_upstream_repodata"]
            record["solver_record"] = {key: item.get(key, []) for key in ("depends", "constrains")}
        else:
            record["source_record"] = {key: value for key, value in item.items()
                                       if key not in {"url", "base_url", "channel", "channel_url"}}
        records.append(record)
    return records


def build_local_repodata(records: list[dict], subdir: str) -> dict:
    if subdir not in ("linux-64", "noarch"):
        raise RuntimeError(f"REPODATA_SUBDIR_UNSUPPORTED:{subdir}")
    packages = {}
    for row in records:
        if row["subdir"] != subdir:
            continue
        source = row.get("source_record") or {}
        index = row.get("index_record") or {}
        filename = row["filename"]
        if not filename.endswith(".tar.bz2"):
            raise RuntimeError(f"REPODATA_ARCHIVE_UNSUPPORTED:{filename}")
        if not isinstance(source.get("depends"), list):
            raise RuntimeError(f"REPODATA_UPSTREAM_DEPENDS_MISSING:{filename}")
        source_repodata = row.get("source_repodata")
        solver_record = row.get("solver_record")
        if source_repodata is not None:
            if (not source_repodata.get("url", "").startswith("https://") or
                    not re.fullmatch(r"[a-fA-F0-9]{64}", source_repodata.get("sha256", ""))):
                raise RuntimeError(f"REPODATA_UPSTREAM_PROVENANCE_INVALID:{filename}")
            if not isinstance(solver_record, dict):
                raise RuntimeError(f"REPODATA_SOLVER_RECORD_MISSING:{filename}")
            for key in ("depends", "constrains"):
                upstream = source.get(key, [])
                solved = solver_record.get(key, [])
                if not isinstance(upstream, list) or not isinstance(solved, list):
                    raise RuntimeError(f"REPODATA_SOLVER_METADATA_MISSING:{filename}:{key}")
                if sorted(upstream) != sorted(solved):
                    raise RuntimeError(f"REPODATA_SOLVER_SOURCE_DEPENDENCY_MISMATCH:{filename}:{key}")
        record = {key: value for key, value in source.items()
                  if key in {"name", "version", "build", "build_number", "depends", "constrains",
                             "track_features", "features", "noarch", "arch", "platform", "license",
                             "license_family", "timestamp", "subdir"}}
        for key in ("name", "version", "build"):
            expected = row[key]
            observed = index.get(key, source.get(key))
            if observed != expected:
                raise RuntimeError(f"REPODATA_ARCHIVE_IDENTITY_MISMATCH:{filename}:{key}:{observed}:{expected}")
            record[key] = expected
        if record.get("subdir", subdir) != subdir:
            raise RuntimeError(f"REPODATA_UPSTREAM_SUBDIR_MISMATCH:{filename}:{record.get('subdir')}:{subdir}")
        index = row.get("index_record") or {}
        dependency_diff = {}
        for key in ("depends", "constrains"):
            index_value = index.get(key, [])
            source_value = source.get(key, [])
            if not isinstance(index_value, list) or not isinstance(source_value, list):
                raise RuntimeError(f"REPODATA_DEPENDENCY_METADATA_INVALID:{filename}:{key}")
            if sorted(index_value) != sorted(source_value):
                if source_repodata is None:
                    raise RuntimeError(f"REPODATA_DEPENDENCY_DIFF_WITHOUT_UPSTREAM_EVIDENCE:{filename}:{key}")
                dependency_diff[key] = {"archive_index": index_value, "upstream_repodata": source_value}
        if dependency_diff:
            row["dependency_metadata_diff"] = dependency_diff
        record.update({"subdir": subdir, "fn": filename, "sha256": row["sha256"],
                       "md5": row["md5"], "size": row["size"]})
        if filename in packages:
            raise RuntimeError(f"REPODATA_DUPLICATE_FILENAME:{filename}")
        packages[filename] = record
    if not packages:
        raise RuntimeError(f"REPODATA_SUBDIR_EMPTY:{subdir}")
    return {"info": {"subdir": subdir, "repodata_version": 1},
            "packages": packages, "packages.conda": {}, "removed": []}


def write_local_repodata(records: list[dict], channel: Path) -> None:
    for subdir in ("linux-64", "noarch"):
        directory = channel / subdir
        directory.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(build_local_repodata(records, subdir), sort_keys=True, separators=(",", ":")) + "\n"
        (directory / "repodata.json").write_text(payload, encoding="utf-8")
        (directory / "current_repodata.json").write_text(payload, encoding="utf-8")


def version_max(values: list[str]) -> str:
    if not values:
        return "2.0"
    return ".".join(map(str, max(tuple(map(int, value.split("."))) for value in values)))


def readelf_versions(output: str, prefix: str, section: str) -> list[str]:
    start = output.find(f"Version {section} section")
    if start < 0:
        return []
    body = output[start:]
    end = body.find("\nVersion ", 1)
    if end >= 0:
        body = body[:end]
    return re.findall(rf"{re.escape(prefix)}_(\d+(?:\.\d+)+)", body)


def check_elf_contract(machine: str, needed: set[str], package_libraries: set[str]) -> list[str]:
    problems = []
    if machine.strip() != "Advanced Micro Devices X86-64":
        problems.append(f"ELF_MACHINE_UNSUPPORTED:{machine.strip()}")
    unresolved = sorted(needed - package_libraries - SYSTEM_RUNTIME_LIBS)
    if unresolved:
        problems.append("ELF_NEEDED_UNRESOLVED:" + ",".join(unresolved))
    return problems


def abi_provider_compatible(required: list[str], provided: list[str]) -> bool:
    if not required:
        return True
    if not provided:
        return False
    return max(tuple(map(int, item.split("."))) for item in required) <= max(
        tuple(map(int, item.split("."))) for item in provided
    )


def audit_conda_elf(records: list[dict], bundle: Path, work: Path) -> dict:
    readelf = shutil.which("readelf")
    if not readelf:
        raise RuntimeError("READELF_MISSING_CANNOT_PROVE_CONDA_ABI")
    glibc, glibcxx, cxxabi, provided_glibcxx, provided_cxxabi = [], [], [], [], []
    needed_libraries, package_libraries, package_elf_files, package_symlinks, checked = set(), set(), set(), [], 0
    for record in records:
        archive_path = bundle / "conda" / record["subdir"] / record["filename"]
        with tarfile.open(archive_path, "r:bz2") as archive:
            for member in archive:
                if member.isdir():
                    continue
                basename = Path(member.name).name
                if member.issym() or member.islnk():
                    package_symlinks.append((basename, Path(member.linkname).name))
                elif member.isfile():
                    source = archive.extractfile(member)
                    if source and source.read(4) == b"\x7fELF":
                        package_elf_files.add(basename)
    package_libraries.update(package_elf_files)
    package_libraries.update(alias for alias, target in package_symlinks if target in package_elf_files)
    for record in records:
        archive_path = bundle / "conda" / record["subdir"] / record["filename"]
        with tarfile.open(archive_path, "r:bz2") as archive:
            for member in archive:
                if member.isdir():
                    continue
                if not member.isfile():
                    continue
                source = archive.extractfile(member)
                if source is None or source.read(4) != b"\x7fELF":
                    continue
                source.seek(0)
                staged = work / f"elf-{checked}"
                with staged.open("wb") as out:
                    shutil.copyfileobj(source, out)
                header = run([readelf, "--file-header", str(staged)], capture=True)
                machine_match = re.search(r"^\s*Machine:\s*(.+)$", header, re.MULTILINE)
                if not machine_match:
                    raise RuntimeError(f"ELF_MACHINE_UNREADABLE:{member.name}")
                elf_problems = check_elf_contract(machine_match.group(1), set(), package_libraries)
                if elf_problems:
                    raise RuntimeError(f"{elf_problems[0]}:{member.name}")
                versions = run([readelf, "--version-info", str(staged)], capture=True)
                needed = run([readelf, "--dynamic", str(staged)], capture=True)
                glibc.extend(readelf_versions(versions, "GLIBC", "needs"))
                glibcxx.extend(readelf_versions(versions, "GLIBCXX", "needs"))
                cxxabi.extend(readelf_versions(versions, "CXXABI", "needs"))
                if Path(member.name).name.startswith("libstdc++.so"):
                    provided_glibcxx.extend(readelf_versions(versions, "GLIBCXX", "definition"))
                    provided_cxxabi.extend(readelf_versions(versions, "CXXABI", "definition"))
                needed_libraries.update(re.findall(r"\(NEEDED\).*?\[(.*?)\]", needed))
                elf_problems = check_elf_contract(machine_match.group(1),
                    set(re.findall(r"\(NEEDED\).*?\[(.*?)\]", needed)), package_libraries)
                if elf_problems:
                    raise RuntimeError(f"{elf_problems[0]}:{member.name}")
                checked += 1
                staged.unlink()
    if checked == 0:
        raise RuntimeError("CONDA_CLOSURE_HAS_NO_AUDITED_ELF")
    glibc_max, glibcxx_max, cxxabi_max = version_max(glibc), version_max(glibcxx), version_max(cxxabi)
    if tuple(map(int, glibc_max.split("."))) > (2, 23):
        raise RuntimeError(f"CONDA_GLIBC_ABI_TOO_NEW:{glibc_max}")
    for label, required, provided in (("GLIBCXX", glibcxx, provided_glibcxx),
                                       ("CXXABI", cxxabi, provided_cxxabi)):
        if not abi_provider_compatible(required, provided):
            raise RuntimeError(f"CONDA_{label}_PROVIDER_INCOMPATIBLE:{version_max(required)}:{version_max(provided)}")
    return {"elf_files_checked": checked, "glibc_max": glibc_max,
            "glibcxx_max": glibcxx_max, "cxxabi_max": cxxabi_max,
            "provided_glibcxx_versions": sorted(set(provided_glibcxx)),
            "provided_cxxabi_versions": sorted(set(provided_cxxabi)),
            "needed_libraries": sorted(needed_libraries),
            "package_library_names": sorted(package_libraries),
            "system_runtime_allowlist": sorted(SYSTEM_RUNTIME_LIBS),
            "method": "readelf machine, version-needs/definitions, and DT_NEEDED resolution across locked package members and explicit system runtime allowlist"}


def wheel_elf_members(wheel: Path) -> list[str]:
    with zipfile.ZipFile(wheel) as archive:
        return [name for name in archive.namelist() if not name.endswith("/")
                and _zip_member_is_elf(archive, name)]


def _zip_member_is_elf(archive: zipfile.ZipFile, name: str) -> bool:
    with archive.open(name) as member:
        return member.read(4) == b"\x7fELF"


def audit_native_wheel_elf(wheel: Path, work: Path, available_libraries: set[str],
                           conda_abi: dict) -> dict:
    readelf = shutil.which("readelf")
    if not readelf:
        raise RuntimeError("READELF_MISSING_CANNOT_PROVE_WHEEL_ABI")
    glibc, glibcxx, cxxabi, needed_libraries = [], [], [], set()
    elf_members = wheel_elf_members(wheel)
    for index, name in enumerate(elf_members):
        staged = work / f"wheel-elf-{sha256(wheel)[:12]}-{index}"
        try:
            with zipfile.ZipFile(wheel) as archive, archive.open(name) as source, staged.open("wb") as out:
                shutil.copyfileobj(source, out)
            header = run([readelf, "--file-header", str(staged)], capture=True)
            machine = re.search(r"^\s*Machine:\s*(.+)$", header, re.MULTILINE)
            if not machine:
                raise RuntimeError(f"WHEEL_ELF_MACHINE_UNREADABLE:{wheel.name}:{name}")
            versions = run([readelf, "--version-info", str(staged)], capture=True)
            dynamic = run([readelf, "--dynamic", str(staged)], capture=True)
            needed = set(re.findall(r"\(NEEDED\).*?\[(.*?)\]", dynamic))
            problems = check_elf_contract(machine.group(1), needed, available_libraries)
            if problems:
                raise RuntimeError(f"WHEEL_ELF_CONTRACT:{wheel.name}:{name}:{problems[0]}")
            glibc.extend(readelf_versions(versions, "GLIBC", "needs"))
            glibcxx.extend(readelf_versions(versions, "GLIBCXX", "needs"))
            cxxabi.extend(readelf_versions(versions, "CXXABI", "needs"))
            needed_libraries.update(needed)
        finally:
            staged.unlink(missing_ok=True)
    glibc_max, glibcxx_max, cxxabi_max = map(version_max, (glibc, glibcxx, cxxabi))
    if tuple(map(int, glibc_max.split("."))) > (2, 23):
        raise RuntimeError(f"WHEEL_GLIBC_ABI_TOO_NEW:{wheel.name}:{glibc_max}")
    for label, required, provider_key in (
        ("GLIBCXX", glibcxx, "provided_glibcxx_versions"),
        ("CXXABI", cxxabi, "provided_cxxabi_versions"),
    ):
        provided = conda_abi.get(provider_key, [])
        if not abi_provider_compatible(required, provided):
            raise RuntimeError(f"WHEEL_{label}_PROVIDER_INCOMPATIBLE:{wheel.name}:"
                               f"{version_max(required)}:{version_max(provided)}")
    return {"elf_files_checked": len(elf_members), "glibc_max": glibc_max,
            "glibcxx_max": glibcxx_max, "cxxabi_max": cxxabi_max,
            "needed_libraries": sorted(needed_libraries),
            "provider_glibcxx_max": version_max(conda_abi.get("provided_glibcxx_versions", [])),
            "provider_cxxabi_max": version_max(conda_abi.get("provided_cxxabi_versions", []))}


def audit_rgt_wheel(wheel: Path, builder: str, work: Path, sdist_digest: str,
                    conda_abi: dict, available_libraries: set[str]) -> dict:
    elf_members = wheel_elf_members(wheel)
    if elf_members:
        elf_audit = audit_native_wheel_elf(wheel, work, available_libraries, conda_abi)
        if os.environ.get("PMA_HINT_BUILDER_MODE", "docker-image") == "docker-image" and not shutil.which("auditwheel"):
            raise RuntimeError("AUDITWHEEL_MISSING_FOR_NATIVE_RGT_WHEEL")
        output = run(auditwheel_command("show", str(wheel)), capture=True)
        (work / "rgt-auditwheel-show.txt").write_text(output, encoding="utf-8")
        glibc = re.findall(r"GLIBC_(\d+(?:\.\d+)+)", output)
        if not glibc:
            raise RuntimeError("AUDITWHEEL_GLIBC_EVIDENCE_UNPARSEABLE")
        policy_match = re.search(r"manylinux[^\s,;]*", output)
        if not policy_match:
            raise RuntimeError("AUDITWHEEL_POLICY_EVIDENCE_MISSING")
        glibc_max = version_max(glibc)
        if tuple(map(int, glibc_max.split("."))) > (2, 23):
            raise RuntimeError(f"RGT_WHEEL_GLIBC_ABI_TOO_NEW:{glibc_max}")
        return {"builder": builder, "python_abi": "cp311", "glibc_symbol_max": glibc_max,
                "auditwheel_policy": policy_match.group(0), "native_dependencies": elf_members,
                "auditwheel_output": output, "native_elf_audit": elf_audit,
                "rgt_sdist_sha256": sdist_digest,
                "rgt_wheel": wheel.name, "rgt_wheel_sha256": sha256(wheel)}
    return {"builder": builder, "python_abi": "cp311", "glibc_symbol_max": "2.0",
            "auditwheel_policy": "pure-python-no-ELF", "native_dependencies": [],
            "rgt_sdist_sha256": sdist_digest, "rgt_wheel": wheel.name,
            "rgt_wheel_sha256": sha256(wheel)}


def audit_pip_wheels(wheels: list[Path], work: Path, conda_abi: dict) -> dict:
    auditwheel_available = (bool(shutil.which("auditwheel")) if
                            os.environ.get("PMA_HINT_BUILDER_MODE", "docker-image") == "docker-image" else True)
    audited, glibc, glibcxx, cxxabi = [], [], [], []
    members_by_wheel = {wheel: wheel_elf_members(wheel) for wheel in wheels}
    wheel_library_names = {Path(name).name for members in members_by_wheel.values() for name in members}
    available_libraries = set(conda_abi.get("package_library_names", [])) | wheel_library_names
    for wheel in wheels:
        elf_members = members_by_wheel[wheel]
        if not elf_members:
            audited.append({"wheel": wheel.name, "sha256": sha256(wheel), "type": "pure-python-no-ELF"})
            continue
        if not auditwheel_available:
            raise RuntimeError(f"AUDITWHEEL_MISSING:{wheel.name}")
        elf_audit = audit_native_wheel_elf(wheel, work, available_libraries, conda_abi)
        output = run(auditwheel_command("show", str(wheel)), capture=True)
        matches = re.findall(r"GLIBC_(\d+(?:\.\d+)+)", output)
        if not matches:
            raise RuntimeError(f"WHEEL_GLIBC_EVIDENCE_UNPARSEABLE:{wheel.name}")
        policy = re.search(r"manylinux[^\s,;]*", output)
        if not policy:
            raise RuntimeError(f"WHEEL_MANYLINUX_POLICY_MISSING:{wheel.name}")
        wheel_glibc = version_max(matches)
        if tuple(map(int, wheel_glibc.split("."))) > (2, 23):
            raise RuntimeError(f"WHEEL_GLIBC_ABI_TOO_NEW:{wheel.name}:{wheel_glibc}")
        glibc.extend(matches)
        glibcxx.extend(re.findall(r"GLIBCXX_(\d+(?:\.\d+)+)", output))
        cxxabi.extend(re.findall(r"CXXABI_(\d+(?:\.\d+)+)", output))
        audited.append({"wheel": wheel.name, "sha256": sha256(wheel), "type": "native",
                        "glibc_max": wheel_glibc, "manylinux_policy": policy.group(0),
                        "elf_members": elf_members, "native_elf_audit": elf_audit,
                        "auditwheel_output": output})
    return {"wheels": audited, "glibc_max": version_max(glibc),
            "glibcxx_max": version_max(glibcxx), "cxxabi_max": version_max(cxxabi),
            "available_library_names": sorted(available_libraries)}


def fetch_and_build_rgt(bundle: Path, work: Path, python: Path) -> Path:
    source_dir = work / "sources"
    source_dir.mkdir()
    source_log = run([str(python), "-m", "pip", "download", "-v", "--no-deps", "--no-binary=:all:",
                      "--dest", str(source_dir), "RGT==1.0.2"], capture=True)
    (work / "rgt-sdist-download.log").write_text(sanitize_text(source_log), encoding="utf-8")
    sources = list(source_dir.iterdir())
    if len(sources) != 1 or sha256(sources[0]) != RGT_SHA256:
        raise RuntimeError("RGT_SDIST_SOURCE_OR_HASH_MISMATCH")
    wheel_dir = bundle / "wheels"
    wheel_dir.mkdir(parents=True, exist_ok=True)
    wheel_log = run([str(python), "-m", "pip", "wheel", "-v", "--no-deps", "--no-build-isolation",
                     "--wheel-dir", str(wheel_dir), str(sources[0])], capture=True)
    (work / "rgt-wheel-build.log").write_text(sanitize_text(wheel_log), encoding="utf-8")
    wheels = [p for p in wheel_dir.glob("*.whl") if str(parse_wheel_filename(p.name)[0]) == "rgt"]
    if len(wheels) != 1:
        raise RuntimeError("RGT_WHEEL_BUILD_NOT_UNIQUE")
    return wheels[0]


def resolve_pip_closure(rgt_wheel: Path, bundle: Path, work: Path, conda_records: list[dict],
                        python: Path) -> list[Path]:
    downloaded = work / "pip-download"
    downloaded.mkdir()
    constraints = work / "pip-constraints.txt"
    constraints.write_text("numpy==1.26.4\nsetuptools==80.9.0\n", encoding="utf-8")
    pip_log = run([str(python), "-m", "pip", "download", "-v", "--only-binary=:all:",
         "--platform", "manylinux2014_x86_64", "--python-version", "3.11",
         "--implementation", "cp", "--abi", "cp311", "--abi", "abi3", "--abi", "none",
         "--constraint", str(constraints), "--dest", str(downloaded), str(rgt_wheel)], capture=True)
    (work / "pip-wheel-download.log").write_text(sanitize_text(pip_log), encoding="utf-8")
    conda_names = {re.sub(r"[-_.]+", "-", row["name"]).lower() for row in conda_records}
    staged = []
    for wheel in sorted(downloaded.glob("*.whl")):
        name, _version, _build, _tags = parse_wheel_filename(wheel.name)
        if str(name) in conda_names:
            continue
        destination = bundle / "wheels" / wheel.name
        if destination.exists() and sha256(destination) != sha256(wheel):
            raise RuntimeError(f"PIP_WHEEL_DUPLICATE_HASH_MISMATCH:{wheel.name}")
        if not destination.exists():
            shutil.copy2(wheel, destination)
        staged.append(destination)
    rgt_dest = bundle / "wheels" / rgt_wheel.name
    if rgt_dest not in staged:
        staged.append(rgt_dest)
    if len(staged) != len({str(parse_wheel_filename(p.name)[0]) for p in staged}):
        raise RuntimeError("PIP_WHEEL_DUPLICATE_DISTRIBUTION")
    return staged


def render_pip_lock(wheels: list[Path]) -> str:
    rows = []
    for wheel in wheels:
        name, version, _build, _tags = parse_wheel_filename(wheel.name)
        rows.append(f"{canonicalize_name(name)}=={version} --hash=sha256:{sha256(wheel)}\n")
    return "".join(sorted(rows))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path, help="external output directory; must be outside the Git checkout")
    parser.add_argument("--evidence-dir", required=True, type=Path,
                        help="persistent external build evidence directory; must be empty")
    args = parser.parse_args()
    bundle = args.bundle.resolve()
    evidence = args.evidence_dir.resolve()
    repo = Path(__file__).resolve().parents[2]
    for label, path in (("BUNDLE", bundle), ("EVIDENCE", evidence)):
        if path == repo or repo in path.parents:
            raise RuntimeError(f"{label}_OUTPUT_MUST_BE_OUTSIDE_REPOSITORY")
    if bundle == evidence or bundle in evidence.parents or evidence in bundle.parents:
        raise RuntimeError("BUNDLE_AND_EVIDENCE_DIRS_MUST_BE_SEPARATE")
    if (bundle.exists() and any(bundle.iterdir())) or (evidence.exists() and any(evidence.iterdir())):
        raise RuntimeError("BUNDLE_AND_EVIDENCE_DIRS_MUST_BE_EMPTY")
    bundle.mkdir(parents=True, exist_ok=True)
    evidence.mkdir(parents=True, exist_ok=True)
    global RUN_LOG
    RUN_LOG = evidence / "commands.log"
    RUN_LOG.write_text("PMA HINT bundle builder command log\n", encoding="utf-8")
    conda, builder_glibc = require_builder()
    builder_mode = os.environ.get("PMA_HINT_BUILDER_MODE", "docker-image")
    builder_id = (os.environ["PMA_HINT_BUILDER_IMAGE"] if builder_mode == "docker-image" else
                  f"argos-native:{platform.node()}")
    package_cache = (Path(os.environ["CONDA_PKGS_DIRS"]).resolve()
                     if builder_mode == "argos-native" else None)
    work = evidence / "work"
    work.mkdir()
    try:
        links, solve_command, solve_json = load_solver_plan(conda, work, package_cache=package_cache)
        parsed_solve = json.loads(solve_json)
        (evidence / "conda-solve.json").write_text(
            json.dumps(sanitize_evidence(parsed_solve), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (evidence / "conda-upstream-link-records.json").write_text(
            json.dumps(sanitize_evidence(links), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        conda_records = copy_conda_closure(links, bundle)
        (evidence / "conda-artifact-provenance.json").write_text(
            json.dumps(sanitize_evidence(conda_records), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if builder_mode == "argos-native":
            write_local_repodata(conda_records, bundle / "conda")
        else:
            run([conda, "index", str(bundle / "conda")])
        abi = audit_conda_elf(conda_records, bundle, work)
        offline_prefix = work / "offline-solve-prefix"
        offline_options = ["--offline", "--no-default-packages", "--override-channels", "-c",
                           (bundle / "conda").as_uri()]
        offline = conda_dry_run(conda, offline_prefix, offline_options, TARGET_SPECS,
                                package_cache=package_cache)
        (evidence / "conda-offline-solve.json").write_text(sanitize_text(offline), encoding="utf-8")
        try:
            offline_links = json.loads(offline)["actions"]["LINK"]
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise RuntimeError(f"CONDA_OFFLINE_SOLVER_JSON_INVALID:{exc}") from exc
        def identity(row: dict) -> tuple:
            url = row.get("url", "")
            subdir = row.get("subdir") or row.get("platform")
            if subdir not in ("linux-64", "noarch"):
                subdir = "noarch" if "/noarch/" in url else "linux-64" if "/linux-64/" in url else "unknown"
            filename = row.get("fn") or url.rsplit("/", 1)[-1]
            build = row.get("build") or row.get("build_string")
            return row["name"], row["version"], build, subdir, filename
        identities = lambda rows: sorted(identity(row) for row in rows)
        if identities(links) != identities(offline_links):
            raise RuntimeError("CONDA_OFFLINE_SOLVER_CLOSURE_MISMATCH")
        build_python = Path(sys.executable).resolve()
        build_python_version = run([str(build_python), "--version"], capture=True).strip()
        if not re.fullmatch(r"Python 3\.11\.\d+", build_python_version):
            raise RuntimeError(f"PREPROVISIONED_BUILDER_PYTHON_MISMATCH:{build_python_version}")
        rgt_wheel = fetch_and_build_rgt(bundle, work, build_python)
        wheels = resolve_pip_closure(rgt_wheel, bundle, work, conda_records, build_python)
        wheel_abi = audit_pip_wheels(wheels, work, abi)
        conda_lock = bundle / "conda-explicit-linux-64.lock"
        conda_lock.write_text("".join("\t".join(row[k] for k in ("subdir", "name", "version", "build", "filename", "sha256")) + "\n" for row in conda_records), encoding="utf-8")
        pip_lock = bundle / "pip-requirements.lock"
        pip_lock.write_text(render_pip_lock(wheels), encoding="utf-8")
        report_path = bundle / "reports" / "rgt-wheel-audit.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        rgt_report = audit_rgt_wheel(rgt_wheel, builder_id, work,
                                     RGT_SHA256, abi, set(wheel_abi["available_library_names"]))
        rgt_report["conda_abi_audit"] = abi
        report_path.write_text(json.dumps(rgt_report, indent=2) + "\n", encoding="utf-8")
        wheel_report_path = bundle / "reports" / "pip-wheel-abi-audit.json"
        wheel_report_path.write_text(json.dumps(wheel_abi, indent=2) + "\n", encoding="utf-8")
        for log_name in ("rgt-sdist-download.log", "rgt-wheel-build.log", "pip-wheel-download.log"):
            shutil.copy2(work / log_name, evidence / log_name)
        versions_report = {
            "builder_mode": builder_mode, "builder_identity": builder_id,
            "architecture": platform.machine(),
            "python": platform.python_version(), "glibc": platform.libc_ver(),
            "conda": run([conda, "--version"], capture=True).strip(),
            "pip": run([str(build_python), "-m", "pip", "--version"], capture=True).strip(),
            "conda_index_packages": (run([conda, "list", "conda-index"], capture=True).strip()
                                     if builder_mode == "docker-image" else None),
            "repodata_generation": ("conda-index" if builder_mode == "docker-image" else
                                    "pma-local-standard-records-v1"),
            "auditwheel": run(auditwheel_command("--version"), capture=True).strip(),
            "readelf": run(["readelf", "--version"], capture=True).splitlines()[0],
            "gcc": run(["gcc", "--version"], capture=True).splitlines()[0],
            "builder_glibc": builder_glibc,
            "build_prefix_python": build_python_version,
            "conda_solve_command": sanitize_evidence(solve_command),
            "conda_artifacts": sanitize_evidence(conda_records),
            "conda_abi_audit": abi, "pip_wheel_abi_audit": wheel_abi}
        if builder_mode == "docker-image":
            versions_report["builder_image"] = builder_id
            shutil.copy2("/opt/conda/build-toolchain-explicit.txt", evidence / "build-toolchain-conda-explicit.txt")
            shutil.copy2("/opt/conda/build-toolchain-pip.json", evidence / "build-toolchain-pip.json")
        else:
            host_report = Path(os.environ["PMA_HINT_HOST_TOOLCHAIN_REPORT"])
            versions_report["host_toolchain_report"] = host_report.name
            versions_report["host_toolchain_report_sha256"] = sha256(host_report)
            shutil.copy2(host_report, evidence / host_report.name)
        (evidence / "builder-versions.json").write_text(
            json.dumps(versions_report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        inventory = []
        for path in sorted(bundle.rglob("*")):
            if path.is_file() and path.name != "artifacts.sha256":
                inventory.append(f"{sha256(path)}  {path.relative_to(bundle).as_posix()}\n")
        (bundle / "artifacts.sha256").write_text("".join(inventory), encoding="utf-8")
        manifest = {"schema_version": 1, "target_platform": "linux-64", "python_abi": "cp311",
                    "glibc_max": version_max([abi["glibc_max"], wheel_abi["glibc_max"]]),
                    "builder": builder_id,
                    "builder_mode": builder_mode,
                    "host_toolchain_report_sha256": (sha256(Path(os.environ["PMA_HINT_HOST_TOOLCHAIN_REPORT"]))
                                                      if builder_mode == "argos-native" else None),
                    "conda_version": run([conda, "--version"], capture=True).strip(),
            "conda_toolchain_explicit_sha256": (sha256(evidence / "build-toolchain-conda-explicit.txt")
                                                 if builder_mode == "docker-image" else None),
            "pip_toolchain_inventory_sha256": (sha256(evidence / "build-toolchain-pip.json")
                                                if builder_mode == "docker-image" else None),
                    "pip_version": run([sys.executable, "-m", "pip", "--version"], capture=True).strip(),
                    "rgt_sdist_sha256": RGT_SHA256, "rgt_wheel": rgt_wheel.name,
                    "rgt_wheel_sha256": sha256(rgt_wheel), "rgt_build_report": "reports/rgt-wheel-audit.json",
                    "rgt_build_report_sha256": sha256(report_path), "conda_lock_sha256": sha256(conda_lock),
                    "pip_lock_sha256": sha256(pip_lock), "artifacts_sha256": sha256(bundle / "artifacts.sha256"),
                    "conda_solve_command": sanitize_evidence(solve_command)}
        (bundle / "bundle-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        validator = Path(__file__).with_name("validate_hint_bundle.py")
        run([sys.executable, str(validator), str(bundle)])
        shutil.copy2(bundle / "bundle-manifest.json", evidence / "bundle-manifest.json")
        archive_path = evidence / "pma_hint_bundle.tar.gz"
        with tarfile.open(archive_path, "w:gz") as archive:
            archive.add(bundle, arcname="pma_hint_bundle")
        (evidence / "bundle-archive.sha256").write_text(
            sha256(archive_path) + "  pma_hint_bundle.tar.gz\n", encoding="utf-8")
        return 0
    except Exception as exc:
        (evidence / "build-failure.txt").write_text(
            sanitize_text(f"{type(exc).__name__}: {exc}\n"), encoding="utf-8")
        raise


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, subprocess.CalledProcessError, ValueError) as exc:
        print(sanitize_text(f"HINT_BUNDLE_BUILD_FAILED:{exc}"), file=sys.stderr)
        raise SystemExit(1)
