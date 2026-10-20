#!/usr/bin/env python3
"""Synthetic contract checks for the deterministic PRINT integration sample selector."""
import hashlib
import importlib.util
import os
import tempfile


SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scripts", "04b_footprint",
                      "select_print_integration_smoke.py")
SPEC = importlib.util.spec_from_file_location("select_print_smoke", SCRIPT)
SELECTOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SELECTOR)


def main():
    with tempfile.TemporaryDirectory(prefix="print-smoke-selector-") as tmp:
        source = os.path.join(tmp, "peaks.bed")
        output = os.path.join(tmp, "smoke.bed")
        mapping = os.path.join(tmp, "smoke.map.tsv")
        rows = []
        for chrom, width, count in (("chr1", 100, 3), ("chr1", 120, 2),
                                    ("chr2", 140, 2), ("chr2", 160, 1)):
            for i in range(count):
                start = 1000 + i * 500 + len(rows) * 10000
                rows.append("%s\t%d\t%d\tpeak%d" % (chrom, start, start + width, len(rows) + 1))
        with open(source, "w") as handle:
            handle.write("\n".join(rows) + "\n")
        digest = hashlib.sha256(open(source, "rb").read()).hexdigest()
        SELECTOR.FROZEN_BED_SHA256 = digest
        SELECTOR.main(["select_print_integration_smoke.py", source, output, mapping])
        with open(output) as handle:
            selected = [line.rstrip("\n") for line in handle]
        with open(mapping) as handle:
            map_rows = handle.read().splitlines()[1:]
        assert len(selected) == 8 and len(map_rows) == 8
        assert [int(row.split("\t")[1]) for row in map_rows] == [1, 4, 2, 6, 8, 5, 7, 3]
        assert [row.split("\t")[6] for row in map_rows] == [
            "group_1", "group_2", "group_1", "group_3",
            "group_4", "group_2", "group_3", "group_1"]
        assert [row.split("\t")[0] for row in selected] == [
            rows[i - 1].split("\t")[0] for i in (1, 4, 2, 6, 8, 5, 7, 3)]
        SELECTOR.FROZEN_BED_SHA256 = "0" * 64
        try:
            SELECTOR.main(["select_print_integration_smoke.py", source,
                           os.path.join(tmp, "bad.bed"), os.path.join(tmp, "bad.map.tsv")])
        except RuntimeError as error:
            assert "frozen full-peak BED SHA-256 mismatch" in str(error)
        else:
            raise AssertionError("selector accepted an incorrect frozen BED hash")
    print("PRINT smoke selector contract checks passed")


if __name__ == "__main__":
    main()
