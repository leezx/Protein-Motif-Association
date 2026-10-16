"""Step 3 §3.3: fine clusters + archetypes over the pre-registered grid, and
the pre-registered cut selection (F28: guardrails, not calibrated metrics).

Per partition and connected component of the edge graph: average linkage,
fine floor 0.50, archetype floor 0.30 (pma_cluster.cluster_component).
Outputs ($PMA_MOTIF_RESULT/step3_motif_clustering/clustering/):
  node_clusters_grid.tsv.gz  node -> fine/archetype label per grid point
  grid_metrics.tsv           per grid point guardrail metrics
  cut_selection.json         selection trace and chosen cuts
"""
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pma_cluster as pc  # noqa: E402

R = Path(os.environ["PMA_MOTIF_RESULT"]) / "step3_motif_clustering"
BENCH = Path(os.environ["PMA_MOTIF_RESULT"]) / "step2_motif_import" / "benchmark" / "benchmark_pairs.tsv"
OUT = R / "clustering"
C_FINE = (0.80, 0.85, 0.90)
C_ARCH = (0.65, 0.70, 0.75)
DEFAULT = (0.85, 0.70)
# pre-registered guardrails (§3.3, F28)
# size guardrail in distinct sequence-specific HGNC TFs (amendment
# 2026-10-16, before results: node counts are dominated by repeated
# profiles of one TF, e.g. CTCF 1,636 nodes); node fraction is descriptive.
FINE_NCHAL, FINE_MAXTF = 0.05, 50
ARCH_NCHAL, ARCH_MAXTF = 0.10, 100
LAYER = os.environ.get("PMA_RAW_LAYER", "v0.2.1")
PROC = Path(os.environ["PMA_MOTIF_PROCESSED"]) / f"{LAYER}_raw_layer"
MASTER = Path(os.environ["PMA_MOTIF_RAW"]) / "hocomoco_v14" / "2026-10-14" / "tf_masterlist.tsv"


def components(nodes, edges):
    i = {n: k for k, n in enumerate(nodes)}
    a, b = edges.a.map(i).to_numpy(dtype=int), edges.b.map(i).to_numpy(dtype=int)
    g = coo_matrix((np.ones(len(a)), (a, b)), shape=(len(nodes), len(nodes)))
    return connected_components(g, directed=False)[1], i


def cluster_partition(nodes, edges):
    """Returns {(cf, ca): (fine_labels, arch_labels)} with global labels and
    the realised minimum pair similarities per cluster (for assertions)."""
    if not nodes:
        return {(cf, ca): [np.zeros(0, int), np.zeros(0, int), 0, 0, 1.0, 1.0] for cf in C_FINE for ca in C_ARCH}
    comp, i = components(nodes, edges)
    a, b, s = edges.a.map(i).to_numpy(dtype=int), edges.b.map(i).to_numpy(dtype=int), edges.s.to_numpy()
    ecomp = comp[a]
    res = {(cf, ca): [np.full(len(nodes), -1), np.full(len(nodes), -1), 0, 0, 1.0, 1.0]
           for cf in C_FINE for ca in C_ARCH}
    order = np.argsort(ecomp, kind="mergesort")
    bounds = np.searchsorted(ecomp[order], np.arange(comp.max() + 2))
    for c in range(comp.max() + 1):
        idx = np.flatnonzero(comp == c)
        loc = np.empty(len(nodes), int)
        loc[idx] = np.arange(len(idx))
        S = np.zeros((len(idx), len(idx)))
        np.fill_diagonal(S, 1.0)
        e = order[bounds[c]:bounds[c + 1]]
        ia, ib = loc[a[e]], loc[b[e]]
        S[ia, ib] = S[ib, ia] = s[e]
        for (cf, ca), r in res.items():
            f, ar = pc.cluster_component(S, cf, ca)
            for lab, k, mi in ((f, 0, 4), (ar, 1, 5)):
                for u in np.unique(lab):
                    r[mi] = min(r[mi], pc.min_pair(S, np.flatnonzero(lab == u)))
                r[k][idx] = lab + r[k + 2]
                r[k + 2] += lab.max() + 1
    return res


def max_tfs(lab_by_node, node_tfs):
    """Largest number of distinct sequence-specific TFs in one cluster."""
    d = pd.DataFrame({"lab": lab_by_node.reindex(node_tfs.index).to_numpy(), "tf": node_tfs.to_numpy()})
    d = d.explode("tf").dropna()
    return int(d.groupby("lab").tf.nunique().max()) if len(d) else 0


def node_tf_sets(mn):
    md = pd.read_csv(PROC / "PMA_motif_metadata.tsv", sep="\t", keep_default_na=False, low_memory=False)
    links = pd.read_csv(PROC / "PMA_motif_tf_links.tsv", sep="\t", keep_default_na=False)
    ml = pd.read_csv(MASTER, sep="\t", keep_default_na=False)
    tfs = pc.sequence_specific_tfs(md, links, ml)
    lk = links[links.tf_hgnc.isin(tfs)].merge(mn[["pma_id", "node_id"]], on="pma_id")
    return lk.groupby("node_id").tf_hgnc.apply(lambda s: sorted(set(s)))


