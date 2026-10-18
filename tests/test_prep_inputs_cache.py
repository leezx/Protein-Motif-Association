import gzip
import importlib.util
import json
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

    def test_absent_gdna_contig_is_zero_without_tabix_fetch(self):
        class NoFetchTabix:
            def fetch(self, *_args):
                raise AssertionError("fetch must not be called for an absent contig")

        self.assertEqual(PREP.count_gdna_coverage(NoFetchTabix(), "chrY", 100, 200, {"chr1"}), 0)

    def test_present_gdna_contig_counts_overlapping_fragments(self):
        class OneRecordTabix:
            def fetch(self, contig, start, end):
                self.assertions = (contig, start, end)
                return iter(["chr1\t105\t110\tgDNA\t1", "chr1\t500\t510\tgDNA\t1"])

        tb = OneRecordTabix()
        self.assertEqual(PREP.count_gdna_coverage(tb, "chr1", 100, 200, {"chr1"}), 1)
        self.assertEqual(tb.assertions, ("chr1", 0, 1200))

    def test_gdna_tile_selection_excludes_zero_coverage_regions(self):
        cov = [(0, "chrY", 100, 200), (0, "chr1", 300, 400), (3, "chr1", 100, 200)]
        self.assertEqual(PREP.select_gdna_tiles(cov, limit=1), [(3, "chr1", 100, 200)])

    def test_gdna_tile_selection_requires_fixed_requested_count(self):
        cov = [(2, "chr1", i, i + 1) for i in range(2001)]
        cov.extend([(0, "chrY", i, i + 1) for i in range(10)])
        exact = PREP.select_gdna_tiles(cov[:2000])
        self.assertEqual(len(exact), 2000)
        selected = PREP.select_gdna_tiles(cov)
        self.assertEqual(len(selected), 2000)
        self.assertTrue(all(record[0] > 0 for record in selected))
        with self.assertRaisesRegex(RuntimeError, "1999 eligible, 2000 required"):
            PREP.select_gdna_tiles(cov[:1999])

    def test_only_chrY_may_be_absent_from_gdna_peak_contigs(self):
        self.assertEqual(PREP.missing_peak_contigs({"chr1", "chrY"}, {"chr1"}), ["chrY"])
        with self.assertRaisesRegex(RuntimeError, "chr2"):
            PREP.missing_peak_contigs({"chr1", "chr2"}, {"chr1"})

    def test_inputs_summary_records_missing_and_eligible_gdna_regions(self):
        with tempfile.TemporaryDirectory() as tmp:
            cov = [(1, "chr1", 10, 20), (0, "chrY", 30, 40), (0, "chr1", 50, 60)]
            selected = [(1, "chr1", 10, 20)]
            metrics = PREP.gdna_coverage_summary(cov, selected, {"chr1"}, ["chrY"])
            PREP.write_inputs_summary(tmp, metrics)
            observed = json.loads((pathlib.Path(tmp) / "inputs_summary.json").read_text())
            self.assertEqual(observed["gdna_missing_peak_contigs"], ["chrY"])
            self.assertEqual(observed["gdna_missing_contig_peak_count"], 1)
            self.assertEqual(observed["gdna_positive_coverage_regions"], 1)
            self.assertEqual(observed["gdna_selected_tiles"], 1)
            self.assertEqual(observed["gdna_observed_zero_regions"], 1)


if __name__ == "__main__":
    unittest.main()
