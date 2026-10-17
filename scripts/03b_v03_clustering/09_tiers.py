"""Step 3b §14: three-tier reference (LOW ~500, MEDIUM ~1000, HIGH ~2000).

usage: 09_tiers.py choose     -> tiers/tier_choice.json, grid/strata_<part>.tsv
       09_tiers.py build      -> tiers/final_tier_<tier>.tsv.gz, tiers/tier_qc.tsv, tiers/tier_mapping.tsv
       09_tiers.py stability  -> adds seed / subsample ARI to tiers/tier_qc.tsv

choose: K_total(res) = K_monomer + K_composite from tiers_scan_<part>.tsv.gz (one
graph: A, PCs 1:30, k 20); per target the tested res with K_total closest
(ties -> smaller res). No tolerance (PI: approximate counts).
build, per tier and partition:
  hub = experiment-balanced affinity medoid:
        argmax_i sum_{j!=i} w_j corr(a_i, a_j) / sum_{j!=i} w_j,
        w_j = 1 / (#cluster nodes sharing node j's resolved experiment), 1 if none;
        ties within 0.01: evidence v2 tier <= 2, more independent experiments,
        length closest to the cluster median, node ID.
  QC (reported, never tunes res): coverage of members by their hub at tau and
  at the strict 0.95; hub redundancy (s >= 0.85 across clusters); N-challenge
  co-clustering; AMI vs Codebook T10 / HOCOMOCO (bootstrap SE); flags.
  Cross-tier: HIGH -> MEDIUM -> LOW max-overlap mapping with parent purity.
"""
import importlib
import json
import os
import sys
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_rand_score

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "02_motif_import"))
import pma_align as pa  # noqa: E402
import pma_motif as pm  # noqa: E402

gt = importlib.import_module("05_gates")
sel = importlib.import_module("06_select")

TARGETS = {"LOW": 500, "MEDIUM": 1000, "HIGH": 2000}
TIE, STRICT, S_RED = 0.01, 0.95, 0.85
R = gt.R
T = R / "tiers"
PARTS = ("composite", "monomer")
BLOCK = 8192


def res_of(c):
    return float(c.rsplit("_r", 1)[1])


def scan(part):
    return pd.read_csv(T / f"tiers_scan_{part}.tsv.gz", sep="\t", dtype=str).set_index("node_id")


def choose():
    k = {p: scan(p).nunique() for p in PARTS}
    tab = pd.DataFrame({"res": [res_of(c) for c in k["monomer"].index], "K_monomer": k["monomer"].to_numpy(),
                        "K_composite": k["composite"].reindex(k["monomer"].index).to_numpy()})
    tab["K_total"] = tab.K_monomer + tab.K_composite
    out = {"scan": tab.to_dict("records"), "tiers": {}}
    for name, tgt in TARGETS.items():
        d = (tab.K_total - tgt).abs()
        best = tab.loc[d[d == d.min()].index].sort_values("res").iloc[0]
        out["tiers"][name] = dict(target=tgt, res=float(best.res), K_total=int(best.K_total),
                                  K_monomer=int(best.K_monomer), K_composite=int(best.K_composite),
                                  deviation=round(float(best.K_total / tgt - 1), 4))
    (T / "tier_choice.json").write_text(json.dumps(out, indent=2) + "\n")
    for part in PARTS:  # G6 strata (same definition as 06_select)
        ids, gc, cpg, maj, fam, gq = sel.node_props(part)
        pd.DataFrame({"node_id": ids, "stratum": [f"{m}|gc{q}" for m, q in zip(maj, gq)]}).to_csv(
            R / "grid" / f"strata_{part}.tsv", sep="\t", index=False)
    print(tab.to_string(index=False))
    print(json.dumps(out["tiers"], indent=2))


def node_experiment(nodes, ids):
    md = pd.read_csv(gt.PROC / "PMA_motif_metadata.tsv", sep="\t", low_memory=False,
                     usecols=["pma_id", "independent_experiment_id", "independence_status"])
    x = nodes.merge(md, on="pma_id")
    ok = x.independent_experiment_id.notna() & ~x.independence_status.isin(["unresolved", "independence_unresolved"])
    x = x[ok & (x.independent_experiment_id.astype(str) != "")]
    return x.groupby("node_id").independent_experiment_id.agg(lambda s: sorted(s.astype(str))[0]).reindex(ids)


