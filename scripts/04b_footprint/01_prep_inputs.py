"""Step 4b-1: common benchmark inputs (identical for every caller).

usage: 01_prep_inputs.py <raw_dir> <work_dir> <hg38_blacklist.bed.gz>
Writes to <work_dir>:
  frags/HCT116_ctrl.frags.tsv.gz, frags/HCT116_aux.frags.tsv.gz   from the ENCODE filtered BAMs (both replicates
      pooled): properly paired, MAPQ >= 30, primary, not duplicate; fragment = [leftmost + 4, rightmost - 5), i.e. the
      Tn5 +4/-5 shift; 5-column 10x layout (chrom, start, end, sample, 1)
  frags/gDNA.frags.tsv.gz        the 5 GEO human naked gDNA libraries pooled (already 5-column, hg38)
  regions/hct116_peaks_1kb.bed   ENCODE replicated peaks of the untreated sample (ENCFF849MMH): summit +/- 500 bp,
      greedily de-overlapped by peak signal; canonical chromosomes, blacklist-free
  regions/hct116_peaks_1kb.sub2000.bed   fixed random subset (seed 20261017) for timing
  regions/gdna_tiles_1kb.bed     1 kb tiles inside the HCT116 peak set ranked by naked-gDNA insertions; the 2,000 best
      covered tiles (naked DNA has no protein: any footprint called there is a false positive)
  inputs_summary.json
No caller-specific processing happens here.
"""
import gzip
import hashlib
import json
import os
import random
import shlex
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

import pysam

CANON = {f"chr{i}" for i in list(range(1, 23)) + ["X", "Y"]}
SEED = 20261017


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def cache_marker(path):
    return Path(str(path) + ".complete.sha256")


def write_cache_marker(path):
    index = Path(str(path) + ".tbi")
    marker = cache_marker(path)
    fd, tmp_marker = tempfile.mkstemp(prefix=f".{marker.name}.", dir=marker.parent)
    with os.fdopen(fd, "w") as f:
        f.write(f"{sha256_file(path)}  {path.name}\n{sha256_file(index)}  {index.name}\n")
    os.replace(tmp_marker, marker)


def indexed_file_ok(path, write_marker=True):
    index, marker = Path(str(path) + ".tbi"), cache_marker(path)
    if not path.is_file() or path.stat().st_size == 0 or not index.is_file() or index.stat().st_size == 0:
        return False
    if marker.is_file():
        try:
            expected = {parts[1]: parts[0] for line in marker.read_text().splitlines()
                        if len(parts := line.split()) == 2}
            return expected.get(path.name) == sha256_file(path) and expected.get(index.name) == sha256_file(index)
        except (OSError, ValueError):
            return False
    try:
        # Read the complete gzip stream to EOF so a valid first BGZF block
        # cannot mask truncation or CRC errors in later blocks.
        has_bytes = False
        with gzip.open(path, "rb") as f:
            while True:
                block = f.read(8 * 1024 * 1024)
                if not block:
                    break
                has_bytes = True
        if not has_bytes:
            return False
        with pysam.TabixFile(str(path)) as tb:
            for contig in tb.contigs:
                if next(tb.fetch(contig), None) is not None:
                    if write_marker:
                        write_cache_marker(path)
                    return True
            return False
    except Exception:
        return False


def archive_cache(path, work):
    index, marker = Path(str(path) + ".tbi"), cache_marker(path)
    existing = [p for p in (path, index, marker) if p.exists()]
    if not existing:
        return
    archive = Path(work) / "cache_interrupted" / f"{path.name}.{time.strftime('%Y%m%dT%H%M%S')}.{os.getpid()}"
    archive.mkdir(parents=True, exist_ok=False)
    for item in existing:
        os.replace(item, archive / item.name)


