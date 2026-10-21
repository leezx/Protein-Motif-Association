"""Two-tier hotspot BEDs for protein binding and open chromatin (§18, frozen 2026-10-21).

usage: 25_hotspot_beds.py <bins500.npz> <chrom.sizes> <out_dir> [atac_n=18651] [dnase_n=2086]

Definitions (quantiles over bins with value > 0 in that track, 500 bp bins from 23_hotspot_bins.py):
  tiers   : top20 / top10 / top5 / top1 = Q0.80 / Q0.90 / Q0.95 / Q0.99 (v2; v1 had only top5 = "high", top1 = "extreme")
  protein : P_b >= Q_t(P | P>0)
  open    : A_b >= Q_t(A | A>0)  AND  D_b >= Q_t(D | D>0)
P = distinct non-histone proteins, A / D = ATAC / DNase experiments with a peak (bin maximum).
Tiers are nested (top1 ⊂ top5 ⊂ top10 ⊂ top20). Passing bins that touch on the same chromosome are merged into one region;
regions are annotation units, not independent motif sites. The per-assay tiers go to per_assay/.

BED6+6: chrom start end name score strand n_bins max_proteins max_atac_frac max_dnase_frac tier overlap_other
  score   = 1000 × ECDF rank of the region maximum among positive bins (open: the smaller of the ATAC and DNase ranks)
  tier    = strictest tier reached by any bin of the region (top1 < top5 < top10 < top20)
  overlap_other = fraction of the region's bins passing the other class at the same tier (protein ↔ open)
"""
import json
import sys
from pathlib import Path

import numpy as np

BIN = 500
TIERS = {"top20": 0.80, "top10": 0.90, "top5": 0.95, "top1": 0.99}  # loosest first
NAMES = ["none"] + list(TIERS)
AS = """table hotspot
"PMA ChIP-Atlas hotspot region (500 bp bins merged)"
(
string chrom; "Chromosome"
uint chromStart; "Start"
uint chromEnd; "End"
string name; "Region id"
uint score; "1000 x ECDF rank of region maximum"
char[1] strand; "Unstranded"
uint nBins; "Number of 500 bp bins"
uint maxProteins; "Max distinct proteins in a bin"
float maxAtacFrac; "Max fraction of ATAC experiments with a peak"
float maxDnaseFrac; "Max fraction of DNase experiments with a peak"
string tier; "strictest tier reached: top1, top5, top10 or top20"
float overlapOther; "Fraction of bins passing the other class at the same tier"
)
"""


def ecdf_rank(v):
    """Fraction of positive bins with value <= v, for every bin (0 for v == 0)."""
    pos = np.sort(v[v > 0])
    return np.searchsorted(pos, v, side="right") / pos.size


def regions(mask, offs, nb):
    idx = np.flatnonzero(mask)
    if idx.size == 0:
        return idx, idx, idx
    ci = np.searchsorted(offs, idx, side="right") - 1
    brk = np.flatnonzero((np.diff(idx) != 1) | (np.diff(ci) != 0)) + 1
    starts = np.concatenate([[0], brk]); ends = np.concatenate([brk, [idx.size]])
    return idx, starts, ends


def write_bed(path, prefix, mask, level, other, offs, nb, chroms, sizes, P, A, D, rank):
    idx, s, e = regions(mask, offs, nb)
    ci = np.searchsorted(offs, idx[s], side="right") - 1 if idx.size else idx
    red = lambda x, f: f.reduceat(x[idx], s) if idx.size else np.array([])
    mP, mA, mD, mR = red(P, np.maximum), red(A, np.maximum), red(D, np.maximum), red(rank, np.maximum)
    lev = red(level, np.maximum); ov = red(other.astype(np.int64), np.add)
    lines = []
    for k in range(s.size):
        c = chroms[ci[k]]; b0 = idx[s[k]] - offs[ci[k]]; n = int(e[k] - s[k])
        st, en = int(b0 * BIN), int(min((b0 + n) * BIN, sizes[c]))
        lines.append(f"{c}\t{st}\t{en}\t{prefix}_{k + 1:06d}\t{int(round(1000 * mR[k]))}\t.\t{n}\t{int(mP[k])}\t"
                     f"{mA[k]:.4f}\t{mD[k]:.4f}\t{NAMES[lev[k]]}\t{ov[k] / n:.3f}\n")
    Path(path).write_text("".join(lines))
    L = (e - s) * BIN if idx.size else np.array([0])
    return {"bins": int(mask.sum()), "Mb": mask.sum() * BIN / 1e6, "regions": int(s.size),
            "region_bins_median": float(np.median(e - s)) if idx.size else 0, "region_bp_max": int(L.max()),
            "pct_regions_single_bin": float(100 * np.mean((e - s) == 1)) if idx.size else 0}


