"""Cell-type context of protein hotspot bins: breadth of use, protein consistency, and composition similarity.

usage: 32_hotspot_context.py bins    <bins500.npz> <bins_annotation.npz> <out_dir> [n_control=20000]
       32_hotspot_context.py chrom   <occupancy.bed.gz> <experiments.tsv.gz> <out_dir> <chrom>
       32_hotspot_context.py analyze <experiments.tsv.gz> <class_annotation.csv> <out_dir>

Unit = 500 bp bin (as 31_hotspot_annotation.py; blacklist and N > 50 % bins excluded). Groups: n_control random bins (memory cap) from
each band top1 (P >= 244), b5 (70-243), b20 (17-35), low (1-16); seed 20261030.
Context = ChIP-Atlas cell type (column 14 of v1 Output A); CT = cell types with >= 50 tested targets, 'Unclassified'
dropped. tested(c) = targets with >= 1 experiment in c; n(c, p) = experiments of p in c. Target key as in
05_occupancy_tracks.py.
chrom mode streams one chromosome and writes parts/<chrom>.tsv: bin_id, cell_type, target, n_exp_with_peak.
analyze mode, for bin b and c in CT: S(b, c) = targets with >= 1 peak at b from an experiment in c;
  f(b, c) = |S(b, c)| / |tested(c)|;  active(b, c) = f(b, c) > q99 of f over the low-band bins in c and |S| >= 3.
  B1 breadth(b) = number of CT cell types where b is active.
  B2 per (top1 bin, target p) with >= 3 cell types active at b and testing p: consistency = share of those cell
     types where p is in S(b, c); hit rate = experiments of p with a peak at b / experiments of p, same cell types.
     Summarised per target and per group (DBP = lambert2018_TF tag; cofactor = non-DBP in Transcription machinery,
     Histone writer/eraser, Histone reader, Chromatin remodeler, Architectural/cohesin; other).
  B3 per top1 bin and pair of active cell types (c1, c2): Jaccard of S(b, c1), S(b, c2) over targets tested in
     both, per group; null = same pair with S(b', c2) from a random other top1 bin active in c2 (one draw per pair).
Outputs: context_bins.bed, parts/, breadth.tsv, consistency_target.tsv, consistency_group.tsv, jaccard_group.tsv,
  celltypes.tsv, summary.json.
"""
import collections
import csv
import glob
import gzip
import json
import random
import subprocess
import sys
from pathlib import Path

import numpy as np

BIN = 500
MIN_TARGETS = 50
COFACTOR = {"Transcription machinery", "Histone writer/eraser", "Histone reader", "Chromatin remodeler",
            "Architectural/cohesin"}


def target_of(sym, raw):
    return "_".join((sym if sym != "." else raw).split())


def load_experiments(path):
    """experiment -> (cell_type, target), and the CT set."""
    exp, per_ct = {}, collections.defaultdict(set)
    with gzip.open(path, "rt") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            t = target_of(r["antigen_hgnc_symbol"], r["antigen_raw"])
            exp[r["experiment_id"]] = (r["cell_type"], t)
            per_ct[r["cell_type"]].add(t)
    ct = sorted(c for c, s in per_ct.items() if len(s) >= MIN_TARGETS and c != "Unclassified")
    return exp, ct


def make_bins(npz, ann, out, n_control=20000):
    z, a = np.load(npz), np.load(ann)
    P = z["proteins"].astype(np.int32)
    keep = a["keep"]
    rng = np.random.default_rng(20261030)
    groups = {}
    for g, lo, hi in (("top1", 244, 1 << 30), ("b5", 70, 244), ("b20", 17, 36), ("low", 1, 17)):
        idx = np.flatnonzero(keep & (P >= lo) & (P < hi))
        groups[g] = np.sort(rng.choice(idx, n_control, replace=False))
    offs, chroms = z["offset"], list(z["chrom"])
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for g, idx in groups.items():
        ci = np.searchsorted(offs, idx, side="right") - 1
        rows += [(chroms[c], int(i - offs[c]) * BIN, g, int(i), int(P[i])) for i, c in zip(idx, ci)]
    rows.sort(key=lambda r: (r[0], r[1]))
    with open(out / "context_bins.bed", "w") as f:
        for c, s, g, i, p in rows:
            f.write(f"{c}\t{s}\t{s + BIN}\t{i}\t{p}\t{g}\n")
    print({g: len(v) for g, v in groups.items()})


