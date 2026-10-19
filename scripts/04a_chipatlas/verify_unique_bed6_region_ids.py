#!/usr/bin/env python3
"""Run one exact region-ID collision audit for a completed BED6 release.

This is deliberately separate from iterative/pilot builder runs. It performs one
external sort over compact unique-region ID/coordinate rows and updates the
release's collision-QC sidecar and manifest. It does not read raw peak data.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import resource
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def region_id(chrom: str, start: int, end: int) -> str:
    payload = "\t".join(("PMA-region-v1", "hg38", chrom, str(start), str(end))).encode("utf-8")
    return "PMA_hg38_" + hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as src:
        for block in iter(lambda: src.read(8 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def require_gridengine_memory_limit() -> dict[str, int | str]:
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
        raise ValueError(f"required Grid Engine h_vmem/RLIMIT_AS guard unavailable or invalid: {exc}") from exc
    return {"mode": "argos_background_rlimit_as" if background else "gridengine_h_vmem_single_slot_plus_rlimit_as", "job_id": job_id, "slots": 1,
            "rlimit_as_soft_bytes": int(soft), "rlimit_as_hard_bytes": int(hard),
            "memory_cap_bytes": maximum}


def reject_repo_path(path: Path) -> None:
    for parent in (path.resolve(), *path.resolve().parents):
        if (parent / ".git").exists():
            raise ValueError(f"QC input/work path is inside a Git checkout: {path.resolve()}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bed", required=True, type=Path, help="completed external BED6 .bed.gz")
    parser.add_argument("--chrom-sizes", required=True, type=Path, help="pinned hg38.chrom.sizes")
    parser.add_argument("--work-dir", required=True, type=Path, help="external scratch for compact ID sort")
    parser.add_argument("--sort-buffer", default="4G")
    parser.add_argument("--sort-workers", type=int, default=2)
    args = parser.parse_args()

    bed, chrom_sizes, work = args.bed.resolve(), args.chrom_sizes.resolve(), args.work_dir.resolve()
    reject_repo_path(bed.parent)
    reject_repo_path(work)
    if not chrom_sizes.is_file():
        parser.error(f"chrom sizes is not a file: {chrom_sizes}")
    if not bed.is_file() or not Path(str(bed) + ".tbi").is_file():
        parser.error("BED6 and its tabix index must exist")
    if args.sort_workers < 1:
        parser.error("--sort-workers must be positive")
    if shutil.which("sort") is None:
        parser.error("GNU sort is required")
    memory_guard = require_gridengine_memory_limit()
    work.mkdir(parents=True, exist_ok=True)
    release_dir = bed.parent
    qc_path = release_dir / "region_id_collision_qc.json"
    manifest_path = release_dir / "MANIFEST.json"
    if not qc_path.is_file() or not manifest_path.is_file():
        parser.error("release region-ID QC sidecar and MANIFEST.json must exist")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    input_hash = sha256_file(bed)
    declared_hash = manifest.get("output_sha256", {}).get(bed.name)
    if (not isinstance(declared_hash, str) or len(declared_hash) != 64
            or any(char not in "0123456789abcdef" for char in declared_hash)):
        raise ValueError("release manifest must declare a valid BED6 SHA-256")
    if declared_hash != input_hash:
        raise ValueError("BED6 SHA-256 does not match the release manifest")
    sort_rows = 0
    hash_mismatches = 0
    mismatch_examples = []
    chrom_order = {}
    chrom_length = {}
    for rank, line in enumerate(chrom_sizes.read_text(encoding="utf-8").splitlines()):
        fields = line.split()
        if len(fields) < 2:
            raise ValueError(f"malformed chrom.sizes line {rank + 1}")
        chrom, length = fields[0], int(fields[1])
        if chrom in chrom_order:
            raise ValueError(f"duplicate chromosome in chrom.sizes: {chrom}")
        chrom_order[chrom] = rank
        chrom_length[chrom] = length
    last_coordinate = None
    duplicate_coordinate_rows = 0

    with tempfile.TemporaryDirectory(prefix="pma-region-id-qc-", dir=work) as tmp:
        tmpdir = Path(tmp)
        unsorted = tmpdir / "ids.tsv"
        sorted_ids = tmpdir / "ids.sorted.tsv"
        with gzip.open(bed, "rt", encoding="utf-8", errors="strict", newline="") as src, \
             unsorted.open("wt", encoding="utf-8", newline="") as ledger:
            for row_number, line in enumerate(src, start=1):
                fields = line.rstrip("\r\n").split("\t")
                if len(fields) != 6:
                    raise ValueError(f"BED6 row {row_number} has {len(fields)} columns")
                chrom, raw_start, raw_end, rid, score, strand = fields
                start, end = int(raw_start), int(raw_end)
                if (chrom not in chrom_order or not (0 <= start < end <= chrom_length.get(chrom, 0))
                        or strand != "."):
                    raise ValueError(f"invalid BED6 coordinates/strand at row {row_number}")
                if not score.isdigit() or not (0 <= int(score) <= 1000):
                    raise ValueError(f"invalid BED6 score at row {row_number}")
                coordinate_order = (chrom_order[chrom], start, end)
                if last_coordinate is not None and coordinate_order < last_coordinate:
                    raise ValueError(f"BED6 sort order violation at row {row_number}")
                if last_coordinate == coordinate_order:
                    duplicate_coordinate_rows += 1
                last_coordinate = coordinate_order
                expected_id = region_id(chrom, start, end)
                if rid != expected_id:
                    hash_mismatches += 1
                    if len(mismatch_examples) < 20:
                        mismatch_examples.append({"row": row_number, "id": rid, "expected_id": expected_id,
                                                  "coordinate": [chrom, start, end]})
                ledger.write(f"{rid}\t{chrom}\t{start}\t{end}\n")
                sort_rows += 1
        expected_regions = int(manifest.get("counts", {}).get("unique_regions", -1))
        row_count_matches = sort_rows == expected_regions
        command = ["sort", "-t\t", "-S", args.sort_buffer, "--parallel", str(args.sort_workers),
                   "-T", str(tmpdir), "-k1,1", "-o", str(sorted_ids), str(unsorted)]
        subprocess.run(command, check=True, env={**os.environ, "LC_ALL": "C"})
        duplicate_rows = different_coordinate_collisions = 0
        collision_examples = []
        last_id = None
        last_coord = None
        with sorted_ids.open("rt", encoding="utf-8", newline="") as src:
            for line in src:
                rid, chrom, raw_start, raw_end = line.rstrip("\n").split("\t")
                coord = [chrom, int(raw_start), int(raw_end)]
                if rid == last_id:
                    duplicate_rows += 1
                    if coord != last_coord:
                        different_coordinate_collisions += 1
                        if len(collision_examples) < 20:
                            collision_examples.append({"region_id": rid, "first_coordinate": last_coord,
                                                       "colliding_coordinate": coord})
                last_id, last_coord = rid, coord

    passed = (duplicate_rows == 0 and different_coordinate_collisions == 0 and
              hash_mismatches == 0 and duplicate_coordinate_rows == 0 and row_count_matches)
    qc = {
        "status": "PASS" if passed else "FAIL",
        "method": "GNU external sort of one row per BED6 region by full SHA-256 region_id; adjacent ID and coordinate comparison",
        "checked_bed_sha256": input_hash,
        "checked_unique_region_ids": sort_rows,
        "bed_rows_match_manifest": row_count_matches,
        "unique_coordinate_keys_from_builder": expected_regions,
        "duplicate_coordinate_rows": duplicate_coordinate_rows,
        "duplicate_region_id_rows": duplicate_rows,
        "different_coordinate_hash_collisions": different_coordinate_collisions,
        "region_id_coordinate_hash_mismatches": hash_mismatches,
        "collision_examples": collision_examples,
        "hash_mismatch_examples": mismatch_examples,
        "sort_buffer": args.sort_buffer,
        "sort_workers": args.sort_workers,
        "sort_version": subprocess.run(["sort", "--version"], check=True, capture_output=True,
                                        text=True).stdout.splitlines()[0],
        "memory_limit_mode": memory_guard["mode"],
        "memory_limit_semantics": ("44-GiB RLIMIT_AS soft/hard on an Argos background task" if memory_guard["mode"] == "argos_background_rlimit_as" else "Grid Engine h_vmem=44G hard job request on one slot; process RLIMIT_AS soft/hard also verified"),
        "memory_cap_bytes": memory_guard["memory_cap_bytes"],
        "task_id": memory_guard["job_id"],
        "gridengine_slots": memory_guard["slots"],
        "rlimit_as_soft_bytes": memory_guard["rlimit_as_soft_bytes"],
        "rlimit_as_hard_bytes": memory_guard["rlimit_as_hard_bytes"],
        "peak_rss_bytes": None,
        "peak_rss_status": "COLLECT_FROM_GRIDENGINE_QACCT_AFTER_JOB",
    }
    qc_path.write_text(json.dumps(qc, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    manifest["region_id_collision_qc"] = qc
    manifest.setdefault("output_sha256", {})[qc_path.name] = sha256_file(qc_path)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(qc, ensure_ascii=False, sort_keys=True))
    return 0 if passed else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
