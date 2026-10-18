#!/usr/bin/env python3
"""Build a CPython 3.11/Linux HINT bundle from a pinned Conda solve.

This program is intentionally limited to artifact construction. It never
creates an Argos environment. Bundle and evidence directories must both be
outside the repository. Run only after review in the configured Docker or
Argos-native Linux environment.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
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
EXTRACTOR_PROVENANCE: dict = {}
EXTRACTOR_PYTHON: Path | None = None
MAX_EXTRACTED_PACKAGE_BYTES = 8 * 1024 * 1024 * 1024
MAX_EXTRACTED_PACKAGE_FILES = 250_000
CONDA_EXTRACTOR_VERSIONS = {
    "conda-package-handling": "2.4.0",
    "conda-package-streaming": "0.11.0",
    "zstandard": "0.23.0",
}
CONDA_ISOLATED_ENV_VARS = (
    "PYTHONPATH", "PMA_HINT_EXTERNAL_TOOLCHAIN_PYTHON_ROOT", "PMA_HINT_ALLOWED_WORKSPACE",
)


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


def run_conda(argv: list[str], *, capture: bool = False,
              env: dict[str, str] | None = None) -> str:
    """Keep the builder's locked Python startup path out of the Conda CLI."""
    child_env = dict(os.environ if env is None else env)
    for key in CONDA_ISOLATED_ENV_VARS:
        child_env.pop(key, None)
    return run(argv, capture=capture, env=child_env)


