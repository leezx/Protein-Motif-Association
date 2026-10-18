"""Small contract checks for the external HINT bundle builder."""
import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/04b_footprint/build_hint_bundle.py"
SPEC = importlib.util.spec_from_file_location("build_hint_bundle", SCRIPT)
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)


class HintBundleBuildContract(unittest.TestCase):
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

    def test_rgt_pure_python_wheel_gets_explicit_no_elf_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            wheel = Path(tmp) / "RGT-1.0.2-py3-none-any.whl"
            with zipfile.ZipFile(wheel, "w") as archive:
                archive.writestr("rgt/__init__.py", "__version__ = '1.0.2'\n")
                archive.writestr("RGT-1.0.2.dist-info/METADATA", "Name: RGT\nVersion: 1.0.2\n")
            result = BUILDER.audit_rgt_wheel(wheel, "builder@sha256:" + "a" * 64,
                                             Path(tmp), BUILDER.RGT_SHA256)
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


if __name__ == "__main__":
    unittest.main()
