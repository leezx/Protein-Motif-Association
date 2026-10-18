#!/usr/bin/env python3
"""Build a CPython 3.11/Linux HINT bundle from a pinned Conda solve.

This program is intentionally limited to artifact construction. It never
creates an Argos environment. Bundle and evidence directories must both be
outside the repository. Run only in a reviewed, digest-pinned linux/amd64 image.
"""
from __future__ import annotations

import argparse
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
from datetime import datetime, timezone
from email.parser import Parser
from pathlib import Path

from packaging.utils import canonicalize_name, parse_wheel_filename

RGT_SHA256 = "2169e71f2018340d101146bab09bb933a384611c5f7b76f4be5999fa835cac7e"
TARGET_SPECS = ("python=3.11", "numpy=1.26.4", "setuptools=80.9.0", "pip")
RUN_LOG: Path | None = None


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run(argv: list[str], *, capture: bool = False) -> str:
    result = subprocess.run(argv, check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    output = result.stdout or ""
    if RUN_LOG:
        with RUN_LOG.open("a", encoding="utf-8") as log:
            log.write(f"\n[{datetime.now(timezone.utc).isoformat()}] $ {shlex.join(argv)}\n")
            log.write(output)
            log.write(f"\n[exit={result.returncode}]\n")
    if result.returncode:
        raise subprocess.CalledProcessError(result.returncode, argv, output=output)
    if output and not capture:
        sys.stdout.write(output)
    return output


def require_builder() -> tuple[str, str]:
    if platform.system() != "Linux" or platform.machine() not in ("x86_64", "AMD64"):
        raise RuntimeError("BUILDER_PLATFORM_MUST_BE_LINUX_X86_64")
    if sys.version_info[:2] != (3, 11):
        raise RuntimeError(f"BUILDER_PYTHON_MUST_BE_3_11:{platform.python_version()}")
    libc, version = platform.libc_ver()
    if libc != "glibc" or tuple(map(int, version.split(".")[:2])) > (2, 23):
        raise RuntimeError(f"BUILDER_GLIBC_MUST_BE_LE_2_23:{libc}:{version}")
    image = os.environ.get("PMA_HINT_BUILDER_IMAGE", "")
    if not re.fullmatch(r"[^\s]+@sha256:[0-9a-f]{64}", image):
        raise RuntimeError("PMA_HINT_BUILDER_IMAGE_MUST_BE_DIGEST_PINNED")
    conda = shutil.which("conda")
    if not conda:
        raise RuntimeError("CONDA_EXECUTABLE_MISSING")
    for executable, code in (("readelf", "READELF_MISSING_CANNOT_PROVE_CONDA_ABI"),
                             ("auditwheel", "AUDITWHEEL_MISSING_CANNOT_PROVE_WHEEL_ABI"),
                             ("gcc", "GCC_MISSING_FOR_CONTROLLED_RGT_BUILD")):
        if not shutil.which(executable):
            raise RuntimeError(code)
    return conda, version


def load_solver_plan(conda: str, work: Path) -> tuple[list[dict], str, str]:
    plan_path = work / "conda-solve.json"
    command = [conda, "create", "--dry-run", "--json", "--yes", "--no-default-packages",
               "--override-channels", "-c", "conda-forge", "-p", str(work / "solve-prefix"), *TARGET_SPECS]
    output = run(command, capture=True)
    plan_path.write_text(output, encoding="utf-8")
    try:
        parsed = json.loads(output)
        links = parsed["actions"]["LINK"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise RuntimeError(f"CONDA_SOLVER_JSON_INVALID:{exc}") from exc
    if not links:
        raise RuntimeError("CONDA_SOLVER_LINK_EMPTY")
    return links, " ".join(command), output


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
                  "build": index["build"], "filename": filename, "sha256": digest.lower(), "url": url}
        plan_build = item.get("build") or item.get("build_string")
        if (record["name"], record["version"], record["build"]) != (
                item.get("name"), item.get("version"), plan_build):
            raise RuntimeError(f"CONDA_PACKAGE_IDENTITY_MISMATCH:{filename}")
        records.append(record)
    return records


def version_max(values: list[str]) -> str:
    if not values:
        return "2.0"
    return ".".join(map(str, max(tuple(map(int, value.split("."))) for value in values)))


def audit_conda_elf(records: list[dict], bundle: Path, work: Path) -> dict:
    readelf = shutil.which("readelf")
    if not readelf:
        raise RuntimeError("READELF_MISSING_CANNOT_PROVE_CONDA_ABI")
    glibc, glibcxx, cxxabi, needed_libraries, checked = [], [], [], set(), 0
    for record in records:
        archive_path = bundle / "conda" / record["subdir"] / record["filename"]
        with tarfile.open(archive_path, "r:bz2") as archive:
            for member in archive:
                if not member.isfile():
                    continue
                source = archive.extractfile(member)
                if source is None or source.read(4) != b"\x7fELF":
                    continue
                source.seek(0)
                staged = work / f"elf-{checked}"
                with staged.open("wb") as out:
                    shutil.copyfileobj(source, out)
                versions = run([readelf, "--version-info", str(staged)], capture=True)
                needed = run([readelf, "--dynamic", str(staged)], capture=True)
                glibc.extend(re.findall(r"GLIBC_(\d+(?:\.\d+)+)", versions))
                glibcxx.extend(re.findall(r"GLIBCXX_(\d+(?:\.\d+)+)", versions))
                cxxabi.extend(re.findall(r"CXXABI_(\d+(?:\.\d+)+)", versions))
                needed_libraries.update(re.findall(r"\(NEEDED\).*?\[(.*?)\]", needed))
                checked += 1
                staged.unlink()
    if checked == 0:
        raise RuntimeError("CONDA_CLOSURE_HAS_NO_AUDITED_ELF")
    glibc_max, glibcxx_max, cxxabi_max = version_max(glibc), version_max(glibcxx), version_max(cxxabi)
    if tuple(map(int, glibc_max.split("."))) > (2, 23):
        raise RuntimeError(f"CONDA_GLIBC_ABI_TOO_NEW:{glibc_max}")
    return {"elf_files_checked": checked, "glibc_max": glibc_max,
            "glibcxx_max": glibcxx_max, "cxxabi_max": cxxabi_max,
            "needed_libraries": sorted(needed_libraries),
            "method": "readelf --version-info and --dynamic on every ELF member in each locked archive"}


def audit_rgt_wheel(wheel: Path, builder: str, work: Path, sdist_digest: str) -> dict:
    with zipfile.ZipFile(wheel) as archive:
        elf_members = []
        for name in archive.namelist():
            if name.endswith("/"):
                continue
            with archive.open(name) as member:
                if member.read(4) == b"\x7fELF":
                    elf_members.append(name)
    if elf_members:
        auditwheel = shutil.which("auditwheel")
        if not auditwheel:
            raise RuntimeError("AUDITWHEEL_MISSING_FOR_NATIVE_RGT_WHEEL")
        output = run([auditwheel, "show", str(wheel)], capture=True)
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
                "auditwheel_output": output, "rgt_sdist_sha256": sdist_digest,
                "rgt_wheel": wheel.name, "rgt_wheel_sha256": sha256(wheel)}
    return {"builder": builder, "python_abi": "cp311", "glibc_symbol_max": "2.0",
            "auditwheel_policy": "pure-python-no-ELF", "native_dependencies": [],
            "rgt_sdist_sha256": sdist_digest, "rgt_wheel": wheel.name,
            "rgt_wheel_sha256": sha256(wheel)}