def verify_argos_toolchain_in_process(python_root: Path) -> None:
    """Check the builder's already-loaded third-party modules in this process."""
    probe_path = Path(__file__).with_name("probe_hint_argos_toolchain.py")
    spec = importlib.util.spec_from_file_location("pma_argos_toolchain_probe", probe_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("ARGOS_TOOLCHAIN_PROBE_UNLOADABLE")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.probe(python_root)


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
    output = run_conda(command, capture=True, env=env)
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
        python_root = toolchain / "python"
        if not python_root.is_dir():
            raise RuntimeError("ARGOS_EXTERNAL_TOOLCHAIN_PYTHON_ROOT_MISSING")
        allowed_workspace = Path(os.environ.get("PMA_HINT_ALLOWED_WORKSPACE", ""))
        if (not allowed_workspace.is_absolute() or
                allowed_workspace.resolve() != python_root.resolve().parent.parent):
            raise RuntimeError("ARGOS_EXTERNAL_TOOLCHAIN_WORKSPACE_MISMATCH")
        configured_root = Path(os.environ.get("PMA_HINT_EXTERNAL_TOOLCHAIN_PYTHON_ROOT", ""))
        if not configured_root.is_absolute() or configured_root.resolve() != python_root.resolve():
            raise RuntimeError("ARGOS_EXTERNAL_TOOLCHAIN_STARTUP_ROOT_MISMATCH")
        pythonpath = os.environ.get("PYTHONPATH", "").split(os.pathsep)
        script_root = str(Path(__file__).resolve().parent)
        if len(pythonpath) != 2 or pythonpath[0] != script_root or pythonpath[1] != str(python_root.resolve()):
            raise RuntimeError("ARGOS_EXTERNAL_TOOLCHAIN_STARTUP_PATH_MISMATCH")
        package_cache = Path(os.environ.get("CONDA_PKGS_DIRS", ""))
        if not package_cache.is_absolute():
            raise RuntimeError("ARGOS_CONDA_PACKAGE_CACHE_MUST_BE_EXPLICIT_EXTERNAL_PATH")
        verify_argos_toolchain_in_process(python_root)
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


def _solver_subdir(item: dict) -> str | None:
    subdir = item.get("subdir") or item.get("platform")
    return subdir if subdir in ("linux-64", "noarch") else None


def resolve_solver_artifacts(links: list[dict], repodata_by_subdir: dict[str, dict], *,
                             fetches: list[dict] | None = None,
                             expected_channel: str | None = None) -> list[dict]:
    """Bind distribution-level LINK rows to exactly one provenance-backed artifact."""
    fetches = fetches or []
    if not isinstance(links, list) or not isinstance(fetches, list):
        raise RuntimeError("CONDA_SOLVER_ACTIONS_INVALID")
    resolved = []
    consumed_fetches = set()
    for item in links:
        subdir = _solver_subdir(item)
        name, version = item.get("name"), item.get("version")
        build = item.get("build") or item.get("build_string")
        if subdir is None or not all(isinstance(value, str) and value for value in (name, version, build)):
            raise RuntimeError("CONDA_SOLVER_LINK_IDENTITY_INVALID")
        expected_dist = f"{name}-{version}-{build}"
        if item.get("dist_name") not in (None, expected_dist):
            raise RuntimeError(f"CONDA_SOLVER_DIST_IDENTITY_MISMATCH:{name}")
        base_url = item.get("base_url")
        if expected_channel is not None:
            if not isinstance(base_url, str) or sanitize_url(base_url).rstrip("/") != expected_channel.rstrip("/"):
                raise RuntimeError(f"CONDA_SOLVER_CHANNEL_MISMATCH:{name}")
        snapshot = repodata_by_subdir.get(subdir)
        if not isinstance(snapshot, dict):
            raise RuntimeError(f"CONDA_SOLVER_REPODATA_SUBDIR_MISSING:{subdir}")
        candidates = []
        for section, suffix in (("packages", ".tar.bz2"), ("packages.conda", ".conda")):
            records = snapshot.get(section)
            if not isinstance(records, dict):
                raise RuntimeError(f"ARGOS_UPSTREAM_REPODATA_SECTION_MISSING:{subdir}:{section}")
            for filename, record in records.items():
                if (not isinstance(filename, str) or not filename.endswith(suffix) or
                        not isinstance(record, dict)):
                    continue
                if (record.get("name"), record.get("version"), record.get("build")) == (name, version, build):
                    candidates.append((section, filename, record))
        matching_fetches = []
        for fetch_index, fetch in enumerate(fetches):
            if not isinstance(fetch, dict):
                raise RuntimeError("CONDA_SOLVER_FETCH_ROW_INVALID")
            fetch_subdir = _solver_subdir(fetch)
            fetch_build = fetch.get("build") or fetch.get("build_string")
            fetch_identity = (fetch.get("name"), fetch.get("version"), fetch_build)
            link_identity = (name, version, build)
            if fetch_identity == link_identity and fetch_subdir != subdir:
                raise RuntimeError(f"CONDA_SOLVER_FETCH_SUBDIR_MISMATCH:{name}")
            fetch_base = fetch.get("base_url")
            if (fetch_identity == link_identity and expected_channel is not None and fetch_base and
                    sanitize_url(fetch_base).rstrip("/") != expected_channel.rstrip("/")):
                raise RuntimeError(f"CONDA_SOLVER_FETCH_CHANNEL_MISMATCH:{name}")
            if (fetch_subdir, fetch.get("name"), fetch.get("version"), fetch_build) == (subdir, name, version, build):
                matching_fetches.append((fetch_index, fetch))
        if len(matching_fetches) > 1:
            raise RuntimeError(f"CONDA_SOLVER_FETCH_DUPLICATE:{name}")
        if matching_fetches:
            fetch_index, fetch = matching_fetches[0]
            if fetch_index in consumed_fetches:
                raise RuntimeError(f"CONDA_SOLVER_FETCH_REUSED:{name}")
            consumed_fetches.add(fetch_index)
            fetch_filename = fetch.get("fn")
            fetch_url = fetch.get("url")
            if fetch_url:
                fetch_filename_from_url = urlsplit(fetch_url).path.rsplit("/", 1)[-1]
                if fetch_filename and fetch_filename != fetch_filename_from_url:
                    raise RuntimeError(f"CONDA_SOLVER_FETCH_FILENAME_CONFLICT:{name}")
                fetch_filename = fetch_filename or fetch_filename_from_url
            fetch_sha = fetch.get("sha256")
            fetch_md5 = fetch.get("md5")
            if len(candidates) > 1 and not (fetch_filename and (fetch_sha or fetch_md5)):
                raise RuntimeError(f"CONDA_SOLVER_FETCH_DISAMBIGUATION_INCOMPLETE:{name}")
            if not fetch_filename or not (fetch_sha or fetch_md5):
                raise RuntimeError(f"CONDA_SOLVER_FETCH_ARTIFACT_IDENTITY_INCOMPLETE:{name}")
            if fetch_filename or fetch_sha or fetch_md5:
                filtered = []
                for candidate in candidates:
                    _section, filename, record = candidate
                    if fetch_filename and filename != fetch_filename:
                        continue
                    if fetch_sha and record.get("sha256", "").lower() != str(fetch_sha).lower():
                        continue
                    if fetch_md5 and record.get("md5", "").lower() != str(fetch_md5).lower():
                        continue
                    filtered.append(candidate)
                if not filtered:
                    raise RuntimeError(f"CONDA_SOLVER_FETCH_REPODATA_CONFLICT:{name}")
                candidates = filtered
        if len(candidates) != 1:
            raise RuntimeError(f"CONDA_SOLVER_ARTIFACT_NOT_UNIQUE:{subdir}:{name}:{len(candidates)}")
        section, filename, source = candidates[0]
        artifact_sha = source.get("sha256")
        size = source.get("size")
        if not re.fullmatch(r"[0-9a-fA-F]{64}", str(artifact_sha or "")):
            raise RuntimeError(f"CONDA_REPODATA_SHA256_INVALID:{filename}")
        if not isinstance(size, int) or size <= 0:
            raise RuntimeError(f"CONDA_REPODATA_SIZE_INVALID:{filename}")
        if source.get("md5") and not re.fullmatch(r"[0-9a-fA-F]{32}", str(source["md5"])):
            raise RuntimeError(f"CONDA_REPODATA_MD5_INVALID:{filename}")
        for key, value in (("build_number", item.get("build_number")),):
            if value is not None and source.get(key) != value:
                raise RuntimeError(f"CONDA_SOLVER_REPODATA_IDENTITY_MISMATCH:{filename}:{key}")
        for key in ("fn", "filename"):
            if item.get(key) and item[key] != filename:
                raise RuntimeError(f"CONDA_SOLVER_REPODATA_IDENTITY_MISMATCH:{filename}:{key}")
        for key in ("depends", "constrains"):
            if key in item:
                link_value, source_value = item[key], source.get(key, [])
                if not isinstance(link_value, list) or not isinstance(source_value, list):
                    raise RuntimeError(f"CONDA_SOLVER_REPODATA_METADATA_INVALID:{filename}:{key}")
                if sorted(link_value) != sorted(source_value):
                    raise RuntimeError(f"CONDA_SOLVER_REPODATA_METADATA_MISMATCH:{filename}:{key}")
        artifact_url = f"{expected_channel.rstrip('/')}/{subdir}/{filename}" if expected_channel else ""
        if matching_fetches and matching_fetches[0][1].get("url") and artifact_url:
            if sanitize_url(matching_fetches[0][1]["url"]) != artifact_url:
                raise RuntimeError(f"CONDA_SOLVER_FETCH_URL_MISMATCH:{filename}")
        if item.get("url") and sanitize_url(item["url"]) != artifact_url:
            raise RuntimeError(f"CONDA_SOLVER_ARTIFACT_URL_MISMATCH:{filename}")
        normalized = dict(item)
        normalized["pma_artifact"] = {
            "channel_base_url": expected_channel or base_url,
            "subdir": subdir, "name": name, "version": version, "build": build,
            "build_number": source.get("build_number"), "repodata_section": section,
            "filename": filename, "artifact_url": sanitize_url(artifact_url) if artifact_url else "",
            "sha256": artifact_sha.lower(), "md5": source.get("md5"), "size": size,
            "depends": source.get("depends"), "constrains": source.get("constrains"),
        }
        normalized["pma_solver_metadata_fields"] = {
            key: key in item for key in ("depends", "constrains", "sha256", "fn", "url")
        }
        normalized["pma_upstream_repodata_record"] = source
        resolved.append(normalized)
    if consumed_fetches != set(range(len(fetches))):
        extra = len(set(range(len(fetches))) - consumed_fetches)
        raise RuntimeError(f"CONDA_SOLVER_FETCH_NOT_IN_LINK:{extra}")
    identities = [(row["pma_artifact"]["subdir"], row["name"], row["version"],
                   row["pma_artifact"]["build"], row["pma_artifact"]["filename"],
                   row["pma_artifact"]["sha256"]) for row in resolved]
    if len(identities) != len(set(identities)):
        raise RuntimeError("CONDA_SOLVER_ARTIFACT_DUPLICATE")
    return resolved


def verify_solver_repodata_cache(package_cache: Path, channel: str, subdir: str,
                                snapshot: dict) -> dict:
    """Prove Conda solved from the same cached repodata bytes saved as evidence."""
    cache = package_cache / "cache"
    expected_url = f"{channel.rstrip('/')}/{subdir}"
    matches = []
    for info_path in cache.glob("*.info.json"):
        try:
            info = json.loads(info_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if sanitize_url(str(info.get("url", ""))).rstrip("/") == expected_url:
            matches.append((info_path, info))
    if len(matches) != 1:
        raise RuntimeError(f"CONDA_SOLVER_REPODATA_CACHE_NOT_UNIQUE:{subdir}:{len(matches)}")
    info_path, info = matches[0]
    json_path = info_path.with_name(info_path.name.removesuffix(".info.json") + ".json")
    if not json_path.is_file():
        raise RuntimeError(f"CONDA_SOLVER_REPODATA_CACHE_MISSING:{subdir}")
    if json_path.stat().st_size != snapshot["size"] or info.get("size") != snapshot["size"]:
        raise RuntimeError(f"CONDA_SOLVER_REPODATA_CACHE_SIZE_MISMATCH:{subdir}")
    digest = sha256(json_path)
    if digest != snapshot["sha256"]:
        raise RuntimeError(f"CONDA_SOLVER_REPODATA_CACHE_HASH_MISMATCH:{subdir}")
    if info.get("url") != expected_url:
        raise RuntimeError(f"CONDA_SOLVER_REPODATA_CACHE_URL_MISMATCH:{subdir}")
    return {"url": expected_url, "cache_file": json_path.name,
            "sha256": digest, "size": json_path.stat().st_size}


def conda_extractor(conda: str, work: Path) -> tuple[Path, dict]:
    """Probe the audited Conda base's existing package extractor; never install it."""
    base_prefix = Path(conda).resolve().parent.parent
    python = (base_prefix / "bin" / "python").resolve()
    if not python.is_file() or not python.resolve().is_relative_to(base_prefix.resolve()):
        raise RuntimeError("CONDA_BASE_PYTHON_INVALID")
    probe = (
        "import importlib.metadata as m, json, pathlib, sys, "
        "conda_package_handling, conda_package_streaming, zstandard; "
        "print(json.dumps({'python':str(pathlib.Path(sys.executable).resolve()),"
        "'python_version':sys.version.split()[0],"
        "'cph_version':m.version('conda-package-handling'),"
        "'cph_module':str(pathlib.Path(conda_package_handling.__file__).resolve()),"
        "'streaming_version':m.version('conda-package-streaming'),"
        "'streaming_module':str(pathlib.Path(conda_package_streaming.__file__).resolve()),"
        "'zstandard_version':m.version('zstandard'),"
        "'zstandard_module':str(pathlib.Path(zstandard.__file__).resolve())}, sort_keys=True))"
    )
    env = os.environ.copy()
    for key in CONDA_ISOLATED_ENV_VARS:
        env.pop(key, None)
    output = run([str(python), "-I", "-c", probe], capture=True, env=env)
    try:
        details = json.loads(output)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"CONDA_EXTRACTOR_PROBE_INVALID:{exc}") from exc
    expected_versions = {
        "conda-package-handling": ("cph_version", "cph_module"),
        "conda-package-streaming": ("streaming_version", "streaming_module"),
        "zstandard": ("zstandard_version", "zstandard_module"),
    }
    for package, (version_key, _module_key) in expected_versions.items():
        if details.get(version_key) != CONDA_EXTRACTOR_VERSIONS[package]:
            raise RuntimeError(f"CONDA_EXTRACTOR_VERSION_NOT_APPROVED:{package}:{details.get(version_key)}")
    for key in ("cph_module", "streaming_module", "zstandard_module"):
        module_path = Path(details.get(key, "")).resolve()
        if not module_path.is_relative_to(base_prefix.resolve()):
            raise RuntimeError(f"CONDA_EXTRACTOR_MODULE_OUTSIDE_BASE:{key}")
    if Path(details.get("python", "")).resolve() != python:
        raise RuntimeError("CONDA_EXTRACTOR_PYTHON_MISMATCH")
    meta = base_prefix / "conda-meta"
    records = {}
    for package in ("conda-package-handling", "conda-package-streaming", "zstandard"):
        candidates = list(meta.glob(f"{package}-*.json"))
        if len(candidates) != 1:
            raise RuntimeError(f"CONDA_EXTRACTOR_PACKAGE_RECORD_NOT_UNIQUE:{package}")
        record_path = candidates[0]
        record = json.loads(record_path.read_text(encoding="utf-8"))
        version_key = {"conda-package-handling": "cph_version",
                       "conda-package-streaming": "streaming_version",
                       "zstandard": "zstandard_version"}[package]
        if record.get("version") != details[version_key]:
            raise RuntimeError(f"CONDA_EXTRACTOR_PACKAGE_VERSION_MISMATCH:{package}")
        if not re.fullmatch(r"[0-9a-fA-F]{64}", str(record.get("sha256") or "")):
            raise RuntimeError(f"CONDA_EXTRACTOR_PACKAGE_HASH_MISSING:{package}")
        paths_metadata = record.get("paths_data")
        paths_data = paths_metadata.get("paths", []) if isinstance(paths_metadata, dict) else []
        expected_file_hashes = {
            row.get("_path"): row.get("sha256_in_prefix")
            for row in paths_data if isinstance(row, dict) and row.get("_path")
        }
        module_path = Path(details[version_key.replace("_version", "_module")]).resolve()
        module_files = [module_path]
        if module_path.name == "__init__.py":
            module_files = [path for path in module_path.parent.rglob("*")
                            if path.is_file() and path.suffix in {".py", ".so", ".pyd", ".dll"}]
        installed_files = []
        for module_file in sorted(set(module_files)):
            relative = module_file.resolve().relative_to(base_prefix.resolve()).as_posix()
            expected_digest = expected_file_hashes.get(relative)
            if not re.fullmatch(r"[0-9a-fA-F]{64}", str(expected_digest or "")):
                raise RuntimeError(f"CONDA_EXTRACTOR_INSTALLED_FILE_HASH_MISSING:{package}:{relative}")
            actual_digest = sha256(module_file)
            if actual_digest.lower() != expected_digest.lower():
                raise RuntimeError(f"CONDA_EXTRACTOR_INSTALLED_FILE_HASH_MISMATCH:{package}:{relative}")
            installed_files.append({"path": relative, "sha256": actual_digest})
        records[package] = {"record_file": record_path.name, "record_sha256": sha256(record_path),
                            "name": record.get("name"), "version": record.get("version"),
                            "build": record.get("build"), "channel": sanitize_url(record.get("channel", "")),
                            "url": sanitize_url(record.get("url", "")),
                            "sha256": record["sha256"], "installed_module_files": installed_files,
                            "integrity_basis": "conda-meta paths_data sha256_in_prefix"}
    evidence = {**details, "base_prefix": str(base_prefix), "packages": records,
                "extract_api": "conda_package_handling.api.extract", "python_isolated": True}
    global EXTRACTOR_PROVENANCE, EXTRACTOR_PYTHON
    EXTRACTOR_PROVENANCE = evidence
    EXTRACTOR_PYTHON = python
    return python, evidence


def validate_conda_archive(path: Path, artifact: dict) -> None:
    name = artifact["name"]
    version = artifact["version"]
    build = artifact["build"]
    expected = {"metadata.json", f"info-{name}-{version}-{build}.tar.zst",
                f"pkg-{name}-{version}-{build}.tar.zst"}
    try:
        with zipfile.ZipFile(path) as archive:
            members = archive.infolist()
            names = [member.filename for member in members]
            if len(names) != len(set(names)) or set(names) != expected:
                raise RuntimeError(f"CONDA_ZIP_MEMBERS_INVALID:{path.name}")
            if any(member.compress_type != zipfile.ZIP_STORED or member.flag_bits & 1 for member in members):
                raise RuntimeError(f"CONDA_ZIP_CONTAINER_ENCODING_INVALID:{path.name}")
            metadata = json.loads(archive.read("metadata.json"))
            if not isinstance(metadata, dict) or metadata.get("conda_pkg_format_version") != 2:
                raise RuntimeError(f"CONDA_ZIP_FORMAT_VERSION_UNSUPPORTED:{path.name}")
            if archive.testzip() is not None:
                raise RuntimeError(f"CONDA_ZIP_CRC_FAILED:{path.name}")
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError) as exc:
        raise RuntimeError(f"CONDA_ZIP_INVALID:{path.name}:{exc}") from exc