def hubs(F, lab, w, length, meta):
    """Experiment-balanced affinity medoid per cluster (rows of F = nodes)."""
    nc = lab.max() + 1
    M = np.zeros((nc, F.shape[1]))
    W = np.bincount(lab, weights=w, minlength=nc)
    from scipy import sparse
    for a in range(0, F.shape[0], BLOCK):
        X = np.asarray(F[a:a + BLOCK], dtype=np.float64)
        l = lab[a:a + BLOCK]
        M += sparse.csr_matrix((w[a:a + BLOCK], (l, np.arange(len(l)))), shape=(nc, len(l))) @ X
    score = np.empty(F.shape[0])
    for a in range(0, F.shape[0], BLOCK):
        X = np.asarray(F[a:a + BLOCK], dtype=np.float64)
        l = lab[a:a + BLOCK]
        ww = w[a:a + BLOCK]
        num = (X * M[l]).sum(1) - ww * (X * X).sum(1)
        den = W[l] - ww
        score[a:a + BLOCK] = np.where(den > 0, num / np.where(den > 0, den, 1), 1.0)
    order = np.argsort(lab, kind="stable")
    bounds = np.r_[0, np.cumsum(np.bincount(lab, minlength=nc))]
    rep = np.empty(nc, dtype=np.int64)
    for c in range(nc):
        mem = order[bounds[c]:bounds[c + 1]]
        cand = mem[score[mem] >= score[mem].max() - TIE]
        med = np.median(length[mem])
        key = pd.DataFrame({"h": ~meta.high.to_numpy()[cand], "e": -meta.n_exp.to_numpy()[cand],
                            "l": np.abs(length[cand] - med), "n": meta.index.to_numpy()[cand]})
        rep[c] = cand[np.lexsort((key.n, key.l, key.e, key.h))[0]]
    return rep, score


