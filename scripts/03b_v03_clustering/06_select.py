"""Step 3b §6.3 selection (selection_contract_v0.3).

usage: 06_select.py candidates   -> gates/deterministic.tsv, gates/candidates.tsv,
                                    pca/strata_<part>.tsv (G6 strata)
       06_select.py select       -> gates/selection.json, gates/stability.tsv

candidates: per partition, G7 = AMI vs Codebook T10 and vs HOCOMOCO each
>= (grid best - SE of the best config); deterministic pass = G1 & G2 & G3 &
G4 & G7. Survivors get stability runs (04_seurat_grid.R stability).
G6 strata = source family x evidence type x GC quintile of the node.

select: G5 = median pairwise ARI over the 10 seeds >= 0.85; G6 = median ARI of
each 80 % subsample vs the full run on its nodes >= 0.75. Among configs
passing all gates: fewest final representatives (K_final); configs within 2 %
of the minimum -> higher G2, then higher G6, then smaller resolution.
GC rule (Step 3 §9.1): chosen within A and within B separately; B replaces
A only if, over 200 bootstrap resamples of nodes stratified by source x GC
quintile, the median gains are: mean external AMI >= +0.03, node coverage
>= +5 points, no GC class (AT-rich GC < 0.35, GC-rich GC > 0.60, CpG
max_i p(C_i) p(G_i+1) >= 0.5) loses > 5 points, and B splits at most one more
P_high pair than A. Otherwise A. None passing -> "no feasible configuration".
"""
import json
import os
import re
import sys
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_mutual_info_score, adjusted_rand_score

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "02_motif_import"))
import pma_motif as pm  # noqa: E402

SEED = 20261016
RESULT = Path(os.environ["PMA_MOTIF_RESULT"])
R = RESULT / "step3b_v03"
G = R / "gates"
PROC = Path(os.environ["PMA_MOTIF_PROCESSED"]) / "v0.3_raw_layer"
EVID = Path(os.environ["PMA_MOTIF_PROCESSED"]) / "annotations" / "evidence_v2" / "PMA_motif_evidence.tsv"


def res_of(c):
    return float(re.search(r"_r([0-9.]+)$", c).group(1))


def node_props(part):
    ids = pd.read_csv(R / "pca" / f"nodes_{part}.tsv", sep="\t").node_id.to_numpy()
    mats = {n: m for n, p, m in pm.read_meme(R / "nodes" / "nodes.meme") if p == part}
    gc = np.array([float((mats[n][:, 1] + mats[n][:, 2]).mean()) for n in ids])
    cpg = np.array([float((mats[n][:-1, 1] * mats[n][1:, 2]).max()) if len(mats[n]) > 1 else 0.0 for n in ids])
    nodes = pd.read_csv(R / "nodes" / "motif_nodes.tsv", sep="\t")
    ev = pd.read_csv(EVID, sep="\t", usecols=["pma_id", "source_db", "evidence_type"])
    x = nodes.merge(ev, on="pma_id")
    x["st"] = x.source_db + "|" + x.evidence_type
    maj = x.groupby("node_id").st.agg(lambda s: s.value_counts().sort_index().idxmax()).reindex(ids)
    fam = maj.str.split("|").str[0].to_numpy()
    gq = pd.qcut(gc, 5, labels=False, duplicates="drop")
    return ids, gc, cpg, maj.to_numpy(), fam, gq


