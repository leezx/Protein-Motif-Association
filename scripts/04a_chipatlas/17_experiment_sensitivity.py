"""Step 4a §16 L1-d: experiment-level confounder sensitivity on the §14 embedding.

usage: 17_experiment_sensitivity.py <embedding.npz> <clusters.tsv> <study_provenance.tsv> <out_dir>
Variants: V0 raw (all 50 components); V1 without component 1; V2 neighbours from the same peak-count decile;
V3 neighbours from other studies; V4 = V2 + V3. For each factor: observed and expected same-label fraction,
fold enrichment and kappa = (obs - exp) / (1 - exp). Within-cell-type and within-protein views under V0 and V4.
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


def score(nn, lab, subset=None):
    lab = np.asarray(lab, dtype=object)
    rows = np.arange(len(lab)) if subset is None else subset
    ok = lab != "."
    obs = []
    for i in rows:
        if not ok[i]:
            continue
        nb = [j for j in nn[i] if j >= 0 and ok[j] and (subset is None or j in sset)] if subset is not None else [j for j in nn[i] if j >= 0 and ok[j]]
        if nb:
            obs.append(np.mean([lab[j] == lab[i] for j in nb]))
    pool = lab[rows][ok[rows]]
    cnt = collections.Counter(pool); n = len(pool)
    exp = sum((v / n) ** 2 for v in cnt.values()) if n else float("nan")
    o = float(np.mean(obs)) if obs else float("nan")
    return dict(n=len(obs), levels=len(cnt), observed=round(o, 4), expected=round(exp, 4),
                fold=round(o / exp, 2) if exp else None, kappa=round((o - exp) / (1 - exp), 4) if exp < 1 else None)


def main(npz, clusters, study_tsv, out):
    global sset
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    d = np.load(npz, allow_pickle=False)
    Z, ids = d["Z"], [str(x) for x in d["ids"]]
    meta = {r["experiment_id"]: r for r in csv.DictReader(open(clusters), delimiter="\t")}
    study = {r["experiment_id"]: r["study"] for r in csv.DictReader(open(study_tsv), delimiter="\t")}
    lab = {f: np.array([meta[e][f] for e in ids], dtype=object) for f in FACTORS}
    dec = np.array([meta[e]["peak_decile"] for e in ids], dtype=object)
    st = np.array([study.get(e, "single:" + e) for e in ids], dtype=object)
    E0 = normalize(Z); E1 = normalize(Z[:, 1:])
    variants = {"V0_raw": neighbours(E0), "V1_drop_comp1": neighbours(E1),
                "V2_same_peak_decile": neighbours(E0, groups=dec), "V3_other_study": neighbours(E0, forbid=st),
                "V4_same_decile_other_study": neighbours(E0, groups=dec, forbid=st)}
    rows = []
    for v, nn in variants.items():
        for f in FACTORS:
            rows.append(dict(variant=v, view="all", factor=f, **score(nn, lab[f])))
    # controlled views: recompute neighbours inside each subset
    top_ct = ["K-562", "Hep G2", "MCF-7"]
    top_p = ["CTCF", "ESR1", "AR", "FOXA1"]
    for key, vals, fs in (("cell_type", top_ct, ["protein", "protein_class"]), ("protein", top_p, ["cell_type", "tissue"])):
        for val in vals:
            sub = np.where(lab[key] == val)[0]
            if len(sub) < 30:
                continue
            for v, kw in (("V0_raw", {}), ("V4_same_decile_other_study", {"groups": dec[sub], "forbid": st[sub]})):
                nn = neighbours(E0[sub], **kw)
                for f in fs:
                    rows.append(dict(variant=v, view=f"{key}={val}", factor=f, **score(nn, lab[f][sub])))
    with open(out / "experiment_confounder_sensitivity.tsv", "w") as w:
        cols = list(rows[0]); w.write("\t".join(cols) + "\n")
        for r in rows:
            w.write("\t".join(str(r[c]) for c in cols) + "\n")
    summ = {f"{r['variant']}|{r['view']}|{r['factor']}": (r["fold"], r["kappa"]) for r in rows if r["view"] == "all"}
    summ["n_studies"] = int(len(set(st))); summ["experiments"] = len(ids)
    (out / "sensitivity_summary.json").write_text(json.dumps(summ, indent=1) + "\n")
    print(json.dumps(summ, indent=0))


if __name__ == "__main__":
    main(*sys.argv[1:5])
