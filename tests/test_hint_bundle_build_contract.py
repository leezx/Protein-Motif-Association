"""Small contract checks for the external HINT bundle builder."""
import importlib.util
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
import warnings
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
PROBE_SCRIPT = ROOT / "scripts/04b_footprint/probe_hint_argos_toolchain.py"
SITECUSTOMIZE_DIR = ROOT / "scripts/04b_footprint"
DATA_ROOT_SPEC = importlib.util.spec_from_file_location(
    "validate_argos_data_root", ROOT / "scripts/04b_footprint/validate_argos_data_root.py")
DATA_ROOT_VALIDATOR = importlib.util.module_from_spec(DATA_ROOT_SPEC)
DATA_ROOT_SPEC.loader.exec_module(DATA_ROOT_VALIDATOR)


class HintBundleBuildContract(unittest.TestCase):
    def _write_cache_pair(self, cache_root: Path, cache_key: str, url: str, payload: bytes):
        cache = cache_root / "cache"
        cache.mkdir(parents=True, exist_ok=True)
        (cache / f"{cache_key}.json").write_bytes(payload)
        (cache / f"{cache_key}.info.json").write_text(
            json.dumps({"url": url, "size": len(payload)}), encoding="utf-8")

    def _make_conda_archive_fixture(self, python: Path, path: Path, *, pkg=(), info=(), corrupt=()):
        spec = json.dumps({"pkg": list(pkg), "info": list(info), "corrupt": list(corrupt)})
        code = r'''import io, json, sys, tarfile, zipfile, zstandard
spec = json.loads(sys.argv[2])
def component(rows, corrupt=False):
    if corrupt:
        return b"invalid-zstd-stream"
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        for row in rows:
            member = tarfile.TarInfo(row["name"])
            kind = row.get("kind", "file")
            if kind == "file":
                body = row.get("data", "fixture").encode()
                member.size = len(body)
                archive.addfile(member, io.BytesIO(body))
            elif kind == "dir":
                member.type = tarfile.DIRTYPE
                archive.addfile(member)
            elif kind == "symlink":
                member.type = tarfile.SYMTYPE
                member.linkname = row["target"]
                archive.addfile(member)
            elif kind == "hardlink":
                member.type = tarfile.LNKTYPE
                member.linkname = row["target"]
                archive.addfile(member)
            else:
                raise ValueError(kind)
    return zstandard.ZstdCompressor(level=1).compress(buffer.getvalue())
dist = "pma-archive-fixture-1.0-0"
with zipfile.ZipFile(sys.argv[1], "w", compression=zipfile.ZIP_STORED) as archive:
    archive.writestr("metadata.json", '{"conda_pkg_format_version":2}')
    archive.writestr("info-" + dist + ".tar.zst", component(spec["info"]))
    archive.writestr("pkg-" + dist + ".tar.zst", component(spec["pkg"], bool(spec["corrupt"])))
'''
        subprocess.run([str(python), "-I", "-c", code, str(path), spec], check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    def _write_import_probe_fixture(self, root: Path, *, metadata_root: Path | None = None,
                                    simulate_pip_spec_side_effect: bool = False):
        metadata_root = metadata_root or root
        root.mkdir(parents=True, exist_ok=True)
        hack_source = """import importlib, sys
def add_shim():
    package = importlib.import_module('setuptools._distutils')
    core = importlib.import_module('setuptools._distutils.core')
    package.__name__ = 'distutils'
    sys.modules['distutils'] = package
    sys.modules['distutils.core'] = core
"""
        if simulate_pip_spec_side_effect:
            hack_source += """
class DistutilsMetaFinder:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'pip':
            sys.modules.pop('distutils', None)
            sys.modules.pop('distutils.core', None)
            try:
                sys.meta_path.remove(self)
            except ValueError:
                pass
        return None
DISTUTILS_FINDER = DistutilsMetaFinder()
_original_add_shim = add_shim
def add_shim():
    _original_add_shim()
    if DISTUTILS_FINDER not in sys.meta_path:
        sys.meta_path.insert(0, DISTUTILS_FINDER)
"""
        (root / "_distutils_hack.py").write_text(hack_source, encoding="utf-8")
        (root / "setuptools" / "_distutils").mkdir(parents=True)
        (root / "setuptools" / "_vendor").mkdir()
        (root / "setuptools" / "__init__.py").write_text("__version__ = '80.9.0'\n", encoding="utf-8")
        (root / "setuptools" / "_distutils" / "__init__.py").write_text("\n", encoding="utf-8")
        (root / "setuptools" / "_distutils" / "core.py").write_text("\n", encoding="utf-8")
        packages = {"pip": ("pip", "25.2"), "packaging": ("packaging", "25.0"),
                    "setuptools": ("setuptools", "80.9.0"), "wheel": ("wheel", "0.45.1"),
                    "auditwheel": ("auditwheel", "6.0.0"), "pyelftools": ("elftools", "0.31")}
        for dist, (module, version) in packages.items():
            if dist != "setuptools":
                (root / module).mkdir(exist_ok=True)
                (root / module / "__init__.py").write_text("\n", encoding="utf-8")
            info = metadata_root / f"{dist}-{version}.dist-info"
            info.mkdir(parents=True, exist_ok=True)
            (info / "METADATA").write_text(f"Name: {dist}\nVersion: {version}\n\n", encoding="utf-8")
            (info / "RECORD").write_text(f"{dist}-{version}.dist-info/METADATA,,\n", encoding="utf-8")

    def test_toolchain_probe_initializes_setuptools_before_pip_and_checks_origins(self):
        source = PROBE_SCRIPT.read_text(encoding="utf-8")
        self.assertLess(source.index('importlib.import_module("setuptools")'),
                        source.index('importlib.import_module("pip")'))
        self.assertIn("ARGOS_TOOLCHAIN_DISTUTILS_ORIGIN_MISMATCH", source)
        self.assertIn("ARGOS_TOOLCHAIN_METADATA_ORIGIN_MISMATCH", source)
        self.assertIn("ARGOS_TOOLCHAIN_MODULE_ORIGIN_MISMATCH", source)
        self.assertIn("sys.modules.items()", source)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "toolchain"
            self._write_import_probe_fixture(root, simulate_pip_spec_side_effect=True)
            env = PREP.toolchain_probe_environment(root, {"PATH": os.environ["PATH"]})
            self.assertEqual(env["SETUPTOOLS_USE_DISTUTILS"], "local")
            result = subprocess.run([sys.executable, str(PROBE_SCRIPT), str(root)], env=env,
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("setuptools", result.stdout)
            self.assertIn(str(root), result.stdout)
            self.assertIn("setuptools-80.9.0.dist-info/METADATA", result.stdout)

    def test_toolchain_probe_rejects_host_distribution_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "toolchain"
            host = Path(tmp) / "host-site"
            self._write_import_probe_fixture(root, metadata_root=host)
            env = PREP.toolchain_probe_environment(root, {"PATH": os.environ["PATH"]})
            env["PYTHONPATH"] = str(root) + os.pathsep + str(host)
            env["PMA_HINT_ALLOWED_WORKSPACE"] = str(Path(tmp))
            result = subprocess.run([sys.executable, str(PROBE_SCRIPT), str(root)],
                                    env=env, cwd=host, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("ARGOS_TOOLCHAIN_METADATA_ORIGIN_MISMATCH", result.stderr)

    def test_toolchain_probe_rejects_host_distutils_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "toolchain"
            host = Path(tmp) / "host-site"
            self._write_import_probe_fixture(root)
            (root / "_distutils_hack.py").write_text("def add_shim(): pass\n", encoding="utf-8")
            (host / "distutils").mkdir(parents=True)
            (host / "distutils" / "__init__.py").write_text("\n", encoding="utf-8")
            (host / "distutils" / "core.py").write_text("\n", encoding="utf-8")
            env = PREP.toolchain_probe_environment(root, {"PATH": os.environ["PATH"]})
            env["PYTHONPATH"] = str(root) + os.pathsep + str(host)
            env["PMA_HINT_ALLOWED_WORKSPACE"] = str(Path(tmp))
            result = subprocess.run([sys.executable, str(PROBE_SCRIPT), str(root)],
                                    env=env, cwd=host, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("ARGOS_TOOLCHAIN_DISTUTILS_ORIGIN_MISMATCH", result.stderr)

    def test_toolchain_probe_rejects_nonlocal_distutils_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "toolchain"
            self._write_import_probe_fixture(root)
            env = PREP.toolchain_probe_environment(root, {"PATH": os.environ["PATH"]})
            env["SETUPTOOLS_USE_DISTUTILS"] = "stdlib"
            result = subprocess.run([sys.executable, str(PROBE_SCRIPT), str(root)],
                                    env=env, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("ARGOS_TOOLCHAIN_DISTUTILS_POLICY_MISMATCH", result.stderr)

    def test_sitecustomize_bootstraps_setuptools_before_child_pip_processes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "toolchain"
            self._write_import_probe_fixture(root)
            (root / "pip" / "__main__.py").write_text(
                "import distutils.core, pathlib\n"
                "assert '_distutils' in pathlib.Path(distutils.core.__file__).parts\n"
                "print('child-pip-started')\n", encoding="utf-8")
            env = PREP.toolchain_probe_environment(root, {"PATH": os.environ["PATH"]})
            env["PMA_HINT_EXTERNAL_TOOLCHAIN_PYTHON_ROOT"] = str(root)
            env["PYTHONPATH"] = os.pathsep.join((str(SITECUSTOMIZE_DIR), str(root)))
            result = subprocess.run([sys.executable, "-m", "pip"],
                                    env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("child-pip-started", result.stdout)

    def test_real_pip_wheel_subprocess_uses_external_toolchain_startup(self):
        python_root = os.environ.get("PMA_HINT_EXTERNAL_TOOLCHAIN_PYTHON_ROOT")
        if not python_root or not Path(python_root).is_dir():
            self.skipTest("requires the prepared external Argos toolchain")
        with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as tmp:
            workspace = Path(tmp)
            source = workspace / "source"
            source.mkdir()
            (source / "setup.py").write_text(
                "from setuptools import setup\n"
                "import distutils.core, os, packaging, jaraco, jaraco.functools\n"
                "from pathlib import Path\n"
                "from probe_hint_argos_toolchain import require_no_host_site_packages\n"
                "root = Path(os.environ['PMA_HINT_EXTERNAL_TOOLCHAIN_PYTHON_ROOT']).resolve()\n"
                "origin = Path(distutils.core.__file__).resolve()\n"
                "assert root in origin.parents, origin\n"
                "assert '_distutils' in origin.parts, origin\n"
                "packaging_origin = Path(packaging.__file__).resolve()\n"
                "assert root / 'packaging' in packaging_origin.parents, packaging_origin\n"
                "assert root / 'setuptools' / '_vendor' not in packaging_origin.parents\n"
                "vendor = root / 'setuptools' / '_vendor'\n"
                "assert vendor in Path(jaraco.functools.__file__).resolve().parents\n"
                "assert all(vendor == Path(p).resolve() or vendor in Path(p).resolve().parents "
                "for p in jaraco.__path__)\n"
                "require_no_host_site_packages(root)\n"
                "setup(name='pma-startup-probe-fixture', version='0.0.1', py_modules=['fixture'])\n",
                encoding="utf-8")
            (source / "fixture.py").write_text("value = 1\n", encoding="utf-8")
            wheels = workspace / "wheels"
            wheels.mkdir()
            temp_dir = workspace / "tmp"
            temp_dir.mkdir()
            cache_dir = workspace / "pip-cache"
            env = dict(os.environ)
            env["PMA_HINT_EXTERNAL_TOOLCHAIN_PYTHON_ROOT"] = str(Path(python_root).resolve())
            env["PYTHONPATH"] = os.pathsep.join((str(SITECUSTOMIZE_DIR), str(Path(python_root).resolve())))
            env["SETUPTOOLS_USE_DISTUTILS"] = "local"
            env["PIP_NO_CACHE_DIR"] = "1"
            env["PIP_CACHE_DIR"] = str(cache_dir)
            env["TMPDIR"] = str(temp_dir)
            env["PMA_HINT_ALLOWED_WORKSPACE"] = str(workspace)
            command = [sys.executable, "-m", "pip", "wheel", "--no-index", "--no-deps",
                       "--no-build-isolation", "--wheel-dir", str(wheels), str(source)]
            result = subprocess.run(command, cwd=workspace, env=env,
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(len(list(wheels.glob("pma_startup_probe_fixture-*.whl"))), 1)

    def test_sitecustomize_fails_closed_on_transitive_host_site_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "toolchain"
            host = Path(tmp) / "host" / "site-packages"
            self._write_import_probe_fixture(root)
            (host / "hosthelper").mkdir(parents=True)
            (host / "hosthelper" / "__init__.py").write_text("\n", encoding="utf-8")
            (root / "setuptools" / "__init__.py").write_text(
                "import hosthelper\n__version__ = '80.9.0'\n", encoding="utf-8")
            env = PREP.toolchain_probe_environment(root, {"PATH": os.environ["PATH"]})
            env["PMA_HINT_EXTERNAL_TOOLCHAIN_PYTHON_ROOT"] = str(root)
            env["PYTHONPATH"] = os.pathsep.join((str(SITECUSTOMIZE_DIR), str(root), str(host)))
            result = subprocess.run([sys.executable, "-c", "print('must-not-run')"],
                                    env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 78)
            self.assertIn("ARGOS_TOOLCHAIN_HOST_SITE_PACKAGES_MODULE:hosthelper", result.stderr)
            self.assertNotIn("must-not-run", result.stdout)

    def test_external_vendor_follows_locked_root_and_excludes_host_site_packages(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "toolchain"
            vendor = root / "setuptools" / "_vendor"
            host = Path(tmp) / "host" / "site-packages"
            (root / "packaging").mkdir(parents=True)
            vendor.mkdir(parents=True)
            (vendor / "packaging").mkdir()
            (host / "jaraco").mkdir(parents=True)
            (root / "packaging" / "__init__.py").write_text("origin = 'locked'\n")
            (vendor / "packaging" / "__init__.py").write_text("origin = 'vendor'\n")
            (host / "jaraco" / "__init__.py").write_text("origin = 'host'\n")
            rogue = Path(tmp) / "other_python_libs"
            rogue.mkdir()
            script = (
                "import pathlib, sys\n"
                "from probe_hint_argos_toolchain import isolate_import_path\n"
                "root, host = map(pathlib.Path, sys.argv[1:3])\n"
                "sys.path.insert(0, str(host))\n"
                "isolate_import_path(root)\n"
                "import packaging\n"
                "assert packaging.origin == 'locked'\n"
                "paths = [pathlib.Path(p).resolve() for p in sys.path if p]\n"
                "assert host.resolve() not in paths\n"
                "assert paths.index(root.resolve()) < paths.index((root / 'setuptools' / '_vendor').resolve())\n"
            )
            env = dict(os.environ, PYTHONPATH=os.pathsep.join((str(SITECUSTOMIZE_DIR), str(root))))
            env.pop("PMA_HINT_ALLOWED_WORKSPACE", None)
            result = subprocess.run([sys.executable, "-S", "-c", script, str(root), str(host)],
                                    env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            contaminated = script.replace("isolate_import_path(root)\n", "import jaraco\nisolate_import_path(root)\n")
            rejected = subprocess.run([sys.executable, "-S", "-c", contaminated, str(root), str(host)],
                                      env=env, capture_output=True, text=True)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("ARGOS_TOOLCHAIN_HOST_SITE_PACKAGES_MODULE:jaraco", rejected.stderr)
            unapproved = script.replace("isolate_import_path(root)\n",
                                        "sys.path.insert(0, sys.argv[3])\nisolate_import_path(root)\n")
            rejected_path = subprocess.run([sys.executable, "-S", "-c", unapproved,
                                            str(root), str(host), str(rogue)],
                                           env=env, capture_output=True, text=True)
            self.assertNotEqual(rejected_path.returncode, 0)
            self.assertIn("ARGOS_TOOLCHAIN_IMPORT_PATH_UNAPPROVED", rejected_path.stderr)

    def test_argos_builder_runs_import_origin_probe_before_conda_discovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            toolchain = root / "toolchain"
            (toolchain / "python").mkdir(parents=True)
            report = root / "host-toolchain.json"
            report.write_text("{}\n", encoding="utf-8")
            conda = root / "conda"
            conda.touch()
            env = {
                "PMA_HINT_BUILDER_MODE": "argos-native",
                "PMA_HINT_HOST_TOOLCHAIN_REPORT": str(report),
                "PMA_HINT_EXTERNAL_TOOLCHAIN": str(toolchain),
                "CONDA_PKGS_DIRS": str(root / "pkgs"),
                "PMA_HINT_CONDA_EXECUTABLE": str(conda),
                "SETUPTOOLS_USE_DISTUTILS": "local",
                "PMA_HINT_EXTERNAL_TOOLCHAIN_PYTHON_ROOT": str(toolchain / "python"),
                "PMA_HINT_ALLOWED_WORKSPACE": str(root),
                "PYTHONPATH": os.pathsep.join((str(SITECUSTOMIZE_DIR), str((toolchain / "python").resolve()))),
            }
            with mock.patch.dict(BUILDER.os.environ, env, clear=True), \
                    mock.patch.object(BUILDER.platform, "system", return_value="Linux"), \
                    mock.patch.object(BUILDER.platform, "machine", return_value="x86_64"), \
                    mock.patch.object(BUILDER.platform, "libc_ver", return_value=("glibc", "2.23")), \
                    mock.patch.object(BUILDER.sys, "version_info", (3, 11, 17)), \
                    mock.patch.object(BUILDER.platform, "python_version", return_value="3.11.17"), \
                    mock.patch.object(BUILDER.shutil, "which", side_effect=lambda name: str(conda) if name == "conda" else str(root / name)), \
                    mock.patch.object(BUILDER, "verify_argos_toolchain_in_process") as verify:
                result = BUILDER.require_builder()
            self.assertEqual(result, (str(conda), "2.23"))
            with mock.patch.dict(BUILDER.os.environ,
                                 {**env, "PMA_HINT_ALLOWED_WORKSPACE": str(root / "other")}, clear=True), \
                    mock.patch.object(BUILDER.platform, "system", return_value="Linux"), \
                    mock.patch.object(BUILDER.platform, "machine", return_value="x86_64"), \
                    mock.patch.object(BUILDER.sys, "version_info", (3, 11, 17)), \
                    mock.patch.object(BUILDER.platform, "libc_ver", return_value=("glibc", "2.23")):
                with self.assertRaisesRegex(RuntimeError, "ARGOS_EXTERNAL_TOOLCHAIN_WORKSPACE_MISMATCH"):
                    BUILDER.require_builder()
            for bad_path in (os.pathsep.join((str(toolchain / "python"), str(SITECUSTOMIZE_DIR))),
                             env["PYTHONPATH"] + os.pathsep + str(root / "injected")):
                with mock.patch.dict(BUILDER.os.environ, {**env, "PYTHONPATH": bad_path}, clear=True), \
                        mock.patch.object(BUILDER.platform, "system", return_value="Linux"), \
                        mock.patch.object(BUILDER.platform, "machine", return_value="x86_64"), \
                        mock.patch.object(BUILDER.sys, "version_info", (3, 11, 17)), \
                        mock.patch.object(BUILDER.platform, "libc_ver", return_value=("glibc", "2.23")):
                    with self.assertRaisesRegex(RuntimeError, "ARGOS_EXTERNAL_TOOLCHAIN_STARTUP_PATH_MISMATCH"):
                        BUILDER.require_builder()
            verify.assert_called_once_with(toolchain / "python")

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

    def test_toolchain_wheel_accepts_nested_vendored_dist_info(self):
        with tempfile.TemporaryDirectory() as tmp:
            wheel = Path(tmp) / "example-1.2.3-py3-none-any.whl"
            self._write_toolchain_wheel(wheel)
            with zipfile.ZipFile(wheel, "a") as archive:
                archive.writestr("example/_vendor/vendor_pkg-4.5.dist-info/METADATA",
                                 "Name: vendor-pkg\nVersion: 4.5\n\n")
                archive.writestr("example/_vendor/vendor_pkg-4.5.dist-info/WHEEL",
                                 "Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n")
            package, version, _metadata = PREP.validate_py3_none_any_wheel(wheel, "3.11.17")
            self.assertEqual((package, version), ("example", "1.2.3"))

    def test_toolchain_wheel_rejects_extra_root_dist_info(self):
        with tempfile.TemporaryDirectory() as tmp:
            wheel = Path(tmp) / "example-1.2.3-py3-none-any.whl"
            self._write_toolchain_wheel(wheel)
            with zipfile.ZipFile(wheel, "a") as archive:
                archive.writestr("unexpected-9.9.dist-info/METADATA",
                                 "Name: unexpected\nVersion: 9.9\n\n")
            with self.assertRaisesRegex(RuntimeError, "WHEEL_METADATA_INVALID"):
                PREP.validate_py3_none_any_wheel(wheel, "3.11.17")

    def test_toolchain_wheel_rejects_duplicate_root_metadata_member(self):
        with tempfile.TemporaryDirectory() as tmp:
            wheel = Path(tmp) / "example-1.2.3-py3-none-any.whl"
            self._write_toolchain_wheel(wheel)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                with zipfile.ZipFile(wheel, "a") as archive:
                    archive.writestr("example-1.2.3.dist-info/METADATA",
                                     "Name: example\nVersion: 1.2.3\n\n")
            with self.assertRaisesRegex(RuntimeError, "WHEEL_METADATA_INVALID"):
                PREP.validate_py3_none_any_wheel(wheel, "3.11.17")

    def test_toolchain_wheel_requires_canonical_root_metadata_even_with_vendored_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            wheel = Path(tmp) / "example-1.2.3-py3-none-any.whl"
            with zipfile.ZipFile(wheel, "w") as archive:
                archive.writestr("example/__init__.py", "value = 1\n")
                archive.writestr("example-1.2.3.dist-info/WHEEL",
                                 "Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n")
                archive.writestr("example/_vendor/vendor_pkg-4.5.dist-info/METADATA",
                                 "Name: vendor-pkg\nVersion: 4.5\n\n")
                archive.writestr("example/_vendor/vendor_pkg-4.5.dist-info/WHEEL",
                                 "Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n")
            with self.assertRaisesRegex(RuntimeError, "WHEEL_METADATA_INVALID"):
                PREP.validate_py3_none_any_wheel(wheel, "3.11.17")

    def test_toolchain_wheel_rejects_root_dist_info_not_matching_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            wheel = Path(tmp) / "example-1.2.3-py3-none-any.whl"
            with zipfile.ZipFile(wheel, "w") as archive:
                archive.writestr("example/__init__.py", "value = 1\n")
                archive.writestr("different-1.2.3.dist-info/METADATA",
                                 "Name: example\nVersion: 1.2.3\n\n")
                archive.writestr("different-1.2.3.dist-info/WHEEL",
                                 "Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n")
            with self.assertRaisesRegex(RuntimeError, "WHEEL_METADATA_INVALID"):
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

    def test_wrapper_failures_preserve_sanitized_evidence_and_externalize_all_writes(self):
        wrapper = ROOT / "scripts/04b_footprint/run_hint_bundle_builder_argos.sh"
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as prefix_tmp:
            root = Path(tmp)
            bio_data = root / "data"
            pma_data = bio_data / "2.PROJECTS" / "PMA"
            data = pma_data / "atac_footprint"
            (data / "raw").mkdir(parents=True)
            (data / "processed" / "round1").mkdir(parents=True)
            prefix = Path(prefix_tmp) / "software" / "envs" / "pmafp"
            (prefix / "bin").mkdir(parents=True)
            python = prefix / "bin" / "python"
            python.write_text("""#!/bin/sh
if [ "$1" = "-" ] || [ "$1" = "-c" ] || \
   [ "$(basename "$1")" = "validate_argos_data_root.py" ] || \
   [ "$(basename "$1")" = "run_redacted_command.py" ]; then
  exec "$WRAPPER_SCRIPT_PYTHON" "$@"
fi
if [ "$1" = "-m" ] && [ "$2" = "pip" ]; then
  echo fake==1.0
  exit 0
fi
case "$(basename "$1")" in
  prepare_hint_argos_toolchain.py)
    printf '%s|%s|%s\\n' "${PIP_NO_CACHE_DIR:-}" "${PIP_CACHE_DIR:-}" "${TMPDIR:-}" > "$PREP_ENV_REPORT"
    if [ "${PREPARE_FAIL:-0}" = "1" ]; then
      echo simulated-download-failure >&2
      exit 17
    fi
    while [ "$#" -gt 0 ]; do
      if [ "$1" = "--report" ]; then shift; report=$1; fi
      if [ "$1" = "--python-root" ]; then shift; pyroot=$1; fi
      if [ "$1" = "--downloads" ]; then shift; downloads=$1; fi
      shift
    done
    mkdir -p "$(dirname "$report")" "$pyroot" "$downloads"
    printf '{"wheels": []}\\n' > "$report"
    exit 0
    ;;
  build_hint_bundle.py)
    printf '%s|%s|%s|%s\n' "${SETUPTOOLS_USE_DISTUTILS:-}" \
      "${PMA_HINT_EXTERNAL_TOOLCHAIN_PYTHON_ROOT:-}" "${PYTHONPATH:-}" "$PWD" > "$BUILDER_ENV_REPORT"
    sh -c 'pwd -P' > "$PIP_CHILD_CWD_REPORT"
    echo 'https://user:secret@example.org/pkg?token=secret' >&2
    exit 23
    ;;
esac
echo unexpected-python-call >&2
exit 2
""")
            python.chmod(0o755)
            conda = root / "conda"
            conda.write_text("""#!/bin/sh
if [ "$1" = "env" ]; then
  printf '{"envs": []}\\n'
elif [ "$1" = "list" ]; then
  printf '@EXPLICIT\\n'
elif [ "$1" = "--version" ]; then
  printf 'conda 25.5.1\\n'
else
  exit 2
fi
""")
            conda.chmod(0o755)
            for tool in ("gcc", "readelf"):
                tool_path = root / tool
                tool_path.write_text(f"#!/bin/sh\nprintf '{tool} mock\\n'\n")
                tool_path.chmod(0o755)
            prep_report = root / "toolchain-env.txt"
            bash_env = root / "bash_env.sh"
            bash_env.write_text("ulimit() { return 0; }\n", encoding="utf-8")
            env = dict(os.environ, BIO_DATA=str(bio_data), BIO_SOFTWARES=str(root / "software"),
                       BIOWORKSPACE_ROOT=str(root), PMA_HINT_SOURCE_PREFIX=str(prefix),
                       PMA_HINT_CONDA=str(conda), PREP_ENV_REPORT=str(prep_report),
                       WRAPPER_SCRIPT_PYTHON=sys.executable,
                       BASH_ENV=str(bash_env),
                       PATH=str(root) + os.pathsep + os.environ.get("PATH", ""))

            protected_work = pma_data / "artifact-builder-work"
            protected = subprocess.run(["bash", str(wrapper), str(data), str(protected_work),
                                        str(protected_work / "bundle"), str(protected_work / "evidence"),
                                        "https://conda.example.org/conda-forge"],
                                       capture_output=True, text=True, env=env)
            self.assertNotEqual(protected.returncode, 0)
            self.assertIn("ARGOS_OUTPUT_PATH_PROTECTED", protected.stderr)
            self.assertFalse(protected_work.exists())

            prep_workspace = root / "prep-workspace"
            prep_evidence = prep_workspace / "evidence"
            prep_env = dict(env, PREPARE_FAIL="1")
            prep_failure = subprocess.run(["bash", str(wrapper), str(data), str(prep_workspace),
                                           str(prep_workspace / "bundle"), str(prep_evidence),
                                           "https://conda.example.org/conda-forge"],
                                          capture_output=True, text=True, env=prep_env)
            self.assertNotEqual(prep_failure.returncode, 0)
            self.assertIn("simulated-download-failure", prep_failure.stderr)
            self.assertTrue((prep_evidence / "pmafp-conda-after.txt").is_file())
            self.assertTrue((prep_evidence / "pmafp-pip-after.txt").is_file())
            integrity = json.loads((prep_evidence / "pmafp-integrity.json").read_text(encoding="utf-8"))
            self.assertEqual(integrity["status"], "PMAFP_INTEGRITY_OK")
            prep_values = prep_report.read_text(encoding="utf-8").strip().split("|")
            self.assertEqual(prep_values[0], "1")
            self.assertEqual(Path(prep_values[1]).resolve(), (prep_workspace / "pip-cache").resolve())
            self.assertEqual(Path(prep_values[2]).resolve(), (prep_workspace / "tmp").resolve())

            builder_workspace = root / "builder-workspace"
            builder_env_report = root / "builder-env.txt"
            pip_child_cwd_report = root / "pip-child-cwd.txt"
            builder_env = dict(env, BUILDER_ENV_REPORT=str(builder_env_report),
                               PIP_CHILD_CWD_REPORT=str(pip_child_cwd_report))
            builder_failure = subprocess.run(["bash", str(wrapper), str(data), str(builder_workspace),
                                              str(builder_workspace / "bundle"),
                                              str(builder_workspace / "evidence"),
                                              "https://conda.example.org/conda-forge"],
                                             cwd=root, capture_output=True, text=True, env=builder_env)
            self.assertEqual(builder_failure.returncode, 23, builder_failure.stderr)
            builder_values = builder_env_report.read_text(encoding="utf-8").strip().split("|")
            self.assertEqual(builder_values[0], "local")
            self.assertEqual(Path(builder_values[1]).resolve(),
                             (builder_workspace / "toolchain" / "python").resolve())
            self.assertEqual(builder_values[2].split(os.pathsep)[0], str(SITECUSTOMIZE_DIR))
            self.assertEqual(builder_values[2].split(os.pathsep)[1], builder_values[1])
            self.assertEqual(Path(builder_values[3]).resolve(), builder_workspace.resolve())
            self.assertEqual(Path(pip_child_cwd_report.read_text(encoding="utf-8").strip()).resolve(),
                             builder_workspace.resolve())


    def test_redacted_command_sanitizes_logs_and_preserves_failure_status(self):
        helper = ROOT / "scripts/04b_footprint/run_redacted_command.py"
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "builder.log"
            result = subprocess.run([
                sys.executable, str(helper), str(log), "--", sys.executable, "-c",
                "import sys; print('https://user:secret@example.org/pkg?token=secret'); sys.exit(23)",
            ], capture_output=True, text=True)
            self.assertEqual(result.returncode, 23)
            content = log.read_text(encoding="utf-8")
            self.assertIn("https://example.org/pkg", content)
            self.assertNotIn("user:secret", content)
            self.assertNotIn("token=secret", content)

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
                "base_url": "https://example.org/channel", "sha256": "a" * 64,
                "url": "https://example.org/channel/linux-64/python-3.11.9-mock_0.tar.bz2?token=secret"
            }]}})
            snapshot_record = {"name": "python", "version": "3.11.9", "build": "mock_0",
                              "sha256": "a" * 64, "size": 123, "depends": [], "constrains": []}
            snapshot = {"url": "https://example.org/channel/linux-64/repodata.json", "sha256": "b" * 64,
                        "evidence_file": "upstream-repodata-linux-64-after.json",
                        "packages": {"python-3.11.9-mock_0.tar.bz2": snapshot_record},
                        "packages.conda": {}}
            package_cache = work / "package-cache"
            with mock.patch.dict(BUILDER.os.environ, {
                "PMA_HINT_BUILDER_MODE": "argos-native",
                "PMA_HINT_ARGOS_CONDA_CHANNEL": "https://example.org/channel",
            }), mock.patch.object(BUILDER, "fetch_repodata_snapshot", return_value=snapshot), \
                 mock.patch.object(BUILDER, "verify_solver_repodata_cache", return_value={"sha256": "b" * 64}), \
                 mock.patch.object(BUILDER, "conda_dry_run", return_value=output):
                BUILDER.load_solver_plan("/mock/conda", work, package_cache=package_cache)
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
                                      "sha256": "c" * 64,
                                      "evidence_file": "upstream-repodata-linux-64-after.json"},
                  "solver_record": {"depends": ["upstream-dep >=2"], "constrains": []}}
        result = BUILDER.build_local_repodata([record], "linux-64")
        self.assertEqual(result["packages"][record["filename"]]["depends"], ["upstream-dep >=2"])
        self.assertEqual(record["dependency_metadata_diff"]["depends"], {
            "archive_index": ["archive-hotfix >=1"], "upstream_repodata": ["upstream-dep >=2"]
        })

    def test_argos_upstream_repodata_snapshot_is_retained_and_hash_verifiable(self):
        payload = b'{"info":{"subdir":"linux-64"},"packages":{"demo-1.0-0.tar.bz2":{"depends":[]}},"packages.conda":{}}'
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)

            def write_snapshot(url, path):
                Path(path).write_bytes(payload)
                return str(path), None

            with mock.patch.object(BUILDER.urllib.request, "urlretrieve", side_effect=write_snapshot):
                snapshot = BUILDER.fetch_repodata_snapshot(
                    "https://example.org/channel", "linux-64", work,
                    load_records=True, snapshot_id="after")
            retained = work / snapshot["evidence_file"]
            self.assertTrue(retained.is_file())
            self.assertEqual(BUILDER.sha256(retained), snapshot["sha256"])
            self.assertEqual(json.loads(retained.read_bytes()), json.loads(payload))
            provenance = json.loads((work / f"{retained.name}.provenance.json").read_text(encoding="utf-8"))
            self.assertEqual(provenance["url"], snapshot["url"])
            self.assertEqual(provenance["sha256"], snapshot["sha256"])
            self.assertEqual(snapshot["size"], len(payload))
            self.assertEqual(snapshot["packages.conda"], {})
            provenance = json.loads((work / f"{retained.name}.provenance.json").read_text(encoding="utf-8"))
            self.assertEqual(provenance["url"], snapshot["url"])
            self.assertEqual(provenance["sha256"], snapshot["sha256"])

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

    def test_realistic_conda_link_uniquely_maps_to_conda_repodata_artifact(self):
        channel = "https://example.org/channel"
        filename = "demo-1.2.3-py311_0.conda"
        record = {"name": "demo", "version": "1.2.3", "build": "py311_0",
                  "build_number": 0, "sha256": "a" * 64, "md5": "b" * 32,
                  "size": 1234, "depends": ["python >=3.11"], "constrains": []}
        link = {"base_url": channel, "channel": "example/channel", "dist_name": "demo-1.2.3-py311_0",
                "name": "demo", "version": "1.2.3", "build_string": "py311_0",
                "build_number": 0, "platform": "linux-64"}
        resolved = BUILDER.resolve_solver_artifacts([link], {
            "linux-64": {"packages": {}, "packages.conda": {filename: record}}
        }, expected_channel=channel)
        artifact = resolved[0]["pma_artifact"]
        self.assertEqual(artifact["filename"], filename)
        self.assertEqual(artifact["sha256"], "a" * 64)
        self.assertEqual(artifact["repodata_section"], "packages.conda")
        self.assertEqual(artifact["artifact_url"], f"{channel}/linux-64/{filename}")
        self.assertEqual(resolved[0]["pma_solver_metadata_fields"]["depends"], False)

    def test_cross_format_duplicate_requires_fetch_filename_and_hash(self):
        channel = "https://example.org/channel"
        link = {"base_url": channel, "name": "demo", "version": "1.2.3",
                "build_string": "py311_0", "platform": "linux-64"}
        tar_fn = "demo-1.2.3-py311_0.tar.bz2"
        conda_fn = "demo-1.2.3-py311_0.conda"
        tar_record = {"name": "demo", "version": "1.2.3", "build": "py311_0",
                      "sha256": "a" * 64, "size": 10}
        conda_record = {**tar_record, "sha256": "b" * 64}
        snapshots = {"linux-64": {"packages": {tar_fn: tar_record},
                                  "packages.conda": {conda_fn: conda_record}}}
        with self.assertRaisesRegex(RuntimeError, "ARTIFACT_NOT_UNIQUE"):
            BUILDER.resolve_solver_artifacts([link], snapshots, expected_channel=channel)
        with self.assertRaisesRegex(RuntimeError, "FETCH_DISAMBIGUATION_INCOMPLETE"):
            BUILDER.resolve_solver_artifacts([link], snapshots,
                fetches=[{"name": "demo", "version": "1.2.3", "build": "py311_0",
                          "subdir": "linux-64", "fn": conda_fn}], expected_channel=channel)
        with self.assertRaisesRegex(RuntimeError, "FETCH_DISAMBIGUATION_INCOMPLETE"):
            BUILDER.resolve_solver_artifacts([link], snapshots,
                fetches=[{"name": "demo", "version": "1.2.3", "build": "py311_0",
                          "subdir": "linux-64", "sha256": "b" * 64}], expected_channel=channel)
        fetch = [{"name": "demo", "version": "1.2.3", "build": "py311_0",
                  "subdir": "linux-64", "fn": conda_fn, "sha256": "b" * 64}]
        resolved = BUILDER.resolve_solver_artifacts([link], snapshots, fetches=fetch,
                                                     expected_channel=channel)
        self.assertEqual(resolved[0]["pma_artifact"]["filename"], conda_fn)
        unrelated = {"name": "other", "version": "9.9", "build": "0",
                     "subdir": "linux-64", "fn": "other-9.9-0.conda", "sha256": "c" * 64}
        with self.assertRaisesRegex(RuntimeError, "FETCH_NOT_IN_LINK"):
            BUILDER.resolve_solver_artifacts([link], snapshots, fetches=[*fetch, unrelated],
                                             expected_channel=channel)
        with self.assertRaisesRegex(RuntimeError, "FETCH_DUPLICATE"):
            BUILDER.resolve_solver_artifacts([link], snapshots, fetches=[*fetch, *fetch],
                                             expected_channel=channel)
        with self.assertRaisesRegex(RuntimeError, "FETCH_SUBDIR_MISMATCH"):
            BUILDER.resolve_solver_artifacts([link], snapshots,
                fetches=[{**fetch[0], "subdir": "noarch"}], expected_channel=channel)
        with self.assertRaisesRegex(RuntimeError, "FETCH_REPODATA_CONFLICT"):
            BUILDER.resolve_solver_artifacts([link], snapshots,
                fetches=[{**fetch[0], "sha256": "c" * 64}], expected_channel=channel)

    def test_solver_missing_depends_differs_from_explicit_empty_depends(self):
        channel = "https://example.org/channel"
        filename = "demo-1.2.3-h0.conda"
        record = {"name": "demo", "version": "1.2.3", "build": "h0",
                  "sha256": "a" * 64, "size": 12, "depends": ["libc >=2.17"]}
        link = {"base_url": channel, "name": "demo", "version": "1.2.3",
                "build_string": "h0", "platform": "noarch"}
        snapshot = {"noarch": {"packages": {}, "packages.conda": {filename: record}}}
        resolved = BUILDER.resolve_solver_artifacts([link], snapshot, expected_channel=channel)
        self.assertFalse(resolved[0]["pma_solver_metadata_fields"]["depends"])
        with self.assertRaisesRegex(RuntimeError, "METADATA_MISMATCH:.*depends"):
            BUILDER.resolve_solver_artifacts([{**link, "depends": []}], snapshot,
                                             expected_channel=channel)

    def test_conda_container_format_and_local_repodata_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "demo-1.2.3-py311_0.conda"
            with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
                archive.writestr("metadata.json", '{"conda_pkg_format_version":2}')
                archive.writestr("info-demo-1.2.3-py311_0.tar.zst", b"info")
                archive.writestr("pkg-demo-1.2.3-py311_0.tar.zst", b"payload")
            artifact = {"name": "demo", "version": "1.2.3", "build": "py311_0"}
            BUILDER.validate_conda_archive(path, artifact)
            with self.assertRaisesRegex(RuntimeError, "ZIP_MEMBERS_INVALID"):
                with zipfile.ZipFile(path, "a", compression=zipfile.ZIP_STORED) as archive:
                    archive.writestr("unexpected.txt", b"extra")
                BUILDER.validate_conda_archive(path, artifact)
        filename = "demo-1.2.3-py311_0.conda"
        record = {"subdir": "linux-64", "name": "demo", "version": "1.2.3",
                  "build": "py311_0", "filename": filename, "sha256": "a" * 64,
                  "md5": "b" * 32, "size": 12, "index_record": {"name": "demo",
                  "version": "1.2.3", "build": "py311_0", "depends": []},
                  "source_record": {"name": "demo", "version": "1.2.3", "build": "py311_0",
                  "depends": [], "constrains": []}}
        result = BUILDER.build_local_repodata([record], "linux-64")
        self.assertNotIn(filename, result["packages"])
        self.assertEqual(result["packages.conda"][filename]["sha256"], "a" * 64)

    def test_conda_official_extractor_preserves_payload_for_abi_scan(self):
        conda = os.environ.get("PMA_HINT_CONDA_EXECUTABLE") or shutil.which("conda")
        self.assertTrue(conda, "audited Conda executable is required for the .conda contract")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prefix = root / "fixture-prefix"
            (prefix / "info").mkdir(parents=True)
            (prefix / "bin").mkdir()
            (prefix / "info/index.json").write_text(json.dumps({
                "name": "pma-conda-fixture", "version": "1.0", "build": "0",
                "build_number": 0, "depends": []}), encoding="utf-8")
            (prefix / "bin/true").write_bytes(Path("/bin/true").read_bytes())
            archive = root / "pma-conda-fixture-1.0-0.conda"
            with mock.patch.dict(BUILDER.CONDA_EXTRACTOR_VERSIONS,
                                 {"conda-package-handling": "0.0.0"}):
                with self.assertRaisesRegex(RuntimeError, "VERSION_NOT_APPROVED:conda-package-handling"):
                    BUILDER.conda_extractor(conda, root)
            python, provenance = BUILDER.conda_extractor(conda, root)
            self.assertEqual(provenance["extract_api"], "conda_package_handling.api.extract")
            self.assertEqual(provenance["packages"]["conda-package-handling"]["version"], "2.4.0")
            for package_record in provenance["packages"].values():
                self.assertTrue(package_record["installed_module_files"])
                for module_file in package_record["installed_module_files"]:
                    self.assertRegex(module_file["sha256"], r"^[0-9a-f]{64}$")
                self.assertEqual(package_record["integrity_basis"],
                                 "conda-meta paths_data sha256_in_prefix")
            create_code = "from conda_package_handling.api import create; import sys; create(sys.argv[1], ['info/index.json', 'bin/true'], sys.argv[2])"
            env = os.environ.copy()
            for key in BUILDER.CONDA_ISOLATED_ENV_VARS:
                env.pop(key, None)
            subprocess.run([str(python), "-I", "-c", create_code, str(prefix), str(archive)],
                           check=True, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           text=True)
            artifact = {"name": "pma-conda-fixture", "version": "1.0", "build": "0"}
            BUILDER.validate_conda_archive(archive, artifact)
            extracted = BUILDER.extract_conda_archive(python, archive, root / "extract", root)
            self.assertEqual((extracted / "info/index.json").read_text(encoding="utf-8"),
                             (prefix / "info/index.json").read_text(encoding="utf-8"))
            bundle = root / "bundle"
            target = bundle / "conda/linux-64" / archive.name
            target.parent.mkdir(parents=True)
            target.write_bytes(archive.read_bytes())
            (root / "audit").mkdir()
            audit = BUILDER.audit_conda_elf([{"subdir": "linux-64", "filename": archive.name}],
                                           bundle, root / "audit", conda)
            self.assertGreater(audit["elf_files_checked"], 0)

    def test_conda_archive_preflight_rejects_malicious_members_and_limits(self):
        conda = os.environ.get("PMA_HINT_CONDA_EXECUTABLE") or shutil.which("conda")
        self.assertTrue(conda, "audited Conda executable is required for archive preflight contracts")
        artifact = {"name": "pma-archive-fixture", "version": "1.0", "build": "0"}
        cases = [
            ("symlink-chain", [{"name": "a", "kind": "symlink", "target": "b"},
                                {"name": "b", "kind": "symlink", "target": "../../outside"}], [], []),
            ("hardlink-forward-target", [{"name": "link", "kind": "hardlink", "target": "later"}], [], []),
            ("directory-replaced-by-link", [{"name": "a/child", "kind": "file"},
                                             {"name": "a", "kind": "symlink", "target": "safe"}], [], []),
            ("cross-component-collision", [{"name": "shared", "kind": "file"}],
             [{"name": "shared", "kind": "file"}], []),
            ("corrupt-zstd", [{"name": "payload", "kind": "file"}], [], ["corrupt"]),
            ("unpacked-size-limit", [{"name": "payload", "kind": "file", "data": "too-large"}], [], []),
            ("file-count-limit", [{"name": "one"}, {"name": "two"}, {"name": "three"}], [], []),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            python, _provenance = BUILDER.conda_extractor(conda, root)
            for name, pkg, info, corrupt in cases:
                with self.subTest(case=name):
                    archive = root / f"{name}.conda"
                    self._make_conda_archive_fixture(python, archive, pkg=pkg, info=info, corrupt=corrupt)
                    BUILDER.validate_conda_archive(archive, artifact)
                    limits = {}
                    if name == "unpacked-size-limit":
                        limits["MAX_EXTRACTED_PACKAGE_BYTES"] = 2
                    if name == "file-count-limit":
                        limits["MAX_EXTRACTED_PACKAGE_FILES"] = 2
                    with mock.patch.multiple(BUILDER, **limits):
                        with self.assertRaises(subprocess.CalledProcessError):
                            BUILDER.extract_conda_archive(
                                python, archive, root / f"extract-{name}", root)

    def test_conda_unknown_package_format_is_rejected_before_download(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = {"pma_artifact": {"subdir": "linux-64", "filename": "python-3.11.0-0.deb",
                                       "sha256": "a" * 64,
                                       "artifact_url": "https://example.org/linux-64/python-3.11.0-0.deb",
                                       "size": 123}}
            with mock.patch.object(BUILDER.urllib.request, "urlretrieve") as download:
                with self.assertRaisesRegex(RuntimeError, "UNSUPPORTED_CONDA_ARTIFACT"):
                    BUILDER.copy_conda_closure([record], root, "/mock/conda", root / "work")
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
            dirty = {
                "PYTHONPATH": "/locked/builder/python",
                "PMA_HINT_EXTERNAL_TOOLCHAIN_PYTHON_ROOT": "/locked/builder/python",
                "PMA_HINT_ALLOWED_WORKSPACE": "/external/work",
            }

            def fake_run(argv, *, capture, env=None):
                observed.append(argv)
                self.assertIsNotNone(env)
                self.assertEqual(env.get("CONDA_PKGS_DIRS"), str((prefix.parent / "cache").resolve()))
                for key in BUILDER.CONDA_ISOLATED_ENV_VARS:
                    self.assertNotIn(key, env)
                return "{}"

            with mock.patch.dict(BUILDER.os.environ, dirty), \
                    mock.patch.object(BUILDER, "run", side_effect=fake_run):
                cache = prefix.parent / "cache"
                self.assertEqual(BUILDER.conda_dry_run("conda", prefix, ["--offline"],
                                                        ("python=3.11",), package_cache=cache), "{}")
                self.assertEqual(BUILDER.conda_dry_run("conda", prefix,
                                                        ["--override-channels", "-c", "https://example.org/channel"],
                                                        ("python=3.11",), package_cache=cache), "{}")
                for key, value in dirty.items():
                    self.assertEqual(BUILDER.os.environ[key], value)
            self.assertEqual(len(observed), 2)
            for command in observed:
                self.assertEqual(command[1:4], ["create", "--dry-run", "--json"])
            self.assertIn("--offline", observed[0])
            self.assertIn("https://example.org/channel", observed[1])
            self.assertFalse(prefix.exists())

            def violating_run(argv, *, capture, env=None):
                Path(argv[argv.index("-p") + 1]).mkdir()
                return "{}"

            with mock.patch.object(BUILDER, "run", side_effect=violating_run):
                with self.assertRaisesRegex(RuntimeError, "CONDA_DRY_RUN_CREATED_PREFIX"):
                    BUILDER.conda_dry_run("conda", prefix, [], ("python=3.11",))
            self.assertTrue(prefix.exists())

    def test_conda_cli_calls_isolate_builder_python_without_changing_other_commands(self):
        dirty = {
            "PYTHONPATH": "/locked/builder/python",
            "PMA_HINT_EXTERNAL_TOOLCHAIN_PYTHON_ROOT": "/locked/builder/python",
            "PMA_HINT_ALLOWED_WORKSPACE": "/external/work",
            "CONDA_PKGS_DIRS": "/external/work/conda-pkgs",
        }
        calls = []

        def fake_run(argv, *, capture=False, env=None):
            calls.append((argv, capture, env))
            return "ok"

        with mock.patch.dict(BUILDER.os.environ, dirty), \
                mock.patch.object(BUILDER, "run", side_effect=fake_run):
            for argv in (["/audited/conda", "--version"],
                         ["/audited/conda", "list", "conda-index"],
                         ["/audited/conda", "index", "/external/work/bundle/conda"],
                         ["/audited/conda", "create", "--dry-run"]):
                self.assertEqual(BUILDER.run_conda(argv, capture=True), "ok")
            for key, value in dirty.items():
                self.assertEqual(BUILDER.os.environ[key], value)
        self.assertEqual(len(calls), 4)
        for argv, capture, env in calls:
            self.assertEqual(argv[0], "/audited/conda")
            self.assertTrue(capture)
            self.assertEqual(env["CONDA_PKGS_DIRS"], dirty["CONDA_PKGS_DIRS"])
            for key in BUILDER.CONDA_ISOLATED_ENV_VARS:
                self.assertNotIn(key, env)

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
                    "name": name, "version": version, "build": build, "sha256": digest,
                    "md5": BUILDER.md5(archive_path), "size": archive_path.stat().st_size
                }
                lock_rows.append("\t".join((subdir, name, version, build, filename, digest)) + "\n")
                inventory_paths.append(archive_path)
            for subdir in ("linux-64", "noarch"):
                path = bundle / "conda" / subdir / "repodata.json"
                repodata[subdir]["info"] = {"subdir": subdir, "repodata_version": 1}
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
                "conda_abi_audit": {"scope": "static-elf-compatibility-audit",
                                    "runtime_linkability_verified": False},
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
            evidence = Path(tmp) / "evidence"
            work = evidence / "work"
            work.mkdir(parents=True)
            cache_root = Path(tmp) / "conda-pkgs"
            online_channel = "https://example.org/channel"
            local_channel_url = (bundle / "conda").resolve().as_uri()
            online_links = []
            offline_links = []
            offline_cache = {}
            online_provenance = {}
            for subdir in ("linux-64", "noarch"):
                snapshot = repodata[subdir]
                snapshot_path = work / f"upstream-repodata-{subdir}-after.json"
                payload = json.dumps(snapshot).encode()
                snapshot_path.write_bytes(payload)
                sidecar = {"snapshot_id": "after", "subdir": subdir,
                           "url": f"{online_channel}/{subdir}/repodata.json",
                           "sha256": hashlib.sha256(payload).hexdigest(),
                           "evidence_file": snapshot_path.name}
                (work / f"{snapshot_path.name}.provenance.json").write_text(
                    json.dumps(sidecar), encoding="utf-8")
                self._write_cache_pair(cache_root, f"online-{subdir}",
                                       f"{online_channel}/{subdir}", payload)
                online_provenance[subdir] = {
                    "url": f"{online_channel}/{subdir}/repodata.json",
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "evidence_file": snapshot_path.name,
                    "solver_cache": {"url": f"{online_channel}/{subdir}",
                                     "cache_file": f"online-{subdir}.json",
                                     "sha256": hashlib.sha256(payload).hexdigest(),
                                     "size": len(payload)}}
                local_payload = (bundle / "conda" / subdir / "repodata.json").read_bytes()
                local_url = f"{local_channel_url}/{subdir}"
                self._write_cache_pair(cache_root, f"offline-{subdir}", local_url, local_payload)
                offline_cache[subdir] = {"url": local_url, "cache_file": f"offline-{subdir}.json",
                                         "sha256": hashlib.sha256(local_payload).hexdigest(),
                                         "size": len(local_payload)}
            for subdir, name, version, build in conda_rows:
                online_links.append({"base_url": online_channel, "name": name, "version": version,
                                     "dist_name": f"{name}-{version}-{build}",
                                     "build_string": build, "platform": subdir})
                offline_links.append({"base_url": local_channel_url, "name": name, "version": version,
                                      "build_string": build, "platform": subdir})
            raw_solve = json.dumps({"actions": {"LINK": online_links, "FETCH": []}})
            snapshots = {}
            for subdir in ("linux-64", "noarch"):
                snapshot = dict(repodata[subdir])
                snapshot.update({"url": f"{online_channel}/{subdir}/repodata.json",
                                 "sha256": hashlib.sha256(
                                     (work / f"upstream-repodata-{subdir}-after.json").read_bytes()
                                 ).hexdigest(),
                                 "size": (work / f"upstream-repodata-{subdir}-after.json").stat().st_size,
                                 "evidence_file": f"upstream-repodata-{subdir}-after.json"})
                snapshots[subdir] = snapshot
            with mock.patch.dict(os.environ, {"PMA_HINT_ARGOS_CONDA_CHANNEL": online_channel}), \
                 mock.patch.object(BUILDER, "fetch_repodata_snapshot",
                                  side_effect=lambda channel, subdir, _work, *, load_records, snapshot_id:
                                  dict(snapshots[subdir])), \
                 mock.patch.object(BUILDER, "conda_dry_run", return_value=raw_solve), \
                 mock.patch.object(BUILDER, "verify_solver_repodata_cache",
                                  side_effect=lambda _cache, _channel, subdir, _snapshot:
                                  online_provenance[subdir]["solver_cache"]):
                resolved_links, _solve_command, solver_output = BUILDER.load_solver_plan(
                    "conda", work, package_cache=cache_root)
            BUILDER.write_online_solver_evidence(evidence, solver_output, resolved_links)
            (evidence / "conda-offline-solve.json").write_text(
                json.dumps({"actions": {"LINK": offline_links, "FETCH": []}}), encoding="utf-8")
            (evidence / "conda-offline-repodata-provenance.json").write_text(
                json.dumps(offline_cache), encoding="utf-8")
            manifest["conda_offline_repodata_provenance_sha256"] = BUILDER.sha256(
                evidence / "conda-offline-repodata-provenance.json")
            (bundle / "bundle-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            (evidence / "conda-solver-cache-root.json").write_text(
                json.dumps({"cache_root": str(cache_root)}), encoding="utf-8")
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
            result = subprocess.run([BUILDER.sys.executable,
                                     str(ROOT / "scripts/04b_footprint/validate_hint_bundle.py"),
                                     str(bundle), "--evidence-dir", str(evidence)],
                                    capture_output=True, text=True, env=env)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            raw_online_path = evidence / "conda-solve.json"
            raw_online_bytes = raw_online_path.read_bytes()
            raw_online = json.loads(raw_online_bytes)
            self.assertNotIn("pma_upstream_repodata", raw_online["actions"]["LINK"][0])
            enriched_path = evidence / "conda-upstream-link-records.json"
            enriched_bytes = enriched_path.read_bytes()
            enriched_records = json.loads(enriched_bytes)
            self.assertIn("pma_upstream_repodata", enriched_records[0])

            # The validator must compare both FETCH digests when the real solver supplies them.
            link = raw_online["actions"]["LINK"][0]
            enriched = enriched_records[0]
            artifact = enriched["pma_artifact"]
            source = repodata[link["platform"]][artifact["repodata_section"]][artifact["filename"]]
            matching_fetch = {"name": link["name"], "version": link["version"],
                              "build_string": link["build_string"], "platform": link["platform"],
                              "fn": artifact["filename"], "base_url": online_channel,
                              "url": artifact["artifact_url"], "sha256": source["sha256"],
                              "md5": source["md5"]}
            raw_online["actions"]["FETCH"] = [matching_fetch]
            raw_online_path.write_text(json.dumps(raw_online), encoding="utf-8")
            both_hashes_valid = subprocess.run([BUILDER.sys.executable,
                str(ROOT / "scripts/04b_footprint/validate_hint_bundle.py"),
                str(bundle), "--evidence-dir", str(evidence)], capture_output=True, text=True, env=env)
            self.assertEqual(both_hashes_valid.returncode, 0,
                             both_hashes_valid.stdout + both_hashes_valid.stderr)
            matching_fetch["md5"] = "c" * 32
            raw_online_path.write_text(json.dumps(raw_online), encoding="utf-8")
            wrong_fetch_md5 = subprocess.run([BUILDER.sys.executable,
                str(ROOT / "scripts/04b_footprint/validate_hint_bundle.py"),
                str(bundle), "--evidence-dir", str(evidence)], capture_output=True, text=True, env=env)
            self.assertNotEqual(wrong_fetch_md5.returncode, 0)
            self.assertIn("ONLINE_SOLVE_ARTIFACT_NOT_UNIQUE", wrong_fetch_md5.stderr)
            raw_online_path.write_bytes(raw_online_bytes)

            enriched_records[0].pop("pma_upstream_repodata")
            enriched_path.write_text(json.dumps(enriched_records), encoding="utf-8")
            missing_enriched_provenance = subprocess.run([BUILDER.sys.executable,
                str(ROOT / "scripts/04b_footprint/validate_hint_bundle.py"),
                str(bundle), "--evidence-dir", str(evidence)], capture_output=True, text=True, env=env)
            self.assertNotEqual(missing_enriched_provenance.returncode, 0)
            self.assertIn("ONLINE_ENRICHED_REPODATA_PROVENANCE_MISSING", missing_enriched_provenance.stderr)
            enriched_path.write_bytes(enriched_bytes)

            offline_solve_path = evidence / "conda-offline-solve.json"
            offline_solve_bytes = offline_solve_path.read_bytes()
            offline_solve_path.write_text(json.dumps({"actions": {"LINK": [], "FETCH": []}}),
                                          encoding="utf-8")
            rejected_offline_evidence = subprocess.run([BUILDER.sys.executable,
                str(ROOT / "scripts/04b_footprint/validate_hint_bundle.py"),
                str(bundle), "--evidence-dir", str(evidence)], capture_output=True, text=True, env=env)
            self.assertNotEqual(rejected_offline_evidence.returncode, 0)
            self.assertIn("OFFLINE_SOLVER_LOCK_CLOSURE_MISMATCH", rejected_offline_evidence.stderr)
            offline_solve_path.write_bytes(offline_solve_bytes)
            extra_repodata = bundle / "conda/linux-64/repodata.json"
            extra_payload = json.loads(extra_repodata.read_text(encoding="utf-8"))
            extra_payload["packages"]["rogue-1.0-0.tar.bz2"] = {
                "name": "rogue", "version": "1.0", "build": "0",
                "sha256": "a" * 64, "size": 1}
            extra_repodata.write_text(json.dumps(extra_payload), encoding="utf-8")
            rejected_repodata = subprocess.run([BUILDER.sys.executable,
                str(ROOT / "scripts/04b_footprint/validate_hint_bundle.py"),
                str(bundle), "--evidence-dir", str(evidence)], capture_output=True, text=True, env=env)
            self.assertNotEqual(rejected_repodata.returncode, 0)
            self.assertIn("REPODATA_RECORD_NOT_IN_LOCK", rejected_repodata.stderr)
            extra_repodata.write_text(json.dumps(repodata["linux-64"]), encoding="utf-8")
            (bundle / "rogue-output.bin").write_bytes(b"not inventoried")
            rejected_extra_file = subprocess.run([BUILDER.sys.executable,
                str(ROOT / "scripts/04b_footprint/validate_hint_bundle.py"),
                str(bundle), "--evidence-dir", str(evidence)], capture_output=True, text=True, env=env)
            self.assertNotEqual(rejected_extra_file.returncode, 0)
            self.assertIn("BUNDLE_FILE_NOT_IN_INVENTORY:rogue-output.bin", rejected_extra_file.stderr)

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
