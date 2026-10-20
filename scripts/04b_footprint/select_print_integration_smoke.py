#!/usr/bin/env python3
"""Select a deterministic, interleaved 8-row subset from the frozen peak BED."""
from __future__ import print_function

import gzip
import hashlib
import json
import os
import sys


FROZEN_BED_SHA256 = "c0c1d0b5350a962b9d7a7f1d2edef1ca98005029c79f07979533f3a14cb40945"
TARGET_COUNTS = (3, 2, 2, 1)
MIN_WIDTH = 100


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_rows(path):
    opener = gzip.open if path.endswith(".gz") else open
    groups = {}
    with opener(path, "rt") as handle:
        for row_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            fields = line.rstrip("\r\n").split("\t")
            if len(fields) < 3:
                raise RuntimeError("BED row %d has fewer than three columns" % row_number)
            try:
                start, end = int(fields[1]), int(fields[2])
            except ValueError:
                raise RuntimeError("BED row %d has non-integer coordinates" % row_number)
            width = end - start
            if start < 0 or width < MIN_WIDTH:
                continue
            key = (fields[0], width)
            groups.setdefault(key, []).append((row_number, line.rstrip("\r\n")))
    return groups


def choose_groups(groups):
    ordered = sorted(groups, key=lambda key: groups[key][0][0])
    large = [key for key in ordered if len(groups[key]) >= 3]
    medium = [key for key in ordered if len(groups[key]) >= 2]
    for a in large:
        for b in medium:
            if b == a or b[1] == a[1]:
                continue
            for c in medium:
                if c in (a, b) or c[1] in (a[1], b[1]):
                    continue
                for d in ordered:
                    if d in (a, b, c):
                        continue
                    if len({a[0], b[0], c[0], d[0]}) < 2:
                        continue
                    return (a, b, c, d)
    raise RuntimeError("frozen BED lacks groups for 3/2/2/1, three widths, and two chromosomes")


def main(argv):
    if len(argv) != 4:
        raise RuntimeError("usage: select_print_integration_smoke.py frozen.bed[.gz] output.bed map.tsv")
    source, output, mapping = argv[1:]
    if os.path.exists(output) or os.path.exists(mapping):
        raise RuntimeError("refusing to overwrite smoke BED or mapping")
    source_sha = sha256(source)
    if source_sha != FROZEN_BED_SHA256:
        raise RuntimeError("frozen full-peak BED SHA-256 mismatch")
    groups = read_rows(source)
    selected_groups = choose_groups(groups)
    # Interleave group rows so exact-width grouping must restore noncontiguous
    # original row indices: A1,B1,A2,C1,D1,B2,C2,A3.
    pattern = ((0, 0), (1, 0), (0, 1), (2, 0), (3, 0), (1, 1), (2, 1), (0, 2))
    selected = []
    for output_index, (group_number, within_group) in enumerate(pattern, 1):
        key = selected_groups[group_number]
        source_row, line = groups[key][within_group]
        chrom, start, end = line.split("\t", 3)[:3]
        selected.append({"output_index": output_index, "source_row_1based": source_row,
                         "chrom": chrom, "start": int(start), "end": int(end),
                         "width": int(end) - int(start),
                         "group": "group_%d" % (group_number + 1),
                         "bed_line": line})
    if len({item["chrom"] for item in selected}) < 2 or len({item["width"] for item in selected}) < 3:
        raise RuntimeError("selected rows do not meet chromosome/width diversity contract")
    with open(output, "x") as bed_out, open(mapping, "x") as map_out:
        map_out.write("output_index\tsource_row_1based\tchrom\tstart\tend\twidth\tgroup\n")
        for item in selected:
            bed_out.write(item["bed_line"] + "\n")
            map_out.write("%d\t%d\t%s\t%d\t%d\t%d\t%s\n" % (
                item["output_index"], item["source_row_1based"], item["chrom"],
                item["start"], item["end"], item["width"], item["group"]))
    report = {"source_bed_sha256": source_sha, "eligible_rows_seen": sum(map(len, groups.values())),
              "selected_rows": 8, "group_sizes": list(TARGET_COUNTS),
              "chromosomes": sorted({item["chrom"] for item in selected}),
              "widths": sorted({item["width"] for item in selected}),
              "output_bed_sha256": sha256(output), "mapping_sha256": sha256(mapping)}
    sys.stdout.write(json.dumps(report, sort_keys=True) + "\n")


if __name__ == "__main__":
    try:
        main(sys.argv)
    except Exception as error:
        sys.stderr.write("SELECT_FAIL: %s\n" % error)
        sys.exit(2)