def extract_conda_archive(python: Path, archive: Path, destination: Path, work: Path) -> Path:
    if destination.exists() or not destination.resolve().is_relative_to(work.resolve()):
        raise RuntimeError("CONDA_EXTRACT_DESTINATION_INVALID")
    env = os.environ.copy()
    for key in CONDA_ISOLATED_ENV_VARS:
        env.pop(key, None)
    preflight = CONDA_ARCHIVE_PREFLIGHT
    run([str(python), "-I", "-c", preflight, str(archive),
         str(MAX_EXTRACTED_PACKAGE_BYTES), str(MAX_EXTRACTED_PACKAGE_FILES)],
        capture=True, env=env)
    code = "from conda_package_handling.api import extract; import sys; extract(sys.argv[1], dest_dir=sys.argv[2])"
    run([str(python), "-I", "-c", code, str(archive), str(destination)], capture=True, env=env)
    if not destination.is_dir():
        raise RuntimeError(f"CONDA_EXTRACT_OUTPUT_MISSING:{archive.name}")
    total_bytes = 0
    count = 0
    root = destination.resolve()
    for path in destination.rglob("*"):
        count += 1
        if count > MAX_EXTRACTED_PACKAGE_FILES:
            raise RuntimeError(f"CONDA_EXTRACT_FILE_COUNT_LIMIT:{archive.name}")
        if path.is_symlink():
            target = Path(os.readlink(path))
            if target.is_absolute() or not (path.parent / target).resolve().is_relative_to(root):
                raise RuntimeError(f"CONDA_EXTRACT_SYMLINK_ESCAPE:{archive.name}:{path.name}")
        elif path.is_file():
            if not path.resolve().is_relative_to(root):
                raise RuntimeError(f"CONDA_EXTRACT_PATH_ESCAPE:{archive.name}:{path.name}")
            total_bytes += path.stat().st_size
            if total_bytes > MAX_EXTRACTED_PACKAGE_BYTES:
                raise RuntimeError(f"CONDA_EXTRACT_SIZE_LIMIT:{archive.name}")
        elif not path.is_dir():
            raise RuntimeError(f"CONDA_EXTRACT_SPECIAL_FILE:{archive.name}:{path.name}")
    return destination


