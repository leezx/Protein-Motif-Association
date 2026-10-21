"""Step 4a §17 A: study independence — provenance coverage, per-protein study influence, pair robustness tiers,
context replication, and targeted QC (SRP158854, Hep G2 BAF). Flags only; nothing is removed.

usage: 20_study_influence.py <occupancy.bed.gz> <class_annotation_v1_1.csv> <blacklist.bed.gz> <chrom.sizes>
                             <study_provenance.tsv> <validation_v1_1/protein dir> <out_dir> [workers]
Rules: occupancy as §13 (500 bp, k = max(floor, ceil(0.05 n)), floor 2 for all, 1 within a cell type); every
subset recomputes k on its own experiment count.
"""
import collections
import csv
import gzip
import importlib.util
import json
import math
import multiprocessing as mp
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("val", HERE / "16_cooccupancy_validation.py")
val = importlib.util.module_from_spec(_spec); sys.modules["val"] = val; _spec.loader.exec_module(val)
cooc = val.cooc
BAF = ["SMARCA4", "SMARCA2", "SMARCC1", "SMARCC2", "SMARCB1", "SMARCE1", "ARID1A", "ARID1B"]
QC_STUDY = "SRP158854"


def kthr(n, floor):
    return max(min(floor, n), math.ceil(0.05 * n))


def occ(b, e, emask, n, floor, valid):
    if n == 0:
        return np.empty(0, dtype=np.int64)
    u, c = np.unique(b[emask[e]], return_counts=True)
    o = u[c >= kthr(n, floor)]
    return o[valid[o]]


def write_tsv(path, rows):
    with open(path, "w") as w:
        if not rows:
            return
        cols = list(rows[0]); w.write("\t".join(cols) + "\n")
        for r in rows:
            w.write("\t".join(str(r.get(c, "")) for c in cols) + "\n")


