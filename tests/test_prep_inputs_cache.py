import gzip
import importlib.util
import pathlib
import sys
import tempfile
import types
import unittest
from unittest.mock import patch


class FakeTabixFile:
    def __init__(self, path):
        self.path = path
        with gzip.open(path, "rb") as handle:
            self.data = handle.read()
        self.contigs = ["chr1"] if self.data else []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def fetch(self, _contig):
        return iter(self.data.decode().splitlines())


ORIGINAL_PYSAM = sys.modules.get("pysam")
sys.modules["pysam"] = types.SimpleNamespace(TabixFile=FakeTabixFile)
MODULE_PATH = pathlib.Path(__file__).parents[1] / "scripts/04b_footprint/01_prep_inputs.py"
SPEC = importlib.util.spec_from_file_location("pma_prep_inputs_cache_test", MODULE_PATH)
PREP = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PREP)
if ORIGINAL_PYSAM is None:
    del sys.modules["pysam"]
else:
    sys.modules["pysam"] = ORIGINAL_PYSAM


class PrepInputCacheTests(unittest.TestCase):
    def test_stale_empty_tabix_pair_is_archived_and_rebuilt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            output = root / "frags/gDNA.frags.tsv.gz"
            output.parent.mkdir()
            output.write_bytes(gzip.compress(b""))
            pathlib.Path(str(output) + ".tbi").write_bytes(b"stale index")
            self.assertFalse(PREP.indexed_file_ok(output))

            staged = {}

            def command_builder(path):
                staged["path"] = path
                return f"mock sort | bgzip > {path} && tabix -f -p bed {path}"

            def mock_run(argv, check):
                self.assertEqual(argv[:3], ["bash", "-o", "pipefail"])
                self.assertIn("tabix -f -p bed", argv[-1])
                staged["path"].write_bytes(gzip.compress(b"chr1\t1\t3\tgDNA\t1\n"))
                pathlib.Path(str(staged["path"]) + ".tbi").write_bytes(b"fresh index")

            with patch.object(PREP.subprocess, "run", side_effect=mock_run):
                PREP.build_indexed_bgzip(output, root, root / "sort_tmp", command_builder)

            self.assertTrue(PREP.indexed_file_ok(output))
            self.assertTrue(pathlib.Path(str(output) + ".complete.sha256").is_file())
            archived = list((root / "cache_interrupted").glob("*/" + output.name))
            self.assertEqual(len(archived), 1)
            self.assertEqual(archived[0].read_bytes(), gzip.compress(b""))

    def test_bgzf_with_readable_front_and_truncated_tail_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = pathlib.Path(tmp) / "frags.tsv.gz"
            full = gzip.compress(b"chr1\t1\t3\tgDNA\t1\n" + b"x" * 128)
            output.write_bytes(full[:-8])
            pathlib.Path(str(output) + ".tbi").write_bytes(b"apparently valid index")
            self.assertFalse(PREP.indexed_file_ok(output))


if __name__ == "__main__":
    unittest.main()