CONDA_ARCHIVE_PREFLIGHT = r'''import posixpath, sys
from conda_package_streaming.package_streaming import stream_conda_component
path = sys.argv[1]
seen = set()
kinds = {}
hardlinks = []
total = 0
count = 0
def safe_name(value):
    if not value or value.startswith("/") or "\\" in value:
        return None
    raw = value.rstrip("/")
    if not raw or any(part in ("", ".", "..") for part in raw.split("/")):
        return None
    normalized = posixpath.normpath(value)
    if normalized in (".", "..") or normalized.startswith("../"):
        return None
    if normalized != raw:
        return None
    return normalized

def safe_link_target(name, link, hardlink):
    if not link or link.startswith("/") or "\\" in link:
        return None
    target = posixpath.normpath(link if hardlink else posixpath.join(posixpath.dirname(name), link))
    if target in (".", "..") or target.startswith("../"):
        return None
    return target

for component in ("pkg", "info"):
    with open(path, "rb") as source:
        for tar, member in stream_conda_component(path, source, component=component):
            name = safe_name(member.name)
            if name is None or name in seen:
                raise SystemExit("CONDA_ARCHIVE_MEMBER_PATH_OR_DUPLICATE_INVALID")
            parts = name.split("/")
            for i in range(1, len(parts)):
                parent = "/".join(parts[:i])
                if kinds.get(parent) not in (None, "dir"):
                    raise SystemExit("CONDA_ARCHIVE_MEMBER_WRITES_THROUGH_NON_DIRECTORY")
            seen.add(name)
            count += 1
            if count > int(sys.argv[3]):
                raise SystemExit("CONDA_ARCHIVE_FILE_COUNT_LIMIT")
            if not member.isdir() and any(existing.startswith(name + "/") for existing in seen):
                raise SystemExit("CONDA_ARCHIVE_NON_DIRECTORY_REPLACES_DIRECTORY")
            if member.isfile():
                kinds[name] = "file"
                total += member.size
            elif member.issym() or member.islnk():
                target = safe_link_target(name, member.linkname, member.islnk())
                if target is None:
                    raise SystemExit("CONDA_ARCHIVE_LINK_ESCAPE")
                if member.issym():
                    kinds[name] = "symlink"
                else:
                    hardlinks.append((name, target))
                    kinds[name] = "hardlink"
            elif not member.isdir():
                raise SystemExit("CONDA_ARCHIVE_SPECIAL_FILE_UNSUPPORTED")
            else:
                kinds[name] = "dir"
            if total > int(sys.argv[2]):
                raise SystemExit("CONDA_ARCHIVE_UNPACKED_SIZE_LIMIT")
for name, target in hardlinks:
    if kinds.get(target) != "file":
        raise SystemExit("CONDA_ARCHIVE_HARDLINK_TARGET_NOT_REGULAR_FILE")
    parts = target.split("/")
    if any(kinds.get("/".join(parts[:i])) not in (None, "dir") for i in range(1, len(parts))):
        raise SystemExit("CONDA_ARCHIVE_HARDLINK_TARGET_THROUGH_NON_DIRECTORY")
'''


