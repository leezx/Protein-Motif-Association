#!/usr/bin/env python3
"""Build a coordinate-unique, source-traceable hg38 ChIP-Atlas BED6 reference.

This is an external-workspace builder. It never writes outputs into the repository.
All source rows receive one mutually exclusive primary status. Included rows are
externally sorted by coordinate/experiment/source-row, reduced to unique regions,
then source-row mappings are externally sorted to reconstruct lossless provenance.
Requires Python 3.10+, GNU sort, bgzip, and tabix.
"""
from __future__ import annotations

import argparse
import bisect
import collections
import gzip
import hashlib
import io
import json
import math
import os
import random
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Iterable, TextIO

CLASSES = ("TFs and others", "RNA polymerase", "Histone")
CLASS_BITS = {name: 1 << i for i, name in enumerate(CLASSES)}
STATUS_NAMES = (
    "MALFORMED_SOURCE_ROW",
    "INVALID_COORDINATE",
    "UNSUPPORTED_CHROM",
    "MISSING_METADATA",
    "AMBIGUOUS_METADATA",
    "OUT_OF_SCOPE_GENOME",
    "OUT_OF_SCOPE_CLASS",
    "INCLUDED_PAIR_FIRST",
    "INCLUDED_PAIR_ADDITIONAL",
)
OUTPUTS = (
    "PMA_chipatlas_hg38_unique_regions.bed.gz",
    "region_experiment.tsv.gz",
    "peak_provenance.tsv.gz",
    "region_summary.tsv.gz",
    "experiment_metadata.tsv.gz",
    "reconciliation.json",
    "tabix_query_qc.json",
    "region_id_collision_qc.json",
    "PMA_chipatlas_hg38_unique_regions.bed.gz.tbi",
    "MANIFEST.json",
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as src:
        for block in iter(lambda: src.read(8 << 20), b""):
            h.update(block)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def region_id(chrom: str, start: int, end: int) -> str:
    payload = "\t".join(("PMA-region-v1", "hg38", chrom, str(start), str(end))).encode("utf-8")
    return "PMA_hg38_" + sha256_bytes(payload)


def open_text_gz(path: Path) -> tuple[io.TextIOWrapper, io.BufferedWriter]:
    raw = path.open("wb")
    gz = gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=6, mtime=0)
    return io.TextIOWrapper(gz, encoding="utf-8", newline=""), raw


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def load_metadata(path: Path) -> tuple[dict[str, list[list[str]]], str]:
    """Read the pinned, headerless experimentList.tab; retain every raw field."""
    records: dict[str, list[list[str]]] = collections.defaultdict(list)
    with path.open("rt", encoding="utf-8", errors="replace", newline="") as src:
        for line in src:
            fields = line.rstrip("\r\n").split("\t")
            if len(fields) >= 3 and fields[0]:
                records[fields[0]].append(fields)
    return records, sha256_file(path)


def load_chrom_sizes(path: Path) -> tuple[dict[str, tuple[int, int]], str]:
    sizes: dict[str, tuple[int, int]] = {}
    for rank, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        fields = line.split()
        if len(fields) < 2:
            raise ValueError(f"malformed chrom.sizes line {rank + 1}")
        chrom, length = fields[0], int(fields[1])
        if chrom in sizes or length <= 0:
            raise ValueError(f"duplicate chromosome or invalid length at line {rank + 1}")
        sizes[chrom] = (rank, length)
    return sizes, sha256_file(path)


def reject_repo_output(path: Path) -> None:
    resolved = path.resolve()
    for parent in (resolved, *resolved.parents):
        if (parent / ".git").exists():
            raise ValueError(f"output/work path is inside a Git repository: {resolved}")


def run_sort(source: Path, target: Path, temp_dir: Path, buffer: str, workers: int, keys: list[str]) -> None:
    cmd = ["sort", "-t\t", "-S", buffer, "--parallel", str(workers), "-T", str(temp_dir), *keys, "-o", str(target), str(source)]
    subprocess.run(cmd, check=True)


