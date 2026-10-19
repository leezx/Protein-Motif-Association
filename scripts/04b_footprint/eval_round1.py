#!/usr/bin/env python3
"""Summarize native-threshold motif-free calls on the frozen round-1 regions.

The JSON spec maps each group to a BED of callable regions and caller names to
native event BED paths. This is a descriptive first-round audit; it cannot rank
accuracy without matched sensitivity and the B2/B3 truth sets.
"""
from __future__ import annotations

import argparse
import bisect
import hashlib
import json
from collections import defaultdict
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_bed(path: Path):
    with path.open("rt", encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            if not line.strip() or line.startswith("#"):
                continue
            fields = line.rstrip("\r\n").split("\t")
            if len(fields) < 3:
                raise ValueError(f"{path}:{number}: fewer than three BED columns")
            chrom, start, end = fields[0], int(fields[1]), int(fields[2])
            if not chrom or not 0 <= start < end:
                raise ValueError(f"{path}:{number}: invalid BED interval")
            yield chrom, start, end


def callable_intervals(path: Path):
    grouped = defaultdict(list)
    raw_count = 0
    for chrom, start, end in parse_bed(path):
        grouped[chrom].append((start, end))
        raw_count += 1
    merged = {}
    length = 0
    for chrom, rows in grouped.items():
        intervals = []
        for start, end in sorted(rows):
            if intervals and start <= intervals[-1][1]:
                intervals[-1] = (intervals[-1][0], max(end, intervals[-1][1]))
            else:
                intervals.append((start, end))
        merged[chrom] = (intervals, [start for start, _ in intervals])
        length += sum(end - start for start, end in intervals)
    if not raw_count or not length:
        raise ValueError(f"empty callable BED: {path}")
    return merged, raw_count, length


def intersects(chrom: str, start: int, end: int, regions) -> bool:
    if chrom not in regions:
        return False
    intervals, starts = regions[chrom]
    index = bisect.bisect_left(starts, end) - 1
    return index >= 0 and intervals[index][1] > start


def audit_events(path: Path, regions) -> dict[str, int | str]:
    rows = inside = outside = 0
    for chrom, start, end in parse_bed(path):
        rows += 1
        if intersects(chrom, start, end, regions):
            inside += 1
        else:
            outside += 1
    return {"native_event_rows": rows, "events_intersecting_callable_regions": inside,
            "events_outside_callable_regions": outside, "sha256": sha256_file(path)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    if any((parent / ".git").exists() for parent in (args.output.resolve().parent, *args.output.resolve().parents)):
        parser.error("report output must be outside a Git checkout")
    if args.output.exists():
        parser.error(f"refusing to overwrite existing report: {args.output}")
    if not isinstance(spec.get("groups"), dict) or set(spec["groups"]) != {"gdna", "ctrl", "aux"}:
        parser.error("spec must contain exactly gdna, ctrl, aux groups")
    report = {"schema_version": "pma.footprint.round1.native_density.v1",
              "interpretation": "Native thresholds only; B1 naked-DNA density is descriptive until sensitivity is matched. No accuracy winner inferred.",
              "groups": {}}
    for group, entry in spec["groups"].items():
        bed = Path(entry["regions"])
        regions, n_regions, bases = callable_intervals(bed)
        if n_regions != 2000:
            raise ValueError(f"{group}: expected 2000 frozen regions, got {n_regions}")
        callers = entry["callers"]
        if not isinstance(callers, dict) or not callers:
            raise ValueError(f"{group}: missing callers")
        results = {}
        for caller, file_name in callers.items():
            event_path = Path(file_name)
            result = audit_events(event_path, regions)
            result["event_bed"] = str(event_path.resolve())
            result["events_per_callable_mb"] = result["events_intersecting_callable_regions"] / (bases / 1_000_000)
            results[caller] = result
        report["groups"][group] = {"regions_bed": str(bed.resolve()), "regions_sha256": sha256_file(bed),
                                   "region_rows": n_regions, "callable_bases_union": bases,
                                   "callable_mb": bases / 1_000_000, "callers": results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({group: {caller: result["events_per_callable_mb"] for caller, result in value["callers"].items()}
                      for group, value in report["groups"].items()}, sort_keys=True))


if __name__ == "__main__":
    main()