def main(bed, ann, blp, sizes_path, study_tsv, v11_dir, out, workers=6):
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    v11_dir = Path(v11_dir)
    prov = {r["experiment_id"]: r for r in csv.DictReader(open(study_tsv), delimiter="\t")}
    study = {e: r["study"] for e, r in prov.items()}
    X, names, cls, n_exp, floor, offs, sizes = cooc.build_occupancy(bed, ann, blp, sizes_path, "all", workers)
    colsum = np.asarray(X.sum(axis=0)).ravel(); universe = colsum > 0
    nohot = universe & (colsum < np.quantile(colsum[universe], 0.99))
    nbins = X.shape[1]
    notbl = np.ones(nbins, dtype=bool)
    for c, bs in cooc.load_blacklist(blp, sizes).items():
        if c in offs:
            notbl[np.fromiter(bs, dtype=np.int64) + offs[c]] = False
    idx = {g: i for i, g in enumerate(names)}
    meta = {}
    exp_ids, exp_index = [], {}
    with gzip.open(Path(bed).with_name("PMA_chipatlas_hg38_experiments.tsv.gz"), "rt") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            meta.setdefault(r["experiment_id"], r)
            if r["antigen_hgnc_symbol"] in idx and r["experiment_id"] not in exp_index:
                exp_index[r["experiment_id"]] = len(exp_ids); exp_ids.append((r["experiment_id"], r["antigen_hgnc_symbol"]))
    # ---------- provenance coverage of the protein input ----------
    allp = [e for e, r in meta.items()]
    used = [e for e, _ in exp_ids]
    cov = dict(v1_experiments=len(allp), v1_mapped=sum(e in prov for e in allp),
               protein_input_experiments=len(used), protein_input_mapped=sum(e in prov for e in used),
               protein_input_studies=len({study.get(e, "single:" + e) for e in used}),
               protein_input_unmapped_singletons=sum(e not in prov for e in used))
    (out / "provenance_coverage.json").write_text(val.dumps(cov) + "\n")
    # ---------- scan ----------
    val.G.update(bed=bed, prot=idx, exps=exp_index)
    with mp.Pool(workers) as pool:
        parts = pool.map(val.scan, list(offs.items()))
    K = np.sort(np.concatenate(parts)); del parts
    bounds = np.searchsorted(K >> 40, np.arange(len(names) + 1))
    e_prot = np.array([idx[p] for _, p in exp_ids])
    st_names, e_study = np.unique(np.array([study.get(e, "single:" + e) for e, _ in exp_ids], dtype=object).astype(str),
                                  return_inverse=True)
    ct_names, e_ct = np.unique(np.array([meta[e]["cell_type"] for e, _ in exp_ids], dtype=object).astype(str),
                               return_inverse=True)
    ct_code = {c: k for k, c in enumerate(ct_names)}
    allm = np.ones(len(exp_ids), dtype=bool)

    def dec(i):
        return val.decode(K[bounds[i]:bounds[i + 1]])
    # ---------- per-protein study influence ----------
    infl_rows = []
    for i, g in enumerate(names):
        b, e = dec(i)
        mine = e_prot == i; n = int(mine.sum())
        sts = collections.Counter(e_study[mine])
        full = occ(b, e, allm, n, 2, notbl)
        best = None
        if len(sts) >= 2:
            u, c = np.unique(b, return_counts=True)
            es = e_study[e]; order = np.argsort(es, kind="stable"); bs_ = b[order]; es_ = es[order]
            for s, ns in sts.items():
                lo_, hi_ = np.searchsorted(es_, s), np.searchsorted(es_, s, side="right")
                us, cs = np.unique(bs_[lo_:hi_], return_counts=True)
                cm = c.copy(); cm[np.searchsorted(u, us)] -= cs
                om = u[cm >= kthr(n - ns, 2)]; om = om[notbl[om]]
                j = val.jac(full, om)
                if best is None or 1 - j > best[0]:
                    best = (1 - j, st_names[s], ns, len(om))
        infl_rows.append(dict(protein=g, protein_class=cls[g], n_experiments=n, n_studies=len(sts),
                              occupied_bins=len(full),
                              max_influence=round(best[0], 4) if best else "",
                              top_study=best[1] if best else "", top_study_experiments=best[2] if best else "",
                              bins_without_top_study=best[3] if best else "",
                              flag_high_influence=bool(best and best[0] >= 0.5)))
    infl_rows.sort(key=lambda r: -(r["max_influence"] or 0))
    write_tsv(out / "protein_study_influence.tsv", infl_rows)
    # ---------- pair tiers + context replication ----------
    bench = json.loads((v11_dir / "benchmark_validation.json").read_text()); p95 = bench["pair_jaccard_p95"]
    pairs = list(csv.DictReader(open(v11_dir / "pair_study_validation.tsv"), delimiter="\t"))
    tier_rows = []
    for r in pairs:
        full = float(r["jaccard_noHOT"]); lo = float(r["loso_min_jaccard"]) if r["loso_min_jaccard"] else float("nan")
        if r["status"] == "study_robust":
            tier = "tier1_high" if lo >= 0.5 * full else "tier2_moderate"
        elif r["status"] == "insufficient_independent_evidence":
            tier = "insufficient_coverage"
        else:
            tier = "study_dependent"
        i, j = idx[r["protein_a"]], idx[r["protein_b"]]
        (bi, ei), (bj, ej) = dec(i), dec(j)
        best = (float("nan"), "", 0, 0)
        if tier != "insufficient_coverage":
            cts = set(e_ct[e_prot == i]) & set(e_ct[e_prot == j]) - {ct_code.get(".", -1)}
            for ct in cts:
                si = set(e_study[(e_prot == i) & (e_ct == ct)]); sj = set(e_study[(e_prot == j) & (e_ct == ct)])
                mi = (e_prot == i) & (e_ct == ct) & ~np.isin(e_study, list(sj))
                mj = (e_prot == j) & (e_ct == ct) & ~np.isin(e_study, list(si))
                ni, nj = int(mi.sum()), int(mj.sum())
                if not ni or not nj:
                    continue
                jc = val.jac(occ(bi, ei, mi, ni, 1, nohot), occ(bj, ej, mj, nj, 1, nohot))
                if math.isnan(best[0]) or jc > best[0]:
                    best = (jc, ct_names[ct], ni, nj)
        rep = (not math.isnan(best[0])) and best[0] >= 0.5 * full and best[0] >= p95
        tier_rows.append(dict(protein_a=r["protein_a"], protein_b=r["protein_b"], kind=r["kind"], jaccard_noHOT=full,
                              loso_min_jaccard=r["loso_min_jaccard"], cross_study_jaccard=r["cross_study_jaccard"],
                              tier=tier, best_context=best[1],
                              context_cross_study_jaccard=round(best[0], 4) if not math.isnan(best[0]) else "",
                              context_n_exp_a=best[2], context_n_exp_b=best[3], context_replicated=rep))
    write_tsv(out / "pair_tiers.tsv", tier_rows)
    tiers = collections.Counter((r["kind"], r["tier"], r["context_replicated"]) for r in tier_rows)
    # ---------- targeted QC: SRP158854 ----------
    qc_rows = [dict(experiment_id=e, antigen=m["antigen_hgnc_symbol"] or m["antigen_raw"], cell_type=m["cell_type"],
                    treatment=m["treatment_status"], perturbation=m["perturbation"], antibody=m["antibody_raw"],
                    n_peaks=m["n_peaks_in_archive"], reads=m["reads"], pct_mapped=m["pct_mapped"],
                    qc_flags=m["qc_flags"], title=m["title"][:200])
               for e, m in meta.items() if study.get(e) == QC_STUDY]
    write_tsv(out / f"{QC_STUDY}_experiments.tsv", qc_rows)
    # ---------- targeted QC: Hep G2 vs K-562 BAF ----------
    baf_rows, baf_summary = [], {}
    for ct in ("Hep G2", "K-562"):
        per_exp = {}
        for g in BAF:
            if g not in idx:
                continue
            i = idx[g]; b, e = dec(i)
            m = (e_prot == i) & (e_ct == ct_code.get(ct, -1)); n = int(m.sum())
            if not n:
                continue
            baf_summary[f"{ct}|{g}"] = dict(n_experiments=n, n_studies=len(set(e_study[m])),
                                            occupied_bins_context=len(occ(b, e, m, n, 1, notbl)))
            for x in np.where(m)[0]:
                one = np.zeros(len(exp_ids), dtype=bool); one[x] = True
                bins = occ(b, e, one, 1, 1, notbl); per_exp[x] = (g, bins)
                eid = exp_ids[x][0]; mm = meta[eid]
                baf_rows.append(dict(cell_type=ct, protein=g, experiment_id=eid, study=st_names[e_study[x]],
                                     n_peaks=mm["n_peaks_in_archive"], occupied_bins=len(bins),
                                     antibody=mm["antibody_raw"], qc_flags=mm["qc_flags"], title=mm["title"][:150]))
        xs = sorted(per_exp)
        cross = [val.jac(per_exp[a][1], per_exp[b][1]) for k, a in enumerate(xs) for b in xs[k + 1:]
                 if per_exp[a][0] != per_exp[b][0]]
        baf_summary[f"{ct}|experiment_pairwise_jaccard_between_subunits"] = dict(
            n_pairs=len(cross), median=round(float(np.median(cross)), 4) if cross else None)
    write_tsv(out / "baf_hepg2_k562_qc.tsv", baf_rows)
    summ = dict(provenance=cov, flagged_high_influence=sum(r["flag_high_influence"] for r in infl_rows),
                proteins_with_2plus_studies=sum(1 for r in infl_rows if r["max_influence"] != ""),
                top_influence=[{k: r[k] for k in ("protein", "n_experiments", "n_studies", "max_influence", "top_study",
                                                  "top_study_experiments")} for r in infl_rows[:25]],
                selected={r["protein"]: {k: r[k] for k in ("n_studies", "max_influence", "top_study", "top_study_experiments")}
                          for r in infl_rows if r["protein"] in ("ESR1", "CTCF", "HMGA1", "PPARA", "SMARCA4", "SMARCC2", "SMARCE1")},
                tiers={f"{k}|{t}|context_replicated={c}": v for (k, t, c), v in sorted(tiers.items())},
                pair_jaccard_p95=p95, srp158854_experiments=len(qc_rows), baf=baf_summary)
    (out / "summary.json").write_text(val.dumps(summ) + "\n")
    print(val.dumps(summ)[:4000])


if __name__ == "__main__":
    a = sys.argv[1:]
    main(*a[:7], workers=int(a[7]) if len(a) > 7 else 6)