def build_indexed_bgzip(output, work, sort_tmp, command_builder):
    fd, tmp_name = tempfile.mkstemp(prefix=f".{output.name}.", suffix=".tmp.gz", dir=output.parent)
    os.close(fd)
    staged = Path(tmp_name)
    staged_index = Path(str(staged) + ".tbi")
    command = command_builder(staged)
    subprocess.run(["bash", "-o", "pipefail", "-c", command], check=True)
    if not indexed_file_ok(staged, write_marker=False):
        raise RuntimeError(f"staged BGZF/tabix output failed validation: {staged}")
    archive_cache(output, work)
    os.replace(staged, output)
    os.replace(staged_index, Path(str(output) + ".tbi"))
    write_cache_marker(output)


def bam_to_frags(bams, out, name, sort_tmp):
    n = Counter()
    tmp = str(out) + ".unsorted"
    with open(tmp, "w") as w:
        for b in bams:
            for r in pysam.AlignmentFile(b):
                n["reads"] += 1
                if (not r.is_paired or not r.is_proper_pair or r.is_secondary or r.is_supplementary or r.is_duplicate
                        or r.is_unmapped or r.mapping_quality < 30 or not r.is_read1 or r.reference_name != r.next_reference_name):
                    continue
                s = min(r.reference_start, r.next_reference_start)
                e = s + abs(r.template_length)
                if abs(r.template_length) < 20:
                    continue
                w.write(f"{r.reference_name}\t{s + 4}\t{e - 5}\t{name}\t1\n")
                n["fragments"] += 1
    def command(staged):
        return (f"LC_ALL=C sort -T {shlex.quote(str(sort_tmp))} -k1,1 -k2,2n -k3,3n -S 4G {shlex.quote(tmp)} "
                f"| bgzip -@ 4 > {shlex.quote(str(staged))} && tabix -f -p bed {shlex.quote(str(staged))}")
    build_indexed_bgzip(out, out.parent.parent, sort_tmp, command)
    Path(tmp).unlink(missing_ok=True)
    return dict(n)


def count_gdna_coverage(tb, contig, start, end, available_contigs):
    """Count naked-gDNA fragments overlapping the peak interval.

    A missing contig is not an observed zero: callers must track that state
    separately and exclude it from B1 tile eligibility.
    """
    if contig not in available_contigs:
        return 0
    return sum(
        1
        for rec in tb.fetch(contig, max(0, start - 1000), end + 1000)
        if (lambda fields: start <= int(fields[1]) < end or start <= int(fields[2]) < end)(
            rec.split("\t")
        )
    )


def select_gdna_tiles(cov, limit=2000):
    """Choose only callable peak regions with observed naked-gDNA coverage."""
    eligible = [t for t in cov if t[0] > 0]
    eligible.sort(key=lambda t: -t[0])
    return sorted(eligible[:limit], key=lambda t: (t[1], t[2]))


def missing_peak_contigs(peak_contigs, available_contigs):
    missing = sorted(set(peak_contigs) - set(available_contigs))
    unexpected = [contig for contig in missing if contig != "chrY"]
    if unexpected:
        raise RuntimeError(f"gDNA Tabix index is missing expected peak contigs: {unexpected}")
    return missing


