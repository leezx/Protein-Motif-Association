"""Step 4a §3/§6: annotate in-scope peak rows (stdin) into Output A rows (stdout), streaming.

usage: <in-scope 5-column peak rows> | 02_peaks.py <stage_dir> <reference_dir> | bgzip > occupancy.bed.gz
Reads <stage_dir>/annotation_suffix.tsv (01_experiments.py). Per row:
  integrity (chrom in hg38.chrom.sizes, 0 <= start < end <= length, finite score, known experiment) ->
  otherwise <stage_dir>/rejected_records.tsv with a reason;
  sort check (each chrom one contiguous block, starts non-decreasing) -> counted, never assumed;
  blacklist_majority_overlap when > 50 % of the peak overlaps ENCODE hg38 blacklist v2.
Writes <stage_dir>/peaks_summary.json and <stage_dir>/peak_counts_included.tsv at the end.
"""
import bisect
import collections
import gzip
import json
import math
import sys
from pathlib import Path


def load_blacklist(path):
    iv = collections.defaultdict(list)
    with gzip.open(path, "rt") as f:
        for line in f:
            c, s, e = line.split("\t")[:3]
            iv[c].append((int(s), int(e)))
    out = {}
    for c, v in iv.items():  # merge overlaps so per-chrom intervals are disjoint and sorted
        v.sort()
        m = [list(v[0])]
        for s, e in v[1:]:
            if s <= m[-1][1]:
                m[-1][1] = max(m[-1][1], e)
            else:
                m.append([s, e])
        out[c] = ([s for s, _ in m], [e for _, e in m])
    return out


def main(stage, ref):
    stage, ref = Path(stage), Path(ref)
    sizes = dict((c, int(n)) for c, n in (line.split() for line in open(ref / "hg38.chrom.sizes")))
    bl = load_blacklist(ref / "hg38-blacklist.v2.bed.gz")
    ann = {}
    with open(stage / "annotation_suffix.tsv", encoding="utf-8") as f:
        for line in f:
            eid, rest = line.rstrip("\n").split("\t", 1)
            prefix, flags = rest.rsplit("\t", 1)
            ann[eid] = (prefix, "" if flags == "." else flags)
    out = sys.stdout
    rej = open(stage / "rejected_records.tsv", "w")
    rej.write("reason\tline\n")
    n_in = n_out = n_bl = 0
    reasons = collections.Counter()
    per_exp = collections.Counter()
    seen_chroms, chrom_order = set(), []
    prev_c, prev_s, unsorted = None, -1, 0
    for line in sys.stdin:
        n_in += 1
        f = line.rstrip("\n").split("\t")
        reason = None
        if len(f) != 5:
            reason = "ncol"
        else:
            c, s, e, eid, q = f
            L = sizes.get(c)
            try:
                si, ei, qv = int(s), int(e), float(q)
            except ValueError:
                si = ei = qv = None
            if L is None:
                reason = "chrom_not_in_hg38_sizes"
            elif si is None or not math.isfinite(qv):
                reason = "non_numeric"
            elif not (0 <= si < ei <= L):
                reason = "coordinates_out_of_range"
            elif eid not in ann:
                reason = "experiment_not_in_scope_metadata"
        if reason:
            reasons[reason] += 1
            rej.write(f"{reason}\t{line.rstrip()}\n")
            continue
        if c != prev_c:
            if c in seen_chroms:
                unsorted += 1
            seen_chroms.add(c)
            chrom_order.append(c)
            prev_c, prev_s = c, -1
        if si < prev_s:
            unsorted += 1
        prev_s = si
        prefix, flags = ann[eid]
        b = bl.get(c)
        if b:
            starts, ends = b
            i = bisect.bisect_right(ends, si)
            ov = 0
            while i < len(starts) and starts[i] < ei:
                ov += min(ei, ends[i]) - max(si, starts[i])
                i += 1
            if ov * 2 > ei - si:
                flags = flags + ";blacklist_majority_overlap" if flags else "blacklist_majority_overlap"
                n_bl += 1
        sc = min(1000, max(0, round(qv)))
        out.write(f"{c}\t{si}\t{ei}\t{eid}\t{sc}\t.\t{q}\t{prefix}\t{flags or '.'}\n")
        n_out += 1
        per_exp[eid] += 1
    rej.close()
    with open(stage / "peak_counts_included.tsv", "w") as f:
        f.write("experiment_id\tn_peaks_in_archive\n")
        for k, v in sorted(per_exp.items()):
            f.write(f"{k}\t{v}\n")
    summ = dict(rows_in=n_in, rows_out=n_out, rejected=dict(reasons), sort_violations=unsorted,
                chromosomes=len(chrom_order), chrom_order_head=chrom_order[:30], blacklist_majority_overlap=n_bl,
                experiments_with_peaks=len(per_exp))
    (stage / "peaks_summary.json").write_text(json.dumps(summ, indent=1) + "\n")
    print(json.dumps(summ), file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
