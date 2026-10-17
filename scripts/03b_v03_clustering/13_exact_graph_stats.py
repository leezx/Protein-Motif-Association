"""Step 3b §15b prerequisites: exact alignment graph statistics (before any Louvain).

usage: 13_exact_graph_stats.py
Per partition: merge align/exact_<part>_*of*.npz, assert completeness
(pairs computed == n(n-1)/2), write align/edges_<part>_kexact.tsv.gz (i, j, s) for
11_align_louvain.R, and report edges, degree distribution (top-degree nodes with
their TF / source), connected components, isolated_at_s065 nodes and K_min.
Legacy concordance (v0.2.1 nodes): for each node, its top-1 / top-10 TOMTOM-
supported matches (Step 3 edges.tsv.gz, ranked by TOMTOM-aligned s) - share
present as exact edges (s >= 0.65) and share with exact s >= tau, stratified by
source family, length and IC.
Outputs: align/exact_graph_summary.json, align/exact_degree_top.tsv,
align/exact_concordance.tsv
"""
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse
from scipy.sparse.csgraph import connected_components

M = Path(os.environ["PMA_MOTIF_RESULT"])
R = M / "step3b_v03"
A = R / "align"
PROC = Path(os.environ["PMA_MOTIF_PROCESSED"])
TAU = float(json.loads((R / "tau_calibration" / "tau.json").read_text())["tau"])


def main():
    nodes = pd.read_csv(R / "nodes" / "motif_nodes.tsv", sep="\t")
    md = pd.read_csv(PROC / "v0.3_raw_layer" / "PMA_motif_metadata.tsv", sep="\t", low_memory=False,
                     usecols=["pma_id", "source_db", "motif_tf_assignment", "length", "ic_mean"])
    nm = nodes.merge(md, on="pma_id")
    nmeta = nm.groupby("node_id").agg(source=("source_db", lambda s: s.value_counts().sort_index().idxmax()),
                                      tf=("motif_tf_assignment", lambda s: ";".join(sorted(set(s.dropna().astype(str))))[:60]),
                                      length=("length", "first"), ic=("ic_mean", "first"), n_motifs=("pma_id", "size"))
    out, deg_rows, conc = {"tau": TAU}, [], []
    e3 = pd.read_csv(M / "step3_motif_clustering" / "edges.tsv.gz", sep="\t", usecols=["a", "b", "s"], dtype={"a": str, "b": str})
    for part in ("composite", "monomer"):
        ids = pd.read_csv(R / "pca" / f"nodes_{part}.tsv", sep="\t").node_id.to_numpy()
        n = len(ids)
        files = sorted(A.glob(f"exact_{part}_*of*.npz"))
        z = [np.load(f) for f in files]
        nch = int(files[0].name.split("of")[1].split(".")[0])
        assert len(files) == nch, (part, files)
        computed = sum(int(x["computed"]) for x in z)
        assert computed == n * (n - 1) // 2, (part, computed, n * (n - 1) // 2)
        q = np.concatenate([x["q"] for x in z]).astype(np.int64)
        t = np.concatenate([x["t"] for x in z]).astype(np.int64)
        s = np.concatenate([x["s"] for x in z])
        assert (q < t).all()
        pd.DataFrame({"i": q, "j": t, "s": s}).to_csv(A / f"edges_{part}_kexact.tsv.gz", sep="\t", index=False,
                                                      float_format="%.5g")
        deg = np.bincount(q, minlength=n) + np.bincount(t, minlength=n)
        deg825 = np.bincount(q[s >= TAU], minlength=n) + np.bincount(t[s >= TAU], minlength=n)
        g = sparse.coo_matrix((np.ones(len(q)), (q, t)), shape=(n, n))
        ncomp, lab = connected_components(g, directed=False)
        sizes = np.bincount(lab)
        iso = deg == 0
        out[part] = dict(nodes=n, pairs_computed=computed, edges_s065=int(len(q)), edges_tau=int((s >= TAU).sum()),
                         components=int(ncomp), isolated_at_s065=int(iso.sum()), largest_component=int(sizes.max()),
                         components_ge2=int((sizes >= 2).sum()),
                         degree_quantiles={str(k): float(v) for k, v in
                                           zip([.5, .9, .99, .999, 1.0], np.quantile(deg, [.5, .9, .99, .999, 1.0]))},
                         isolated_by_source=nmeta.reindex(ids[iso]).source.value_counts().to_dict())
        top = np.argsort(-deg)[:50]
        d = nmeta.reindex(ids[top]).reset_index()
        d.insert(0, "partition", part)
        d["degree_s065"], d["degree_tau"] = deg[top], deg825[top]
        deg_rows.append(d)
        # legacy concordance on v0.2.1 nodes of this partition
        idx = {x: i for i, x in enumerate(ids)}
        e = e3[e3.a.isin(idx) & e3.b.isin(idx)].copy()
        e["i"], e["j"] = e.a.map(idx), e.b.map(idx)
        key = pd.Series(s, index=np.minimum(q, t) * n + np.maximum(q, t))
        e["k"] = np.minimum(e.i, e.j).astype(np.int64) * n + np.maximum(e.i, e.j)
        e["s_exact"] = key.reindex(e.k).to_numpy()
        both = pd.concat([e.rename(columns={"i": "node"}), e.rename(columns={"j": "node"})])
        both = both.sort_values(["node", "s"], ascending=[True, False])
        both["rank"] = both.groupby("node").cumcount() + 1
        meta = nmeta.reindex(ids[both.node.to_numpy()])
        both["source"] = meta.source.to_numpy()
        both["len_bin"] = pd.cut(meta.length.to_numpy(), [0, 8, 12, 16, 20, 1000]).astype(str)
        both["ic_q"] = pd.qcut(meta.ic.to_numpy(), 4, labels=["q1", "q2", "q3", "q4"], duplicates="drop").astype(str)
        for topk in (1, 10):
            b = both[both["rank"] <= topk]
            for col in ("all", "source", "len_bin", "ic_q"):
                grp = [("all", b)] if col == "all" else list(b.groupby(col))
                for gname, gb in grp:
                    conc.append(dict(part=part, top=topk, stratum_type=col, stratum=gname, n=len(gb),
                                     edge_s065=float(gb.s_exact.notna().mean()),
                                     exact_ge_tau=float((gb.s_exact >= TAU).mean())))
        print(part, json.dumps(out[part])[:600], flush=True)
    out["K_min_total"] = out["composite"]["components"] + out["monomer"]["components"]
    out["tier_feasible"] = {t: out["K_min_total"] <= k for t, k in (("LOW", 500), ("MEDIUM", 1000), ("HIGH", 2000))}
    (A / "exact_graph_summary.json").write_text(json.dumps(out, indent=2, default=int) + "\n")
    pd.concat(deg_rows).to_csv(A / "exact_degree_top.tsv", sep="\t", index=False)
    c = pd.DataFrame(conc)
    c.to_csv(A / "exact_concordance.tsv", sep="\t", index=False, float_format="%.4f")
    print(json.dumps({k: out[k] for k in ("K_min_total", "tier_feasible")}))
    print(c[c.stratum_type == "all"].to_string(index=False))


if __name__ == "__main__":
    main()