def main(raw, work, blacklist):
    raw, work = Path(raw), Path(work)
    (work / "frags").mkdir(parents=True, exist_ok=True)
    (work / "regions").mkdir(parents=True, exist_ok=True)
    sort_tmp = work / "sort_tmp"
    sort_tmp.mkdir(parents=True, exist_ok=True)
    enc, geo = raw / "encode", raw / "geo"
    summ = {}
    for name, bams in (("HCT116_ctrl", ["ENCFF784ATG.bam", "ENCFF794FUH.bam"]),
                       ("HCT116_aux", ["ENCFF877LRY.bam", "ENCFF745WLX.bam"])):
        out = work / "frags" / f"{name}.frags.tsv.gz"
        if not indexed_file_ok(out):
            summ[name] = bam_to_frags([str(enc / b) for b in bams], out, name, sort_tmp)
    g = work / "frags" / "gDNA.frags.tsv.gz"
    if not indexed_file_ok(g):
        files = " ".join(shlex.quote(str(p)) for p in sorted(geo.glob("GSM859988*_gDNA_*.frags.txt.gz")))
        def command(staged):
            return (f"zcat {files} | awk 'BEGIN{{OFS=\"\\t\"}}{{print $1,$2,$3,\"gDNA\",$5}}' "
                    f"| LC_ALL=C sort -T {shlex.quote(str(sort_tmp))} -k1,1 -k2,2n -k3,3n -S 4G "
                    f"| bgzip -@ 4 > {shlex.quote(str(staged))} && tabix -f -p bed {shlex.quote(str(staged))}")
        build_indexed_bgzip(g, work, sort_tmp, command)
    bl = []
    with gzip.open(blacklist, "rt") as f:
        bl = [(c, int(s), int(e)) for c, s, e, *_ in (line.split("\t") for line in f)]
    blk = {}
    for c, s, e in bl:
        blk.setdefault(c, []).append((s, e))

    def in_bl(c, s, e):
        return any(s < be and bs < e for bs, be in blk.get(c, []))

    pk = []
    with gzip.open(enc / "ENCFF849MMH.bed.gz", "rt") as f:
        for line in f:
            x = line.split("\t")
            c, s, sig, summit = x[0], int(x[1]), float(x[6]), int(x[9])
            if c not in CANON:
                continue
            m = s + summit
            pk.append((sig, c, m - 500, m + 500))
    pk.sort(key=lambda t: -t[0])
    taken, keep = {}, []
    for sig, c, s, e in pk:  # greedy de-overlap by signal
        if s < 0 or in_bl(c, s, e) or any(s < te and ts < e for ts, te in taken.get(c, [])):
            continue
        taken.setdefault(c, []).append((s, e))
        keep.append((c, s, e))
    keep.sort()
    bed = work / "regions" / "hct116_peaks_1kb.bed"
    bed.write_text("".join(f"{c}\t{s}\t{e}\tP{i:06d}\n" for i, (c, s, e) in enumerate(keep)))
    random.seed(SEED)
    sub = sorted(random.sample(keep, min(2000, len(keep))))
    (work / "regions" / "hct116_peaks_1kb.sub2000.bed").write_text(
        "".join(f"{c}\t{s}\t{e}\tS{i:05d}\n" for i, (c, s, e) in enumerate(sub)))
    # Query naked-gDNA coverage over the HCT116 peak regions; missing contigs are tracked separately below.
    tb = pysam.TabixFile(str(g))
    available_contigs = set(tb.contigs)
    peak_contigs = {c for c, _, _ in keep}
    missing_contigs = missing_peak_contigs(peak_contigs, available_contigs)
    cov = []
    for c, s, e in keep:
        k = count_gdna_coverage(tb, c, s, e, available_contigs)
        cov.append((k, c, s, e))
    # Missing contigs and queryable regions with observed zero inserts are
    # both ineligible for B1; neither supplies evidence for false positives.
    top = select_gdna_tiles(cov)
    (work / "regions" / "gdna_tiles_1kb.bed").write_text(
        "".join(f"{c}\t{s}\t{e}\tG{i:05d}\t{k}\n" for i, (k, c, s, e) in enumerate(top)))
    absent_regions = sum(c not in available_contigs for _, c, _, _ in cov)
    observed_zero_regions = sum(c in available_contigs and k == 0 for k, c, _, _ in cov)
    summ.update(regions=len(keep), sub=len(sub), gdna_tiles=len(top),
                gdna_missing_contigs=missing_contigs,
                gdna_contig_absent_regions=absent_regions,
                gdna_observed_zero_regions=observed_zero_regions,
                gdna_insertions_per_tile=dict(min=min(t[0] for t in top) if top else None,
                                              median=sorted(t[0] for t in top)[len(top) // 2] if top else None))
    (work / "inputs_summary.json").write_text(json.dumps(summ, indent=1) + "\n")
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
