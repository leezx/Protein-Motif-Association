"""Step 3b §6.2-6.3: representatives, single split and deterministic gates per grid config.

usage: 05_gates.py <part> <rep A|B> <dims>
Reads grid/grid_<part>_<rep>_d<dims>.tsv.gz (24 configs: k x resolution) and
writes gates/gates_<part>_<rep>_d<dims>.tsv (one row per config) and
gates/final_<part>_<rep>_d<dims>.tsv.gz (final cluster + representative per node).

Per config, frozen rules:
1. Representative per Louvain community: members whose mean affinity-profile
   correlation to the community (x_i . mean(x)) is within 0.05 of the best;
   among them high-evidence nodes first (a member of evidence v2 tier 1 in vitro
   or tier 2 curated core), then more independent experiments,
   then higher total IC, then node ID.
2. Coverage = share of members with s(rep, member) >= tau (pre-split).
   G1: >= 80 % of communities with coverage >= 90 %.
   G2: node-weighted pre-split coverage >= 90 % and >= 85 % in every source
       family with >= 1,000 nodes.
3. Communities with coverage < 90 % are split once: complete linkage on
   1 - s (full pairwise matrix), cut at 1 - tau; each subcluster gets a
   representative by rule 1; coverage 100 % is asserted. Communities larger
   than NMAX are reported as a compute limitation (not split).
4. G3: share of final representatives with s >= 0.85 to a representative of
   another final cluster (<= 15 %).
   G4: share of v0.2.1 N-challenge pairs (both in this partition) in one final
   cluster (<= 5 %, legacy subset).
   G7 inputs: AMI of final clusters vs Codebook T10 and HOCOMOCO
   H14CORE-CLUSTERED on shared motifs, 200-resample bootstrap SE (the
   within-1-SE-of-best test is applied across the grid in 06_select.py).
"""
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse
from scipy.cluster.hierarchy import fcluster, linkage
from sklearn.metrics import adjusted_mutual_info_score

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "02_motif_import"))
import pma_align as pa  # noqa: E402
import pma_motif as pm  # noqa: E402

SEED, WIN, COV, NMAX, NBOOT, S_RED = 20261016, 0.05, 0.90, 40_000, 200, 0.85
PROC = Path(os.environ["PMA_MOTIF_PROCESSED"]) / "v0.3_raw_layer"
RESULT = Path(os.environ["PMA_MOTIF_RESULT"])
R = RESULT / "step3b_v03"
RAW = Path(os.environ["PMA_MOTIF_RAW"])
EVID = Path(os.environ["PMA_MOTIF_PROCESSED"]) / "annotations" / "evidence_v2" / "PMA_motif_evidence.tsv"
BLOCK = 8192


def node_meta(ids):
    nodes = pd.read_csv(R / "nodes" / "motif_nodes.tsv", sep="\t")
    md = pd.read_csv(PROC / "PMA_motif_metadata.tsv", sep="\t", low_memory=False,
                     usecols=["pma_id", "source_db", "ic_total", "independent_experiment_id", "codebook_cluster"])
    ev = pd.read_csv(EVID, sep="\t", usecols=["pma_id", "evidence_tier"])
    x = nodes.merge(md, on="pma_id").merge(ev, on="pma_id", how="left")
    x["high"] = x.evidence_tier.le(2)  # evidence v2 tier 1 (in vitro) or 2 (curated core)
    g = x.groupby("node_id")
    t = pd.DataFrame({
        "high": g.high.any(),
        "n_exp": g.independent_experiment_id.agg(lambda s: s.fillna("").replace("", np.nan).nunique()),
        "ic": g.ic_total.max(),
        "family": g.source_db.agg(lambda s: s.value_counts().sort_index().idxmax()),
    }).reindex(ids)
    return t, nodes, x


def rank_key(t):
    """Smaller is better: high-evidence, more experiments, higher IC, node ID."""
    return pd.DataFrame({"h": ~t.high.to_numpy(), "e": -t.n_exp.to_numpy(), "i": -t.ic.to_numpy(),
                         "n": t.index.to_numpy()})


def community_means(F, labs):
    """labs: list of int label arrays (n,) -> list of (n_comm x d) mean matrices."""
    sums = [np.zeros((lab.max() + 1, F.shape[1]), dtype=np.float64) for lab in labs]
    for a in range(0, F.shape[0], BLOCK):
        X = np.asarray(F[a:a + BLOCK], dtype=np.float32)
        for s, lab in zip(sums, labs):
            l = lab[a:a + BLOCK]
            oh = sparse.csr_matrix((np.ones(len(l), np.float32), (l, np.arange(len(l)))), shape=(s.shape[0], len(l)))
            s += oh @ X
    return [s / np.bincount(lab)[:, None] for s, lab in zip(sums, labs)]


