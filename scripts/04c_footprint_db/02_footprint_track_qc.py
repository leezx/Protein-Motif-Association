"""QC for a footprint sample-count track built by 01_footprint_tracks.sh (streams; memory stays small).

usage: 02_footprint_track_qc.py <footprints.bed.gz> <samples.bedGraph.gz> <samples.tsv> <qc.json>
Checks:
  conservation  sum(value * bp) over the bedGraph == total footprint bp (footprints are disjoint within a sample)
  range         1 <= value <= number of samples; bedGraph sorted and non-overlapping within each chromosome
  recount       at 300 random footprint bases + 300 random bedGraph bases, the number of distinct samples whose
                footprints cover the base (tabix on footprints.bed.gz, independent of genomecov) equals the
                bedGraph value at that base (tabix on the bedGraph)
Needs tabix on PATH and both files tabix-indexed.
"""
import gzip
import json
import subprocess
import sys

import numpy as np

N_CHECK = 300


def tabix(path, c, p):
    out = subprocess.run(["tabix", path, f"{c}:{p + 1}-{p + 1}"], capture_output=True, text=True, check=True).stdout
    return [l.split("\t") for l in out.splitlines() if l]


def pick(path, n, rng, total):
    want = set(rng.choice(total, min(n, total), replace=False).tolist()); out = []
    with gzip.open(path, "rt") as f:
        for i, l in enumerate(f):
            if i in want:
                c, s, e = l.split("\t")[:3]; out.append((c, int(rng.integers(int(s), int(e)))))
    return out


def main(fp, bg, samples, out):
    rng = np.random.default_rng(7)
    n_samples = sum(1 for _ in open(samples)) - 1
    fp_bp = 0; n_fp = 0
    with gzip.open(fp, "rt") as f:
        for l in f:
            c, s, e = l.split("\t")[:3]; fp_bp += int(e) - int(s); n_fp += 1
    vbp = 0.0; vmax = 0.0; vmin = float("inf"); cov = 0; n_bg = 0; ok_order = True; last = (None, -1)
    with gzip.open(bg, "rt") as f:
        for l in f:
            c, s, e, v = l.split("\t"); s, e, v = int(s), int(e), float(v)
            if c == last[0] and s < last[1]:
                ok_order = False
            last = (c, e); vbp += v * (e - s); cov += e - s; vmax = max(vmax, v); vmin = min(vmin, v); n_bg += 1
    pos = pick(fp, N_CHECK, rng, n_fp) + pick(bg, N_CHECK, rng, n_bg)
    bad = []
    for c, p in pos:
        n = len({r[3] for r in tabix(fp, c, p) if int(r[1]) <= p < int(r[2])})
        v = [float(r[3]) for r in tabix(bg, c, p) if int(r[1]) <= p < int(r[2])]
        if n != (v[0] if v else 0):
            bad.append([c, p, n, v])
    qc = {"samples": n_samples, "footprints": n_fp, "footprint_bp": fp_bp, "bedgraph_value_bp": vbp,
          "conservation_ok": abs(vbp - fp_bp) < 0.5, "covered_bp": cov, "max_samples": vmax, "min_value": vmin,
          "range_ok": vmin >= 1 and vmax <= n_samples, "sorted_nonoverlap_ok": ok_order,
          "recount_checked": len(pos), "recount_mismatch": len(bad), "mismatch_examples": bad[:5]}
    qc["PASS"] = bool(qc["conservation_ok"] and qc["range_ok"] and ok_order and not bad)
    json.dump(qc, open(out, "w"), indent=1)
    if not qc["PASS"]:
        sys.exit(f"QC FAIL: {json.dumps(qc)}")


if __name__ == "__main__":
    main(*sys.argv[1:])