def metadata_status(fields: list[str] | None) -> str:
    if fields is None:
        return "MISSING_METADATA"
    if len(fields) != 1:
        return "AMBIGUOUS_METADATA"
    row = fields[0]
    if len(row) < 3:
        return "MISSING_METADATA"
    if row[1] != "hg38":
        return "OUT_OF_SCOPE_GENOME"
    if row[2] not in CLASS_BITS:
        return "OUT_OF_SCOPE_CLASS"
    return "INCLUDED"


def iter_gzip_text(path: Path) -> Iterable[str]:
    with gzip.open(path, "rt", encoding="utf-8", errors="replace", newline="") as src:
        yield from src


def make_queries(chroms: dict[str, tuple[int, int]], count: int = 48) -> list[dict[str, object]]:
    """Choose deterministic random 1 kb windows over the hg38 assembly."""
    chrom_order = sorted(chroms, key=lambda chrom: chroms[chrom][0])
    cumulative: list[int] = []
    total = 0
    for chrom in chrom_order:
        total += chroms[chrom][1]
        cumulative.append(total)
    rng = random.Random(20261019)
    queries: list[dict[str, object]] = []
    for idx in range(count):
        point = rng.randrange(total)
        chrom_idx = bisect.bisect_right(cumulative, point)
        prior = cumulative[chrom_idx - 1] if chrom_idx else 0
        chrom = chrom_order[chrom_idx]
        length = chroms[chrom][1]
        start = point - prior
        end = min(length, start + 1000)
        queries.append({"id": idx + 1, "chrom": chrom, "start": start, "end": end, "expected": []})
    return queries


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--peaks", required=True, type=Path, help="pinned allPeaks_light.hg38.05.bed.gz")
    parser.add_argument("--metadata", required=True, type=Path, help="pinned experimentList.tab")
    parser.add_argument("--chrom-sizes", required=True, type=Path, help="hg38.chrom.sizes with canonical sort order")
    parser.add_argument("--output-dir", required=True, type=Path, help="new directory outside the Git checkout")
    parser.add_argument("--work-dir", required=True, type=Path, help="external scratch with enough space for sort files")
    parser.add_argument("--sort-buffer", default="4G", help="GNU sort memory buffer; default 4G")
    parser.add_argument("--sort-workers", type=int, default=2, help="GNU sort workers; default 2")
    args = parser.parse_args()

    peaks, metadata, chrom_sizes = args.peaks.resolve(), args.metadata.resolve(), args.chrom_sizes.resolve()
    outdir, workdir = args.output_dir.resolve(), args.work_dir.resolve()
    if args.sort_workers < 1:
        parser.error("--sort-workers must be positive")
    for path in (peaks, metadata, chrom_sizes):
        if not path.is_file():
            parser.error(f"input is not a file: {path}")
    reject_repo_output(outdir)
    reject_repo_output(workdir)
    if outdir.exists() and any(outdir.iterdir()):
        parser.error(f"output directory must be absent or empty: {outdir}")
    outdir.mkdir(parents=True, exist_ok=True)
    workdir.mkdir(parents=True, exist_ok=True)
    if shutil.which("sort") is None or shutil.which("bgzip") is None or shutil.which("tabix") is None:
        parser.error("GNU sort, bgzip, and tabix must be available in the approved external environment")

    metadata_rows, metadata_sha = load_metadata(metadata)
    chroms, chrom_sha = load_chrom_sizes(chrom_sizes)
    queries = make_queries(chroms)
    queries_by_chrom: dict[str, list[dict[str, object]]] = collections.defaultdict(list)
    for query in queries:
        queries_by_chrom[str(query["chrom"])].append(query)
    for items in queries_by_chrom.values():
        items.sort(key=lambda query: int(query["start"]))
    query_positions: collections.Counter[str] = collections.Counter()
    active_queries: dict[str, list[dict[str, object]]] = collections.defaultdict(list)
    archive_sha = sha256_file(peaks)
    counts: collections.Counter[str] = collections.Counter()
    rows_by_class: collections.Counter[str] = collections.Counter()
    rows_by_metadata_class_genome: collections.Counter[str] = collections.Counter()
    experiments_with_peaks: set[str] = set()
    class_experiments: collections.Counter[str] = collections.Counter()
    for eid, candidates in metadata_rows.items():
        if metadata_status(candidates) == "INCLUDED":
            class_experiments[candidates[0][2]] += 1

    with tempfile.TemporaryDirectory(prefix="pma-chipatlas-unique-", dir=workdir) as tmp:
        tmpdir = Path(tmp)
        unsorted = tmpdir / "eligible-coordinate-experiment-row.tsv"
        sorted_rows = tmpdir / "eligible-coordinate-experiment-row.sorted.tsv"
        row_map = tmpdir / "included-row-map.tsv"
        sorted_map = tmpdir / "included-row-map.sorted.tsv"
        with unsorted.open("wt", encoding="utf-8", newline="") as spool:
            for ordinal, line in enumerate(iter_gzip_text(peaks), start=1):
                fields = line.rstrip("\r\n").split("\t")
                status = None
                if len(fields) != 5:
                    status = "MALFORMED_SOURCE_ROW"
                else:
                    chrom, raw_start, raw_end, eid, raw_score = fields
                    candidates = metadata_rows.get(eid)
                    if candidates and len(candidates) == 1 and len(candidates[0]) >= 3:
                        meta_row = candidates[0]
                        rows_by_metadata_class_genome[f"{meta_row[1]}|{meta_row[2]}"] += 1
                    try:
                        start, end, qscore = int(raw_start), int(raw_end), float(raw_score)
                    except ValueError:
                        start = end = 0
                        qscore = math.nan
                    if not math.isfinite(qscore) or not (0 <= start < end):
                        status = "INVALID_COORDINATE"
                    elif chrom not in chroms:
                        status = "UNSUPPORTED_CHROM"
                    elif end > chroms[chrom][1]:
                        status = "INVALID_COORDINATE"
                    else:
                        mstatus = metadata_status(metadata_rows.get(eid))
                        if mstatus != "INCLUDED":
                            status = mstatus
                        else:
                            meta = metadata_rows[eid][0]
                            bit = CLASS_BITS[meta[2]]
                            spool.write(f"{chroms[chrom][0]}\t{chrom}\t{start}\t{end}\t{eid}\t{ordinal}\t{qscore:.17g}\t{bit}\n")
                            rows_by_class[meta[2]] += 1
                            experiments_with_peaks.add(eid)
                counts[status or "INCLUDED_CANDIDATE"] += 1

        # coordinate, experiment, source-row order: exact coordinates collapse once.
        run_sort(unsorted, sorted_rows, tmpdir, args.sort_buffer, args.sort_workers,
                 ["-k1,1n", "-k2,2", "-k3,3n", "-k4,4n", "-k5,5", "-k6,6n"])
        bed_plain = tmpdir / "regions.bed"
        id_ledger = tmpdir / "unique-region-id-coordinate.tsv"
        links_gz, links_raw = open_text_gz(outdir / "region_experiment.tsv.gz")
        summary_gz, summary_raw = open_text_gz(outdir / "region_summary.tsv.gz")
        links_gz.write("region_id\texperiment_id\n")
        summary_gz.write("region_id\tchrom\tstart\tend\tsupporting_experiments\tsource_peak_rows\tclass_mask\n")
        mask_counts: collections.Counter[int] = collections.Counter()
        n_regions = n_links = n_included_rows = 0
        n_multi_experiment_regions = 0
        with bed_plain.open("wt", encoding="utf-8", newline="") as bed, \
             id_ledger.open("wt", encoding="utf-8", newline="") as ids, \
             row_map.open("wt", encoding="utf-8", newline="") as mapping:
            group_key: tuple[str, int, int] | None = None
            rid = ""
            previous_eid: str | None = None
            support = source_rows = class_mask = 0
            def finish_group() -> None:
                nonlocal n_regions, n_links, n_multi_experiment_regions, group_key, rid, support, source_rows, class_mask
                if group_key is None:
                    return
                chrom, start, end = group_key
                bed_line = f"{chrom}\t{start}\t{end}\t{rid}\t{min(1000, support)}\t."
                bed.write(bed_line + "\n")
                ids.write(f"{rid}\t{chrom}\t{start}\t{end}\n")
                summary_gz.write(f"{rid}\t{chrom}\t{start}\t{end}\t{support}\t{source_rows}\t{class_mask}\n")
                mask_counts[class_mask] += 1
                n_regions += 1
                n_links += support
                if support > 1:
                    n_multi_experiment_regions += 1
                chrom_queries = queries_by_chrom.get(chrom, [])
                next_query = query_positions[chrom]
                while next_query < len(chrom_queries) and int(chrom_queries[next_query]["start"]) < end:
                    active_queries[chrom].append(chrom_queries[next_query])
                    next_query += 1
                query_positions[chrom] = next_query
                active_queries[chrom] = [query for query in active_queries[chrom]
                                         if int(query["end"]) > start]
                for query in active_queries[chrom]:
                    if int(query["start"]) < end and int(query["end"]) > start:
                        query["expected"].append(bed_line)

            with sorted_rows.open("rt", encoding="utf-8", newline="") as rows:
                for line in rows:
                    rank_s, chrom, start_s, end_s, eid, ordinal_s, qscore_s, bit_s = line.rstrip("\n").split("\t")
                    start, end, ordinal, bit = int(start_s), int(end_s), int(ordinal_s), int(bit_s)
                    key = (chrom, start, end)
                    if key != group_key:
                        finish_group()
                        group_key = key
                        rid = region_id(chrom, start, end)
                        previous_eid = None
                        support = source_rows = class_mask = 0
                    status = "INCLUDED_PAIR_FIRST" if eid != previous_eid else "INCLUDED_PAIR_ADDITIONAL"
                    if eid != previous_eid:
                        support += 1
                        class_mask |= bit
                        links_gz.write(f"{rid}\t{eid}\n")
                        previous_eid = eid
                    source_rows += 1
                    n_included_rows += 1
                    mapping.write(f"{ordinal}\t{rid}\t{eid}\t{status}\n")
            finish_group()
        links_gz.close(); links_raw.close()
        summary_gz.close(); summary_raw.close()

        # Release-level third external sort: exact verification of ID uniqueness.
        sorted_ids = tmpdir / "unique-region-id-coordinate.sorted.tsv"
        run_sort(id_ledger, sorted_ids, tmpdir, args.sort_buffer, args.sort_workers, ["-k1,1"])
        collision_count = 0
        duplicate_id_count = 0
        collision_examples = []
        last_id = None
        last_coord = None
        with sorted_ids.open("rt", encoding="utf-8", newline="") as ids:
            for line in ids:
                rid, chrom, start, end = line.rstrip("\n").split("\t")
                coord = [chrom, int(start), int(end)]
                if rid == last_id:
                    duplicate_id_count += 1
                    if coord != last_coord:
                        collision_count += 1
                        if len(collision_examples) < 20:
                            collision_examples.append({"region_id": rid, "first_coordinate": last_coord,
                                                       "colliding_coordinate": coord})
                last_id, last_coord = rid, coord
        collision_qc = {"checked_unique_region_ids": n_regions,
                        "unique_coordinate_keys": n_regions,
                        "duplicate_region_id_rows": duplicate_id_count,
                        "different_coordinate_hash_collisions": collision_count,
                        "collision_examples": collision_examples,
                        "status": "PASS" if duplicate_id_count == 0 else "FAIL"}
        write_json(outdir / "region_id_collision_qc.json", collision_qc)
        if duplicate_id_count != 0:
            raise RuntimeError("region_id uniqueness check failed; see region_id_collision_qc.json")

        run_sort(row_map, sorted_map, tmpdir, args.sort_buffer, args.sort_workers, ["-k1,1n"])
        provenance, provenance_raw = open_text_gz(outdir / "peak_provenance.tsv.gz")
        provenance.write("source_archive_sha256\tsource_row_ordinal\tregion_id\texperiment_id\tprimary_status\tchrom\tstart\tend\tsource_qscore\n")
        matched = 0
        with sorted_map.open("rt", encoding="utf-8", newline="") as mapping, gzip.open(
            peaks, "rt", encoding="utf-8", errors="replace", newline=""
        ) as source:
            pending = next(mapping, None)
            for ordinal, line in enumerate(source, start=1):
                if pending is None:
                    break
                map_fields = pending.rstrip("\n").split("\t")
                mapped_ordinal = int(map_fields[0])
                if mapped_ordinal < ordinal:
                    raise RuntimeError(f"source-row mapping was skipped at row {mapped_ordinal}")
                if mapped_ordinal > ordinal:
                    continue
                source_fields = line.rstrip("\r\n").split("\t")
                if len(source_fields) != 5:
                    raise RuntimeError(f"source changed between passes at row {ordinal}")
                chrom, start, end, eid, qscore = source_fields
                _, rid, map_eid, status = map_fields
                if eid != map_eid:
                    raise RuntimeError(f"source/mapping experiment mismatch at row {ordinal}")
                provenance.write(f"{archive_sha}\t{ordinal}\t{rid}\t{eid}\t{status}\t{chrom}\t{start}\t{end}\t{qscore}\n")
                matched += 1
                pending = next(mapping, None)
            if pending is not None:
                raise RuntimeError("included source-row mapping extends beyond source archive")
        provenance.close(); provenance_raw.close()
        if matched != n_included_rows or n_included_rows != counts["INCLUDED_CANDIDATE"]:
            raise RuntimeError("included-row accounting/provenance cardinality mismatch")

        # Exactly seven nonempty masks are possible for the three included classes; write zeros too.
        mask_report = {str(mask): mask_counts[mask] for mask in range(1, 1 << len(CLASSES))}
        if sum(mask_report.values()) != n_regions:
            raise RuntimeError("class-mask counts do not sum to global unique-region count")
        if any(mask not in mask_report for mask in mask_counts):
            raise RuntimeError("unexpected class-membership mask")

        bed_gz = outdir / OUTPUTS[0]
        with bed_gz.open("wb") as dst:
            subprocess.run(["bgzip", "-c", str(bed_plain)], check=True, stdout=dst)
        subprocess.run(["tabix", "-f", "-p", "bed", str(bed_gz)], check=True)

        query_results = []
        for query in queries:
            chrom = str(query["chrom"])
            start, end = int(query["start"]), int(query["end"])
            interval = f"{chrom}:{start + 1}-{end}"
            result = subprocess.run(["tabix", str(bed_gz), interval], check=True,
                                    capture_output=True, text=True, encoding="utf-8")
            observed = result.stdout.splitlines()
            expected = query["expected"]
            passed = observed == expected
            query_results.append({"id": query["id"], "interval_bed0": [chrom, start, end],
                                  "expected_hits": len(expected), "observed_hits": len(observed),
                                  "exact_match": passed})
            if not passed:
                raise RuntimeError(f"tabix query mismatch for {interval}")

    # Emit deterministic, complete metadata for all in-scope experiments, including zero-peak experiments.
    exp_path, exp_raw = open_text_gz(outdir / "experiment_metadata.tsv.gz")
    exp_path.write("experiment_id\tgenome\tantigen_class\tantigen\tmetadata_fields_json\n")
    for eid in sorted(metadata_rows):
        if metadata_status(metadata_rows[eid]) == "INCLUDED":
            row = metadata_rows[eid][0]
            exp_path.write(f"{eid}\t{row[1]}\t{row[2]}\t{row[3] if len(row) > 3 else ''}\t{json.dumps(row, ensure_ascii=False, separators=(',', ':'))}\n")
    exp_path.close(); exp_raw.close()

    expected_source_rows = sum(counts.values())
    counts["INCLUDED_PAIR_FIRST"] = n_links
    counts["INCLUDED_PAIR_ADDITIONAL"] = n_included_rows - n_links
    del counts["INCLUDED_CANDIDATE"]
    source_rows = sum(counts.values())
    if source_rows != expected_source_rows:
        raise RuntimeError(f"source row reconciliation failed: statuses={source_rows}, source={expected_source_rows}")
    reconciliation = {
        "source_archive_sha256": archive_sha,
        "source_rows": expected_source_rows,
        "primary_status_rows": dict(sorted(counts.items())),
        "included_source_rows": n_included_rows,
        "included_region_experiment_pairs": n_links,
        "unique_regions": n_regions,
        "source_rows_by_included_class": dict(sorted(rows_by_class.items())),
        "source_rows_by_metadata_genome_and_class": dict(sorted(rows_by_metadata_class_genome.items())),
        "metadata_experiments_by_included_class": dict(sorted(class_experiments.items())),
        "unique_regions_by_included_class": {
            name: sum(n for mask, n in mask_counts.items() if mask & CLASS_BITS[name]) for name in CLASSES
        },
        "metadata_experiments_without_included_peaks": sorted(
            eid for eid, rows in metadata_rows.items()
            if metadata_status(rows) == "INCLUDED" and eid not in experiments_with_peaks
        ),
        "region_class_membership_mask_counts": mask_report,
        "regions_with_multiple_experiments": n_multi_experiment_regions,
        "status_precedence": list(STATUS_NAMES),
    }
    if sum(reconciliation["primary_status_rows"].values()) != expected_source_rows:
        raise RuntimeError("mutually exclusive primary-status counts do not close")
    write_json(outdir / "reconciliation.json", reconciliation)
    query_qc = {"seed": 20261019, "query_count": len(query_results),
                "exact_matches": sum(bool(row["exact_match"]) for row in query_results),
                "queries": query_results}
    write_json(outdir / "tabix_query_qc.json", query_qc)

    outputs_hash = {name: sha256_file(outdir / name) for name in OUTPUTS if name != "MANIFEST.json"}
    manifest = {
        "schema_version": "pma.chipatlas.unique_bed6.v1",
        "assembly": "hg38",
        "classes_included": list(CLASSES),
        "deduplication_key": ["assembly", "chrom", "start", "end"],
        "coordinate_convention": "BED0, 0-based, half-open; exact-coordinate dedup only; no overlap merging",
        "region_id": "PMA_hg38_ + SHA256(UTF-8 tab-join of PMA-region-v1,hg38,chrom,start,end; no trailing newline)",
        "bed6_score": "min(1000, distinct supporting experiment IDs); exact count in region_summary.tsv.gz",
        "strand": ".",
        "primary_status_precedence": list(STATUS_NAMES),
        "source_files": {
            str(peaks): archive_sha,
            str(metadata): metadata_sha,
            str(chrom_sizes): chrom_sha,
        },
        "builder_commit": subprocess.run(["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip(),
        "builder": "scripts/04a_chipatlas/build_unique_bed6.py",
        "counts": {
            "source_rows": expected_source_rows,
            "included_source_rows": n_included_rows,
            "unique_regions": n_regions,
            "region_experiment_pairs": n_links,
        },
        "output_sha256": outputs_hash,
        "region_id_collision_qc": collision_qc,
        "external_data_only": True,
        "resource_notes": {"sort_buffer": args.sort_buffer, "sort_workers": args.sort_workers},
    }
    write_json(outdir / "MANIFEST.json", manifest)
    print(json.dumps({"status": "complete", "reconciliation": reconciliation,
                      "manifest": str(outdir / "MANIFEST.json")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
