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
import json
import random
import shlex
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pysam

CANON = {f"chr{i}" for i in list(range(1, 23)) + ["X", "Y"]}
SEED = 20261017


def indexed_file_ok(path):
    index = Path(str(path) + ".tbi")
    if not path.is_file() or path.stat().st_size == 0 or not index.is_file() or index.stat().st_size == 0:
        return False
    try:
        with pysam.TabixFile(str(path)) as tb:
            for contig in tb.contigs:
                if next(tb.fetch(contig), None) is not None:
                    return True
            return False
    except Exception:
        return False


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
    cmd = (f"LC_ALL=C sort -T {shlex.quote(str(sort_tmp))} -k1,1 -k2,2n -k3,3n -S 4G {shlex.quote(tmp)} "
           f"| bgzip -@ 4 > {shlex.quote(str(out))} && tabix -p bed {shlex.quote(str(out))} && rm {shlex.quote(tmp)}")
    subprocess.run(["bash", "-o", "pipefail", "-c", cmd], check=True)
    return dict(n)


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
        cmd = (f"zcat {files} | awk 'BEGIN{{OFS=\"\\t\"}}{{print $1,$2,$3,\"gDNA\",$5}}' "
               f"| LC_ALL=C sort -T {shlex.quote(str(sort_tmp))} -k1,1 -k2,2n -k3,3n -S 4G "
               f"| bgzip -@ 4 > {shlex.quote(str(g))} && tabix -p bed {shlex.quote(str(g))}")
        subprocess.run(["bash", "-o", "pipefail", "-c", cmd], check=True)
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
    # naked-gDNA coverage in the same 1 kb regions (the callable space is identical; gDNA has no protein)
    tb = pysam.TabixFile(str(g))
    cov = []
    for c, s, e in keep:
        k = sum(1 for _ in tb.fetch(c, max(0, s - 1000), e + 1000)
                if (lambda t: s <= int(t[1]) < e or s <= int(t[2]) < e)(_.split("\t")))
        cov.append((k, c, s, e))
    cov.sort(key=lambda t: -t[0])
    top = sorted(cov[:2000], key=lambda t: (t[1], t[2]))
    (work / "regions" / "gdna_tiles_1kb.bed").write_text(
        "".join(f"{c}\t{s}\t{e}\tG{i:05d}\t{k}\n" for i, (k, c, s, e) in enumerate(top)))
    summ.update(regions=len(keep), sub=len(sub), gdna_tiles=len(top),
                gdna_insertions_per_tile=dict(min=top and min(t[0] for t in top), median=sorted(t[0] for t in top)[len(top) // 2]))
    (work / "inputs_summary.json").write_text(json.dumps(summ, indent=1) + "\n")
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
