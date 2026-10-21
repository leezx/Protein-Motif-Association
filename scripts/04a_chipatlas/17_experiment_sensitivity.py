"""Step 4a §16 L1-d: experiment-level confounder sensitivity on the §14 embedding.

usage: 17_experiment_sensitivity.py <embedding.npz> <clusters.tsv> <study_provenance.tsv> <out_dir>
Variants: V0 raw (all 50 components); V1 without component 1; V2 neighbours from the same peak-count decile;
V3 neighbours from other studies; V4 = V2 + V3. For each factor: observed same-label fraction, global and
conditional expectation (§17 B), kappa on the conditional expectation, permutation p, and anchors with 10 eligible
neighbours. Within-cell-type and within-protein views under V0, V2, V3 and V4.
"""
import collections
import csv
import json
import sys
from pathlib import Path

import numpy as np
from sklearn.preprocessing import normalize

K = 10
FACTORS = ["protein", "protein_class", "cell_type", "tissue"]


def neighbours(E, groups=None, forbid=None, k=K, chunk=2000):
    """k nearest (cosine) neighbours per row; restricted to rows with the same `groups` value (if given) and to
    rows whose `forbid` value differs (if given)."""
    n = len(E); out = np.full((n, k), -1, dtype=np.int64)
    for a in range(0, n, chunk):
        S = E[a:a + chunk] @ E.T
        rows = np.arange(a, min(a + chunk, n))
        S[np.arange(len(rows)), rows] = -np.inf
        if groups is not None:
            S[groups[rows][:, None] != groups[None, :]] = -np.inf
        if forbid is not None:
            S[forbid[rows][:, None] == forbid[None, :]] = -np.inf
        top = np.argpartition(-S, k, axis=1)[:, :k]
        ok = np.take_along_axis(S, top, axis=1) > -np.inf
        out[rows] = np.where(ok, top, -1)
    return out


def score(nn, lab, grp=None, forb=None, strata=None, n_perm=200, seed=20261021):
    """Observed same-label fraction among neighbours and two expectations (§17 B):
    - expected_global: sum of squared label frequencies (v1.1);
    - expected_conditional: per anchor, the same-label fraction of its eligible-neighbour set (same `grp`, other
      `forb`, not itself), averaged over anchors.
    kappa uses the conditional expectation; kappa_global is kept for comparison with v1.1. p_perm: labels permuted
    within `strata` (peak deciles) with the neighbour graph fixed."""
    import pandas as pd
    lab = np.asarray(lab, dtype=object)
    ok = lab != "."
    codes = pd.factorize(lab)[0]
    valid = (nn >= 0) & ok[np.clip(nn, 0, None)]
    has = ok & valid.any(axis=1)

    def obs_of(c):
        same = (c[np.clip(nn, 0, None)] == c[:, None]) & valid
        return same.sum(axis=1)[has] / valid.sum(axis=1)[has]
    o = float(np.mean(obs_of(codes))) if has.any() else float("nan")
    df = pd.DataFrame({"lab": codes, "ok": ok, "g": grp if grp is not None else 0, "f": forb if forb is not None else 0})
    d = df[df.ok]
    n_g = d.groupby("g").size(); n_gl = d.groupby(["g", "lab"]).size()
    tot = df["g"].map(n_g).fillna(0).to_numpy() - 1
    same = pd.Series(list(zip(df.g, df.lab))).map(n_gl).fillna(0).to_numpy() - 1
    if forb is not None:
        n_gf = d.groupby(["g", "f"]).size(); n_gfl = d.groupby(["g", "f", "lab"]).size()
        tot = tot - (pd.Series(list(zip(df.g, df.f))).map(n_gf).fillna(0).to_numpy() - 1)
        same = same - (pd.Series(list(zip(df.g, df.f, df.lab))).map(n_gfl).fillna(0).to_numpy() - 1)
    sel = has & (tot > 0)
    exp_c = float(np.mean(same[sel] / tot[sel])) if sel.any() else float("nan")
    cnt = collections.Counter(lab[ok]); n = int(ok.sum())
    exp_g = sum((v / n) ** 2 for v in cnt.values()) if n else float("nan")
    rng = np.random.default_rng(seed)
    st = strata if strata is not None else np.zeros(len(lab), dtype=int)
    ge = 0
    okidx = np.where(ok)[0]
    for _ in range(n_perm):
        c = codes.copy()
        for s_ in np.unique(st[okidx]):
            m = okidx[st[okidx] == s_]; c[m] = c[rng.permutation(m)]
        ge += np.mean(obs_of(c)) >= o
    return dict(n=int(has.sum()), n_full_10_neighbours=int((ok & (valid.sum(axis=1) == K)).sum()), levels=len(cnt),
                observed=round(o, 4), expected_global=round(exp_g, 4), expected_conditional=round(exp_c, 4),
                fold=round(o / exp_c, 2) if exp_c else None,
                kappa=round((o - exp_c) / (1 - exp_c), 4) if exp_c < 1 else None,
                kappa_global=round((o - exp_g) / (1 - exp_g), 4) if exp_g < 1 else None,
                p_perm=round((1 + ge) / (1 + n_perm), 4))


