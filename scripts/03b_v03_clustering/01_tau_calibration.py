"""Step 3b §6.1: calibrate the coverage threshold tau on the frozen v0.2.1 TOMTOM.

Calibration set (frozen rule):
- query nodes from v0.2.1 (partition-aware), visited in seeded random order,
  accepted while their TF and their experiment each have < 20 accepted queries;
- for each query: every TOMTOM-kept partner (q < 0.05 row in either
  direction, same partition) + the 20 nearest same-partition nodes by s that
  have no TOMTOM row in either direction (hard negatives);
- label (amendment §13) = pair passes statistical_match_v0.1 in EITHER
  direction (eligible_directed.tsv.gz), the Step 3 §8.3 coverage relation;
  the original both-direction label (edges.tsv.gz) is kept as legacy curve.

Rule: tau = smallest candidate in {0.650, 0.675, ..., 0.950} such that
>= 95 % of calibration pairs with s >= tau are labelled positive and every
major source stratum (query source family, >= 500 pairs at that tau)
reaches >= 90 %. None -> tau_calibration_failed.

usage: 01_tau_calibration.py   (env PMA_MOTIF_RESULT, PMA_MOTIF_PROCESSED)
Outputs (result/step3b_v03/tau_calibration/): pairs.tsv.gz, curve.tsv,
strata_curve.tsv, tau.json
"""
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "02_motif_import"))
import pma_align as pa  # noqa: E402
import pma_motif as pm  # noqa: E402

SEED = 20261016
CAP = 20
N_HARD = 20
TAUS = np.round(np.arange(0.65, 0.95 + 1e-9, 0.025), 3)
R = Path(os.environ["PMA_MOTIF_RESULT"]) / "step3_motif_clustering"
MD = Path(os.environ["PMA_MOTIF_PROCESSED"]) / "v0.2.1_raw_layer" / "PMA_motif_metadata.tsv"
OUT = Path(os.environ["PMA_MOTIF_RESULT"]) / "step3b_v03" / "tau_calibration"


