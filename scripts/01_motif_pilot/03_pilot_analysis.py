"""Step 1 pilot analysis: Q1 coverage, Q2 alternative patterns, Q3 clustering reuse.

Design: docs/STEP1_MOTIF_PILOT_DESIGN.md §3.3–3.6.
Full per-motif tables -> $PMA_MOTIF_RESULT/step1_motif_pilot/
Small summaries       -> <repo>/results/01_motif_pilot/
"""
import json
import os
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

PROC = Path(os.environ["PMA_MOTIF_PROCESSED"]) / "v0.1_pilot"
RES = Path(os.environ["PMA_MOTIF_RESULT"]) / "step1_motif_pilot"
REPO_RES = Path(__file__).resolve().parents[2] / "results" / "01_motif_pilot"

Q_PRIMARY, OV_PRIMARY = 0.01, 0.6
Q_GRID, OV_GRID = (0.001, 0.01, 0.05), (0.5, 0.6, 0.75)


def bh_per_query(t):
    """Per-query Benjamini-Hochberg (pi0=1) over all reported targets.
    Replaces TOMTOM's randomised-pi0 q-values (see design §3.3 amendment)."""
    t = t.copy()
    t["tomtom_q"] = t["q-value"]
    p = t["p-value"].to_numpy()
    q = np.empty_like(p)
    for _, idx in t.groupby("Query_ID").indices.items():
        pv = p[idx]
        order = np.argsort(pv)
        n = len(pv)
        adj = pv[order] * n / np.arange(1, n + 1)
        adj = np.minimum.accumulate(adj[::-1])[::-1]
        q[idx[order]] = np.minimum(adj, 1)
    t["q-value"] = q
    return t


def load():
    ja = pd.read_csv(PROC / "jaspar2026_core_vert_nr_metadata.tsv", sep="\t")
    cb = pd.read_csv(PROC / "codebook2026_motif_metadata.tsv", sep="\t")
    cb["cluster"] = pd.to_numeric(cb["Motif cluster"], errors="coerce")
    jc = bh_per_query(pd.read_csv(RES / "tomtom" / "jaspar_vs_codebook.tsv", sep="\t", comment="#"))
    cc = bh_per_query(pd.read_csv(RES / "tomtom" / "codebook_vs_codebook.tsv", sep="\t", comment="#"))
    length = pd.concat([ja.set_index("pma_id").length, cb.set_index("pma_id").length])
    for t in (jc, cc):
        t["min_len"] = np.minimum(t.Query_ID.map(length), t.Target_ID.map(length))
        t["ov_frac"] = t.Overlap / t.min_len
    cc = cc[cc.Query_ID != cc.Target_ID]
    return ja, cb, jc, cc


def matched(t, q, ov):
    return t[(t["q-value"] < q) & (t.ov_frac >= ov)]


def classify_jaspar(ja, cb, jc, q, ov):  # noqa: C901
    cb_tf = cb.set_index("pma_id").hgnc_current
    hits = matched(jc, q, ov).copy()
    hits["target_tf"] = hits.Target_ID.map(cb_tf)
    own = ja.set_index("pma_id").components_hgnc.str.split(";")
    hits["same_tf"] = [tt in own[qid] for qid, tt in zip(hits.Query_ID, hits.target_tf)]
    g = hits.groupby("Query_ID")
    out = ja[["pma_id", "name", "components_hgnc", "is_human", "n_components", "type",
              "tf_class", "length", "ic_total"]].copy()
    out["n_hits"] = out.pma_id.map(g.size()).fillna(0).astype(int)
    out["n_same_tf_hits"] = out.pma_id.map(g.same_tf.sum()).fillna(0).astype(int)
    best = hits.sort_values("q-value").drop_duplicates("Query_ID").set_index("Query_ID")
    out["best_target"] = out.pma_id.map(best.Target_ID)
    out["best_target_tf"] = out.pma_id.map(best.target_tf)
    out["best_q"] = out.pma_id.map(best["q-value"])
    cb_tfs = set(cb.hgnc_current)
    out["tf_has_codebook_pwm"] = out.components_hgnc.str.split(";").map(lambda c: any(x in cb_tfs for x in c))
    out["coverage_class"] = np.select(
        [out.n_same_tf_hits > 0, out.n_hits > 0], ["same_TF", "other_TF_only"], "not_represented")
    # other_TF_only refinement: a matched Codebook PWM shares a Supp. Table 10
    # cluster with a Codebook PWM of the query's own TF -> paralog-level match
    cb_clus = cb.set_index("pma_id").cluster
    own_clusters = cb.groupby("hgnc_current").cluster.agg(lambda c: set(c.dropna()))
    hit_clusters = hits.assign(c=hits.Target_ID.map(cb_clus)).groupby("Query_ID").c.agg(lambda c: set(c.dropna()))
    def paralog(r):
        mine = set().union(*[own_clusters.get(t, set()) for t in r.components_hgnc.split(";")])
        return bool(mine & hit_clusters.get(r.pma_id, set()))
    out["other_tf_paralog_cluster"] = [paralog(r) if c == "other_TF_only" else False
                                       for r, c in zip(out.itertuples(), out.coverage_class)]
    # near miss: best q (any target) between q and 0.05 -> likely short-motif power limit
    best_any = jc.groupby("Query_ID")["q-value"].min()
    out["best_q_any"] = out.pma_id.map(best_any)
    out["near_miss"] = (out.coverage_class == "not_represented") & (out.best_q_any < 0.05)
    out["length_bin"] = pd.cut(out.length, [0, 8, 10, 12, 15, 100], labels=["<=8", "9-10", "11-12", "13-15", ">15"])
    return out, hits


