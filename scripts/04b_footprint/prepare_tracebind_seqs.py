#!/usr/bin/env python3
"""Precompute TraceBIND regionSeqs.txt from indexed hg38 FASTA on Argos.

TraceBIND's get_bias() skips its slow per-region BSgenome getSeq() loop when
regionSeqs.txt already exists. This reproduces its BED0 -> 1-based conversion,
max-width extension, and 50-base context on each side for uniform-width beds.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import resource
from pathlib import Path

import pysam


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def require_argos_cap() -> None:
    soft, hard = resource.getrlimit(resource.RLIMIT_AS)
    maximum = 44 * (1 << 30)
    if not (os.environ.get("JOB_ID", "").startswith("BG_TRACE_PRESEQ_")
            and os.environ.get("NSLOTS") == "1"
            and 0 < soft <= maximum and 0 < hard <= maximum
            and soft <= hard and os.environ.get("CUDA_VISIBLE_DEVICES") == ""):
        raise ValueError("requires a CPU-only capped Argos background task")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--regions", required=True, type=Path)
    parser.add_argument("--genome", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--expected-rows", required=True, type=int)
    parser.add_argument("--compare", type=Path, help="independent BSgenome regionSeqs.txt fixture")
    args = parser.parse_args()
    require_argos_cap()
    if args.expected_rows <= 0 or not args.genome.with_suffix(args.genome.suffix + ".fai").is_file():
        raise ValueError("positive expected rows and indexed FASTA are required")
    for path in (args.regions, args.genome, args.output):
        if any((parent / ".git").exists() for parent in (path.resolve(), *path.resolve().parents)):
            raise ValueError("project data/output may not be inside a repository")
    if args.output.exists():
        raise ValueError("refusing to overwrite an existing sequence file")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_name(args.output.name + f".partial.{os.getpid()}")
    if temporary.exists():
        raise ValueError("temporary sequence file already exists")
    rows = 0
    width = None
    try:
        with pysam.FastaFile(str(args.genome)) as fasta, \
                args.regions.open("rt", encoding="utf-8") as regions, \
                temporary.open("wt", encoding="ascii", newline="\n") as output:
            for line in regions:
                fields = line.rstrip("\r\n").split("\t")
                if len(fields) < 3:
                    raise ValueError(f"malformed BED row {rows + 1}")
                chrom, start, end = fields[0], int(fields[1]), int(fields[2])
                if width is None:
                    width = end - start
                if end - start != width or width <= 0:
                    raise ValueError("TraceBIND precompute requires uniform positive-width BED regions")
                if start < 50 or chrom not in fasta.references or end + 50 > fasta.get_reference_length(chrom):
                    raise ValueError(f"region/context outside indexed genome at row {rows + 1}")
                seq = fasta.fetch(chrom, start - 50, end + 50).upper()
                if len(seq) != width + 100:
                    raise ValueError(f"unexpected sequence width at row {rows + 1}")
                output.write(seq + "\n")
                rows += 1
        if rows != args.expected_rows:
            raise ValueError(f"expected {args.expected_rows} regions, found {rows}")
        if args.compare is not None:
            with temporary.open("rb") as generated, args.compare.open("rb") as reference:
                if generated.read() != reference.read():
                    raise ValueError("indexed FASTA sequences differ from BSgenome fixture")
        temporary.replace(args.output)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    print(json.dumps({"status": "PASS", "regions": rows, "context_width": width + 100,
                      "regions_sha256": sha256_file(args.regions),
                      "genome_sha256": sha256_file(args.genome),
                      "output_sha256": sha256_file(args.output)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