def wilson(k, n, z=1.96):
    if n == 0:
        return (np.nan, np.nan)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def node_table():
    nodes = pd.read_csv(R / "nodes" / "motif_nodes.tsv", sep="\t")
    nodes = nodes[~nodes.unclusterable.astype(bool)]
    md = pd.read_csv(MD, sep="\t", low_memory=False, usecols=["pma_id", "source_db", "motif_tf_assignment",
                                                               "experiment_ids"])
    x = nodes.merge(md, on="pma_id")
    first = lambda s: sorted(v for v in s.fillna("").astype(str) if v)[0] if (s.fillna("") != "").any() else ""  # noqa: E731
    g = x.groupby("node_id")
    t = pd.DataFrame({
        "partition": g.partition.first(),
        "source_family": g.source_db.agg(lambda s: s.value_counts().sort_index().idxmax()),
        "tf": g.motif_tf_assignment.agg(first).str.split(";").str[0],
        "experiment": g.experiment_ids.agg(first).str.split(";").str[0],
    })
    return t


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    motifs = pm.read_meme(R / "nodes" / "nodes.meme")
    ids = [m[0] for m in motifs]
    idx = {n: i for i, n in enumerate(ids)}
    Z, Zrc, start, lens = pa.pack([m[2] for m in motifs])
    t = node_table().reindex(ids)
    part = t.partition.to_numpy()
    gc = np.array([float((m[2][:, 1] + m[2][:, 2]).mean()) for m in motifs])
    t["len_tertile"] = pd.qcut(lens, 3, labels=False, duplicates="drop")
    t["gc_quintile"] = pd.qcut(gc, 5, labels=False, duplicates="drop")

    kept = []
    for f in sorted((R / "tomtom" / "kept").glob("chunk_*.tsv.gz")):
        k = pd.read_csv(f, sep="\t", usecols=["query", "target"], dtype=str)
        kept.append(k[k["query"] != k["target"]])
    kept = pd.concat(kept)
    qi = kept["query"].map(idx).to_numpy()
    ti = kept["target"].map(idx).to_numpy()
    ok = ~(np.isnan(qi.astype(float)) | np.isnan(ti.astype(float)))
    qi, ti = qi[ok].astype(np.int64), ti[ok].astype(np.int64)
    a, b = np.minimum(qi, ti), np.maximum(qi, ti)
    kept_pairs = set(zip(a.tolist(), b.tolist()))
    partners = {}
    for x, y in kept_pairs:
        if part[x] == part[y]:
            partners.setdefault(x, set()).add(y)
            partners.setdefault(y, set()).add(x)

    e = pd.read_csv(R / "edges.tsv.gz", sep="\t", usecols=["a", "b"], dtype=str)
    ea, eb = e.a.map(idx).to_numpy(), e.b.map(idx).to_numpy()
    both = set(zip(np.minimum(ea, eb).tolist(), np.maximum(ea, eb).tolist()))
    d = pd.read_csv(R / "eligible_directed.tsv.gz", sep="\t", usecols=["query", "target"], dtype=str)
    da, db = d["query"].map(idx).to_numpy(), d["target"].map(idx).to_numpy()
    pos = set(zip(np.minimum(da, db).tolist(), np.maximum(da, db).tolist()))

    rng = np.random.default_rng(SEED)
    order = rng.permutation(len(ids))
    ntf, nexp, queries = {}, {}, []
    for i in order:
        tf, ex = t.tf.iat[i] or f"_none_{i}", t.experiment.iat[i] or f"_none_{i}"
        if ntf.get(tf, 0) < CAP and nexp.get(ex, 0) < CAP:
            queries.append(i)
            ntf[tf] = ntf.get(tf, 0) + 1
            nexp[ex] = nexp.get(ex, 0) + 1

    rows = []
    for i in queries:
        same = np.flatnonzero((part == part[i]) & (np.arange(len(ids)) != i)).astype(np.int64)
        s_all = pa.s_one_vs_all(Z, Zrc, start, lens, np.int64(i), same)
        mate = np.isin(same, np.fromiter(partners.get(i, ()), dtype=np.int64))
        rows += [(i, int(j), float(s), "tomtom_kept") for j, s in zip(same[mate], s_all[mate])]
        cand, sc_ = same[~mate], s_all[~mate]
        top = np.argsort(-sc_, kind="stable")[:N_HARD]
        rows += [(i, int(cand[k]), float(sc_[k]), "hard_negative") for k in top]
    p = pd.DataFrame(rows, columns=["qi", "ti", "s", "kind"])
    p["positive"] = [(min(x, y), max(x, y)) in pos for x, y in zip(p.qi, p.ti)]
    p["positive_both"] = [(min(x, y), max(x, y)) in both for x, y in zip(p.qi, p.ti)]
    p["query"] = np.array(ids)[p.qi]
    p["target"] = np.array(ids)[p.ti]
    for c in ("source_family", "len_tertile", "gc_quintile", "tf", "experiment"):
        p[f"q_{c}"] = t[c].to_numpy()[p.qi]
    p.drop(columns=["qi", "ti"]).to_csv(OUT / "pairs.tsv.gz", sep="\t", index=False, float_format="%.6g")

    curve, sc, tau = [], [], None
    for tv in TAUS:
        sel = p[p.s >= tv]
        k, n = int(sel.positive.sum()), len(sel)
        lo, hi = wilson(k, n)
        ok_strata = True
        for fam, g in sel.groupby("q_source_family"):
            kk, nn = int(g.positive.sum()), len(g)
            l2, h2 = wilson(kk, nn)
            major = nn >= 500
            sc.append(dict(tau=tv, source_family=fam, n=nn, agree=kk / nn if nn else np.nan, ci_lo=l2, ci_hi=h2,
                           major=major))
            if major and kk / nn < 0.90:
                ok_strata = False
        agree = k / n if n else np.nan
        passed = bool(n and agree >= 0.95 and ok_strata)
        curve.append(dict(tau=tv, n=n, agree=agree, ci_lo=lo, ci_hi=hi, strata_ok=ok_strata, passes=passed,
                          agree_both_legacy=float(sel.positive_both.mean()) if n else np.nan))
        if passed and tau is None:
            tau = float(tv)
    pd.DataFrame(curve).to_csv(OUT / "curve.tsv", sep="\t", index=False, float_format="%.6g")
    pd.DataFrame(sc).to_csv(OUT / "strata_curve.tsv", sep="\t", index=False, float_format="%.6g")
    res = dict(tau=tau, status="ok" if tau is not None else "tau_calibration_failed", seed=SEED,
               n_queries=len(queries), n_pairs=len(p), n_tomtom_kept=int((p.kind == "tomtom_kept").sum()),
               n_hard_negative=int((p.kind == "hard_negative").sum()), n_positive=int(p.positive.sum()),
               label="statistical_match_v0.1 either direction (amendment §13)",
               tau_strict_sensitivity=0.95)
    (OUT / "tau.json").write_text(json.dumps(res, indent=2) + "\n")
    print(json.dumps(res, indent=2))
    print(pd.DataFrame(curve).to_string(index=False))


if __name__ == "__main__":
    main()
