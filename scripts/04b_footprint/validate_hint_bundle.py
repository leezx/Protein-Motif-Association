#!/usr/bin/env python3
"""Validate the immutable files and pip dependency closure in an offline HINT bundle."""
import argparse
import hashlib
import json
import os
import re
import sys
import zipfile
from email.parser import Parser
from pathlib import Path

from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import parse_wheel_filename
from packaging.version import Version

RGT_SDIST_SHA256 = "2169e71f2018340d101146bab09bb933a384611c5f7b76f4be5999fa835cac7e"


def conda_container_issues(path, name, version, build):
    expected = {"metadata.json", f"info-{name}-{version}-{build}.tar.zst",
                f"pkg-{name}-{version}-{build}.tar.zst"}
    try:
        with zipfile.ZipFile(path) as archive:
            members = archive.infolist()
            names = [member.filename for member in members]
            if len(names) != len(set(names)) or set(names) != expected:
                return ["CONDA_ZIP_MEMBERS_INVALID"]
            if any(member.compress_type != zipfile.ZIP_STORED or member.flag_bits & 1 for member in members):
                return ["CONDA_ZIP_CONTAINER_ENCODING_INVALID"]
            metadata = json.loads(archive.read("metadata.json"))
            if not isinstance(metadata, dict) or metadata.get("conda_pkg_format_version") != 2:
                return ["CONDA_ZIP_FORMAT_VERSION_UNSUPPORTED"]
            if archive.testzip() is not None:
                return ["CONDA_ZIP_CRC_FAILED"]
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError):
        return ["CONDA_ZIP_INVALID"]
    return []


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