def run_chrom(bed, exps, out, chrom):
    exp, ct = load_experiments(exps)
    cts = set(ct)
    bins = {}
    with open(Path(out) / "context_bins.bed") as f:
        for line in f:
            c, s, _, i, _, _ = line.rstrip("\n").split("\t")
            if c == chrom:
                bins[int(s) // BIN] = int(i)
    hits = collections.defaultdict(set)  # (bin_id, cell_type, target) -> experiments
    proc = subprocess.Popen(["tabix", bed, chrom], stdout=subprocess.PIPE, text=True, bufsize=1 << 20)
    for line in proc.stdout:
        f = line.split("\t", 15)
        if f[13] not in cts:
            continue
        s, e = int(f[1]), int(f[2])
        for k in range(s // BIN, (e - 1) // BIN + 1):
            b = bins.get(k)
            if b is not None:
                hits[(b, f[13], target_of(f[8], f[7]))].add(f[3])
    assert proc.wait() == 0
    parts = Path(out) / "parts"
    parts.mkdir(exist_ok=True)
    with open(parts / f"{chrom}.tsv", "w") as f:
        for (b, c, t), ex in hits.items():
            f.write(f"{b}\t{c}\t{t}\t{len(ex)}\n")
    (parts / f"{chrom}.done").write_text(str(len(hits)))


def analyze(exps, ann_csv, out):
    out = Path(out)
    exp, ct = load_experiments(exps)
    tested = collections.defaultdict(set)
    nexp = collections.Counter()
    for c, t in exp.values():
        tested[c].add(t)
        nexp[(c, t)] += 1
    dbp, cls = set(), {}
    with open(ann_csv) as f:
        for r in csv.DictReader(f):
            cls[r["gene"]] = r["Class"]
            if "lambert2018_TF" in r["functional_tags"].split(";"):
                dbp.add(r["gene"])

    def group(t):
        return "DBP" if t in dbp else ("cofactor" if cls.get(t) in COFACTOR else "other")

    grp_of = {}
    with open(out / "context_bins.bed") as f:
        for line in f:
            x = line.rstrip("\n").split("\t")
            grp_of[int(x[3])] = (x[5], int(x[4]), f"{x[0]}:{x[1]}")
    S = collections.defaultdict(dict)  # bin -> cell_type -> {target: n_exp_with_peak}
    for p in sorted(glob.glob(str(out / "parts/*.tsv"))):
        with open(p) as f:
            for line in f:
                b, c, t, n = line.rstrip("\n").split("\t")
                S[int(b)].setdefault(c, {})[t] = int(n)
    # activity thresholds from low-band bins
    thr = {}
    low = [b for b, g in grp_of.items() if g[0] == "low"]
    for c in ct:
        fr = np.array([len(S[b].get(c, {})) / len(tested[c]) for b in low])
        thr[c] = float(np.quantile(fr, 0.99))

    def active(b):
        return [c for c in ct if len(S[b].get(c, {})) >= 3 and len(S[b].get(c, {})) / len(tested[c]) > thr[c]]

    act = {b: active(b) for b in grp_of}
    with open(out / "breadth.tsv", "w") as f:
        f.write("bin_id\tlocus\tgroup\tP\tn_active\tactive_celltypes\n")
        for b, (g, p, loc) in sorted(grp_of.items()):
            f.write(f"{b}\t{loc}\t{g}\t{p}\t{len(act[b])}\t{','.join(act[b])}\n")
    with open(out / "celltypes.tsv", "w") as f:
        f.write("cell_type\ttested_targets\texperiments\tq99_low\tpct_top1_active\n")
        top1 = [b for b, g in grp_of.items() if g[0] == "top1"]
        for c in ct:
            ne = sum(v for (cc, _), v in nexp.items() if cc == c)
            pa = sum(c in act[b] for b in top1) / len(top1)
            f.write(f"{c}\t{len(tested[c])}\t{ne}\t{thr[c]:.5f}\t{pa:.4f}\n")

    # B2 consistency
    per_t = collections.defaultdict(lambda: [0, 0.0, 0, 0])  # n pairs, sum consistency, hits, total experiments
    per_g = collections.defaultdict(list)
    for b in top1:
        A = act[b]
        if len(A) < 3:
            continue
        cand = set().union(*(S[b][c].keys() for c in A))
        for t in cand:
            cs = [c for c in A if t in tested[c]]
            if len(cs) < 3:
                continue
            k = sum(t in S[b][c] for c in cs)
            hit = sum(S[b][c].get(t, 0) for c in cs)
            tot = sum(nexp[(c, t)] for c in cs)
            v = per_t[t]
            v[0] += 1; v[1] += k / len(cs); v[2] += hit; v[3] += tot
            per_g[group(t)].append(k / len(cs))
    with open(out / "consistency_target.tsv", "w") as f:
        f.write("target\tgroup\tclass\tn_bins\tmean_consistency\thit_rate\n")
        for t, (n, s, h, tot) in sorted(per_t.items(), key=lambda x: -x[1][0]):
            f.write(f"{t}\t{group(t)}\t{cls.get(t, 'Non-gene label')}\t{n}\t{s / n:.4f}\t{h / tot:.4f}\n")
    with open(out / "consistency_group.tsv", "w") as f:
        f.write("group\tn_pairs\tmean\tq25\tmedian\tq75\tpct_eq1\tpct_le_half\n")
        for g, v in sorted(per_g.items()):
            v = np.array(v)
            f.write(f"{g}\t{len(v)}\t{v.mean():.4f}\t{np.quantile(v, .25):.4f}\t{np.median(v):.4f}\t"
                    f"{np.quantile(v, .75):.4f}\t{(v == 1).mean():.4f}\t{(v <= 0.5).mean():.4f}\n")

    # B3 Jaccard, observed vs shuffled
    rng = random.Random(20261030)
    by_ct = collections.defaultdict(list)
    for b in top1:
        for c in act[b]:
            by_ct[c].append(b)
    jac = collections.defaultdict(lambda: [[], []])
    sample = [b for b in top1 if len(act[b]) >= 2]
    rng.shuffle(sample)
    for b in sample[:10000]:
        A = act[b]
        for i in range(len(A)):
            for j in range(i + 1, len(A)):
                c1, c2 = A[i], A[j]
                T = tested[c1] & tested[c2]
                b2 = rng.choice(by_ct[c2])
                while b2 == b and len(by_ct[c2]) > 1:
                    b2 = rng.choice(by_ct[c2])
                for g in ("all", "DBP", "cofactor"):
                    Tg = T if g == "all" else {t for t in T if group(t) == g}
                    s1 = set(S[b][c1]) & Tg
                    for k, s2 in ((0, set(S[b][c2]) & Tg), (1, set(S[b2][c2]) & Tg)):
                        u = s1 | s2
                        if u:
                            jac[g][k].append(len(s1 & s2) / len(u))
    with open(out / "jaccard_group.tsv", "w") as f:
        f.write("group\tn_pairs\tobserved_mean\tobserved_median\tshuffled_mean\tshuffled_median\tratio_mean\n")
        for g, (o, s) in jac.items():
            f.write(f"{g}\t{len(o)}\t{np.mean(o):.4f}\t{np.median(o):.4f}\t{np.mean(s):.4f}\t{np.median(s):.4f}\t"
                    f"{np.mean(o) / np.mean(s):.3f}\n")
    br = collections.defaultdict(list)
    for b, (g, _, _) in grp_of.items():
        br[g].append(len(act[b]))
    summ = dict(cell_types=ct, n_cell_types=len(ct),
                breadth={g: dict(n=len(v), median=float(np.median(v)), mean=float(np.mean(v)),
                                 pct_0=float(np.mean(np.array(v) == 0)), pct_ge5=float(np.mean(np.array(v) >= 5)),
                                 pct_ge10=float(np.mean(np.array(v) >= 10))) for g, v in br.items()},
                consistency_pairs={g: len(v) for g, v in per_g.items()}, jaccard_bins=min(10000, len(sample)))
    (out / "summary.json").write_text(json.dumps(summ, indent=1))
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    m = sys.argv[1]
    if m == "bins":
        make_bins(*sys.argv[2:5], *(int(x) for x in sys.argv[5:6]))
    elif m == "chrom":
        run_chrom(*sys.argv[2:6])
    else:
        analyze(*sys.argv[2:5])