def mean_corr(F, labs, means):
    out = [np.empty(F.shape[0]) for _ in labs]
    for a in range(0, F.shape[0], BLOCK):
        X = np.asarray(F[a:a + BLOCK], dtype=np.float64)
        for o, lab, m in zip(out, labs, means):
            o[a:a + BLOCK] = (X * m[lab[a:a + BLOCK]]).sum(1)
    return out


def pick(members, corr, key):
    best = corr[members].max()
    cand = members[corr[members] >= best - WIN]
    k = key.iloc[cand]
    return int(cand[np.lexsort((k.n, k.i, k.e, k.h))[0]])


def ami_boot(ref, lab, rng):
    a = adjusted_mutual_info_score(ref, lab)
    n = len(ref)
    bs = [adjusted_mutual_info_score(ref[i], lab[i]) for i in (rng.integers(0, n, n) for _ in range(NBOOT))]
    return float(a), float(np.std(bs, ddof=1))


def main(part, rep, dims):
    out = R / "gates"
    out.mkdir(parents=True, exist_ok=True)
    tau = json.loads((R / "tau_calibration" / "tau.json").read_text())
    assert tau["status"] == "ok", tau
    tau = float(tau["tau"])
    ids = pd.read_csv(R / "pca" / f"nodes_{part}.tsv", sep="\t").node_id.to_numpy()
    idx = {n: i for i, n in enumerate(ids)}
    F = np.load(R / "pca" / f"features_{part}.f16", mmap_mode="r")
    assert F.shape[0] == len(ids)
    mats = {n: m for n, p, m in pm.read_meme(R / "nodes" / "nodes.meme") if p == part}
    Z, Zrc, st, ln = pa.pack([mats[n] for n in ids])
    meta, nodes, mx = node_meta(ids)
    key = rank_key(meta)
    fam = meta.family.to_numpy()

    grid = pd.read_csv(R / "grid" / f"grid_{part}_{rep}_d{dims}.tsv.gz", sep="\t", dtype=str)
    grid = grid.set_index("node_id").reindex(ids)
    cfgs = list(grid.columns)
    labs = [pd.factorize(grid[c])[0] for c in cfgs]
    means = community_means(F, labs)
    corrs = mean_corr(F, labs, means)
    del means

    # references for G4 / G7 (motif level -> node)
    node_of = dict(zip(nodes.pma_id, nodes.node_id))
    bp = pd.read_csv(RESULT / "step2_motif_import" / "benchmark" / "benchmark_pairs.tsv", sep="\t", dtype=str)
    nch = bp[bp["set"] == "N_challenge"]
    nch = nch.assign(a=nch.m1.map(node_of).map(idx), b=nch.m2.map(node_of).map(idx)).dropna(subset=["a", "b"])
    na, nb = nch.a.astype(int).to_numpy(), nch.b.astype(int).to_numpy()
    cb = mx[mx.codebook_cluster.notna() & mx.node_id.isin(idx)]
    cb_ref, cb_node = cb.codebook_cluster.astype(str).to_numpy(), cb.node_id.map(idx).to_numpy()
    hc = pd.read_csv(RAW / "hocomoco_v14" / "2026-10-14" / "H14CORE-CLUSTERED_cluster_list.tsv", sep="\t")
    h14 = {f"HO14_{m.strip()}": r for r, ms in zip(hc.Representative_Motif, hc.Clustered_Motifs) for m in ms.split(";")}
    ho = pd.DataFrame({"pma_id": list(h14), "ref": list(h14.values())})
    ho["node"] = ho.pma_id.map(node_of).map(idx)
    ho = ho.dropna(subset=["node"])
    ho_ref, ho_node = ho.ref.to_numpy(), ho.node.astype(int).to_numpy()

    rows, finals = [], {"node_id": ids}
    for c, lab, corr in zip(cfgs, labs, corrs):
        ncomm = lab.max() + 1
        order = np.argsort(lab, kind="stable")
        bounds = np.r_[0, np.cumsum(np.bincount(lab, minlength=ncomm))]
        reps = np.array([pick(order[bounds[k]:bounds[k + 1]], corr, key) for k in range(ncomm)])
        cov_s = pa.s_pairs(Z, Zrc, st, ln, reps[lab].astype(np.int64), np.arange(len(ids), dtype=np.int64))
        covered = cov_s >= tau
        ccov = np.bincount(lab, weights=covered, minlength=ncomm) / np.bincount(lab, minlength=ncomm)
        g1 = float((ccov >= COV).mean())
        fam_cov = pd.Series(covered).groupby(fam).agg(["mean", "size"])
        major = fam_cov[fam_cov["size"] >= 1000]
        g2 = float(covered.mean())
        # single split
        final = lab.astype(np.int64).copy()
        final_rep = reps[lab].copy()
        nxt, limited, nsplit, frag = ncomm, [], 0, []
        for k in np.flatnonzero(ccov < COV):
            mem = order[bounds[k]:bounds[k + 1]]
            if len(mem) > NMAX:
                limited.append(int(len(mem)))
                continue
            a, b = np.triu_indices(len(mem), 1)
            s = pa.s_pairs(Z, Zrc, st, ln, mem[a].astype(np.int64), mem[b].astype(np.int64))
            sub = fcluster(linkage(1.0 - s, "complete"), 1.0 - tau, "distance")
            nsplit += 1
            frag.append(int(sub.max()))
            for u in np.unique(sub):
                mm = mem[sub == u]
                cm = np.asarray(F[np.sort(mm)], dtype=np.float64)
                cm_mean = cm.mean(0)
                lc = np.empty(len(ids))
                lc[np.sort(mm)] = cm @ cm_mean
                r = pick(mm, lc, key)
                final[mm] = nxt
                final_rep[mm] = r
                nxt += 1
            chk = pa.s_pairs(Z, Zrc, st, ln, final_rep[mem].astype(np.int64), mem.astype(np.int64))
            assert (chk >= tau - 1e-9).all(), f"{c}: post-split coverage < 100 % in community {k}"
        final = pd.factorize(final)[0]
        fr = np.unique(final_rep)
        fr_lab = final[fr]
        a, b = np.triu_indices(len(fr), 1)
        rs = pa.s_pairs(Z, Zrc, st, ln, fr[a].astype(np.int64), fr[b].astype(np.int64))
        hit = (rs >= S_RED) & (fr_lab[a] != fr_lab[b])
        red = np.zeros(len(fr), bool)
        red[a[hit]] = red[b[hit]] = True
        g4 = float((final[na] == final[nb]).mean()) if len(na) else np.nan
        rng = np.random.default_rng(SEED)
        ami_cb, se_cb = ami_boot(cb_ref, final[cb_node], rng) if len(cb_ref) else (np.nan, np.nan)
        ami_ho, se_ho = ami_boot(ho_ref, final[ho_node], rng) if len(ho_ref) else (np.nan, np.nan)
        rows.append(dict(config=c, part=part, rep=rep, dims=dims, n_nodes=len(ids), K_louvain=int(ncomm),
                         K_final=int(final.max() + 1), communities_split=nsplit,
                         fragmentation_mean=float(np.mean(frag)) if frag else 1.0,
                         compute_limited=";".join(map(str, limited)),
                         G1=g1, G1_pass=g1 >= 0.80, G2=g2,
                         G2_min_major_family=float(major["mean"].min()) if len(major) else np.nan,
                         G2_pass=bool(g2 >= 0.90 and (major["mean"] >= 0.85).all()),
                         G3=float(red.mean()), G3_pass=bool(red.mean() <= 0.15),
                         G4=g4, G4_n=int(len(na)), G4_pass=bool(np.isnan(g4) or g4 <= 0.05),
                         AMI_codebook=ami_cb, AMI_codebook_se=se_cb, n_codebook=int(len(cb_ref)),
                         AMI_hocomoco=ami_ho, AMI_hocomoco_se=se_ho, n_hocomoco=int(len(ho_ref)),
                         family_coverage=json.dumps(fam_cov["mean"].round(4).to_dict())))
        finals[f"{c}|louvain"] = lab
        finals[f"{c}|covered_presplit"] = covered.astype(np.int8)
        finals[f"{c}|cluster"] = final
        finals[f"{c}|rep"] = ids[final_rep]
        print(c, rows[-1]["K_louvain"], rows[-1]["K_final"], round(g1, 3), round(g2, 3),
              round(rows[-1]["G3"], 3), g4, flush=True)
    pd.DataFrame(rows).to_csv(out / f"gates_{part}_{rep}_d{dims}.tsv", sep="\t", index=False, float_format="%.6g")
    pd.DataFrame(finals).to_csv(out / f"final_{part}_{rep}_d{dims}.tsv.gz", sep="\t", index=False)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]))
