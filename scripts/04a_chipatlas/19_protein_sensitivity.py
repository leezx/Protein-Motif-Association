"""Step 4a §17 B/C: complex-recovery sensitivity for one occupancy variant (bin size / threshold via PMA_BIN, PMA_KFRAC).

usage: 19_protein_sensitivity.py <occupancy.bed.gz> <class_annotation_v1_1.csv> <blacklist.bed.gz> <chrom.sizes>
                                 <complexportal_9606.tsv> <hgnc_complete_set.txt> <out_dir> [workers]
Writes complex_recovery.tsv and summary.json:
- pair metrics (AUROC, PR-AUC, protein-resampling CI) on all bins and on non-HOT bins;
- per complex: p under (all bins, size-matched), (non-HOT, size-matched), (non-HOT, breadth-matched);
- BH over all entries and over distinct member sets (representative = minimum-p entry; first-entry kept for
  comparison with v1.1);
- named physical complexes.
PMA_SENS_MATCHED=1 also writes the K-562 / Hep G2 matched-universe precision@20/50 and top-50 overlap.
"""
import collections
import importlib.util
import json
import os
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("val", HERE / "16_cooccupancy_validation.py")
val = importlib.util.module_from_spec(_spec); sys.modules["val"] = val; _spec.loader.exec_module(val)
cooc = val.cooc
NAMED = ["CPX-5989", "CPX-5991", "CPX-4206", "CPX-6267", "CPX-3323", "CPX-2327", "CPX-880", "CPX-922", "CPX-9065",
         "CPX-3227", "CPX-915"]
N_BREADTH, N_SIZE = 10000, 2000


def pvals(J, ii, tri, obs, pools, dec, rng, m, n):
    rr = np.stack([rng.choice(pools[dec[i]], N_BREADTH) for i in ii], axis=1)
    rr = rr[np.array([len(set(r)) == m for r in rr])]
    p_b = (1 + (np.median(J[rr[:, tri[0]], rr[:, tri[1]]], axis=1) >= obs).sum()) / (1 + len(rr))
    return p_b


def size_p(J, tri, obs, rs):
    null = np.median(J[rs[:, tri[0]], rs[:, tri[1]]], axis=1)
    return (1 + (null >= obs).sum()) / (1 + len(null))


def distinct_bh(rows, key, rep):
    """BH over distinct member sets; representative = minimum p (rep='min') or first entry (rep='first')."""
    groups = collections.OrderedDict()
    for r in rows:
        groups.setdefault(r["members"], []).append(r)
    reps = [min(g, key=lambda r: r[key]) if rep == "min" else g[0] for g in groups.values()]
    q = val.bh([r[key] for r in reps])
    return len(reps), int((q <= 0.05).sum()), int(sum(r[key] <= 0.05 for r in reps))


def top_overlap(Jc, common, same_c, n):
    iu = np.triu_indices(len(common), 1)
    order = np.argsort(-Jc[iu], kind="stable")[:n]
    pairs = [(iu[0][o], iu[1][o]) for o in order]
    return pairs, float(np.mean([p in same_c for p in pairs]))