def coclustered(lab_by_node, pairs, node_of):
    m1, m2 = pairs.m1.map(node_of), pairs.m2.map(node_of)
    ok = m1.isin(lab_by_node.index) & m2.isin(lab_by_node.index)
    same = lab_by_node.reindex(m1[ok]).to_numpy() == lab_by_node.reindex(m2[ok]).to_numpy()
    return float(same.mean()) if ok.any() else float("nan"), int(ok.sum())


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    mn = pd.read_csv(R / "nodes" / "motif_nodes.tsv", sep="\t", keep_default_na=False)
    mn["unclusterable"] = mn.unclusterable.astype(str).eq("True")
    nodes = mn[~mn.unclusterable].drop_duplicates("node_id")[["node_id", "partition"]]
    edges = pd.read_csv(R / "edges.tsv.gz", sep="\t")
    n_all = len(nodes)
    lab = {k: [[], []] for k in ((cf, ca) for cf in C_FINE for ca in C_ARCH)}
    minpair = {}
    ids = []
    for p in ("monomer", "composite"):
        nd = nodes[nodes.partition == p].node_id.tolist()
        res = cluster_partition(nd, edges[edges.partition == p])
        ids += nd
        for k, (f, ar, nf, na, mf, ma) in res.items():
            off_f = sum(len(set(x)) for x in lab[k][0]) if lab[k][0] else 0
            off_a = sum(len(set(x)) for x in lab[k][1]) if lab[k][1] else 0
            lab[k][0].append(f + off_f)
            lab[k][1].append(ar + off_a)
            pf, pa = minpair.get(k, (1.0, 1.0))
            minpair[k] = (min(pf, mf), min(pa, ma))
    grid = pd.DataFrame({"node_id": ids})
    for (cf, ca), (f, ar) in lab.items():
        grid[f"fine_{cf:.2f}_{ca:.2f}"] = np.concatenate(f)
        grid[f"arch_{cf:.2f}_{ca:.2f}"] = np.concatenate(ar)
    grid.to_csv(OUT / "node_clusters_grid.tsv.gz", sep="\t", index=False)

    pairs = pd.read_csv(BENCH, sep="\t", keep_default_na=False)
    node_of = mn.set_index("pma_id").node_id
    g = grid.set_index("node_id")
    ntf = node_tf_sets(mn)
    rows = []
    for (cf, ca) in lab:
        f, ar = g[f"fine_{cf:.2f}_{ca:.2f}"], g[f"arch_{cf:.2f}_{ca:.2f}"]
        row = dict(c_fine=cf, c_arch=ca, nodes=n_all, n_fine=f.nunique(), n_arch=ar.nunique(),
                   max_fine_frac=f.value_counts().iloc[0] / n_all, max_arch_frac=ar.value_counts().iloc[0] / n_all,
                   max_fine_tfs=max_tfs(f, ntf), max_arch_tfs=max_tfs(ar, ntf),
                   min_pair_fine=minpair[(cf, ca)][0], min_pair_arch=minpair[(cf, ca)][1])
        for st in ("N_challenge", "P_high", "P_provisional"):
            sub = pairs[pairs.set == st]
            row[f"{st}_fine"], row[f"{st}_n"] = coclustered(f, sub, node_of)
            row[f"{st}_arch"], _ = coclustered(ar, sub, node_of)
        rows.append(row)
    gm = pd.DataFrame(rows)
    gm.to_csv(OUT / "grid_metrics.tsv", sep="\t", index=False, float_format="%.4f")
    # F25: realised floors over all member pairs
    assert (gm.min_pair_fine >= pc.FINE_FLOOR - 1e-9).all() and (gm.min_pair_arch >= pc.ARCH_FLOOR - 1e-9).all()

    # pre-registered selection: default, then one step more conservative per failure
    trace = []
    gi = gm.set_index(["c_fine", "c_arch"])

    def fine_fail(cf):
        r = gi.loc[(cf, DEFAULT[1])]
        return [x for x, bad in (("N_challenge", r.N_challenge_fine > FINE_NCHAL),
                                 ("largest", r.max_fine_tfs > FINE_MAXTF)) if bad]

    cf = DEFAULT[0]
    while True:
        why = fine_fail(cf)
        trace.append(dict(level="fine", cut=cf, failures=why))
        if not why or cf == C_FINE[-1]:
            break
        cf = C_FINE[C_FINE.index(cf) + 1]
    fine_pass = not fine_fail(cf)
    ca = DEFAULT[1]
    while True:
        r = gi.loc[(cf, ca)]
        why = [x for x, bad in (("N_challenge", r.N_challenge_arch > ARCH_NCHAL),
                                ("largest", r.max_arch_tfs > ARCH_MAXTF)) if bad]
        trace.append(dict(level="archetype", cut=ca, failures=why))
        if not why or ca == C_ARCH[-1]:
            break
        ca = C_ARCH[C_ARCH.index(ca) + 1]
    sel = dict(c_fine=cf, c_arch=ca, fine_guardrails_pass=fine_pass, arch_guardrails_pass=not why, trace=trace)
    (OUT / "cut_selection.json").write_text(json.dumps(sel, indent=2) + "\n")
    print(gm.to_string(index=False))
    print(json.dumps(sel, indent=2))


if __name__ == "__main__":
    main()