def solver_identity_rows(solve, repodata_by_subdir, channel_by_subdir, label):
    issues = []
    if not isinstance(solve, dict) or not isinstance(solve.get("actions"), dict):
        return [], [f"{label}_SOLVE_ACTIONS_INVALID"]
    actions = solve["actions"]
    links, fetches = actions.get("LINK"), actions.get("FETCH", [])
    if not isinstance(links, list) or not isinstance(fetches, list):
        return [], [f"{label}_SOLVE_LINK_FETCH_INVALID"]
    consumed_fetches = set()
    identities = []
    for link_index, link in enumerate(links):
        if not isinstance(link, dict):
            issues.append(f"{label}_SOLVE_LINK_ROW_INVALID:{link_index}")
            continue
        subdir = link.get("subdir") or link.get("platform")
        name, version = link.get("name"), link.get("version")
        build = link.get("build") or link.get("build_string")
        if (subdir not in ("linux-64", "noarch") or
                not all(isinstance(value, str) and value for value in (name, version, build))):
            issues.append(f"{label}_SOLVE_LINK_IDENTITY_INVALID:{link_index}")
            continue
        if link.get("dist_name") not in (None, f"{name}-{version}-{build}"):
            issues.append(f"{label}_SOLVE_DIST_IDENTITY_MISMATCH:{name}")
        expected_channel = channel_by_subdir.get(subdir)
        if link.get("base_url") != expected_channel:
            issues.append(f"{label}_SOLVE_LINK_CHANNEL_MISMATCH:{name}")
        snapshot = repodata_by_subdir.get(subdir, {})
        candidates = []
        for section, suffix in (("packages", ".tar.bz2"), ("packages.conda", ".conda")):
            section_records = snapshot.get(section, {})
            if not isinstance(section_records, dict):
                issues.append(f"{label}_SOLVE_REPODATA_SECTION_INVALID:{subdir}:{section}")
                continue
            for filename, record in section_records.items():
                if (isinstance(filename, str) and filename.endswith(suffix) and isinstance(record, dict) and
                        (record.get("name"), record.get("version"), record.get("build")) ==
                        (name, version, build)):
                    candidates.append((section, filename, record))
        matching_fetches = []
        for fetch_index, fetch in enumerate(fetches):
            if not isinstance(fetch, dict):
                issues.append(f"{label}_SOLVE_FETCH_ROW_INVALID:{fetch_index}")
                continue
            fetch_subdir = fetch.get("subdir") or fetch.get("platform")
            fetch_build = fetch.get("build") or fetch.get("build_string")
            fetch_identity = (fetch.get("name"), fetch.get("version"), fetch_build)
            link_identity = (name, version, build)
            fetch_base = fetch.get("base_url")
            if fetch_identity == link_identity and fetch_subdir != subdir:
                issues.append(f"{label}_SOLVE_FETCH_SUBDIR_MISMATCH:{name}")
            if (fetch_identity == link_identity and fetch_subdir == subdir and fetch_base and
                    fetch_base.rstrip("/") != expected_channel.rstrip("/")):
                issues.append(f"{label}_SOLVE_FETCH_CHANNEL_MISMATCH:{name}")
            if fetch_identity == link_identity and fetch_subdir == subdir:
                matching_fetches.append((fetch_index, fetch))
        if len(matching_fetches) > 1:
            issues.append(f"{label}_SOLVE_FETCH_DUPLICATE:{name}")
            continue
        if matching_fetches:
            fetch_index, fetch = matching_fetches[0]
            if fetch_index in consumed_fetches:
                issues.append(f"{label}_SOLVE_FETCH_REUSED:{name}")
                continue
            consumed_fetches.add(fetch_index)
            filename = fetch.get("fn")
            fetch_url = fetch.get("url")
            if fetch_url:
                url_filename = fetch_url.rsplit("/", 1)[-1]
                if filename and filename != url_filename:
                    issues.append(f"{label}_SOLVE_FETCH_FILENAME_CONFLICT:{name}")
                filename = filename or url_filename
            fetch_sha = fetch.get("sha256")
            fetch_md5 = fetch.get("md5")
            if (fetch_sha is not None and not re.fullmatch(r"[a-fA-F0-9]{64}", str(fetch_sha))):
                issues.append(f"{label}_SOLVE_FETCH_SHA256_INVALID:{name}")
            if (fetch_md5 is not None and not re.fullmatch(r"[a-fA-F0-9]{32}", str(fetch_md5))):
                issues.append(f"{label}_SOLVE_FETCH_MD5_INVALID:{name}")
            if not filename or not (fetch_sha or fetch_md5):
                issues.append(f"{label}_SOLVE_FETCH_IDENTITY_INCOMPLETE:{name}")
                continue
            candidates = [candidate for candidate in candidates
                          if candidate[1] == filename and
                          (not fetch_sha or str(candidate[2].get("sha256", "")).lower() ==
                           str(fetch_sha).lower()) and
                          (not fetch_md5 or str(candidate[2].get("md5", "")).lower() ==
                           str(fetch_md5).lower())]
            expected_url = f"{expected_channel.rstrip('/')}/{subdir}/{filename}"
            if fetch_url and fetch_url != expected_url:
                issues.append(f"{label}_SOLVE_FETCH_URL_MISMATCH:{filename}")
        if len(candidates) != 1:
            issues.append(f"{label}_SOLVE_ARTIFACT_NOT_UNIQUE:{subdir}:{name}:{len(candidates)}")
            continue
        _section, filename, record = candidates[0]
        digest = record.get("sha256")
        size = record.get("size")
        if not re.fullmatch(r"[0-9a-fA-F]{64}", str(digest or "")) or not isinstance(size, int) or size <= 0:
            issues.append(f"{label}_SOLVE_REPODATA_IDENTITY_INVALID:{filename}")
            continue
        if link.get("build_number") is not None and record.get("build_number") != link["build_number"]:
            issues.append(f"{label}_SOLVE_BUILD_NUMBER_MISMATCH:{filename}")
        for field in ("depends", "constrains"):
            if field in link:
                link_value = link.get(field)
                source_value = record.get(field, [])
                if (not isinstance(link_value, list) or not isinstance(source_value, list) or
                        sorted(link_value) != sorted(source_value)):
                    issues.append(f"{label}_SOLVE_METADATA_MISMATCH:{filename}:{field}")
        for field, expected_value in (("sha256", digest), ("md5", record.get("md5"))):
            if field in link and str(link[field]).lower() != str(expected_value or "").lower():
                issues.append(f"{label}_SOLVE_METADATA_MISMATCH:{filename}:{field}")
        for field in ("fn", "filename"):
            if field in link and link[field] != filename:
                issues.append(f"{label}_SOLVE_METADATA_MISMATCH:{filename}:{field}")
        expected_url = f"{expected_channel.rstrip('/')}/{subdir}/{filename}"
        if link.get("url") and link["url"] != expected_url:
            issues.append(f"{label}_SOLVE_METADATA_MISMATCH:{filename}:url")
        identities.append((name, version, build, subdir, filename, digest.lower()))
    if consumed_fetches != set(range(len(fetches))):
        issues.append(f"{label}_SOLVE_FETCH_UNCONSUMED:{len(set(range(len(fetches)))-consumed_fetches)}")
    if len(identities) != len(set(identities)):
        issues.append(f"{label}_SOLVE_LINK_DUPLICATE")
    return identities, issues


