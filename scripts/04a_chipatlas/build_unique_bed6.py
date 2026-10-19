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
import itertools
import json
import math
import os
import random
import re
import resource
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


def require_gridengine_memory_limit() -> dict[str, int | str]:
    """Require one Argos task with a finite 44-GiB address-space limit."""
    maximum = 44 * (1 << 30)
    try:
        job_id = os.environ.get("JOB_ID", "")
        slots = os.environ.get("NSLOTS", "")
        background = os.environ.get("PMA_BACKGROUND_EXECUTION") == "1"
        if slots != "1" or not (job_id.isdecimal() or (background and job_id.startswith("BG_BED6_"))):
            raise ValueError(f"expected one Grid Engine slot or capped Argos background task, got JOB_ID={job_id!r}, NSLOTS={slots!r}")
        if not hasattr(resource, "RLIMIT_AS"):
            raise ValueError("RLIMIT_AS is unavailable")
        soft, hard = resource.getrlimit(resource.RLIMIT_AS)
        if any(value == resource.RLIM_INFINITY or value <= 0 or value > maximum for value in (soft, hard)):
            raise ValueError(f"RLIMIT_AS soft/hard must be finite and <=44 GiB, got {(soft, hard)!r}")
        if soft > hard:
            raise ValueError(f"RLIMIT_AS soft limit exceeds hard limit: {(soft, hard)!r}")
        if not background:
            qstat = subprocess.run(["qstat", "-j", job_id], check=True, capture_output=True, text=True,
                                   encoding="utf-8", timeout=10).stdout
            if not re.search(r"(?:^|[,\s])h_vmem=44G(?:[,\s]|$)", qstat):
                raise ValueError("qstat does not confirm the exact hard request h_vmem=44G")
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        raise RuntimeError(f"required Grid Engine h_vmem/RLIMIT_AS guard unavailable or invalid: {exc}") from exc
    return {"mode": "argos_background_rlimit_as" if background else "gridengine_h_vmem_single_slot_plus_rlimit_as", "job_id": job_id, "slots": 1,
            "rlimit_as_soft_bytes": int(soft), "rlimit_as_hard_bytes": int(hard),
            "memory_cap_bytes": maximum}


def load_metadata(path: Path) -> tuple[dict[str, list[list[str]]], str]:
    """Read the pinned, headerless experimentList.tab; retain every raw field."""
    records: dict[str, list[list[str]]] = collections.defaultdict(list)
    with path.open("rt", encoding="utf-8", errors="strict", newline="") as src:
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
    subprocess.run(cmd, check=True, env={**os.environ, "LC_ALL": "C"})


def tool_version(command: list[str]) -> str:
    result = subprocess.run(command, check=True, capture_output=True, text=True, encoding="utf-8")
    return result.stdout.splitlines()[0] if result.stdout else result.stderr.splitlines()[0]