def audit_pip_wheels(wheels: list[Path], work: Path) -> dict:
    auditwheel = shutil.which("auditwheel")
    audited, glibc, glibcxx, cxxabi = [], [], [], []
    for wheel in wheels:
        with zipfile.ZipFile(wheel) as archive:
            elf_members = []
            for name in archive.namelist():
                if name.endswith("/"):
                    continue
                with archive.open(name) as member:
                    if member.read(4) == b"\x7fELF":
                        elf_members.append(name)
        if not elf_members:
            audited.append({"wheel": wheel.name, "sha256": sha256(wheel), "type": "pure-python-no-ELF"})
            continue
        if not auditwheel:
            raise RuntimeError(f"AUDITWHEEL_MISSING:{wheel.name}")
        output = run([auditwheel, "show", str(wheel)], capture=True)
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
                        "elf_members": elf_members, "auditwheel_output": output})
    return {"wheels": audited, "glibc_max": version_max(glibc),
            "glibcxx_max": version_max(glibcxx), "cxxabi_max": version_max(cxxabi)}


def fetch_and_build_rgt(bundle: Path, work: Path, python: Path) -> Path:
    source_dir = work / "sources"
    source_dir.mkdir()
    source_log = run([str(python), "-m", "pip", "download", "-v", "--no-deps", "--no-binary=:all:",
                      "--dest", str(source_dir), "RGT==1.0.2"], capture=True)
    (work / "rgt-sdist-download.log").write_text(source_log, encoding="utf-8")
    sources = list(source_dir.iterdir())
    if len(sources) != 1 or sha256(sources[0]) != RGT_SHA256:
        raise RuntimeError("RGT_SDIST_SOURCE_OR_HASH_MISMATCH")
    wheel_dir = bundle / "wheels"
    wheel_dir.mkdir(parents=True, exist_ok=True)
    wheel_log = run([str(python), "-m", "pip", "wheel", "-v", "--no-deps", "--no-build-isolation",
                     "--wheel-dir", str(wheel_dir), str(sources[0])], capture=True)
    (work / "rgt-wheel-build.log").write_text(wheel_log, encoding="utf-8")
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
    (work / "pip-wheel-download.log").write_text(pip_log, encoding="utf-8")
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
    conda, _builder_glibc = require_builder()
    work = evidence / "work"
    work.mkdir()
    try:
        links, solve_command, solve_json = load_solver_plan(conda, work)
        (evidence / "conda-solve.json").write_text(solve_json, encoding="utf-8")
        conda_records = copy_conda_closure(links, bundle)
        run([conda, "index", str(bundle / "conda")])
        abi = audit_conda_elf(conda_records, bundle, work)
        offline = run([conda, "create", "--dry-run", "--json", "--yes", "--offline",
                       "--no-default-packages", "--override-channels", "-c",
                       (bundle / "conda").as_uri(), "-p", str(work / "offline-solve-prefix"),
                       *TARGET_SPECS], capture=True)
        (evidence / "conda-offline-solve.json").write_text(offline, encoding="utf-8")
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
        build_prefix = work / "rgt-build-prefix"
        run([conda, "create", "--yes", "--offline", "--copy", "--no-default-packages",
             "--override-channels", "-c", (bundle / "conda").as_uri(), "-p", str(build_prefix), *TARGET_SPECS])
        build_python = build_prefix / "bin/python"
        build_python_version = run([str(build_python), "--version"], capture=True).strip()
        if not re.fullmatch(r"Python 3\.11\.\d+", build_python_version):
            raise RuntimeError(f"BUILD_PREFIX_PYTHON_MISMATCH:{build_python_version}")
        rgt_wheel = fetch_and_build_rgt(bundle, work, build_python)
        wheels = resolve_pip_closure(rgt_wheel, bundle, work, conda_records, build_python)
        wheel_abi = audit_pip_wheels(wheels, work)
        conda_lock = bundle / "conda-explicit-linux-64.lock"
        conda_lock.write_text("".join("\t".join(row[k] for k in ("subdir", "name", "version", "build", "filename", "sha256")) + "\n" for row in conda_records), encoding="utf-8")
        pip_lock = bundle / "pip-requirements.lock"
        pip_lock.write_text(render_pip_lock(wheels), encoding="utf-8")
        report_path = bundle / "reports" / "rgt-wheel-audit.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        rgt_report = audit_rgt_wheel(rgt_wheel, os.environ["PMA_HINT_BUILDER_IMAGE"], work, RGT_SHA256)
        rgt_report["conda_abi_audit"] = abi
        report_path.write_text(json.dumps(rgt_report, indent=2) + "\n", encoding="utf-8")
        wheel_report_path = bundle / "reports" / "pip-wheel-abi-audit.json"
        wheel_report_path.write_text(json.dumps(wheel_abi, indent=2) + "\n", encoding="utf-8")
        for log_name in ("rgt-sdist-download.log", "rgt-wheel-build.log", "pip-wheel-download.log"):
            shutil.copy2(work / log_name, evidence / log_name)
        (evidence / "builder-versions.json").write_text(json.dumps({
            "builder_image": os.environ["PMA_HINT_BUILDER_IMAGE"], "architecture": platform.machine(),
            "python": platform.python_version(), "glibc": platform.libc_ver(),
            "conda": run([conda, "--version"], capture=True).strip(),
            "pip": run([str(build_python), "-m", "pip", "--version"], capture=True).strip(),
            "conda_index_packages": run([conda, "list", "conda-index"], capture=True).strip(),
            "auditwheel": run(["auditwheel", "--version"], capture=True).strip(),
            "readelf": run(["readelf", "--version"], capture=True).splitlines()[0],
            "gcc": run(["gcc", "--version"], capture=True).splitlines()[0],
            "build_prefix_python": build_python_version,
            "conda_solve_command": solve_command, "conda_artifacts": conda_records,
            "conda_abi_audit": abi, "pip_wheel_abi_audit": wheel_abi}, indent=2) + "\n", encoding="utf-8")
        inventory = []
        for path in sorted(bundle.rglob("*")):
            if path.is_file() and path.name != "artifacts.sha256":
                inventory.append(f"{sha256(path)}  {path.relative_to(bundle).as_posix()}\n")
        (bundle / "artifacts.sha256").write_text("".join(inventory), encoding="utf-8")
        manifest = {"schema_version": 1, "target_platform": "linux-64", "python_abi": "cp311",
                    "glibc_max": version_max([abi["glibc_max"], wheel_abi["glibc_max"]]),
                    "builder": os.environ["PMA_HINT_BUILDER_IMAGE"],
                    "conda_version": run([conda, "--version"], capture=True).strip(),
                    "pip_version": run([sys.executable, "-m", "pip", "--version"], capture=True).strip(),
                    "rgt_sdist_sha256": RGT_SHA256, "rgt_wheel": rgt_wheel.name,
                    "rgt_wheel_sha256": sha256(rgt_wheel), "rgt_build_report": "reports/rgt-wheel-audit.json",
                    "rgt_build_report_sha256": sha256(report_path), "conda_lock_sha256": sha256(conda_lock),
                    "pip_lock_sha256": sha256(pip_lock), "artifacts_sha256": sha256(bundle / "artifacts.sha256"),
                    "conda_solve_command": solve_command}
        (bundle / "bundle-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        validator = Path(__file__).with_name("validate_hint_bundle.py")
        run([sys.executable, str(validator), str(bundle)])
        shutil.rmtree(build_prefix)
        shutil.copy2(bundle / "bundle-manifest.json", evidence / "bundle-manifest.json")
        archive_path = evidence / "pma_hint_bundle.tar.gz"
        with tarfile.open(archive_path, "w:gz") as archive:
            archive.add(bundle, arcname="pma_hint_bundle")
        (evidence / "bundle-archive.sha256").write_text(
            sha256(archive_path) + "  pma_hint_bundle.tar.gz\n", encoding="utf-8")
        return 0
    except Exception as exc:
        (evidence / "build-failure.txt").write_text(f"{type(exc).__name__}: {exc}\n", encoding="utf-8")
        raise


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, subprocess.CalledProcessError, ValueError) as exc:
        print(f"HINT_BUNDLE_BUILD_FAILED:{exc}", file=sys.stderr)
        raise SystemExit(1)
