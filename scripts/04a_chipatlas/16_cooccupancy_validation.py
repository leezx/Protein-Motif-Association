"""Step 4a §16 (v1.1 validation gate): study-aware protein co-occupancy validation.

usage: 16_cooccupancy_validation.py <occupancy.bed.gz> <class_annotation_v1_1.csv> <blacklist.bed.gz> <chrom.sizes>
                                    <complexportal_9606.tsv> <hgnc_complete_set.txt> <study_provenance.tsv> <out_dir>
                                    [workers]
Writes complex_recovery_validation.tsv, benchmark_validation.json, pair_study_validation.tsv,
complex_coverage.tsv. Definitions: design §13 (occupancy) and §16 (L1-b, L1-c).
"""
import array
import collections
import csv
import gzip
import importlib.util
import json
import math
import multiprocessing as mp
import subprocess
import sys
from pathlib import Path

import numpy as np
from scipy import sparse

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("cooc", HERE / "12_cooccupancy.py")
cooc = importlib.util.module_from_spec(_spec); sys.modules["cooc"] = cooc; _spec.loader.exec_module(cooc)
BIN = cooc.BIN
CORE = ["RAD21", "SMC1A", "SMC3", "STAG1", "STAG2"]
G = {}


def scan(args):
    chrom, off = args
    keys = array.array("q")
    prot, exps = G["prot"], G["exps"]
    p = subprocess.Popen(["tabix", G["bed"], chrom], stdout=subprocess.PIPE, text=True, bufsize=1 << 20)
    for line in p.stdout:
        f = line.split("\t", 10)
        pi = prot.get(f[8]); ei = exps.get(f[3])
        if pi is None or ei is None:
            continue
        s, e = int(f[1]), int(f[2])
        for b in range(s // BIN, (e - 1) // BIN + 1):
            keys.append((pi << 40) | ((off + b) << 16) | ei)
    assert p.wait() == 0
    return np.unique(np.frombuffer(keys, dtype=np.int64))


def kthr(n, floor=2):
    return max(min(floor, n), math.ceil(0.05 * n))


def decode(keys_p):
    return (keys_p >> 16) & ((1 << 24) - 1), (keys_p & 0xFFFF).astype(np.int64)


def occ_bins(be, emask, n_sub, valid):
    """Occupied valid global bins of one protein from its decoded (bin, exp) arrays, experiments in emask only."""
    if n_sub == 0:
        return np.empty(0, dtype=np.int64)
    b, e = be
    m = emask[e]
    u, c = np.unique(b[m], return_counts=True)
    occ = u[c >= kthr(n_sub)]
    return occ[valid[occ]]


def jac(a, b):
    if len(a) == 0 or len(b) == 0:
        return 0.0
    i = len(np.intersect1d(a, b, assume_unique=True))
    return i / (len(a) + len(b) - i)


def auroc_ap(scores, labels):
    from sklearn.metrics import average_precision_score, roc_auc_score
    if labels.sum() == 0 or labels.sum() == len(labels):
        return float("nan"), float("nan")
    return float(roc_auc_score(labels, scores)), float(average_precision_score(labels, scores))


def pair_metrics(J, names, same_pairs, rng, nboot=1000):
    n = len(names)
    iu = np.triu_indices(n, 1)
    P = np.zeros((n, n), dtype=bool)
    for a, b in same_pairs:
        P[a, b] = P[b, a] = True
    lab = P[iu]
    au, ap = auroc_ap(J[iu], lab)
    bs_au, bs_ap = [], []
    for _ in range(nboot):
        idx = np.unique(rng.choice(n, n, replace=True))
        sub = J[np.ix_(idx, idx)]
        ii = np.triu_indices(len(idx), 1)
        sl = P[np.ix_(idx, idx)][ii]
        a1, a2 = auroc_ap(sub[ii], sl)
        if not math.isnan(a1):
            bs_au.append(a1); bs_ap.append(a2)
    q = lambda v: [round(float(np.quantile(v, 0.025)), 4), round(float(np.quantile(v, 0.975)), 4)] if v else None
    return dict(n_proteins=n, n_pairs=int(len(lab)), n_positive_pairs=int(lab.sum()), auroc=round(au, 4),
                auroc_ci95=q(bs_au), pr_auc=round(ap, 4), pr_auc_ci95=q(bs_ap),
                pr_auc_baseline=round(float(lab.mean()), 5))


def bh(p):
    p = np.asarray(p, dtype=float); n = len(p); o = np.argsort(p)
    q = np.empty(n); prev = 1.0
    for r, i in enumerate(o[::-1]):
        k = n - r
        prev = min(prev, p[i] * n / k); q[i] = prev
    return q


def jaccard_matrix(X, cols):
    Xm = X[:, cols]
    a = np.asarray(Xm.sum(axis=1)).ravel()
    inter = (Xm @ Xm.T).toarray()
    union = a[:, None] + a[None, :] - inter
    J = np.where(union > 0, inter / np.maximum(union, 1), 0.0)
    np.fill_diagonal(J, 1.0)
    return J, a


def main(bed, ann, blp, sizes_path, cp, hgnc, study_tsv, out, workers=6):
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(20261021)
    study = {}
    with open(study_tsv) as f:
        for r in csv.DictReader(f, delimiter="\t"):
            study[r["experiment_id"]] = r["study"]
    # ---------- base occupancy (context all), identical rules to §13 ----------
    X, genes, cls, n_exp, floor, offs, sizes = cooc.build_occupancy(bed, ann, blp, sizes_path, "all", workers)
    colsum = np.asarray(X.sum(axis=0)).ravel()
    universe = colsum > 0
    hot_cut = np.quantile(colsum[universe], 0.99)
    nohot = universe & (colsum < hot_cut)
    J, breadth = jaccard_matrix(X, np.where(nohot)[0])
    names = genes; idx = {g: i for i, g in enumerate(names)}
    cpx = cooc.complexes(cp, hgnc, set(names))
    cpx_all = cooc.complexes(cp, hgnc, set(cls) | {"CTCF"})  # members mappable to HGNC among annotated proteins
    same = set()
    for gs in cpx.values():
        for a in range(len(gs)):
            for b in range(a + 1, len(gs)):
                same.add(tuple(sorted((idx[gs[a]], idx[gs[b]]))))
    bench = dict(context="all", proteins=len(names), nohot_bins=int(nohot.sum()), hot_cut=float(hot_cut))
    bench["pair_metrics_all"] = pair_metrics(J, names, same, rng)
    # ---------- breadth-matched null per complex ----------
    dec = np.digitize(breadth, np.quantile(breadth, np.linspace(0.1, 0.9, 9)))
    pools = {d: np.where(dec == d)[0] for d in range(10)}
    rows = []
    for nm, gs in cpx.items():
        ii = np.array([idx[g] for g in gs])
        tri = np.triu_indices(len(ii), 1)
        obs = float(np.median(J[np.ix_(ii, ii)][tri]))
        m = len(ii)
        rr = np.stack([rng.choice(pools[dec[i]], 10000) for i in ii], axis=1)
        ok = np.array([len(set(r)) == m for r in rr])
        rr = rr[ok]
        null = np.median(J[rr[:, tri[0]], rr[:, tri[1]]], axis=1)
        p_b = (1 + (null >= obs).sum()) / (1 + len(null))
        rs = np.argsort(rng.random((2000, len(names))), axis=1)[:, :m]
        null_s = np.median(J[rs[:, tri[0]], rs[:, tri[1]]], axis=1)
        p_s = (1 + (null_s >= obs).sum()) / (1 + len(null_s))
        rows.append(dict(complex=nm, members=";".join(gs), n_members_present=len(gs),
                         n_members_mapped=len(cpx_all.get(nm, gs)), median_jaccard=round(obs, 4),
                         null_breadth_median=round(float(np.median(null)), 4), p_breadth_matched=p_b,
                         null_size_median=round(float(np.median(null_s)), 4), p_size_matched_unadjusted=p_s))
    q_all = bh([r["p_breadth_matched"] for r in rows])
    first = {}
    for r, q in zip(rows, q_all):
        r["fdr_bh_all"] = round(float(q), 5); first.setdefault(r["members"], r)
    q_dist = bh([r["p_breadth_matched"] for r in first.values()])
    for r, q in zip(first.values(), q_dist):
        r["fdr_bh_distinct_sets"] = round(float(q), 5)
    for r in rows:
        r.setdefault("fdr_bh_distinct_sets", first[r["members"]]["fdr_bh_distinct_sets"])
        r["p_breadth_matched"] = round(r["p_breadth_matched"], 5); r["p_size_matched_unadjusted"] = round(r["p_size_matched_unadjusted"], 5)
    rows.sort(key=lambda r: r["p_breadth_matched"])
    with open(out / "complex_recovery_validation.tsv", "w") as w:
        cols = list(rows[0]); w.write("\t".join(cols) + "\n")
        for r in rows:
            w.write("\t".join(str(r[c]) for c in cols) + "\n")
    bench["complexes_tested"] = len(rows)
    bench["nominal_p05_breadth"] = sum(r["p_breadth_matched"] <= 0.05 for r in rows)
    bench["fdr05_all"] = sum(r["fdr_bh_all"] <= 0.05 for r in rows)
    bench["distinct_sets"] = len(first); bench["fdr05_distinct_sets"] = sum(r["fdr_bh_distinct_sets"] <= 0.05 for r in first.values())
    bench["nominal_p05_size_unadjusted"] = sum(r["p_size_matched_unadjusted"] <= 0.05 for r in rows)
    # physical cohesin core vs functional CTCF-cohesin
    core = [g for g in CORE if g in idx]
    tri = np.triu_indices(len(core), 1)
    bench["cohesin_core_physical"] = dict(members=core, median_jaccard=round(float(np.median(J[np.ix_([idx[g] for g in core], [idx[g] for g in core])][tri])), 4))
    if "CTCF" in idx:
        bench["ctcf_cohesin_functional"] = {g: round(float(J[idx["CTCF"], idx[g]]), 4) for g in core}
        bench["ctcf_jaccard_percentile_vs_all_pairs"] = round(float((J[np.triu_indices(len(names), 1)] < np.median(list(bench["ctcf_cohesin_functional"].values()))).mean()), 4)
    # ---------- per-complex coverage ----------
    exp_tab = Path(bed).with_name("PMA_chipatlas_hg38_experiments.tsv.gz")
    exps_of = collections.defaultdict(list)
    with gzip.open(exp_tab, "rt") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            exps_of[r["antigen_hgnc_symbol"]].append(r["experiment_id"])
    with open(out / "complex_coverage.tsv", "w") as w:
        w.write("complex\tmembers_mapped\tmembers_in_pma\tmember_experiments\tmember_studies\n")
        for nm, gs in sorted(cpx_all.items()):
            inn = [g for g in gs if g in idx]
            if not inn:
                continue
            w.write(f"{nm}\t{len(gs)}\t{len(inn)}\t" + ";".join(f"{g}:{len(exps_of[g])}" for g in gs) + "\t"
                    + ";".join(f"{g}:{len({study.get(e, e) for e in exps_of[g]})}" for g in gs) + "\n")
    # ---------- matched universe K-562 / Hep G2 ----------
    ctx = {}
    for c in ("K-562", "Hep G2"):
        Xc, gc, *_ = cooc.build_occupancy(bed, ann, blp, sizes_path, c, workers)
        cs = np.asarray(Xc.sum(axis=0)).ravel(); uc = cs > 0
        hc = np.quantile(cs[uc], 0.99)
        Jc, _ = jaccard_matrix(Xc, np.where(uc & (cs < hc))[0])
        ctx[c] = (Jc, gc)
    common = sorted(set(ctx["K-562"][1]) & set(ctx["Hep G2"][1]))
    cpx_c = cooc.complexes(cp, hgnc, set(common)); ic = {g: i for i, g in enumerate(common)}
    same_c = set()
    for gs in cpx_c.values():
        for a in range(len(gs)):
            for b in range(a + 1, len(gs)):
                same_c.add(tuple(sorted((ic[gs[a]], ic[gs[b]]))))
    bench["matched_universe"] = {"proteins": len(common), "complexes": len(cpx_c)}
    for c, (Jc, gc) in ctx.items():
        pos = [gc.index(g) for g in common]
        bench["matched_universe"][c] = pair_metrics(Jc[np.ix_(pos, pos)], common, same_c, rng)
        named = {}
        for nm, gs in (("cohesin_core", CORE), ("BAF", ["SMARCA4", "SMARCA2", "SMARCC1", "SMARCC2", "SMARCB1", "ARID1A", "ARID1B", "SMARCE1"]),
                       ("PRC2", ["EZH2", "SUZ12", "EED", "JARID2", "MTF2"]), ("NuRD", ["CHD4", "HDAC1", "HDAC2", "MTA1", "MTA2", "MTA3", "GATAD2A", "GATAD2B", "MBD3"])):
            g2 = [g for g in gs if g in ic]
            if len(g2) >= 2:
                pp = [gc.index(g) for g in g2]; tt = np.triu_indices(len(pp), 1)
                named[nm] = dict(members=g2, median_jaccard=round(float(np.median(Jc[np.ix_(pp, pp)][tt])), 4),
                                 context_median_all_pairs=round(float(np.median(Jc[np.ix_(pos, pos)][np.triu_indices(len(pos), 1)])), 4))
        bench["matched_universe"][c]["named"] = named
    # ---------- study-level LOSO / cross-study for candidate pairs ----------
    exps_sorted = None
    exp_ids = []; exp_index = {}
    with gzip.open(exp_tab, "rt") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if r["antigen_hgnc_symbol"] in idx and r["experiment_id"] not in exp_index:
                exp_index[r["experiment_id"]] = len(exp_ids); exp_ids.append((r["experiment_id"], r["antigen_hgnc_symbol"]))
    G.update(bed=bed, prot=idx, exps=exp_index)
    chroms = list(offs)
    with mp.Pool(workers) as pool:
        parts = pool.map(scan, [(c, offs[c]) for c in chroms])
    K = np.sort(np.concatenate(parts)); del parts
    pk = K >> 40
    bounds = np.searchsorted(pk, np.arange(len(names) + 1))
    valid = nohot.copy()
    e_prot = np.array([idx[p] for _, p in exp_ids]); e_study = np.array([study.get(e, "single:" + e) for e, _ in exp_ids])
    studies_of = {i: sorted(set(e_study[e_prot == i])) for i in range(len(names))}
    iu = np.triu_indices(len(names), 1)
    vals = J[iu]; p95 = float(np.quantile(vals, 0.95))
    nonc = [(i, j) for i, j in zip(*iu) if (i, j) not in same]
    nonc.sort(key=lambda x: -J[x])
    cand = [(i, j, "complex_portal") for i, j in sorted(same)] + [(i, j, "top_non_complex") for i, j in nonc[:300]]
    allm = np.ones(len(exp_ids), dtype=bool)
    out_rows = []
    for i, j, kind in cand:
        ki, kj = decode(K[bounds[i]:bounds[i + 1]]), decode(K[bounds[j]:bounds[j + 1]])
        si, sj = studies_of[i], studies_of[j]
        shared = sorted(set(si) & set(sj))
        full = float(J[i, j])
        loso = []
        for s in sorted(set(si) | set(sj)):
            m = allm & (e_study != s)
            ni = int((m & (e_prot == i)).sum()); nj = int((m & (e_prot == j)).sum())
            loso.append(jac(occ_bins(ki, m, ni, valid), occ_bins(kj, m, nj, valid)))
        mi = (e_prot == i) & ~np.isin(e_study, sj); mj = (e_prot == j) & ~np.isin(e_study, si)
        ni, nj = int(mi.sum()), int(mj.sum())
        cross = jac(occ_bins(ki, mi, ni, valid), occ_bins(kj, mj, nj, valid)) if ni and nj else float("nan")
        if len(si) < 2 or len(sj) < 2 or not ni or not nj:
            status = "insufficient_independent_evidence"
        elif cross >= 0.5 * full and cross >= p95:
            status = "study_robust"
        else:
            status = "study_dependent"
        out_rows.append(dict(protein_a=names[i], protein_b=names[j], kind=kind, jaccard_noHOT=round(full, 4),
                             n_studies_a=len(si), n_studies_b=len(sj), shared_studies=len(shared),
                             loso_min_jaccard=round(min(loso), 4) if loso else "", cross_study_jaccard=round(cross, 4) if not math.isnan(cross) else "",
                             cross_n_exp_a=ni, cross_n_exp_b=nj, status=status))
    with open(out / "pair_study_validation.tsv", "w") as w:
        cols = list(out_rows[0]); w.write("\t".join(cols) + "\n")
        for r in out_rows:
            w.write("\t".join(str(r[c]) for c in cols) + "\n")
    st = collections.Counter((r["kind"], r["status"]) for r in out_rows)
    bench["pair_study_status"] = {f"{k}|{s}": v for (k, s), v in sorted(st.items())}
    bench["pair_jaccard_p95"] = round(p95, 4)
    (out / "benchmark_validation.json").write_text(json.dumps(bench, indent=1) + "\n")
    print(json.dumps(bench)[:4000])


if __name__ == "__main__":
    a = sys.argv[1:]
    main(*a[:8], workers=int(a[8]) if len(a) > 8 else 6)
