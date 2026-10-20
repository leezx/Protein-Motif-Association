#!/usr/bin/env python3
"""Select 64 deterministic midpoint-quantile rows from the frozen K562 peak BED."""
from __future__ import print_function

import gzip
import hashlib
import json
import os
import sys


SOURCE_SHA256 = "c0c1d0b5350a962b9d7a7f1d2edef1ca98005029c79f07979533f3a14cb40945"
EXPECTED_SOURCE_ROWS = 159628
SAMPLE_SIZE = 64
MIN_WIDTH = 1


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_frozen_rows(path):
    opener = gzip.open if path.endswith(".gz") else open
    rows = []
    with opener(path, "rt") as handle:
        for row_number, line in enumerate(handle, 1):
            line = line.rstrip("\r\n")
            if not line:
                continue
            fields = line.split("\t")
            if len(fields) < 3:
                raise RuntimeError("BED row %d has fewer than three columns" % row_number)
            try:
                start, end = int(fields[1]), int(fields[2])
            except ValueError:
                raise RuntimeError("BED row %d has non-integer coordinates" % row_number)
            if not fields[0] or start < 0 or end <= start or end - start < MIN_WIDTH:
                raise RuntimeError("BED row %d has an invalid interval" % row_number)
            rows.append((row_number, line, fields[0], start, end))
    return rows


def select_quantiles(rows):
    if len(rows) != EXPECTED_SOURCE_ROWS:
        raise RuntimeError("expected %d source rows, found %d" %
                           (EXPECTED_SOURCE_ROWS, len(rows)))
    # Midpoint quantiles span the full immutable BED row order without a random seed.
    indices = [((2 * i + 1) * len(rows)) // (2 * SAMPLE_SIZE)
               for i in range(SAMPLE_SIZE)]
    if len(set(indices)) != SAMPLE_SIZE or indices[0] < 0 or indices[-1] >= len(rows):
        raise RuntimeError("quantile selector did not produce 64 unique in-range indices")
    return [rows[index] for index in indices]


def main(argv):
    if len(argv) != 4:
        raise RuntimeError("usage: select_print_speed64.py source.bed.gz output.bed map.tsv")
    source, output, mapping = argv[1:]
    if os.path.exists(output) or os.path.exists(mapping):
        raise RuntimeError("refusing to overwrite selected BED or row map")
    source_sha = sha256(source)
    if source_sha != SOURCE_SHA256:
        raise RuntimeError("frozen K562 peak BED SHA-256 mismatch")
    rows = read_frozen_rows(source)
    selected = select_quantiles(rows)
    selected_chroms = {}
    selected_widths = []
    for _, _, chrom, start, end in selected:
        selected_chroms[chrom] = selected_chroms.get(chrom, 0) + 1
        selected_widths.append(end - start)
    if len(selected_chroms) < 2:
        raise RuntimeError("quantile sample covers fewer than two chromosomes")
    with open(output, "x") as bed_out, open(mapping, "x") as map_out:
        map_out.write("sample_index\tsource_row_1based\tchrom\tstart\tend\twidth\n")
        for sample_index, (source_row, line, chrom, start, end) in enumerate(selected, 1):
            bed_out.write(line + "\n")
            map_out.write("%d\t%d\t%s\t%d\t%d\t%d\n" %
                          (sample_index, source_row, chrom, start, end, end - start))
    ordered_widths = sorted(selected_widths)
    median_width = (ordered_widths[31] + ordered_widths[32]) / 2.0
    summary = {
        "selection": "64 midpoint quantiles of frozen BED row order; no filtering or interval edits",
        "source_bed_sha256": source_sha,
        "source_rows": len(rows),
        "selected_rows": len(selected),
        "source_row_indices_1based": [item[0] for item in selected],
        "chromosome_counts": dict(sorted(selected_chroms.items())),
        "selected_interval_bp_sum": sum(selected_widths),
        "selected_width_bp_min": min(selected_widths),
        "selected_width_bp_median": median_width,
        "selected_width_bp_max": max(selected_widths),
        "selected_bed_sha256": sha256(output),
        "row_map_sha256": sha256(mapping),
    }
    sys.stdout.write(json.dumps(summary, sort_keys=True) + "\n")


if __name__ == "__main__":
    try:
        main(sys.argv)
    except Exception as error:
        sys.stderr.write("SELECT_FAIL: %s\n" % error)
        sys.exit(2)