def candidates():
    files = [f for f in sorted(G.glob("gates_*.tsv")) if "_tau" not in f.name]  # strict-tau files excluded
    t = pd.concat([pd.read_csv(f, sep="\t") for f in files], ignore_index=True)
    for part, g in t.groupby("part"):
        for ref in ("codebook", "hocomoco"):
            a, se = g[f"AMI_{ref}"], g[f"AMI_{ref}_se"]
            if a.notna().any():
                b = a.idxmax()
                t.loc[g.index, f"G7_{ref}"] = a >= a[b] - se[b]
            else:
                t.loc[g.index, f"G7_{ref}"] = True
    t["G7_pass"] = t.G7_codebook.astype(bool) & t.G7_hocomoco.astype(bool)
    t["deterministic_pass"] = t.G1_pass & t.G2_pass & t.G3_pass & t.G4_pass & t.G7_pass
    t.to_csv(G / "deterministic.tsv", sep="\t", index=False, float_format="%.6g")
    c = t[t.deterministic_pass][["part", "rep", "dims", "config", "K_final"]]
    c = c.assign(k=c.config.str.extract(r"_k(\d+)_")[0].astype(int), res=c.config.map(res_of))
    c.to_csv(G / "candidates.tsv", sep="\t", index=False)
    for part in t.part.unique():
        ids, gc, cpg, maj, fam, gq = node_props(part)
        pd.DataFrame({"node_id": ids, "stratum": [f"{m}|gc{q}" for m, q in zip(maj, gq)]}).to_csv(
            R / "grid" / f"strata_{part}.tsv", sep="\t", index=False)
    print(t.groupby(["part", "rep"]).deterministic_pass.agg(["sum", "size"]).to_string())
    print(f"{len(c)} candidates for stability")


def stability(part, rep, dims, k, res):
    f = R / "grid" / f"stability_{part}_{rep}_d{dims}_k{k}_r{res:g}.tsv.gz"
    if not f.exists():
        f = R / "grid" / f"stability_{part}_{rep}_d{dims}_k{k}_r{res}.tsv.gz"
    s = pd.read_csv(f, sep="\t", dtype=str)
    seeds = [c for c in s.columns if c.startswith("seed")]
    g5 = float(np.median([adjusted_rand_score(s[a], s[b]) for a, b in combinations(seeds, 2)]))
    full = s[seeds[0]]
    subs = [c for c in s.columns if c.startswith("sub")]
    g6 = float(np.median([adjusted_rand_score(full[s[c].notna()], s[c].dropna()) for c in subs]))
    return g5, g6


def gc_rule(part, a, b, props):
    """B replaces A only if every median bootstrap gain meets §9.1."""
    ids, gc, cpg, maj, fam, gq = props
    fa = pd.read_csv(G / f"final_{part}_A_d{a.dims}.tsv.gz", sep="\t", dtype=str).set_index("node_id").reindex(ids)
    fb = pd.read_csv(G / f"final_{part}_B_d{b.dims}.tsv.gz", sep="\t", dtype=str).set_index("node_id").reindex(ids)
    ca, cb = fa[f"{a.config}|covered_presplit"].astype(int).to_numpy(), fb[f"{b.config}|covered_presplit"].astype(int).to_numpy()
    la, lb = fa[f"{a.config}|cluster"].to_numpy(), fb[f"{b.config}|cluster"].to_numpy()
    nodes = pd.read_csv(R / "nodes" / "motif_nodes.tsv", sep="\t")
    md = pd.read_csv(PROC / "PMA_motif_metadata.tsv", sep="\t", low_memory=False, usecols=["pma_id", "codebook_cluster"])
    idx = {n: i for i, n in enumerate(ids)}
    cbm = nodes.merge(md, on="pma_id").dropna(subset=["codebook_cluster"])
    cbm = cbm[cbm.node_id.isin(idx)]
    cb_node, cb_ref = cbm.node_id.map(idx).to_numpy(), cbm.codebook_cluster.astype(str).to_numpy()
    bp = pd.read_csv(RESULT / "step2_motif_import" / "benchmark" / "benchmark_pairs.tsv", sep="\t", dtype=str)
    ph = bp[bp["set"] == "P_high"]
    node_of = dict(zip(nodes.pma_id, nodes.node_id))
    ph = ph.assign(x=ph.m1.map(node_of).map(idx), y=ph.m2.map(node_of).map(idx)).dropna(subset=["x", "y"])
    px, py = ph.x.astype(int).to_numpy(), ph.y.astype(int).to_numpy()
    split_a, split_b = int((la[px] != la[py]).sum()), int((lb[px] != lb[py]).sum())
    classes = {"AT": gc < 0.35, "GC": gc > 0.60, "CpG": cpg >= 0.5}
    strata = pd.Series([f"{f}|{q}" for f, q in zip(fam, gq)])
    rng = np.random.default_rng(SEED)
    gains = {"ami": [], "cov": [], **{k: [] for k in classes}}
    groups = [np.flatnonzero(strata.to_numpy() == s) for s in strata.unique()]
    pos_in_cb = pd.Series(np.arange(len(cb_node))).groupby(cb_node).apply(list).to_dict()
    for _ in range(200):
        bs = np.concatenate([g[rng.integers(0, len(g), len(g))] for g in groups])
        gains["cov"].append(cb[bs].mean() - ca[bs].mean())
        for k, m in classes.items():
            mm = bs[m[bs]]
            gains[k].append((cb[mm].mean() - ca[mm].mean()) if len(mm) else 0.0)
        sel = np.concatenate([pos_in_cb.get(i, []) for i in bs]).astype(int)
        if len(sel):
            gains["ami"].append(adjusted_mutual_info_score(cb_ref[sel], lb[cb_node[sel]])
                                - adjusted_mutual_info_score(cb_ref[sel], la[cb_node[sel]]))
    med = {k: float(np.median(v)) for k, v in gains.items() if v}
    ok = (med.get("ami", -1) >= 0.03 and med["cov"] >= 0.05 and all(med[k] >= -0.05 for k in classes)
          and split_b - split_a <= 1)
    return ok, dict(median_gain=med, p_high_split_A=split_a, p_high_split_B=split_b)