def build():
    choice = json.loads((T / "tier_choice.json").read_text())["tiers"]
    tau = float(json.loads((R / "tau_calibration" / "tau.json").read_text())["tau"])
    nodes_all = pd.read_csv(R / "nodes" / "motif_nodes.tsv", sep="\t")
    qc, finals = [], {}
    for part in PARTS:
        ids = pd.read_csv(R / "pca" / f"nodes_{part}.tsv", sep="\t").node_id.to_numpy()
        idx = {n: i for i, n in enumerate(ids)}
        F = np.load(R / "pca" / f"features_{part}.f16", mmap_mode="r")
        mats = {n: m for n, p, m in pm.read_meme(R / "nodes" / "nodes.meme") if p == part}
        Z, Zrc, st, ln = pa.pack([mats[n] for n in ids])
        meta, nodes, mx = gt.node_meta(ids)
        exp = node_experiment(nodes, ids).to_numpy()
        length = ln.astype(float)
        sc = scan(part).reindex(ids)
        node_of = dict(zip(nodes.pma_id, nodes.node_id))
        bp = pd.read_csv(gt.RESULT / "step2_motif_import" / "benchmark" / "benchmark_pairs.tsv", sep="\t", dtype=str)
        nch = bp[bp["set"] == "N_challenge"]
        nch = nch.assign(a=nch.m1.map(node_of).map(idx), b=nch.m2.map(node_of).map(idx)).dropna(subset=["a", "b"])
        na, nb = nch.a.astype(int).to_numpy(), nch.b.astype(int).to_numpy()
        for name, t in choice.items():
            col = f"A_d30_k20_r{t['res']:g}"
            lab = pd.factorize(sc[col])[0]
            key = pd.Series(exp).fillna("").astype(str)
            grp = pd.Series(lab).astype(str) + "|" + key
            cnt = grp.map(grp.value_counts())
            w = np.where(key == "", 1.0, 1.0 / cnt.to_numpy())
            rep, score = hubs(F, lab, w, length, meta)
            hub = rep[lab]
            s = pa.s_pairs(Z, Zrc, st, ln, hub.astype(np.int64), np.arange(len(ids), dtype=np.int64))
            ccov = np.bincount(lab, weights=s >= tau) / np.bincount(lab)
            a, b = np.triu_indices(len(rep), 1)
            rs = pa.s_pairs(Z, Zrc, st, ln, rep[a], rep[b]) if len(rep) > 1 else np.array([])
            red = np.zeros(len(rep), bool)
            red[a[rs >= S_RED]] = red[b[rs >= S_RED]] = True
            finals.setdefault(name, []).append(pd.DataFrame({
                "node_id": ids, "partition": part, "cluster": [f"{part[0].upper()}{x}" for x in lab],
                "rep_node": ids[hub], "hub_score": score, "s_to_hub": s, "covered": (s >= tau).astype(int),
                "covered_strict": (s >= STRICT).astype(int)}))
            qc.append(dict(tier=name, part=part, res=t["res"], K=int(lab.max() + 1), n_nodes=len(ids),
                           coverage_tau=float((s >= tau).mean()), coverage_strict=float((s >= STRICT).mean()),
                           clusters_cov90=float((ccov >= 0.9).mean()), hub_redundancy=float(red.mean()),
                           n_challenge=float((lab[na] == lab[nb]).mean()) if len(na) else np.nan,
                           n_challenge_pairs=int(len(na))))
            print(qc[-1], flush=True)
    q = pd.DataFrame(qc)
    tot = []
    for name, parts in finals.items():
        f = pd.concat(parts, ignore_index=True)
        f.to_csv(T / f"final_tier_{name}.tsv.gz", sep="\t", index=False, float_format="%.6g")
        finals[name] = f
        g = q[q.tier == name]
        cov = float((g.coverage_tau * g.n_nodes).sum() / g.n_nodes.sum())
        nchal = float(np.nansum(g.n_challenge * g.n_challenge_pairs) / max(g.n_challenge_pairs.sum(), 1))
        red = float((g.hub_redundancy * g.K).sum() / g.K.sum())
        flags = [x for x, bad in (("low_fidelity", cov < 0.90), ("possible_overmerging", nchal > 0.05),
                                  ("residual_redundancy", red > 0.15)) if bad]
        tot.append(dict(tier=name, part="ALL", res=g.res.iloc[0], K=int(g.K.sum()), n_nodes=int(g.n_nodes.sum()),
                        coverage_tau=cov, coverage_strict=float((g.coverage_strict * g.n_nodes).sum() / g.n_nodes.sum()),
                        clusters_cov90=float((g.clusters_cov90 * g.K).sum() / g.K.sum()), hub_redundancy=red,
                        n_challenge=nchal, n_challenge_pairs=int(g.n_challenge_pairs.sum()), flags=";".join(flags)))
    q = pd.concat([q, pd.DataFrame(tot)], ignore_index=True)
    # external AMI on the whole tier (motif level -> node -> cluster)
    rng = np.random.default_rng(gt.SEED)
    md = pd.read_csv(gt.PROC / "PMA_motif_metadata.tsv", sep="\t", low_memory=False, usecols=["pma_id", "codebook_cluster"])
    hc = pd.read_csv(gt.RAW / "hocomoco_v14" / "2026-10-14" / "H14CORE-CLUSTERED_cluster_list.tsv", sep="\t")
    h14 = {f"HO14_{m.strip()}": r for r, ms in zip(hc.Representative_Motif, hc.Clustered_Motifs) for m in ms.split(";")}
    refs = {"codebook": md.dropna(subset=["codebook_cluster"]).set_index("pma_id").codebook_cluster.astype(str),
            "hocomoco": pd.Series(h14)}
    node_of = dict(zip(nodes_all.pma_id, nodes_all.node_id))
    for name, f in finals.items():
        cl = dict(zip(f.node_id, f.cluster))
        for rname, ref in refs.items():
            lab = ref.index.map(node_of).map(cl)
            ok = pd.notna(lab)
            a, se = gt.ami_boot(ref.to_numpy()[ok], np.asarray(lab[ok]).astype(str), rng)
            q.loc[(q.tier == name) & (q.part == "ALL"), [f"AMI_{rname}", f"AMI_{rname}_se"]] = [a, se]
    q.to_csv(T / "tier_qc.tsv", sep="\t", index=False, float_format="%.6g")
    # cross-tier mapping (node level)
    rows = []
    for child, parent in (("HIGH", "MEDIUM"), ("MEDIUM", "LOW")):
        m = finals[child][["node_id", "cluster"]].merge(finals[parent][["node_id", "cluster"]], on="node_id",
                                                         suffixes=("_child", "_parent"))
        ct = m.groupby(["cluster_child", "cluster_parent"]).size().rename("n").reset_index()
        best = ct.sort_values(["cluster_child", "n"], ascending=[True, False]).drop_duplicates("cluster_child")
        size = m.groupby("cluster_child").size()
        best["purity"] = best.n.to_numpy() / size.reindex(best.cluster_child).to_numpy()
        best["child_tier"], best["parent_tier"] = child, parent
        rows.append(best)
    mp = pd.concat(rows, ignore_index=True)
    mp.to_csv(T / "tier_mapping.tsv", sep="\t", index=False, float_format="%.4g")
    print(q[q.part == "ALL"].to_string(index=False))
    print(mp.groupby(["child_tier", "parent_tier"]).purity.describe().round(3).to_string())


def stability():
    choice = json.loads((T / "tier_choice.json").read_text())["tiers"]
    q = pd.read_csv(T / "tier_qc.tsv", sep="\t")
    for name, t in choice.items():
        for part in PARTS:
            f = R / "grid" / f"stability_{part}_A_d30_k20_r{t['res']:g}.tsv.gz"
            if not f.exists():
                continue
            s = pd.read_csv(f, sep="\t", dtype=str)
            seeds = [c for c in s.columns if c.startswith("seed")]
            g5 = float(np.median([adjusted_rand_score(s[a], s[b]) for a, b in combinations(seeds, 2)]))
            subs = [c for c in s.columns if c.startswith("sub")]
            g6 = float(np.median([adjusted_rand_score(s[seeds[0]][s[c].notna()], s[c].dropna()) for c in subs]))
            q.loc[(q.tier == name) & (q.part == part), ["seed_ARI", "subsample_ARI"]] = [g5, g6]
    q.to_csv(T / "tier_qc.tsv", sep="\t", index=False, float_format="%.6g")
    print(q.to_string(index=False))


if __name__ == "__main__":
    {"choose": choose, "build": build, "stability": stability}[sys.argv[1]]()