def main(bed, ann, blp, sizes_path, cp, hgnc, out, workers=6):
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(20261021)
    X, names, cls, n_exp, floor, offs, sizes = cooc.build_occupancy(bed, ann, blp, sizes_path, "all", workers)
    colsum = np.asarray(X.sum(axis=0)).ravel(); universe = colsum > 0
    hot_cut = np.quantile(colsum[universe], 0.99); nohot = universe & (colsum < hot_cut)
    J_all, _ = val.jaccard_matrix(X, np.where(universe)[0])
    J_nh, breadth = val.jaccard_matrix(X, np.where(nohot)[0])
    idx = {g: i for i, g in enumerate(names)}
    cpx = cooc.complexes(cp, hgnc, set(names))
    same = {tuple(sorted((idx[a], idx[b]))) for gs in cpx.values() for x, a in enumerate(gs) for b in gs[x + 1:]}
    summ = dict(bin_bp=cooc.BIN, kfrac=cooc.KFRAC, proteins=len(names), universe_bins=int(universe.sum()),
                nohot_bins=int(nohot.sum()), hot_cut=float(hot_cut), complexes=len(cpx))
    summ["pair_metrics_nohot"] = val.pair_metrics(J_nh, names, same, rng)
    summ["pair_metrics_all_bins"] = val.pair_metrics(J_all, names, same, rng)
    summ["ci_label"] = "protein-resampling CI (1,000 resamples of proteins)"
    dec = np.digitize(breadth, np.quantile(breadth, np.linspace(0.1, 0.9, 9)))
    pools = {d: np.where(dec == d)[0] for d in range(10)}
    rows = []
    for nm, gs in cpx.items():
        ii = np.array([idx[g] for g in gs]); m = len(ii); tri = np.triu_indices(m, 1)
        obs_nh = float(np.median(J_nh[np.ix_(ii, ii)][tri])); obs_all = float(np.median(J_all[np.ix_(ii, ii)][tri]))
        rs = np.argsort(rng.random((N_SIZE, len(names))), axis=1)[:, :m]
        rows.append(dict(complex=nm, members=";".join(gs), n_members=m, jaccard_nohot=round(obs_nh, 4),
                         jaccard_all_bins=round(obs_all, 4),
                         p_allbins_size=size_p(J_all, tri, obs_all, rs), p_nohot_size=size_p(J_nh, tri, obs_nh, rs),
                         p_nohot_breadth=pvals(J_nh, ii, tri, obs_nh, pools, dec, rng, m, len(names))))
    decomp = {}
    for key in ("p_allbins_size", "p_nohot_size", "p_nohot_breadth"):
        q = val.bh([r[key] for r in rows])
        for r, qq in zip(rows, q):
            r[key.replace("p_", "fdr_")] = round(float(qq), 5)
        nd, fdr_min, nom_min = distinct_bh(rows, key, "min")
        _, fdr_first, _ = distinct_bh(rows, key, "first")
        decomp[key] = dict(nominal_p05=int(sum(r[key] <= 0.05 for r in rows)), fdr05_all=int((q <= 0.05).sum()),
                           distinct_sets=nd, distinct_nominal_p05_minrep=nom_min, distinct_fdr05_minrep=fdr_min,
                           distinct_fdr05_firstrep=fdr_first)
    summ["hot_null_decomposition"] = decomp
    summ["fdr_label"] = "breadth-matched empirical FDR (BH); breadth = non-HOT occupied bins, deciles"
    summ["named"] = {r["complex"]: dict(jaccard_nohot=r["jaccard_nohot"], p=round(r["p_nohot_breadth"], 5),
                                        fdr=r["fdr_nohot_breadth"])
                     for r in rows if r["complex"].split()[0] in NAMED}
    if "CTCF" in idx:
        summ["ctcf_cohesin"] = {g: round(float(J_nh[idx["CTCF"], idx[g]]), 4) for g in val.CORE if g in idx}
    rows.sort(key=lambda r: r["p_nohot_breadth"])
    with open(out / "complex_recovery.tsv", "w") as w:
        cols = list(rows[0]); w.write("\t".join(cols) + "\n")
        for r in rows:
            w.write("\t".join(str(round(r[c], 5) if isinstance(r[c], float) else r[c]) for c in cols) + "\n")
    if os.environ.get("PMA_SENS_MATCHED") == "1":
        ctx = {}
        for c in ("K-562", "Hep G2"):
            Xc, gc, *_ = cooc.build_occupancy(bed, ann, blp, sizes_path, c, workers)
            cs = np.asarray(Xc.sum(axis=0)).ravel(); uc = cs > 0; hc = np.quantile(cs[uc], 0.99)
            ctx[c] = (val.jaccard_matrix(Xc, np.where(uc & (cs < hc))[0])[0], gc)
        common = sorted(set(ctx["K-562"][1]) & set(ctx["Hep G2"][1])); ic = {g: i for i, g in enumerate(common)}
        cpx_c = cooc.complexes(cp, hgnc, set(common))
        same_c = {tuple(sorted((ic[a], ic[b]))) for gs in cpx_c.values() for x, a in enumerate(gs) for b in gs[x + 1:]}
        mu = {"proteins": len(common), "positive_pairs": len(same_c)}
        tops = {}
        for c, (Jc, gc) in ctx.items():
            pos = [gc.index(g) for g in common]; Jm = Jc[np.ix_(pos, pos)]
            d = val.pair_metrics(Jm, common, same_c, rng)
            for n in (20, 50):
                pairs, prec = top_overlap(Jm, common, same_c, n)
                d[f"precision_at_{n}"] = round(prec, 3)
                if n == 50:
                    tops[c] = pairs
                    d["top50_pairs"] = [f"{common[a]}-{common[b]}{'*' if (a, b) in same_c else ''}" for a, b in pairs]
            mu[c] = d
        s1, s2 = set(tops["K-562"]), set(tops["Hep G2"])
        mu["top50_overlap"] = len(s1 & s2)
        mu["top50_overlap_pairs"] = [f"{common[a]}-{common[b]}" for a, b in sorted(s1 & s2)]
        mu["top50_overlap_same_complex"] = sum(p in same_c for p in s1 & s2)
        summ["matched_universe"] = mu
    (out / "summary.json").write_text(val.dumps(summ) + "\n")
    print(val.dumps(summ)[:3000])


if __name__ == "__main__":
    a = sys.argv[1:]
    main(*a[:7], workers=int(a[7]) if len(a) > 7 else 6)