def select():
    det = pd.read_csv(G / "deterministic.tsv", sep="\t")
    cand = pd.read_csv(G / "candidates.tsv", sep="\t")
    rows = []
    for r in cand.itertuples():
        g5, g6 = stability(r.part, r.rep, r.dims, r.k, r.res)
        rows.append(dict(part=r.part, rep=r.rep, dims=r.dims, config=r.config, G5=g5, G6=g6,
                         G5_pass=g5 >= 0.85, G6_pass=g6 >= 0.75))
    st = pd.DataFrame(rows)
    st.to_csv(G / "stability.tsv", sep="\t", index=False, float_format="%.6g")
    m = det.merge(st, on=["part", "rep", "dims", "config"])
    m = m[m.G5_pass & m.G6_pass].assign(res=lambda d: d.config.map(res_of))
    out = {}
    for part in det.part.unique():
        chosen = {}
        for rep in ("A", "B"):
            g = m[(m.part == part) & (m.rep == rep)]
            if g.empty:
                continue
            g = g[g.K_final <= g.K_final.min() * 1.02]
            chosen[rep] = g.sort_values(["G2", "G6", "res"], ascending=[False, False, True]).iloc[0]
        if not chosen:
            out[part] = dict(status="no feasible configuration")
            continue
        pick, gc = chosen.get("A", chosen.get("B")), None
        if "A" in chosen and "B" in chosen:
            ok, gc = gc_rule(part, chosen["A"], chosen["B"], node_props(part))
            pick = chosen["B"] if ok else chosen["A"]
        elif "A" not in chosen:
            gc = dict(note="no feasible A; B chosen as the only feasible representation")
        out[part] = dict(status="selected", config=pick.config, rep=pick.rep, dims=int(pick.dims),
                         K_louvain=int(pick.K_louvain), K_final=int(pick.K_final), G1=pick.G1, G2=pick.G2,
                         G3=pick.G3, G4=pick.G4, G5=pick.G5, G6=pick.G6, AMI_codebook=pick.AMI_codebook,
                         AMI_hocomoco=pick.AMI_hocomoco, gc_rule=gc,
                         feasible_A=int(((m.part == part) & (m.rep == "A")).sum()),
                         feasible_B=int(((m.part == part) & (m.rep == "B")).sum()))
    (G / "selection.json").write_text(json.dumps(out, indent=2, default=float) + "\n")
    print(json.dumps(out, indent=2, default=float))


if __name__ == "__main__":
    {"candidates": candidates, "select": select}[sys.argv[1]]()