def main(npz, clusters, study_tsv, out):
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    d = np.load(npz, allow_pickle=False)
    Z, ids = d["Z"], [str(x) for x in d["ids"]]
    meta = {r["experiment_id"]: r for r in csv.DictReader(open(clusters), delimiter="\t")}
    study = {r["experiment_id"]: r["study"] for r in csv.DictReader(open(study_tsv), delimiter="\t")}
    lab = {f: np.array([meta[e][f] for e in ids], dtype=object) for f in FACTORS}
    dec = np.array([meta[e]["peak_decile"] for e in ids], dtype=object)
    st = np.array([study.get(e, "single:" + e) for e in ids], dtype=object)
    E0 = normalize(Z); E1 = normalize(Z[:, 1:])
    spec = {"V0_raw": (E0, None, None), "V1_drop_comp1": (E1, None, None), "V2_same_peak_decile": (E0, dec, None),
            "V3_other_study": (E0, None, st), "V4_same_decile_other_study": (E0, dec, st)}
    rows = []
    for v, (E, g, fb) in spec.items():
        nn = neighbours(E, groups=g, forbid=fb)
        for f in FACTORS:
            rows.append(dict(variant=v, view="all", factor=f, **score(nn, lab[f], g, fb, dec)))
    # controlled views: recompute neighbours inside each subset
    top_ct = ["K-562", "Hep G2", "MCF-7"]
    top_p = ["CTCF", "ESR1", "AR", "FOXA1"]
    for key, vals, fs in (("cell_type", top_ct, ["protein", "protein_class"]), ("protein", top_p, ["cell_type", "tissue"])):
        for val in vals:
            sub = np.where(lab[key] == val)[0]
            if len(sub) < 30:
                continue
            for v, g, fb in (("V0_raw", None, None), ("V2_same_peak_decile", dec[sub], None),
                             ("V3_other_study", None, st[sub]), ("V4_same_decile_other_study", dec[sub], st[sub])):
                nn = neighbours(E0[sub], groups=g, forbid=fb)
                for f in fs:
                    rows.append(dict(variant=v, view=f"{key}={val}", factor=f, **score(nn, lab[f][sub], g, fb, dec[sub])))
    with open(out / "experiment_confounder_sensitivity.tsv", "w") as w:
        cols = list(rows[0]); w.write("\t".join(cols) + "\n")
        for r in rows:
            w.write("\t".join(str(r[c]) for c in cols) + "\n")
    summ = {f"{r['variant']}|{r['view']}|{r['factor']}": dict(kappa=r["kappa"], kappa_global=r["kappa_global"],
                                                               p_perm=r["p_perm"], n=r["n"], n_full=r["n_full_10_neighbours"])
            for r in rows}
    summ["n_studies"] = int(len(set(st))); summ["experiments"] = len(ids)
    (out / "sensitivity_summary.json").write_text(json.dumps(summ, indent=1) + "\n")
    print(json.dumps(summ, indent=0))


if __name__ == "__main__":
    main(*sys.argv[1:5])