def load_local_repodata(channel: Path) -> dict[str, dict]:
    result = {}
    for subdir in ("linux-64", "noarch"):
        try:
            result[subdir] = json.loads((channel / subdir / "repodata.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"LOCAL_CONDA_REPODATA_INVALID:{subdir}:{exc}") from exc
    return result


def load_solver_plan(conda: str, work: Path, package_cache: Path | None = None) -> tuple[list[dict], str, str]:
    plan_path = work / "conda-solve.json"
    solve_prefix = work / "solve-prefix"
    channel = os.environ.get("PMA_HINT_ARGOS_CONDA_CHANNEL", "https://conda.anaconda.org/conda-forge")
    if not channel.startswith("https://"):
        raise RuntimeError("CONDA_CHANNEL_MUST_BE_EXPLICIT_HTTPS_URL")
    parsed_channel = urlsplit(channel)
    if not parsed_channel.netloc or parsed_channel.username or parsed_channel.password or parsed_channel.query or parsed_channel.fragment:
        raise RuntimeError("CONDA_CHANNEL_MUST_NOT_CONTAIN_CREDENTIALS_OR_QUERY")
    options = ["--no-default-packages", "--override-channels", "--repodata-fn", "repodata.json",
               "-c", channel]
    command = [conda, "create", "--dry-run", "--json", "--yes", *options,
               "-p", str(solve_prefix), *TARGET_SPECS]
    repodata_before = {}
    for subdir in ("linux-64", "noarch"):
        repodata_before[subdir] = fetch_repodata_snapshot(
            channel, subdir, work, load_records=False, snapshot_id="before")
    output = conda_dry_run(conda, solve_prefix, options, TARGET_SPECS, package_cache=package_cache)
    try:
        parsed = json.loads(output)
        links = parsed["actions"]["LINK"]
        fetches = parsed["actions"].get("FETCH", [])
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise RuntimeError(f"CONDA_SOLVER_JSON_INVALID:{exc}") from exc
    if not links:
        raise RuntimeError("CONDA_SOLVER_LINK_EMPTY")
    if repodata_before:
        repodata_by_subdir = {}
        for subdir in ("linux-64", "noarch"):
            snapshot = fetch_repodata_snapshot(
                channel, subdir, work, load_records=True, snapshot_id="after")
            if snapshot["sha256"] != repodata_before[subdir]["sha256"]:
                raise RuntimeError(f"ARGOS_UPSTREAM_REPODATA_CHANGED_DURING_SOLVE:{subdir}")
            if package_cache is None:
                raise RuntimeError("CONDA_PACKAGE_CACHE_REQUIRED_FOR_SOLVE_PROVENANCE")
            snapshot["solver_cache"] = verify_solver_repodata_cache(
                package_cache, channel, subdir, snapshot)
            repodata_by_subdir[subdir] = snapshot
        resolved = resolve_solver_artifacts(links, repodata_by_subdir, fetches=fetches,
                                            expected_channel=channel)
        for original, normalized in zip(links, resolved):
            original.update(normalized)
            original["pma_upstream_repodata"] = {
                "url": repodata_by_subdir[_solver_subdir(original)]["url"],
                "sha256": repodata_by_subdir[_solver_subdir(original)]["sha256"],
                "evidence_file": repodata_by_subdir[_solver_subdir(original)]["evidence_file"],
                "solver_cache": repodata_by_subdir[_solver_subdir(original)]["solver_cache"]}
    plan_path.write_text(json.dumps(sanitize_evidence(parsed), indent=2, sort_keys=True) + "\n",
                         encoding="utf-8")
    return links, " ".join(command), output


def fetch_repodata_snapshot(channel: str, subdir: str, work: Path, *, load_records: bool,
                            snapshot_id: str) -> dict:
    if subdir not in ("linux-64", "noarch"):
        raise RuntimeError(f"ARGOS_REPODATA_SUBDIR_UNSUPPORTED:{subdir}")
    if snapshot_id not in ("before", "after"):
        raise RuntimeError("ARGOS_REPODATA_SNAPSHOT_ID_INVALID")
    url = f"{channel.rstrip('/')}/{subdir}/repodata.json"
    path = work / f"upstream-repodata-{subdir}-{snapshot_id}.json"
    try:
        urllib.request.urlretrieve(url, path)
        digest = sha256(path)
        result = {"url": sanitize_url(url), "sha256": digest, "size": path.stat().st_size,
                  "evidence_file": path.name}
        (work / f"{path.name}.provenance.json").write_text(
            json.dumps({"snapshot_id": snapshot_id, "subdir": subdir, "url": result["url"],
                        "sha256": digest, "evidence_file": path.name},
                       indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if load_records:
            try:
                with path.open(encoding="utf-8") as stream:
                    repodata = json.load(stream)
            except (OSError, json.JSONDecodeError) as exc:
                raise RuntimeError(f"ARGOS_UPSTREAM_REPODATA_INVALID:{subdir}:{exc}") from exc
            for section in ("packages", "packages.conda"):
                packages = repodata.get(section)
                if not isinstance(packages, dict):
                    raise RuntimeError(f"ARGOS_UPSTREAM_REPODATA_SECTION_MISSING:{subdir}:{section}")
                result[section] = packages
            result["info"] = repodata.get("info", {})
        return result
    except (OSError, urllib.error.URLError) as exc:
        raise RuntimeError(f"ARGOS_UPSTREAM_REPODATA_FETCH_FAILED:{subdir}:{sanitize_text(str(exc))}") from exc


def copy_conda_closure(links: list[dict], bundle: Path, conda: str, work: Path) -> list[dict]:
    records = []
    extractor_python = None
    for item in links:
        artifact = item.get("pma_artifact")
        if not isinstance(artifact, dict):
            raise RuntimeError("CONDA_ARTIFACT_LOCK_MISSING")
        filename = artifact["filename"]
        subdir = artifact["subdir"]
        url = artifact["artifact_url"]
        digest = artifact["sha256"]
        if (subdir not in ("linux-64", "noarch") or
                not (filename.endswith(".tar.bz2") or filename.endswith(".conda"))):
            raise RuntimeError(f"UNSUPPORTED_CONDA_ARTIFACT:{subdir}:{filename}")
        if not re.fullmatch(r"[0-9a-fA-F]{64}", str(digest or "")):
            raise RuntimeError(f"CONDA_SHA256_MISSING:{filename}")
        if not url.startswith("https://"):
            raise RuntimeError(f"CONDA_SOURCE_URL_INVALID:{filename}")
        destination = bundle / "conda" / subdir / filename
        destination.parent.mkdir(parents=True, exist_ok=True)
        partial = destination.with_name(destination.name + ".partial")
        if destination.exists() or partial.exists():
            raise RuntimeError(f"CONDA_ARTIFACT_DESTINATION_EXISTS:{filename}")
        try:
            urllib.request.urlretrieve(url, partial)
            if partial.stat().st_size != artifact["size"]:
                raise RuntimeError(f"CONDA_SIZE_MISMATCH:{filename}")
            if sha256(partial) != digest.lower():
                raise RuntimeError(f"CONDA_SHA256_MISMATCH:{filename}")
            if artifact.get("md5") and md5(partial) != artifact["md5"].lower():
                raise RuntimeError(f"CONDA_MD5_MISMATCH:{filename}")
            os.replace(partial, destination)
        except Exception:
            partial.unlink(missing_ok=True)
            raise
        if filename.endswith(".conda"):
            validate_conda_archive(destination, artifact)
            if extractor_python is None:
                extractor_python, _ = conda_extractor(conda, work)
            extract_dir = work / "artifact-info" / re.sub(r"[^A-Za-z0-9_.-]", "_", filename)
            extracted = extract_conda_archive(extractor_python, destination, extract_dir, work)
            index_path = extracted / "info" / "index.json"
            try:
                index = json.loads(index_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise RuntimeError(f"CONDA_PACKAGE_INDEX_INVALID:{filename}:{exc}") from exc
            shutil.rmtree(extracted)
        else:
            with tarfile.open(destination, "r:bz2") as archive:
                index = json.load(archive.extractfile("info/index.json"))
        record = {"subdir": subdir, "name": index["name"], "version": index["version"],
                  "build": index["build"], "filename": filename, "sha256": digest.lower()}
        plan_build = artifact["build"]
        if (record["name"], record["version"], record["build"]) != (
                artifact["name"], artifact["version"], plan_build):
            raise RuntimeError(f"CONDA_PACKAGE_IDENTITY_MISMATCH:{filename}")
        for field in ("depends", "constrains"):
            if field in index and sorted(index[field]) != sorted(artifact.get(field) or []):
                item.setdefault("pma_package_index_metadata_diff", {})[field] = {
                    "archive_index": index[field], "solver_repodata": artifact.get(field) or []}
        record["md5"] = md5(destination)
        record["size"] = destination.stat().st_size
        record["source_url"] = sanitize_url(url)
        record["index_record"] = index
        if "pma_upstream_repodata_record" in item:
            record["source_record"] = item["pma_upstream_repodata_record"]
            record["source_repodata"] = item["pma_upstream_repodata"]
            record["solver_record"] = {key: item[key] for key in ("depends", "constrains") if key in item}
            record["solver_metadata_fields"] = item.get("pma_solver_metadata_fields", {})
        else:
            record["source_record"] = {key: value for key, value in item.items()
                                       if key not in {"url", "base_url", "channel", "channel_url"}}
        records.append(record)
    return records


def build_local_repodata(records: list[dict], subdir: str) -> dict:
    if subdir not in ("linux-64", "noarch"):
        raise RuntimeError(f"REPODATA_SUBDIR_UNSUPPORTED:{subdir}")
    packages = {}
    packages_conda = {}
    for row in records:
        if row["subdir"] != subdir:
            continue
        source = row.get("source_record") or {}
        index = row.get("index_record") or {}
        filename = row["filename"]
        if filename.endswith(".tar.bz2"):
            package_section = packages
        elif filename.endswith(".conda"):
            package_section = packages_conda
        else:
            raise RuntimeError(f"REPODATA_ARCHIVE_UNSUPPORTED:{filename}")
        if not isinstance(source.get("depends"), list):
            raise RuntimeError(f"REPODATA_UPSTREAM_DEPENDS_MISSING:{filename}")
        source_repodata = row.get("source_repodata")
        solver_record = row.get("solver_record")
        if source_repodata is not None:
            evidence_file = source_repodata.get("evidence_file", "")
            if (not source_repodata.get("url", "").startswith("https://") or
                    not re.fullmatch(r"[a-fA-F0-9]{64}", source_repodata.get("sha256", "")) or
                    Path(evidence_file).name != evidence_file or
                    not re.fullmatch(r"upstream-repodata-(linux-64|noarch)-after\.json", evidence_file)):
                raise RuntimeError(f"REPODATA_UPSTREAM_PROVENANCE_INVALID:{filename}")
            if not isinstance(solver_record, dict):
                raise RuntimeError(f"REPODATA_SOLVER_RECORD_MISSING:{filename}")
            solver_fields = row.get("solver_metadata_fields", {})
            for key in ("depends", "constrains"):
                if not solver_fields.get(key, key in solver_record):
                    continue
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
        if filename in package_section:
            raise RuntimeError(f"REPODATA_DUPLICATE_FILENAME:{filename}")
        package_section[filename] = record
    if not packages and not packages_conda:
        raise RuntimeError(f"REPODATA_SUBDIR_EMPTY:{subdir}")
    return {"info": {"subdir": subdir, "repodata_version": 1},
            "packages": packages, "packages.conda": packages_conda, "removed": []}


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


def audit_conda_elf(records: list[dict], bundle: Path, work: Path, conda: str) -> dict:
    readelf = shutil.which("readelf")
    if not readelf:
        raise RuntimeError("READELF_MISSING_CANNOT_PROVE_CONDA_ABI")
    extractor_python = EXTRACTOR_PYTHON
    if any(row["filename"].endswith(".conda") for row in records) and extractor_python is None:
        extractor_python, _ = conda_extractor(conda, work)
    glibc, glibcxx, cxxabi, provided_glibcxx, provided_cxxabi = [], [], [], [], []
    needed_libraries, package_libraries, package_elf_files, package_symlinks, checked = set(), set(), set(), [], 0
    for index, record in enumerate(records):
        archive_path = bundle / "conda" / record["subdir"] / record["filename"]
        if record["filename"].endswith(".conda"):
            extracted = extract_conda_archive(
                extractor_python, archive_path, work / f"abi-inventory-{index}", work)
            try:
                for member in extracted.rglob("*"):
                    basename = member.name
                    if member.is_symlink():
                        package_symlinks.append((basename, Path(os.readlink(member)).name))
                    elif member.is_file():
                        with member.open("rb") as source:
                            if source.read(4) == b"\x7fELF":
                                package_elf_files.add(basename)
            finally:
                shutil.rmtree(extracted)
            continue
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
    for index, record in enumerate(records):
        archive_path = bundle / "conda" / record["subdir"] / record["filename"]
        if record["filename"].endswith(".conda"):
            extracted = extract_conda_archive(
                extractor_python, archive_path, work / f"abi-audit-{index}", work)
            try:
                for member in extracted.rglob("*"):
                    if member.is_symlink() or not member.is_file():
                        continue
                    with member.open("rb") as source:
                        if source.read(4) != b"\x7fELF":
                            continue
                        source.seek(0)
                        staged = work / f"elf-{checked}"
                        with staged.open("wb") as out:
                            shutil.copyfileobj(source, out)
                    member_name = member.relative_to(extracted).as_posix()
                    header = run([readelf, "--file-header", str(staged)], capture=True)
                    machine_match = re.search(r"^\s*Machine:\s*(.+)$", header, re.MULTILINE)
                    if not machine_match:
                        raise RuntimeError(f"ELF_MACHINE_UNREADABLE:{member_name}")
                    elf_problems = check_elf_contract(machine_match.group(1), set(), package_libraries)
                    if elf_problems:
                        raise RuntimeError(f"{elf_problems[0]}:{member_name}")
                    versions = run([readelf, "--version-info", str(staged)], capture=True)
                    needed = run([readelf, "--dynamic", str(staged)], capture=True)
                    glibc.extend(readelf_versions(versions, "GLIBC", "needs"))
                    glibcxx.extend(readelf_versions(versions, "GLIBCXX", "needs"))
                    cxxabi.extend(readelf_versions(versions, "CXXABI", "needs"))
                    if member.name.startswith("libstdc++.so"):
                        provided_glibcxx.extend(readelf_versions(versions, "GLIBCXX", "definition"))
                        provided_cxxabi.extend(readelf_versions(versions, "CXXABI", "definition"))
                    needed_libraries.update(re.findall(r"\(NEEDED\).*?\[(.*?)\]", needed))
                    elf_problems = check_elf_contract(machine_match.group(1),
                        set(re.findall(r"\(NEEDED\).*?\[(.*?)\]", needed)), package_libraries)
                    if elf_problems:
                        raise RuntimeError(f"{elf_problems[0]}:{member_name}")
                    checked += 1
                    staged.unlink()
            finally:
                shutil.rmtree(extracted)
            continue
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
            "scope": "static-elf-compatibility-audit",
            "runtime_linkability_verified": False,
            "method": "readelf machine, version-needs/definitions, and DT_NEEDED basename resolution across locked package members and explicit system runtime allowlist; does not resolve runtime RPATH/RUNPATH",
            "conda_extractor": EXTRACTOR_PROVENANCE if any(row["filename"].endswith(".conda") for row in records) else None}


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
    work = evidence / "work"
    work.mkdir()
    if builder_mode == "argos-native":
        package_cache = Path(os.environ["CONDA_PKGS_DIRS"]).resolve()
    else:
        package_cache = work / "conda-package-cache"
    (evidence / "conda-solver-cache-root.json").write_text(
        json.dumps({"cache_root": str(package_cache.resolve())}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    try:
        links, solve_command, solve_json = load_solver_plan(conda, work, package_cache=package_cache)
        parsed_solve = json.loads(solve_json)
        (evidence / "conda-solve.json").write_text(
            json.dumps(sanitize_evidence(parsed_solve), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (evidence / "conda-upstream-link-records.json").write_text(
            json.dumps(sanitize_evidence(links), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        conda_records = copy_conda_closure(links, bundle, conda, work)
        if EXTRACTOR_PROVENANCE:
            (evidence / "conda-extractor-provenance.json").write_text(
                json.dumps(sanitize_evidence(EXTRACTOR_PROVENANCE), indent=2, sort_keys=True) + "\n",
                encoding="utf-8")
        (evidence / "conda-artifact-provenance.json").write_text(
            json.dumps(sanitize_evidence(conda_records), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        write_local_repodata(conda_records, bundle / "conda")
        abi = audit_conda_elf(conda_records, bundle, work, conda)
        offline_prefix = work / "offline-solve-prefix"
        offline_options = ["--offline", "--no-default-packages", "--override-channels",
                           "--repodata-fn", "repodata.json", "-c",
                           (bundle / "conda").as_uri()]
        offline = conda_dry_run(conda, offline_prefix, offline_options, TARGET_SPECS,
                                package_cache=package_cache)
        (evidence / "conda-offline-solve.json").write_text(sanitize_text(offline), encoding="utf-8")
        try:
            offline_links = json.loads(offline)["actions"]["LINK"]
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise RuntimeError(f"CONDA_OFFLINE_SOLVER_JSON_INVALID:{exc}") from exc
        offline_repodata_provenance = {}
        for subdir in ("linux-64", "noarch"):
            local_path = bundle / "conda" / subdir / "repodata.json"
            local_snapshot = {"sha256": sha256(local_path), "size": local_path.stat().st_size}
            offline_repodata_provenance[subdir] = verify_solver_repodata_cache(
                package_cache, (bundle / "conda").as_uri(), subdir, local_snapshot)
        (evidence / "conda-offline-repodata-provenance.json").write_text(
            json.dumps(offline_repodata_provenance, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
        offline_resolved = resolve_solver_artifacts(
            offline_links, load_local_repodata(bundle / "conda"),
            fetches=json.loads(offline).get("actions", {}).get("FETCH", []),
            expected_channel=(bundle / "conda").as_uri())
        def identity(row: dict) -> tuple:
            artifact = row["pma_artifact"]
            return (row["name"], row["version"], artifact["build"], artifact["subdir"],
                    artifact["filename"], artifact["sha256"])
        online_identities = sorted(identity(row) for row in links)
        offline_identities = sorted(identity(row) for row in offline_resolved)
        if online_identities != offline_identities:
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
            "conda": run_conda([conda, "--version"], capture=True).strip(),
            "pip": run([str(build_python), "-m", "pip", "--version"], capture=True).strip(),
            "conda_index_packages": (run_conda([conda, "list", "conda-index"], capture=True).strip()
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
                    "conda_version": run_conda([conda, "--version"], capture=True).strip(),
            "conda_toolchain_explicit_sha256": (sha256(evidence / "build-toolchain-conda-explicit.txt")
                                                 if builder_mode == "docker-image" else None),
            "pip_toolchain_inventory_sha256": (sha256(evidence / "build-toolchain-pip.json")
                                                if builder_mode == "docker-image" else None),
                    "pip_version": run([sys.executable, "-m", "pip", "--version"], capture=True).strip(),
                    "rgt_sdist_sha256": RGT_SHA256, "rgt_wheel": rgt_wheel.name,
                    "rgt_wheel_sha256": sha256(rgt_wheel), "rgt_build_report": "reports/rgt-wheel-audit.json",
                    "rgt_build_report_sha256": sha256(report_path), "conda_lock_sha256": sha256(conda_lock),
                    "pip_lock_sha256": sha256(pip_lock), "artifacts_sha256": sha256(bundle / "artifacts.sha256"),
                    "conda_artifact_format_counts": {
                        "tar.bz2": sum(row["filename"].endswith(".tar.bz2") for row in conda_records),
                        "conda": sum(row["filename"].endswith(".conda") for row in conda_records)},
                    "conda_online_repodata": {
                        subdir: next(row["pma_upstream_repodata"] for row in links
                                     if row["pma_artifact"]["subdir"] == subdir)
                        for subdir in ("linux-64", "noarch")
                        if any(row["pma_artifact"]["subdir"] == subdir for row in links)},
                    "conda_offline_repodata_provenance_sha256": sha256(
                        evidence / "conda-offline-repodata-provenance.json"),
                    "conda_extractor_provenance_sha256": (sha256(evidence / "conda-extractor-provenance.json")
                                                           if (evidence / "conda-extractor-provenance.json").is_file()
                                                           else None),
                    "conda_solve_command": sanitize_evidence(solve_command)}
        (bundle / "bundle-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        validator = Path(__file__).with_name("validate_hint_bundle.py")
        run([sys.executable, str(validator), str(bundle), "--evidence-dir", str(evidence)])
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
