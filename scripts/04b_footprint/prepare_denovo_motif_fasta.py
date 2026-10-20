#!/usr/bin/env python3
"""Prepare same-window, GC-matched exploratory footprint/background FASTA.

One highest-scoring footprint per 1-kb accessible window prevents a dense
window from acting as many independent examples. This is B4 exploration,
not a benchmark truth set or a finished motif reference.
"""

import argparse
import hashlib
import json
from bisect import bisect_right
from collections import defaultdict
from pathlib import Path

import pysam


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read_regions(path):
    regions = defaultdict(list)
    with open(path) as handle:
        for line in handle:
            if not line.strip() or line.startswith("#"):
                continue
            fields = line.rstrip("\n").split("\t")
            chrom, start, end = fields[0], int(fields[1]), int(fields[2])
            if end - start != 1000:
                raise ValueError(f"expected 1-kb window: {line.rstrip()}")
            regions[chrom].append((start, end, fields[3]))
    for chrom in regions:
        regions[chrom].sort()
        for left, right in zip(regions[chrom], regions[chrom][1:]):
            if left[1] > right[0]:
                raise ValueError(f"overlapping windows on {chrom}")
    return regions


def gc(seq):
    return (seq.count("G") + seq.count("C")) / len(seq)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--regions", required=True)
    parser.add_argument("--events", required=True)
    parser.add_argument("--fasta", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--score-column", type=int, required=True,
                        help="1-based BED score column")
    parser.add_argument("--max-gc-delta", type=float, default=0.1)
    parser.add_argument("--background-exclusion", choices=("all_calls", "selected_only"),
                        default="all_calls",
                        help="selected_only permits other native calls in backgrounds; "
                             "use consistently across callers when calls saturate windows")
    args = parser.parse_args()
    if args.score_column < 4 or not 0 <= args.max_gc_delta <= 1:
        parser.error("invalid score column or GC delta")
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=False)
    regions = read_regions(args.regions)
    starts = {chrom: [r[0] for r in rows] for chrom, rows in regions.items()}
    per_region = defaultdict(list)
    n_events = 0
    with open(args.events) as handle:
        for line in handle:
            if not line.strip() or line.startswith("#"):
                continue
            fields = line.rstrip("\n").split("\t")
            chrom, start, end = fields[0], int(fields[1]), int(fields[2])
            if end <= start or len(fields) < args.score_column:
                raise ValueError(f"bad event row: {line.rstrip()}")
            if chrom not in regions:
                continue
            idx = bisect_right(starts[chrom], start) - 1
            if idx < 0:
                continue
            region = regions[chrom][idx]
            if start < region[0] or end > region[1]:
                continue
            score = float(fields[args.score_column - 1])
            center = (start + end) // 2
            per_region[(chrom, idx)].append((score, center, start, end))
            n_events += 1
    fasta = pysam.FastaFile(args.fasta)
    positives = []
    negatives = []
    metadata = []
    rejected = defaultdict(int)
    for (chrom, idx), calls in sorted(per_region.items()):
        start, end, region_id = regions[chrom][idx]
        calls.sort(reverse=True)
        score, center, ev_start, ev_end = calls[0]
        pos_start = center - 25
        if pos_start < start or pos_start + 50 > end:
            rejected["positive_outside_window"] += 1
            continue
        window = fasta.fetch(chrom, start, end).upper()
        positive = window[pos_start - start:pos_start - start + 50]
        if len(positive) != 50 or set(positive) - set("ACGT"):
            rejected["positive_non_acgt"] += 1
            continue
        pos_gc = gc(positive)
        candidates = []
        exclusion_calls = calls if args.background_exclusion == "all_calls" else [(score, center, ev_start, ev_end)]
        for neg_start in range(start + 25, end - 75, 10):
            neg_end = neg_start + 50
            if any(neg_start < e + 25 and neg_end > s - 25
                   for _, _, s, e in exclusion_calls):
                continue
            negative = window[neg_start - start:neg_end - start]
            if len(negative) != 50 or set(negative) - set("ACGT"):
                continue
            delta = abs(gc(negative) - pos_gc)
            candidates.append((delta, neg_start, negative))
        if not candidates:
            rejected["no_background"] += 1
            continue
        delta, neg_start, negative = min(candidates)
        if delta > args.max_gc_delta:
            rejected["gc_mismatch"] += 1
            continue
        name = f"{region_id}|{chrom}:{pos_start}-{pos_start + 50}"
        positives.append((name, positive))
        negatives.append((f"{region_id}|{chrom}:{neg_start}-{neg_start + 50}", negative))
        metadata.append((region_id, chrom, pos_start, pos_start + 50,
                         neg_start, neg_start + 50, score, pos_gc,
                         gc(negative), len(calls)))
    fasta.close()
    if not positives:
        raise RuntimeError("no GC-matched footprint/background pairs")
    for filename, records in (("positive.fa", positives), ("background.fa", negatives)):
        with open(output / filename, "w") as handle:
            for name, seq in records:
                handle.write(f">{name}\n{seq}\n")
    with open(output / "pairs.tsv", "w") as handle:
        handle.write("region_id\tchrom\tpositive_start\tpositive_end\tbackground_start\tbackground_end\tscore\tpositive_gc\tbackground_gc\tregion_event_count\n")
        for row in metadata:
            handle.write("\t".join(map(str, row)) + "\n")
    manifest = {
        "purpose": "exploratory_B4_only", "sequence_length": 50,
        "selection": "highest_score_event_per_1kb_accessible_window",
        "background": "same_window_gc_matched",
        "background_exclusion": args.background_exclusion,
        "max_gc_delta": args.max_gc_delta, "contained_events": n_events,
        "windows_with_events": len(per_region), "pairs": len(positives),
        "rejected": dict(rejected), "score_column": args.score_column,
        "inputs_sha256": {key: sha256(getattr(args, key)) for key in ("regions", "events", "fasta")},
        "outputs_sha256": {name: sha256(output / name) for name in ("positive.fa", "background.fa", "pairs.tsv")},
    }
    with open(output / "manifest.json", "w") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(json.dumps(manifest, sort_keys=True))


if __name__ == "__main__":
    main()