def validate_emitted_sidecars(outdir: Path, archive_sha: str, regions: int, links_expected: int,
                               included_rows: int, status_counts: collections.Counter[str],
                               chromosome_order: dict[str, tuple[int, int]]) -> dict[str, object]:
    """Sequentially reconcile complete emitted files; gzip reads also verify CRCs."""
    bed_path = outdir / OUTPUTS[0]
    summary_path = outdir / "region_summary.tsv.gz"
    links_path = outdir / "region_experiment.tsv.gz"
    provenance_path = outdir / "peak_provenance.tsv.gz"
    summary_rows = link_rows = 0
    summary_source_rows = 0
    previous_coordinate: tuple[int, int, int] | None = None
    with gzip.open(bed_path, "rt", encoding="utf-8", errors="strict", newline="") as bed, \
         gzip.open(summary_path, "rt", encoding="utf-8", errors="strict", newline="") as summary, \
         gzip.open(links_path, "rt", encoding="utf-8", errors="strict", newline="") as links:
        if next(summary, None) != "region_id\tchrom\tstart\tend\tsupporting_experiments\tsource_peak_rows\tclass_mask\n":
            raise RuntimeError("region summary header mismatch")
        if next(links, None) != "region_id\texperiment_id\n":
            raise RuntimeError("region-experiment header mismatch")
        for row_number, (bed_line, summary_line) in enumerate(
                itertools.zip_longest(bed, summary, fillvalue=None), start=1):
            if bed_line is None or summary_line is None:
                raise RuntimeError(f"BED6 and region summary row counts differ at row {row_number}")
            b = bed_line.rstrip("\r\n").split("\t")
            s = summary_line.rstrip("\r\n").split("\t")
            if len(b) != 6 or len(s) != 7:
                raise RuntimeError(f"BED/summary field count mismatch at region {row_number}")
            chrom, start, end, rid, score, strand = b
            srid, schrom, sstart, send, support_s, source_s, mask_s = s
            start_i, end_i, support, source_count, class_mask = map(int, (start, end, support_s, source_s, mask_s))
            if (rid != srid or rid != region_id(chrom, start_i, end_i)
                    or chrom not in chromosome_order
                    or not (0 <= start_i < end_i <= chromosome_order[chrom][1])
                    or chrom != schrom or start_i != int(sstart) or end_i != int(send)
                    or strand != "." or int(score) != min(1000, support) or support < 1
                    or source_count < support or not 1 <= class_mask <= 7):
                raise RuntimeError(f"BED6 and region summary disagree at row {row_number}")
            coordinate = (chromosome_order[chrom][0], start_i, end_i)
            if previous_coordinate is not None and coordinate <= previous_coordinate:
                raise RuntimeError(f"region coordinates duplicate or out of order at row {row_number}")
            previous_coordinate = coordinate
            seen_experiments: set[str] = set()
            prior_experiment = ""
            for _ in range(support):
                pair = next(links, None)
                if pair is None:
                    raise RuntimeError("region-experiment sidecar ended before declared support count")
                pair_fields = pair.rstrip("\r\n").split("\t")
                if len(pair_fields) != 2 or pair_fields[0] != rid:
                    raise RuntimeError(f"region-experiment rows do not match region {rid}")
                eid = pair_fields[1]
                if eid in seen_experiments or (prior_experiment and eid <= prior_experiment):
                    raise RuntimeError(f"duplicate or unordered experiment linkage for {rid}")
                seen_experiments.add(eid)
                prior_experiment = eid
                link_rows += 1
            summary_source_rows += source_count
            summary_rows += 1
        if next(bed, None) is not None or next(summary, None) is not None or next(links, None) is not None:
            raise RuntimeError("BED, summary, or linkage sidecar has trailing/unmatched rows")

    provenance_rows = 0
    provenance_statuses: collections.Counter[str] = collections.Counter()
    last_ordinal = 0
    with gzip.open(provenance_path, "rt", encoding="utf-8", errors="strict", newline="") as src:
        if next(src, None) != "source_archive_sha256\tsource_row_ordinal\tregion_id\texperiment_id\tprimary_status\tchrom\tstart\tend\tsource_qscore\n":
            raise RuntimeError("peak provenance header mismatch")
        for line in src:
            fields = line.rstrip("\r\n").split("\t")
            if len(fields) != 9:
                raise RuntimeError(f"peak provenance field count mismatch at row {provenance_rows + 1}")
            digest, ordinal_s, rid, eid, status, chrom, start_s, end_s, qscore_s = fields
            ordinal, start, end = int(ordinal_s), int(start_s), int(end_s)
            if (digest != archive_sha or ordinal <= last_ordinal or not eid
                    or status not in {"INCLUDED_PAIR_FIRST", "INCLUDED_PAIR_ADDITIONAL"}
                    or rid != region_id(chrom, start, end) or not math.isfinite(float(qscore_s))
                    or not (0 <= start < end)):
                raise RuntimeError(f"invalid peak provenance row {provenance_rows + 1}")
            last_ordinal = ordinal
            provenance_statuses[status] += 1
            provenance_rows += 1
    if (summary_rows != regions or link_rows != links_expected or provenance_rows != included_rows
            or summary_source_rows != included_rows
            or provenance_statuses["INCLUDED_PAIR_FIRST"] != links_expected
            or sum(provenance_statuses.values()) != sum(status_counts[k] for k in provenance_statuses)):
        raise RuntimeError("emitted sidecars fail row-count reconciliation")
    return {"status": "PASS", "method": "full sequential read and cross-file reconciliation",
            "regions_checked": summary_rows, "region_experiment_links_checked": link_rows,
            "source_provenance_rows_checked": provenance_rows,
            "summary_source_peak_rows_sum": summary_source_rows,
            "provenance_status_counts": dict(sorted(provenance_statuses.items())),
            "gzip_crc_checked": True}


def hg38_metadata_row(fields: list[list[str]] | None) -> list[str] | None:
    """Select the unique hg38 record for an experiment also listed on hg19."""
    if not fields:
        return None
    matches = [row for row in fields if len(row) >= 3 and row[1] == "hg38"]
    return matches[0] if len(matches) == 1 else None