def q1_q2(ja, cb, cls):
    hum = cls[cls.is_human]
    comps = hum.components_hgnc.str.split(";").explode()
    cb_all, cb_direct = set(cb.hgnc_current), set(cb[cb.evidence_class == "direct"].hgnc_current)
    tf_cov = dict(
        jaspar_human_component_tfs=int(comps.nunique()),
        with_any_codebook_pwm=int(comps.drop_duplicates().isin(cb_all).sum()),
        with_direct_codebook_pwm=int(comps.drop_duplicates().isin(cb_direct).sum()),
    )
    motif_cov = {k: hum.coverage_class.value_counts().to_dict() for k in ["human"]}
    motif_cov["nonhuman"] = cls[~cls.is_human].coverage_class.value_counts().to_dict()
    # Q2 = patterns not kept by Codebook under the TF's own name
    q2 = hum[hum.coverage_class != "same_TF"]
    q2_tab = {
        "by_class": q2.groupby("coverage_class").size().to_dict(),
        "by_type": q2.groupby(["coverage_class", "type"]).size().unstack(0, fill_value=0),
        "by_dimer": q2.assign(dimer=q2.n_components > 1).groupby(["coverage_class", "dimer"]).size().unstack(0, fill_value=0),
        "by_tf_has_cb": q2.groupby(["coverage_class", "tf_has_codebook_pwm"]).size().unstack(0, fill_value=0),
    }
    # IC comparison: are not_represented motifs low-information?
    ic = hum.assign(ic_per_pos=hum.ic_total / hum.length).groupby("coverage_class").ic_per_pos.describe()
    # multi-motif TFs (monomeric JASPAR names only)
    mono = hum[hum.n_components == 1]
    multi = mono.groupby("components_hgnc").filter(lambda d: len(d) > 1)
    mm = multi.groupby("components_hgnc").agg(
        n_jaspar=("pma_id", "size"),
        n_same_tf=("coverage_class", lambda s: (s == "same_TF").sum()),
        n_distinct_best=("best_target", lambda s: s.dropna().nunique()),
        n_unmatched=("coverage_class", lambda s: (s == "not_represented").sum()))
    return tf_cov, motif_cov, q2_tab, ic, mm


def q3(cb, cc, cls_hits, q, ov):
    clus = cb.set_index("pma_id").cluster
    m = matched(cc, q, ov)
    pairs = {tuple(sorted(p)) for p in zip(m.Query_ID, m.Target_ID)}
    ids = cb.pma_id[cb.cluster.notna()].tolist()
    within = between = within_m = between_m = 0
    for a, b in combinations(ids, 2):
        same = clus[a] == clus[b]
        hit = (a, b) in pairs
        if same:
            within += 1; within_m += hit
        else:
            between += 1; between_m += hit
    # consistency of JASPAR hits with Table-10 clusters
    h = cls_hits.assign(cluster=cls_hits.Target_ID.map(clus))
    per_q = h.groupby("Query_ID").cluster.agg(lambda s: s.dropna().nunique())
    multi = per_q[h.groupby("Query_ID").size() > 1]
    return dict(
        n_clustered_pwms=len(ids), n_clusters=int(clus.nunique()),
        within_pairs=within, within_matched_frac=within_m / within if within else np.nan,
        between_pairs=between, between_matched_frac=between_m / between if between else np.nan,
        between_matched_n=between_m,
        jaspar_multi_hit_queries=int(len(multi)),
        jaspar_multi_hit_single_cluster_frac=float((multi <= 1).mean()) if len(multi) else np.nan,
    )


