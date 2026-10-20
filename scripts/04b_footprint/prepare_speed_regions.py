#!/usr/bin/env python3
"""Freeze K562 peak-centred 1-kb speed windows plus off-peak controls.

Use the same signal-ranked de-overlap convention as 01_prep_inputs.py.
All I/O paths must be in external data/work space, never inside the Git repo.
"""
from __future__ import annotations

import argparse
import bisect
import gzip
import hashlib
import json
import random
from collections import Counter, defaultdict
from pathlib import Path


def open_text(path: Path):
    return gzip.open(path, "rt") if path.suffix == ".gz" else path.open("rt")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def merged_intervals(rows):
    merged = []
    for start, end in sorted(rows):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return merged


def overlaps(rows, start, end):
    i = bisect.bisect_left(rows, (start, end))
    return (i > 0 and rows[i - 1][1] > start) or (i < len(rows) and rows[i][0] < end)


def reject_repo(path: Path):
    resolved = path.resolve()
    if any((parent / ".git").exists() for parent in (resolved, *resolved.parents)):
        raise ValueError(f"analysis file may not be inside Git checkout: {path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--peaks", required=True, type=Path)
    parser.add_argument("--blacklist", required=True, type=Path)
    parser.add_argument("--chrom-sizes", required=True, type=Path)
    parser.add_argument("--out-bed", required=True, type=Path)
    parser.add_argument("--out-json", required=True, type=Path)
    parser.add_argument("--negative-windows", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=20261019)
    args = parser.parse_args()
    for path in (args.peaks, args.blacklist, args.chrom_sizes, args.out_bed, args.out_json):
        reject_repo(path)
    if args.out_bed.exists() or args.out_json.exists():
        parser.error("refusing to overwrite a frozen output")
    chroms = {}
    for line in args.chrom_sizes.read_text().splitlines():
        chrom, size = line.split()[:2]
        if chrom in {f"chr{i}" for i in range(1, 23)} | {"chrX", "chrY"}:
            chroms[chrom] = int(size)
    if len(chroms) != 24:
        parser.error("expected all 22 autosomes and X/Y in chrom sizes")
    black = defaultdict(list)
    with open_text(args.blacklist) as handle:
        for line in handle:
            fields = line.split()
            if len(fields) >= 3 and fields[0] in chroms:
                black[fields[0]].append((int(fields[1]), int(fields[2])))
    black = {chrom: merged_intervals(rows) for chrom, rows in black.items()}

    counts = Counter()
    candidates = []
    peak_intervals = defaultdict(list)
    with open_text(args.peaks) as handle:
        for line in handle:
            counts["source_peak_rows"] += 1
            fields = line.split()
            if len(fields) < 10 or fields[0] not in chroms:
                counts["noncanonical_or_malformed"] += 1
                continue
            chrom, pstart, pend = fields[0], int(fields[1]), int(fields[2])
            if not (0 <= pstart < pend <= chroms[chrom]):
                counts["invalid_peak_coordinate"] += 1
                continue
            peak_intervals[chrom].append((pstart, pend))
            summit = int(fields[9])
            if summit < 0 or pstart + summit >= pend:
                counts["invalid_summit"] += 1
                continue
            centre = pstart + summit
            start, end = centre - 500, centre + 500
            if start < 0 or end > chroms[chrom]:
                counts["boundary"] += 1
                continue
            candidates.append((float(fields[6]), chrom, start, end))
    peak_intervals = {chrom: merged_intervals(rows) for chrom, rows in peak_intervals.items()}
    candidates.sort(key=lambda item: -item[0])
    kept = defaultdict(list)
    for _, chrom, start, end in candidates:
        if overlaps(black.get(chrom, []), start, end):
            counts["blacklist_excluded"] += 1
        elif overlaps(kept[chrom], start, end):
            counts["overlapping_lower_signal_excluded"] += 1
        else:
            bisect.insort(kept[chrom], (start, end))
            counts["accessible_windows"] += 1

    rng = random.Random(args.seed)
    canonical = [f"chr{i}" for i in range(1, 23)] + ["chrX", "chrY"]
    weights = [chroms[chrom] for chrom in canonical]
    negatives = defaultdict(list)
    attempts = 0
    while sum(len(rows) for rows in negatives.values()) < args.negative_windows:
        attempts += 1
        if attempts > args.negative_windows * 1000:
            raise RuntimeError("could not obtain enough disjoint off-peak windows")
        chrom = rng.choices(canonical, weights=weights)[0]
        start = rng.randrange(chroms[chrom] - 1000)
        end = start + 1000
        if (overlaps(peak_intervals.get(chrom, []), start, end)
                or overlaps(black.get(chrom, []), start, end)
                or overlaps(kept[chrom], start, end)
                or overlaps(negatives[chrom], start, end)):
            continue
        bisect.insort(negatives[chrom], (start, end))
    counts["offpeak_windows"] = args.negative_windows
    counts["negative_draw_attempts"] = attempts

    args.out_bed.parent.mkdir(parents=True, exist_ok=True)
    with args.out_bed.open("wt") as out:
        for chrom in canonical:
            rows = [(start, end, "P") for start, end in kept[chrom]]
            rows.extend((start, end, "N") for start, end in negatives[chrom])
            for start, end, label in sorted(rows):
                out.write(f"{chrom}\t{start}\t{end}\t{label}_{chrom}_{start:09d}\n")
    report = {"schema_version": "pma.footprint.speed_regions.v1",
              "source_peak_accession": "ENCFF993BAP", "sample_bam_accession": "ENCFF534DCE",
              "window_rule": "summit +/- 500 bp; signal-descending greedy non-overlap; canonical chromosomes; blacklist-excluded",
              "offpeak_rule": "seeded 1-kb uniform genomic windows, disjoint from all source peaks, blacklist and accepted windows",
              "seed": args.seed, "counts": dict(counts),
              "source_sha256": {str(args.peaks): sha256(args.peaks), str(args.blacklist): sha256(args.blacklist),
                                str(args.chrom_sizes): sha256(args.chrom_sizes)},
              "bed_sha256": sha256(args.out_bed)}
    args.out_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"counts": report["counts"], "bed_sha256": report["bed_sha256"]}, sort_keys=True))


if __name__ == "__main__":
    main()
