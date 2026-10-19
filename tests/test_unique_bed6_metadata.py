"""Regression checks for ChIP-Atlas experiment IDs listed on two assemblies."""

import importlib.util
import pathlib
import unittest


SOURCE = pathlib.Path(__file__).resolve().parents[1] / "scripts/04a_chipatlas/build_unique_bed6.py"
SPEC = importlib.util.spec_from_file_location("build_unique_bed6", SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class MetadataSelectionTest(unittest.TestCase):
    def test_same_accession_hg19_and_hg38_selects_hg38(self):
        rows = [["SRX1", "hg19", "Histone"], ["SRX1", "hg38", "TFs and others"]]
        self.assertEqual(MODULE.metadata_status(rows), "INCLUDED")
        self.assertEqual(MODULE.hg38_metadata_row(rows), rows[1])

    def test_two_hg38_records_remain_ambiguous(self):
        rows = [["SRX1", "hg38", "Histone"], ["SRX1", "hg38", "TFs and others"]]
        self.assertEqual(MODULE.metadata_status(rows), "AMBIGUOUS_METADATA")
        self.assertIsNone(MODULE.hg38_metadata_row(rows))

    def test_non_hg38_and_excluded_class(self):
        self.assertEqual(MODULE.metadata_status([["SRX1", "hg19", "Histone"]]), "OUT_OF_SCOPE_GENOME")
        self.assertEqual(MODULE.metadata_status([["SRX1", "hg38", "ATAC-Seq"]]), "OUT_OF_SCOPE_CLASS")
        self.assertEqual(MODULE.metadata_status(None), "MISSING_METADATA")


if __name__ == "__main__":
    unittest.main()