def main():
    RES.mkdir(parents=True, exist_ok=True)
    REPO_RES.mkdir(parents=True, exist_ok=True)
    ja, cb, jc, cc = load()

    grid = []
    for q in Q_GRID:
        for ov in OV_GRID:
            cls, hits = classify_jaspar(ja, cb, jc, q, ov)
            hum = cls[cls.is_human].coverage_class.value_counts()
            r = dict(q=q, ov=ov, **{f"human_{k}": int(hum.get(k, 0)) for k in
                                    ["same_TF", "other_TF_only", "not_represented"]})
            r.update(q3(cb, cc, hits, q, ov))
            grid.append(r)
    grid = pd.DataFrame(grid)
    grid.to_csv(REPO_RES / "sensitivity_grid.tsv", sep="\t", index=False)

    cls, hits = classify_jaspar(ja, cb, jc, Q_PRIMARY, OV_PRIMARY)
    cls.to_csv(RES / "jaspar_motif_coverage_classes.tsv", sep="\t", index=False)
    hits.to_csv(RES / "jaspar_vs_codebook_matched_primary.tsv", sep="\t", index=False)
    tf_cov, motif_cov, q2_tab, ic, mm = q1_q2(ja, cb, cls)
    q3r = q3(cb, cc, hits, Q_PRIMARY, OV_PRIMARY)

    mm.to_csv(REPO_RES / "q2_multi_motif_tfs.tsv", sep="\t")
    hum = cls[cls.is_human]
    hum.groupby(["length_bin", "coverage_class"], observed=True).size().unstack(fill_value=0).to_csv(
        REPO_RES / "q1_coverage_by_length.tsv", sep="\t")
    refined = dict(
        other_TF_only_paralog_cluster=int((hum.coverage_class.eq("other_TF_only") & hum.other_tf_paralog_cluster).sum()),
        other_TF_only_unrelated=int((hum.coverage_class.eq("other_TF_only") & ~hum.other_tf_paralog_cluster).sum()),
        not_represented_near_miss_q_lt_0_05=int(hum.near_miss.sum()),
        not_represented_no_match_q_ge_0_05=int((hum.coverage_class.eq("not_represented") & ~hum.near_miss).sum()),
    )
    for k in ("by_type", "by_dimer", "by_tf_has_cb"):
        q2_tab[k].to_csv(REPO_RES / f"q2_{k}.tsv", sep="\t")
    ic.to_csv(REPO_RES / "q2_ic_per_position_by_class.tsv", sep="\t")
    cls[cls.is_human & (cls.coverage_class == "not_represented") & ~cls.near_miss].sort_values(["tf_class", "name"]).to_csv(
        REPO_RES / "q2_human_not_represented_motifs.tsv", sep="\t", index=False)

    summary = dict(
        criterion=dict(q=Q_PRIMARY, overlap_frac_of_shorter=OV_PRIMARY),
        inputs=dict(codebook_pwms=len(cb), codebook_tfs=int(cb.hgnc_current.nunique()),
                    codebook_direct=int((cb.evidence_class == "direct").sum()),
                    codebook_inferred=int((cb.evidence_class == "inferred").sum()),
                    jaspar_nr=len(ja), jaspar_human=int(ja.is_human.sum()),
                    jaspar_heterodimer=int((ja.n_components > 1).sum())),
        q1_tf_coverage=tf_cov, q1_motif_coverage=motif_cov, q1_q2_refined_human=refined,
        q2_multi_motif_tfs=dict(n_tfs=len(mm), n_motifs=int(mm.n_jaspar.sum()),
                                tfs_with_unmatched_motif=int((mm.n_unmatched > 0).sum()),
                                tfs_all_motifs_same_best=int((mm.n_distinct_best <= 1).sum())),
        q3=q3r,
    )
    with open(REPO_RES / "summary.json", "w") as fh:
        json.dump(summary, fh, indent=2, default=lambda o: o.item() if hasattr(o, "item") else str(o))
    print(json.dumps(summary, indent=2, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
    print(grid.to_string())


if __name__ == "__main__":
    main()