def validate_solver_evidence(bundle, evidence):
    issues = []

    def read_json(path, code):
        try:
            with open(path, encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            issues.append(f"{code}:{exc}")
            return None

    online = read_json(os.path.join(evidence, "conda-solve.json"), "ONLINE_SOLVE_EVIDENCE_INVALID")
    enriched_online = read_json(os.path.join(evidence, "conda-upstream-link-records.json"),
                                "ONLINE_ENRICHED_LINK_EVIDENCE_INVALID")
    offline = read_json(os.path.join(evidence, "conda-offline-solve.json"), "OFFLINE_SOLVE_EVIDENCE_INVALID")
    offline_provenance = read_json(os.path.join(evidence, "conda-offline-repodata-provenance.json"),
                                   "OFFLINE_REPODATA_PROVENANCE_INVALID")
    cache_root_record = read_json(os.path.join(evidence, "conda-solver-cache-root.json"),
                                  "CONDA_SOLVER_CACHE_ROOT_INVALID")
    if (not all(isinstance(item, dict) for item in (online, offline, offline_provenance, cache_root_record)) or
            not isinstance(enriched_online, list)):
        return issues

    online_actions = online.get("actions", {})
    link_rows = online_actions.get("LINK", []) if isinstance(online_actions, dict) else []
    channels = {row.get("base_url") for row in link_rows if isinstance(row, dict)}
    if len(channels) != 1 or not isinstance(next(iter(channels), None), str):
        issues.append("ONLINE_SOLVE_CHANNEL_NOT_UNIQUE")
        return issues
    online_channel = next(iter(channels))
    online_repodata = {}
    online_bases = {}
    for subdir in ("linux-64", "noarch"):
        filename = f"upstream-repodata-{subdir}-after.json"
        snapshot_path = os.path.join(evidence, "work", filename)
        sidecar_path = snapshot_path + ".provenance.json"
        sidecar = read_json(sidecar_path, f"UPSTREAM_REPODATA_SIDECAR_INVALID:{subdir}")
        snapshot = read_json(snapshot_path, f"UPSTREAM_REPODATA_SNAPSHOT_INVALID:{subdir}")
        expected_url = f"{online_channel.rstrip('/')}/{subdir}/repodata.json"
        if not isinstance(sidecar, dict) or not isinstance(snapshot, dict):
            continue
        digest = sha256(snapshot_path)
        size = os.path.getsize(snapshot_path)
        if (sidecar.get("snapshot_id") != "after" or sidecar.get("subdir") != subdir or
                sidecar.get("evidence_file") != filename or sidecar.get("url") != expected_url or
                sidecar.get("sha256") != digest):
            issues.append(f"UPSTREAM_REPODATA_SNAPSHOT_PROVENANCE_MISMATCH:{subdir}")
        online_repodata[subdir] = snapshot
        online_bases[subdir] = online_channel
        info = snapshot.get("info", {})
        if not isinstance(info, dict) or info.get("subdir") not in (None, subdir):
            issues.append(f"UPSTREAM_REPODATA_SUBDIR_MISMATCH:{subdir}")
        if not all(isinstance(snapshot.get(key), dict) for key in ("packages", "packages.conda")):
            issues.append(f"UPSTREAM_REPODATA_SECTIONS_INVALID:{subdir}")
    online_ids, online_issues = solver_identity_rows(online, online_repodata, online_bases, "ONLINE")
    issues.extend(online_issues)

    def solver_key(row):
        subdir = row.get("subdir") or row.get("platform")
        build = row.get("build") or row.get("build_string")
        return subdir, row.get("name"), row.get("version"), build

    raw_by_key = {}
    if not isinstance(link_rows, list):
        issues.append("ONLINE_SOLVE_LINKS_INVALID")
        link_rows = []
    for index, row in enumerate(link_rows):
        if not isinstance(row, dict):
            issues.append(f"ONLINE_SOLVE_LINK_ROW_INVALID:{index}")
            continue
        key = solver_key(row)
        if key in raw_by_key:
            issues.append(f"ONLINE_SOLVE_LINK_IDENTITY_DUPLICATE:{key}")
        raw_by_key[key] = row
    enriched_by_key = {}
    for index, row in enumerate(enriched_online):
        if not isinstance(row, dict):
            issues.append(f"ONLINE_ENRICHED_LINK_ROW_INVALID:{index}")
            continue
        key = solver_key(row)
        if key in enriched_by_key:
            issues.append(f"ONLINE_ENRICHED_LINK_IDENTITY_DUPLICATE:{key}")
        enriched_by_key[key] = row
    if set(raw_by_key) != set(enriched_by_key):
        issues.append("ONLINE_RAW_ENRICHED_LINK_IDENTITY_SET_MISMATCH")
    identities_by_key = {}
    for name, version, build, subdir, filename, digest in online_ids:
        key = (subdir, name, version, build)
        if key in identities_by_key:
            issues.append(f"ONLINE_RESOLVED_IDENTITY_DUPLICATE:{key}")
        identities_by_key[key] = (name, version, build, subdir, filename, digest)
    for key in sorted(set(raw_by_key) & set(enriched_by_key), key=str):
        raw, enriched = raw_by_key[key], enriched_by_key[key]
        for field in ("base_url", "channel", "dist_name", "name", "version", "build", "build_string",
                      "build_number", "platform", "subdir", "depends", "constrains", "sha256", "md5",
                      "fn", "filename", "url"):
            if field in raw and enriched.get(field) != raw[field]:
                issues.append(f"ONLINE_RAW_ENRICHED_FIELD_MISMATCH:{key}:{field}")
        identity = identities_by_key.get(key)
        artifact = enriched.get("pma_artifact")
        if identity is None or not isinstance(artifact, dict):
            issues.append(f"ONLINE_ENRICHED_ARTIFACT_MISSING:{key}")
        else:
            name, version, build, subdir, filename, digest = identity
            expected_artifact = (name, version, build, subdir, filename, digest)
            observed_artifact = (artifact.get("name"), artifact.get("version"), artifact.get("build"),
                                 artifact.get("subdir"), artifact.get("filename"),
                                 str(artifact.get("sha256", "")).lower())
            if observed_artifact != expected_artifact:
                issues.append(f"ONLINE_ENRICHED_ARTIFACT_MISMATCH:{key}")
            section = "packages.conda" if filename.endswith(".conda") else "packages"
            source_record = online_repodata.get(subdir, {}).get(section, {}).get(filename)
            if enriched.get("pma_upstream_repodata_record") != source_record:
                issues.append(f"ONLINE_ENRICHED_REPODATA_RECORD_MISMATCH:{key}")
            expected_upstream = enriched.get("pma_upstream_repodata")
            if not isinstance(expected_upstream, dict):
                issues.append(f"ONLINE_ENRICHED_REPODATA_PROVENANCE_MISSING:{key}")

    local_repodata = {}
    local_channel = os.path.join(bundle, "conda")
    local_channel_url = Path(local_channel).resolve().as_uri()
    for subdir in ("linux-64", "noarch"):
        snapshot = read_json(os.path.join(local_channel, subdir, "repodata.json"),
                             f"BUNDLE_REPODATA_INVALID:{subdir}")
        provenance = offline_provenance.get(subdir)
        path = os.path.join(local_channel, subdir, "repodata.json")
        if not isinstance(snapshot, dict) or not isinstance(provenance, dict):
            issues.append(f"OFFLINE_REPODATA_EVIDENCE_MISSING:{subdir}")
            continue
        expected_url = f"{local_channel_url}/{subdir}"
        if (provenance.get("url") != expected_url or provenance.get("sha256") != sha256(path) or
                provenance.get("size") != os.path.getsize(path)):
            issues.append(f"OFFLINE_REPODATA_PROVENANCE_MISMATCH:{subdir}")
        local_repodata[subdir] = snapshot

    cache_path = cache_root_record.get("cache_root")
    try:
        cache_root = os.path.realpath(cache_path)
        workspace_root = os.path.realpath(os.path.dirname(evidence))
        if os.path.commonpath((workspace_root, cache_root)) != workspace_root:
            raise ValueError("cache root is outside the external workspace")
    except (TypeError, ValueError, OSError) as exc:
        issues.append(f"CONDA_SOLVER_CACHE_PATH_INVALID:{exc}")
        cache_root = ""

    if cache_root:
        for subdir in ("linux-64", "noarch"):
            for label, base, snapshot in (("ONLINE", online_channel, online_repodata.get(subdir)),
                                          ("OFFLINE", local_channel_url, local_repodata.get(subdir))):
                if not isinstance(snapshot, dict):
                    continue
                expected_url = f"{base.rstrip('/')}/{subdir}"
                matching = []
                for info_path in Path(cache_root, "cache").glob("*.info.json"):
                    record = read_json(str(info_path), f"CONDA_CACHE_INFO_INVALID:{info_path.name}")
                    if isinstance(record, dict) and record.get("url") == expected_url:
                        matching.append((info_path, record))
                if len(matching) != 1:
                    issues.append(f"CONDA_SOLVER_CACHE_ENTRY_NOT_UNIQUE:{label}:{subdir}:{len(matching)}")
                    continue
                info_path, cache_info = matching[0]
                cache_json = info_path.with_name(info_path.name.removesuffix(".info.json") + ".json")
                expected_digest = sha256(os.path.join(evidence, "work", f"upstream-repodata-{subdir}-after.json")) if label == "ONLINE" else sha256(os.path.join(local_channel, subdir, "repodata.json"))
                expected_size = (os.path.getsize(os.path.join(evidence, "work", f"upstream-repodata-{subdir}-after.json"))
                                 if label == "ONLINE" else os.path.getsize(os.path.join(local_channel, subdir, "repodata.json")))
                if (not cache_json.is_file() or cache_info.get("size") != expected_size or
                        cache_json.stat().st_size != expected_size or sha256(cache_json) != expected_digest):
                    issues.append(f"CONDA_SOLVER_CACHE_BYTES_MISMATCH:{label}:{subdir}")
                    continue
                if label == "OFFLINE":
                    provenance = offline_provenance.get(subdir, {})
                    if (provenance.get("cache_file") != cache_json.name or
                            provenance.get("sha256") != expected_digest or
                            provenance.get("size") != expected_size):
                        issues.append(f"OFFLINE_CACHE_PROVENANCE_MISMATCH:{subdir}")
                else:
                    subdir_links = [row for row in enriched_online if isinstance(row, dict) and
                                    (row.get("subdir") or row.get("platform")) == subdir]
                    for row in subdir_links:
                        upstream = row.get("pma_upstream_repodata", {})
                        solver_cache = upstream.get("solver_cache", {}) if isinstance(upstream, dict) else {}
                        if not isinstance(solver_cache, dict):
                            solver_cache = {}
                        if not isinstance(upstream, dict):
                            issues.append(f"ONLINE_REPODATA_PROVENANCE_MISSING:{subdir}")
                            break
                        if (upstream.get("url") != f"{online_channel.rstrip('/')}/{subdir}/repodata.json" or
                                upstream.get("sha256") != expected_digest or
                                upstream.get("evidence_file") != f"upstream-repodata-{subdir}-after.json" or
                                solver_cache.get("url") != expected_url or
                                solver_cache.get("cache_file") != cache_json.name or
                                solver_cache.get("sha256") != expected_digest or
                                solver_cache.get("size") != expected_size):
                            issues.append(f"ONLINE_CACHE_PROVENANCE_MISMATCH:{subdir}")
                            break

    offline_ids, offline_issues = solver_identity_rows(
        offline, local_repodata, {subdir: local_channel_url for subdir in ("linux-64", "noarch")}, "OFFLINE")
    issues.extend(offline_issues)
    lock_ids = []
    try:
        with open(os.path.join(bundle, "conda-explicit-linux-64.lock"), encoding="utf-8") as handle:
            for line in handle:
                if not line.strip() or line.lstrip().startswith("#"):
                    continue
                fields = line.rstrip("\n").split("\t")
                if len(fields) != 6:
                    issues.append("CONDA_LOCK_ROW_INVALID_IN_EVIDENCE")
                    continue
                subdir, name, version, build, filename, digest = fields
                lock_ids.append((name, version, build, subdir, filename, digest.lower()))
    except OSError as exc:
        issues.append(f"CONDA_LOCK_EVIDENCE_READ_FAILED:{exc}")
    if any(row[4].endswith(".conda") for row in lock_ids):
        extractor_path = os.path.join(evidence, "conda-extractor-provenance.json")
        extractor = read_json(extractor_path, "CONDA_EXTRACTOR_PROVENANCE_INVALID")
        expected_versions = {"conda-package-handling": "2.4.0",
                             "conda-package-streaming": "0.11.0", "zstandard": "0.23.0"}
        if isinstance(extractor, dict):
            base_prefix = os.path.realpath(extractor.get("base_prefix", ""))
            if (not extractor.get("python_isolated") or
                    extractor.get("extract_api") != "conda_package_handling.api.extract" or
                    not os.path.isabs(extractor.get("base_prefix", "")) or
                    not os.path.isdir(os.path.join(base_prefix, "conda-meta"))):
                issues.append("CONDA_EXTRACTOR_PROVENANCE_BOUNDARY_INVALID")
            package_records = extractor.get("packages")
            if not isinstance(package_records, dict):
                issues.append("CONDA_EXTRACTOR_PACKAGE_RECORDS_INVALID")
                package_records = {}
            for package, expected_version in expected_versions.items():
                record = package_records.get(package)
                if not isinstance(record, dict):
                    issues.append(f"CONDA_EXTRACTOR_PACKAGE_PROVENANCE_MISSING:{package}")
                    continue
                if record.get("version") != expected_version:
                    issues.append(f"CONDA_EXTRACTOR_VERSION_NOT_APPROVED:{package}")
                if record.get("integrity_basis") != "conda-meta paths_data sha256_in_prefix":
                    issues.append(f"CONDA_EXTRACTOR_INTEGRITY_BASIS_INVALID:{package}")
                record_file = os.path.join(base_prefix, "conda-meta", record.get("record_file", ""))
                if (not os.path.isfile(record_file) or sha256(record_file) != record.get("record_sha256")):
                    issues.append(f"CONDA_EXTRACTOR_CONDA_META_RECORD_MISMATCH:{package}")
                files = record.get("installed_module_files")
                if not isinstance(files, list) or not files:
                    issues.append(f"CONDA_EXTRACTOR_MODULE_FILE_EVIDENCE_MISSING:{package}")
                    continue
                for module_file in files:
                    if not isinstance(module_file, dict):
                        issues.append(f"CONDA_EXTRACTOR_MODULE_FILE_ROW_INVALID:{package}")
                        continue
                    relative = module_file.get("path", "")
                    path = os.path.realpath(os.path.join(base_prefix, relative))
                    if (not relative or os.path.isabs(relative) or ".." in relative.split("/") or
                            os.path.commonpath((base_prefix, path)) != base_prefix or
                            not os.path.isfile(path) or sha256(path) != module_file.get("sha256")):
                        issues.append(f"CONDA_EXTRACTOR_INSTALLED_FILE_MISMATCH:{package}:{relative}")
            manifest = read_json(os.path.join(bundle, "bundle-manifest.json"),
                                 "BUNDLE_MANIFEST_EXTRACTOR_REFERENCE_INVALID")
            if (isinstance(manifest, dict) and manifest.get("conda_extractor_provenance_sha256") !=
                    sha256(extractor_path)):
                issues.append("CONDA_EXTRACTOR_PROVENANCE_MANIFEST_HASH_MISMATCH")
    provenance_path = os.path.join(evidence, "conda-offline-repodata-provenance.json")
    manifest = read_json(os.path.join(bundle, "bundle-manifest.json"),
                         "BUNDLE_MANIFEST_OFFLINE_REFERENCE_INVALID")
    if (isinstance(manifest, dict) and manifest.get("conda_offline_repodata_provenance_sha256") !=
            sha256(provenance_path)):
        issues.append("OFFLINE_REPODATA_PROVENANCE_MANIFEST_HASH_MISMATCH")
    for label, observed in (("ONLINE", online_ids), ("OFFLINE", offline_ids)):
        if sorted(observed) != sorted(lock_ids):
            issues.append(f"{label}_SOLVER_LOCK_CLOSURE_MISMATCH")
    if sorted(online_ids) != sorted(offline_ids):
        issues.append("ONLINE_OFFLINE_SOLVER_CLOSURE_MISMATCH")
    return issues


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle")
    parser.add_argument("--evidence-dir", required=True)
    args = parser.parse_args()
    bundle = os.path.abspath(args.bundle)
    evidence = os.path.abspath(args.evidence_dir)
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
            conda_abi = report.get("conda_abi_audit", {})
            if not isinstance(conda_abi, dict):
                check(False, "CONDA_ABI_AUDIT_INVALID")
            else:
                check(conda_abi.get("scope") == "static-elf-compatibility-audit",
                      "CONDA_ABI_SCOPE_MISSING_OR_INVALID")
                check(conda_abi.get("runtime_linkability_verified") is False,
                      "CONDA_RUNTIME_LINKABILITY_CLAIM_INVALID")
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
                if relative in artifacts:
                    issues.append(f"ARTIFACT_ROW_DUPLICATE:{relative}")
                artifacts[relative] = digest.lower()
                path = os.path.join(bundle, relative)
                if not os.path.isfile(path):
                    issues.append(f"MISSING_OR_INVALID_ARTIFACT:{relative}")
                elif sha256(path) != digest.lower():
                    issues.append(f"ARTIFACT_HASH_MISMATCH:{relative}")
    except OSError as exc:
        issues.append(f"ARTIFACT_INVENTORY_INVALID:{exc}")
    observed_files = set()
    try:
        for root, directories, filenames in os.walk(bundle, followlinks=False):
            for name in list(directories):
                path = os.path.join(root, name)
                if os.path.islink(path):
                    issues.append(f"BUNDLE_SYMLINK_UNSUPPORTED:{os.path.relpath(path, bundle)}")
                    directories.remove(name)
            for name in filenames:
                path = os.path.join(root, name)
                relative = os.path.relpath(path, bundle).replace(os.sep, "/")
                if relative in {"artifacts.sha256", "bundle-manifest.json"}:
                    continue
                if os.path.islink(path) or not os.path.isfile(path):
                    issues.append(f"BUNDLE_NONREGULAR_FILE:{relative}")
                observed_files.add(relative)
    except OSError as exc:
        issues.append(f"BUNDLE_WALK_FAILED:{exc}")
    if observed_files != set(artifacts):
        for relative in sorted(observed_files - set(artifacts)):
            issues.append(f"BUNDLE_FILE_NOT_IN_INVENTORY:{relative}")
        for relative in sorted(set(artifacts) - observed_files):
            issues.append(f"INVENTORY_FILE_MISSING_FROM_BUNDLE:{relative}")
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
            elif (not isinstance(parsed_repodata.get("packages"), dict) or
                  not isinstance(parsed_repodata.get("packages.conda"), dict)):
                issues.append(f"REPODATA_PACKAGES_INVALID:{relative}")
                repodata_by_subdir[subdir] = parsed_repodata
            else:
                repodata_by_subdir[subdir] = parsed_repodata
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            issues.append(f"REPODATA_INVALID:{relative}:{exc}")

    conda_packages = {}
    repodata_dist_keys = {}
    expected_repodata_keys = set()
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
                if filename.endswith(".tar.bz2"):
                    package_section = "packages"
                elif filename.endswith(".conda"):
                    package_section = "packages.conda"
                else:
                    package_section = None
                    issues.append(f"CONDA_PACKAGE_FORMAT_UNSUPPORTED:{filename}")
                if package_section:
                    expected_repodata_keys.add((subdir, package_section, filename))
                if artifacts.get(relative) != digest.lower():
                    issues.append(f"CONDA_ARTIFACT_NOT_IN_INVENTORY:{relative}")
                path = os.path.join(bundle, relative)
                if not os.path.isfile(path):
                    issues.append(f"MISSING_CONDA_ARTIFACT:{name}={version}={build}")
                elif sha256(path) != digest.lower():
                    issues.append(f"CONDA_ARTIFACT_HASH_MISMATCH:{relative}")
                package_record = (repodata_by_subdir.get(subdir, {}).get(package_section, {}).get(filename)
                                  if package_section else None)
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
                    artifact_path = os.path.join(bundle, relative)
                    if package_record.get("size") is not None and package_record["size"] != os.path.getsize(artifact_path):
                        issues.append(f"CONDA_REPODATA_SIZE_MISMATCH:{relative}")
                    if filename.endswith(".conda"):
                        for issue in conda_container_issues(artifact_path, name, version, build):
                            issues.append(f"{issue}:{relative}")
    except OSError as exc:
        issues.append(f"CONDA_LOCK_INVALID:{exc}")
    observed_repodata_keys = set()
    for subdir in ("linux-64", "noarch"):
        parsed = repodata_by_subdir.get(subdir, {})
        for section in ("packages", "packages.conda"):
            records = parsed.get(section, {}) if isinstance(parsed, dict) else {}
            if not isinstance(records, dict):
                continue
            expected_suffix = ".tar.bz2" if section == "packages" else ".conda"
            for filename, record in records.items():
                observed_repodata_keys.add((subdir, section, filename))
                if not filename.endswith(expected_suffix):
                    issues.append(f"REPODATA_FILENAME_SECTION_MISMATCH:{subdir}/{section}/{filename}")
                if not isinstance(record, dict):
                    issues.append(f"REPODATA_RECORD_INVALID:{subdir}/{section}/{filename}")
    if observed_repodata_keys != expected_repodata_keys:
        for key in sorted(observed_repodata_keys - expected_repodata_keys):
            issues.append(f"REPODATA_RECORD_NOT_IN_LOCK:{'/'.join(key)}")
        for key in sorted(expected_repodata_keys - observed_repodata_keys):
            issues.append(f"LOCK_RECORD_NOT_IN_REPODATA:{'/'.join(key)}")
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
                if requirement.extras:
                    issues.append(
                        f"UNSUPPORTED_PIP_EXTRAS:{key}:{raw_requirement}:"
                        f"{','.join(sorted(requirement.extras))}"
                    )
                    continue
                dependency = normalized(requirement.name)
                if dependency not in installed:
                    issues.append(f"UNRESOLVED_WHEEL_DEPENDENCY:{key}:{raw_requirement}")
                elif not requirement.specifier.contains(Version(installed[dependency]), prereleases=True):
                    issues.append(f"WHEEL_DEPENDENCY_VERSION_MISMATCH:{key}:{raw_requirement}:{installed[dependency]}")
            except (ValueError, TypeError) as exc:
                issues.append(f"WHEEL_DEPENDENCY_INVALID:{key}:{raw_requirement}:{exc}")

    try:
        issues.extend(validate_solver_evidence(bundle, evidence))
    except (AssertionError, KeyError, OSError, TypeError, ValueError) as exc:
        issues.append(f"SOLVER_EVIDENCE_VALIDATION_ERROR:{exc}")

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
