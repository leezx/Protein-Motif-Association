"""Small contract checks for the external HINT bundle builder."""
import importlib.util
import hashlib
import json
import os
import re
import subprocess
import tarfile
import tempfile
import unittest
import zipfile
from io import BytesIO
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/04b_footprint/build_hint_bundle.py"
SPEC = importlib.util.spec_from_file_location("build_hint_bundle", SCRIPT)
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)
PREP_SCRIPT = ROOT / "scripts/04b_footprint/prepare_hint_argos_toolchain.py"
PREP_SPEC = importlib.util.spec_from_file_location("prepare_hint_argos_toolchain", PREP_SCRIPT)
PREP = importlib.util.module_from_spec(PREP_SPEC)
PREP_SPEC.loader.exec_module(PREP)
DATA_ROOT_SPEC = importlib.util.spec_from_file_location(
    "validate_argos_data_root", ROOT / "scripts/04b_footprint/validate_argos_data_root.py")
DATA_ROOT_VALIDATOR = importlib.util.module_from_spec(DATA_ROOT_SPEC)
DATA_ROOT_SPEC.loader.exec_module(DATA_ROOT_VALIDATOR)


class HintBundleBuildContract(unittest.TestCase):
    def _write_toolchain_wheel(self, path: Path, *, requires_python=">=3.11", declared_tag="py3-none-any",
                               root_is_purelib="true", payload=b"python source"):
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("example/__init__.py", payload)
            archive.writestr("example-1.2.3.dist-info/METADATA",
                             f"Name: example\nVersion: 1.2.3\nRequires-Python: {requires_python}\n\n")
            archive.writestr("example-1.2.3.dist-info/WHEEL",
                             f"Wheel-Version: 1.0\nRoot-Is-Purelib: {root_is_purelib}\nTag: {declared_tag}\n")

    def test_toolchain_wheel_requires_compatible_python(self):
        with tempfile.TemporaryDirectory() as tmp:
            wheel = Path(tmp) / "example-1.2.3-py3-none-any.whl"
            self._write_toolchain_wheel(wheel, requires_python="<3.11.17")
            with self.assertRaisesRegex(RuntimeError, "REQUIRES_PYTHON_MISMATCH"):
                PREP.validate_py3_none_any_wheel(wheel, "3.11.17")

    def test_toolchain_wheel_declared_tag_must_match_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            wheel = Path(tmp) / "example-1.2.3-py3-none-any.whl"
            self._write_toolchain_wheel(wheel, declared_tag="cp311-cp311-manylinux_2_17_x86_64")
            with self.assertRaisesRegex(RuntimeError, "WHEEL_TAG_MISMATCH"):
                PREP.validate_py3_none_any_wheel(wheel, "3.11.17")

    def test_toolchain_py3_none_any_wheel_rejects_elf_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            wheel = Path(tmp) / "example-1.2.3-py3-none-any.whl"
            self._write_toolchain_wheel(wheel, payload=bytes((0x7f,)) + b"ELFfixture")
            with self.assertRaisesRegex(RuntimeError, "PURE_WHEEL_HAS_NATIVE_PAYLOAD"):
                PREP.validate_py3_none_any_wheel(wheel, "3.11.17")

    def test_argos_data_root_must_match_repository_configured_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            configured = root / "configured-data" / "PMA"
            expected = configured / "atac_footprint"
            wrong = root / "lookalike" / "atac_footprint"
            for candidate in (expected, wrong):
                (candidate / "raw").mkdir(parents=True)
                (candidate / "processed" / "round1").mkdir(parents=True)
            self.assertEqual(DATA_ROOT_VALIDATOR.validate_data_root(expected, configured), expected.resolve())
            with self.assertRaisesRegex(ValueError, "DOES_NOT_MATCH_REPOSITORY_CONFIG"):
                DATA_ROOT_VALIDATOR.validate_data_root(wrong, configured)

    def test_wrapper_records_pmafp_integrity_when_toolchain_preparation_fails(self):
        wrapper = ROOT / "scripts/04b_footprint/run_hint_bundle_builder_argos.sh"
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as prefix_tmp:
            root = Path(tmp)
            data = root / "data" / "2.PROJECTS" / "PMA" / "atac_footprint"
            (data / "raw").mkdir(parents=True)
            (data / "processed" / "round1").mkdir(parents=True)
            workspace = root / "external-work"
            bundle = workspace / "bundle"
            evidence = workspace / "evidence"
            prefix = Path(prefix_tmp) / "software" / "envs" / "pmafp"
            (prefix / "bin").mkdir(parents=True)
            python = prefix / "bin" / "python"
            python.write_text("#!/bin/sh\nif [ \"$1\" = \"-m\" ] && [ \"$2\" = \"pip\" ]; then\n  echo fake==1.0\n  exit 0\nfi\necho simulated-download-failure >&2\nexit 17\n")
            python.chmod(0o755)
            conda = root / "conda"
            conda.write_text("#!/bin/sh\nif [ \"$1\" = \"env\" ]; then\n  printf '{\"envs\": []}\\n'\nelif [ \"$1\" = \"list\" ]; then\n  printf '@EXPLICIT\\n'\nelse\n  exit 2\nfi\n")
            conda.chmod(0o755)
            env = dict(os.environ, BIO_DATA=str(root / "data"), BIO_SOFTWARES=str(root / "software"),
                       BIOWORKSPACE_ROOT=str(root), PMA_HINT_SOURCE_PREFIX=str(prefix),
                       PMA_HINT_CONDA=str(conda))
            result = subprocess.run(["bash", str(wrapper), str(data), str(workspace), str(bundle),
                                     str(evidence), "https://conda.example.org/conda-forge"],
                                    capture_output=True, text=True, env=env)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("simulated-download-failure", result.stderr)
            self.assertTrue((evidence / "pmafp-conda-after.txt").is_file())
            self.assertTrue((evidence / "pmafp-pip-after.txt").is_file())
            integrity = json.loads((evidence / "pmafp-integrity.json").read_text(encoding="utf-8"))
            self.assertEqual(integrity["status"], "PMAFP_INTEGRITY_OK")

    def test_solver_evidence_removes_url_credentials_and_queries(self):
        payload = {"url": "https://user:secret@example.org/linux-64/pkg.tar.bz2?token=hidden",
                   "nested": ["https://example.org/noarch/pkg.tar.bz2?sig=hidden"]}
        cleaned = BUILDER.sanitize_evidence(payload)
        self.assertEqual(cleaned["url"], "https://example.org/linux-64/pkg.tar.bz2")
        self.assertEqual(cleaned["nested"][0], "https://example.org/noarch/pkg.tar.bz2")
        self.assertNotIn("secret", json.dumps(cleaned))
        self.assertNotIn("hidden", json.dumps(cleaned))

    def test_argos_channel_credentials_are_rejected_before_solver_or_evidence_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            with mock.patch.dict(BUILDER.os.environ, {
                "PMA_HINT_BUILDER_MODE": "argos-native",
                "PMA_HINT_ARGOS_CONDA_CHANNEL": "https://user:secret@example.org/channel?token=hidden",
            }), mock.patch.object(BUILDER, "conda_dry_run") as solve, \
                 mock.patch.object(BUILDER, "fetch_repodata_snapshot") as repodata:
                with self.assertRaisesRegex(RuntimeError, "CREDENTIALS_OR_QUERY"):
                    BUILDER.load_solver_plan("/mock/conda", work)
            solve.assert_not_called()
            repodata.assert_not_called()
            self.assertEqual(list(work.iterdir()), [])

    def test_solver_plan_evidence_redacts_tokens_across_full_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            output = json.dumps({"actions": {"LINK": [{
                "name": "python", "version": "3.11.9", "build": "mock_0",
                "fn": "python-3.11.9-mock_0.tar.bz2", "subdir": "linux-64",
                "sha256": "a" * 64,
                "url": "https://example.org/linux-64/python-3.11.9-mock_0.tar.bz2?token=secret"
            }]}})
            snapshot_record = {"name": "python", "version": "3.11.9", "build": "mock_0",
                              "sha256": "a" * 64, "depends": [], "constrains": []}
            snapshot = {"url": "https://example.org/linux-64/repodata.json", "sha256": "b" * 64,
                        "packages": {"python-3.11.9-mock_0.tar.bz2": snapshot_record}}
            with mock.patch.dict(BUILDER.os.environ, {
                "PMA_HINT_BUILDER_MODE": "argos-native",
                "PMA_HINT_ARGOS_CONDA_CHANNEL": "https://example.org/channel",
            }), mock.patch.object(BUILDER, "fetch_repodata_snapshot", return_value=snapshot), \
                 mock.patch.object(BUILDER, "conda_dry_run", return_value=output):
                BUILDER.load_solver_plan("/mock/conda", work)
            for path in work.rglob("*"):
                if path.is_file():
                    content = path.read_text(encoding="utf-8")
                    self.assertNotIn("secret", content)
                    self.assertNotIn("token=", content)

    def test_argos_repodata_records_hotfix_difference_with_frozen_evidence(self):
        record = {"subdir": "linux-64", "name": "python", "version": "3.11.9",
                  "build": "mock_0", "filename": "python-3.11.9-mock_0.tar.bz2",
                  "sha256": "a" * 64, "md5": "b" * 32, "size": 123,
                  "index_record": {"name": "python", "version": "3.11.9", "build": "mock_0",
                                   "depends": ["archive-hotfix >=1"]},
                  "source_record": {"name": "python", "version": "3.11.9", "build": "mock_0",
                                    "depends": ["upstream-dep >=2"], "constrains": []},
                  "source_repodata": {"url": "https://example.org/linux-64/repodata.json",
                                      "sha256": "c" * 64},
                  "solver_record": {"depends": ["upstream-dep >=2"], "constrains": []}}
        result = BUILDER.build_local_repodata([record], "linux-64")
        self.assertEqual(result["packages"][record["filename"]]["depends"], ["upstream-dep >=2"])
        self.assertEqual(record["dependency_metadata_diff"]["depends"], {
            "archive_index": ["archive-hotfix >=1"], "upstream_repodata": ["upstream-dep >=2"]
        })

    def test_argos_repodata_rejects_archive_dependency_difference_without_provenance(self):
        record = {"subdir": "linux-64", "name": "python", "version": "3.11.9",
                  "build": "mock_0", "filename": "python-3.11.9-mock_0.tar.bz2",
                  "sha256": "a" * 64, "md5": "b" * 32, "size": 123,
                  "index_record": {"name": "python", "version": "3.11.9", "build": "mock_0",
                                   "depends": ["archive-dep >=1"]},
                  "source_record": {"name": "python", "version": "3.11.9", "build": "mock_0",
                                    "depends": ["solver-dep >=2"]}}
        with self.assertRaisesRegex(RuntimeError, "DIFF_WITHOUT_UPSTREAM_EVIDENCE"):
            BUILDER.build_local_repodata([record], "linux-64")

    def test_argos_local_repodata_requires_frozen_solver_dependencies(self):
        record = {"subdir": "linux-64", "name": "python", "version": "3.11.9",
                  "build": "h955ad1f_0", "filename": "python-3.11.9-h955ad1f_0.tar.bz2",
                  "sha256": "a" * 64, "md5": "b" * 32, "size": 123,
                  "index_record": {"name": "python", "version": "3.11.9", "build": "h955ad1f_0",
                                   "depends": ["libc >=2.17"]},
                  "source_record": {"name": "python", "version": "3.11.9",
                                    "build_string": "h955ad1f_0", "depends": ["libc >=2.17"]}}
        with self.assertRaisesRegex(RuntimeError, "REPODATA_UPSTREAM_DEPENDS_MISSING"):
            BUILDER.build_local_repodata([{**record, "source_record": {"name": "python"}}], "linux-64")
        record["source_record"]["build"] = record["build"]
        result = BUILDER.build_local_repodata([record], "linux-64")
        pkg = result["packages"][record["filename"]]
        self.assertEqual(pkg["depends"], ["libc >=2.17"])
        self.assertEqual(pkg["sha256"], "a" * 64)
        self.assertEqual(pkg["md5"], "b" * 32)

    def test_glibc_version_max_is_numeric(self):
        self.assertEqual(BUILDER.version_max(["2.9", "2.23", "2.17"]), "2.23")

    def test_builder_refuses_non_linux_host(self):
        with mock.patch.object(BUILDER.platform, "system", return_value="Darwin"):
            with self.assertRaisesRegex(RuntimeError, "BUILDER_PLATFORM_MUST_BE_LINUX_X86_64"):
                BUILDER.require_builder()

    def test_builder_requires_digest_pinned_image(self):
        with mock.patch.object(BUILDER.platform, "system", return_value="Linux"), \
             mock.patch.object(BUILDER.platform, "machine", return_value="x86_64"), \
             mock.patch.object(BUILDER.sys, "version_info", (3, 11, 0)), \
             mock.patch.object(BUILDER.platform, "libc_ver", return_value=("glibc", "2.17")), \
             mock.patch.dict(BUILDER.os.environ, {"PMA_HINT_BUILDER_IMAGE": "mutable:latest"}):
            with self.assertRaisesRegex(RuntimeError, "MUST_BE_DIGEST_PINNED"):
                BUILDER.require_builder()

    def test_argos_conda_path_must_resolve_to_audited_executable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            expected = root / "bin" / "conda"
            expected.parent.mkdir()
            expected.write_text("mock")
            alias = root / "alias-conda"
            alias.symlink_to(expected)
            BUILDER.validate_audited_conda(str(alias), str(expected))
            other = root / "other-conda"
            other.write_text("other")
            with self.assertRaisesRegex(RuntimeError, "DOES_NOT_MATCH_AUDITED"):
                BUILDER.validate_audited_conda(str(other), str(expected))
            with self.assertRaisesRegex(RuntimeError, "AUDITED_CONDA_EXECUTABLE_REQUIRED"):
                BUILDER.require_audited_conda(str(expected), None)

    def test_rgt_pure_python_wheel_gets_explicit_no_elf_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            wheel = Path(tmp) / "RGT-1.0.2-py3-none-any.whl"
            with zipfile.ZipFile(wheel, "w") as archive:
                archive.writestr("rgt/__init__.py", "__version__ = '1.0.2'\n")
                archive.writestr("RGT-1.0.2.dist-info/METADATA", "Name: RGT\nVersion: 1.0.2\n")
            result = BUILDER.audit_rgt_wheel(wheel, "builder@sha256:" + "a" * 64,
                                             Path(tmp), BUILDER.RGT_SHA256, {}, set())
            self.assertEqual(result["auditwheel_policy"], "pure-python-no-ELF")
            self.assertEqual(result["native_dependencies"], [])

    def test_conda_package_format_must_match_validator_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            record = {"subdir": "linux-64", "fn": "python-3.11.0-0.conda",
                      "sha256": "a" * 64, "url": "https://example.org/linux-64/python-3.11.0-0.conda"}
            with mock.patch.object(BUILDER.urllib.request, "urlretrieve") as download:
                with self.assertRaisesRegex(RuntimeError, "UNSUPPORTED_CONDA_ARTIFACT"):
                    BUILDER.copy_conda_closure([record], Path(tmp))
            download.assert_not_called()

    def test_pip_lock_uses_canonical_distribution_name_and_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            wheel = Path(tmp) / "Some_Pkg-1.2.3-py3-none-any.whl"
            wheel.write_bytes(b"fixture-wheel")
            self.assertEqual(
                BUILDER.render_pip_lock([wheel]),
                f"some-pkg==1.2.3 --hash=sha256:{BUILDER.sha256(wheel)}\n",
            )

    def test_elf_contract_rejects_wrong_architecture_and_unresolved_needed(self):
        wrong_arch = BUILDER.check_elf_contract("AArch64", set(), {"libc.so.6"})
        self.assertTrue(any(item.startswith("ELF_MACHINE_UNSUPPORTED") for item in wrong_arch))
        missing = BUILDER.check_elf_contract(
            "Advanced Micro Devices X86-64", {"libc.so.6", "libmissing.so"}, {"libstdc++.so.6"}
        )
        self.assertEqual(missing, ["ELF_NEEDED_UNRESOLVED:libmissing.so"])

    def test_readelf_version_parser_separates_needs_and_definitions(self):
        output = """Version needs section '.gnu.version_r' contains 1 entry:
  Name: GLIBCXX_3.4.26
Version definition section '.gnu.version_d' contains 1 entry:
  Name: GLIBCXX_3.4.29
"""
        self.assertEqual(BUILDER.readelf_versions(output, "GLIBCXX", "needs"), ["3.4.26"])
        self.assertEqual(BUILDER.readelf_versions(output, "GLIBCXX", "definition"), ["3.4.29"])
        self.assertTrue(BUILDER.abi_provider_compatible(["3.4.26"], ["3.4.29"]))
        self.assertFalse(BUILDER.abi_provider_compatible(["3.4.30"], ["3.4.29"]))
        self.assertFalse(BUILDER.abi_provider_compatible(["1.3.8"], []))

    def _native_wheel(self, folder: Path, name: str) -> Path:
        wheel = folder / f"{name}-1.0-cp311-cp311-manylinux_2_17_x86_64.whl"
        with zipfile.ZipFile(wheel, "w") as archive:
            archive.writestr(f"{name}/extension.so", b"\x7fELFfixture")
        return wheel

    def _mock_native_readelf(self, args, *, capture):
        if "--file-header" in args:
            return "Machine: Advanced Micro Devices X86-64\n"
        if "--version-info" in args:
            return "Version needs section '.gnu.version_r' contains 1 entry:\n  Name: GLIBC_2.17\n  Name: GLIBCXX_3.4.35\n"
        if "--dynamic" in args:
            return "(NEEDED) Shared library: [libstdc++.so.6]\n"
        raise AssertionError(args)

    def test_native_wheel_audit_fails_when_glibcxx_exceeds_conda_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            wheel = self._native_wheel(folder, "nativepkg")
            conda_abi = {"package_library_names": ["libstdc++.so.6"],
                         "provided_glibcxx_versions": ["3.4.30"],
                         "provided_cxxabi_versions": ["1.3.13"]}
            with mock.patch.object(BUILDER.shutil, "which", side_effect=lambda name: f"/mock/{name}"), \
                 mock.patch.object(BUILDER, "run", side_effect=self._mock_native_readelf):
                with self.assertRaisesRegex(RuntimeError, "WHEEL_GLIBCXX_PROVIDER_INCOMPATIBLE"):
                    BUILDER.audit_pip_wheels([wheel], folder, conda_abi)

    def test_native_wheel_audit_fails_on_unresolved_dt_needed(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            wheel = self._native_wheel(folder, "nativepkg")
            conda_abi = {"package_library_names": ["libstdc++.so.6"],
                         "provided_glibcxx_versions": ["3.4.40"],
                         "provided_cxxabi_versions": ["1.3.20"]}

            def unresolved_readelf(args, *, capture):
                if "--file-header" in args:
                    return "Machine: Advanced Micro Devices X86-64\n"
                if "--version-info" in args:
                    return "Version needs section '.gnu.version_r' contains 1 entry:\n  Name: GLIBC_2.17\n"
                if "--dynamic" in args:
                    return "(NEEDED) Shared library: [libmissing.so]\n"
                raise AssertionError(args)

            with mock.patch.object(BUILDER.shutil, "which", side_effect=lambda name: f"/mock/{name}"), \
                 mock.patch.object(BUILDER, "run", side_effect=unresolved_readelf):
                with self.assertRaisesRegex(RuntimeError, "ELF_NEEDED_UNRESOLVED:libmissing.so"):
                    BUILDER.audit_pip_wheels([wheel], folder, conda_abi)

    def test_conda_solver_never_creates_its_target_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            prefix = Path(tmp) / "must-remain-absent"
            observed = []

            def fake_run(argv, *, capture, env=None):
                observed.extend(argv)
                self.assertIsNotNone(env)
                self.assertEqual(env.get("CONDA_PKGS_DIRS"), str((prefix.parent / "cache").resolve()))
                return "{}"

            with mock.patch.object(BUILDER, "run", side_effect=fake_run):
                cache = prefix.parent / "cache"
                self.assertEqual(BUILDER.conda_dry_run("conda", prefix, ["--offline"],
                                                        ("python=3.11",), package_cache=cache), "{}")
            self.assertIn("--dry-run", observed)
            self.assertFalse(prefix.exists())

            def violating_run(argv, *, capture, env=None):
                Path(argv[argv.index("-p") + 1]).mkdir()
                return "{}"

            with mock.patch.object(BUILDER, "run", side_effect=violating_run):
                with self.assertRaisesRegex(RuntimeError, "CONDA_DRY_RUN_CREATED_PREFIX"):
                    BUILDER.conda_dry_run("conda", prefix, [], ("python=3.11",))
            self.assertTrue(prefix.exists())

    def test_mock_bundle_build_helpers_pass_repository_validator(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "bundle"
            for subdir in ("linux-64", "noarch"):
                (bundle / "conda" / subdir).mkdir(parents=True)
            (bundle / "wheels").mkdir()
            (bundle / "reports").mkdir()
            conda_rows = [
                ("linux-64", "python", "3.11.9", "mock_0"),
                ("linux-64", "numpy", "1.26.4", "mock_0"),
                ("noarch", "setuptools", "80.9.0", "mock_0"),
                ("linux-64", "pip", "25.2", "mock_0"),
            ]
            repodata = {"linux-64": {"packages": {}, "packages.conda": {}},
                        "noarch": {"packages": {}, "packages.conda": {}}}
            lock_rows = []
            inventory_paths = []
            for subdir, name, version, build in conda_rows:
                filename = f"{name}-{version}-{build}.tar.bz2"
                archive_path = bundle / "conda" / subdir / filename
                with tarfile.open(archive_path, "w:bz2") as archive:
                    payload = json.dumps({"name": name, "version": version, "build": build}).encode()
                    info = tarfile.TarInfo("info/index.json")
                    info.size = len(payload)
                    archive.addfile(info, BytesIO(payload))
                digest = BUILDER.sha256(archive_path)
                repodata[subdir]["packages"][filename] = {
                    "name": name, "version": version, "build": build, "sha256": digest
                }
                lock_rows.append("\t".join((subdir, name, version, build, filename, digest)) + "\n")
                inventory_paths.append(archive_path)
            for subdir in ("linux-64", "noarch"):
                path = bundle / "conda" / subdir / "repodata.json"
                path.write_text(json.dumps(repodata[subdir]), encoding="utf-8")
                inventory_paths.append(path)
            conda_lock = bundle / "conda-explicit-linux-64.lock"
            conda_lock.write_text("".join(lock_rows), encoding="utf-8")
            inventory_paths.append(conda_lock)

            wheel = bundle / "wheels/RGT-1.0.2-py3-none-any.whl"
            with zipfile.ZipFile(wheel, "w") as archive:
                archive.writestr("RGT-1.0.2.dist-info/METADATA",
                                 "Name: RGT\nVersion: 1.0.2\nRequires-Python: >=3.11,<3.12\n\n")
                archive.writestr("RGT-1.0.2.dist-info/WHEEL",
                                 "Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n")
            pip_lock = bundle / "pip-requirements.lock"
            pip_lock.write_text(BUILDER.render_pip_lock([wheel]), encoding="utf-8")
            inventory_paths.extend((wheel, pip_lock))

            report = bundle / "reports/rgt-wheel-audit.json"
            report.write_text(json.dumps({
                "rgt_sdist_sha256": BUILDER.RGT_SHA256,
                "builder": "mock.example/pma@sha256:" + "a" * 64,
                "python_abi": "cp311", "glibc_symbol_max": "2.17",
                "auditwheel_policy": "pure-python-no-ELF", "native_dependencies": [],
                "rgt_wheel": wheel.name, "rgt_wheel_sha256": BUILDER.sha256(wheel),
            }), encoding="utf-8")
            inventory_paths.append(report)
            inventory = bundle / "artifacts.sha256"
            inventory.write_text("".join(
                f"{BUILDER.sha256(path)}  {path.relative_to(bundle).as_posix()}\n"
                for path in sorted(inventory_paths)
            ), encoding="utf-8")
            manifest = {
                "schema_version": 1, "target_platform": "linux-64", "python_abi": "cp311",
                "glibc_max": "2.17", "builder": "mock.example/pma@sha256:" + "a" * 64,
                "conda_version": "conda 25.3.1", "pip_version": "pip 25.2",
                "rgt_sdist_sha256": BUILDER.RGT_SHA256, "rgt_wheel": wheel.name,
                "rgt_wheel_sha256": BUILDER.sha256(wheel),
                "rgt_build_report": "reports/rgt-wheel-audit.json",
                "rgt_build_report_sha256": BUILDER.sha256(report),
                "conda_lock_sha256": BUILDER.sha256(conda_lock),
                "pip_lock_sha256": BUILDER.sha256(pip_lock),
                "artifacts_sha256": BUILDER.sha256(inventory),
            }
            (bundle / "bundle-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
            result = subprocess.run([BUILDER.sys.executable,
                                     str(ROOT / "scripts/04b_footprint/validate_hint_bundle.py"),
                                     str(bundle)], capture_output=True, text=True, env=env)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_dockerfile_pins_base_digest_and_tool_versions(self):
        text = (ROOT / "scripts/04b_footprint/Dockerfile.hint-builder").read_text()
        base = re.search(r"^FROM --platform=linux/amd64 (\S+)$", text, re.MULTILINE)
        self.assertIsNotNone(base)
        self.assertRegex(base.group(1), r"@sha256:[0-9a-f]{64}$")
        self.assertNotRegex(text, r"(?m)^ARG [A-Z_]+(?:IMAGE|RELEASE|SHA256)\b")
        for package in ("conda=25.3.1", "conda-index=0.12.1"):
            self.assertIn(package, text)
        lock = (ROOT / "scripts/04b_footprint/hint-builder-requirements.lock").read_text()
        for package in ("pip==25.2", "packaging==25.0", "setuptools==80.9.0",
                        "wheel==0.45.1", "auditwheel==6.0.0", "pyelftools==0.31"):
            self.assertIn(package, lock)
        for line in lock.splitlines():
            self.assertRegex(line, r"^\S+==\S+ --hash=sha256:[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