def metadata_status(fields: list[list[str]] | None) -> str:
    if not fields:
        return "MISSING_METADATA"
    hg38_rows = [row for row in fields if len(row) >= 3 and row[1] == "hg38"]
    if len(hg38_rows) > 1:
        return "AMBIGUOUS_METADATA"
    if not hg38_rows:
        if any(len(row) < 3 for row in fields):
            return "MISSING_METADATA"
        return "OUT_OF_SCOPE_GENOME"
    row = hg38_rows[0]
    if row[2] not in CLASS_BITS:
        return "OUT_OF_SCOPE_CLASS"
    return "INCLUDED"


def iter_gzip_text(path: Path) -> Iterable[str]:
    with gzip.open(path, "rt", encoding="utf-8", errors="strict", newline="") as src:
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
    parser.add_argument("--metadata-release", required=True,
                        help="explicit ChIP-Atlas release identifier for experimentList.tab")
    parser.add_argument("--chrom-sizes", required=True, type=Path, help="hg38.chrom.sizes with canonical sort order")
    parser.add_argument("--output-dir", required=True, type=Path, help="new directory outside the Git checkout")
    parser.add_argument("--work-dir", required=True, type=Path, help="external scratch with enough space for sort files")
    parser.add_argument("--sort-buffer", default="4G", help="GNU sort memory buffer; default 4G")
    parser.add_argument("--sort-workers", type=int, default=2, help="GNU sort workers; default 2")
    args = parser.parse_args()
    if not args.metadata_release.strip():
        parser.error("--metadata-release must be non-empty and name the source release, not a local directory")

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
    memory_guard = require_gridengine_memory_limit()
    outdir.mkdir(parents=True, exist_ok=True)
    workdir.mkdir(parents=True, exist_ok=True)
    if shutil.which("sort") is None or shutil.which("bgzip") is None or shutil.which("tabix") is None:
        parser.error("GNU sort, bgzip, and tabix must be available in the approved external environment")

    repo_root = Path(__file__).resolve().parents[2]
    builder_path = Path(__file__).resolve()
    tracked = subprocess.run(["git", "-C", str(repo_root), "ls-files", "--error-unmatch",
                              str(builder_path.relative_to(repo_root))],
                             check=True, capture_output=True, text=True)
    if not tracked.stdout.strip():
        raise RuntimeError("builder source is not tracked in the resolved repository")
    source_diff = subprocess.run(["git", "-C", str(repo_root), "diff", "--quiet", "HEAD", "--",
                                  str(builder_path.relative_to(repo_root))])
    if source_diff.returncode != 0:
        raise RuntimeError("builder source is dirty relative to HEAD; commit it before building")
    builder_commit = subprocess.run(["git", "-C", str(repo_root), "rev-parse", "HEAD"],
                                    check=True, capture_output=True, text=True).stdout.strip()
    builder_sha = sha256_file(builder_path)

    metadata_rows, metadata_sha = load_metadata(metadata)
    metadata_status_by_eid = {eid: metadata_status(rows) for eid, rows in metadata_rows.items()}
    hg38_metadata_by_eid = {eid: row for eid, rows in metadata_rows.items()
                            if (row := hg38_metadata_row(rows)) is not None}
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
    for eid, status in metadata_status_by_eid.items():
        if status == "INCLUDED":
            class_experiments[hg38_metadata_by_eid[eid][2]] += 1

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
                    meta_row = hg38_metadata_by_eid.get(eid)
                    if meta_row is not None:
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
                        mstatus = metadata_status_by_eid.get(eid, "MISSING_METADATA")
                        if mstatus != "INCLUDED":
                            status = mstatus
                        else:
                            meta = hg38_metadata_by_eid[eid]
                            bit = CLASS_BITS[meta[2]]
                            spool.write(f"{chroms[chrom][0]}\t{chrom}\t{start}\t{end}\t{eid}\t{ordinal}\t{qscore:.17g}\t{bit}\n")
                            rows_by_class[meta[2]] += 1
                            experiments_with_peaks.add(eid)
                counts[status or "INCLUDED_CANDIDATE"] += 1

        # coordinate, experiment, source-row order: exact coordinates collapse once.
        run_sort(unsorted, sorted_rows, tmpdir, args.sort_buffer, args.sort_workers,
                 ["-k1,1n", "-k2,2", "-k3,3n", "-k4,4n", "-k5,5", "-k6,6n"])
        bed_plain = tmpdir / "regions.bed"
        links_gz, links_raw = open_text_gz(outdir / "region_experiment.tsv.gz")
        summary_gz, summary_raw = open_text_gz(outdir / "region_summary.tsv.gz")
        links_gz.write("region_id\texperiment_id\n")
        summary_gz.write("region_id\tchrom\tstart\tend\tsupporting_experiments\tsource_peak_rows\tclass_mask\n")
        mask_counts: collections.Counter[int] = collections.Counter()
        n_regions = n_links = n_included_rows = 0
        n_multi_experiment_regions = 0
        with bed_plain.open("wt", encoding="utf-8", newline="") as bed, \
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

        collision_qc = {"checked_unique_region_ids": None, "unique_coordinate_keys": n_regions,
                        "duplicate_region_id_rows": None, "different_coordinate_hash_collisions": None,
                        "collision_examples": [], "status": "NOT_RUN",
                        "risk_control": "NEGLIGIBLE_ASSUMED",
                        "method": "release-level exact collision QC is a separate command"}
        write_json(outdir / "region_id_collision_qc.json", collision_qc)

        run_sort(row_map, sorted_map, tmpdir, args.sort_buffer, args.sort_workers, ["-k1,1n"])
        provenance, provenance_raw = open_text_gz(outdir / "peak_provenance.tsv.gz")
        provenance.write("source_archive_sha256\tsource_row_ordinal\tregion_id\texperiment_id\tprimary_status\tchrom\tstart\tend\tsource_qscore\n")
        matched = 0
        with sorted_map.open("rt", encoding="utf-8", newline="") as mapping, gzip.open(
            peaks, "rt", encoding="utf-8", errors="strict", newline=""
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
                try:
                    source_region_id = region_id(chrom, int(start), int(end))
                except ValueError as exc:
                    raise RuntimeError(f"source coordinate changed or became invalid at row {ordinal}") from exc
                if eid != map_eid or source_region_id != rid:
                    raise RuntimeError(f"source/mapping coordinate or experiment mismatch at row {ordinal}")
                provenance.write(f"{archive_sha}\t{ordinal}\t{rid}\t{eid}\t{status}\t{chrom}\t{start}\t{end}\t{qscore}\n")
                matched += 1
                pending = next(mapping, None)
            if pending is not None:
                raise RuntimeError("included source-row mapping extends beyond source archive")
        provenance.close(); provenance_raw.close()
        if matched != n_included_rows or n_included_rows != counts["INCLUDED_CANDIDATE"]:
            raise RuntimeError("included-row accounting/provenance cardinality mismatch")
        if sha256_file(peaks) != archive_sha:
            raise RuntimeError("peak archive SHA-256 changed between builder passes")
        if sha256_file(metadata) != metadata_sha:
            raise RuntimeError("experiment metadata SHA-256 changed during builder run")

        # Exactly seven nonempty masks are possible for the three included classes; write zeros too.
        mask_report = {str(mask): mask_counts[mask] for mask in range(1, 1 << len(CLASSES))}
        if sum(mask_report.values()) != n_regions:
            raise RuntimeError("class-mask counts do not sum to global unique-region count")
        if any(str(mask) not in mask_report for mask in mask_counts):
            raise RuntimeError("unexpected class-membership mask")

        bed_gz = outdir / OUTPUTS[0]
        with bed_gz.open("wb") as dst:
            subprocess.run(["bgzip", "-c", str(bed_plain)], check=True, stdout=dst)
        subprocess.run(["tabix", "-f", "-p", "bed", str(bed_gz)], check=True)

        query_results = []
        if n_regions:
            with bed_plain.open("rt", encoding="utf-8", newline="") as first_region_file:
                first_region = first_region_file.readline().rstrip("\n")
            first_fields = first_region.split("\t")
            control_chrom, control_start, control_end = first_fields[0], int(first_fields[1]), int(first_fields[2])
            control_expected = []
            with bed_plain.open("rt", encoding="utf-8", newline="") as bed_rows:
                for candidate in bed_rows:
                    fields = candidate.rstrip("\n").split("\t")
                    if fields[0] == control_chrom and int(fields[1]) < control_end and int(fields[2]) > control_start:
                        control_expected.append(candidate.rstrip("\n"))
            queries.append({"id": len(queries) + 1, "chrom": control_chrom,
                            "start": control_start, "end": control_end,
                            "expected": control_expected, "positive_control": True})
        for query in queries:
            chrom = str(query["chrom"])
            start, end = int(query["start"]), int(query["end"])
            interval = f"{chrom}:{start + 1}-{end}"
            result = subprocess.run(["tabix", str(bed_gz), interval], check=True,
                                    capture_output=True)
            observed_bytes = result.stdout
            expected = query["expected"]
            expected_bytes = ("".join(row + "\n" for row in expected)).encode("utf-8")
            passed = observed_bytes == expected_bytes
            observed = observed_bytes.decode("utf-8", errors="strict").splitlines()
            query_results.append({"id": query["id"], "interval_bed0": [chrom, start, end],
                                  "expected_hits": len(expected), "observed_hits": len(observed),
                                  "positive_control": bool(query.get("positive_control", False)),
                                  "exact_byte_match": passed})
            if not passed:
                raise RuntimeError(f"tabix query mismatch for {interval}")
        if n_regions and not any(row["positive_control"] and row["observed_hits"] > 0
                                 for row in query_results):
            raise RuntimeError("tabix positive-control query returned no rows")

    # Emit deterministic, complete metadata for all in-scope experiments, including zero-peak experiments.
    exp_path, exp_raw = open_text_gz(outdir / "experiment_metadata.tsv.gz")
    exp_path.write("experiment_id\tgenome\tantigen_class\tantigen\tmetadata_fields_json\n")
    for eid in sorted(metadata_rows):
        if metadata_status_by_eid[eid] == "INCLUDED":
            row = hg38_metadata_by_eid[eid]
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
            if metadata_status_by_eid[eid] == "INCLUDED" and eid not in experiments_with_peaks
        ),
        "region_class_membership_mask_counts": mask_report,
        "regions_with_multiple_experiments": n_multi_experiment_regions,
        "status_precedence": list(STATUS_NAMES),
    }
    if sum(reconciliation["primary_status_rows"].values()) != expected_source_rows:
        raise RuntimeError("mutually exclusive primary-status counts do not close")
    write_json(outdir / "reconciliation.json", reconciliation)
    query_qc = {"seed": 20261019, "query_count": len(query_results),
                "exact_matches": sum(bool(row["exact_byte_match"]) for row in query_results),
                "queries": query_results}
    write_json(outdir / "tabix_query_qc.json", query_qc)

    output_integrity = validate_emitted_sidecars(outdir, archive_sha, n_regions, n_links,
                                                 n_included_rows, counts, chroms)
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
        "builder_commit": builder_commit,
        "builder_source_sha256": builder_sha,
        "builder": "scripts/04a_chipatlas/build_unique_bed6.py",
        "argv": sys.argv,
        "metadata_release": args.metadata_release.strip(),
        "metadata_filename": metadata.name,
        "counts": {
            "source_rows": expected_source_rows,
            "included_source_rows": n_included_rows,
            "unique_regions": n_regions,
            "region_experiment_pairs": n_links,
        },
        "output_sha256": outputs_hash,
        "output_integrity": output_integrity,
        "region_id_collision_qc": collision_qc,
        "external_data_only": True,
        "resource_notes": {"sort_buffer": args.sort_buffer, "sort_workers": args.sort_workers,
                            "sort_locale": "LC_ALL=C"},
        "tool_versions": {"python": sys.version.split()[0], "gnu_sort": tool_version(["sort", "--version"]),
                           "bgzip": tool_version(["bgzip", "--version"]),
                           "tabix": tool_version(["tabix", "--version"])},
        "resource_measurement": {"memory_limit_mode": memory_guard["mode"],
                                 "memory_limit_semantics": ("44-GiB RLIMIT_AS soft/hard on an Argos background task" if memory_guard["mode"] == "argos_background_rlimit_as" else "Grid Engine h_vmem=44G hard job request on one slot; process RLIMIT_AS soft/hard also verified"),
                                 "memory_cap_bytes": memory_guard["memory_cap_bytes"],
                                 "task_id": memory_guard["job_id"],
                                 "gridengine_slots": memory_guard["slots"],
                                 "rlimit_as_soft_bytes": memory_guard["rlimit_as_soft_bytes"],
                                 "rlimit_as_hard_bytes": memory_guard["rlimit_as_hard_bytes"],
                                 "peak_rss_bytes": None,
                                 "peak_rss_status": "COLLECT_FROM_GRIDENGINE_QACCT_AFTER_JOB"},
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