def main(npz, sizes_path, out, *opts):
    o = dict(a.split("=") for a in opts)
    out = Path(out); (out / "per_assay").mkdir(parents=True, exist_ok=True)
    z = np.load(npz); chroms = [str(c) for c in z["chrom"]]; offs = z["offset"]; nb = z["n_bins"]
    sizes = {l.split()[0]: int(l.split()[1]) for l in open(sizes_path) if l.strip()}
    P = z["proteins"].astype(np.int64)
    den = {"protein": None, "atac": int(o.get("atac_n", 18651)), "dnase": int(o.get("dnase_n", 2086))}
    A = z["atac_experiments"] / den["atac"]; D = z["dnase_experiments"] / den["dnase"]
    tr = {"protein": (P, z["proteins"]), "atac": (A, z["atac_experiments"]), "dnase": (D, z["dnase_experiments"])}
    thr, M = {}, {}
    for name, (v, cnt) in tr.items():
        pos = cnt[cnt > 0]
        for t, q in TIERS.items():
            qv = float(np.quantile(pos, q)); m = cnt >= qv
            thr[f"{name}_{t}"] = {"quantile": q, "q_value_count": qv, "threshold_count_ge": int(np.ceil(qv)),
                                  "threshold_fraction": int(np.ceil(qv)) / den[name] if den[name] else None,
                                  "bins_at_threshold": int((cnt == np.ceil(qv)).sum()),
                                  "realized_pct_of_positive": float(100 * m.sum() / pos.size)}
            M[f"{name}_{t}"] = m
    for t in TIERS:
        M[f"open_{t}"] = M[f"atac_{t}"] & M[f"dnase_{t}"]
    LV = {c: sum(M[f"{c}_{t}"].astype(np.int8) for t in TIERS) for c in ("protein", "open", "atac", "dnase")}
    rP, rA, rD = ecdf_rank(z["proteins"]), ecdf_rank(z["atac_experiments"]), ecdf_rank(z["dnase_experiments"])
    rO = np.minimum(rA, rD)
    summ = {"definition": __doc__.split("\n\n")[1], "thresholds": thr, "files": {}, "overlap": {}}
    for t in TIERS:
        for cls, rank, other in (("protein", rP, "open"), ("open", rO, "protein")):
            f = f"PMA_hotspot_{cls}_{t}.bed"
            summ["files"][f] = write_bed(out / f, f"{cls}HOT_{t}", M[f"{cls}_{t}"], LV[cls], M[f"{other}_{t}"],
                                          offs, nb, chroms, sizes, P, A, D, rank)
        for a, rank in (("atac", rA), ("dnase", rD)):
            f = f"per_assay/PMA_hotspot_{a}_{t}.bed"
            summ["files"][f] = write_bed(out / f, f"{a}HOT_{t}", M[f"{a}_{t}"], LV[a], M[f"protein_{t}"],
                                          offs, nb, chroms, sizes, P, A, D, rank)
        a, d, p, op = M[f"atac_{t}"], M[f"dnase_{t}"], M[f"protein_{t}"], M[f"open_{t}"]
        summ["overlap"][t] = {"atac_bins": int(a.sum()), "dnase_bins": int(d.sum()), "atac_and_dnase": int(op.sum()),
                              "pct_of_atac_in_both": 100 * op.sum() / a.sum(), "pct_of_dnase_in_both": 100 * op.sum() / d.sum(),
                              "protein_and_open": int((p & op).sum()), "pct_protein_bins_open": 100 * (p & op).sum() / p.sum(),
                              "pct_open_bins_protein": 100 * (p & op).sum() / op.sum(),
                              "jaccard_protein_open": (p & op).sum() / (p | op).sum()}
    (out / "hotspot.as").write_text(AS)
    (out / "summary.json").write_text(json.dumps(summ, indent=1, default=float))
    print(json.dumps({k: v for k, v in summ.items() if k != "definition"}, indent=1, default=float))


if __name__ == "__main__":
    main(*sys.argv[1:])
